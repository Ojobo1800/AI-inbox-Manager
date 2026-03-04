# Directives

This directory contains Standard Operating Procedures (SOPs) and runbooks.

## Purpose
Directives define **what to do** in human-readable form. Claude reads these before taking action.

## Structure
Each directive should include:
- **Goal**: What this directive accomplishes
- **Inputs**: What data/parameters are needed
- **Outputs**: What results are produced
- **Steps**: Clear, numbered steps for execution
- **Edge Cases**: Known exceptions and how to handle them
- **Safety Constraints**: What must never happen
- **Related Scripts**: Which execution scripts implement this

## Rules
- Written in plain language
- Living documents - update as system learns
- No executable code
- No orchestration logic
- Reference execution scripts, don't replace them

## Example Structure
```
# Directive: [Name]

## Goal
[What this accomplishes]

## Inputs
- [Input 1]
- [Input 2]

## Steps
1. [Step 1]
2. [Step 2]

## Edge Cases
- **Scenario**: [How to handle]

## Related Scripts
- `execution/[script_name].py`
```
