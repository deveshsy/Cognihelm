import boto3
import os
import time
from boto3.dynamodb.conditions import Key
from dotenv import load_dotenv

load_dotenv()

# Initialize the DynamoDB resource
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.getenv('AWS_REGION', 'eu-north-1'),
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

table = dynamodb.Table(os.getenv('DYNAMODB_TABLE_NAME', 'CogniHelm_Ledger'))

def get_latest_task_status(task_id: str):
    """Retrieves the most recent ledger entry for a specific task."""
    response = table.query(
        KeyConditionExpression=Key('task_id').eq(task_id),
        ScanIndexForward=False, # Newest first
        Limit=1
    )
    items = response.get('Items', [])
    return items[0] if items else None

def is_task_resolved(task_id: str) -> bool:
    """CIRCUIT BREAKER: Returns True if the task is already APPROVED or REJECTED."""
    latest = get_latest_task_status(task_id)
    if not latest:
        return False
    return latest.get("status") in ["APPROVED", "REJECTED"]

def append_ledger_entry(task_id: str, status: str, metadata: dict):
    """Writes an immutable, timestamped record to the ledger."""
    timestamp = int(time.time() * 1000)
    item = {
        'task_id': task_id,
        'timestamp': timestamp,
        'status': status,
        'metadata': metadata
    }
    return table.put_item(Item=item)
