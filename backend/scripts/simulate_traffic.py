import asyncio
import httpx
import random
import time
from datetime import datetime
import uuid

API_URL = "http://localhost:8000/api/transactions/simulate"
# If running inside docker, use: http://backend:8000/...

MERCHANT_CATEGORIES = [
    'entertainment', 'food_dining', 'gas_transport', 'grocery_net',
    'grocery_pos', 'health_fitness', 'home', 'kids_pets',
    'misc_net', 'misc_pos', 'personal_care', 'shopping_net',
    'shopping_pos', 'travel'
]

async def simulate_traffic(interval=2.0):
    """Continuously send random transactions to the API"""
    print(f"Starting traffic simulation to {API_URL}...")
    print("Press Ctrl+C to stop.")
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                # Generate random transaction
                is_suspicious = random.random() < 0.15 # 15% chance of being "suspicious"
                
                payload = {
                    "id": f"SIM-{uuid.uuid4().hex[:8].upper()}",
                    "sender_account": f"ACC-{random.randint(1000, 9999)}",
                    "receiver_account": f"ACC-{random.randint(1000, 9999)}",
                    "amount": float(random.randint(10, 5000)) if is_suspicious else float(random.randint(1, 500)),
                    "timestamp": datetime.utcnow().isoformat(),
                    "merchant_category": random.choice(MERCHANT_CATEGORIES),
                    "haversine_distance": float(random.randint(100, 5000)) if is_suspicious else float(random.randint(0, 50)),
                    "hour": datetime.now().hour,
                    "day_of_week": datetime.now().weekday(),
                    "velocity_1min": random.randint(5, 20) if is_suspicious else 1,
                }
                
                response = await client.post(API_URL, json=payload, timeout=10.0)
                if response.status_code == 200:
                    res = response.json()
                    risk = res.get('risk_level', 'UNKNOWN')
                    prob = res.get('final_fraud_probability', 0.5)
                    color = "\033[91m" if risk == "HIGH" else "\033[92m"
                    reset = "\033[0m"
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {payload['id']} - Amount: ${payload['amount']:>8.2f} - Risk: {color}{risk:<6}{reset} ({prob:.2f})")
                else:
                    print(f"Error: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"Simulation error: {e}")
                
            await asyncio.sleep(interval)

if __name__ == "__main__":
    try:
        asyncio.run(simulate_traffic())
    except KeyboardInterrupt:
        print("\nSimulation stopped.")
