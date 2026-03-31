import asyncio
import json
import logging
from typing import Dict, Any, Optional
import redis.asyncio as redis
from datetime import datetime
import aiohttp
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

logger = logging.getLogger(__name__)

class AlertBlockingAgent:
    """Agent for blocking high-risk transactions and sending alerts"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.running = False

        # Alert channels configuration
        self.email_config = {
            'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'username': os.getenv('SMTP_USERNAME'),
            'password': os.getenv('SMTP_PASSWORD'),
            'from_email': os.getenv('FROM_EMAIL', 'alerts@fraud-system.com')
        }

        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL')
        self.twilio_config = {
            'account_sid': os.getenv('TWILIO_ACCOUNT_SID'),
            'auth_token': os.getenv('TWILIO_AUTH_TOKEN'),
            'from_number': os.getenv('TWILIO_FROM_NUMBER')
        }

        # HTTP session for async requests
        self.session = None

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def init_http_session(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession()

    async def subscribe_to_risk_assessments(self):
        """Subscribe to risk assessments stream"""
        last_id = '0'  # Start from beginning

        while self.running:
            try:
                # Read from stream
                streams = await self.redis.xread(
                    streams={"transactions:risk": last_id},
                    count=10,
                    block=1000
                )

                for stream_name, messages in streams:
                    for message_id, message_data in messages:
                        last_id = message_id

                        risk_assessment = json.loads(message_data[b'data'].decode('utf-8'))
                        await self.process_risk_assessment(risk_assessment)

            except Exception as e:
                logger.error(f"Error reading from Redis stream: {e}")
                await asyncio.sleep(1)

    async def process_risk_assessment(self, risk_assessment: Dict[str, Any]):
        """Process risk assessment and take action"""
        transaction_id = risk_assessment['transaction_id']
        fraud_prob = risk_assessment['final_fraud_probability']
        risk_level = risk_assessment['risk_level']
        action = risk_assessment['action']

        logger.info(f"Processing {risk_level} risk transaction {transaction_id} with action {action}")

        # Auto-block high risk transactions
        if action == "BLOCK":
            await self._block_transaction(transaction_id, risk_assessment)

        # Send alerts for medium/high risk
        if risk_level in ["MEDIUM", "HIGH"]:
            await self._send_alerts(risk_assessment)

    async def _block_transaction(self, transaction_id: str, risk_assessment: Dict[str, Any]):
        """Block the transaction via gRPC call (simulated)"""
        try:
            # Simulate gRPC call to payment processor
            # In real implementation, this would be a gRPC call
            logger.info(f"Blocking transaction {transaction_id}")

            # Simulate blocking API call
            block_result = await self._call_blocking_service(transaction_id, risk_assessment)

            if block_result['success']:
                logger.info(f"Successfully blocked transaction {transaction_id}")
                risk_assessment['blocked_at'] = datetime.utcnow().isoformat()
                risk_assessment['block_success'] = True
            else:
                logger.error(f"Failed to block transaction {transaction_id}: {block_result.get('error')}")

        except Exception as e:
            logger.error(f"Error blocking transaction {transaction_id}: {e}")

    async def _call_blocking_service(self, transaction_id: str, risk_assessment: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate call to blocking service"""
        # In real implementation, this would be a gRPC client call
        # For demo, simulate with delay
        await asyncio.sleep(0.01)  # 10ms delay

        # Simulate 99% success rate
        success = asyncio.get_event_loop().time() % 100 > 1

        return {
            'success': success,
            'error': 'Service unavailable' if not success else None
        }

    async def _send_alerts(self, risk_assessment: Dict[str, Any]):
        """Send alerts via multiple channels"""
        transaction_id = risk_assessment['transaction_id']
        fraud_prob = risk_assessment['final_fraud_probability']
        risk_level = risk_assessment['risk_level']

        alert_message = self._format_alert_message(risk_assessment)

        # Send alerts concurrently
        tasks = []

        if self.email_config['username']:
            tasks.append(self._send_email_alert(alert_message, risk_assessment))

        if self.slack_webhook:
            tasks.append(self._send_slack_alert(alert_message, risk_assessment))

        if self.twilio_config['account_sid']:
            tasks.append(self._send_sms_alert(alert_message, risk_assessment))

        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
                logger.info(f"Sent alerts for transaction {transaction_id}")
            except Exception as e:
                logger.error(f"Error sending alerts for transaction {transaction_id}: {e}")

    def _format_alert_message(self, risk_assessment: Dict[str, Any]) -> str:
        """Format alert message"""
        return f"""
🚨 FRAUD ALERT 🚨

Transaction ID: {risk_assessment['transaction_id']}
Risk Level: {risk_assessment['risk_level']}
Fraud Probability: {risk_assessment['final_fraud_probability']:.3f}
Amount: ${risk_assessment.get('amount', 'N/A')}
Sender: {risk_assessment.get('sender_account', 'N/A')}
Receiver: {risk_assessment.get('receiver_account', 'N/A')}

Action Taken: {risk_assessment['action']}

Time: {datetime.utcnow().isoformat()}
"""

    async def _send_email_alert(self, message: str, risk_assessment: Dict[str, Any]):
        """Send email alert"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['from_email']
            msg['To'] = os.getenv('ALERT_EMAIL_RECIPIENTS', 'security@company.com')
            msg['Subject'] = f"Fraud Alert: {risk_assessment['risk_level']} Risk Transaction"

            msg.attach(MIMEText(message, 'plain'))

            server = smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port'])
            server.starttls()
            server.login(self.email_config['username'], self.email_config['password'])
            text = msg.as_string()
            server.sendmail(self.email_config['from_email'], msg['To'], text)
            server.quit()

            logger.debug("Email alert sent")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    async def _send_slack_alert(self, message: str, risk_assessment: Dict[str, Any]):
        """Send Slack alert"""
        try:
            payload = {
                "text": message,
                "username": "Fraud Detection System",
                "icon_emoji": ":warning:"
            }

            async with self.session.post(self.slack_webhook, json=payload) as response:
                if response.status == 200:
                    logger.debug("Slack alert sent")
                else:
                    logger.error(f"Slack alert failed with status {response.status}")

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")

    async def _send_sms_alert(self, message: str, risk_assessment: Dict[str, Any]):
        """Send SMS alert via Twilio"""
        try:
            # Import here to avoid dependency if not used
            from twilio.rest import Client

            client = Client(self.twilio_config['account_sid'], self.twilio_config['auth_token'])

            # Send to configured recipients
            recipients = os.getenv('SMS_RECIPIENTS', '+1234567890').split(',')

            for recipient in recipients:
                client.messages.create(
                    body=message[:160],  # SMS length limit
                    from_=self.twilio_config['from_number'],
                    to=recipient.strip()
                )

            logger.debug("SMS alert sent")

        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")

    async def start(self):
        """Start the alert blocking agent"""
        self.running = True
        await self.connect_redis()
        await self.init_http_session()

        logger.info("Alert blocking agent started")

        try:
            await self.subscribe_to_risk_assessments()
        except KeyboardInterrupt:
            logger.info("Shutting down alert blocking agent")
        finally:
            self.running = False
            if self.session:
                await self.session.close()
            if self.redis:
                await self.redis.close()

    async def stop(self):
        """Stop the alert blocking agent"""
        self.running = False
        logger.info("Alert blocking agent stopped")

# For running as standalone
async def main():
    agent = AlertBlockingAgent()
    await agent.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())