# GitHub Actions Pipelines

CI/CD using GitHub Actions with OIDC authentication.

---

## Files

| File | Purpose | Trigger |
|------|---------|---------|
| `.github/workflows/ci.yml` | Validate PRs | Pull request to `main` |
| `.github/workflows/cd.yml` | Deploy to environments | Push to `main` |

## CI Pipeline (`.github/workflows/ci.yml`)

```yaml
name: CI — Validate Agent Config
on:
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      # 1. Checkout code
      - uses: actions/checkout@v4

      # 2. Set up Python
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # 3. Install dependencies
      - run: pip install -e ".[dev]"

      # 4. Lint
      - run: ruff check src/

      # 5. Unit tests
      - run: pytest src/tests/unit/ -v

      # 6. Dry-run deployment (validates config without calling Azure)
      - run: python src/scripts/deploy_agent.py --env dev --dry-run
      - run: python src/scripts/deploy_agent.py --env prod --dry-run
```

!!! info "No Azure credentials needed"
    CI uses `--dry-run` which loads config and validates SDK parameters
    without making any API calls. No secrets needed for PR validation.

## CD Pipeline (`.github/workflows/cd.yml`)

### Key Concepts

=== "OIDC Authentication"

    ```yaml
    permissions:
      id-token: write    # ← Required for OIDC
      contents: read

    steps:
      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
    ```

    No secrets stored in GitHub — Azure trusts GitHub's identity token.

=== "Environment Gates"

    ```yaml
    jobs:
      deploy-dev:
        environment: dev     # ← No approval needed
      deploy-test:
        environment: test    # ← Requires 1 approver
        needs: deploy-dev
      deploy-prod:
        environment: prod    # ← Requires 2+ approvers
        needs: deploy-test
    ```

    Configure approvers in **Settings → Environments**.

=== "Infrastructure as Code"

    Each environment deploys infrastructure first, then the agent:

    ```yaml
    steps:
      - uses: azure/login@v2
        with: { ... }

      # 1. Deploy IaC (creates resource group + all Azure resources)
      - name: Deploy Infrastructure
        run: |
          az deployment sub create \
            --location eastus2 \
            --template-file infra/deploy-infra.bicep \
            --parameters environment=dev pipelineSource=github \
            --parameters infra/environments/dev.parameters.json

      # 2. Deploy the agent into that infrastructure
      - name: Deploy Agent
        run: python src/scripts/deploy_agent.py --env dev

      # 3. Evaluate quality
      - name: Evaluate Agent
        run: python src/scripts/run_evaluation.py --env dev
    ```

    The `pipelineSource=github` parameter ensures GitHub Actions creates resource
    groups named `rg-foundry-github-{env}`, while Azure DevOps creates
    `rg-foundry-ado-{env}` — no conflicts between pipeline systems.

=== "Deployment Steps"

    Each environment runs the same three steps:

    1. **Deploy Infrastructure** — subscription-level Bicep creates the RG + resources
    2. **Deploy Agent** — SDK creates/updates the agent in Foundry
    3. **Evaluate Agent** — quality gate with pass/fail thresholds

    The project endpoint is captured dynamically from Bicep outputs — no need
    to hardcode `AZURE_AI_PROJECT_ENDPOINT` per environment.

## Setting Up GitHub Environments

1. Go to **Settings → Environments**
2. Create: `dev`, `test`, `prod`
3. For `test` and `prod`:
   - Add **required reviewers**
   - Optionally add **wait timer** (e.g., 5 minutes for prod)
4. Add environment secrets:
   - `AZURE_CLIENT_ID`
   - `AZURE_TENANT_ID`
   - `AZURE_SUBSCRIPTION_ID`

!!! tip "No manual endpoint configuration needed"
    The CD pipeline dynamically captures `AZURE_AI_PROJECT_ENDPOINT` from the
    Bicep deployment outputs. You don't need to manually set it per environment.

!!! tip "Different subscriptions per environment"
    Each GitHub Environment can have different secrets. Use this to point
    dev/test/prod to different Azure subscriptions and Foundry projects.

## Dual-Pipeline Isolation

This repo supports deploying from **both** GitHub Actions and Azure DevOps simultaneously.
Each pipeline system gets its own isolated resource groups:

| Pipeline | Dev RG | Prod RG |
|----------|--------|---------|
| GitHub Actions | `rg-foundry-github-dev` | `rg-foundry-github-prod` |
| Azure DevOps | `rg-foundry-ado-dev` | `rg-foundry-ado-prod` |

The `infra/deploy-infra.bicep` file (subscription-scoped) creates these resource
groups and deploys all infrastructure into them. The `pipelineSource` parameter
is what differentiates the two pipeline systems.

!!! warning "Subscription-level permissions required"
    The pipeline identity needs **Contributor** role at the **subscription** level
    (not just resource group level) to create resource groups via `az deployment sub create`.
