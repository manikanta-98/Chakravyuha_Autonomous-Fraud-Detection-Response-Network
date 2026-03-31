import asyncio
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis
from kafka import KafkaConsumer
import websockets
from datetime import datetime

logger = logging.getLogger(__name__)

class MonitoringAgent:
    """Agent for ingesting and monitoring transaction streams"""

    def __init__(self, redis_url: str = "redis://localhost:6379", kafka_bootstrap: str = "localhost:9092"):
        self.redis_url = redis_url
        self.kafka_bootstrap = kafka_bootstrap
        self.redis = None
        self.running = False

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def start_kafka_consumer(self):
        """Start Kafka consumer for transaction ingestion"""
        loop = asyncio.get_event_loop()
        consumer = KafkaConsumer(
            'transactions',
            bootstrap_servers=[self.kafka_bootstrap],
            auto_offset_reset='latest',
            enable_auto_commit=True,
            group_id='monitoring-agent',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )

        logger.info("Started Kafka consumer")

        try:
            while self.running:
                # Poll for messages
                message_batch = consumer.poll(timeout_ms=1000)

                for topic_partition, messages in message_batch.items():
                    for message in messages:
                        transaction = message.value
                        await self.process_transaction(transaction, source="kafka")

                await asyncio.sleep(0.1)  # Small delay to prevent busy loop

        except Exception as e:
            logger.error(f"Kafka consumer error: {e}")
        finally:
            consumer.close()

    async def start_websocket_server(self, host: str = "0.0.0.0", port: int = 8765):
        """Start WebSocket server for real-time transaction ingestion"""
        async def ws_handler(websocket, path):
            logger.info(f"WebSocket connection from {websocket.remote_address}")
            try:
                async for message in websocket:
                    try:
                        transaction = json.loads(message)
                        await self.process_transaction(transaction, source="websocket")
                        # Send acknowledgment
                        await websocket.send(json.dumps({"status": "received", "id": transaction.get("id")}))
                    except json.JSONDecodeError:
                        await websocket.send(json.dumps({"error": "Invalid JSON"}))
                    except Exception as e:
                        logger.error(f"Error processing WebSocket message: {e}")
                        await websocket.send(json.dumps({"error": str(e)}))
            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket connection closed")

        server = await websockets.serve(ws_handler, host, port)
        logger.info(f"WebSocket server started on ws://{host}:{port}")
        return server

    async def process_transaction(self, transaction: Dict[str, Any], source: str):
        """Process incoming transaction"""
        # Add metadata
        transaction['ingested_at'] = datetime.utcnow().isoformat()
        transaction['source'] = source

        # Validate transaction
        if not self._validate_transaction(transaction):
            logger.warning(f"Invalid transaction: {transaction}")
            return

        # Publish to Redis stream
        await self._publish_to_redis(transaction)

        logger.info(f"Processed transaction {transaction.get('id')} from {source}")

    def _validate_transaction(self, transaction: Dict[str, Any]) -> bool:
        """Validate transaction structure"""
        required_fields = ['id', 'sender_account', 'receiver_account', 'amount', 'timestamp']
        return all(field in transaction for field in required_fields)

    async def _publish_to_redis(self, transaction: Dict[str, Any]):
        """Publish transaction to Redis stream"""
        try:
            stream_data = {
                'id': transaction['id'],
                'data': json.dumps(transaction)
            }
            await self.redis.xadd("transactions:raw", stream_data)
        except Exception as e:
            logger.error(f"Failed to publish to Redis: {e}")

    async def start(self):
        """Start the monitoring agent"""
        self.running = True
        await self.connect_redis()

        # Start Kafka consumer
        kafka_task = asyncio.create_task(self.start_kafka_consumer())

        # Start WebSocket server
        ws_server = await self.start_websocket_server()

        logger.info("Monitoring agent started")

        try:
            # Keep running
            await asyncio.gather(kafka_task)
        except KeyboardInterrupt:
            logger.info("Shutting down monitoring agent")
        finally:
            self.running = False
            ws_server.close()
            await ws_server.wait_closed()
            if self.redis:
                await self.redis.close()

    async def stop(self):
        """Stop the monitoring agent"""
        self.running = False
        logger.info("Monitoring agent stopped")

# For running as standalone
async def main():
    agent = MonitoringAgent()
    await agent.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())