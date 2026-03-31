import asyncio
import os
import asyncpg
import pandas as pd
from river import datasets
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://frauduser:fraud_pass@db:5432/frauddetection")

async def load_kaggle_data(limit=5000):
    """Load CreditCard dataset from river and insert into PostgreSQL"""
    logger.info(f"Connecting to database at {DATABASE_URL}")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
    except Exception as e:
        logger.error(f"Failed to connect to DB: {e}")
        return

    logger.info("Fetching CreditCard dataset from river...")
    dataset = datasets.CreditCard()
    
    count = 0
    now = datetime.utcnow()
    
    logger.info(f"Inserting up to {limit} transactions...")
    
    async with conn.transaction():
        for x, y in dataset:
            if count >= limit:
                break
                
            transaction_id = f"KAG-{count:06d}"
            # Mapping Kaggle features to our schema
            # Kaggle has Time, V1-V28, Amount
            v_features = [x.get(f"V{i}", 0.0) for i in range(1, 29)]
            amount = float(x.get("Amount", 0.0))
            is_fraud = bool(y)
            risk_level = "HIGH" if is_fraud else "LOW"
            
            # Synthetic accounts and metadata
            sender = f"ACC-{1000 + (count % 100)}"
            receiver = f"ACC-{2000 + (count % 50)}"
            timestamp = now - timedelta(minutes=(limit - count))
            
            await conn.execute("""
                INSERT INTO transactions (
                    transaction_id, sender_account, receiver_account, amount,
                    risk_level, fraud_probability, is_fraud, timestamp,
                    v1, v2, v3, v4, v5, v6, v7, v8, v9, v10,
                    v11, v12, v13, v14, v15, v16, v17, v18, v19, v20,
                    v21, v22, v23, v24, v25, v26, v27, v28,
                    hour, day_of_week
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14, $15, $16, $17, $18,
                    $19, $20, $21, $22, $23, $24, $25, $26, $27, $28,
                    $29, $30, $31, $32, $33, $34, $35, $36,
                    $37, $38
                ) ON CONFLICT (transaction_id) DO NOTHING
            """, 
            transaction_id, sender, receiver, amount,
            risk_level, 1.0 if is_fraud else 0.1, is_fraud, timestamp,
            *v_features, timestamp.hour, timestamp.weekday())
            
            count += 1
            if count % 500 == 0:
                logger.info(f"Inserted {count} records...")

    await conn.close()
    logger.info(f"Successfully loaded {count} transactions into the database.")

if __name__ == "__main__":
    asyncio.run(load_kaggle_data())
