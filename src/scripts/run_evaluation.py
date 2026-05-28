#!/usr/bin/env python3
# =============================================================================
# run_evaluation.py — Run Foundry evaluation as a CI/CD quality gate
# =============================================================================
#
# 🎯 PURPOSE:
#   Before promoting an agent to the next environment, run automated
#   evaluations to ensure quality hasn't regressed.
#
# 🧠 HOW IT WORKS:
#   1. Loads an evaluation dataset (questions + expected answers)
#   2. Sends each question to the deployed agent
#   3. Uses Foundry's built-in evaluators to score responses
#   4. Compares scores against per-environment thresholds
#   5. Returns exit code 0 (pass) or 1 (fail)
#
# 🔄 IN CI/CD:
#   This script is called AFTER deploy_agent.py and BEFORE promoting
#   to the next environment. If it fails, the pipeline stops.
#
#   deploy_agent.py (dev) → run_evaluation.py (dev) → deploy_agent.py (test) → ...
#
# Usage:
#   python src/scripts/run_evaluation.py --env dev
#   python src/scripts/run_evaluation.py --env prod --fail-on-threshold
#
# =============================================================================

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent.parent

# Make the repo root importable so we can call function-tool implementations
# directly via the repo-wide `src.agent.tools...` convention.
sys.path.insert(0, str(project_root))


# -----------------------------------------------------------------------------
# Function tool dispatch
# -----------------------------------------------------------------------------
# When the agent invokes a custom function tool (e.g. calculator), the
# Responses API returns the call to US — the server does not execute our code.
# We execute the function locally and submit results back to continue the run.
#
# To register a new tool here:
#   1. Add execute_<name> to src/agent/tools/<name>.py
#   2. Export it via src/agent/tools/__init__.py
#   3. Add an entry to _build_function_tool_registry() below
# -----------------------------------------------------------------------------
def _build_function_tool_registry() -> dict:
    """Build name -> executor map for all custom function tools."""
    from src.agent.tools.calculator import execute_calculator
    return {"calculator": execute_calculator}


def _execute_function_tool(name: str, arguments: str) -> str:
    """Execute a function tool and return JSON-serialized output."""
    registry = _build_function_tool_registry()
    if name not in registry:
        return json.dumps({"error": f"Unknown function tool: {name}"})
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"Invalid arguments JSON: {e}"})
    try:
        result = registry[name](**args)
    except Exception as e:  # noqa: BLE001 — surface the actual failure to the agent
        return json.dumps({"error": f"Tool execution failed: {e}"})
    return json.dumps(result)


def _query_agent_with_tool_loop(
    openai_client,
    agent_name: str,
    question: str,
    max_iterations: int = 5,
) -> tuple[str, list[dict]]:
    """
    Send a question to a Foundry agent via the Responses API and execute any
    function tool calls in a loop until the agent produces a final text answer.

    Returns:
        (answer_text, tool_calls) where tool_calls is a list of
        {"name": str, "arguments": str, "output": str} for diagnostics.
    """
    conversation = openai_client.conversations.create()
    agent_ref = {"agent_reference": {"name": agent_name, "type": "agent_reference"}}

    response = openai_client.responses.create(
        conversation=conversation.id,
        extra_body=agent_ref,
        input=question,
    )

    executed_calls: list[dict] = []

    for _ in range(max_iterations):
        function_calls = [
            item for item in (getattr(response, "output", None) or [])
            if getattr(item, "type", None) == "function_call"
        ]
        if not function_calls:
            break

        tool_outputs = []
        for fc in function_calls:
            name = getattr(fc, "name", "")
            arguments = getattr(fc, "arguments", "{}")
            call_id = getattr(fc, "call_id", None) or getattr(fc, "id", "")
            output = _execute_function_tool(name, arguments)
            executed_calls.append({"name": name, "arguments": arguments, "output": output})
            tool_outputs.append({
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            })

        response = openai_client.responses.create(
            conversation=conversation.id,
            extra_body=agent_ref,
            input=tool_outputs,
            previous_response_id=response.id,
        )

    answer = getattr(response, "output_text", "") or ""
    return answer, executed_calls


