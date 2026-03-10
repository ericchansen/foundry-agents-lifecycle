// =============================================================================
// keyvault.bicep — Azure Key Vault for Secrets Management
// =============================================================================
//
// WHY KEY VAULT:
//   Never put secrets in code, config files, or environment variables.
//   Key Vault stores them securely. Your agent and pipeline access secrets
//   via managed identity (no passwords needed!).
//
// =============================================================================

@description('Name for the Key Vault')
param name string

@description('Azure region')
param location string

@description('Principal ID to grant secrets access')
param deployerPrincipalId string

resource keyVault 'Microsoft.KeyVault/vaults@2025-05-01' = {
  name: name
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// Grant the deployer identity access to secrets
resource secretsOfficerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(keyVault.id, deployerPrincipalId, 'Key Vault Secrets Officer')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
    principalId: deployerPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
