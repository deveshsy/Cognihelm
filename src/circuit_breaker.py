from src.aws_ledger import get_latest_task_status

def is_task_resolved(task_id: str) -> bool:
    """CIRCUIT BREAKER: Returns True if the task is already APPROVED or REJECTED."""
    latest = get_latest_task_status(task_id)
    if not latest:
        return False
    return latest.get("status") in ["APPROVED", "REJECTED"]
