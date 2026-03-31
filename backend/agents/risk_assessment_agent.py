import asyncio
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis
from datetime import datetime
import pandas as pd
import numpy as np
from core.ensemble_model import EnsembleFraudDetector

logger = logging.getLogger(__name__)

class RiskAssessmentAgent:
    """Agent for risk assessment using ensemble models"""

    def __init__(self, redis_url: str = "redis://localhost:6379", model_path: str = "./models"):
        self.redis_url = redis_url
        self.model_path = model_path
        self.redis = None
        self.running = False
        self.ensemble_model = EnsembleFraudDetector()

        # Load trained model
        try:
            self.ensemble_model.load_models(model_path)
            logger.info("Ensemble model loaded")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def subscribe_to_scored_transactions(self):
        """Subscribe to scored transactions stream"""
        last_id = '0'  # Start from beginning

        while self.running:
            try:
                # Read from stream
                streams = await self.redis.xread(
                    streams={"transactions:scored": last_id},
                    count=10,
                    block=1000
                )

                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        last_id = message_id

                        transaction = json.loads(message_data[b'data'].decode('utf-8'))
                        await self.assess_risk(transaction)

            except Exception as e:
                logger.error(f"Error reading from Redis stream: {e}")
                await asyncio.sleep(1)

    async def assess_risk(self, transaction: Dict[str, Any]):
        """Assess risk for transaction"""
        try:
            # Prepare features for model
            features = self._prepare_features(transaction)

            # Get risk assessment
            risk_result = await self.ensemble_model.predict_async(features)

            # Add transaction metadata
            risk_result['transaction_id'] = transaction['id']
            risk_result['assessed_at'] = datetime.utcnow().isoformat()

            # Determine action
            action = self._determine_action(risk_result['final_fraud_probability'])

            risk_result['action'] = action
            risk_result['threshold_breached'] = self._check_thresholds(risk_result['final_fraud_probability'])

            # Publish to risk stream
            await self._publish_risk_assessment(risk_result)

            logger.info(f"Assessed risk for transaction {transaction['id']}: {risk_result['risk_level']} ({risk_result['final_fraud_probability']:.3f})")

        except Exception as e:
            logger.error(f"Error assessing risk for transaction {transaction.get('id')}: {e}")

    def _prepare_features(self, transaction: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare features for model input"""
        # This should match the feature engineering from the spec
        return {
            'amount': transaction.get('amount', 0),
            'velocity_1min': transaction.get('velocity_1min', 0),
            'velocity_5min': transaction.get('velocity_5min', 0),
            'velocity_1hr': transaction.get('velocity_1hr', 0),
            'avg_amount': transaction.get('avg_amount', 0),
            'merchant_category': transaction.get('merchant_category', 'unknown'),
            'haversine_distance': transaction.get('haversine_distance', 0),
            'pagerank_score': transaction.get('sender_pagerank', 0),  # Use sender as primary
            'in_degree': transaction.get('sender_in_degree', 0),
            'out_degree': transaction.get('sender_out_degree', 0),
            'hour_sin': np.sin(2 * np.pi * transaction.get('hour', 12) / 24),
            'hour_cos': np.cos(2 * np.pi * transaction.get('hour', 12) / 24),
            'day_sin': np.sin(2 * np.pi * transaction.get('day_of_week', 0) / 7),
            'day_cos': np.cos(2 * np.pi * transaction.get('day_of_week', 0) / 7),
            'is_holiday': 1 if transaction.get('is_holiday', False) else 0
        }

    def _determine_action(self, fraud_prob: float) -> str:
        """Determine action based on fraud probability"""
        if fraud_prob >= 0.7:
            return "BLOCK"
        elif fraud_prob >= 0.4:
            return "REVIEW"
        else:
            return "ALLOW"

    def _check_thresholds(self, fraud_prob: float) -> Dict[str, bool]:
        """Check which thresholds are breached"""
        return {
            'low_threshold': fraud_prob < 0.3,
            'medium_threshold': 0.3 <= fraud_prob < 0.7,
            'high_threshold': fraud_prob >= 0.7
        }

    async def _publish_risk_assessment(self, risk_result: Dict[str, Any]):
        """Publish risk assessment to next stage"""
        try:
            stream_data = {
                'id': risk_result['transaction_id'],
                'data': json.dumps(risk_result)
            }
            await self.redis.xadd("transactions:risk", stream_data)
        except Exception as e:
            logger.error(f"Failed to publish risk assessment: {e}")

    async def start(self):
        """Start the risk assessment agent"""
        self.running = True
        await self.connect_redis()

        logger.info("Risk assessment agent started")

        try:
            await self.subscribe_to_scored_transactions()
        except KeyboardInterrupt:
            logger.info("Shutting down risk assessment agent")
        finally:
            self.running = False
            if self.redis:
                await self.redis.close()

    async def stop(self):
        """Stop the risk assessment agent"""
        self.running = False
        logger.info("Risk assessment agent stopped")

# For running as standalone
async def main():
    agent = RiskAssessmentAgent()
    await agent.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())