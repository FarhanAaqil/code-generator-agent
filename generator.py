import json
import os
import datetime
from groq import Groq
from config import GROQ_API_KEY, MODEL, TEMPERATURE, MAX_TOKENS, MAX_RETRIES, LOG_DIR
from sandbox import run_code

ATTEMPT_LOG = os.path.join(LOG_DIR, "attempts.jsonl")

GENERATOR_SYSTEM_PROMPT = """You are a Python code generator. 
Output ONLY raw Python code. 
No markdown. No backticks. No explanation. No comments unless they are actual Python comments.
The code must be complete and executable as-is.
Do not use input() anywhere.
Print the result so it can be seen in stdout."""


def _log_attempt(record: dict):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(ATTEMPT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def build_generator_prompt(task: str, memory_context: str = "", rewrite_instructions: str = "") -> str:
    parts = []
    if memory_context:
        parts.append(memory_context)
        parts.append("---")
    if rewrite_instructions:
        parts.append(f"REWRITE INSTRUCTIONS (from code reviewer):\n{rewrite_instructions}")
        parts.append("---")
    parts.append(f"Task: {task}")
    parts.append("Write the Python code now:")
    return "\n\n".join(parts)


def stream_generate(
    task: str,
    memory_context: str = "",
    rewrite_instructions: str = "",
    api_key_override: str = None,
    model_override: str = None,
    temperature_override: float = None,
    max_tokens_override: int = None
):
    """
    Generator that yields code tokens as they stream.
    Usage: for token in stream_generate(task): ...
    """
    api_key = api_key_override or GROQ_API_KEY
    model = model_override or MODEL
    temperature = temperature_override if temperature_override is not None else TEMPERATURE
    max_tokens = max_tokens_override or MAX_TOKENS

    client = Groq(api_key=api_key)
    prompt = build_generator_prompt(task, memory_context, rewrite_instructions)

    stream = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": GENERATOR_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def run_generator_loop(
    task: str,
    memory_context: str = "",
    max_retries: int = None,
    api_key_override: str = None,
    model_override: str = None,
    temperature_override: float = None,
    max_tokens_override: int = None,
    on_token=None,
    on_attempt_start=None,
    on_attempt_result=None
) -> dict:
    """
    Full generator retry loop (for CLI / evaluate.py use).
    Callbacks: on_token(token), on_attempt_start(attempt, total),
               on_attempt_result(attempt, success, code, output, error)
    Returns {success, code, output, error, attempts}
    """
    if max_retries is None:
        max_retries = MAX_RETRIES

    last_error = ""
    last_code = ""
    rewrite_instructions = ""

    for attempt in range(1, max_retries + 1):
        if on_attempt_start:
            on_attempt_start(attempt, max_retries)

        code_tokens = []
        try:
            for token in stream_generate(
                task=task,
                memory_context=memory_context,
                rewrite_instructions=rewrite_instructions,
                api_key_override=api_key_override,
                model_override=model_override,
                temperature_override=temperature_override,
                max_tokens_override=max_tokens_override
            ):
                code_tokens.append(token)
                if on_token:
                    on_token(token)

            code = "".join(code_tokens).strip()
            # Strip accidental markdown fences
            if code.startswith("```"):
                lines = code.splitlines()
                lines = [l for l in lines if not l.strip().startswith("```")]
                code = "\n".join(lines).strip()

            last_code = code
            result = run_code(code)

            _log_attempt({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "phase": "generator",
                "task": task,
                "attempt": attempt,
                "code": code,
                "success": result["success"],
                "error": result["error"],
                "output": result["output"]
            })

            if on_attempt_result:
                on_attempt_result(attempt, result["success"], code, result["output"], result["error"])

            if result["success"]:
                return {
                    "success": True,
                    "code": code,
                    "output": result["output"],
                    "error": "",
                    "attempts": attempt
                }
            else:
                last_error = result["error"]
                rewrite_instructions = f"Previous attempt failed with error:\n{last_error}\n\nFix this error."

        except Exception as e:
            last_error = str(e)
            _log_attempt({
                "timestamp": datetime.datetime.utcnow().isoformat(),
                "phase": "generator",
                "task": task,
                "attempt": attempt,
                "code": "".join(code_tokens),
                "success": False,
                "error": last_error,
                "output": ""
            })
            if on_attempt_result:
                on_attempt_result(attempt, False, "".join(code_tokens), "", last_error)

    return {
        "success": False,
        "code": last_code,
        "output": "",
        "error": last_error,
        "attempts": max_retries
    }


def enhance_prompt(task: str, api_key_override: str = None, model_override: str = None) -> str:
    """Use LLM to enhance a vague task into a specific coding task."""
    api_key = api_key_override or GROQ_API_KEY
    model = model_override or MODEL
    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Rewrite this vague task into a specific Python coding task with "
                        "clear input/output requirements, example values, and edge cases to handle. "
                        "Return only the enhanced task description, no explanation.\n\n"
                        f"Task: {task}"
                    )
                }
            ],
            temperature=0.3,
            max_tokens=512,
            stream=False
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return task
