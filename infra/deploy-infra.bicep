// =============================================================================
// deploy-infra.bicep — Subscription-Level Infrastructure Orchestrator
// =============================================================================
//
// 🎯 PURPOSE:
//   This file deploys infrastructure at the SUBSCRIPTION level, which means it
//   can create resource groups themselves — not just resources inside them.
//
// 🧠 WHY SUBSCRIPTION-LEVEL?
//   When you have MULTIPLE CI/CD pipeline systems (e.g., GitHub Actions AND
//   Azure DevOps) deploying the same application, each pipeline needs its own
//   isolated set of Azure resources to avoid conflicts. The cleanest way to
//   achieve this is to give each pipeline its own resource group:
//
//     GitHub Actions → rg-foundry-github-dev, rg-foundry-github-prod
//     Azure DevOps   → rg-foundry-ado-dev,    rg-foundry-ado-prod
//
//   A resource-group-scoped deployment (targetScope = 'resourceGroup') can't
//   create the resource group it deploys into — that's a chicken-and-egg
//   problem. Subscription-level deployment solves this by:
//     1. Creating the resource group (if it doesn't exist)
//     2. Deploying all resources INTO that resource group via a module
//
// 📐 ARCHITECTURE:
//   deploy-infra.bicep (subscription scope)
//     └── main.bicep (resource group scope) — called as a module
//           ├── modules/foundry-account.bicep
//           ├── modules/model-deployments.bicep
//           └── modules/keyvault.bicep
//
// 💡 HOW TO USE:
//   # Deploy from GitHub Actions pipeline:
//   az deployment sub create \
//     --location eastus2 \
//     --template-file infra/deploy-infra.bicep \
//     --parameters environment=dev pipelineSource=github \
//     --parameters infra/environments/dev.parameters.json
//
//   # Deploy from Azure DevOps pipeline:
//   az deployment sub create \
//     --location eastus2 \
//     --template-file infra/deploy-infra.bicep \
//     --parameters environment=dev pipelineSource=ado \
//     --parameters infra/environments/dev.parameters.json
//
//   # Both pipelines deploy the SAME app but into DIFFERENT resource groups,
//   # so they never interfere with each other.
//
// =============================================================================

// ---------------------------------------------------------------------------
// Target Scope — this is the key!
// ---------------------------------------------------------------------------
// 'subscription' scope lets us create resource groups and deploy into them.
// Compare to 'resourceGroup' scope (used in main.bicep) which can only create
// resources inside an already-existing resource group.
// ---------------------------------------------------------------------------
targetScope = 'subscription'

// ---------------------------------------------------------------------------
// Parameters
// ---------------------------------------------------------------------------

@description('Environment name (dev, test, prod) — controls resource sizing and naming')
@allowed(['dev', 'test', 'prod'])
param environment string

@description('Which CI/CD pipeline system is deploying — used to isolate resource groups')
@allowed(['github', 'ado'])
param pipelineSource string

@description('Azure region for all resources. Subscription-level deployments require an explicit location.')
param location string = 'eastus2'

@description('Base name prefix for all resources (e.g., foundry-demo)')
param baseName string = 'foundry-demo'

@description('Model deployments to provision (passed through to main.bicep)')
param modelDeployments array = [
  {
    name: 'gpt-4o-mini'
    model: 'gpt-4o-mini'
    version: '2024-07-18'
    sku: 'GlobalStandard'
    capacity: 10
  }
]

@description('Principal ID of the deployer identity (for RBAC assignments)')
param deployerPrincipalId string = ''

// ---------------------------------------------------------------------------
// Resource Group
// ---------------------------------------------------------------------------
// We create a resource group per pipeline source per environment.
// This is the foundation of the dual-pipeline isolation pattern:
//
//   Pipeline Source    Environment    Resource Group
//   ─────────────     ───────────    ──────────────────────────
//   github            dev            rg-foundry-github-dev
//   github            prod           rg-foundry-github-prod
//   ado               dev            rg-foundry-ado-dev
//   ado               prod           rg-foundry-ado-prod
//
// Each resource group is fully independent — its own AI Foundry account,
// its own model deployments, its own Key Vault. No shared state, no
// conflicts, no "who deployed last?" problems.
// ---------------------------------------------------------------------------
resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: 'rg-foundry-${pipelineSource}-${environment}'
  location: location
  tags: {
    environment: environment
    pipelineSource: pipelineSource
    managedBy: 'bicep'
    project: baseName
  }
}

// ---------------------------------------------------------------------------
// Module: Deploy Infrastructure into the Resource Group
// ---------------------------------------------------------------------------
// This calls main.bicep as a module, scoped to the resource group we just
// created above. The 'scope: rg' directive is what makes this work — it tells
// Bicep to deploy the module's resources inside our new resource group.
//
// We append the pipeline source to the baseName so that resources within
// each resource group also have unique names (important for globally-unique
// resources like Key Vault names and AI Foundry account names).
// ---------------------------------------------------------------------------
module infra 'main.bicep' = {
  name: 'infra-${pipelineSource}-${environment}'
  scope: rg
  params: {
    baseName: '${baseName}-${pipelineSource}'
    location: location
    environment: environment
    modelDeployments: modelDeployments
    deployerPrincipalId: deployerPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Outputs
// ---------------------------------------------------------------------------
// These outputs are captured by the pipeline after deployment.
//
// In GitHub Actions:
//   echo "PROJECT_ENDPOINT=$(az deployment sub show ... --query properties.outputs.projectEndpoint.value -o tsv)"
//
// In Azure DevOps:
//   echo "##vso[task.setvariable variable=PROJECT_ENDPOINT]$(az deployment sub show ...)"
//
// The pipeline then passes the endpoint to the agent deploy script,
// eliminating the need to hardcode endpoints in pipeline variables.
// ---------------------------------------------------------------------------
output resourceGroupName string = rg.name
output projectEndpoint string = infra.outputs.projectEndpoint
output keyVaultName string = infra.outputs.keyVaultName
output foundryResourceName string = infra.outputs.foundryResourceName
