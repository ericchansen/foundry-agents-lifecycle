# Frequently Asked Questions

---

## General

### Can I export an agent from the Foundry portal and import it elsewhere?

**No.** Foundry agents have no export/import mechanism. This is the entire
reason this repo exists — you define agents in code and create them via
the SDK in each environment.

### Is there a Foundry "artifact" I can promote between environments?

**No.** Foundry agents have no export/import or artifact promotion mechanism.
CI/CD means recreating the agent from your code and config in each environment via the SDK.

### What about Foundry "Solutions"?

Foundry Solutions are **not** a CI/CD mechanism. They're for sharing
pre-built templates. Don't confuse them with deployment artifacts.

---

## SDK & API

### Which SDK do I use?

`azure-ai-projects` (Python, version 2.0.0b3+). Install all dependencies with:
```bash
pip install -e ".[dev]"
```

### What API does the SDK call?

The Azure AI Agents API (based on the OpenAI Assistants API).
The key method is `client.agents.create()` (SDK v2). Model, instructions,
and tools are wrapped in a `PromptAgentDefinition` object.

### Does the SDK support other languages?

Yes — .NET, Java, and JavaScript SDKs exist. This repo uses Python
because it's the most mature for AI workloads.

---

## Authentication

### How does authentication work in CI/CD?

- **GitHub Actions:** OIDC federation (no secrets stored)
- **Azure DevOps:** Service Connections (workload identity federation)
- **Local dev:** `az login` (Azure CLI)

All use `DefaultAzureCredential()` — same code everywhere.

### What permissions does the pipeline need?

`Azure AI User` role on the Foundry account/project. This grants
permission to create, list, and delete agents.

---

## Environments

### Do I need separate Azure subscriptions per environment?

**Recommended but not required.** You can use:

- **Separate subscriptions** — maximum isolation (recommended for enterprise)
- **Separate resource groups** — lighter isolation, same subscription
- **Same project, different agent names** — minimal isolation (dev/testing only)

### How do I add a new environment?

1. Copy an existing config: `cp config/agent-config.test.json config/agent-config.staging.json`
2. Add a stage to your pipeline
3. Create infrastructure (if using separate subscriptions)
4. Create Bicep parameters: `cp infra/environments/test.parameters.json infra/environments/staging.parameters.json`

---

## Evaluation

### Are the evaluation scores real?

The included `run_evaluation.py` has **simulated scores** for demo
purposes. For production, integrate with the real Foundry evaluation API.

### What's a good threshold?

| Environment | Suggested | Reasoning |
|-------------|-----------|-----------|
| Dev | 3.0/5.0 | Low bar for experimentation |
| Test | 3.5/5.0 | Moderate quality for integration testing |
| Prod | 4.0/5.0 | High bar for production |

### How many test questions should I have?

At least **50-100** representative questions covering:
- Happy path scenarios
- Edge cases
- Tool usage scenarios
- Adversarial inputs

---

## Azure DevOps

### Can I use this with Azure DevOps instead of GitHub?

**Yes.** The `.azdo/pipelines/` directory has equivalent ADO pipelines.
Same logic, different YAML syntax.

### How do I set up an ADO organization?

1. Go to [dev.azure.com](https://dev.azure.com)
2. Sign in with your Microsoft account
3. Create a new organization
4. Create a project
5. Push this repo or import from GitHub

Free for up to 5 users with unlimited private repos.

---

## Logic Apps

### If my agent uses Logic Apps as tools, what do I do?

Deploy Logic Apps **before** the agent in your pipeline:

```
Infrastructure → Logic Apps → Agent → Evaluation
```

See [Logic Apps CI/CD](advanced/logic-apps.md) for full guidance.
