# CogniHelm: Immutable HITL Governance for Autonomous Agents

[![Protocol: A2A](https://img.shields.io/badge/Protocol-A2A-blue.svg)](https://a2a-protocol.org)
[![Compliance: EU AI Act](https://img.shields.io/badge/Compliance-EU%20AI%20Act%20Art.12-green.svg)](https://artificialintelligenceact.eu/)

## The "Log and Pray" Problem
Current AI agent frameworks (LangChain, AutoGen, CrewAI) treat execution logs as ephemeral side-effects. In high-stakes fintech environments, "logging" is insufficient. If an autonomous agent triggers a $1M capital reallocation, a standard JSON log file provides zero cryptographic guarantee of human authorization or state integrity. Under **EU AI Act Article 12**, high-risk AI systems must ensure traceability and "logging of events throughout the system's lifetime."

## The CogniHelm Solution
CogniHelm is a framework-agnostic middleware protocol that acts as an **Immutable Transaction Circuit Breaker**. It sits between the agent's reasoning engine and the execution environment, enforcing a strict cryptographic pause-and-sign workflow.

### Architectural Pillars
1. **Append-Only Ledger (No Updates):** CogniHelm utilizes an immutable data model. We explicitly forbid `UpdateItem` or `DeleteItem` operations. Every state change—from initial reasoning to final human approval—is persisted as a unique, timestamped row in DynamoDB.
2. **Cryptographic Resumption:** Execution context is hashed using SHA-256. Resumption is only possible via a signed RS256 JWT, preventing "Semantic Drift" where an agent modifies a payload post-approval.
3. **Hardware-Gated Approval:** Integration with Slack/Teams Block Kit ensures that human decisions are captured at the edge and cryptographically bound to the transaction ID.

## Data Model (DynamoDB)
We employ a high-resolution time-series schema to ensure strict linearizability of agent events.

* **Partition Key (PK):** `task_id` (UUIDv4)
* **Sort Key (SK):** `timestamp` (Epoch nanoseconds)

| Task ID (PK) | Timestamp (SK) | Event Type | Status | Payload Hash |
| :--- | :--- | :--- | :--- | :--- |
| `tx-99` | `1717621200000` | `INGESTION` | `PENDING` | `e3b0c4...` |
| `tx-99` | `1717621200500` | `HITL_PAUSE` | `AWAITING` | `e3b0c4...` |
| `tx-99` | `1717621500000` | `HUMAN_SIG` | `APPROVED` | `e3b0c4...` |

## Quick Start (Python)
```python
from ledger import CogniHelmLedger

ledger = CogniHelmLedger(table_name="CogniHelm_Audit_v1")
ledger.append_event(
    task_id="ach-7788",
    event_type="AGENT_PROPOSAL",
    actor_id="risk-agent-01",
    payload={"amount": 45000, "currency": "USD"}
)
```
