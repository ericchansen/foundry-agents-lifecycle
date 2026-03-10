# CI/CD for Microsoft Foundry Agents — Reference Demo

> **TL;DR:** Foundry agents have no portal export/import or artifact promotion.
> CI/CD means **defining agents in code** and **recreating them via SDK** in each environment.
> This repo shows you exactly how to do that.

---

## 🎯 What This Demo Teaches

| Concept | What You'll Learn |
|---------|-------------------|
| **Code-First Agents** | Define agents entirely in Python using the `azure-ai-projects` SDK |
| **Infrastructure as Code** | Bicep templates for Foundry account, project, models, Key Vault |
| **Environment Promotion** | Same code → different configs → deploy to dev/test/prod |
| **CI/CD Pipelines** | GitHub Actions (best practice) + Azure DevOps (for ADO shops) |
| **Evaluation Gates** | Run Foundry evaluations in CI/CD — block bad agents from reaching prod |
| **Logic Apps CI/CD** | Deploy Logic Apps alongside agents (Standard + Consumption patterns) |

---

## 🧠 The Key Mental Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    WHAT CI/CD IS NOT                             │
│                                                                 │
│  ❌ Export agent from Foundry portal                            │
│  ❌ Promote an "agent artifact" between environments            │
│  ❌ Use Foundry "Solutions" for deployment                      │
│  ❌ Copy agent settings manually between projects               │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                    WHAT CI/CD ACTUALLY IS                        │
│                                                                 │
│  ✅ Agent config lives in YOUR code repo (Python/JSON)          │
│  ✅ SDK script creates/updates the agent in each environment    │
│  ✅ Bicep/Terraform provisions the infrastructure               │
│  ✅ Pipeline orchestrates: test → eval → deploy                 │
│  ✅ Each environment gets a FRESH agent from the same code      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Repository Structure

```
foundry-agents-lifecycle/
│
├── README.md                          ← You are here
├── azure.yaml                         ← azd project config
├── pyproject.toml                     ← Python dependencies
├── .env.example                       ← Template for local development
│
├── infra/                             ← 🏗️ Infrastructure as Code (Bicep)
│   ├── deploy-infra.bicep             ← Entry point (subscription-level)
│   ├── main.bicep                     ← Orchestrator (resource-group-level)
│   ├── modules/
│   │   ├── foundry-account.bicep      ← AI Foundry account + project
│   │   ├── model-deployments.bicep    ← GPT-4o, GPT-4o-mini, etc.
│   │   └── keyvault.bicep             ← Secrets management
│   └── environments/
│       ├── dev.parameters.json        ← Dev-specific settings
│       ├── test.parameters.json       ← Test-specific settings
│       └── prod.parameters.json       ← Prod-specific settings
│
├── src/
│   ├── agent/                         ← 🤖 Agent definition & code
│   │   ├── agent_definition.py        ← THE core file — defines the agent
│   │   ├── tools/                     ← Agent tools (functions, MCP, etc.)
│   │   │   ├── __init__.py
│   │   │   └── calculator.py          ← Example function tool
│   │   └── prompts/
│   │       ├── system_prompt.md       ← Main system prompt
│   │       └── system_prompt.prod.md  ← Production override (optional)
│   │
│   ├── scripts/                       ← 🔧 Deployment & management scripts
│   │   ├── deploy_agent.py            ← Create/update agent via SDK
│   │   ├── run_evaluation.py          ← Run Foundry evaluations
│   │   ├── list_agents.py             ← List agents in a project
│   │   └── teardown_agent.py          ← Delete agent (cleanup)
│   │
│   └── tests/                         ← 🧪 Tests
│       ├── unit/
│       │   └── test_agent_config.py   ← Validate agent configuration
│       └── integration/
│           └── eval_dataset.jsonl     ← Evaluation test data
│
├── config/                            ← ⚙️ Per-environment agent configs
│   ├── agent-config.dev.json          ← Dev: cheaper model, verbose logging
│   ├── agent-config.test.json         ← Test: production model, test data
│   └── agent-config.prod.json         ← Prod: production model, real data
│
├── .github/workflows/                 ← 🚀 GitHub Actions (best practice)
│   ├── ci.yml                         ← PR validation
│   └── cd.yml                         ← Deploy to environments
│
├── .azdo/pipelines/                   ← 🔄 Azure DevOps (for ADO shops)
│   ├── ci-pipeline.yml
│   ├── cd-pipeline.yml
│   └── templates/
│       └── deploy-stage.yml           ← Reusable deploy stage template
│
└── docs/                              ← 📚 Documentation
    ├── architecture.md                ← Architecture decisions & rationale
    ├── how-it-works.md                ← Step-by-step walkthrough
    └── enterprise-guidance.md          ← Accommodating enterprise constraints
```

