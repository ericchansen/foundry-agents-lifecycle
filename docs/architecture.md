# Architecture Decisions

This document explains the **why** behind the architecture choices in this demo.

---

## Decision 1: Code-First, Not Portal-First

**Decision:** Define agents entirely in code, not in the Foundry portal.

**Why:**
- The Foundry portal has no export/import for agents
- Portal-created agents can't be version-controlled
- There's no way to diff, review, or rollback portal changes
- The SDK is the only way to automate agent creation

**Trade-off:**
- Developers must learn the SDK and write Python
- Can't "click around" in the portal to configure agents
- Prototyping is slightly slower (but more reliable)

**Recommendation:**
Use the portal for initial exploration and testing. Once you know what you want,
codify it in `agent_definition.py` and never use the portal for that agent again.

---

## Decision 2: Versioned Agents (Not Delete + Recreate)

**Decision:** Each deployment creates a new **version** of the agent using `agents.create_version()`.

**Why:**
- SDK v2 supports agent versioning natively
- Each version is a snapshot of the agent config at deployment time
- No downtime — old version stays active until new one is ready
- Metadata tracks the git SHA, so you always know what code maps to which version

**Trade-off:**
- Agent versions accumulate (can be cleaned up with teardown script)
- Must ensure consumers reference the correct version

**How it works in the deploy script:**
```python
# Create a new version of the agent from the config
agent = client.agents.create_version(
    name=config.name,
    definition=config.to_sdk_params()["definition"],
    metadata=config.metadata,
)
```

---

## Decision 3: Per-Environment Config Files

**Decision:** Use JSON config files per environment, not environment variables alone.

**Why:**
- Config files are version-controlled and reviewable
- Easy to diff dev vs prod configurations
- Unit tests can validate all configs at once
- More readable than long lists of env vars

**What goes in config files (not secrets):**
- Agent name
- Model selection
- Tool configuration
- Eval thresholds

**What stays in environment variables (secrets):**
- `AZURE_AI_PROJECT_ENDPOINT` (varies by environment)
- `AZURE_CLIENT_ID` (pipeline identity)
- Any API keys or connection strings

---

## Decision 4: OIDC Federation for Authentication

**Decision:** Use OIDC (OpenID Connect) federation instead of client secrets.

**Why:**
- No secrets to store, rotate, or leak
- Azure trusts the GitHub/ADO identity token directly
- Works with managed identity in Azure-hosted runners
- Best practice per Microsoft security guidance

**Setup (GitHub Actions):**
```bash
# 1. Create an app registration
az ad app create --display-name "foundry-agents-lifecycle"

# 2. Add a federated credential for GitHub Actions
az ad app federated-credential create \
  --id <APP_ID> \
  --parameters '{
    "name": "github-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:your-org/foundry-agents-lifecycle:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# 3. Grant the app "Azure AI User" role on your Foundry project
az role assignment create \
  --assignee <APP_ID> \
  --role "Azure AI User" \
  --scope /subscriptions/<SUB_ID>/resourceGroups/<RG>/providers/Microsoft.CognitiveServices/accounts/<ACCOUNT>
```

**For Azure DevOps:**
Use Service Connections with workload identity federation (similar concept, ADO UI).

---

## Decision 5: Evaluation as a Quality Gate

**Decision:** Run automated evaluations in the pipeline before promoting to the next environment.

**Why:**
- AI agents can regress silently (a prompt change might hurt quality)
- Automated evaluation catches regressions before users see them
- Different thresholds per environment allow iteration in dev but enforce quality in prod

**How it works:**
1. Pipeline deploys agent to environment
2. Evaluation script sends test questions to the agent
3. Foundry evaluators score responses (groundedness, relevance, coherence)
4. If scores are below thresholds, pipeline fails → no promotion

**Thresholds by environment:**
| Environment | Groundedness | Relevance | Coherence | Task Adherence | Intent Resolution | Tool Call Accuracy |
|-------------|-------------|-----------|-----------|----------------|-------------------|--------------------|
| Dev         | 3.0         | 3.0       | 3.0       | 3.0            | 3.0               | 3.0                |
| Test        | 3.5         | 3.5       | 3.5       | 3.5            | 3.5               | 3.5                |
| Prod        | 4.0         | 4.0       | 4.0       | 4.0            | 4.0               | 4.0                |

---

## Decision 6: Bicep for Infrastructure

**Decision:** Use Bicep (not Terraform) for Azure infrastructure.

**Why:**
- Bicep is Azure-native — tightest integration with ARM
- No state file to manage (ARM tracks deployed state)
- Simpler syntax than ARM JSON templates
- Works directly with `az deployment` commands

**For Terraform shops:**
The same concepts apply. Replace Bicep files with Terraform `.tf` files.
The agent deployment script (`deploy_agent.py`) remains the same regardless
of which IaC tool you use for infrastructure.

---

## Decision 7: Subscription-Level Deployment for Dual-Pipeline Isolation

**Decision:** Use a subscription-scoped Bicep file (`deploy-infra.bicep`) that creates
resource groups dynamically, parameterized by `pipelineSource` (github or ado).

**Why:**
- When both GitHub Actions and Azure DevOps deploy the same app, they need
  isolated resource groups to avoid conflicts
- A resource-group-scoped deployment can't create its own resource group
  (chicken-and-egg problem)
- Subscription-level deployment solves this: it creates the RG, then deploys into it

**Resource Group Naming:**

| Pipeline Source | Environment | Resource Group |
|----------------|-------------|-------------------------------|
| GitHub Actions | dev         | `rg-foundry-github-dev`       |
| GitHub Actions | prod        | `rg-foundry-github-prod`      |
| Azure DevOps   | dev         | `rg-foundry-ado-dev`          |
| Azure DevOps   | prod        | `rg-foundry-ado-prod`         |

**How it works:**
```
deploy-infra.bicep (subscription scope)
  ├── Creates resource group: rg-foundry-{pipelineSource}-{env}
  └── Calls main.bicep (resource group scope) as a module
        ├── foundry-account.bicep  → AI Foundry account + project
        ├── model-deployments.bicep → GPT models
        └── keyvault.bicep         → Key Vault for secrets
```

**Trade-off:**
- Pipeline identity needs Contributor at the **subscription level** (not just RG level)
- More resource groups to manage (but Azure tags make them easy to find)

**Setup requirement:**
The service principal or managed identity used by the pipeline must have `Contributor`
role at the subscription scope to create resource groups.
