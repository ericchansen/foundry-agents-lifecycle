# Architecture Decisions

Why we made the choices we made.

---

## Decision 1: Code-First, Not Portal-First

**Decision:** Define agents entirely in code, not the Foundry portal.

**Why:** The portal has no export/import, no version control, no PR reviews,
no rollback capability. The SDK is the only path to automation.

**Trade-off:** Developers must learn the SDK. Portal is better for exploration.

**Recommendation:** Use portal to prototype. Once validated, codify it.

---

## Decision 2: Delete + Recreate (Not Update)

**Decision:** Each deployment deletes the old agent and creates a fresh one.

**Why:** Guarantees the deployed agent matches code exactly. No drift.

**Trade-off:** Agent ID changes. Use names, not IDs, for all integrations.

---

## Decision 3: JSON Config Files Per Environment

**Decision:** Use JSON files, not just environment variables.

**Why:** Version-controlled, diffable, testable, reviewable in PRs.

**Rule:** Secrets go in env vars. Everything else goes in JSON config.

---

## Decision 4: OIDC Federation

**Decision:** Use OIDC instead of client secrets for CI/CD auth.

**Why:** No secrets to store, rotate, or leak.

[Full OIDC setup guide →](pipelines/oidc-setup.md)

---

## Decision 5: Evaluation as Quality Gate

**Decision:** Run automated evaluation after deployment, before promotion.

**Why:** AI agents regress silently. Evaluation catches quality drops.

[Full evaluation guide →](concepts/evaluation.md)

---

## Decision 6: Bicep (Not Terraform)

**Decision:** Use Bicep for Azure infrastructure.

**Why:** Azure-native, no state file, tightest ARM integration.

**For Terraform shops:** Same concepts apply. Replace `.bicep` with `.tf` files.
The agent deployment script is IaC-tool-agnostic.

---

## Decision 7: Both GitHub Actions and Azure DevOps

**Decision:** Provide pipeline definitions for both platforms.

**Why:** Different teams use different tools. The logic is identical —
only the YAML syntax and auth mechanism differ.
