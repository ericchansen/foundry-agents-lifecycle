#!/usr/bin/env python3
# =============================================================================
# deploy_agent.py — Create or update a Foundry agent from code
# =============================================================================
#
# 🎯 THIS IS THE MOST IMPORTANT SCRIPT IN THE REPO
#
# EXECUTION FLOW:
#   1. Load config   → Read agent-config.{env}.json + system prompt
#   2. Auth          → DefaultAzureCredential (CLI | Managed Identity | OIDC)
#   3. Connect       → AIProjectClient to Foundry project
#   4. Deploy        → create_version() — creates or updates agent in one call
#   5. Output        → Save agent ID for pipeline consumption
#
# How it's called:
#   # Locally (uses your `az login` credentials)
#   python src/scripts/deploy_agent.py --env dev
#
#   # In CI/CD (uses managed identity or OIDC federation)
#   python src/scripts/deploy_agent.py --env prod
#
# What "deploying an agent" actually means:
#   It's a single API call. The SDK sends a POST/PUT to the Foundry API with:
#   - Model name (which model deployment to use)
#   - Instructions (the system prompt)
#   - Tools (code interpreter, functions, etc.)
#   - Metadata (git SHA, environment, version)
#
#   That's it. There's no container to build, no artifact to promote.
#   The agent IS its configuration.
#
# =============================================================================

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv  # noqa: E402 — must be before our imports

# Add project root to path so we can import our modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


def deploy_agent(environment: str, dry_run: bool = False) -> None:
    """
    Deploy (create or update) an agent to the specified environment.

    Args:
        environment: Target environment ('dev', 'test', 'prod')
        dry_run: If True, print what would happen without making API calls
    """
    # -------------------------------------------------------------------------
    # Step 1: Load environment variables
    # -------------------------------------------------------------------------
    # In local dev: loads from .env file
    # In CI/CD: environment variables are set by the pipeline
    # -------------------------------------------------------------------------
    load_dotenv()

    # -------------------------------------------------------------------------
    # Step 2: Load the agent config for this environment
    # -------------------------------------------------------------------------
    from src.agent.agent_definition import load_agent_config

    print(f"\n{'='*60}")
    print(f"  DEPLOYING AGENT — Environment: {environment.upper()}")
    print(f"{'='*60}\n")

    config = load_agent_config(environment, project_root)

    print(f"  Agent Name:    {config.name}")
    print(f"  Model:         {config.model}")
    print(f"  Tools:         {len(config.tools)} tool(s)")
    print(f"  Instructions:  {len(config.instructions)} chars")
    print(f"  Metadata:      {config.metadata}")
    print()

    if dry_run:
        print("  🔍 DRY RUN — No changes will be made.")
        print("  SDK parameters that would be sent:")
        import json

        print(json.dumps(config.to_sdk_params(), indent=2, default=str))
        return

    # -------------------------------------------------------------------------
    # Step 3: Authenticate to Azure
    # -------------------------------------------------------------------------
    # DefaultAzureCredential tries multiple auth methods in order:
    #   1. Environment variables (for CI/CD service principals)
    #   2. Managed Identity (for Azure-hosted pipelines)
    #   3. Azure CLI (for local development — `az login`)
    #   4. Azure Developer CLI (for `azd` workflows)
    #
    # This means the SAME code works locally and in CI/CD without changes.
    # -------------------------------------------------------------------------
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    project_endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")

    if not project_endpoint:
        print("  ❌ ERROR: AZURE_AI_PROJECT_ENDPOINT not set.")
        print("  Set it in .env (local) or pipeline variables (CI/CD).")
        sys.exit(1)

    print(f"  Project:       {project_endpoint}")

    # -------------------------------------------------------------------------
    # Step 4: Connect to the Foundry project
    # -------------------------------------------------------------------------
    from azure.ai.projects import AIProjectClient

    client = AIProjectClient(
        endpoint=project_endpoint,
        credential=credential,
    )

    # -------------------------------------------------------------------------
    # Step 5: Check if agent already exists, then create or update
    # -------------------------------------------------------------------------
    # In SDK v2, .create() creates a new agent (not create_agent()).
    # If an agent with the same name exists, we delete and recreate.
    #
    # WHY delete+recreate instead of update?
    #   - The Assistants API doesn't have a great "update everything" method
    #   - Delete+create ensures the agent matches the code exactly
    #   - Metadata tracks the git SHA, so you always know what's deployed
    # -------------------------------------------------------------------------
    sdk_params = config.to_sdk_params()

    with client:
        agents_client = client.agents

        # create_version handles both new agents and new versions of existing ones.
        # If the agent name doesn't exist yet, it creates the agent.
        # If it already exists, it creates a new version with the updated config.
        print(f"  🚀 Deploying agent '{config.name}'...")
        agent = agents_client.create_version(
            agent_name=config.name,
            definition=sdk_params["definition"],
            metadata=sdk_params.get("metadata"),
        )
        print("  ✅ Agent deployed successfully!")
        print(f"  📋 Agent ID: {agent.id}")
        print(f"  🏷️  Name:     {agent.name}")

    # -------------------------------------------------------------------------
    # Step 6: Output for pipeline consumption
    # -------------------------------------------------------------------------
    # CI/CD pipelines can capture this output to use in subsequent steps.
    # GitHub Actions: echo "agent_id=xxx" >> $GITHUB_OUTPUT
    # Azure DevOps:  echo "##vso[task.setvariable variable=agentId]xxx"
    # -------------------------------------------------------------------------
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"agent_id={agent.id}\n")
            f.write(f"agent_name={agent.name}\n")

    print(f"\n{'='*60}")
    print("  DEPLOYMENT COMPLETE ✅")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy a Foundry agent to a specific environment",
        epilog="""
Examples:
  # Deploy to dev (local)
  python src/scripts/deploy_agent.py --env dev

  # Dry run — see what would happen without making changes
  python src/scripts/deploy_agent.py --env prod --dry-run

  # Deploy to prod (in CI/CD pipeline)
  python src/scripts/deploy_agent.py --env prod
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["dev", "test", "prod"],
        help="Target environment (dev, test, prod)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would happen without making API calls",
    )
    args = parser.parse_args()

    deploy_agent(args.env, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    main()
