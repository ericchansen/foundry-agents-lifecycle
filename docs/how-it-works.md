# How It Works — Step-by-Step Walkthrough

This document walks through **exactly** how CI/CD works for Foundry agents,
from a developer making a change to that change running in production.

---

## The Core Insight

> **There is no agent artifact to promote between environments.**

Unlike traditional software where you build a binary, container, or package
and promote it through environments, Foundry agents are **pure configuration**.
An agent is just:

| Component | Where It Lives | How It's Deployed |
|-----------|---------------|-------------------|
| System prompt | `src/agent/prompts/system_prompt.md` | Read by deploy script |
| Tool definitions | `src/agent/tools/*.py` | Registered via SDK |
| Model selection | `config/agent-config.{env}.json` | Passed to SDK |
| Agent name | `config/agent-config.{env}.json` | Passed to SDK |
| Metadata | Generated at deploy time | Passed to SDK |

**The agent IS its configuration.** CI/CD = "apply this configuration to the target environment."

---

## The Full CI/CD Flow

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Developer   │────▶│  Pull Request │────▶│  CI Pipeline  │────▶│   Merge      │
│  makes a     │     │  opened       │     │  (validate)   │     │   to main    │
│  change      │     │               │     │               │     │              │
└─────────────┘     └──────────────┘     └──────────────┘     └──────┬───────┘
                                                                      │
                                         ┌────────────────────────────┘
                                         ▼
                    ┌──────────────────────────────────────────────────────┐
                    │                CD Pipeline Stages                    │
                    │                                                      │
                    │  ┌──────────┐   ┌──────────┐   ┌──────────┐        │
                    │  │  DEV     │──▶│  TEST    │──▶│  PROD    │        │
                    │  │ (auto)   │   │ (approve)│   │ (approve)│        │
                    │  │          │   │          │   │          │        │
                    │  │ deploy → │   │ deploy → │   │ deploy → │        │
                    │  │ evaluate │   │ evaluate │   │ evaluate │        │
                    │  └──────────┘   └──────────┘   └──────────┘        │
                    └──────────────────────────────────────────────────────┘
```

---

## Step 1: Developer Makes a Change

A developer modifies one or more of these:

- **System prompt** (`src/agent/prompts/system_prompt.md`) — e.g., "be more concise"
- **Tool code** (`src/agent/tools/calculator.py`) — e.g., add a new function tool
- **Agent config** (`config/agent-config.*.json`) — e.g., switch to a different model
- **Infrastructure** (`infra/*.bicep`) — e.g., add a new model deployment

They create a branch and open a Pull Request.

---

## Step 2: CI Pipeline Validates (Automatic)

When the PR is opened, the CI pipeline (`.github/workflows/ci.yml`) runs:

### 2a. Lint Check
```bash
ruff check src/
```
Catches code style issues, unused imports, basic bugs.

### 2b. Unit Tests
```bash
pytest src/tests/unit/ -v
```
Validates:
- All config files are valid JSON with required fields
- Prompt files referenced by configs actually exist
- Agent names meet Foundry's naming rules (alphanumeric + hyphens, ≤63 chars)
- Tool definitions have the correct schema
- Config loading logic works for all environments

### 2c. Dry-Run Deployment
```bash
python src/scripts/deploy_agent.py --env dev --dry-run
python src/scripts/deploy_agent.py --env prod --dry-run
```
Loads the config and converts it to SDK parameters, but **doesn't call Azure**.
Catches configuration errors before any deployment attempt.

If any step fails, the PR **cannot be merged**.

---

## Step 3: Code is Merged to Main

After PR review and CI passing, the code is merged to `main`.
This triggers the CD pipeline.

---

## Step 4: CD Deploys to DEV (Automatic)

The CD pipeline (`.github/workflows/cd.yml`) starts:

### 4a. Authenticate to Azure
```yaml
- uses: azure/login@v2
  with:
    client-id: ${{ secrets.AZURE_CLIENT_ID }}
    tenant-id: ${{ secrets.AZURE_TENANT_ID }}
    subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```
Uses OIDC federation — no secrets stored in GitHub!

### 4b. Deploy the Agent
```bash
python src/scripts/deploy_agent.py --env dev
```

This script:
1. Loads `config/agent-config.dev.json`
2. Reads the system prompt from `src/agent/prompts/system_prompt.md`
3. Resolves tool definitions from Python code
4. Builds a `PromptAgentDefinition` (SDK v2) with model, instructions, tools
5. Connects to the DEV Foundry project
6. Checks if the agent exists → deletes old version (or updates if delete fails)
7. Creates a new agent via `agents.create()`

### 4c. Evaluate the Agent
```bash
python src/scripts/run_evaluation.py --env dev
```

Runs test questions against the deployed agent and scores the responses.
In dev, thresholds are relaxed (3.0/5.0) to allow experimentation.

---

## Step 5: Manual Approval → Deploy to TEST

The pipeline **pauses** and waits for a human to approve.
(Configured via GitHub Environments or ADO Environments.)

When approved, the **exact same process** runs for TEST:
- Different config: `config/agent-config.test.json`
- Different (or same) Foundry project
- Stricter eval thresholds (3.5/5.0)

---

## Step 6: Manual Approval → Deploy to PROD

Same pattern, stricter controls:
- Config: `config/agent-config.prod.json`
- May use a different system prompt (`system_prompt.prod.md`)
- Uses the production model (gpt-4o) with higher capacity
- Strictest eval thresholds (4.0/5.0)
- May require multiple approvers

---

## What Happens in Each Environment?

| Aspect | DEV | TEST | PROD |
|--------|-----|------|------|
| Model | gpt-4o-mini | gpt-4o | gpt-4o |
| Capacity | 10K TPM | 20K TPM | 50K TPM |
| Prompt | standard | standard | production |
| Eval threshold | 3.0 | 3.5 | 4.0 |
| Approval | None | 1 approver | 2+ approvers |
| Deploy | Automatic | Manual gate | Manual gate |

---

## Key Files Reference

| File | Purpose | When It's Used |
|------|---------|----------------|
| `src/agent/agent_definition.py` | Loads config + prompt → agent params | Every deployment |
| `src/scripts/deploy_agent.py` | Creates/updates agent via SDK | Every deployment |
| `src/scripts/run_evaluation.py` | Runs eval quality gate | After each deployment |
| `config/agent-config.{env}.json` | Per-environment agent settings | Loaded by agent_definition.py |
| `src/agent/prompts/system_prompt.md` | The agent's system prompt | Read at deploy time |
| `.github/workflows/cd.yml` | GitHub Actions CD pipeline | On merge to main |
| `.azdo/pipelines/cd-pipeline.yml` | Azure DevOps CD pipeline | On merge to main (ADO) |
| `infra/main.bicep` | Infrastructure (Foundry, models, KV) | Initial setup or infra changes |
