import os
import decimal
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from src.aws_ledger import table

app = FastAPI(title="CogniHelm Enterprise Compliance Console")

def convert_decimals(obj):
    """Recursively converts DynamoDB Decimal objects to standard float or int for JSON serialization."""
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serves the main single-page Tailwind compliance dashboard."""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    if not os.path.exists(html_path):
        raise HTTPException(status_code=404, detail="Dashboard template not found")
        
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read dashboard template: {str(e)}")

@app.get("/api/logs")
async def get_logs():
    """Fetches the 50 most recent ledger entries from the DynamoDB audit trail."""
    try:
        response = table.scan()
        items = response.get('Items', [])
        
        # Serialize Decimals
        items = convert_decimals(items)
        
        # Sort by timestamp descending (newest first)
        items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        return items[:50]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")