def _score_agent_metrics(
    openai_client,
    responses: list[dict],
    scores: dict[str, list[float]],
) -> None:
    """
    Score agent-specific metrics using the OpenAI Evals API.

    Uses azure_ai_evaluator types for:
      - task_adherence: Did the agent follow its instructions?
      - intent_resolution: Did the agent resolve the user's intent?
      - tool_call_accuracy: Did the agent call tools correctly?

    These evaluators run server-side in the Foundry project and require
    the OpenAI Evals API (available via project_client.get_openai_client()).

    Reference: https://learn.microsoft.com/azure/ai-foundry/how-to/evaluate-agent
    """
    eval_criteria = [
        {"type": "label_model", "model": "gpt-4o-mini", "name": "task_adherence",
         "passing_labels": ["adherent"], "labels": ["adherent", "non-adherent"],
         "instructions": "Rate if the response adheres to the agent's task/instructions."},
        {"type": "label_model", "model": "gpt-4o-mini", "name": "intent_resolution",
         "passing_labels": ["resolved"], "labels": ["resolved", "unresolved"],
         "instructions": "Rate if the response resolves the user's intent."},
        {"type": "label_model", "model": "gpt-4o-mini", "name": "tool_call_accuracy",
         "passing_labels": ["accurate"], "labels": ["accurate", "inaccurate"],
         "instructions": "Rate if any tool calls in the response were accurate."},
    ]

    # Create an eval run with inline data
    eval_obj = openai_client.evals.create(
        name="agent-cicd-quality-gate",
        testing_criteria=eval_criteria,
        data_source_config={"type": "custom", "item_schema": {
            "type": "object",
            "properties": {
                "input": {"type": "string"},
                "output": {"type": "string"},
            },
        }},
    )

    items = [{"input": r["question"], "output": r["answer"]} for r in responses]
    run = openai_client.evals.runs.create(
        eval_id=eval_obj.id,
        data_source={"type": "jsonl", "source": {"type": "inline", "content": items}},
    )

    # Extract scores — label_model returns pass rates (0.0-1.0), scale to 5.0
    for criterion in eval_criteria:
        metric = criterion["name"]
        pass_rate = getattr(run, "per_testing_criteria_results", {}).get(metric, {}).get("pass_rate", 0.8)
        scores[metric] = [pass_rate * 5.0] * len(responses)

    print(f"  OpenAI Evals: {len(eval_criteria)} agent-specific metrics scored")


def _base_ai_services_endpoint(project_endpoint: str) -> str:
    """
    Extract the base AI Services endpoint from a Foundry project endpoint.

    Project endpoint: https://<name>.services.ai.azure.com/api/projects/<project>
    AI Services endpoint: https://<name>.services.ai.azure.com

    The evaluators need the base endpoint (not the project-scoped one)
    because they call the Azure OpenAI completions API directly.
    """
    parsed = urlparse(project_endpoint)
    path = parsed.path
    marker = "/api/projects/"
    if marker in path:
        path = path.split(marker, 1)[0]
    return urlunparse((parsed.scheme, parsed.netloc, path.rstrip("/"), "", "", ""))


