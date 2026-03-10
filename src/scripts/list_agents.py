#!/usr/bin/env python3
# =============================================================================
# list_agents.py — List all agents in your Foundry project
# =============================================================================
#
# Useful for:
#   - Verifying what's deployed in each environment
#   - Debugging "which agent is running?"
#   - Audit and inventory
#
# Usage:
#   python src/scripts/list_agents.py
#
# =============================================================================

import os
import sys

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv


def list_agents():
    load_dotenv()

    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        print("❌ AZURE_AI_PROJECT_ENDPOINT not set.")
        sys.exit(1)

    client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())

    with client:
        agents_list = list(client.agents.list())

        if not agents_list:
            print("No agents found in this project.")
            return

        print(f"\n{'Name':<35} {'Model':<20} {'ID':<40}")
        print("-" * 100)
        for agent in agents_list:
            # SDK v2: model lives under versions.latest.definition
            model = "unknown"
            latest = agent.get("versions", {}).get("latest", {})
            defn = latest.get("definition", {})
            model = defn.get("model", "unknown")
            print(f"{(agent.name or 'unnamed'):<35} {model:<20} {agent.id:<40}")


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    list_agents()
