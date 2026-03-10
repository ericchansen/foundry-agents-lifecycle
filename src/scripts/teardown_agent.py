#!/usr/bin/env python3
# =============================================================================
# teardown_agent.py — Delete an agent from a Foundry project
# =============================================================================
#
# Useful for:
#   - Cleaning up after demos
#   - Removing agents from decommissioned environments
#   - CI/CD cleanup steps
#
# Usage:
#   python src/scripts/teardown_agent.py --name foundry-demo-agent-dev
#   python src/scripts/teardown_agent.py --all  # Delete ALL agents (careful!)
#
# =============================================================================

import argparse
import os
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def teardown_agent(name: str | None = None, delete_all: bool = False):
    load_dotenv()

    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        print("❌ AZURE_AI_PROJECT_ENDPOINT not set.")
        sys.exit(1)

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    with client:
        agents_list = list(client.agents.list())

        deleted = 0
        for agent in agents_list:
            if delete_all or (name and agent.name == name):
                print(f"🗑️  Deleting agent: {agent.name} (ID: {agent.id})")
                try:
                    client.agents.delete(agent.id)
                except Exception as e:
                    print(f"  ⚠️  Delete failed ({e}). Skipping.")
                    continue
                deleted += 1

        if deleted == 0:
            print("No agents found matching criteria.")
        else:
            print(f"\n✅ Deleted {deleted} agent(s).")


def main():
    parser = argparse.ArgumentParser(description="Delete agents from a Foundry project")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", help="Name of the agent to delete")
    group.add_argument("--all", action="store_true", help="Delete ALL agents (use with caution!)")
    args = parser.parse_args()

    teardown_agent(name=args.name, delete_all=args.all)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    main()
