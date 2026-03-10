// =============================================================================
// model-deployments.bicep — Deploy AI Models
// =============================================================================
//
// WHAT THIS CREATES:
//   Model deployments (e.g., GPT-4o, GPT-4o-mini) in the AI Services account.
//
// WHY THIS MATTERS FOR CI/CD:
//   Your agent needs a model to run. The model deployment must exist BEFORE
//   you create the agent. This Bicep module ensures models are provisioned
//   as part of the infrastructure, not manually in the portal.
//
// =============================================================================

@description('Name of the AI Services account (CognitiveServices/OpenAI)')
param aiServicesName string

@description('Array of model deployments to create')
param deployments array

resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesName
}

// Create each model deployment sequentially — CognitiveServices doesn't allow
// parallel operations on the same account (RequestConflict error)
@batchSize(1)
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [
  for deploy in deployments: {
    parent: aiServices
    name: deploy.name
    sku: {
      name: deploy.sku
      capacity: deploy.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: deploy.model
        version: deploy.version
      }
    }
  }
]
