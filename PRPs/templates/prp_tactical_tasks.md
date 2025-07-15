
### The Philosophy: Why This Works

Before the template, the creed. This approach is built on three pillars:

1.  **One Task, One File.** The AI's entire universe for a single job is contained within one PRP file. This eliminates context switching and cognitive overload.
2.  **Context is Not a Pointer; It is the Payload.** You do not link to docs. You *embed* the relevant snippets. You don't describe a pattern. You *provide* the code example. The PRP is a self-contained data packet.
3.  **Validation is the Contract.** The "Validation Gate" section is not a suggestion. It is a non-negotiable, deterministic definition of "done." The AI's job is to make those commands pass. Nothing more, nothing less.

### The Workflow: How to Wield This Weapon

1.  **Consult the Master Blueprint:** Open your grand `NARRATIVE_FACTORY_PRP_v2.md`.
2.  **Identify One Atomic Task:** Look at your `Ordered Task List`. Select the very next, smallest, most logical unit of work (e.g., "Implement JWT authentication").
3.  **Create a New PRP File:** Create a new file using the naming convention: `PRP-[Phase]-[Task#]-[BriefName].md`. (e.g., `PRP-P0-T7-Authentication.md`).
4.  **Fill Out the Template:** Use the template below to fill in every section with meticulous detail. This is the part that requires your human intelligence.
5.  **Deliver the Surgical PRP:** Give this single, small file to your AI agent.
6.  **Verify & Commit:** Once the AI has made the Validation Gate pass, review the code and commit it to your repository.
7.  **Archive the PRP & Repeat:** Move the completed PRP to an "archive" or "done" folder. Go back to step 1.

---

## The Nova-Forged Surgical PRP Template v1.0

```markdown
# PRP: [Action-Oriented Title of the Task]

**PRP Version:** 1.0  
**Status:** READY_FOR_EXECUTION  
**Parent Epic:** [Link or Filename of the Master Blueprint, e.g., NARRATIVE_FACTORY_PRP_v2.md]  
**Target Agent:** [e.g., Claude, GPT-4]

---

## 1. The Goal (The "What")

> A single, concise sentence starting with a verb. What is the observable outcome of this task?

Implement a [COMPONENT/FUNCTION/FEATURE] that [ACHIEVES A SPECIFIC GOAL].

---

## 2. The Context Payload (The "With What")

> This section contains ALL information the AI needs. No external lookups allowed.

#### Files to Create/Modify:
- **CREATE:** `path/to/new/file.ts`
- **UPDATE:** `path/to/existing/file.py`

#### Key Dependencies & Imports:
- `fastapi`: For creating the API router.
- `pydantic`: For data models `User` and `Token`.
- `python-jose[cryptography]`: Specifically the `jwt` module for token creation.

#### Required Patterns & Code Snippets:
> CRITICAL: Provide direct code snippets the AI must follow.

**Pattern for FastAPI Dependency Injection:**
```python
# You MUST use this pattern for protected routes.
async def get_current_user(token: str = Depends(oauth2_scheme)):
    # ... logic to decode token and fetch user ...
```

#### Environment Variables Required:
- `SECRET_KEY`: The secret key for signing the JWT.
- `ALGORITHM`: The algorithm to use (e.g., `HS256`).
- `ACCESS_TOKEN_EXPIRE_MINUTES`: The token's time-to-live.

---

## 3. The Implementation Blueprint (The "How")

> The detailed, step-by-step logic and structure.

#### Logic Steps / Pseudocode:
1.  In `security.py`, create a function `create_access_token` that accepts a `data` dictionary and `expires_delta`.
2.  It should encode the data into a JWT using the `SECRET_KEY` and `ALGORITHM`.
3.  In `auth.py`, create a `POST /token` endpoint.
4.  This endpoint must authenticate the user (for now, use a hardcoded dummy user).
5.  If authentication is successful, call `create_access_token` to generate a JWT and return it.

#### Data Models / Type Definitions:
> Provide the exact Pydantic/TypeScript models required.

```python
# In models/token.py
from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
```

---

## 4. The Validation Gate (The "Definition of Done")

> **This is the contract.** The task is complete ONLY when all commands in this section execute successfully without error.

#### L1: Static Analysis (Syntax, Style, Types)
```bash
# First, ensure the code is clean.
ruff check path/to/changed/files/
mypy path/to/changed/files/ --strict
```

#### L2: Unit & Integration Tests (Functional Correctness)
> The primary measure of success. Provide the exact test cases.

**Create/Update `tests/test_auth.py` with the following tests:**
- `test_get_token_success()`: Mocks a valid user, calls `/token`, and asserts a token is returned.
- `test_get_token_failure()`: Uses invalid credentials and asserts a 401 error.
- `test_read_protected_route_success()`: Gets a valid token, then uses it to call a protected endpoint, asserting a 200 OK.
- `test_read_protected_route_failure()`: Calls a protected endpoint without a token, asserting a 401 error.

**Execution Command:**
```bash
# The final gate. This MUST pass.
pytest tests/test_auth.py -v
```
---
```