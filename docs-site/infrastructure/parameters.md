# Environment Parameters

How to customize Bicep deployments per environment.

---

## Parameter Files

Each environment has a `.parameters.json` file that customizes the Bicep deployment:

```
infra/environments/
├── dev.parameters.json
├── test.parameters.json
└── prod.parameters.json
```

## Parameter Reference

| Parameter | Type | Description |
|-----------|------|-------------|
| `baseName` | string | Base name for all resources (e.g., `foundry-demo`) |
| `environment` | string | Environment name (`dev`, `test`, `prod`) |
| `modelDeployments` | array | Which AI models to deploy and their capacity |
| `deployerPrincipalId` | string | (Optional) Service principal ID for RBAC |

## Model Deployment Object

Each entry in `modelDeployments` has:

```json
{
  "name": "gpt-4o",              // Deployment name (referenced in agent config)
  "model": "gpt-4o",             // Azure AI model name
  "version": "2024-11-20",       // Model version
  "sku": "GlobalStandard",       // Pricing tier
  "capacity": 50                 // Tokens per minute (thousands)
}
```

!!! tip "Match model names to agent config"
    The `name` field here must match the `model` field in your
    `agent-config.{env}.json`. This is how the agent knows which
    model deployment to use.

## Capacity Planning

| Environment | Model | Capacity | Reasoning |
|-------------|-------|----------|-----------|
| Dev | gpt-4o-mini only | 10K TPM | Cheap, fast, for iteration |
| Test | gpt-4o + gpt-4o-mini | 20K TPM | Production model for realistic testing |
| Prod | gpt-4o + gpt-4o-mini | 50K TPM | Full capacity for real traffic |

## Multi-Subscription Pattern

For maximum isolation, deploy infrastructure to different subscriptions:

```bash
# Dev subscription
az account set --subscription "Dev Sub"
az deployment group create -g rg-foundry-dev \
  -f infra/main.bicep \
  -p infra/environments/dev.parameters.json

# Prod subscription
az account set --subscription "Prod Sub"
az deployment group create -g rg-foundry-prod \
  -f infra/main.bicep \
  -p infra/environments/prod.parameters.json
```

Each subscription gets its own Foundry account, project, models, and Key Vault.
The only thing shared is the source code in git.
