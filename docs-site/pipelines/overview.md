# CI/CD Pipeline Overview

How changes flow from code to production.

---

## The Full Flow

```mermaid
graph TD
    A[Developer Pushes Code] --> B[Pull Request]
    B --> C[CI Pipeline]
    C --> D{Tests Pass?}
    D -->|No| E[❌ Fix & Retry]
    D -->|Yes| F[Merge to Main]
    F --> G[CD Pipeline]
    G --> H[Deploy to DEV]
    H --> I[Evaluate DEV]
    I --> J{Quality OK?}
    J -->|No| K[❌ Fix & Retry]
    J -->|Yes| L[⏸️ Approve for TEST]
    L --> M[Deploy to TEST]
    M --> N[Evaluate TEST]
    N --> O{Quality OK?}
    O -->|No| P[❌ Fix & Retry]
    O -->|Yes| Q[⏸️ Approve for PROD]
    Q --> R[Deploy to PROD]
    R --> S[Evaluate PROD]
    S --> T{Quality OK?}
    T -->|Yes| U[✅ Done!]
    T -->|No| V[🔄 Rollback]
    style U fill:#9f6,stroke:#333
```

## CI vs. CD

| Aspect | CI (Continuous Integration) | CD (Continuous Deployment) |
|--------|---------------------------|---------------------------|
| **When** | On every Pull Request | On merge to `main` |
| **Purpose** | Validate changes are safe | Deploy to environments |
| **Speed** | Fast (seconds to minutes) | Slower (deploys + evals) |
| **Calls Azure?** | No (dry-run only) | Yes (creates real agents) |
| **Blocks** | PR merge | Environment promotion |

## What CI Checks

1. **Lint** — Code style and basic bugs (`ruff check`)
2. **Unit tests** — Config validation, tool testing (`pytest`)
3. **Dry-run deploy** — Config loads correctly, SDK params are valid

## What CD Does

For each environment (dev → test → prod):

1. **Authenticate** — OIDC (GitHub) or Service Connection (ADO)
2. **Deploy agent** — Create via SDK
3. **Evaluate** — Run test questions, score responses
4. **Gate** — Block if quality scores are below thresholds
5. **Wait for approval** — Human review before next environment

## Choosing Your Platform

This repo includes pipelines for both:

| Platform | Files | Best For |
|----------|-------|----------|
| [GitHub Actions](github-actions.md) | `.github/workflows/` | GitHub-native repos, OIDC |
| [Azure DevOps](azure-devops.md) | `.azdo/pipelines/` | Enterprise, ADO-native shops |

The logic is **identical** — only the YAML syntax differs.
