import subprocess
import tempfile
import os
from config import SANDBOX_TIMEOUT


def run_code(code: str, timeout: int = None) -> dict:
    """
    Execute Python code in a subprocess sandbox.
    Returns {success: bool, output: str, error: str}
    """
    if timeout is None:
        timeout = SANDBOX_TIMEOUT

    tmp = None
    try:
        # Write to temp file with explicit UTF-8 encoding (Windows safe)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            encoding="utf-8"
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name

        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )

        success = result.returncode == 0
        output = result.stdout.strip()
        error = result.stderr.strip()

        # Treat "PASS" in output as explicit success signal
        if "PASS" in output and result.returncode == 0:
            success = True

        return {"success": success, "output": output, "error": error}

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"Execution timed out after {timeout} seconds."
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e)
        }
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
