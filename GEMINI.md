# GEMINI.md - CogniHelm HITL Governance

## Project Overview
**CogniHelm** is a high-resolution, framework-agnostic middleware protocol designed to provide **Immutable Human-In-The-Loop (HITL) Governance** for autonomous AI agents. It addresses the "Log and Pray" problem by enforcing a cryptographic pause-and-sign workflow, ensuring that every agent proposal and human approval is traceable and tamper-evident, in compliance with **EU AI Act Article 12**.

### Core Architecture
- **Immutable Ledger:** Every state transition is recorded as a unique, timestamped event in an append-only DynamoDB table. Updates and deletions are architecturally forbidden.
- **A2A Protocol:** Implements the Agent-to-Agent (A2A) JSON-RPC specification for interoperability.
- **x402 V2 Payments:** Integrates a "Payment Required" challenge (USDC on Base Sepolia) for API access, ensuring economic alignment.
- **Cryptographic Resumption:** Uses SHA-256 context hashing and RS256 JWTs for secure execution resumption post-approval.

### Tech Stack
- **Backend:** FastAPI (Python 3.10+)
- **Storage:** AWS DynamoDB
- **Payments:** Crossmint WaaS (x402 V2)
- **Messaging:** Slack/Teams Block Kit (for human interaction)
- **AI Frameworks:** Compatible with LangChain, LangGraph, and AutoGen.

---

## Building and Running

### Prerequisites
- Python 3.10 or higher
- AWS Account (DynamoDB access)
- Slack App (for approval routing)

### Installation
```bash
pip install -r requirements.txt
```

### Environment Setup
Copy `.env.example` to `.env` and configure the following:
- `SLACK_SIGNING_SECRET`: For webhook verification.
- `AWS_REGION` & `DYNAMODB_TABLE_NAME`: For the immutable ledger.
- `RSA_PRIVATE_KEY_PATH`: For signing resumption JWTs.
- `CROSSMINT_ID`: For x402 V2 payment verification.

### Running the Server
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### Testing the Workflow
A client script `a.py` is provided to simulate the agent-side task creation and polling process:
```bash
python a.py
```

---

## Development Conventions

### 1. Immutability Mandate
- **NEVER** use `UpdateItem` or `DeleteItem` operations on the ledger.
- All state changes must be appended as new events using `ledger.append_event()`.
- Reference: `ledger.py`

### 2. A2A & JSON-RPC
- Follow the A2A JSON-RPC 2.0 structure for all task operations (`tasks/send`, `tasks/get`).
- Use `a2a_error` helper for consistent error reporting.

### 3. Payment Enforcement (x402 V2)
- High-value operations must trigger a `402 Payment Required` response if a valid `PAYMENT-SIGNATURE` header is missing.
- Mock verification is currently implemented in `server.py`; production should verify against Crossmint/On-chain state.

### 4. Security
- All incoming webhooks from Slack **MUST** pass through the `SlackVerificationMiddleware`.
- Resumption tokens must be signed with RS256 using the project's private RSA key.

---

## Key Files
- `server.py`: FastAPI entry point and A2A routing logic.
- `ledger.py`: The `CogniHelmLedger` class enforcing the append-only architecture.
- `a.py`: Reference implementation of an A2A agent client.
- `schemas/mcp-tools.json`: MCP-compliant tool definitions for requesting human approval.
- `public/.well-known/agent-card.json`: Machine-readable agent capability discovery.