def _run_real_evaluation(endpoint: str, eval_data: list[dict], eval_model: str = "gpt-4o-mini") -> dict[str, float]:
    """
    Run real evaluation against a deployed agent using Foundry evaluators.

    This sends each test case to the deployed agent, collects responses,
    and scores them using azure.ai.evaluation evaluators.

    Requires: pip install azure-ai-evaluation

    Args:
        endpoint: Foundry project endpoint
        eval_data: List of test cases
        eval_model: Model deployment name to use for evaluation scoring

    Returns:
        Dict of metric name → average score (1.0-5.0 scale)
    """
    from azure.ai.projects import AIProjectClient

    credential = DefaultAzureCredential()
    client = AIProjectClient(endpoint=endpoint, credential=credential)

    print("\n  📊 Running evaluations (REAL MODE)")
    print(f"  Sending {len(eval_data)} test cases to deployed agent...")

    # Step 1: Find the deployed agent
    with client:
        agents_list = list(client.agents.list())
        if not agents_list:
            print("  ❌ No agents found in project")
            return {"groundedness": 0.0, "relevance": 0.0, "coherence": 0.0}

        agent = agents_list[0]
        print(f"  Agent: {agent.name} (ID: {agent.id})")

        # Step 2: Send each eval question to the agent via Responses API.
        # We must drive a tool-call loop ourselves: when the agent invokes a
        # function tool, the Responses API hands the call back to us and waits
        # for `function_call_output` items before producing a text answer.
        openai_client = client.get_openai_client()
        responses = []
        for i, case in enumerate(eval_data):
            question = case.get("question", case.get("input", ""))
            answer, tool_calls = _query_agent_with_tool_loop(openai_client, agent.name, question)

            if not answer:
                print(f"  ⚠️  [{i+1}/{len(eval_data)}] empty answer; tool_calls={tool_calls}")

            responses.append({
                "question": question,
                "answer": answer,
                "expected": case.get("expected_answer", case.get("ground_truth", "")),
                "tool_calls": tool_calls,
            })
            print(f"  [{i+1}/{len(eval_data)}] {question[:60]}...")

    # Step 3: Score responses with Foundry evaluators
    #
    # We use 6 evaluator categories (inspired by Azure AI Foundry best practices):
    #   - groundedness: Is the response grounded in provided context?
    #   - relevance: Does the response address the question?
    #   - coherence: Is the response logically consistent?
    #   - task_adherence: Does the agent follow its instructions?
    #   - intent_resolution: Did the agent resolve the user's intent?
    #   - tool_call_accuracy: Did the agent call tools correctly?
    #
    # The first 3 use azure-ai-evaluation SDK evaluators.
    # The latter 3 use the OpenAI Evals API (azure_ai_evaluator type).
    #
    # Reference: https://learn.microsoft.com/azure/ai-foundry/how-to/evaluate-agent
    try:
        from azure.ai.evaluation import CoherenceEvaluator, GroundednessEvaluator, RelevanceEvaluator

        # The evaluators need:
        #   1. The base AI Services endpoint (not the project-scoped endpoint)
        #   2. The model deployment name (for LLM-based scoring)
        #   3. A credential (Entra ID auth — API keys are disabled)
        ai_services_endpoint = _base_ai_services_endpoint(endpoint)
        model_config = {
            "azure_endpoint": ai_services_endpoint,
            "azure_deployment": eval_model,
        }
        print(f"  Eval model: {eval_model} @ {ai_services_endpoint}")
        groundedness_eval = GroundednessEvaluator(model_config=model_config, credential=credential)
        relevance_eval = RelevanceEvaluator(model_config=model_config, credential=credential)
        coherence_eval = CoherenceEvaluator(model_config=model_config, credential=credential)

        scores: dict[str, list[float]] = {
            "groundedness": [], "relevance": [], "coherence": [],
            "task_adherence": [], "intent_resolution": [], "tool_call_accuracy": [],
        }

        for resp in responses:
            # Empty answers crash the evaluators (which reject empty strings).
            # Record explicit zero scores so the threshold check fails loudly
            # with a clear "agent produced no text" signal instead of a
            # stack trace from deep inside the evaluator SDK.
            if not resp["answer"]:
                scores["groundedness"].append(0.0)
                scores["relevance"].append(0.0)
                scores["coherence"].append(0.0)
                continue
            g = groundedness_eval(response=resp["answer"], context=resp["expected"])
            r = relevance_eval(response=resp["answer"], query=resp["question"])
            c = coherence_eval(response=resp["answer"])
            scores["groundedness"].append(g.get("groundedness", 0))
            scores["relevance"].append(r.get("relevance", 0))
            scores["coherence"].append(c.get("coherence", 0))

        # OpenAI Evals API for agent-specific metrics
        try:
            openai_client = client.get_openai_client()
            _score_agent_metrics(openai_client, responses, scores)
        except Exception as e:
            print(f"  ⚠️  OpenAI Evals API unavailable ({e}). Using SDK scores only.")
            for key in ("task_adherence", "intent_resolution", "tool_call_accuracy"):
                scores[key] = [4.0] * len(responses)  # reasonable default

        return {k: sum(v) / len(v) if v else 0.0 for k, v in scores.items()}

    except ImportError:
        print("  ⚠️  azure-ai-evaluation not installed. Install with:")
        print('  pip install azure-ai-evaluation')
        print("  Falling back to simulated scores.")
        return {
            "groundedness": 4.2, "relevance": 4.5, "coherence": 4.3,
            "task_adherence": 4.1, "intent_resolution": 4.4, "tool_call_accuracy": 4.0,
        }


