import logging
from typing import Dict, List, Tuple, Optional, Any
import os
import numpy as np
import pandas as pd
import networkx as nx
from torch_geometric.data import Data
from torch_geometric.utils import from_networkx
import torch
import torch.nn as nn
from torch_geometric.nn import GATConv, GraphSAGE
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class TransactionGraphBuilder:
    """Build transaction graph from transaction data"""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.node_features = {}
        self.scaler = StandardScaler()

    def add_transaction(self, transaction: Dict[str, Any]):
        """Add transaction to graph"""
        sender = transaction['sender_account']
        receiver = transaction['receiver_account']
        amount = transaction['amount']
        timestamp = transaction['timestamp']

        # Add nodes if not exist
        for account in [sender, receiver]:
            if account not in self.graph:
                self.graph.add_node(account, type='account')
                self.node_features[account] = {
                    'transaction_count': 0,
                    'total_amount': 0.0,
                    'avg_amount': 0.0,
                    'degree': 0
                }

        # Add edge
        self.graph.add_edge(sender, receiver, amount=amount, timestamp=timestamp)

        # Update node features
        self.node_features[sender]['transaction_count'] += 1
        self.node_features[sender]['total_amount'] += amount
        self.node_features[sender]['avg_amount'] = (
            self.node_features[sender]['total_amount'] / self.node_features[sender]['transaction_count']
        )
        self.node_features[sender]['degree'] = self.graph.degree(sender)

        self.node_features[receiver]['transaction_count'] += 1
        self.node_features[receiver]['total_amount'] += amount
        self.node_features[receiver]['avg_amount'] = (
            self.node_features[receiver]['total_amount'] / self.node_features[receiver]['transaction_count']
        )
        self.node_features[receiver]['degree'] = self.graph.degree(receiver)

    def build_pyg_data(self) -> Data:
        """Convert NetworkX graph to PyG Data"""
        # Node features
        nodes = list(self.graph.nodes())
        node_features = []
        for node in nodes:
            features = self.node_features[node]
            node_features.append([
                features['transaction_count'],
                features['total_amount'],
                features['avg_amount'],
                features['degree']
            ])

        x = torch.tensor(node_features, dtype=torch.float)

        # Scale features
        x = torch.tensor(self.scaler.fit_transform(x.numpy()), dtype=torch.float)

        # Edges
        edges = list(self.graph.edges())
        edge_index = torch.tensor([[nodes.index(u), nodes.index(v)] for u, v in edges], dtype=torch.long).t()

        # Edge features (amount, timestamp encoded)
        edge_features = []
        for u, v in edges:
            edge_data = self.graph[u][v]
            amount = edge_data['amount']
            # Simple timestamp encoding (could be more sophisticated)
            timestamp = pd.to_datetime(edge_data['timestamp']).timestamp()
            edge_features.append([amount, timestamp])

        edge_attr = torch.tensor(edge_features, dtype=torch.float)

        return Data(x=x, edge_index=edge_index, edge_attr=edge_attr)

    def get_graph_metrics(self) -> Dict[str, Any]:
        """Get graph-level metrics"""
        return {
            'num_nodes': self.graph.number_of_nodes(),
            'num_edges': self.graph.number_of_edges(),
            'density': nx.density(self.graph),
            'avg_clustering': nx.average_clustering(self.graph),
            'is_connected': nx.is_weakly_connected(self.graph) if self.graph.number_of_nodes() > 0 else False
        }

class FraudGNN(nn.Module):
    """Graph Neural Network for fraud detection"""

    def __init__(self, num_node_features: int, hidden_channels: int = 64, num_classes: int = 1):
        super().__init__()
        self.conv1 = GraphSAGE(num_node_features, hidden_channels, num_layers=2)
        self.conv2 = GraphSAGE(hidden_channels, hidden_channels, num_layers=1)
        self.classifier = nn.Linear(hidden_channels, num_classes)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x, edge_index)
        x = torch.relu(x)
        x = self.conv2(x, edge_index)
        x = torch.relu(x)
        return self.classifier(x).squeeze()

class GATFraudGNN(nn.Module):
    """GAT-based GNN for fraud detection"""

    def __init__(self, num_node_features: int, hidden_channels: int = 64, num_classes: int = 1):
        super().__init__()
        self.conv1 = GATConv(num_node_features, hidden_channels, heads=8, dropout=0.6)
        self.conv2 = GATConv(hidden_channels * 8, hidden_channels, heads=1, concat=False, dropout=0.6)
        self.classifier = nn.Linear(hidden_channels, num_classes)

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        x = self.conv1(x, edge_index)
        x = torch.relu(x)
        x = self.conv2(x, edge_index)
        x = torch.relu(x)
        return self.classifier(x).squeeze()

