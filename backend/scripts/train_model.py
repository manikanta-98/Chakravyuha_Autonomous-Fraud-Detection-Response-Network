import asyncio
import os
import asyncpg
import pandas as pd
import numpy as np
from core.ensemble_model import EnsembleFraudDetector
import logging
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://frauduser:fraud_pass@db:5432/frauddetection")
MODEL_PATH = os.getenv("MODEL_PATH", "./models")

async def train_model():
    """Fetch data from DB and train the Ensemble model"""
    logger.info(f"Connecting to database at {DATABASE_URL}")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return

    logger.info("Fetching data for training...")
    rows = await conn.fetch("SELECT * FROM transactions ORDER BY timestamp DESC LIMIT 5000")
    await conn.close()
    
    if not rows:
        logger.warning("No data found in database. Run load_kaggle_data.py first!")
        return
        
    df = pd.DataFrame(rows, columns=rows[0].keys())
    
    # Selecting Kaggle-style features (V1-V28 and Amount)
    feature_cols = [f"v{i}" for i in range(1, 29)] + ['amount']
    # If V features are null, fill with 0
    X = df[feature_cols].fillna(0).values
    y = df['is_fraud'].values.astype(int)
    
    logger.info(f"Training on {len(X)} samples (Fraud: {sum(y)})")
    
    # Initialize detector
    detector = EnsembleFraudDetector(use_gpu=False)
    
    # Split for meta-learner training
    split_idx = int(len(X) * 0.8)
    X_train, X_val = X[:split_idx], X[split_idx:]
    y_train, y_val = y[:split_idx], y[split_idx:]
    
    # Convert back to DataFrame for the detector's train method
    X_train_df = pd.DataFrame(X_train, columns=feature_cols)
    X_val_df = pd.DataFrame(X_val, columns=feature_cols)
    y_train_ser = pd.Series(y_train)
    y_val_ser = pd.Series(y_val)
    
    # Train base models
    detector.train(X_train_df, y_train_ser)
    
    # Train meta-learner
    detector.train_meta_learner(X_val_df, y_val_ser)
    
    # Save models
    logger.info(f"Saving models to {MODEL_PATH}")
    detector.save_models(MODEL_PATH)
    
    logger.info("Training complete!")

if __name__ == "__main__":
    asyncio.run(train_model())
