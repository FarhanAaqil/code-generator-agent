# Code Generator Agent

> A Groq-powered LLM agent that generates Python code from natural-language prompts, executes it in a subprocess sandbox, auto-repairs errors, and streams results — zero-cost stack.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20Llama%203.3%2070B-F55036?style=flat)](https://console.groq.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat)](LICENSE)

---

## What It Does

The Code Generator Agent takes a plain-English coding task, generates a Python solution using Llama 3.3 70B via the Groq API, runs it inside an isolated subprocess, and automatically feeds errors back to the LLM for repair — looping until the code executes successfully or the retry limit is reached.

**Example prompts:**
```
Write a function to reverse a linked list
Generate a FastAPI endpoint that accepts a JSON body and returns a summary
Write a Python script to scrape headlines from a news page
Implement quicksort and benchmark it against Python's sorted()
```

---

## Features

- **Natural-language → runnable Python** — Single prompt to working code
- **Subprocess sandbox** — Generated code runs in isolation; no access to the host environment
- **Auto-repair loop** — On runtime error, the error message and traceback are appended to the prompt and the LLM tries again (configurable max retries)
- **Zero cost** — Groq free tier + local execution, no paid APIs or cloud compute
- **Streaming output** — See tokens as they arrive from the Groq API

---

## Project Structure

```
code-generator-agent/
├── main.py              ← CLI entry point
├── agent.py             ← Core generation + repair loop
├── sandbox.py           ← Subprocess code runner
├── config.py            ← Model name, retry limit, prompt templates
├── requirements.txt
└── logs/
    └── attempts.jsonl   ← Every generation attempt logged
```

---

## Setup

### 1. Get a free Groq API key

Visit [console.groq.com](https://console.groq.com) — sign up and create a key. No credit card required.

### 2. Clone and install

```bash
git clone https://github.com/FarhanAaqil/code-generator-agent.git
cd code-generator-agent
pip install -r requirements.txt
```

### 3. Set your API key

```bash
# Linux / macOS
export GROQ_API_KEY="your_key_here"

# Windows (PowerShell)
$env:GROQ_API_KEY = "your_key_here"
```

Or create a `.env` file:

```env
GROQ_API_KEY=your_key_here
```

### 4. Run

```bash
python main.py
```

You'll be prompted to enter a coding task. The agent will generate code, run it, and display the output. If execution fails, it retries automatically.

---

## How It Works

```
User prompt
    │
    ▼
┌─────────────────┐
│  Groq API call  │  Llama 3.3 70B generates Python code
│  (agent.py)     │
└────────┬────────┘
         │ code string
         ▼
┌─────────────────┐
│    Sandbox      │  subprocess.run() with timeout
│  (sandbox.py)   │  captures stdout, stderr, exit code
└────────┬────────┘
         │
    ┌────┴────┐
    │ success │ → print output, log attempt, done
    │         │
    │  error  │ → append traceback to prompt, retry (max N times)
    └─────────┘
```

---

## Configuration

Edit `config.py` to adjust:

```python
MODEL = "llama-3.3-70b-versatile"   # Groq model
MAX_RETRIES = 3                      # Max auto-repair attempts
SANDBOX_TIMEOUT = 10                 # Seconds before subprocess is killed
LOG_PATH = "logs/attempts.jsonl"     # Attempt log file
```

---

## Zero-Cost Stack

| Component | Tool | Cost |
|---|---|---|
| LLM | Groq API — Llama 3.3 70B | Free tier |
| Code execution | Python `subprocess` | Free |
| Logging | JSONL file | Free |

---

## Related Projects

This agent is the foundation of [self-improving-agent](https://github.com/FarhanAaqil/self-improving-agent), which extends it with a Critique Agent, ChromaDB vector memory, HumanEval benchmarking, and a Streamlit UI.

---

## Author

**Farhan Aaqil Durrani**
B.Tech AI/ML — JPNCE Mahbubnagar, Telangana

[![GitHub](https://img.shields.io/badge/GitHub-FarhanAaqil-181717?style=flat&logo=github)](https://github.com/FarhanAaqil)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-farhan--aaqil-0A66C2?style=flat&logo=linkedin)](https://linkedin.com/in/farhan-aaqil-4730432bb)
