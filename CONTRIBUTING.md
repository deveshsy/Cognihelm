# Contributing to CogniHelm

Thank you for your interest in contributing to CogniHelm! We welcome community contributions to help improve the open-source Human-in-the-Loop (HITL) authorization gateway for autonomous AI agents.

By contributing to this repository, you help make AI agents safer, more auditable, and compliant with emerging standards like the **EU AI Act**.

---

## 🏗️ Open-Core Architecture & Fallbacks

CogniHelm is built using an **Open-Core Model**. The repository is split into two directories:
*   `src/`: **Open-Source Core** (Publicly distributed in this repository).
*   `ee/`: **Enterprise Edition** (Proprietary features, ignored by Git).

### Critical Rule: Zero Static Imports of `ee/` inside `src/`
To prevent the open-source gateway from failing when the enterprise extension folder is absent:
1.  **Never** statically import modules from `ee/` inside the `src/` folder.
2.  If you need to load proprietary enterprise middleware or extensions dynamically, always wrap the import in a graceful fallback block:
    ```python
    try:
        from ee.module import enterprise_feature
        HAS_ENTERPRISE = True
    except ImportError:
        HAS_ENTERPRISE = False
        # Define a safe fallback or pass
    ```

---

## 🛠️ Local Development Setup

To set up a local development environment:

### 1. Clone the Repository
```bash
git clone https://github.com/deveshsy/Cognihelm.git
cd Cognihelm
```

### 2. Configure a Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Local Credentials
Copy the environment variables template and configure your secrets:
```bash
cp .env.example .env
```
Ensure your local `.env` contains valid AWS and Slack configurations.

### 4. Run the Dev Servers
Start the API Gateway (`port 8000`):
```bash
venv/bin/python -m uvicorn src.main:app --port 8000 --reload
```
Start the local Compliance Console (`port 8080`):
```bash
venv/bin/python -m uvicorn src.console:app --port 8080 --reload
```

---

## 🧪 Testing Guidelines

Before submitting a Pull Request, verify that all tests pass successfully.

### Running Pytest
Run the test suite using the virtual environment interpreter:
```bash
venv/bin/python -m pytest
```

### Adding Tests
If you add a new platform adapter or edit webhook endpoints:
1.  Create a corresponding test case in `tests/test_adapters.py`.
2.  Mock DynamoDB and network requests using `unittest.mock.patch` to keep tests fast, offline, and reliable.
3.  Ensure you verify both success paths (valid credentials/signatures) and error paths (invalid signatures, failed validations).

---

## 🎨 Code & Security Conventions

1.  **Directory Structure Conventions**: Place API routers and adapters inside `src/api/` (adapters go in `src/api/adapters/`), business logic inside `src/services/`, database operations inside `src/db/`, and central settings models inside `src/core/`.
2.  **Non-Blocking Async I/O**: Do not run synchronous blocking calls (like `urllib` or `requests`) inside FastAPI `async def` routes. Use `httpx.AsyncClient` or run synchronous calls in threadpools.
3.  **Signature Verification**: Every new channel adapter must implement cryptographic signature verification inside its `verify_signature(request)` method. Never accept unverified webhook payloads in production.
4.  **Immutable Operations**: Never use `UpdateItem` or `DeleteItem` operations on the ledger database. All transaction updates must be written as new, timestamped rows.
