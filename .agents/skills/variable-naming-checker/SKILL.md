---
name: variable-naming-checker
description: A specialized workspace skill to check variable, function, and class naming conventions across the codebase for PEP 8 and JavaScript best practices. Always execute this capability by defining and invoking a dedicated sub-agent that NEVER proposes or writes any changes. It only checks naming and reports findings.
---

# Variable Naming Checker Skill

This skill allows the agent to scan the repository and review naming conventions for variables, parameters, attributes, functions, and classes against PEP 8 (Python) and modern camelCase (JavaScript/TypeScript) best practices. It does not propose or make any changes to the codebase; it only scans and generates a compliance report.

## Mandatory Execution Policy: Always Run as Sub-Agent

To maintain security, keep logs clean, and avoid cluttering the parent agent's context, variable naming checks **MUST ALWAYS** run as a specialized sub-agent.

### Step 1: Define the Sub-Agent
Define a dedicated sub-agent using the `define_subagent` tool with the following configuration:
*   **name**: `variable-naming-checker`
*   **description**: `Dedicated agent that scans files for variable naming style mismatches, built-in shadowing, and overly short names, then reports findings. It NEVER writes any changes.`
*   **system_prompt**:
    ```
    You are a code quality focused sub-agent. Your only task is to run the variable naming check script and report any compliance findings. You must NEVER write or modify any files under any circumstances; only detect naming mismatches and report back to the root agent.
    
    To scan the files:
    1. Run the scanning script via command:
       `uv run python .agents/skills/variable-naming-checker/scripts/check_variable_naming.py`
    2. If the command succeeds (exit code 0), report back that all variables are compliant with naming best practices.
    3. If the command fails (exit code 1), parse the output, extract the listed violations (files, line numbers, issue type, non-compliant names, and suggestions), and report them clearly. Do NOT attempt to modify or fix the files.
    ```
*   **enable_write_tools**: `true` (required to run shell commands)

### Step 2: Invoke the Sub-Agent
Invoke the sub-agent using the `invoke_subagent` tool:
*   **TypeName**: `variable-naming-checker`
*   **Role**: `Naming Convention Auditor`
*   **Prompt**: `Please run the variable naming checker script and report any findings or errors.`

---

## Technical Details

The scanning script runs:
`git ls-files -z --cached --others --exclude-standard`
to retrieve all repository files (excluding those in `.gitignore`).

### Supported Language Guidelines

#### Python (PEP 8)
*   **Classes**: `PascalCase` (e.g., `class TravelPlanner:`)
*   **Functions & Methods**: `snake_case` (e.g., `def calculate_route():`), ignoring standard dunders like `__init__`.
*   **Local Variables**: `snake_case` (e.g., `user_id = 42`).
*   **Global Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_TIMEOUT = 30`) or `snake_case`.
*   **Arguments/Parameters**: `snake_case` (e.g., `def plan(trip_id):`).

#### JavaScript & TypeScript
*   **Classes**: `PascalCase` (e.g., `class MapWidget {}`)
*   **Functions & Methods**: `camelCase` (e.g., `function updateRoute() {}`)
*   **Variables**: `camelCase` or `UPPER_SNAKE_CASE` for global constant definitions.

### Common Quality Rules Applied
1.  **Style Mismatches**: Flags any names that violate the naming guidelines.
2.  **Built-in Shadowing**: Flags variables, arguments, or functions that shadow system built-in functions or types (e.g., `id`, `type`, `list`, `sum` in Python; `Object`, `Array`, `console`, `window` in JS/TS).
3.  **Too Short/Uninformative**: Flags single-character variable names (e.g., `a`, `v`, `q`), except for accepted loop index and mathematical context variables: `i`, `j`, `k`, `n`, `_`, `x`, `y`, `z`, `e`, `f`, `d`.

### Safe Bypasses & Exclusions
If a match is detected on a dummy file, example file, or legitimate use case, developers can bypass the check for that specific line by adding one of the following comments to the end of the line:
*   **Python**: `# ignore-naming` or `# nosec`
*   **JS/TS**: `// ignore-naming` or `// nosec`

Example:
```python
id = "123"  # ignore-naming
```
