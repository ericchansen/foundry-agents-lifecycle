# Multi-Subscription Environments

Maximum isolation using separate Azure subscriptions per environment.

---

## Architecture

```
┌──────────────────────────┐  ┌──────────────────────────┐  ┌──────────────────────────┐
│    Dev Subscription       │  │    Test Subscription      │  │    Prod Subscription     │
│                           │  │                           │  │                          │
│  ┌────────────────────┐  │  │  ┌────────────────────┐  │  │  ┌────────────────────┐ │
│  │ rg-foundry-dev     │  │  │  │ rg-foundry-test    │  │  │  │ rg-foundry-prod    │ │
│  │                    │  │  │  │                    │  │  │  │                    │ │
│  │ • Foundry Account  │  │  │  │ • Foundry Account  │  │  │  │ • Foundry Account  │ │
│  │ • Foundry Project  │  │  │  │ • Foundry Project  │  │  │  │ • Foundry Project  │ │
│  │ • GPT-4o-mini      │  │  │  │ • GPT-4o           │  │  │  │ • GPT-4o           │ │
│  │ • Key Vault        │  │  │  │ • Key Vault        │  │  │  │ • Key Vault        │ │
│  └────────────────────┘  │  │  └────────────────────┘  │  │  └────────────────────┘ │
└──────────────────────────┘  └──────────────────────────┘  └──────────────────────────┘
```

## Why Separate Subscriptions?

| Benefit | Description |
|---------|-------------|
| **Billing isolation** | Each environment has its own cost tracking |
| **Access control** | Dev team can't accidentally touch prod |
| **Quota isolation** | Dev usage doesn't eat into prod capacity |
| **Compliance** | Some regulations require environment separation |
| **Blast radius** | A misconfiguration in dev can't break prod |

## Pipeline Configuration

Each pipeline stage targets a different subscription via separate
credentials:

=== "GitHub Actions"

    Each **GitHub Environment** has its own secrets:

    | Environment | `AZURE_SUBSCRIPTION_ID` | `AZURE_AI_PROJECT_ENDPOINT` |
    |-------------|------------------------|---------------------------|
    | `dev` | Dev subscription ID | Dev project endpoint |
    | `test` | Test subscription ID | Test project endpoint |
    | `prod` | Prod subscription ID | Prod project endpoint |

=== "Azure DevOps"

    Each **Service Connection** points to a different subscription:

    | Service Connection | Target Subscription |
    |-------------------|-------------------|
    | `azure-dev` | Dev subscription |
    | `azure-test` | Test subscription |
    | `azure-prod` | Prod subscription |

## Deploying Infrastructure

```bash
# Dev
az account set --subscription "Dev Subscription"
az deployment group create \
  --resource-group rg-foundry-dev \
  --template-file infra/main.bicep \
  --parameters infra/environments/dev.parameters.json

# Test
az account set --subscription "Test Subscription"
az deployment group create \
  --resource-group rg-foundry-test \
  --template-file infra/main.bicep \
  --parameters infra/environments/test.parameters.json

# Prod
az account set --subscription "Prod Subscription"
az deployment group create \
  --resource-group rg-foundry-prod \
  --template-file infra/main.bicep \
  --parameters infra/environments/prod.parameters.json
```

## RBAC Per Subscription

Your pipeline identity needs permissions in **each** subscription:

```bash
# For each subscription:
az role assignment create \
  --assignee $APP_ID \
  --role "Azure AI User" \
  --scope /subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.CognitiveServices/accounts/$ACCOUNT
```

!!! tip "Least privilege"
    Grant `Azure AI User` (not Owner or Contributor) to the pipeline
    identity. It only needs to create agents, not manage infrastructure.
    Use a separate identity with `Contributor` role for Bicep deployments.
