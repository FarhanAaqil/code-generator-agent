from groq import Groq
from config import GROQ_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS

CRITIQUE_SYSTEM_PROMPT = """You are a strict Python code reviewer. Your job is to evaluate code for algorithmic efficiency and correctness — NOT style.

Review criteria:
- Flag O(n^2) algorithms when an O(n) or O(n log n) solution exists
- Flag redundant code that computes the same thing twice
- Flag missing edge cases that would cause crashes or wrong output
- Flag incorrect output format compared to the task requirements

Do NOT flag:
- Variable naming preferences
- Style choices (spacing, formatting)
- Nice-to-have improvements with no performance impact

Respond ONLY in this exact format — no preamble, no explanation outside the format:

If code is acceptable:
VERDICT: APPROVED

If code needs improvement:
VERDICT: REWRITE
ISSUES:
- [specific issue 1]
- [specific issue 2]
REWRITE_INSTRUCTIONS:
[specific, actionable instructions for the generator to rewrite the code]"""


def _parse_verdict(raw: str) -> dict:
    """Parse structured verdict from critique response."""
    raw = raw.strip()
    verdict = "APPROVED"
    issues = []
    instructions = ""

    if "VERDICT: REWRITE" in raw:
        verdict = "REWRITE"
        # Parse issues
        if "ISSUES:" in raw:
            issues_block = raw.split("ISSUES:")[1]
            if "REWRITE_INSTRUCTIONS:" in issues_block:
                issues_block = issues_block.split("REWRITE_INSTRUCTIONS:")[0]
            for line in issues_block.strip().splitlines():
                line = line.strip()
                if line.startswith("- "):
                    issues.append(line[2:].strip())
                elif line:
                    issues.append(line)
        # Parse instructions
        if "REWRITE_INSTRUCTIONS:" in raw:
            instructions = raw.split("REWRITE_INSTRUCTIONS:")[1].strip()
    elif "VERDICT: APPROVED" in raw:
        verdict = "APPROVED"

    return {
        "verdict": verdict,
        "issues": issues,
        "instructions": instructions,
        "raw": raw
    }


def critique_code(
    task: str,
    code: str,
    output: str,
    client_override=None,
    model_override: str = None,
    api_key_override: str = None
) -> dict:
    """
    Critique code and return structured verdict.
    Returns {verdict, issues, instructions, raw}
    """
    api_key = api_key_override or GROQ_API_KEY
    model = model_override or MODEL

    client = client_override or Groq(api_key=api_key)

    user_msg = f"""Task: {task}

Code to review:
```python
{code}
```

Output produced:
{output if output else "(no output)"}

Review this code and respond in the required format."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": CRITIQUE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.0,
            max_tokens=1024,
            stream=False
        )
        raw = response.choices[0].message.content or ""
        return _parse_verdict(raw)
    except Exception as e:
        return {
            "verdict": "ERROR",
            "issues": [str(e)],
            "instructions": "",
            "raw": str(e)
        }
