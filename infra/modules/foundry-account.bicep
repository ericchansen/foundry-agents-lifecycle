// =============================================================================
// foundry-account.bicep — Microsoft Foundry Resource + Project
// =============================================================================
//
// WHAT THIS CREATES:
//   1. Foundry resource (CognitiveServices/AIServices with project management)
//   2. Foundry project (child resource of the Foundry resource)
//
// WHY THIS PATTERN:
//   The modern Foundry pattern uses a single CognitiveServices account with
//   kind 'AIServices' and allowProjectManagement=true. Projects are created
//   as child resources. No ML hub/workspace needed.
//
//   Foundry Resource → Project → Agent → uses models deployed on the resource
//
//   This gives us the .services.ai.azure.com endpoint that the
//   azure-ai-projects SDK requires.
//
// =============================================================================

@description('Base name for resources')
param name string

@description('Azure region')
param location string

@description('Name for the Foundry project')
param projectName string

@description('Principal ID to grant data-plane access for agent CRUD (e.g., pipeline SP)')
param deployerPrincipalId string = ''

// ---------------------------------------------------------------------------
// Foundry Resource — hosts models AND manages projects
// ---------------------------------------------------------------------------
// kind: 'AIServices' with allowProjectManagement: true is the modern
// Foundry pattern. This single resource handles everything:
//   - Model deployments (gpt-4o-mini, etc.)
//   - Project management (agents, evals, tools)
//   - Entra ID auth (managed identity, no API keys)
//
// API version 2025-04-01-preview is required for allowProjectManagement.
// ---------------------------------------------------------------------------
resource foundryResource 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: name
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    customSubDomainName: name
    allowProjectManagement: true
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

// ---------------------------------------------------------------------------
// Foundry Project — where agents live
// ---------------------------------------------------------------------------
// Projects are child resources of the Foundry resource.
// Each environment gets its own project for isolation.
// The SDK connects to the project endpoint to manage agents.
// ---------------------------------------------------------------------------
resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: foundryResource
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

// ---------------------------------------------------------------------------
// RBAC — Grant deployer identity data-plane access for agent CRUD
// ---------------------------------------------------------------------------
// 'Cognitive Services User' (2aaa9365-...) includes the wildcard
// Microsoft.CognitiveServices/* data action, which covers the newer
// AIServices/agents/* namespace that agent create/delete/update requires.
// 'Azure AI Developer' does NOT cover this namespace (as of March 2026).
// ---------------------------------------------------------------------------
resource cogServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(foundryResource.id, deployerPrincipalId, 'a97b65f3-24c7-4388-baec-2e87135dc908')
  scope: foundryResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: deployerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output foundryResourceName string = foundryResource.name
output aiServicesName string = foundryResource.name
output foundryEndpoint string = foundryResource.properties.endpoints['AI Foundry API']
output projectName string = foundryProject.name
// Full project endpoint for the SDK (AIProjectClient needs this, not just the AI Services endpoint)
output projectEndpoint string = '${foundryResource.properties.endpoints['AI Foundry API']}api/projects/${foundryProject.name}'
