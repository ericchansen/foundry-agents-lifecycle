# =============================================================================
# test_agent_config.py — Unit tests for agent configuration
# =============================================================================
#
# WHAT THESE TESTS VALIDATE:
#   - Config files are valid JSON
#   - Required fields exist in every config
#   - Prompt files referenced by configs actually exist
#   - Tool definitions are well-formed
#   - Environment-specific overrides work correctly
#
# WHY THIS MATTERS FOR CI/CD:
#   These tests run in the CI pipeline (on every PR).
#   They catch configuration mistakes before any deployment attempt.
#   A broken config file should never make it past CI.
#
# =============================================================================

import json
from pathlib import Path

import pytest

# Project root is 4 levels up: src/tests/unit/ → src/tests/ → src/ → repo root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class TestAgentConfigs:
    """Test that all environment config files are valid and complete."""

    ENVIRONMENTS = ["dev", "test", "prod"]

    @pytest.fixture(params=ENVIRONMENTS)
    def env_config(self, request):
        """Load config for each environment."""
        env = request.param
        config_path = PROJECT_ROOT / "config" / f"agent-config.{env}.json"
        assert config_path.exists(), f"Config file missing for environment: {env}"

        with open(config_path) as f:
            config = json.load(f)
        return env, config

    def test_config_has_agent_section(self, env_config):
        """Every config must have an 'agent' section."""
        env, config = env_config
        assert "agent" in config, f"{env}: missing 'agent' section"

    def test_agent_has_required_fields(self, env_config):
        """Every agent config must have name, model, and instructions_file."""
        env, config = env_config
        agent = config["agent"]

        required_fields = ["name", "model", "instructions_file"]
        for field in required_fields:
            assert field in agent, f"{env}: agent missing required field '{field}'"

    def test_instructions_file_exists(self, env_config):
        """The instructions file referenced in config must actually exist."""
        env, config = env_config
        instructions_path = PROJECT_ROOT / config["agent"]["instructions_file"]
        assert instructions_path.exists(), (
            f"{env}: instructions file not found: {instructions_path}\n"
            f"Referenced by: config/agent-config.{env}.json"
        )

    def test_agent_name_is_valid(self, env_config):
        """Agent names must be alphanumeric with hyphens, max 63 chars."""
        env, config = env_config
        name = config["agent"]["name"]

        assert len(name) <= 63, f"{env}: agent name too long ({len(name)} > 63 chars)"
        assert name[0].isalnum(), f"{env}: agent name must start with alphanumeric"
        assert name[-1].isalnum(), f"{env}: agent name must end with alphanumeric"
        for char in name:
            assert char.isalnum() or char == "-", f"{env}: invalid char in agent name: '{char}'"

    def test_tools_are_valid(self, env_config):
        """All tools must have a valid type."""
        env, config = env_config
        valid_types = {"code_interpreter", "function", "bing_grounding", "file_search"}

        for tool in config["agent"].get("tools", []):
            assert "type" in tool, f"{env}: tool missing 'type' field"
            assert tool["type"] in valid_types, f"{env}: unknown tool type '{tool['type']}'"


class TestToolDefinitions:
    """Test that custom tool definitions are well-formed."""

    def test_calculator_tool_has_required_fields(self):
        """Calculator tool definition must be valid for the SDK."""
        from src.agent.tools.calculator import get_calculator_tool_definition

        tool = get_calculator_tool_definition()
        assert tool["type"] == "function"
        assert "function" in tool
        assert "name" in tool["function"]
        assert "parameters" in tool["function"]

    def test_calculator_execution(self):
        """Calculator should return correct results."""
        from src.agent.tools.calculator import execute_calculator

        result = execute_calculator("add", 2, 3)
        assert result["result"] == 5

        result = execute_calculator("multiply", 4, 5)
        assert result["result"] == 20

        result = execute_calculator("divide", 10, 0)
        assert "Error" in str(result["result"])


