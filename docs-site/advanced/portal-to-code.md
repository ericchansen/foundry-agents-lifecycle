# Portal-to-Code Migration

How to take a portal-authored agent and make it code-first.

---

## Why Migrate?

Portal-authored agents have no CI/CD:

| Aspect | Portal | Code-First |
|--------|--------|-----------|
| Version control | ❌ No history | ✅ Full git history |
| Code review | ❌ No PRs | ✅ PR reviews |
| Rollback | ❌ Manual recreation | ✅ `git revert` |
| Multi-env | ❌ Copy/paste in portal | ✅ Per-env configs |
| Testing | ❌ Manual testing | ✅ Automated eval |
| Audit trail | ❌ None | ✅ Git commits + pipeline logs |

## Migration Steps

### Step 1: Document the Portal Agent

In the Foundry portal, note everything about your agent:

- [ ] **Agent name**
- [ ] **Model deployment** used
- [ ] **System prompt** (copy the full text)
- [ ] **Tools** (code interpreter, functions, file search, etc.)
- [ ] **File attachments** (if any)
- [ ] **Knowledge sources** (if any)

### Step 2: Create the Config File

```json title="config/agent-config.dev.json"
{
    "agent": {
        "name": "my-portal-agent-dev",
        "model": "gpt-4o-mini",
        "instructions_file": "src/agent/prompts/system_prompt.md",
        "tools": [
            {"type": "code_interpreter"},
            {"type": "function", "function_name": "my_tool"}
        ]
    },
    "evaluation": {
        "thresholds": {
            "groundedness": 3.0,
            "relevance": 3.0,
            "coherence": 3.0
        }
    }
}
```

### Step 3: Save the System Prompt

Copy the system prompt from the portal into a markdown file:

```bash
# Create the file
cat > src/agent/prompts/system_prompt.md << 'EOF'
You are a helpful assistant that...
(paste your portal system prompt here)
EOF
```

### Step 4: Codify Custom Tools

If the agent uses function tools, create Python definitions:

```python title="src/agent/tools/my_tool.py"
def get_my_tool_definition():
    return {
        "type": "function",
        "function": {
            "name": "my_tool",
            "description": "Does something useful",
            "parameters": {
                "type": "object",
                "properties": {
                    "input": {"type": "string"}
                },
                "required": ["input"]
            }
        }
    }
```

### Step 5: Test the Codified Agent

```bash
# Deploy to dev
python src/scripts/deploy_agent.py --env dev

# Verify behavior matches the portal agent
python src/scripts/run_evaluation.py --env dev
```

### Step 6: Delete the Portal Agent

Once the codified agent is validated, delete the portal-created one.
**From now on, all changes go through code → PR → CI/CD.**

!!! success "You're now code-first"
    Every future change is:

    1. Edit code/config in a branch
    2. Open a PR → CI validates
    3. Merge → CD deploys to dev → test → prod
    4. Full audit trail in git
