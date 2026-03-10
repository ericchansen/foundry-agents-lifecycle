# Prerequisites

Everything you need before getting started.

---

## Required Tools

| Tool | Version | Purpose | Install |
|------|---------|---------|---------|
| **Python** | 3.10+ | Runtime for all scripts | [python.org](https://python.org) |
| **Azure CLI** | Latest | Authentication + infra deployment | `winget install Microsoft.AzureCLI` |
| **Git** | Latest | Version control | [git-scm.com](https://git-scm.com) |

## Optional Tools

| Tool | Purpose | When You Need It |
|------|---------|-----------------|
| **Azure Developer CLI (azd)** | Simplified infra + app deployment | If using `azure.yaml` workflow |
| **Bicep CLI** | Infrastructure as Code | If deploying Bicep directly (bundled with Azure CLI) |
| **VS Code** | Editor with great Python + Bicep support | Recommended editor |

## Azure Resources

You need access to:

1. **Azure AI Foundry project** — Where agents are deployed
2. **Model deployment** — At least one model (e.g., GPT-4o-mini) deployed in your Foundry account
3. **Azure subscription** — For Bicep infrastructure deployment

!!! tip "Don't have a Foundry project yet?"
    Use the Bicep modules in `infra/` to create one:
    ```bash
    az deployment group create \
      --resource-group my-rg \
      --template-file infra/main.bicep \
      --parameters infra/environments/dev.parameters.json
    ```

## For CI/CD Pipelines

=== "GitHub Actions"

    - GitHub repository (public or private)
    - Azure App Registration with OIDC federation
    - GitHub Environments configured (dev, test, prod)
    - See [OIDC Setup Guide](../pipelines/oidc-setup.md)

=== "Azure DevOps"

    - Azure DevOps organization and project
    - Service Connections (one per environment/subscription)
    - ADO Environments with approval gates
    - See [Azure DevOps Pipelines](../pipelines/azure-devops.md)

## Authentication Hierarchy

The `DefaultAzureCredential` tries these in order:

```
1. Environment variables      ← CI/CD pipelines set these
2. Workload Identity          ← OIDC federation (GitHub/ADO)
3. Managed Identity           ← Azure-hosted runners
4. Azure CLI                  ← Local development (az login)
5. Azure PowerShell           ← If you prefer PowerShell
6. Interactive browser        ← Last resort
```

!!! info "Same code everywhere"
    You never change the auth code. `DefaultAzureCredential()` works
    in local dev, GitHub Actions, Azure DevOps, and Azure VMs.