class TestEvaluationConfig:
    """Test that evaluation config sections are valid."""

    ENVIRONMENTS = ["dev", "test", "prod"]
    REQUIRED_EVALUATORS = [
        "groundedness", "relevance", "coherence",
        "task_adherence", "intent_resolution", "tool_call_accuracy",
    ]

    @pytest.fixture(params=ENVIRONMENTS)
    def eval_config(self, request):
        """Load evaluation config for each environment."""
        env = request.param
        config_path = PROJECT_ROOT / "config" / f"agent-config.{env}.json"
        with open(config_path) as f:
            config = json.load(f)
        return env, config.get("evaluation", {})

    def test_evaluation_section_exists(self, eval_config):
        """Every config must have an evaluation section."""
        env, eval_cfg = eval_config
        assert eval_cfg, f"{env}: missing 'evaluation' section"
        assert "thresholds" in eval_cfg, f"{env}: evaluation missing 'thresholds'"

    def test_all_evaluators_have_thresholds(self, eval_config):
        """All 6 standard evaluators must have threshold values."""
        env, eval_cfg = eval_config
        thresholds = eval_cfg.get("thresholds", {})
        for evaluator in self.REQUIRED_EVALUATORS:
            assert evaluator in thresholds, f"{env}: missing threshold for '{evaluator}'"
            assert isinstance(thresholds[evaluator], (int, float)), (
                f"{env}: threshold for '{evaluator}' must be numeric"
            )

    def test_thresholds_increase_with_environment(self):
        """Prod thresholds should be >= test >= dev (stricter in higher envs)."""
        configs = {}
        for env in self.ENVIRONMENTS:
            path = PROJECT_ROOT / "config" / f"agent-config.{env}.json"
            with open(path) as f:
                configs[env] = json.load(f)["evaluation"]["thresholds"]

        for metric in self.REQUIRED_EVALUATORS:
            dev = configs["dev"].get(metric, 0)
            test = configs["test"].get(metric, 0)
            prod = configs["prod"].get(metric, 0)
            assert dev <= test <= prod, (
                f"{metric}: thresholds must increase: dev({dev}) <= test({test}) <= prod({prod})"
            )

    def test_dataset_file_exists(self, eval_config):
        """The evaluation dataset referenced in config must exist."""
        env, eval_cfg = eval_config
        if not eval_cfg.get("enabled", False):
            pytest.skip(f"{env}: evaluation disabled")
        dataset = eval_cfg.get("dataset", "")
        if dataset:
            assert (PROJECT_ROOT / dataset).exists(), f"{env}: dataset not found: {dataset}"


class TestAgentDefinitionLoading:
    """Test the agent definition loading logic."""

    def test_load_dev_config(self):
        """Should successfully load dev config."""
        from src.agent.agent_definition import load_agent_config

        config = load_agent_config("dev", PROJECT_ROOT)
        assert config.name == "foundry-demo-agent-dev"
        assert config.model == "gpt-4o-mini"
        assert len(config.instructions) > 0
        assert len(config.tools) > 0

    def test_load_prod_config(self):
        """Should successfully load prod config."""
        from src.agent.agent_definition import load_agent_config

        config = load_agent_config("prod", PROJECT_ROOT)
        assert config.name == "foundry-demo-agent-prod"
        assert config.model == "gpt-4o"

    def test_invalid_environment_raises(self):
        """Should raise FileNotFoundError for invalid environment."""
        from src.agent.agent_definition import load_agent_config

        with pytest.raises(FileNotFoundError):
            load_agent_config("staging", PROJECT_ROOT)

    def test_sdk_params_format(self):
        """to_sdk_params() should return a dict with expected keys (SDK v2 format)."""
        from src.agent.agent_definition import load_agent_config

        config = load_agent_config("dev", PROJECT_ROOT)
        params = config.to_sdk_params()

        # SDK v2: top-level keys are name, definition, metadata
        assert "name" in params
        assert "definition" in params
        assert "metadata" in params

        # Model, instructions, tools are inside the definition object
        defn = params["definition"]
        assert hasattr(defn, "model") or isinstance(defn, dict)
        assert params["metadata"]["environment"] == "dev"
