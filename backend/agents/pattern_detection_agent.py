import asyncio
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis
from datetime import datetime, timedelta
import numpy as np
from core.gnn_model import TransactionGNNPredictor
from core.ensemble_model import EnsembleFraudDetector
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor

logger = logging.getLogger(__name__)

class PatternDetectionAgent:
    """Agent for detecting patterns using GNN and anomaly detection"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.running = False
        self.gnn_predictor = TransactionGNNPredictor()
        self.isolation_forest = IsolationForest(n_estimators=100, contamination=0.1, random_state=42)
        self.lof = LocalOutlierFactor(n_neighbors=20, contamination=0.1, novelty=True)

        # In-memory transaction buffer for graph building
        self.transaction_buffer = []
        self.buffer_size = 1000  # Process in batches

        # Feature buffer for anomaly detection
        self.feature_buffer = []
        self.anomaly_models_trained = False

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def subscribe_to_transactions(self):
        """Subscribe to raw transactions stream"""
        last_id = '0'  # Start from beginning

        while self.running:
            try:
                # Read from stream
                streams = await self.redis.xread(
                    streams={"transactions:raw": last_id},
                    count=10,
                    block=1000
                )

                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        last_id = message_id

                        transaction = json.loads(message_data[b'data'].decode('utf-8'))
                        await self.process_transaction(transaction)

                # Process buffer if full
                if len(self.transaction_buffer) >= self.buffer_size:
                    await self.process_batch()

            except Exception as e:
                logger.error(f"Error reading from Redis stream: {e}")
                await asyncio.sleep(1)

    async def process_transaction(self, transaction: Dict[str, Any]):
        """Process individual transaction"""
        # Add to buffer
        self.transaction_buffer.append(transaction)

        # Extract features for anomaly detection
        features = self._extract_features(transaction)
        self.feature_buffer.append(features)

        # Process immediately for low-latency
        enriched_transaction = await self._enrich_transaction(transaction)
        await self._publish_enriched(enriched_transaction)

    async def process_batch(self):
        """Process batch of transactions for graph analysis"""
        if not self.transaction_buffer:
            return

        logger.info(f"Processing batch of {len(self.transaction_buffer)} transactions")

        # Update GNN with new transactions
        self.gnn_predictor.add_transactions(self.transaction_buffer)

        # Train/retrain anomaly models if enough data
        if len(self.feature_buffer) >= 100 and not self.anomaly_models_trained:
            await self._train_anomaly_models()

        # Clear buffer
        self.transaction_buffer = []
        self.feature_buffer = []

    async def _enrich_transaction(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich transaction with pattern detection features"""
        enriched = transaction.copy()

        # GNN-based features
        sender = transaction['sender_account']
        receiver = transaction['receiver_account']

        gnn_sender_prob = self.gnn_predictor.predict_node(sender) or 0.5
        gnn_receiver_prob = self.gnn_predictor.predict_node(receiver) or 0.5
        gnn_transaction_prob = self.gnn_predictor.predict_transaction(transaction)

        enriched['gnn_sender_score'] = gnn_sender_prob
        enriched['gnn_receiver_score'] = gnn_receiver_prob
        enriched['gnn_transaction_score'] = gnn_transaction_prob

        # Graph features
        sender_graph_features = self.gnn_predictor.get_graph_features(sender)
        receiver_graph_features = self.gnn_predictor.get_graph_features(receiver)

        enriched['sender_pagerank'] = sender_graph_features['pagerank']
        enriched['sender_in_degree'] = sender_graph_features['in_degree']
        enriched['sender_out_degree'] = sender_graph_features['out_degree']
        enriched['sender_clustering'] = sender_graph_features['clustering_coeff']

        enriched['receiver_pagerank'] = receiver_graph_features['pagerank']
        enriched['receiver_in_degree'] = receiver_graph_features['in_degree']
        enriched['receiver_out_degree'] = receiver_graph_features['out_degree']
        enriched['receiver_clustering'] = receiver_graph_features['clustering_coeff']

        # Anomaly scores
        if self.anomaly_models_trained:
            features = self._extract_features(transaction)
            features_array = np.array([features])

            if_scores = self.isolation_forest.score_samples(features_array)
            lof_scores = -self.lof.score_samples(features_array)  # Negative decision function

            # Normalize scores
            enriched['isolation_forest_score'] = float((if_scores[0] + 1) / 2)  # -1 to 1 -> 0 to 1
            enriched['lof_score'] = float((lof_scores[0] - lof_scores.min()) / (lof_scores.max() - lof_scores.min()) if len(lof_scores) > 1 else 0.5)
        else:
            enriched['isolation_forest_score'] = 0.5
            enriched['lof_score'] = 0.5

        enriched['enriched_at'] = datetime.utcnow().isoformat()
        return enriched

    def _extract_features(self, transaction: Dict[str, Any]) -> list:
        """Extract numerical features for anomaly detection"""
        return [
            transaction.get('amount', 0),
            transaction.get('velocity_1min', 0),
            transaction.get('velocity_5min', 0),
            transaction.get('velocity_1hr', 0),
            transaction.get('haversine_distance', 0),
            transaction.get('hour', 12),
            1 if transaction.get('is_holiday', False) else 0
        ]

    async def _train_anomaly_models(self):
        """Train anomaly detection models"""
        if len(self.feature_buffer) < 100:
            return

        logger.info("Training anomaly detection models")

        features_array = np.array(self.feature_buffer)

        # Train Isolation Forest
        self.isolation_forest.fit(features_array)

        # Train LOF
        self.lof.fit(features_array)

        self.anomaly_models_trained = True
        logger.info("Anomaly models trained")

    async def _publish_enriched(self, enriched_transaction: Dict[str, Any]):
        """Publish enriched transaction to next stage"""
        try:
            stream_data = {
                'id': enriched_transaction['id'],
                'data': json.dumps(enriched_transaction)
            }
            await self.redis.xadd("transactions:scored", stream_data)
        except Exception as e:
            logger.error(f"Failed to publish enriched transaction: {e}")

    async def start(self):
        """Start the pattern detection agent"""
        self.running = True
        await self.connect_redis()

        logger.info("Pattern detection agent started")

        try:
            await self.subscribe_to_transactions()
        except KeyboardInterrupt:
            logger.info("Shutting down pattern detection agent")
        finally:
            self.running = False
            if self.redis:
                await self.redis.close()

    async def stop(self):
        """Stop the pattern detection agent"""
        self.running = False
        logger.info("Pattern detection agent stopped")

# For running as standalone
async def main():
    agent = PatternDetectionAgent()
    await agent.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())