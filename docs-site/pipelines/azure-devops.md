# Azure DevOps Pipelines

CI/CD using Azure DevOps with Service Connections and YAML Templates.

---

!!! info "For enterprise ADO shops"
    This is the equivalent of the GitHub Actions pipelines, translated
    for teams that use Azure DevOps. Same logic, different syntax.

## Files

| File | Purpose | Trigger |
|------|---------|---------|
| `.azdo/pipelines/ci-pipeline.yml` | Validate PRs | PR to `main` |
| `.azdo/pipelines/cd-pipeline.yml` | Deploy to environments | Merge to `main` |
| `.azdo/pipelines/templates/deploy-stage.yml` | Reusable deploy stage | Referenced by CD |

## ADO Features Used

| Feature | How We Use It |
|---------|--------------|
| **YAML Templates** | DRY deploy logic — define once, reuse per environment |
| **Environments** | Approval gates for test and prod |
| **Service Connections** | Per-environment Azure authentication |
| **PublishTestResults** | Test results appear in the ADO "Tests" tab |
| **UsePythonVersion** | Consistent Python version across agents |
| **Multi-stage pipelines** | DEV → TEST → PROD with gates |

## Key Differences from GitHub Actions

| Concept | GitHub Actions | Azure DevOps |
|---------|---------------|-------------|
| **Auth** | OIDC federation | Service Connections |
| **Variables** | `${{ secrets.X }}` | `$(variableName)` |
| **Environments** | GitHub Environments | ADO Environments |
| **Agents** | `runs-on: ubuntu-latest` | `pool: vmImage: 'ubuntu-latest'` |
| **Stages** | Jobs with `needs` | Explicit `stages:` block |
| **Approvals** | Environment protection rules | Environment checks |
| **DRY patterns** | Reusable workflows | YAML Templates |

## CI Pipeline

Runs on every PR and push — validates code quality without deploying:

```yaml title=".azdo/pipelines/ci-pipeline.yml"
pool:
  vmImage: "ubuntu-latest"

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: "3.12"

  - script: pip install -e ".[dev]"
    displayName: "Install dependencies"

  - script: ruff check src/
    displayName: "Lint"

  - script: pytest src/tests/unit/ -v --junitxml=test-results.xml
    displayName: "Unit tests"

  - task: PublishTestResults@2
    condition: always()
    inputs:
      testResultsFormat: "JUnit"
      testResultsFiles: "test-results.xml"

  - script: python src/scripts/deploy_agent.py --env dev --dry-run
    displayName: "Dry-run (dev)"
```

## CD Pipeline with YAML Templates

The CD pipeline uses a **reusable YAML template** to avoid duplicating the
same deploy steps for every environment. This is an ADO best practice:

```yaml title=".azdo/pipelines/cd-pipeline.yml"
stages:
  # Each stage references the same template with different parameters
  - template: templates/deploy-stage.yml
    parameters:
      environment: dev
      serviceConnection: azure-dev

  - template: templates/deploy-stage.yml
    parameters:
      environment: test
      serviceConnection: azure-test
      dependsOn: Deploy_dev

  - template: templates/deploy-stage.yml
    parameters:
      environment: prod
      serviceConnection: azure-prod
      dependsOn: Deploy_test
```

The template (`templates/deploy-stage.yml`) handles:

1. **Python setup** → `UsePythonVersion@0`
2. **Install deps** → `pip install -e .`
3. **Deploy IaC** → `az deployment sub create` via `AzureCLI@2`
4. **Deploy agent** → `deploy_agent.py` via `AzureCLI@2`
5. **Evaluate** → `run_evaluation.py` with 6 quality gate evaluators

!!! tip "Why YAML Templates?"
    Without templates, you'd copy-paste ~50 lines per stage × 3 environments = 150 lines
    of duplicated YAML. With templates, changes to the deploy logic happen in ONE place.

## Dual-Pipeline Isolation

This repo deploys from **both** GitHub Actions and Azure DevOps without conflicts:

| Pipeline | Dev RG | Test RG | Prod RG |
|----------|--------|---------|---------|
| GitHub Actions | `rg-foundry-github-dev` | `rg-foundry-github-test` | `rg-foundry-github-prod` |
| Azure DevOps | `rg-foundry-ado-dev` | `rg-foundry-ado-test` | `rg-foundry-ado-prod` |

Each pipeline creates its own resource group via `infra/deploy-infra.bicep`
(a subscription-scoped Bicep file) using the `pipelineSource` parameter.

## Setup Checklist

### 1. Service Connections

Service Connections authenticate your pipeline to Azure:

1. Go to **Project Settings → Service Connections**
2. Click **New service connection → Azure Resource Manager**
3. Choose **Workload Identity Federation** (recommended — zero secrets)
4. Create one per environment:

| Connection Name | Target Subscription | Used By |
|----------------|-------------------|---------|
| `azure-dev` | Dev subscription | DEV stage |
| `azure-test` | Test subscription | TEST stage |
| `azure-prod` | Prod subscription | PROD stage |

!!! warning "Subscription-level permissions required"
    The service principal needs **Contributor** at the **subscription** level
    (not just resource group) to create resource groups via `az deployment sub create`.

### 2. ADO Environments

Environments provide approval gates — they're auto-created on first pipeline run, then you configure checks:

1. Run the CD pipeline once (environments auto-create)
2. Go to **Pipelines → Environments**
3. For `test` and `prod`:
    - Click **⋮ → Approvals and checks**
    - Add **Approvals** → specify approvers
    - Optionally add **Business hours** or **Exclusive lock** checks

### 3. Import the Pipeline

1. Go to **Pipelines → New Pipeline**
2. Choose **Azure Repos Git** (or GitHub if you imported)
3. Select **Existing Azure Pipelines YAML file**
4. Pick `.azdo/pipelines/ci-pipeline.yml` → Save
5. Repeat for `.azdo/pipelines/cd-pipeline.yml`

### 4. Agent Pool

The pipelines use `vmImage: "ubuntu-latest"` (Microsoft-hosted agents) by default.

!!! note "Self-hosted agents"
    To use self-hosted agents instead, change the pool configuration:

    ```yaml
    pool:
      name: "Default"   # or your custom pool name
    ```

    Self-hosted agents must have Python 3.12+ and Azure CLI installed.
    New ADO organizations may need to [request hosted parallelism](https://aka.ms/azpipelines-parallelism-request).

## Setting Up Your ADO Organization

!!! tip "Creating a personal Azure DevOps org"
    If you don't have an ADO org yet:

    1. Go to [dev.azure.com](https://dev.azure.com)
    2. Sign in with your Microsoft account
    3. Click **New organization**
    4. Create a project (e.g., `foundry-agents-lifecycle`)
    5. Push the repo:

    ```bash
    git remote add azdo https://dev.azure.com/your-org/your-project/_git/foundry-agents-lifecycle
    git push azdo main
    ```

    Free for up to 5 users with unlimited private repos.