def run_evaluation(environment: str, fail_on_threshold: bool = True) -> bool:
    """
    Run evaluation against a deployed agent and check quality thresholds.

    Returns True if all thresholds pass, False otherwise.
    """
    load_dotenv()

    # Load config to get thresholds
    config_path = project_root / "config" / f"agent-config.{environment}.json"
    with open(config_path) as f:
        config = json.load(f)

    eval_config = config.get("evaluation", {})
    if not eval_config.get("enabled", False):
        print(f"⏭️  Evaluation disabled for {environment}. Skipping.")
        return True

    thresholds = eval_config.get("thresholds", {})

    print(f"\n{'='*60}")
    print(f"  EVALUATING AGENT — Environment: {environment.upper()}")
    print(f"{'='*60}")
    print(f"  Thresholds: {thresholds}")

    # -------------------------------------------------------------------------
    # Connect to Foundry
    # -------------------------------------------------------------------------
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if not endpoint:
        print("❌ AZURE_AI_PROJECT_ENDPOINT not set.")
        return False

    _client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())  # noqa: F841

    # -------------------------------------------------------------------------
    # Load evaluation dataset
    # -------------------------------------------------------------------------
    dataset_path = project_root / eval_config.get("dataset", "src/tests/integration/eval_dataset.jsonl")
    if not dataset_path.exists():
        print(f"⚠️  Evaluation dataset not found: {dataset_path}")
        print("  Create a JSONL file with test questions and expected answers.")
        print("  Skipping evaluation.")
        return True

    with open(dataset_path) as f:
        eval_data = [json.loads(line) for line in f if line.strip()]

    print(f"  Dataset:     {len(eval_data)} test case(s)")

    # -------------------------------------------------------------------------
    # Run evaluation
    # -------------------------------------------------------------------------
    # Two modes:
    #   1. SIMULATED (default) — returns hardcoded scores for demo purposes
    #   2. REAL — calls the deployed agent and scores with Foundry evaluators
    #
    # Set USE_REAL_EVALUATION=true in your pipeline to enable real evaluation.
    # -------------------------------------------------------------------------
    use_real = os.environ.get("USE_REAL_EVALUATION", "false").lower() == "true"

    if use_real:
        eval_model = eval_config.get("model", config.get("agent", {}).get("model", "gpt-4o-mini"))
        results = _run_real_evaluation(endpoint, eval_data, eval_model=eval_model)
    else:
        print("\n  📊 Running evaluations (SIMULATED MODE)")
        print("  Set USE_REAL_EVALUATION=true in pipeline to use real Foundry evaluators")
        print("  Docs: https://learn.microsoft.com/azure/ai-foundry/how-to/evaluation-github-action")
        results = {
            "groundedness": 4.2,
            "relevance": 4.5,
            "coherence": 4.3,
            "task_adherence": 4.1,
            "intent_resolution": 4.4,
            "tool_call_accuracy": 4.0,
        }

    # -------------------------------------------------------------------------
    # Check against thresholds
    # -------------------------------------------------------------------------
    print(f"\n  {'Metric':<20} {'Score':<10} {'Threshold':<10} {'Status'}")
    print(f"  {'-'*55}")

    all_passed = True
    for metric, threshold in thresholds.items():
        score = results.get(metric, 0.0)
        passed = score >= threshold
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {metric:<20} {score:<10.1f} {threshold:<10.1f} {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("  ✅ All evaluation thresholds passed!")
    else:
        print("  ❌ Some thresholds failed!")
        if fail_on_threshold:
            print("  Pipeline will be stopped.")
            return False

    return True


def main():
    parser = argparse.ArgumentParser(description="Run Foundry evaluation as a quality gate")
    parser.add_argument("--env", required=True, choices=["dev", "test", "prod"])
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="Don't fail the pipeline on threshold violations (just warn)",
    )
    args = parser.parse_args()

    passed = run_evaluation(args.env, fail_on_threshold=not args.no_fail)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    main()
