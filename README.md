# Self-Improving Code Agent 🤖

A zero-cost, production-grade AI agent that generates Python code, critiques it for quality, benchmarks performance improvements, and learns from failures using vector memory.

**Stack:** Groq (Llama 3.3-70B) · ChromaDB · Sentence Transformers · Streamlit · Plotly · subprocess sandbox

---

## Architecture

```
Task Input
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 1 — Memory Lookup                                │
│  ChromaDB semantic search → inject past failure context │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 2 — Generator Agent                              │
│  Groq LLM → code → subprocess sandbox → auto-retry     │
│  On failure: store to ChromaDB vector memory            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 3 — Critique Agent                               │
│  LLM reviews for efficiency + correctness               │
│  APPROVED / REWRITE → generator rewrites → re-validate  │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  Phase 4 — Benchmark (if code was rewritten)            │
│  timeit (runtime) + tracemalloc (memory)                │
│  before vs after comparison with delta %                │
└─────────────────────────────────────────────────────────┘
                     │
                     ▼
             Final Code + Analytics
```

---

## Project Structure

```
self_improving_agent/
├── app.py                  # Streamlit UI (5 tabs)
├── main.py                 # CLI entry point
├── config.py               # All settings and constants
├── generator.py            # Generator agent with streaming
├── critique.py             # Critique agent with verdict parser
├── sandbox.py              # subprocess code execution sandbox
├── benchmark.py            # timeit + tracemalloc benchmarking
├── memory.py               # ChromaDB vector memory (CRUD + search)
├── evaluate.py             # HumanEval benchmark engine
├── humaneval_problems.py   # 20 benchmark problems (easy/medium/hard)
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your Groq API key

```bash
export GROQ_API_KEY="gsk_your_key_here"
```

Or paste it in the sidebar / Settings tab of the UI.

### 3a. Launch Streamlit UI

```bash
streamlit run app.py
```

### 3b. Use the CLI

```bash
python main.py "Write a function that finds all prime numbers up to n using the Sieve of Eratosthenes"

# Options:
python main.py "your task" --retries 5 --critique 3
python main.py "your task" --no-memory --no-benchmark
python main.py "your task" --model llama-3.1-8b-instant
```

---

## Features

### 🤖 Agent Tab
- **Task templates** — 5 prompt templates for different task types
- **Prompt enhancer** — LLM rewrites vague tasks into precise specs
- **Streaming output** — watch code generate token by token
- **Attempt timeline** — visual Plotly chart of each attempt's result
- **Code diff viewer** — side-by-side HTML diff (original vs after critique)
- **Download button** — export final `.py` file with headers
- **Resume sentence generator** — copy benchmark results as bullet points

### 📐 HumanEval Tab
- 20 curated problems: 8 easy / 8 medium / 4 hard
- Runs **Agent** (retry loop) vs **Baseline** (single shot)
- Reports pass@1 %, per-difficulty breakdown, per-problem table
- Trend chart across multiple runs
- Export results as CSV

### 📈 Analytics Tab
- Attempts-per-task line chart
- Cumulative success rate over time
- Critique rewrite impact bar chart
- Memory retrieval hit rate
- Export session JSON / benchmark CSV

### 🧠 Memory Explorer Tab
- Semantic search across all stored failures
- Paginated browser (10 per page, newest first)
- Delete individual entries or clear all
- Storage stats: total entries, disk size, oldest/newest timestamps

### ⚙️ Settings Tab
- LLM: model, temperature, max tokens
- Agent: retries, critique rounds, sandbox timeout, benchmark runs
- Feature toggles: critique, memory, benchmark, diff viewer, auto-enhance
- Memory: similarity threshold (0.0–1.0), top-k retrieval count
- Export / Import all settings as JSON

---

## Zero-Cost Stack

| Component | Service | Cost |
|-----------|---------|------|
| LLM inference | Groq free tier | Free |
| Vector memory | ChromaDB local | Free |
| Embeddings | sentence-transformers (local) | Free |
| Sandbox | Python subprocess | Free |
| UI | Streamlit | Free |

---

## CLI Flags

```
python main.py "<task>"
  --model         Model ID (default: llama-3.3-70b-versatile)
  --retries N     Max fix retries (default: 5)
  --critique N    Max critique rounds (default: 3)
  --no-memory     Disable vector memory
  --no-critique   Disable critique agent
  --no-benchmark  Disable benchmark
```

---

## Environment Variables

```bash
GROQ_API_KEY=gsk_...       # Required
```

All other settings are configurable in `config.py` or the Settings tab.

---

## Sample HumanEval Results

After a full benchmark run, a typical result looks like:

```
Agent pass@1:    85.0% (17/20)
Baseline pass@1: 60.0% (12/20)
Delta:          +25.0%
Avg attempts:    1.8
```

---

## Resume Bullet

> Built a Self-Improving Code Agent achieving **85% pass@1** on 20 HumanEval problems vs 60% baseline (+25% delta) using Groq Llama 3.3-70B with LangChain-style critique loop, subprocess sandboxing, ChromaDB vector memory, and timeit/tracemalloc benchmarking. Deployed with Streamlit; zero API cost.

---

## Roadmap

- [x] Week 1: Core agent + sandbox + Streamlit UI
- [x] Week 2: Critique agent + benchmark + memory + HumanEval
- [ ] Week 3: Multi-agent debate (Proposer vs Adversary)
- [ ] Week 4: Long-term memory with periodic pruning
- [ ] Week 5: GitHub Actions CI for automated benchmark regression

---

## Author

**Farhan Aaqil** — AI/ML Engineer  
GitHub: [github.com/FarhanAaqil](https://github.com/FarhanAaqil)  
LinkedIn: [linkedin.com/in/farhan-aaqil-4730432bb](https://linkedin.com/in/farhan-aaqil-4730432bb)
