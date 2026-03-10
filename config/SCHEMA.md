# Agent Configuration Schema

Reference for `config/agent-config.{env}.json`. Each environment (dev, test, prod) has its own config file that controls agent behavior, model selection, and evaluation criteria.

This schema is consumed by `agent_definition.py`, which converts it to SDK v2 `PromptAgentDefinition` format for the `azure-ai-projects` SDK.

---

## Top-Level Structure

```json
{
    "agent": { ... },
    "evaluation": { ... }
}
```

| Section | Purpose |
|---------|---------|
| `agent` | Defines the agent identity, model, tools, and system prompt |
| `evaluation` | Controls quality evaluation runs and pass/fail thresholds |

---

## `agent` Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | Yes | Unique agent name registered in Azure AI Foundry. Convention: `foundry-demo-agent-{env}`. Changing this creates a **new** agent instead of updating the existing one. |
| `model` | `string` | Yes | Model deployment name to use (e.g., `gpt-4o-mini`, `gpt-4o`). **Must match a deployment** in `infra/environments/{env}.parameters.json` — see [Model ↔ Infrastructure Relationship](#model--infrastructure-relationship). |
| `instructions_file` | `string` | Yes | Relative path (from repo root) to the system prompt markdown file. The agent reads this file at deployment time. |
| `tools` | `array` | Yes | List of tool objects the agent can invoke. See [Tool Types](#tool-types). |
| `metadata` | `object` | Yes | Key-value pairs attached to the agent for tracking. |

### `agent.metadata`

| Field | Type | Description |
|-------|------|-------------|
| `environment` | `string` | Environment name (`dev`, `test`, `prod`). Used for filtering and dashboards. |
| `deployed_by` | `string` | Deployer identifier. Set to `ci-cd-pipeline` for automated deployments; overridden locally during manual runs. |
| `version` | `string` | Semantic version or git SHA. The CI/CD pipeline replaces `will-be-set-by-pipeline` at deploy time. Do not hardcode a version here. |

---

## Tool Types

Each entry in `agent.tools` must have a `type` field. Three tool types are supported:

### `code_interpreter` (built-in)

```json
{ "type": "code_interpreter" }
```

A sandbox Python environment provided by Azure AI Foundry. The agent can write and execute Python code for data analysis, chart generation, file processing, and complex calculations. No additional configuration required.

### `function` (custom)

```json
{ "type": "function", "function_name": "calculator" }
```

A custom Python function you define. The `function_name` must correspond to a tool module in `src/agent/tools/`. For example, `"calculator"` maps to `src/agent/tools/calculator.py`, which exports:
- `get_calculator_tool_definition()` — returns the OpenAI-compatible function schema
- `execute_calculator(operation, a, b)` — runs the actual logic

To add a new function tool:
1. Create `src/agent/tools/{name}.py` with the definition and execution functions
2. Add `{ "type": "function", "function_name": "{name}" }` to the tools array
3. Register the tool in `src/agent/tools/__init__.py`

### `bing_grounding` (web search)

```json
{ "type": "bing_grounding" }
```

Enables the agent to search the web via Bing. Requires the `BING_CONNECTION_ID` environment variable to be set with a valid Azure AI Foundry Bing connection resource ID. Without this variable, deployment will fail.

---

## `evaluation` Section

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | `boolean` | Yes | Whether to run AI-assisted evaluation after deployment. Set to `false` to skip (not recommended for prod). |
| `dataset` | `string` | Yes | Relative path to a `.jsonl` file of test cases. Each line is a JSON object with `question`, `expected_answer`, and `category` fields. |
| `thresholds` | `object` | Yes | Minimum scores (1–5 scale) that the agent must meet. Evaluation fails if any metric falls below its threshold. |

### `evaluation.thresholds`

All thresholds use a **1 to 5 scale** where 1 is worst and 5 is best. Scores are computed by an AI evaluator (GPT-based) against your eval dataset.

| Metric | What It Measures | Fails When |
|--------|-----------------|------------|
| `groundedness` | Are the agent's claims supported by the context/tools it used? Detects hallucination. | Agent invents facts not derived from tool output or provided context. |
| `relevance` | Does the response actually answer the user's question? | Agent gives a correct but off-topic response, or ignores part of the question. |
| `coherence` | Is the response well-structured, clear, and logically consistent? | Agent produces contradictory, rambling, or hard-to-follow output. |

---

## Model ↔ Infrastructure Relationship

The `agent.model` value is **not** a raw OpenAI model name — it's the **deployment name** from your Azure AI Foundry account. This deployment is provisioned by Bicep via the parameter files in `infra/environments/`.

**The flow:**

```
infra/environments/{env}.parameters.json    →    Bicep deploys model    →    agent-config.{env}.json references it
         (defines deployment)                    (creates endpoint)              (agent uses endpoint)
```

**If you change `agent.model`**, you must ensure:
1. The model deployment exists in `infra/environments/{env}.parameters.json` under `modelDeployments`
2. The `name` field in the parameters file matches exactly what you put in `agent.model`
3. You run the infrastructure pipeline (or `azd provision`) before deploying the agent

**Example:** Dev uses `gpt-4o-mini` (cheaper, faster iteration). The corresponding infrastructure:

```json
// infra/environments/dev.parameters.json
"modelDeployments": [{
    "name": "gpt-4o-mini",        // ← This must match agent.model
    "model": "gpt-4o-mini",
    "version": "2024-07-18",
    "sku": "GlobalStandard",
    "capacity": 10                // TPM in thousands
}]
```

---

## Environment Recommendations

| Setting | Dev | Test | Prod |
|---------|-----|------|------|
| `agent.model` | `gpt-4o-mini` — fast and cheap for iteration | `gpt-4o` — match prod model | `gpt-4o` — best quality |
| `instructions_file` | `system_prompt.md` | `system_prompt.md` | `system_prompt.prod.md` (tighter guardrails) |
| `evaluation.enabled` | `true` | `true` | `true` |
| `evaluation.thresholds` | `3.0` — permissive, catch regressions | `3.5` — stricter gate | `4.0` — high bar for production |
| Infra model capacity | Low (10 TPM) | Medium | High (50 TPM) |

**Why different thresholds?** Dev uses relaxed thresholds so you can iterate quickly without evaluation blocking every change. Prod thresholds are strict because low-quality responses reach real users. Test sits in between as a pre-prod gate.

---

## Quick Reference: Adding a New Environment

1. Copy an existing config: `cp config/agent-config.dev.json config/agent-config.staging.json`
2. Update `agent.name` to include the environment suffix
3. Update `agent.metadata.environment`
4. Create `infra/environments/staging.parameters.json` with the model deployments you need
5. Adjust evaluation thresholds to match your quality bar
6. Add the environment to your CI/CD pipeline