---

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+** — [Download](https://www.python.org/downloads/)
2. **Azure CLI** — [Install](https://learn.microsoft.com/cli/azure/install-azure-cli)
3. **Azure Developer CLI (azd)** — [Install](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
4. **An Azure subscription** with permissions to create AI Foundry resources

### 1. Clone & Install

```bash
git clone <this-repo>
cd foundry-agents-lifecycle
pip install -e ".[dev]"
```

### 2. Configure Your Environment

```bash
cp .env.example .env
# Edit .env with your Azure details:
#   AZURE_AI_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
```

### 3. Deploy Infrastructure (First Time)

> ⚠️ **Subscription-level Contributor required:** The Bicep deployment creates resource
> groups, which requires **Contributor** role at the subscription level (not just resource group).

```bash
# Option A: Using azd (recommended)
azd up

# Option B: Using Bicep directly (subscription-level — creates resource group)
az deployment sub create \
  --location eastus2 \
  --template-file infra/deploy-infra.bicep \
  --parameters environment=dev pipelineSource=github

# Option C: Using Bicep directly (resource-group-level — RG must exist)
az deployment group create \
  --resource-group rg-foundry-demo-dev \
  --template-file infra/main.bicep \
  --parameters infra/environments/dev.parameters.json
```

### 4. Deploy the Agent

```bash
# This is the key command — it creates/updates your agent via SDK
python src/scripts/deploy_agent.py --env dev
```

### 5. Test the Agent

```bash
python src/scripts/test_agent.py --env dev
```

---

## 📖 How CI/CD Works (Step by Step)

See [docs/how-it-works.md](docs/how-it-works.md) for the full walkthrough.

**Short version:**

1. **Developer** changes agent code (prompts, tools, config)
2. **PR is opened** → CI pipeline runs lint, unit tests, evaluation
3. **PR is merged** → CD pipeline deploys to dev automatically
4. **Manual approval** → CD promotes to test, then prod
5. **Each environment** gets the agent recreated from the same code + env-specific config

---

## 🤔 FAQ

**Q: Can I keep using the Foundry portal to author agents?**
> You can prototype in the portal, but for CI/CD you must codify the agent definition.
> See `src/scripts/deploy_agent.py` for how agent config maps to SDK calls.

**Q: What about Logic Apps used as agent tools?**
> Logic Apps need their own CI/CD pipeline. Standard Logic Apps support zip deploy with proper
> CI/CD. Consumption Logic Apps must use ARM/Bicep templates. See [docs/enterprise-guidance.md](docs/enterprise-guidance.md).

**Q: We use Azure DevOps, not GitHub Actions. Does this still work?**
> Yes! The `.azdo/pipelines/` directory has equivalent Azure DevOps YAML pipelines.
> Same concepts, different syntax. See [docs/enterprise-guidance.md](docs/enterprise-guidance.md).

**Q: How do we handle secrets?**
> Secrets go in Azure Key Vault, referenced via managed identity. Never in code.
> See `infra/modules/keyvault.bicep` and the pipeline OIDC/service connection setup.

---

## 📚 Further Reading

- [Azure AI Foundry Agent Service docs](https://learn.microsoft.com/azure/ai-foundry/agents/)
- [azure-ai-projects Python SDK](https://learn.microsoft.com/python/api/azure-ai-projects/)
- [azd AI Agent Extension](https://learn.microsoft.com/azure/developer/azure-developer-cli/extensions/azure-ai-foundry-extension)
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework)
- [Foundry Evaluation GitHub Action](https://learn.microsoft.com/azure/ai-foundry/how-to/evaluation-github-action)
