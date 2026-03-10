# Quick Start

Deploy your first Foundry agent via CI/CD in under 10 minutes.

---

## Prerequisites Checklist

Before starting, make sure you have:

- [x] **Python 3.10+** — run `python --version` to check
- [x] **Azure CLI** — run `az version` to check ([install](https://learn.microsoft.com/cli/azure/install-azure-cli))
- [x] **An Azure subscription** with Contributor access
- [x] **An AI Foundry project** — [create one](https://learn.microsoft.com/azure/ai-foundry/how-to/create-projects) if you don't have one
- [x] **A model deployed** in your Foundry account (gpt-4o-mini for dev)
- [x] **15 minutes** of uninterrupted time

!!! warning "Don't have a Foundry project yet?"
    You can deploy the infrastructure first using Bicep — see [Infrastructure Setup](../infrastructure/bicep.md).
    Or create one manually in the [Azure AI Foundry portal](https://ai.azure.com).

---

## Step 1: Clone the Repository

```bash
git clone https://github.com/ericchansen/foundry-agents-lifecycle.git
cd foundry-agents-lifecycle
```

## Step 2: Install Dependencies

```bash
pip install -e ".[dev]"
```

This installs everything defined in `pyproject.toml` — the Azure AI Projects SDK,
Azure Identity, and dev tools (pytest, ruff).

**Expected output:**
```
Successfully installed azure-ai-projects-2.0.0 azure-identity-1.x.x ...
```

## Step 3: Configure Your Environment

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
# Your Foundry project endpoint (find in Azure portal → AI Foundry → Project → Overview)
AZURE_AI_PROJECT_ENDPOINT=https://your-account.services.ai.azure.com/api/projects/your-project

# The environment to deploy (dev, test, or prod)
AGENT_ENVIRONMENT=dev
```

!!! tip "Where to find your endpoint"
    Azure Portal → AI Foundry → Your Project → Overview → **Project endpoint** (copy the full URL)

## Step 4: Authenticate to Azure

```bash
az login
```

!!! tip "Why `az login`?"
    The `DefaultAzureCredential` in our code automatically picks up your
    Azure CLI session. In CI/CD, it uses OIDC instead. Same code, different auth.

## Step 5: Dry-Run Deployment

Test that your config loads correctly without calling Azure:

```bash
python src/scripts/deploy_agent.py --env dev --dry-run
```

**Expected output:**
```
============================================================
  DEPLOYING AGENT — Environment: DEV
============================================================

  Agent Name:    foundry-demo-agent-dev
  Model:         gpt-4o-mini
  Tools:         2 tool(s)
  Instructions:  148 chars
  Metadata:      {'environment': 'dev', 'deployed_by': 'ci-cd-pipeline', ...}

  🔍 DRY RUN — No changes will be made.
```

!!! success "If you see this, your config is valid"
    The dry-run proves that the agent definition, system prompt, and tool
    configurations all load correctly. The next step actually calls Azure.

## Step 6: Deploy for Real

```bash
python src/scripts/deploy_agent.py --env dev
```

**Expected output:**
```
============================================================
  DEPLOYING AGENT — Environment: DEV
============================================================

  Agent Name:    foundry-demo-agent-dev
  Model:         gpt-4o-mini
  Tools:         2 tool(s)
  Instructions:  148 chars

  Project:       https://your-account.services.ai.azure.com/api/projects/...
  🚀 Creating agent 'foundry-demo-agent-dev'...
  ✅ Agent created successfully!
  📋 Agent ID: asst_abc123def456
  🏷️  Name:     foundry-demo-agent-dev
  🤖 Model:    gpt-4o-mini

============================================================
  DEPLOYMENT COMPLETE ✅
============================================================
```

## Step 7: Test Your Agent

Verify the agent actually works by sending it a query:

```bash
python src/scripts/test_agent.py --env dev --query "What is 25 times 4?"
```

**Expected output:**
```
  🔍 Found agent: foundry-demo-agent-dev
  💬 Sending query: What is 25 times 4?
  🤖 Response: 25 times 4 equals 100.
  ⏱️  Response time: 1.2s
```

!!! tip "Function tools"
    The agent is configured with a `calculator` function tool in
    `config/agent-config.dev.json`. If the agent invokes it, you'll see
    a `🔧 Tool call` line in the output. The model may also answer
    arithmetic directly without calling the tool.

You can also start an interactive chat:

```bash
python src/scripts/test_agent.py --env dev
```

## Step 8: Verify What's Deployed

List all agents in your Foundry project:

```bash
python src/scripts/list_agents.py
```

**Expected output:**
```
Name                                Model               ID                                       Created
------------------------------------------------------------------------------------------------------------------------
foundry-demo-agent-dev              gpt-4o-mini          asst_abc123def456                        2026-03-10T...
```

---

## ✅ You Just Did CI/CD!

After running those commands, you have:

- ✅ A live agent named `foundry-demo-agent-dev` in your Foundry project
- ✅ A deployment driven entirely by code (not portal clicks)
- ✅ A pipeline-ready script (the same `deploy_agent.py` runs in CI/CD)
- ✅ A tested, verified agent that responds to queries

**The exact same script that ran on your laptop runs in the CI/CD pipeline.**
That's the whole point — there's no manual portal step in the loop.

---

## What's Next?

| Next Step | What You'll Learn |
|-----------|-------------------|
| [Mental Model](../concepts/mental-model.md) | Why agents have no artifact to promote |
| [Set Up CI/CD](../pipelines/overview.md) | Automate deployments with GitHub Actions or ADO |
| [Environment Configs](../concepts/environment-configs.md) | How dev/test/prod differ |
| [Run Evaluations](../concepts/evaluation.md) | Quality gates before promotion |
| [Enterprise Guide](../pipelines/azure-devops.md) | ADO, Logic Apps, multi-subscription |
