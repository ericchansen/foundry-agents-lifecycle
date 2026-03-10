# =============================================================================
# calculator.py — Example Function Tool for Foundry Agent
# =============================================================================
#
# WHY THIS FILE EXISTS:
#   Foundry agents can call "function tools" — your custom Python functions
#   that the agent invokes when it needs to perform specific actions.
#
#   This is a simple calculator example, but in production this could be:
#   - A database query function
#   - An API call to an internal service
#   - A data transformation function
#   - Anything your agent needs to do that requires custom code
#
# HOW IT CONNECTS TO CI/CD:
#   This code is version-controlled alongside the agent definition.
#   When you deploy the agent, the function tool schema is registered
#   with the agent so it knows what functions are available.
#
# =============================================================================


def get_calculator_tool_definition() -> dict:
    """
    Returns the OpenAI-compatible function tool definition for the calculator.

    This JSON schema tells the agent:
    - What the function is called
    - What parameters it accepts
    - What each parameter means

    The agent uses this to decide WHEN to call the function and
    WHAT arguments to pass.
    """
    return {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Perform basic arithmetic calculations. "
                "Use this for addition, subtraction, multiplication, and division."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "The arithmetic operation to perform",
                    },
                    "a": {
                        "type": "number",
                        "description": "The first number",
                    },
                    "b": {
                        "type": "number",
                        "description": "The second number",
                    },
                },
                "required": ["operation", "a", "b"],
            },
        },
    }


def execute_calculator(operation: str, a: float, b: float) -> dict:
    """
    Execute a calculator operation. This is what runs when the agent
    calls the calculator function tool.

    In a real scenario, this function might:
    - Call an external API
    - Query a database
    - Run a complex business calculation
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "Error: Division by zero",
    }

    if operation not in operations:
        return {"error": f"Unknown operation: {operation}"}

    result = operations[operation](a, b)
    return {"result": result, "expression": f"{a} {operation} {b} = {result}"}
