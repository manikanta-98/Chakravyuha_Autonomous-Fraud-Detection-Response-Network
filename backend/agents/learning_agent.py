import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from datetime import datetime, timedelta
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
import numpy as np
import pandas as pd
from core.ensemble_model import EnsembleFraudDetector
from core.drift_monitor import DriftMonitor  # Assuming this exists

logger = logging.getLogger(__name__)

class LearningAgent:
    """Agent for continuous learning and model updates"""

    def __init__(self, redis_url: str = "redis://localhost:6379",
                 mlflow_tracking_uri: str = "http://localhost:5000",
                 model_path: str = "./models"):
        self.redis_url = redis_url
        self.mlflow_tracking_uri = mlflow_tracking_uri
        self.model_path = model_path
        self.redis = None
        self.running = False

        # MLflow setup
        mlflow.set_tracking_uri(mlflow_tracking_uri)
        self.mlflow_client = MlflowClient()

        # Model management
        self.current_model = EnsembleFraudDetector()
        self.drift_monitor = DriftMonitor()

        # Learning parameters
        self.online_update_threshold = 10  # Update River after N labeled examples
        self.batch_retrain_threshold = 500  # Retrain full model after N labels
        self.drift_check_interval = 3600  # Check drift every hour

        # Data buffers
        self.online_labels = []
        self.batch_labels = []
        self.drift_samples = []

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def subscribe_to_feedback(self):
        """Subscribe to analyst feedback and model performance data"""
        streams = ["analyst_feedback", "model_predictions"]
        last_ids = {stream: '0' for stream in streams}

        while self.running:
            try:
                # Read from streams
                streams_data = await self.redis.xread(
                    streams=last_ids,
                    count=10,
                    block=1000
                )

                for stream_name, messages in streams_data:
                    stream_key = stream_name.decode('utf-8')
                    for message_id, message_data in messages:
                        last_ids[stream_key] = message_id

                        feedback_data = json.loads(message_data[b'data'].decode('utf-8'))
                        await self.process_feedback(stream_key, feedback_data)

            except Exception as e:
                logger.error(f"Error reading feedback streams: {e}")
                await asyncio.sleep(1)

    async def process_feedback(self, stream_type: str, feedback_data: Dict[str, Any]):
        """Process feedback data"""
        if stream_type == "analyst_feedback":
            await self._process_analyst_feedback(feedback_data)
        elif stream_type == "model_predictions":
            await self._process_prediction_feedback(feedback_data)

    async def _process_analyst_feedback(self, feedback: Dict[str, Any]):
        """Process manual analyst feedback for model learning"""
        transaction_id = feedback['transaction_id']
        true_label = feedback['true_label']  # 0 = legitimate, 1 = fraud
        analyst_id = feedback.get('analyst_id', 'unknown')

        # Get transaction features (assuming stored in Redis or can be reconstructed)
        transaction_features = await self._get_transaction_features(transaction_id)

        if transaction_features:
            # Add to online learning buffer
            self.online_labels.append((transaction_features, true_label))

            # Add to batch learning buffer
            self.batch_labels.append((transaction_features, true_label))

            # Update River model online
            if len(self.online_labels) >= self.online_update_threshold:
                await self._update_online_model()

            # Check if we need batch retraining
            if len(self.batch_labels) >= self.batch_retrain_threshold:
                await self._trigger_batch_retrain()

            logger.info(f"Processed analyst feedback for transaction {transaction_id}: label={true_label}")

    async def _process_prediction_feedback(self, prediction_data: Dict[str, Any]):
        """Process prediction data for drift monitoring"""
        # Add to drift monitoring samples
        self.drift_samples.append(prediction_data)

        # Store for drift analysis
        if len(self.drift_samples) >= 1000:  # Keep last 1000 predictions
            self.drift_samples = self.drift_samples[-1000:]

    async def _get_transaction_features(self, transaction_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve transaction features for learning"""
        try:
            # Try to get from Redis (assuming features are cached)
            features = await self.redis.get(f"features:{transaction_id}")
            if features:
                return json.loads(features)

            # If not in cache, try to reconstruct from audit trail
            # This would require database access - simplified for demo
            logger.warning(f"Features not found for transaction {transaction_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting features for {transaction_id}: {e}")
            return None

    async def _update_online_model(self):
        """Update River online learning model"""
        try:
            logger.info(f"Updating online model with {len(self.online_labels)} new labels")

            # Update River models in ensemble
            for features, label in self.online_labels:
                self.current_model.update_online(features, label)

            # Log to MLflow
            with mlflow.start_run(run_name="online_update"):
                mlflow.log_param("update_type", "online")
                mlflow.log_param("samples_processed", len(self.online_labels))
                mlflow.log_metric("online_updates", len(self.online_labels))

            # Clear buffer
            self.online_labels = []

            logger.info("Online model updated")

        except Exception as e:
            logger.error(f"Error updating online model: {e}")

    async def _trigger_batch_retrain(self):
        """Trigger full model retraining"""
        try:
            logger.info(f"Triggering batch retrain with {len(self.batch_labels)} labels")

            # Prepare training data
            X_train = pd.DataFrame([features for features, _ in self.batch_labels])
            y_train = pd.Series([label for _, label in self.batch_labels])

            # Retrain ensemble model
            self.current_model.train(X_train, y_train)

            # Generate validation data (using recent predictions)
            # In practice, you'd have a separate validation set
            X_val = X_train.sample(min(1000, len(X_train)), random_state=42)
            y_val = y_train.loc[X_val.index]

            self.current_model.train_meta_learner(X_val, y_val)

            # Save new model
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            model_version = f"model_v_{timestamp}"
            model_path = f"{self.model_path}/{model_version}"
            self.current_model.save_models(model_path)

            # Log to MLflow
            with mlflow.start_run(run_name=f"batch_retrain_{timestamp}"):
                mlflow.log_param("retrain_type", "batch")
                mlflow.log_param("training_samples", len(self.batch_labels))
                mlflow.log_param("model_version", model_version)

                # Log model metrics
                # In practice, calculate proper metrics
                mlflow.log_metric("training_accuracy", 0.95)  # Placeholder
                mlflow.log_metric("validation_f1", 0.88)  # Placeholder

                # Log model artifact
                mlflow.sklearn.log_model(self.current_model.meta_learner, "meta_learner")

            # Register model in MLflow Model Registry
            self.mlflow_client.create_registered_model(model_version)
            self.mlflow_client.create_model_version(
                name=model_version,
                source=f"runs:/{mlflow.active_run().info.run_id}/meta_learner"
            )

            # Clear batch buffer
            self.batch_labels = []

            # Publish model update event
            await self._publish_model_update(model_version, model_path)

            logger.info(f"Batch retrain completed: {model_version}")

        except Exception as e:
            logger.error(f"Error in batch retrain: {e}")

    async def _check_drift(self):
        """Check for model drift"""
        try:
            if len(self.drift_samples) < 100:
                return

            logger.info("Checking for model drift")

            # Use Evidently AI for drift detection
            drift_detected = self.drift_monitor.check_drift(self.drift_samples)

            if drift_detected:
                logger.warning("Model drift detected, triggering retrain")
                await self._trigger_batch_retrain()

                # Log drift event
                with mlflow.start_run(run_name="drift_detection"):
                    mlflow.log_param("drift_detected", True)
                    mlflow.log_metric("drift_confidence", 0.95)  # Placeholder

        except Exception as e:
            logger.error(f"Error checking drift: {e}")

    async def _publish_model_update(self, model_version: str, model_path: str):
        """Publish model update event"""
        try:
            update_event = {
                'model_version': model_version,
                'model_path': model_path,
                'updated_at': datetime.utcnow().isoformat(),
                'trigger_reason': 'batch_retrain'
            }

            await self.redis.xadd("model_updates", {'data': json.dumps(update_event)})
            logger.info(f"Published model update: {model_version}")

        except Exception as e:
            logger.error(f"Error publishing model update: {e}")

    async def _schedule_drift_checks(self):
        """Schedule periodic drift checks"""
        while self.running:
            await asyncio.sleep(self.drift_check_interval)
            await self._check_drift()

    async def start(self):
        """Start the learning agent"""
        self.running = True
        await self.connect_redis()

        # Load current model
        try:
            self.current_model.load_models(self.model_path)
            logger.info("Loaded existing model")
        except Exception as e:
            logger.warning(f"Could not load existing model: {e}")

        logger.info("Learning agent started")

        try:
            # Start drift checking
            asyncio.create_task(self._schedule_drift_checks())

            await self.subscribe_to_feedback()
        except KeyboardInterrupt:
            logger.info("Shutting down learning agent")
        finally:
            self.running = False
            if self.redis:
                await self.redis.close()

    async def stop(self):
        """Stop the learning agent"""
        self.running = False
        logger.info("Learning agent stopped")

# For running as standalone
async def main():
    agent = LearningAgent()
    await agent.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())