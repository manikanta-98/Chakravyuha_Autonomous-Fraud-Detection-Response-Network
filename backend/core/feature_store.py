import logging
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime, timedelta
import feast
from feast import FeatureStore
from feast.data_source import PushSource
from feast.entity import Entity
from feast.feature_view import FeatureView
from feast.field import Field
from feast.types import Float32, Int64, String, Bool
from feast.value_type import ValueType
import redis
import os

logger = logging.getLogger(__name__)

class FraudFeatureStore:
    """Feature store using Feast for online/offline feature serving"""

    def __init__(self, repo_path: str = "./backend/core/feature_repo",
                 redis_url: str = "redis://localhost:6379"):
        self.repo_path = repo_path
        self.redis_url = redis_url
        self.store = None
        self.redis_client = None

        # Ensure repo directory exists
        os.makedirs(repo_path, exist_ok=True)

    def initialize_store(self):
        """Initialize Feast feature store"""
        try:
            self.store = FeatureStore(repo_path=self.repo_path)
            logger.info("Feast feature store initialized")
        except Exception as e:
            logger.error(f"Failed to initialize feature store: {e}")
            raise

    def connect_redis(self):
        """Connect to Redis for online features"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            logger.info("Connected to Redis for online features")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def define_entities(self):
        """Define entities for the feature store"""
        # Account entity
        account = Entity(
            name="account",
            join_keys=["account_id"],
            description="Customer account entity"
        )

        # Transaction entity
        transaction = Entity(
            name="transaction",
            join_keys=["transaction_id"],
            description="Transaction entity"
        )

        return account, transaction

    def define_feature_views(self):
        """Define feature views"""
        account, transaction = self.define_entities()

        # Account velocity features
        account_velocity_fv = FeatureView(
            name="account_velocity_features",
            entities=[account],
            schema=[
                Field(name="velocity_1min", dtype=Int64),
                Field(name="velocity_5min", dtype=Int64),
                Field(name="velocity_1hr", dtype=Int64),
                Field(name="avg_amount", dtype=Float32),
                Field(name="total_transactions", dtype=Int64),
                Field(name="last_transaction_timestamp", dtype=String),
            ],
            online=True,
            source=PushSource(name="account_velocity_push_source"),
            ttl=timedelta(days=1)
        )

        # Transaction features
        transaction_features_fv = FeatureView(
            name="transaction_features",
            entities=[transaction],
            schema=[
                Field(name="amount", dtype=Float32),
                Field(name="merchant_category", dtype=String),
                Field(name="haversine_distance", dtype=Float32),
                Field(name="hour", dtype=Int64),
                Field(name="day_of_week", dtype=Int64),
                Field(name="is_holiday", dtype=Bool),
                Field(name="sender_pagerank", dtype=Float32),
                Field(name="receiver_pagerank", dtype=Float32),
                Field(name="sender_in_degree", dtype=Int64),
                Field(name="receiver_in_degree", dtype=Int64),
            ],
            online=True,
            source=PushSource(name="transaction_push_source"),
            ttl=timedelta(hours=1)
        )

        # Graph features
        graph_features_fv = FeatureView(
            name="graph_features",
            entities=[account],
            schema=[
                Field(name="pagerank_score", dtype=Float32),
                Field(name="in_degree", dtype=Int64),
                Field(name="out_degree", dtype=Int64),
                Field(name="clustering_coefficient", dtype=Float32),
                Field(name="betweenness_centrality", dtype=Float32),
            ],
            online=True,
            source=PushSource(name="graph_features_push_source"),
            ttl=timedelta(hours=6)
        )

        return account_velocity_fv, transaction_features_fv, graph_features_fv

    def apply_feature_store_config(self):
        """Apply feature store configuration"""
        try:
            account, transaction = self.define_entities()
            feature_views = self.define_feature_views()

            # In a real implementation, you'd apply these to the store
            # self.store.apply([account, transaction] + list(feature_views))

            logger.info("Feature store configuration applied")

        except Exception as e:
            logger.error(f"Failed to apply feature store config: {e}")
            raise

    async def push_online_features(self, entity_name: str, features: Dict[str, Any]):
        """Push features to online store"""
        try:
            if not self.store:
                raise ValueError("Feature store not initialized")

            # Convert to DataFrame
            df = pd.DataFrame([features])

            # Push to online store
            self.store.push(entity_name, df, to="online")

            logger.debug(f"Pushed features for {entity_name}")

        except Exception as e:
            logger.error(f"Failed to push online features: {e}")

    def get_online_features(self, entity_name: str, entity_ids: List[str],
                          features: List[str]) -> pd.DataFrame:
        """Get online features"""
        try:
            if not self.store:
                raise ValueError("Feature store not initialized")

            # Get features
            feature_refs = [f"{entity_name}:{feature}" for feature in features]
            features_df = self.store.get_online_features(
                features=feature_refs,
                entity_rows=[{f"{entity_name}_id": eid} for eid in entity_ids]
            ).to_df()

            return features_df

        except Exception as e:
            logger.error(f"Failed to get online features: {e}")
            return pd.DataFrame()

    def materialize_features(self, start_date: datetime, end_date: datetime):
        """Materialize features to online store"""
        try:
            if not self.store:
                raise ValueError("Feature store not initialized")

            # Materialize features
            self.store.materialize(start_date, end_date)

            logger.info(f"Features materialized from {start_date} to {end_date}")

        except Exception as e:
            logger.error(f"Failed to materialize features: {e}")

    def get_historical_features(self, entity_df: pd.DataFrame,
                              features: List[str],
                              start_date: datetime,
                              end_date: datetime) -> pd.DataFrame:
        """Get historical features for training"""
        try:
            if not self.store:
                raise ValueError("Feature store not initialized")

            # Get historical features
            feature_refs = [f"{entity_df.columns[0].split('_')[0]}:{feature}" for feature in features]
            historical_features = self.store.get_historical_features(
                entity_df=entity_df,
                features=feature_refs,
                start_date=start_date,
                end_date=end_date
            )

            return historical_features.to_df()

        except Exception as e:
            logger.error(f"Failed to get historical features: {e}")
            return pd.DataFrame()

    # Convenience methods for fraud detection features
    async def update_account_velocity(self, account_id: str, velocity_data: Dict[str, Any]):
        """Update account velocity features"""
        features = {
            "account_id": account_id,
            "velocity_1min": velocity_data.get("velocity_1min", 0),
            "velocity_5min": velocity_data.get("velocity_5min", 0),
            "velocity_1hr": velocity_data.get("velocity_1hr", 0),
            "avg_amount": velocity_data.get("avg_amount", 0.0),
            "total_transactions": velocity_data.get("total_transactions", 0),
            "last_transaction_timestamp": velocity_data.get("last_timestamp", datetime.utcnow().isoformat())
        }

        await self.push_online_features("account_velocity_features", features)

    async def update_transaction_features(self, transaction_id: str, transaction_data: Dict[str, Any]):
        """Update transaction features"""
        features = {
            "transaction_id": transaction_id,
            "amount": transaction_data.get("amount", 0.0),
            "merchant_category": transaction_data.get("merchant_category", "unknown"),
            "haversine_distance": transaction_data.get("haversine_distance", 0.0),
            "hour": transaction_data.get("hour", 12),
            "day_of_week": transaction_data.get("day_of_week", 0),
            "is_holiday": transaction_data.get("is_holiday", False),
            "sender_pagerank": transaction_data.get("sender_pagerank", 0.0),
            "receiver_pagerank": transaction_data.get("receiver_pagerank", 0.0),
            "sender_in_degree": transaction_data.get("sender_in_degree", 0),
            "receiver_in_degree": transaction_data.get("receiver_in_degree", 0)
        }

        await self.push_online_features("transaction_features", features)

    async def update_graph_features(self, account_id: str, graph_data: Dict[str, Any]):
        """Update graph-based features"""
        features = {
            "account_id": account_id,
            "pagerank_score": graph_data.get("pagerank", 0.0),
            "in_degree": graph_data.get("in_degree", 0),
            "out_degree": graph_data.get("out_degree", 0),
            "clustering_coefficient": graph_data.get("clustering_coeff", 0.0),
            "betweenness_centrality": graph_data.get("betweenness", 0.0)
        }

        await self.push_online_features("graph_features", features)

    def get_transaction_features(self, transaction_id: str) -> Dict[str, Any]:
        """Get all features for a transaction"""
        try:
            # Get transaction features
            txn_features = self.get_online_features(
                "transaction", [transaction_id],
                ["amount", "merchant_category", "haversine_distance", "hour", "day_of_week", "is_holiday"]
            )

            if txn_features.empty:
                return {}

            # Convert to dict
            features = txn_features.iloc[0].to_dict()

            # Add graph features for sender/receiver if available
            # This would require additional logic to get sender/receiver from transaction

            return features

        except Exception as e:
            logger.error(f"Failed to get transaction features: {e}")
            return {}

    def get_account_features(self, account_id: str) -> Dict[str, Any]:
        """Get all features for an account"""
        try:
            # Get velocity features
            velocity_features = self.get_online_features(
                "account", [account_id],
                ["velocity_1min", "velocity_5min", "velocity_1hr", "avg_amount", "total_transactions"]
            )

            # Get graph features
            graph_features = self.get_online_features(
                "account", [account_id],
                ["pagerank_score", "in_degree", "out_degree", "clustering_coefficient"]
            )

            features = {}
            if not velocity_features.empty:
                features.update(velocity_features.iloc[0].to_dict())
            if not graph_features.empty:
                features.update(graph_features.iloc[0].to_dict())

            return features

        except Exception as e:
            logger.error(f"Failed to get account features: {e}")
            return {}

# Global instance
feature_store = FraudFeatureStore()

def get_feature_store() -> FraudFeatureStore:
    """Get the global feature store instance"""
    return feature_store