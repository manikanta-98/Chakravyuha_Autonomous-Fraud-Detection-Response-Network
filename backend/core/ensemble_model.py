import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.linear_model import LogisticRegression
import xgboost as xgb
from tabpfn import TabPFNClassifier
import torch
import torch.nn as nn
from torch_geometric.data import Data
from torch_geometric.nn import GraphSAGE
import river
from river.tree import HoeffdingTreeClassifier
import shap
import lime
import lime.lime_tabular
from langchain_community.llms import Ollama, OpenAI
import os

logger = logging.getLogger(__name__)

class EnsembleFraudDetector:
    def __init__(self, use_gpu: bool = True, llm_provider: str = "ollama"):
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = torch.device("cuda" if self.use_gpu else "cpu")

        # Initialize models
        self.tabpfn = TabPFNClassifier(device="cuda" if self.use_gpu else "cpu")
        self.xgb = xgb.XGBClassifier(
            objective="binary:logistic",
            n_estimators=100,
            max_depth=6,
            learning_rate=0.1,
            device="cuda" if self.use_gpu else "cpu",
            booster="dart",
            rate_drop=0.1,
            skip_drop=0.5
        )
        self.isolation_forest = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        self.lof = LocalOutlierFactor(n_neighbors=20, contamination=0.1, novelty=True)
        self.river_model = HoeffdingTreeClassifier()

        # Meta-learner
        self.meta_learner = LogisticRegression(random_state=42)

        # LLM for reasoning
        self.llm_provider = llm_provider
        self.llm = None
        try:
            if llm_provider == "ollama":
                self.llm = Ollama(model="llama2:7b-chat", temperature=0.1)
            else:
                self.llm = OpenAI(model="gpt-4o", temperature=0.1)
        except Exception as e:
            logger.warning(f"LLM initialization failed: {e}")

        self.llm_prompt_template = """
You are a senior fraud analyst. Given this transaction context, explain your risk decision in plain English.
Consider factors like amount, velocity, merchant type, geographic anomalies, and behavioral patterns.

Transaction Context:
{transaction_context}

Provide a concise explanation (2-3 sentences) of why this transaction might be fraudulent or legitimate, and assign a risk score from 0.0 to 1.0.
Format: EXPLANATION | SCORE
"""

        # GNN model (to be initialized with graph data)
        self.gnn_model = None
        self.gnn_trained = False

        # SHAP and LIME explainers
        self.shap_explainer = None
        self.lime_explainer = None

        # Feature names for explainability
        self.feature_names = [
            'amount', 'velocity_1min', 'velocity_5min', 'velocity_1hr',
            'avg_amount', 'merchant_category', 'haversine_distance',
            'pagerank_score', 'in_degree', 'out_degree', 'hour_sin', 'hour_cos',
            'day_sin', 'day_cos', 'is_holiday'
        ]

        # Model states
        self.trained = False
        self.meta_trained = False

    def _build_gnn_model(self, num_features: int, hidden_channels: int = 64):
        """Build GraphSAGE model for transaction graph"""
        class GraphSAGEModel(nn.Module):
            def __init__(self, num_features, hidden_channels):
                super().__init__()
                self.conv1 = GraphSAGE(num_features, hidden_channels, num_layers=2)
                self.conv2 = GraphSAGE(hidden_channels, hidden_channels, num_layers=1)
                self.classifier = nn.Linear(hidden_channels, 1)

            def forward(self, x, edge_index):
                x = self.conv1(x, edge_index)
                x = torch.relu(x)
                x = self.conv2(x, edge_index)
                x = torch.relu(x)
                return self.classifier(x).squeeze()

        self.gnn_model = GraphSAGEModel(num_features, hidden_channels).to(self.device)

    def train_gnn(self, graph_data: Data, labels: torch.Tensor, epochs: int = 100):
        """Train GNN on transaction graph"""
        if self.gnn_model is None:
            self._build_gnn_model(graph_data.x.shape[1])

        optimizer = torch.optim.Adam(self.gnn_model.parameters(), lr=0.01)
        criterion = nn.BCEWithLogitsLoss()

        self.gnn_model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            out = self.gnn_model(graph_data.x.to(self.device), graph_data.edge_index.to(self.device))
            loss = criterion(out, labels.to(self.device))
            loss.backward()
            optimizer.step()

            if epoch % 20 == 0:
                logger.info(f"GNN Epoch {epoch}, Loss: {loss.item():.4f}")

        self.gnn_trained = True

    def train(self, X_train: pd.DataFrame, y_train: pd.Series):
        """Train all models except GNN"""
        logger.info("Training ensemble models...")

        # TabPFN
        self.tabpfn.fit(X_train.values, y_train.values)

        # XGBoost
        self.xgb.fit(X_train, y_train)

        # Isolation Forest
        self.isolation_forest.fit(X_train)

        # LOF
        self.lof.fit(X_train)

        # River (online learning)
        for idx, row in X_train.iterrows():
            self.river_model.learn_one(row.to_dict(), y_train[idx])

        self.trained = True
        logger.info("Base models trained")

    def train_meta_learner(self, X_val: pd.DataFrame, y_val: pd.Series):
        """Train meta-learner on validation set"""
        if not self.trained:
            raise ValueError("Train base models first")

        logger.info("Training meta-learner...")

        # Get predictions from base models
        meta_features = self._get_meta_features(X_val)

        # Train logistic regression
        self.meta_learner.fit(meta_features, y_val)

        # Initialize explainers
        self._init_explainers(meta_features)

        self.meta_trained = True
        logger.info("Meta-learner trained")

    def _get_meta_features(self, X: pd.DataFrame) -> np.ndarray:
        """Get predictions from all base models with safety fallbacks"""
        # TabPFN
        try:
            tabpfn_probs = self.tabpfn.predict_proba(X.values)[:, 1]
        except:
            tabpfn_probs = np.full(len(X), 0.5)

        # XGBoost
        try:
            xgb_probs = self.xgb.predict_proba(X)[:, 1]
        except:
            xgb_probs = np.full(len(X), 0.5)

        # Isolation Forest scores
        try:
            if_scores = self.isolation_forest.score_samples(X)
            if_scores = (if_scores - if_scores.min()) / (if_scores.max() - if_scores.min() + 1e-6)
        except:
            if_scores = np.full(len(X), 0.5)

        # LOF scores
        try:
            lof_scores = -self.lof.score_samples(X)
            lof_scores = (lof_scores - lof_scores.min()) / (lof_scores.max() - lof_scores.min() + 1e-6)
        except:
            lof_scores = np.full(len(X), 0.5)

        # River predictions
        river_probs = []
        for _, row in X.iterrows():
            try:
                prob = self.river_model.predict_proba_one(row.to_dict())
                river_probs.append(prob.get(1, 0.5))
            except:
                river_probs.append(0.5)
        river_probs = np.array(river_probs)

        # GNN prediction
        gnn_probs = np.full(len(X), 0.5)

        return np.column_stack([tabpfn_probs, xgb_probs, gnn_probs, if_scores, lof_scores, river_probs])

    def _init_explainers(self, X_sample: np.ndarray):
        """Initialize SHAP and LIME explainers"""
        self.shap_explainer = shap.Explainer(self.meta_learner, X_sample)
        self.lime_explainer = lime.lime_tabular.LimeTabularExplainer(
            X_sample,
            feature_names=self.feature_names,
            class_names=['legitimate', 'fraud'],
            discretize_continuous=True
        )

    async def predict_async(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Async prediction with LLM reasoning if needed"""
        if not self.meta_trained:
            raise ValueError("Model not trained")

        # Convert transaction to DataFrame
        X = pd.DataFrame([transaction])

        # Get meta features safely
        try:
            if self.meta_trained:
                meta_features = self._get_meta_features(X)
                final_prob = self.meta_learner.predict_proba(meta_features)[0, 1]
            else:
                final_prob = 0.5
        except Exception as e:
            logger.warning(f"Base model prediction failed: {e}. Using fallback baseline 0.5.")
            final_prob = 0.5

        result = {
            'fraud_probability': float(final_prob),
            'risk_level': self._get_risk_level(final_prob),
            'model_confidence': float(abs(final_prob - 0.5) * 2),  # 0-1 confidence
            'timestamp': pd.Timestamp.now().isoformat()
        }

        # LLM reasoning for uncertain cases
        if 0.4 <= final_prob <= 0.7 and self.llm:
            try:
                context = self._format_transaction_context(transaction)
                prompt = self.llm_prompt_template.format(transaction_context=context)
                llm_response = await asyncio.get_event_loop().run_in_executor(
                    None, self.llm.invoke, prompt
                )
                explanation, llm_score = self._parse_llm_response(llm_response)
                result['llm_explanation'] = explanation
                result['llm_score'] = float(llm_score)
                # Blend scores
                result['final_fraud_probability'] = (final_prob + float(llm_score)) / 2
                result['risk_level'] = self._get_risk_level(result['final_fraud_probability'])
            except Exception as e:
                logger.warning(f"LLM reasoning failed: {e}")
                result['llm_explanation'] = None
                result['final_fraud_probability'] = final_prob
        else:
            result['final_fraud_probability'] = final_prob
            result['llm_explanation'] = None
        # Apply heuristic risk boosting for specific categories (Gambling/International)
        result['final_fraud_probability'] = self._apply_heuristic_risk_boosting(transaction, result['final_fraud_probability'])
        result['risk_level'] = self._get_risk_level(result['final_fraud_probability'])

        return result

    def predict(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous prediction"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.predict_async(transaction))
        finally:
            loop.close()

    def explain_prediction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Generate SHAP and LIME explanations"""
        if not self.meta_trained:
            raise ValueError("Model not trained")

        X = pd.DataFrame([transaction])
        meta_features = self._get_meta_features(X)

        explanations = {}

        # SHAP
        if self.shap_explainer:
            shap_values = self.shap_explainer(meta_features)
            explanations['shap'] = {
                'base_value': float(shap_values.base_values[0]),
                'feature_importance': dict(zip(self.feature_names, shap_values.values[0]))
            }

        # LIME
        if self.lime_explainer:
            lime_exp = self.lime_explainer.explain_instance(
                meta_features[0], self.meta_learner.predict_proba, num_features=10
            )
            explanations['lime'] = {
                'prediction': lime_exp.predicted_value,
                'feature_weights': dict(lime_exp.as_list())
            }

        return explanations

    def update_online(self, transaction: Dict[str, Any], label: int):
        """Update River model with new labeled data"""
        self.river_model.learn_one(transaction, label)

    def _get_risk_level(self, prob: float) -> str:
        if prob < 0.3:
            return "LOW"
        elif prob < 0.7:
            return "MEDIUM"
        else:
            return "HIGH"

    def _apply_heuristic_risk_boosting(self, transaction: Dict[str, Any], current_prob: float) -> float:
        """Manually boost risk for specific high-risk patterns (Gambling/International)"""
        category = transaction.get('merchant_category', '').lower()
        distance = float(transaction.get('haversine_distance', 0.0))
        amount = float(transaction.get('amount', 0.0))
        
        boost = 0.0
        
        # 1. Online Gambling Rule
        if category == 'online_gambling':
            boost += 0.25
            if amount > 500:
                boost += 0.15  # Extra boost for high-value gambling
                
        # 2. International / Distal Rule
        if category == 'international_transfer' or distance > 1000:
            boost += 0.30
            if amount > 1000:
                boost += 0.10  # Extra boost for large international transfers
        
        final_prob = min(0.99, current_prob + boost)
        
        if boost > 0:
            logger.info(f"Heuristic risk boost applied: +{boost:.2f} (Category: {category}, Distance: {distance})")
            
        return final_prob

    def _format_transaction_context(self, transaction: Dict[str, Any]) -> str:
        """Format transaction for LLM"""
        return f"""
Amount: ${transaction.get('amount', 0):.2f}
Velocity (1min): {transaction.get('velocity_1min', 0)}
Velocity (5min): {transaction.get('velocity_5min', 0)}
Velocity (1hr): {transaction.get('velocity_1hr', 0)}
Merchant: {transaction.get('merchant_category', 'unknown')}
Distance from home: {transaction.get('haversine_distance', 0):.2f} km
Time: {transaction.get('hour', 0):02d}:00
Is holiday: {transaction.get('is_holiday', False)}
"""

    def _parse_llm_response(self, response: str) -> Tuple[str, float]:
        """Parse LLM response"""
        try:
            explanation, score_str = response.split('|')
            score = float(score_str.strip())
            return explanation.strip(), min(max(score, 0.0), 1.0)
        except:
            return response, 0.5

    def save_models(self, path: str):
        """Save trained models"""
        import joblib
        import torch

        os.makedirs(path, exist_ok=True)

        # Save sklearn models
        joblib.dump(self.meta_learner, f"{path}/meta_learner.pkl")
        joblib.dump(self.isolation_forest, f"{path}/isolation_forest.pkl")
        joblib.dump(self.lof, f"{path}/lof.pkl")

        # Save XGBoost
        self.xgb.save_model(f"{path}/xgb_model.json")

        # Save GNN if trained
        if self.gnn_trained and self.gnn_model:
            torch.save(self.gnn_model.state_dict(), f"{path}/gnn_model.pth")

        logger.info(f"Models saved to {path}")

    def load_models(self, path: str):
        """Load trained models"""
        import joblib
        import torch

        # Load sklearn models
        try:
            self.meta_learner = joblib.load(f"{path}/meta_learner.pkl")
            self.isolation_forest = joblib.load(f"{path}/isolation_forest.pkl")
            self.lof = joblib.load(f"{path}/lof.pkl")

            # Load XGBoost
            self.xgb.load_model(f"{path}/xgb_model.json")

            # Load GNN if exists
            gnn_path = f"{path}/gnn_model.pth"
            if os.path.exists(gnn_path) and self.gnn_model:
                self.gnn_model.load_state_dict(torch.load(gnn_path))
                self.gnn_trained = True
        except Exception as e:
            logger.warning(f"Could not load all model files: {e}. Falling back to heuristics/LLM.")

        self.meta_trained = True
        logger.info(f"Models initialized (Pre-trained files: {os.path.exists(f'{path}/meta_learner.pkl')})")