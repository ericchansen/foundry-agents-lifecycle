# Enterprise-Specific Guidance

This document addresses specific constraints and requirements for teams
using Azure DevOps, Logic Apps, and multi-subscription environments.

---

## Azure DevOps (Instead of GitHub Actions)

### What's Different

| Concept | GitHub Actions | Azure DevOps |
|---------|---------------|-------------|
| Pipeline file | `.github/workflows/*.yml` | `.azdo/pipelines/*.yml` |
| Authentication | OIDC federation | Service Connections |
| Env protection | GitHub Environments | ADO Environments |
| Variables | `${{ secrets.X }}` / `${{ vars.X }}` | `$(variableName)` |
| Runners | `runs-on: ubuntu-latest` | `pool: { vmImage: 'ubuntu-latest' }` |
| Stages | Jobs with `needs` | Explicit `stages` block |
| Approval gates | Environment protection rules | Environment checks & approvals |

### Setting Up Service Connections

Instead of OIDC federation, Azure DevOps uses **Service Connections**:

1. Go to **Project Settings → Service Connections**
2. Create **Azure Resource Manager** connection for each environment:
   - `azure-dev` → Dev subscription
   - `azure-test` → Test subscription
   - `azure-prod` → Prod subscription
3. Use **Workload Identity Federation** (recommended) or **Service Principal**

### Setting Up Environments

1. Go to **Pipelines → Environments**
2. Create environments: `dev`, `test`, `prod`
3. Configure approvals:
   - `dev`: No approvals
   - `test`: 1 approver required
   - `prod`: 2+ approvers required, optional wait timer

### Pipeline Files

The Azure DevOps pipelines are in `.azdo/pipelines/`:
- `ci-pipeline.yml` — PR validation (same logic as GitHub CI)
- `cd-pipeline.yml` — Multi-stage deployment (same flow as GitHub CD)

---

## Multi-Subscription Environments

### Recommended Architecture

```
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  Dev Subscription     │  │  Test Subscription    │  │  Prod Subscription   │
│                       │  │                       │  │                      │
│  ┌─────────────────┐ │  │  ┌─────────────────┐ │  │  ┌─────────────────┐│
│  │ Resource Group   │ │  │  │ Resource Group   │ │  │  │ Resource Group  ││
│  │                  │ │  │  │                  │ │  │  │                 ││
│  │ • Foundry Account│ │  │  │ • Foundry Account│ │  │  │ • Foundry Acct  ││
│  │ • Foundry Project│ │  │  │ • Foundry Project│ │  │  │ • Foundry Proj  ││
│  │ • GPT-4o-mini   │ │  │  │ • GPT-4o         │ │  │  │ • GPT-4o       ││
│  │ • Key Vault     │ │  │  │ • GPT-4o-mini    │ │  │  │ • GPT-4o-mini  ││
│  └─────────────────┘ │  │  │ • Key Vault      │ │  │  │ • Key Vault    ││
│                       │  │  └─────────────────┘ │  │  └─────────────────┘│
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

### How This Works with the Pipeline

Each environment has its own:
1. **Subscription** (isolated billing and access control)
2. **Service Connection** (pipeline identity per subscription)
3. **Foundry Project Endpoint** (where agents are deployed)
4. **Bicep Parameters** (different models, capacities, settings)

The pipeline variable `AZURE_AI_PROJECT_ENDPOINT` changes per environment:
- Dev: `https://foundry-demo-dev.services.ai.azure.com/api/projects/...`
- Test: `https://foundry-demo-test.services.ai.azure.com/api/projects/...`
- Prod: `https://foundry-demo-prod.services.ai.azure.com/api/projects/...`

### Deploying Infrastructure per Subscription

**Option A: Subscription-scoped (pipeline recommended)**

```bash
# Dev
az deployment sub create \
  --location eastus2 \
  --template-file infra/deploy-infra.bicep \
  --parameters environment=dev pipelineSource=ado

# Prod
az deployment sub create \
  --location eastus2 \
  --template-file infra/deploy-infra.bicep \
  --parameters environment=prod pipelineSource=ado
```

This creates the resource group automatically. Use `pipelineSource=ado` for
ADO pipelines or `pipelineSource=github` for GitHub Actions.