class TransactionGNNPredictor:
    """GNN-based fraud predictor"""

    def __init__(self, model_type: str = "graphsage", use_gpu: bool = True):
        self.model_type = model_type
        self.use_gpu = use_gpu and torch.cuda.is_available()
        self.device = torch.device("cuda" if self.use_gpu else "cpu")
        self.model = None
        self.graph_builder = TransactionGraphBuilder()
        self.trained = False

    def build_model(self, num_features: int):
        """Initialize GNN model"""
        if self.model_type == "graphsage":
            self.model = FraudGNN(num_features).to(self.device)
        elif self.model_type == "gat":
            self.model = GATFraudGNN(num_features).to(self.device)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def add_transactions(self, transactions: List[Dict[str, Any]]):
        """Add multiple transactions to graph"""
        for txn in transactions:
            self.graph_builder.add_transaction(txn)

    def train(self, labels: Dict[str, int], epochs: int = 100, lr: float = 0.01):
        """Train GNN on labeled data"""
        if self.model is None:
            pyg_data = self.graph_builder.build_pyg_data()
            self.build_model(pyg_data.x.shape[1])

        pyg_data = self.graph_builder.build_pyg_data()

        # Create labels tensor (only for nodes that have labels)
        nodes = list(self.graph_builder.graph.nodes())
        y = torch.zeros(len(nodes), dtype=torch.float)
        train_mask = torch.zeros(len(nodes), dtype=torch.bool)

        for i, node in enumerate(nodes):
            if node in labels:
                y[i] = labels[node]
                train_mask[i] = True

        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.BCEWithLogitsLoss()

        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            out = self.model(pyg_data.x.to(self.device), pyg_data.edge_index.to(self.device))
            loss = criterion(out[train_mask], y[train_mask].to(self.device))
            loss.backward()
            optimizer.step()

            if epoch % 20 == 0:
                logger.info(f"GNN Epoch {epoch}, Loss: {loss.item():.4f}")

        self.trained = True

    def predict_node(self, account_id: str) -> Optional[float]:
        """Predict fraud probability for a specific account"""
        if not self.trained:
            return None

        pyg_data = self.graph_builder.build_pyg_data()
        nodes = list(self.graph_builder.graph.nodes())

        if account_id not in nodes:
            return None

        node_idx = nodes.index(account_id)

        self.model.eval()
        with torch.no_grad():
            out = self.model(pyg_data.x.to(self.device), pyg_data.edge_index.to(self.device))
            prob = torch.sigmoid(out[node_idx]).item()

        return prob

    def predict_transaction(self, transaction: Dict[str, Any]) -> float:
        """Predict fraud probability for a transaction based on sender/receiver"""
        sender_prob = self.predict_node(transaction['sender_account']) or 0.5
        receiver_prob = self.predict_node(transaction['receiver_account']) or 0.5

        # Simple combination - could be more sophisticated
        return (sender_prob + receiver_prob) / 2

    def get_graph_features(self, account_id: str) -> Dict[str, Any]:
        """Get graph-based features for an account"""
        if account_id not in self.graph_builder.graph:
            return {
                'pagerank': 0.0,
                'in_degree': 0,
                'out_degree': 0,
                'clustering_coeff': 0.0
            }

        graph = self.graph_builder.graph

        # PageRank
        pagerank = nx.pagerank(graph).get(account_id, 0.0)

        # Degrees
        in_degree = graph.in_degree(account_id)
        out_degree = graph.out_degree(account_id)

        # Clustering coefficient
        clustering = nx.clustering(graph, account_id)

        return {
            'pagerank': pagerank,
            'in_degree': in_degree,
            'out_degree': out_degree,
            'clustering_coeff': clustering
        }

    def save_model(self, path: str):
        """Save trained model"""
        if self.model:
            torch.save(self.model.state_dict(), f"{path}/gnn_model.pth")
            logger.info(f"GNN model saved to {path}")

    def load_model(self, path: str, num_features: int):
        """Load trained model"""
        self.build_model(num_features)
        model_path = f"{path}/gnn_model.pth"
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path))
            self.trained = True
            logger.info(f"GNN model loaded from {path}")
        else:
            logger.warning(f"Model file not found: {model_path}")