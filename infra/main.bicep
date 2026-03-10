// =============================================================================
// main.bicep — Orchestrator for all infrastructure
// =============================================================================
//
// WHAT THIS DEPLOYS:
//   1. AI Foundry Resource + Project (AIServices with allowProjectManagement)
//   2. Model deployments (GPT-4o-mini on the AI Services account)
//   3. Key Vault (for secrets management)
//
// HOW TO USE:
//   # Deploy to dev
//   az deployment group create \
//     --resource-group rg-foundry-demo-dev \
//     --template-file infra/main.bicep \
//     --parameters infra/environments/dev.parameters.json
//
// WHY BICEP:
//   Bicep is Azure's native IaC language. It compiles to ARM templates
//   but is much more readable. Terraform works too — same concepts.
//
// =============================================================================

targetScope = 'resourceGroup'

// ---------------------------------------------------------------------------
// Parameters — these change per environment
// ---------------------------------------------------------------------------
@description('Base name for all resources (e.g., foundry-demo)')
param baseName string

@description('Azure region for deployment')
param location string = resourceGroup().location

@description('Environment name (dev, test, prod)')
@allowed(['dev', 'test', 'prod'])
param environment string

@description('Model deployments to create')
param modelDeployments array = [
  {
    name: 'gpt-4o-mini'
    model: 'gpt-4o-mini'
    version: '2024-07-18'
    sku: 'GlobalStandard'
    capacity: 10
  }
]

@description('Principal ID to grant AI User role (your pipeline identity)')
param deployerPrincipalId string = ''

// Short name for Key Vault (max 24 chars: 3-24 alphanumeric + hyphens)
var kvShortBase = replace(baseName, 'foundry-demo-', 'fd-')

// ---------------------------------------------------------------------------
// Key Vault
// ---------------------------------------------------------------------------
// Store secrets like API keys, connection strings, etc.
// Agents access secrets via managed identity — never hardcoded.
// ---------------------------------------------------------------------------
module keyVault 'modules/keyvault.bicep' = {
  name: 'key-vault'
  params: {
    name: 'kv-${kvShortBase}-${environment}'
    location: location
    deployerPrincipalId: deployerPrincipalId
  }
}

// ---------------------------------------------------------------------------
// Foundry Resource + Project
// ---------------------------------------------------------------------------
// Modern Foundry pattern: a single AIServices resource with project management.
// No ML hub/workspace needed — projects are child resources of the Foundry
// resource. This gives us the .services.ai.azure.com endpoint that the SDK needs.
// ---------------------------------------------------------------------------
module foundryAccount 'modules/foundry-account.bicep' = {
  name: 'foundry-account'
  params: {
    name: '${baseName}-${environment}'
    location: location
    projectName: '${baseName}-project-${environment}'
  }
}

// ---------------------------------------------------------------------------
// Model Deployments
// ---------------------------------------------------------------------------
// Deploy the AI models that agents will use.
// Models deploy into the AI Services account (created by foundry-account).
// Different environments can have different models/capacities.
// Dev: small/cheap models. Prod: full-size models with more capacity.
// ---------------------------------------------------------------------------
module models 'modules/model-deployments.bicep' = {
  name: 'model-deployments'
  params: {
    aiServicesName: foundryAccount.outputs.aiServicesName
    deployments: modelDeployments
  }
}

// ---------------------------------------------------------------------------
// Outputs — used by scripts and pipelines
// ---------------------------------------------------------------------------
output projectEndpoint string = foundryAccount.outputs.projectEndpoint
output keyVaultName string = keyVault.outputs.keyVaultName
output foundryResourceName string = foundryAccount.outputs.foundryResourceName
output aiServicesEndpoint string = foundryAccount.outputs.foundryEndpoint
