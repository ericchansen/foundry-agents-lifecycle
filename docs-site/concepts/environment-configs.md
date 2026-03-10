# Per-Environment Configs

Same code, different settings — how environments work.

---

## The Config Pattern

Each environment has its own JSON config file:

```
config/
├── agent-config.dev.json    ← Fast iteration, cheap model
├── agent-config.test.json   ← Production model, medium thresholds
└── agent-config.prod.json   ← Full production, strict quality gates
```

## What Changes Between Environments

| Setting | Dev | Test | Prod |
|---------|-----|------|------|
| **Model** | `gpt-4o-mini` | `gpt-4o` | `gpt-4o` |
| **Agent name** | `foundry-demo-agent-dev` | `foundry-demo-agent-test` | `foundry-demo-agent` |
| **System prompt** | `system_prompt.md` | `system_prompt.md` | `system_prompt.prod.md` |
| **Eval: groundedness** | 3.0 | 3.5 | 4.0 |
| **Eval: relevance** | 3.0 | 3.5 | 4.0 |
| **Eval: coherence** | 3.0 | 3.5 | 4.0 |

## What Stays the Same

- **Agent code** — `agent_definition.py` and all tool code
- **Deployment script** — `deploy_agent.py`
- **CI/CD pipeline** — Same pipeline file, different env variable

## Why JSON (Not Environment Variables Alone)?

!!! question "Why not just use env vars for everything?"

    | Approach | Pros | Cons |
    |----------|------|------|
    | **JSON config files** | Version-controlled, reviewable, diffable, testable | One more file to manage |
    | **Env vars only** | Simple, standard | Can't diff, can't test, can't review in PRs |

    We use **both**: JSON for non-secret config, env vars for secrets.

    ```
    JSON config files (committed to git):
    ├── Model selection
    ├── Agent name
    ├── Tool configuration
    └── Eval thresholds

    Environment variables (NOT in git):
    ├── AZURE_AI_PROJECT_ENDPOINT
    ├── AZURE_CLIENT_ID
    └── Any API keys or connection strings
    ```

## Adding a New Environment

To add a `staging` environment:

1. **Create the config file:**

    ```bash
    cp config/agent-config.test.json config/agent-config.staging.json
    ```

2. **Edit the new config** — adjust model, name, thresholds

3. **Add environment to CI/CD pipeline:**

    === "GitHub Actions"

        Add a new job in `.github/workflows/cd.yml`:
        ```yaml
        deploy-staging:
          needs: deploy-test
          environment: staging
          # ... same steps, different env
        ```

    === "Azure DevOps"

        Add a new stage in `.azdo/pipelines/cd-pipeline.yml`:
        ```yaml
        - stage: deploy_staging
          dependsOn: deploy_test
          variables:
            AGENT_ENVIRONMENT: staging
        ```

4. **Create infrastructure** (if using separate subscriptions):

    ```bash
    cp infra/environments/test.parameters.json infra/environments/staging.parameters.json
    ```
