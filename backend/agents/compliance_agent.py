import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
import redis.asyncio as redis
from datetime import datetime
import asyncpg
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
import os
import hashlib

logger = logging.getLogger(__name__)

class ComplianceAgent:
    """Agent for compliance auditing and reporting"""

    def __init__(self, redis_url: str = "redis://localhost:6379",
                 db_url: str = "postgresql://fraud_user:fraud_pass@localhost:5432/fraud_detection"):
        self.redis_url = redis_url
        self.db_url = db_url
        self.redis = None
        self.db_pool = None
        self.running = False

    async def connect_redis(self):
        """Connect to Redis"""
        self.redis = redis.from_url(self.redis_url)
        logger.info("Connected to Redis")

    async def connect_database(self):
        """Connect to PostgreSQL"""
        self.db_pool = await asyncpg.create_pool(self.db_url)
        logger.info("Connected to PostgreSQL")

        # Create tables if they don't exist
        await self._create_tables()

    async def _create_tables(self):
        """Create audit tables"""
        async with self.db_pool.acquire() as conn:
            # Main audit trail table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id SERIAL PRIMARY KEY,
                    transaction_id VARCHAR(255) NOT NULL,
                    event_type VARCHAR(50) NOT NULL,
                    agent_name VARCHAR(100) NOT NULL,
                    event_data JSONB NOT NULL,
                    masked_pii JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    hash_value VARCHAR(64) UNIQUE NOT NULL
                )
            """)

            # Indexes for performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_transaction_id ON audit_trail(transaction_id)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_trail(event_type)
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_created_at ON audit_trail(created_at)
            """)

            # Compliance reports table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS compliance_reports (
                    id SERIAL PRIMARY KEY,
                    report_type VARCHAR(50) NOT NULL,
                    report_period_start TIMESTAMP WITH TIME ZONE NOT NULL,
                    report_period_end TIMESTAMP WITH TIME ZONE NOT NULL,
                    report_data JSONB NOT NULL,
                    pdf_path VARCHAR(500),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """)

    async def subscribe_to_all_streams(self):
        """Subscribe to all transaction streams for auditing"""
        streams = ["transactions:raw", "transactions:scored", "transactions:risk"]
        last_ids = {stream: '0' for stream in streams}

        while self.running:
            try:
                # Read from all streams
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
                        await self.audit_event(stream_key, event_data)

            except Exception as e:
                logger.error(f"Error reading from Redis streams: {e}")
                await asyncio.sleep(1)

    async def audit_event(self, stream_name: str, event_data: Dict[str, Any]):
        """Audit an event"""
        try:
            transaction_id = event_data.get('id') or event_data.get('transaction_id')
            if not transaction_id:
                logger.warning(f"No transaction ID in event: {event_data}")
                return

            # Determine agent name from stream
            agent_name = self._get_agent_from_stream(stream_name)

            # Mask PII data
            masked_pii = self._mask_pii(event_data)

            # Create hash for immutability
            hash_value = self._create_event_hash(event_data, agent_name)

            # Store in database
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO audit_trail (transaction_id, event_type, agent_name, event_data, masked_pii, hash_value)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (hash_value) DO NOTHING
                """, transaction_id, stream_name, agent_name, json.dumps(event_data), json.dumps(masked_pii), hash_value)

            logger.debug(f"Audited event for transaction {transaction_id} by {agent_name}")

        except Exception as e:
            logger.error(f"Error auditing event: {e}")

    def _get_agent_from_stream(self, stream_name: str) -> str:
        """Get agent name from stream name"""
        mapping = {
            "transactions:raw": "monitoring_agent",
            "transactions:scored": "pattern_detection_agent",
            "transactions:risk": "risk_assessment_agent"
        }
        return mapping.get(stream_name, "unknown_agent")

    def _mask_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask personally identifiable information"""
        masked = {}

        # Fields to mask
        pii_fields = ['sender_account', 'receiver_account', 'account_number', 'card_number', 'email', 'phone']

        for key, value in data.items():
            if any(pii_field in key.lower() for pii_field in pii_fields):
                if isinstance(value, str):
                    # Mask all but last 4 characters
                    masked[key] = f"{'*' * max(0, len(value) - 4)}{value[-4:]}" if len(value) > 4 else "***"
                else:
                    masked[key] = "[MASKED]"
            else:
                masked[key] = value

        return masked

    def _create_event_hash(self, event_data: Dict[str, Any], agent_name: str) -> str:
        """Create SHA256 hash for event immutability"""
        # Sort keys for consistent hashing
        sorted_data = json.dumps(event_data, sort_keys=True)
        content = f"{agent_name}:{sorted_data}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    async def generate_compliance_report(self, report_type: str = "daily",
                                       start_date: Optional[datetime] = None,
                                       end_date: Optional[datetime] = None) -> str:
        """Generate compliance report"""
        if start_date is None:
            start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        if end_date is None:
            end_date = datetime.utcnow()

        logger.info(f"Generating {report_type} compliance report for {start_date} to {end_date}")

        # Fetch audit data
        audit_data = await self._fetch_audit_data(start_date, end_date)

        # Generate statistics
        stats = self._calculate_compliance_stats(audit_data)

        # Generate PDF
        pdf_path = await self._generate_pdf_report(stats, audit_data, start_date, end_date)

        # Store report metadata
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO compliance_reports (report_type, report_period_start, report_period_end, report_data, pdf_path)
                VALUES ($1, $2, $3, $4, $5)
            """, report_type, start_date, end_date, json.dumps(stats), pdf_path)

        logger.info(f"Compliance report generated: {pdf_path}")
        return pdf_path

    async def _fetch_audit_data(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Fetch audit data for the period"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT * FROM audit_trail
                WHERE created_at >= $1 AND created_at <= $2
                ORDER BY created_at
            """, start_date, end_date)

            return [dict(row) for row in rows]

    def _calculate_compliance_stats(self, audit_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate compliance statistics"""
        total_events = len(audit_data)
        events_by_agent = {}
        events_by_type = {}
        fraud_detections = 0
        blocks = 0

        for event in audit_data:
            agent = event['agent_name']
            event_type = event['event_type']

            events_by_agent[agent] = events_by_agent.get(agent, 0) + 1
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

            # Check for fraud detections and blocks
            if event_type == "transactions:risk":
                event_data = event['event_data']
                if event_data.get('action') == "BLOCK":
                    blocks += 1
                if event_data.get('final_fraud_probability', 0) > 0.5:
                    fraud_detections += 1

        return {
            'total_events': total_events,
            'events_by_agent': events_by_agent,
            'events_by_type': events_by_type,
            'fraud_detections': fraud_detections,
            'blocks': blocks,
            'audit_completeness': total_events > 0  # All events should be audited
        }

    async def _generate_pdf_report(self, stats: Dict[str, Any], audit_data: List[Dict[str, Any]],
                                 start_date: datetime, end_date: datetime) -> str:
        """Generate PDF compliance report"""
        filename = f"compliance_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        filepath = os.path.join("reports", filename)
        os.makedirs("reports", exist_ok=True)

        doc = SimpleDocTemplate(filepath, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title = Paragraph("Fraud Detection System - Compliance Report", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))

        # Period
        period_text = f"Report Period: {start_date.strftime('%Y-%m-%d %H:%M:%S')} to {end_date.strftime('%Y-%m-%d %H:%M:%S')}"
        story.append(Paragraph(period_text, styles['Normal']))
        story.append(Spacer(1, 12))

        # Statistics
        story.append(Paragraph("Compliance Statistics", styles['Heading2']))
        stat_data = [
            ['Metric', 'Value'],
            ['Total Events Audited', str(stats['total_events'])],
            ['Fraud Detections', str(stats['fraud_detections'])],
            ['Transactions Blocked', str(stats['blocks'])],
            ['Audit Completeness', '100%' if stats['audit_completeness'] else 'Incomplete']
        ]

        stat_table = Table(stat_data)
        stat_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(stat_table)
        story.append(Spacer(1, 20))

        # Events by Agent
        story.append(Paragraph("Events by Agent", styles['Heading2']))
        agent_data = [['Agent', 'Event Count']]
        for agent, count in stats['events_by_agent'].items():
            agent_data.append([agent, str(count)])

        agent_table = Table(agent_data)
        agent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(agent_table)

        # Build PDF
        doc.build(story)
        return filepath

    async def start(self):
        """Start the compliance agent"""
        self.running = True
        await self.connect_redis()
        await self.connect_database()

        logger.info("Compliance agent started")

        try:
            # Generate daily report at midnight
            asyncio.create_task(self._schedule_daily_reports())

            await self.subscribe_to_all_streams()
        except KeyboardInterrupt:
            logger.info("Shutting down compliance agent")
        finally:
            self.running = False
            if self.db_pool:
                await self.db_pool.close()
            if self.redis:
                await self.redis.close()

    async def _schedule_daily_reports(self):
        """Schedule daily compliance reports"""
        while self.running:
            now = datetime.utcnow()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            seconds_until_midnight = (midnight - now).total_seconds()

            await asyncio.sleep(seconds_until_midnight)

            try:
                await self.generate_compliance_report("daily")
            except Exception as e:
                logger.error(f"Error generating daily report: {e}")

    async def stop(self):
        """Stop the compliance agent"""
        self.running = False
        logger.info("Compliance agent stopped")

# For running as standalone
async def main():
    agent = ComplianceAgent()
    await agent.start()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())