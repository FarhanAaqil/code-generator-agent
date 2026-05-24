import json
import datetime
import os
from config import GROQ_API_KEY, MODEL, MAX_RETRIES, LOG_DIR
from sandbox import run_code
from humaneval_problems import PROBLEMS

HUMANEVAL_LOG = os.path.join(LOG_DIR, "humaneval_results.jsonl")

BASELINE_SYSTEM = """You are a Python code generator.
Output ONLY raw Python code. No markdown. No backticks. No explanation.
The code must be complete and executable."""


def _strip_fences(code: str) -> str:
    if code.startswith("```"):
        lines = code.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        return "\n".join(lines).strip()
    return code.strip()


def run_baseline(problem: dict, api_key: str = None, model: str = None) -> dict:
    """Single LLM call, no retry loop, no critique."""
    from groq import Groq
    api_key = api_key or GROQ_API_KEY
    model = model or MODEL
    client = Groq(api_key=api_key)

    prompt = f"{problem['prompt']}\n\nWrite the complete Python code now:"
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": BASELINE_SYSTEM},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=1024,
            stream=False
        )
        code = response.choices[0].message.content or ""
        code = _strip_fences(code)
        test_code = code + "\n" + problem["test"]
        result = run_code(test_code)
        return {
            "id": problem["id"],
            "passed": result["success"] and "PASS" in result["output"],
            "code": code,
            "output": result["output"],
            "error": result["error"],
            "attempts": 1
        }
    except Exception as e:
        return {
            "id": problem["id"],
            "passed": False,
            "code": "",
            "output": "",
            "error": str(e),
            "attempts": 1
        }


def run_agent(problem: dict, api_key: str = None, model: str = None,
              max_retries: int = None, on_progress=None) -> dict:
    """Full generator loop with error fixing, up to max_retries."""
    from groq import Groq
    from generator import stream_generate
    api_key = api_key or GROQ_API_KEY
    model = model or MODEL
    max_retries = max_retries or MAX_RETRIES
    client = Groq(api_key=api_key)

    rewrite_instructions = ""
    last_code = ""
    last_error = ""

    for attempt in range(1, max_retries + 1):
        if on_progress:
            on_progress(attempt, max_retries, problem["entry_point"])

        code_tokens = []
        try:
            for token in stream_generate(
                task=problem["prompt"],
                rewrite_instructions=rewrite_instructions,
                api_key_override=api_key,
                model_override=model
            ):
                code_tokens.append(token)

            code = _strip_fences("".join(code_tokens))
            last_code = code
            test_code = code + "\n" + problem["test"]
            result = run_code(test_code)

            if result["success"] and "PASS" in result["output"]:
                return {
                    "id": problem["id"],
                    "passed": True,
                    "code": code,
                    "output": result["output"],
                    "error": "",
                    "attempts": attempt
                }
            else:
                last_error = result["error"] or result["output"]
                rewrite_instructions = f"Previous attempt failed:\n{last_error}\n\nFix this error."

        except Exception as e:
            last_error = str(e)
            rewrite_instructions = f"Previous attempt threw exception:\n{last_error}\n\nFix this."

    return {
        "id": problem["id"],
        "passed": False,
        "code": last_code,
        "output": "",
        "error": last_error,
        "attempts": max_retries
    }


def run_full_benchmark(
    problem_ids: list = None,
    api_key: str = None,
    model: str = None,
    max_retries: int = None,
    on_problem_start=None,
    on_problem_done=None
) -> dict:
    """
    Run full HumanEval benchmark for given problem IDs.
    Returns summary dict and logs results.
    """
    if problem_ids is None:
        problem_ids = [p["id"] for p in PROBLEMS]

    selected = [p for p in PROBLEMS if p["id"] in problem_ids]
    agent_results = []
    baseline_results = []

    for i, problem in enumerate(selected):
        if on_problem_start:
            on_problem_start(i + 1, len(selected), problem["entry_point"])

        agent_res = run_agent(problem, api_key=api_key, model=model, max_retries=max_retries)
        baseline_res = run_baseline(problem, api_key=api_key, model=model)

        agent_results.append({**agent_res, "difficulty": problem["difficulty"], "function": problem["entry_point"]})
        baseline_results.append({**baseline_res, "difficulty": problem["difficulty"], "function": problem["entry_point"]})

        if on_problem_done:
            on_problem_done(i + 1, len(selected), problem["entry_point"], agent_res["passed"], baseline_res["passed"])

    # Compute summary
    total = len(selected)
    agent_passed = sum(1 for r in agent_results if r["passed"])
    baseline_passed = sum(1 for r in baseline_results if r["passed"])
    agent_pass1 = round(agent_passed / total * 100, 1) if total else 0
    baseline_pass1 = round(baseline_passed / total * 100, 1) if total else 0
    improvement = round(agent_pass1 - baseline_pass1, 1)
    avg_attempts = round(sum(r["attempts"] for r in agent_results) / total, 2) if total else 0

    # By difficulty
    breakdown = {}
    for diff in ["easy", "medium", "hard"]:
        diff_agent = [r for r in agent_results if r["difficulty"] == diff]
        diff_base = [r for r in baseline_results if r["difficulty"] == diff]
        if diff_agent:
            breakdown[diff] = {
                "agent_pass": sum(1 for r in diff_agent if r["passed"]),
                "baseline_pass": sum(1 for r in diff_base if r["passed"]),
                "total": len(diff_agent)
            }

    summary = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "model": model or MODEL,
        "total_problems": total,
        "agent": {"pass1_pct": agent_pass1, "passed": agent_passed},
        "baseline": {"pass1_pct": baseline_pass1, "passed": baseline_passed},
        "improvement_pct": improvement,
        "avg_agent_attempts": avg_attempts,
        "by_difficulty": breakdown,
        "agent_results": agent_results,
        "baseline_results": baseline_results
    }

    # Log
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(HUMANEVAL_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(summary) + "\n")

    return summary


def load_past_runs() -> list:
    """Load all past HumanEval runs from log."""
    if not os.path.exists(HUMANEVAL_LOG):
        return []
    runs = []
    with open(HUMANEVAL_LOG, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    runs.append(json.loads(line))
                except Exception:
                    pass
    return runs
