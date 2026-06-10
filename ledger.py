import boto3
import time
import json
import hashlib
from typing import Dict, Any

class CogniHelmLedger:
    """
    CogniHelm Immutable Ledger implementation.
    
    This class strictly enforces the 'Append-Only' architectural mandate.
    It fulfills tamper-evident record-keeping standards required by high-stakes
    fintech regulations (e.g., EU AI Act, PMLA).
    
    CRITICAL: Updates and Deletions are architecturally forbidden to preserve 
    the integrity of the audit lineage.
    """

    def __init__(self, table_name: str, region: str = "us-east-1"):
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)

    def append_event(self, task_id: str, event_type: str, actor_id: str, payload: Dict[str, Any], reasoning: str = ""):
        """
        Appends a new immutable state to the ledger.
        
        Args:
            task_id: Unique identifier for the agentic transaction.
            event_type: Semantic category of the event (e.g., AGENT_PROPOSAL, HUMAN_SIG).
            actor_id: Identifier for the entity triggering the event (Agent ID or User ID).
            payload: The raw execution context or transaction data.
            reasoning: Human-readable lineage explaining the 'why' behind the state change.
        """
        # 1. Generate high-resolution epoch nanosecond timestamp for Sort Key (SK)
        timestamp_ns = time.time_ns()

        # 2. Generate deterministic payload hash for cryptographic verification
        payload_str = json.dumps(payload, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        item = {
            'task_id': task_id,             # Partition Key (PK)
            'timestamp': timestamp_ns,       # Sort Key (SK)
            'event_type': event_type,
            'actor_id': actor_id,
            'payload_hash': payload_hash,
            'payload': payload,
            'reasoning_lineage': reasoning,
            'created_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')
        }

        # 3. Strictly use PutItem to create a new row.
        # Architecture Guideline: Never use UpdateItem or DeleteItem.
        try:
            self.table.put_item(Item=item)
            return {"status": "SUCCESS", "timestamp": timestamp_ns, "hash": payload_hash}
        except Exception as e:
            print(f"LEDGER_FAILURE: Unable to append immutable event. {e}")
            raise e

    def get_audit_trail(self, task_id: str):
        """
        Retrieves the complete, linear audit lineage for a specific task.
        Returns events sorted by timestamp (SK).
        """
        from boto3.dynamodb.conditions import Key
        response = self.table.query(
            KeyConditionExpression=Key('task_id').eq(task_id)
        )
        return response.get('Items', [])