**Option B: Resource-group-scoped (manual / existing RG)**

```bash
# Dev
az account set --subscription "Dev Subscription"
az deployment group create \
  --resource-group rg-foundry-demo-dev \
  --template-file infra/main.bicep \
  --parameters infra/environments/dev.parameters.json

# Prod
az account set --subscription "Prod Subscription"
az deployment group create \
  --resource-group rg-foundry-demo-prod \
  --template-file infra/main.bicep \
  --parameters infra/environments/prod.parameters.json
```

---

## Logic Apps CI/CD

### The Challenge

If your agent uses **Logic Apps as tools**, those Logic Apps also need CI/CD.
But Logic Apps come in two flavors with very different deployment models:

| Aspect | Standard | Consumption |
|--------|----------|-------------|
| Hosting | Dedicated (App Service Plan) | Serverless |
| CI/CD | Zip deploy (like web apps) | ARM/Bicep templates |
| Source control | File-based workflows | JSON definition only |
| Parameterization | App settings + parameters.json | ARM template parameters |
| **Foundry agent tool** | Can be used | Often required for tools |

### Standard Logic Apps (Recommended)

Standard Logic Apps have proper CI/CD support:

```bash
# 1. Build the Logic App project
cd logic-app-project/
zip -r ../logic-app.zip .

# 2. Deploy via zip deploy
az functionapp deployment source config-zip \
  --resource-group rg-foundry-demo-dev \
  --name la-foundry-demo-dev \
  --src logic-app.zip
```

**In the pipeline:**
```yaml
- task: AzureCLI@2
  displayName: "Deploy Logic App (Standard)"
  inputs:
    azureSubscription: "azure-dev"
    scriptType: "bash"
    scriptLocation: "inlineScript"
    inlineScript: |
      cd logic-apps/
      zip -r ../logic-app.zip .
      az functionapp deployment source config-zip \
        --resource-group $(RESOURCE_GROUP) \
        --name $(LOGIC_APP_NAME) \
        --src ../logic-app.zip
```

### Consumption Logic Apps (ARM Templates)

Consumption Logic Apps can only be deployed via ARM/Bicep:

```bicep
// infra/modules/logic-app-consumption.bicep
resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'la-agent-tool-${environment}'
  location: location
  properties: {
    definition: {
      // The workflow definition goes here
      // Export it from the portal, then parameterize it
    }
    parameters: {
      // Environment-specific parameters
    }
  }
}
```

### Separate Pipeline Stages

Logic Apps and Foundry agents should deploy in a specific order:

```
1. Deploy Infrastructure (Bicep)      — Foundry account, Key Vault, models
2. Deploy Logic Apps                   — They must exist before agents reference them
3. Deploy Agent (SDK)                  — Agent can now reference Logic App tools
4. Run Evaluation                      — Validate agent + tools work together
```

---

## Migrating from Portal-Authored Agents

If agents were initially created in the Foundry portal, here's how to codify them:

### Step 1: Document What's in the Portal

In the Foundry portal, note:
- Agent name
- Model deployment used
- System prompt (copy the full text)
- Tools configured (code interpreter, functions, file search, etc.)
- Any file attachments or knowledge sources

### Step 2: Create the Config File

Map the portal settings to `config/agent-config.{env}.json`:

```json
{
    "agent": {
        "name": "my-portal-agent",
        "model": "gpt-4o-mini",
        "instructions_file": "src/agent/prompts/system_prompt.md",
        "tools": [
            {"type": "code_interpreter"},
            {"type": "function", "function_name": "my_tool"}
        ]
    }
}
```

### Step 3: Save the System Prompt

Copy the system prompt from the portal into `src/agent/prompts/system_prompt.md`.

### Step 4: Codify Any Custom Tools

If the agent uses custom function tools, implement them in `src/agent/tools/`.

### Step 5: Test the Codified Agent

```bash
# Deploy the codified agent to dev
python src/scripts/deploy_agent.py --env dev

# Verify it behaves the same as the portal version
python src/scripts/run_evaluation.py --env dev
```

### Step 6: Delete the Portal Agent

Once the codified agent is validated, delete the portal-created one.
From now on, all changes go through code → PR → CI/CD.
