from unittest.mock import patch

def test_whatsapp_get_challenge(client):
    """Verifies that WhatsApp/Meta GET subscription verification requests are handled correctly."""
    response = client.get(
        "/v1/webhooks/whatsapp-callback",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "1158201444",
            "hub.verify_token": "test_token"
        }
    )
    assert response.status_code == 200
    assert response.text == "1158201444"

@patch("src.main.is_task_resolved")
@patch("src.main.get_latest_task_status")
@patch("src.main.append_ledger_entry")
def test_telegram_post_callback(mock_append, mock_get_status, mock_is_resolved, client):
    """Verifies Telegram webhook POST request parsing and signature token validation."""
    mock_is_resolved.return_value = False
    mock_get_status.return_value = {"payload_hash": "mocked_telegram_hash"}

    payload = {
        "callback_query": {
            "id": "query_id_abc",
            "data": "approve_task-tele-99",
            "from": {
                "id": 8888,
                "username": "telegram_officer"
            }
        }
    }

    # Verify matching header secret
    response = client.post(
        "/v1/webhooks/telegram-callback",
        json=payload,
        headers={"X-Telegram-Bot-Api-Secret-Token": "test_telegram_token"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "processed",
        "task_id": "task-tele-99",
        "decision": "APPROVED"
    }

    mock_append.assert_called_once_with(
        task_id="task-tele-99",
        status="APPROVED",
        metadata={
            "platform": "telegram",
            "auditor": "telegram_officer",
            "auditor_id": "8888"
        },
        payload_hash="mocked_telegram_hash"
    )

@patch("src.main.is_task_resolved")
@patch("src.main.get_latest_task_status")
@patch("src.main.append_ledger_entry")
def test_teams_post_callback(mock_append, mock_get_status, mock_is_resolved, client):
    """Verifies Microsoft Teams webhook POST parsing of Adaptive Card values."""
    mock_is_resolved.return_value = False
    mock_get_status.return_value = {"payload_hash": "mocked_teams_hash"}

    payload = {
        "value": {
            "task_id": "task-teams-44",
            "action": "reject"
        },
        "from": {
            "name": "Jane Teams",
            "id": "teams-id-123"
        }
    }

    response = client.post(
        "/v1/webhooks/teams-callback",
        json=payload,
        headers={"Authorization": "Bearer test_teams_jwt_token"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "processed",
        "task_id": "task-teams-44",
        "decision": "REJECTED"
    }

    mock_append.assert_called_once_with(
        task_id="task-teams-44",
        status="REJECTED",
        metadata={
            "platform": "teams",
            "auditor": "Jane Teams",
            "auditor_id": "teams-id-123"
        },
        payload_hash="mocked_teams_hash"
    )

@patch("src.main.is_task_resolved")
@patch("src.main.get_latest_task_status")
@patch("src.main.append_ledger_entry")
def test_slack_post_callback_success(mock_append, mock_get_status, mock_is_resolved, client):
    """Verifies Slack webhook POST request parsing with valid signature verification."""
    import hmac
    import hashlib
    import time
    import json
    import urllib.parse

    mock_is_resolved.return_value = False
    mock_get_status.return_value = {"payload_hash": "mocked_slack_hash"}

    payload = {
        "actions": [
            {
                "action_id": "hitl_approve",
                "value": "approve_task-slack-77"
            }
        ],
        "user": {
            "name": "Jane Slack",
            "id": "U12345"
        },
        "response_url": "https://hooks.slack.com/actions/T123/B123/mock"
    }

    from unittest.mock import AsyncMock
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = AsyncMock(status_code=200)
        
        form_data = {"payload": json.dumps(payload)}
        raw_body = urllib.parse.urlencode(form_data)
        
        timestamp = str(int(time.time()))
        sig_basestring = f"v0:{timestamp}:{raw_body}"
        computed_signature = "v0=" + hmac.new(
            b"test_secret",
            sig_basestring.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        response = client.post(
            "/v1/webhooks/slack-callback",
            data=form_data,
            headers={
                "X-Slack-Request-Timestamp": timestamp,
                "X-Slack-Signature": computed_signature
            }
        )

        assert response.status_code == 200
        assert response.json() == {
            "status": "processed",
            "task_id": "task-slack-77",
            "decision": "APPROVED"
        }
        mock_post.assert_called_once()

@patch("src.main.is_task_resolved")
@patch("src.main.get_latest_task_status")
@patch("src.main.append_ledger_entry")
def test_slack_post_callback_invalid_signature(mock_append, mock_get_status, mock_is_resolved, client):
    """Verifies Slack webhook POST request returns 403 Forbidden with invalid signature."""
    import time
    import json

    mock_is_resolved.return_value = False
    mock_get_status.return_value = {"payload_hash": "mocked_slack_hash"}

    payload = {
        "actions": [
            {
                "action_id": "hitl_approve",
                "value": "approve_task-slack-77"
            }
        ],
        "user": {
            "name": "Jane Slack",
            "id": "U12345"
        }
    }

    response = client.post(
        "/v1/webhooks/slack-callback",
        data={"payload": json.dumps(payload)},
        headers={
            "X-Slack-Request-Timestamp": str(int(time.time())),
            "X-Slack-Signature": "v0=invalid_signature"
        }
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Invalid signature"}

