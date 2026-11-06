"""Persist Kafka rejection diagnostics with replay-safe topic/partition/offset."""
import json,os
from kafka import KafkaConsumer

SCHEMA="""
CREATE TABLE IF NOT EXISTS processing_errors (
 topic text NOT NULL, partition_id integer NOT NULL, kafka_offset bigint NOT NULL,
 stage text NOT NULL, reason text NOT NULL, received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(topic,partition_id,kafka_offset)
);
CREATE OR REPLACE VIEW processing_error_summary AS
 SELECT date_trunc('hour',received_at) AS hour_start,stage,reason,count(*) AS rejected_events
 FROM processing_errors GROUP BY 1,2,3;
"""

class ErrorReader:
    def __init__(self):
        self.consumer=KafkaConsumer('ripe.dead_letter',bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS','kafka:9092').split(','),group_id='ripe-operational-diagnostics-v1',enable_auto_commit=False,auto_offset_reset='earliest',max_poll_records=100)
    def poll(self,conn):
        batches=self.consumer.poll(timeout_ms=100,max_records=100)
        with conn.transaction():
            for messages in batches.values():
                for message in messages:
                    try:
                        body=json.loads(message.value)
                        if not isinstance(body,dict):body={}
                    except (ValueError,TypeError):body={}
                    conn.execute('INSERT INTO processing_errors(topic,partition_id,kafka_offset,stage,reason) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(message.topic,message.partition,message.offset,str(body.get('stage') or 'legacy_unknown')[:100],str(body.get('reason') or 'LEGACY_REASON_MISSING')[:1000]))
        if batches:self.consumer.commit()
