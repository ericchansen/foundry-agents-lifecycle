# Foundry Agents Lifecycle

## The complete guide to CI/CD for Microsoft Foundry AI agents

---

!!! tip "What is this?"
    This is an **educational demo repository** that teaches you how to build, deploy,
    evaluate, and promote AI agents across environments using code-first practices.

    Every file is heavily commented. Every decision is explained. Start here, then
    explore the sections that interest you most.

## The Key Mental Model

```
┌─────────────────────────────────────────────────────────┐
│                    YOUR GIT REPO                        │
│                    (Source of Truth)                     │
│                                                         │
│   config/agent-config.dev.json    ← What to deploy      │
│   config/agent-config.prod.json   ← (per environment)   │
│   src/agent/prompts/              ← Agent instructions   │
│   src/agent/tools/                ← Agent capabilities   │
│   infra/main.bicep                ← Infrastructure       │
└──────────────┬──────────────────────────────────────────┘
               │
               │  CI/CD Pipeline
               │  (GitHub Actions or Azure DevOps)
               │
     ┌─────────▼─────────┐
     │  For each env:     │
     │  1. Read config    │
     │  2. Auth to Azure  │
     │  3. Call SDK        │  ← azure-ai-projects Python SDK
     │  4. Create agent   │
     │  5. Run eval       │
     │  6. Gate on score  │
     └───────────────────┘
```

!!! warning "There is no artifact to promote"
    Unlike containers or binaries, Foundry agents can't be exported and imported.
    **CI/CD = recreate the agent from code** in each environment using the SDK.

    This is by design. There is no export/import mechanism — your code and config
    **are** the deployment artifact. The SDK recreates the agent fresh each time.

## Before You Start

Make sure you have these ready:

| Prerequisite | Check | Install |
|---|---|---|
| Python 3.10+ | `python --version` | [python.org](https://python.org) |
| Azure CLI | `az version` | [Install Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) |
| Azure subscription | `az account show` | [Free trial](https://azure.microsoft.com/free) |
| Git | `git --version` | [git-scm.com](https://git-scm.com) |

All set? → **[Quick Start](getting-started/quick-start.md)** (10 minutes)

## Quick Navigation

<div class="grid cards" markdown>

-   :material-rocket-launch:{ .lg .middle } **Getting Started**

    ---

    Set up your environment and deploy your first agent in minutes.

    [:octicons-arrow-right-24: Quick Start](getting-started/quick-start.md)

-   :material-lightbulb:{ .lg .middle } **Core Concepts**

    ---

    Understand the mental model, agent definitions, and environment configs.

    [:octicons-arrow-right-24: Mental Model](concepts/mental-model.md)

-   :material-pipe:{ .lg .middle } **CI/CD Pipelines**

    ---

    GitHub Actions and Azure DevOps pipelines with OIDC auth.

    [:octicons-arrow-right-24: Pipeline Overview](pipelines/overview.md)

-   :material-server:{ .lg .middle } **Infrastructure**

    ---

    Bicep modules for Foundry accounts, models, and Key Vault.

    [:octicons-arrow-right-24: Bicep Modules](infrastructure/bicep.md)

-   :material-puzzle:{ .lg .middle } **Advanced Topics**

    ---

    Logic Apps, portal migration, and multi-subscription patterns.

    [:octicons-arrow-right-24: Advanced](advanced/logic-apps.md)

-   :material-frequently-asked-questions:{ .lg .middle } **FAQ**

    ---

    Common questions about Foundry agent CI/CD.

    [:octicons-arrow-right-24: FAQ](faq.md)

</div>
