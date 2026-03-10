# =============================================================================
# agent_definition.py — THE core file that defines what an agent IS
# =============================================================================
#
# 🎯 PURPOSE:
#   This file reads the per-environment config (config/agent-config.{env}.json)
#   and constructs everything needed to create/update an agent via the SDK.
#
# 🧠 KEY CONCEPT:
#   There is NO "agent artifact" in Foundry. An agent is just:
#     1. A name
#     2. A model deployment to use
#     3. Instructions (system prompt)
#     4. Tools (code interpreter, functions, Bing, etc.)
#     5. Metadata (key-value pairs for tracking)
#
#   This file assembles all of those from version-controlled sources.
#   The deploy_agent.py script then calls the SDK to create/update it.
#
# 🔄 CI/CD FLOW:
#   Code change → PR → CI validates → Merge → CD calls deploy_agent.py
#   → deploy_agent.py loads this config → SDK creates agent in target env
#
# =============================================================================

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from src.agent.tools.calculator import get_calculator_tool_definition


@dataclass
class AgentConfig:
    """
    Everything needed to create a Foundry agent.

    This dataclass is populated from the per-environment JSON config file.
    It's the "blueprint" that the deploy script uses to call the SDK.
    """

    name: str
    model: str
    instructions: str
    tools: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_sdk_params(self) -> dict:
        """
        Convert this config into the parameters that the
        azure-ai-projects SDK v2 expects for agents.create().

        SDK v2 uses a PromptAgentDefinition object instead of flat params.
        """
        from azure.ai.projects.models import FunctionTool, PromptAgentDefinition

        # Build definition — include all SDK-compatible tools
        definition_kwargs = {
            "model": self.model,
            "instructions": self.instructions,
        }
        # Convert config tools to SDK objects:
        #   - Built-in tools (code_interpreter, file_search) pass through as dicts
        #   - Function tools must be converted from OpenAI format
        #     {"type": "function", "function": {"name": ..., "parameters": ...}}
        #     to SDK FunctionTool(name=..., parameters=...)
        sdk_tools = []
        for t in self.tools:
            if not isinstance(t, dict):
                continue
            tool_type = t.get("type")
            if tool_type in ("code_interpreter", "file_search"):
                sdk_tools.append(t)
            elif tool_type == "function" and "function" in t:
                fn = t["function"]
                sdk_tools.append(FunctionTool(
                    name=fn["name"],
                    description=fn.get("description", ""),
                    parameters=fn.get("parameters", {}),
                ))
        if sdk_tools:
            definition_kwargs["tools"] = sdk_tools

        definition = PromptAgentDefinition(**definition_kwargs)
        return {
            "name": self.name,
            "definition": definition,
            "metadata": self.metadata,
        }


def load_agent_config(environment: str, project_root: Path | None = None) -> AgentConfig:
    """
    Load agent configuration for a specific environment.

    This function:
    1. Reads the per-environment JSON config file
    2. Loads the system prompt from the referenced file
    3. Resolves tool definitions into SDK-compatible format
    4. Returns a fully-populated AgentConfig ready for deployment

    Args:
        environment: One of 'dev', 'test', 'prod'
        project_root: Root of the project (defaults to repo root)

    Returns:
        AgentConfig with all fields populated from config + prompt files

    Example:
        >>> config = load_agent_config("dev")
        >>> print(config.name)
        'foundry-demo-agent-dev'
        >>> print(config.model)
        'gpt-4o-mini'
    """
    if project_root is None:
        project_root = Path(__file__).parent.parent.parent  # src/agent/ → repo root

    # -------------------------------------------------------------------------
    # Step 1: Load the per-environment config file
    # -------------------------------------------------------------------------
    config_path = project_root / "config" / f"agent-config.{environment}.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"No config file for environment '{environment}'. "
            f"Expected: {config_path}\n"
            f"Available environments: dev, test, prod"
        )

    with open(config_path) as f:
        raw_config = json.load(f)

    agent_config = raw_config["agent"]

    # -------------------------------------------------------------------------
    # Step 2: Load the system prompt from file
    # -------------------------------------------------------------------------
    # The instructions_file in the config points to a markdown file containing
    # the system prompt. This lets you version-control prompts separately
    # and override them per environment (e.g., stricter prod prompt).
    # -------------------------------------------------------------------------
    instructions_file = project_root / agent_config["instructions_file"]
    if not instructions_file.exists():
        raise FileNotFoundError(
            f"System prompt file not found: {instructions_file}\n"
            f"Referenced by: {config_path}"
        )

    instructions = instructions_file.read_text(encoding="utf-8").strip()

    # -------------------------------------------------------------------------
    # Step 3: Resolve tools into SDK-compatible format
    # -------------------------------------------------------------------------
    # The config file lists tools by type/name. Here we convert them into
    # the JSON format the SDK expects.
    #
    # Tool types:
    #   - "code_interpreter" → Built-in, just needs {"type": "code_interpreter"}
    #   - "function"         → Custom function, needs full JSON schema
    #   - "bing_grounding"   → Needs a connection ID (from Foundry project)
    # -------------------------------------------------------------------------
    sdk_tools = []
    for tool_def in agent_config.get("tools", []):
        tool_type = tool_def["type"]

        if tool_type == "code_interpreter":
            sdk_tools.append({"type": "code_interpreter"})

        elif tool_type == "function":
            # Look up the function definition by name
            func_name = tool_def["function_name"]
            if func_name == "calculator":
                sdk_tools.append(get_calculator_tool_definition())
            else:
                raise ValueError(f"Unknown function tool: {func_name}")

        elif tool_type == "bing_grounding":
            # Bing grounding requires a connection ID from the Foundry project
            # This would come from environment variables or Key Vault
            connection_id = os.environ.get("BING_CONNECTION_ID", "")
            if connection_id:
                sdk_tools.append({
                    "type": "bing_grounding",
                    "bing_grounding": {"connection": {"id": connection_id}},
                })
        else:
            raise ValueError(f"Unknown tool type: {tool_type}")

    # -------------------------------------------------------------------------
    # Step 4: Set metadata (useful for tracking deployments)
    # -------------------------------------------------------------------------
    metadata = agent_config.get("metadata", {})
    # Add git commit SHA if available (set by CI/CD pipeline)
    git_sha = os.environ.get("GIT_SHA", os.environ.get("GITHUB_SHA", "local"))
    metadata["git_sha"] = git_sha[:8]  # Short SHA for readability

    # -------------------------------------------------------------------------
    # Step 5: Return the fully-populated config
    # -------------------------------------------------------------------------
    return AgentConfig(
        name=agent_config["name"],
        model=agent_config["model"],
        instructions=instructions,
        tools=sdk_tools,
        metadata=metadata,
    )
