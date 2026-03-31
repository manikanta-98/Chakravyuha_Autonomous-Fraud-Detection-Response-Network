-- Fraud Detection System - Core Schema

-- Cleanup existing (if any)
DROP TABLE IF EXISTS transactions;

-- Main transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(50) UNIQUE NOT NULL,
    sender_account VARCHAR(50) NOT NULL,
    receiver_account VARCHAR(50) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    merchant_category VARCHAR(50),
    risk_level VARCHAR(20) DEFAULT 'UNKNOWN',
    fraud_probability FLOAT DEFAULT 0.5,
    is_fraud BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Kaggle V1-V28 Anonymous Features (Nullable for backwards compatibility)
    v1 FLOAT, v2 FLOAT, v3 FLOAT, v4 FLOAT, v5 FLOAT,
    v6 FLOAT, v7 FLOAT, v8 FLOAT, v9 FLOAT, v10 FLOAT,
    v11 FLOAT, v12 FLOAT, v13 FLOAT, v14 FLOAT, v15 FLOAT,
    v16 FLOAT, v17 FLOAT, v18 FLOAT, v19 FLOAT, v20 FLOAT,
    v21 FLOAT, v22 FLOAT, v23 FLOAT, v24 FLOAT, v25 FLOAT,
    v26 FLOAT, v27 FLOAT, v28 FLOAT,
    
    -- Metadata
    haversine_distance FLOAT DEFAULT 0.0,
    velocity_1min INT DEFAULT 1,
    hour INT,
    day_of_week INT,
    is_holiday BOOLEAN DEFAULT FALSE
);

-- Index for analytics performance
CREATE INDEX idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX idx_transactions_risk_level ON transactions(risk_level);
CREATE INDEX idx_transactions_is_fraud ON transactions(is_fraud);

-- User management (for later implementation)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'analyst',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
