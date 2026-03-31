import asyncio
import json
import logging
from typing import Dict, Any, Optional, List, Callable
import redis.asyncio as redis
from datetime import datetime, timedelta
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog

logger = structlog.get_logger(__name__)

class AgentOrchestrator:
    """Agent-to-Agent orchestrator with load balancing"""

    def __init__(self, redis_url: str = "redis://host.docker.internal:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.running = False

        # Message queues
        self.message_queues = {
            'monitoring_agent': asyncio.Queue(),
            'pattern_detection_agent': asyncio.Queue(),
            'risk_assessment_agent': asyncio.Queue(),
            'alert_blocking_agent': asyncio.Queue(),
            'compliance_agent': asyncio.Queue(),
            'learning_agent': asyncio.Queue()
        }

        # Agent status tracking
        self.agent_status = {agent: 'idle' for agent in self.message_queues.keys()}

        # Load balancing
        self.agent_load = {agent: 0 for agent in self.message_queues.keys()}
        self.round_robin_index = 0

        # Dead letter queue
        self.dead_letter_queue = asyncio.Queue()

        # Message routing table
        self.routing_table = {
            'transactions:raw': ['pattern_detection_agent', 'compliance_agent'],
            'transactions:scored': ['risk_assessment_agent', 'compliance_agent'],
            'transactions:risk': ['alert_blocking_agent', 'compliance_agent', 'learning_agent'],
            'analyst_feedback': ['learning_agent'],
            'model_predictions': ['learning_agent']
        }

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def start_message_bus(self):
        """Start the message bus for inter-agent communication"""
        # Subscribe to all relevant streams
        streams = list(self.routing_table.keys())
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

                        event_data = json.loads(message_data[b'data'].decode('utf-8'))
                        await self.route_message(stream_key, event_data)

            except Exception as e:
                logger.error("Error in message bus", error=str(e))
                await asyncio.sleep(1)

    async def route_message(self, stream_key: str, message: Dict[str, Any]):
        """Route message to appropriate agents"""
        target_agents = self.routing_table.get(stream_key, [])

        if not target_agents:
            logger.warning("No routing rule for stream", stream=stream_key)
            return

        # Route to each target agent
        for agent in target_agents:
            await self.send_to_agent(agent, {
                'stream': stream_key,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'message_id': f"{stream_key}_{message.get('id', 'unknown')}_{datetime.utcnow().timestamp()}"
            })

    async def send_to_agent(self, agent_name: str, message: Dict[str, Any]):
        """Send message to specific agent with load balancing"""
        try:
            queue = self.message_queues.get(agent_name)
            if not queue:
                logger.error("Unknown agent", agent=agent_name)
                await self.dead_letter_queue.put({
                    'agent': agent_name,
                    'message': message,
                    'error': 'unknown_agent',
                    'timestamp': datetime.utcnow().isoformat()
                })
                return

            # Add to queue
            await queue.put(message)
            self.agent_load[agent_name] += 1

            logger.debug("Message queued for agent", agent=agent_name, queue_size=queue.qsize())

        except Exception as e:
            logger.error("Error sending to agent", agent=agent_name, error=str(e))
            await self.dead_letter_queue.put({
                'agent': agent_name,
                'message': message,
                'error': str(e),
                'timestamp': datetime.utcnow().isoformat()
            })

    async def start_agent_workers(self):
        """Start worker tasks for each agent"""
        workers = []
        for agent_name, queue in self.message_queues.items():
            worker = asyncio.create_task(self._agent_worker(agent_name, queue))
            workers.append(worker)

        # Dead letter queue processor
        dlq_worker = asyncio.create_task(self._process_dead_letters())
        workers.append(dlq_worker)

        # Health check worker
        health_worker = asyncio.create_task(self._health_check())
        workers.append(health_worker)

        await asyncio.gather(*workers, return_exceptions=True)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _agent_worker(self, agent_name: str, queue: asyncio.Queue):
        """Worker for processing agent messages"""
        logger.info("Started agent worker", agent=agent_name)

        while self.running:
            try:
                # Get message from queue
                message = await queue.get()

                # Update status
                self.agent_status[agent_name] = 'processing'

                # Process message
                await self._process_agent_message(agent_name, message)

                # Update status
                self.agent_status[agent_name] = 'idle'
                self.agent_load[agent_name] -= 1

                queue.task_done()

            except Exception as e:
                logger.error("Agent worker error", agent=agent_name, error=str(e))
                await asyncio.sleep(1)

    async def _process_agent_message(self, agent_name: str, message: Dict[str, Any]):
        """Process message for specific agent"""
        # In a real implementation, this would call the actual agent methods
        # For now, simulate processing with logging

        processing_time = await self._simulate_processing(agent_name, message)

        logger.info("Processed message for agent",
                   agent=agent_name,
                   message_id=message.get('message_id'),
                   processing_time_ms=processing_time)

        # Simulate publishing result to next stream if applicable
        await self._publish_agent_result(agent_name, message)

    async def _simulate_processing(self, agent_name: str, message: Dict[str, Any]) -> float:
        """Simulate agent processing time"""
        # Simulate different processing times for different agents
        base_times = {
            'monitoring_agent': 10,
            'pattern_detection_agent': 50,
            'risk_assessment_agent': 100,
            'alert_blocking_agent': 20,
            'compliance_agent': 30,
            'learning_agent': 200
        }

        base_time = base_times.get(agent_name, 50)
        # Add some randomness
        processing_time = base_time + (asyncio.get_event_loop().time() % 20)

        await asyncio.sleep(processing_time / 1000)  # Convert to seconds
        return processing_time

    async def _publish_agent_result(self, agent_name: str, original_message: Dict[str, Any]):
        """Publish agent processing result"""
        # Determine output stream based on agent
        output_streams = {
            'monitoring_agent': 'transactions:raw',
            'pattern_detection_agent': 'transactions:scored',
            'risk_assessment_agent': 'transactions:risk',
            'alert_blocking_agent': None,  # No output stream
            'compliance_agent': None,  # Logs to database
            'learning_agent': 'model_updates'
        }

        output_stream = output_streams.get(agent_name)
        if not output_stream:
            return

        # Create result message
        result_message = {
            'processed_by': agent_name,
            'original_message': original_message,
            'processing_timestamp': datetime.utcnow().isoformat(),
            'status': 'completed'
        }

        try:
            await self.redis.xadd(output_stream, {'data': json.dumps(result_message)})
        except Exception as e:
            logger.error("Error publishing agent result", agent=agent_name, error=str(e))

    async def _process_dead_letters(self):
        """Process dead letter queue"""
        logger.info("Started dead letter queue processor")

        while self.running:
            try:
                dead_message = await self.dead_letter_queue.get()

                # Log dead letter
                logger.warning("Dead letter message",
                             agent=dead_message['agent'],
                             error=dead_message['error'],
                             message_id=dead_message.get('message', {}).get('message_id'))

                # In production, you might:
                # - Store in database
                # - Send to monitoring system
                # - Retry later

                self.dead_letter_queue.task_done()

            except Exception as e:
                logger.error("Error processing dead letter", error=str(e))
                await asyncio.sleep(1)

    async def _health_check(self):
        """Periodic health check of agents"""
        while self.running:
            await asyncio.sleep(30)  # Check every 30 seconds

            health_status = {
                'timestamp': datetime.utcnow().isoformat(),
                'agents': {}
            }

            for agent, status in self.agent_status.items():
                queue_size = self.message_queues[agent].qsize()
                load = self.agent_load[agent]
                health_status['agents'][agent] = {
                    'status': status,
                    'queue_size': queue_size,
                    'load': load
                }

            # Publish health status
            try:
                await self.redis.xadd("agent_health_stream", {"data": json.dumps(health_status)})
            except Exception as e:
                logger.error("Error publishing health status", error=str(e))

            logger.debug("Health check completed", **health_status)

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get current status of all agents"""
        return {
            'agent_status': self.agent_status.copy(),
            'queue_sizes': {agent: q.qsize() for agent, q in self.message_queues.items()},
            'agent_load': self.agent_load.copy(),
            'dead_letter_queue_size': self.dead_letter_queue.qsize()
        }

    async def start(self):
        """Start the agent orchestrator"""
        self.running = True
        await self.connect_redis()

        logger.info("Agent orchestrator started")

        try:
            # Start message bus and workers
            await asyncio.gather(
                self.start_message_bus(),
                self.start_agent_workers(),
                return_exceptions=True
            )
        except KeyboardInterrupt:
            logger.info("Shutting down agent orchestrator")
        finally:
            self.running = False
            if self.redis:
                await self.redis.close()

    async def stop(self):
        """Stop the agent orchestrator"""
        self.running = False
        logger.info("Agent orchestrator stopped")

# For running as standalone
async def main():
    orchestrator = AgentOrchestrator()
    await orchestrator.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())