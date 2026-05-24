"""
Self-Improving Code Agent — Streamlit Application
Refactored for modern chat UX, stable session state, and production-grade patterns.
"""
import streamlit as st
import json
import os
import datetime
import difflib
import time
import plotly.graph_objects as go
import plotly.express as px

# ── page config MUST be first Streamlit call ────────────────────────────────
st.set_page_config(
    page_title="Self-Improving Code Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── local imports ────────────────────────────────────────────────────────────
from config import (
    GROQ_API_KEY, MODEL, AVAILABLE_MODELS, TEMPERATURE, MAX_TOKENS,
    MAX_RETRIES, MAX_CRITIQUE_ROUNDS, SANDBOX_TIMEOUT, BENCHMARK_RUNS,
    LOG_DIR, MEMORY_DIR
)
from sandbox import run_code
from generator import stream_generate, enhance_prompt, build_generator_prompt
from critique import critique_code
from benchmark import benchmark_code, compare, log_benchmark
import memory as mem_module
from memory import (
    store_failure, retrieve_similar_failures, build_memory_context,
    memory_stats, clear_memory, get_all_memories, get_oldest_newest_timestamps,
    delete_memory_by_id, CHROMADB_AVAILABLE
)
from evaluate import run_full_benchmark, load_past_runs
from humaneval_problems import PROBLEMS, EASY_IDS, DIFFICULTY_COLOR


# ════════════════════════════════════════════════════════════════════════════
# SESSION STATE — single initialisation, one source of truth per key
# ════════════════════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        # --- core task state (ONE source of truth) ---
        "task_input": "",           # current task text
        # "pending_task" is a transient key — set before rerun, consumed at top of render
        # "enhanced_task" is a transient key — set by enhancer, cleared on use/dismiss

        # --- session counters ---
        "tasks_run": 0,
        "successes": 0,
        "total_attempts": 0,
        "total_critique_rounds": 0,
        "memories_used": 0,
        "memories_stored": 0,

        # --- history ---
        "session_history": [],
        "benchmark_history": [],
        "memory_hit_history": [],
        "humaneval_result": None,

        # --- LLM / agent settings ---
        # NOTE: api_key is intentionally NOT pre-populated from GROQ_API_KEY here.
        # It is resolved at call time via _api_key() so the value is never
        # rendered visibly in the page outside of password inputs.
        "api_key": "",
        "model": MODEL,
        "temperature": TEMPERATURE,
        "max_tokens": MAX_TOKENS,
        "max_retries": MAX_RETRIES,
        "max_critique_rounds": MAX_CRITIQUE_ROUNDS,
        "sandbox_timeout": SANDBOX_TIMEOUT,
        "benchmark_runs": BENCHMARK_RUNS,

        # --- feature toggles ---
        "enable_critique": True,
        "enable_memory": CHROMADB_AVAILABLE,
        "enable_benchmark": True,
        "show_diff": True,
        "auto_enhance": False,

        # --- memory settings ---
        "mem_threshold": 0.3,
        "mem_top_k": 3,

        # --- misc ---
        "mem_page": 1,
        "auto_run": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ════════════════════════════════════════════════════════════════════════════
# PENDING-UPDATE PATTERN
# Any code that needs to update task_input BEFORE a widget is rendered must
# set st.session_state["pending_task"] and call st.rerun().
# This block runs once per render cycle, before any widget reads task_input.
# ════════════════════════════════════════════════════════════════════════════
if "pending_task" in st.session_state:
    st.session_state["task_input"] = st.session_state.pop("pending_task")


# ════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _api_key() -> str:
    """Return the active API key: session override → env fallback. Never displayed."""
    return st.session_state.api_key.strip() or GROQ_API_KEY


def _save_session():
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = os.path.join(LOG_DIR, f"session_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "tasks_run": st.session_state.tasks_run,
            "successes": st.session_state.successes,
            "session_history": st.session_state.session_history,
        }, f, indent=2)


def _load_sessions():
    sessions = []
    if not os.path.exists(LOG_DIR):
        return sessions
    for fname in sorted(os.listdir(LOG_DIR), reverse=True):
        if fname.startswith("session_") and fname.endswith(".json"):
            try:
                with open(os.path.join(LOG_DIR, fname), "r", encoding="utf-8") as f:
                    sessions.append(json.load(f))
            except Exception:
                pass
    return sessions[:5]


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _diff_html(before: str, after: str, label_before: str = "Original", label_after: str = "After Critique") -> str:
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    left_html, right_html = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ln, (l, r) in enumerate(zip(before_lines[i1:i2], after_lines[j1:j2])):
                n = i1 + ln + 1
                left_html.append(f'<tr><td class="ln">{n}</td><td class="code">{_esc(l)}</td></tr>')
                right_html.append(f'<tr><td class="ln">{j1+ln+1}</td><td class="code">{_esc(r)}</td></tr>')
        elif tag == "replace":
            for ln, l in enumerate(before_lines[i1:i2]):
                left_html.append(f'<tr class="del"><td class="ln">{i1+ln+1}</td><td class="code">{_esc(l)}</td></tr>')
            for ln, r in enumerate(after_lines[j1:j2]):
                right_html.append(f'<tr class="add"><td class="ln">{j1+ln+1}</td><td class="code">{_esc(r)}</td></tr>')
        elif tag == "delete":
            for ln, l in enumerate(before_lines[i1:i2]):
                left_html.append(f'<tr class="del"><td class="ln">{i1+ln+1}</td><td class="code">{_esc(l)}</td></tr>')
        elif tag == "insert":
            for ln, r in enumerate(after_lines[j1:j2]):
                right_html.append(f'<tr class="add"><td class="ln">{j1+ln+1}</td><td class="code">{_esc(r)}</td></tr>')

    return f"""
<style>
.diff-wrap {{display:flex;gap:12px;font-family:monospace;font-size:12px;overflow-x:auto}}
.diff-pane {{flex:1;min-width:0}}
.diff-pane h4 {{margin:0 0 6px;color:#ccc;font-size:13px}}
.diff-pane table {{border-collapse:collapse;width:100%}}
.diff-pane td {{padding:1px 6px;white-space:pre}}
.ln {{color:#555;min-width:30px;text-align:right;user-select:none;border-right:1px solid #333}}
.code {{width:100%}}
tr.del {{background:#4a1515}}
tr.add {{background:#0f3520}}
</style>
<div class="diff-wrap">
  <div class="diff-pane"><h4>{label_before}</h4><table>{"".join(left_html)}</table></div>
  <div class="diff-pane"><h4>{label_after}</h4><table>{"".join(right_html)}</table></div>
</div>"""


def _auto_scroll():
    """Inject JS that smoothly scrolls the page to the bottom after each update."""
    st.components.v1.html(
        "<script>window.parent.document.querySelector('section.main').scrollTo("
        "{top: window.parent.document.querySelector('section.main').scrollHeight, behavior: 'smooth'});"
        "</script>",
        height=0,
    )


def _strip_fences(code: str) -> str:
    """Remove markdown code fences from LLM output."""
    code = code.strip()
    if code.startswith("```"):
        lines = code.splitlines()
        lines = [l for l in lines if not l.strip().startswith("```")]
        code = "\n".join(lines).strip()
    return code


# ════════════════════════════════════════════════════════════════════════════
# TASK TEMPLATES & EXAMPLES
# ════════════════════════════════════════════════════════════════════════════
TASK_TEMPLATES = {
    "General Python": "Write a Python function that [describe what it should do]. It should accept [inputs] and return [outputs].",
    "Algorithm": "Implement the [algorithm name] algorithm in Python. Given [input description], return [output description]. Handle edge cases: [edge cases].",
    "Data Processing": "Write Python code that reads a list of [data type] and [processes/filters/transforms] it. Input: [example]. Output: [example output].",
    "String Manipulation": "Write a Python function that takes a string and [describe transformation]. Example: input='[example]' → output='[example output]'.",
    "Math/Statistics": "Write Python code to compute [mathematical concept] given [inputs]. Return [output format]. Example: input=[values] → output=[result].",
}

EXAMPLE_TASKS = [
    "Write a function that finds all prime numbers up to n using the Sieve of Eratosthenes",
    "Implement binary search on a sorted list and return the index or -1",
    "Write a function that groups a list of integers by whether they are even or odd",
    "Create a function that converts Roman numerals to integers",
    "Write a function that returns the nth Fibonacci number using dynamic programming",
    "Implement a stack with push, pop, peek, and is_empty methods",
]


# ════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS — ChatGPT/Claude-style chat feel
# ════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
/* ── chat input stays at bottom, full width ── */
[data-testid="stChatInput"] {
    position: sticky;
    bottom: 0;
    z-index: 100;
    background: var(--background-color);
    padding: 8px 0 4px;
    border-top: 1px solid rgba(255,255,255,0.07);
}

/* ── slim top header ── */
h1 { margin-bottom: 0 !important; }

/* ── task badge pill ── */
.task-badge {
    display: inline-block;
    background: rgba(99,179,237,0.15);
    border: 1px solid rgba(99,179,237,0.3);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 13px;
    color: #63b3ed;
    margin-bottom: 12px;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* ── phase containers — subtle left accent ── */
[data-testid="stContainer"] > div {
    border-radius: 8px;
}

/* ── enhanced prompt box ── */
.enhanced-box {
    background: rgba(72,187,120,0.08);
    border: 1px solid rgba(72,187,120,0.3);
    border-radius: 10px;
    padding: 14px 18px;
    margin: 8px 0 12px;
}

/* ── sidebar stat metric compact ── */
[data-testid="stMetric"] label { font-size: 12px !important; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🤖 Code Agent")
    st.caption(f"Model: `{st.session_state.model}`")
    st.divider()

    # ── Model ────────────────────────────────────────────────────────────────
    def _on_model_change():
        st.session_state["model"] = st.session_state["_sb_model_widget"]

    st.selectbox(
        "Model",
        AVAILABLE_MODELS,
        index=AVAILABLE_MODELS.index(st.session_state.model),
        key="_sb_model_widget",
        on_change=_on_model_change,
    )

    st.divider()

    # ── Quick controls ────────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.max_retries = st.number_input(
            "Fix retries", 1, 10, st.session_state.max_retries, key="_sb_retries"
        )
    with col2:
        st.session_state.max_critique_rounds = st.number_input(
            "Critique rounds", 1, 5, st.session_state.max_critique_rounds, key="_sb_critique"
        )

    st.divider()

    # ── Feature toggles ───────────────────────────────────────────────────────
    st.markdown("**Features**")
    st.session_state.enable_critique = st.toggle(
        "🔍 Critique Agent", value=st.session_state.enable_critique, key="_sb_crit"
    )
    mem_label = "🧠 Vector Memory" if CHROMADB_AVAILABLE else "🧠 Memory (install chromadb)"
    st.session_state.enable_memory = st.toggle(
        mem_label, value=st.session_state.enable_memory,
        disabled=not CHROMADB_AVAILABLE, key="_sb_mem"
    )
    st.session_state.enable_benchmark = st.toggle(
        "📊 Benchmark", value=st.session_state.enable_benchmark, key="_sb_bench"
    )
    if not CHROMADB_AVAILABLE:
        st.warning("Install chromadb:\n`pip install chromadb sentence-transformers`")

    st.divider()

    # ── Session stats ─────────────────────────────────────────────────────────
    st.markdown("**Session Stats**")
    total_t = st.session_state.tasks_run
    suc_t = st.session_state.successes
    st.metric("Tasks run", total_t)
    col_a, col_b = st.columns(2)
    col_a.metric("Success rate", f"{round(suc_t/total_t*100)}%" if total_t else "—")
    col_b.metric("Avg attempts", f"{st.session_state.total_attempts/total_t:.1f}" if total_t else "—")

    if CHROMADB_AVAILABLE:
        stats = memory_stats()
        col_m1, col_m2 = st.columns([2, 1])
        col_m1.metric("Memories stored", stats["total_failures_stored"])
        if col_m2.button("🗑", help="Clear all memories"):
            clear_memory()
            st.toast("Memory cleared.")
            st.rerun()

    st.divider()

    # ── Previous sessions ─────────────────────────────────────────────────────
    with st.expander("📂 Load previous session"):
        sessions = _load_sessions()
        if sessions:
            for s in sessions:
                ts = s.get("timestamp", "?")
                tasks = s.get("tasks_run", 0)
                if st.button(f"{ts} — {tasks} tasks", key=f"sess_{ts}"):
                    st.session_state.session_history = s.get("session_history", [])
                    st.session_state.tasks_run = s.get("tasks_run", 0)
                    st.session_state.successes = s.get("successes", 0)
                    st.toast("Session loaded.")
                    st.rerun()
        else:
            st.caption("No saved sessions.")

    if st.button("🔄 Clear session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# CHAT INPUT — bottom-fixed, Enter-to-send (st.chat_input)
# This is declared BEFORE the tabs so Streamlit renders it anchored to
# the bottom of the viewport across all tab views.
# ════════════════════════════════════════════════════════════════════════════
chat_prompt = st.chat_input("Describe your Python coding task… (Enter to send)")

if chat_prompt and chat_prompt.strip():
    st.session_state["pending_task"] = chat_prompt.strip()
    st.session_state["auto_run"] = True
    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# MAIN TABS
# ════════════════════════════════════════════════════════════════════════════
tab_agent, tab_humaneval, tab_analytics, tab_memory, tab_settings = st.tabs([
    "🤖 Agent", "📐 HumanEval", "📈 Analytics", "🧠 Memory Explorer", "⚙️ Settings"
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — AGENT
# ════════════════════════════════════════════════════════════════════════════
with tab_agent:
    st.subheader("Agent Task Runner")

    # ── Task input area ───────────────────────────────────────────────────────
    # Template selector — sets pending_task (safe, happens before widget render below)
    template_sel = st.selectbox(
        "Task template", ["(none)"] + list(TASK_TEMPLATES.keys()), key="tpl_sel"
    )
    if template_sel != "(none)":
        tpl_text = TASK_TEMPLATES[template_sel]
        if tpl_text != st.session_state.task_input:
            st.session_state["pending_task"] = tpl_text
            # Don't auto-run templates — they contain placeholder text the user should edit first
            st.rerun()

    # Example tasks expander
    with st.expander("💡 Example tasks"):
        for ex in EXAMPLE_TASKS:
            if st.button(ex, key=f"ex_{ex[:30]}"):
                st.session_state["pending_task"] = ex
                st.session_state["auto_run"] = True
                st.rerun()

    # Show current task (read-only display + clear)
    col_task, col_clear = st.columns([5, 1])
    with col_task:
        if st.session_state.task_input:
            st.markdown(
                f'<div class="task-badge">📝 {st.session_state.task_input[:120]}'
                f'{"…" if len(st.session_state.task_input) > 120 else ""}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("No task entered yet — use the chat input below or choose a template above.")
    with col_clear:
        if st.button("✕ Clear", key="clear_btn", help="Clear current task"):
            st.session_state["task_input"] = ""
            st.session_state.pop("enhanced_task", None)
            st.rerun()

    # ── Enhance Prompt ────────────────────────────────────────────────────────
    # Rendered as a collapsible section to avoid crowding the main flow.
    with st.expander("✨ Enhance my prompt", expanded=bool(st.session_state.get("enhanced_task"))):
        if not st.session_state.task_input.strip():
            st.info("Enter a task first (use the chat input at the bottom).")
        else:
            if st.button("✨ Enhance with AI", key="enhance_btn"):
                with st.spinner("Enhancing prompt…"):
                    try:
                        enhanced = enhance_prompt(
                            st.session_state.task_input,
                            _api_key(),
                            st.session_state.model,
                        )
                        # Robustly validate the response
                        if enhanced and isinstance(enhanced, str) and enhanced.strip():
                            st.session_state["enhanced_task"] = enhanced.strip()
                        else:
                            st.error("Enhancer returned an empty response. Try again.")
                    except Exception as e:
                        st.error(f"Enhancement failed: {e}")

        # Display enhanced result (if present)
        if st.session_state.get("enhanced_task"):
            st.markdown(
                f'<div class="enhanced-box"><strong>Enhanced version:</strong><br><br>'
                f'{_esc(st.session_state["enhanced_task"])}</div>',
                unsafe_allow_html=True,
            )
            col_use, col_dismiss = st.columns(2)
            if col_use.button("✅ Use this version", key="use_enhanced"):
                st.session_state["pending_task"] = st.session_state.pop("enhanced_task")
                st.session_state["auto_run"] = True
                st.rerun()
            if col_dismiss.button("✖ Dismiss", key="dismiss_enhanced"):
                st.session_state.pop("enhanced_task", None)
                st.rerun()

    st.divider()

    # ── Trigger detection — chat input / example task / "Use this version" ───
    run_clicked = st.session_state.pop("auto_run", False)

    if not st.session_state.task_input.strip() and not run_clicked:
        st.info("⬇ Type your task in the chat bar at the bottom and press Enter.")

    # ════════════════════════════════════════════════════════════════════════
    # EXECUTION PIPELINE
    # ════════════════════════════════════════════════════════════════════════
    if run_clicked and st.session_state.task_input.strip():
        task = st.session_state["task_input"]  # capture snapshot for this run

        # ── auto-enhance if enabled ────────────────────────────────────────
        if st.session_state.auto_enhance:
            with st.spinner("Auto-enhancing prompt…"):
                try:
                    enhanced = enhance_prompt(task, _api_key(), st.session_state.model)
                    if enhanced and enhanced.strip():
                        task = enhanced.strip()
                        st.session_state["task_input"] = task
                        st.toast("Prompt auto-enhanced.")
                except Exception:
                    pass  # silently fall back to original task

        # Tracking vars (local — not session state, avoids stale-state bugs)
        gen_attempts = 0
        critique_rounds_done = 0
        memories_used = 0
        original_code = None
        final_code = None
        working_output = ""
        run_success = False
        attempt_timeline = []
        critique_happened = False
        before_bench = None
        after_bench = None

        # ── Phase 1: Memory Lookup ─────────────────────────────────────────
        memory_context = ""
        if st.session_state.enable_memory and CHROMADB_AVAILABLE:
            with st.container(border=True):
                st.subheader("Phase 1 — 🧠 Memory Lookup")
                with st.spinner("Searching vector memory for similar failures…"):
                    failures = retrieve_similar_failures(task, top_k=st.session_state.mem_top_k)

                if failures:
                    st.info(f"Found **{len(failures)}** similar past failure(s):")
                    for f in failures:
                        with st.expander(f"[{f['similarity']:.2f}] {f['task'][:70]}…", expanded=False):
                            st.markdown(f"**Similarity:** `{f['similarity']:.2f}`")
                            st.markdown(f"**Task:** {f['task']}")
                            st.code(f["code"], language="python")
                            st.error(f"**Error:** {f['error']}")
                    memory_context = build_memory_context(task, top_k=st.session_state.mem_top_k)
                    memories_used = len(failures)
                    st.caption(f"💉 Injecting {memories_used} memory context(s) into generator prompt.")
                else:
                    st.success("✅ No similar failures found — starting fresh.")

        # ── Phase 2: Generator ────────────────────────────────────────────
        with st.container(border=True):
            st.subheader("Phase 2 — ⚙️ Generator Agent")
            progress_bar = st.progress(0, text="Waiting…")
            max_ret = st.session_state.max_retries
            rewrite_instructions = ""

            for attempt in range(1, max_ret + 1):
                progress_bar.progress(attempt / max_ret, text=f"Attempt {attempt}/{max_ret}")

                with st.container(border=True):
                    mem_badge = f"🧠 +{memories_used} memories" if memories_used > 0 else ""
                    st.markdown(f"**Attempt {attempt}** {mem_badge}")
                    status_ph = st.empty()
                    status_ph.info("⏳ Generating…")
                    code_ph = st.empty()
                    tokens = []

                    try:
                        for token in stream_generate(
                            task=task,
                            memory_context=memory_context,
                            rewrite_instructions=rewrite_instructions,
                            api_key_override=_api_key(),
                            model_override=st.session_state.model,
                            temperature_override=st.session_state.temperature,
                            max_tokens_override=st.session_state.max_tokens,
                        ):
                            tokens.append(token)
                            code_ph.code("".join(tokens), language="python")
                            # Auto-scroll while streaming
                            if len(tokens) % 30 == 0:
                                _auto_scroll()

                        code = _strip_fences("".join(tokens))
                        status_ph.warning("⏳ Running in sandbox…")
                        result = run_code(code, timeout=st.session_state.sandbox_timeout)
                        gen_attempts = attempt

                        if result["success"]:
                            status_ph.success(f"✅ PASSED — attempt {attempt}")
                            st.caption(f"Output: `{result['output'][:100]}`")
                            attempt_timeline.append({"attempt": attempt, "status": "passed", "critique_rewrite": False})
                            final_code = code
                            original_code = code
                            working_output = result["output"]
                            run_success = True
                            _auto_scroll()
                            break
                        else:
                            status_ph.error(f"❌ FAILED — attempt {attempt}")
                            with st.expander("Traceback", expanded=False):
                                st.code(result["error"], language="text")
                            attempt_timeline.append({"attempt": attempt, "status": "error", "critique_rewrite": False})
                            if st.session_state.enable_memory and CHROMADB_AVAILABLE:
                                store_failure(task, code, result["error"])
                                st.caption("📥 Stored failure in memory.")
                                st.session_state.memories_stored += 1
                            rewrite_instructions = f"Previous attempt failed:\n{result['error']}\nFix this."

                    except Exception as e:
                        status_ph.error(f"❌ LLM error: {str(e)[:120]}")
                        attempt_timeline.append({"attempt": attempt, "status": "error", "critique_rewrite": False})
                        rewrite_instructions = f"Previous attempt threw: {str(e)}\nFix this."

            if not run_success:
                st.error("Generator failed after all retries.")
                progress_bar.progress(1.0, text="Failed")

        # ── Phase 3: Critique ─────────────────────────────────────────────
        if run_success and st.session_state.enable_critique:
            st.divider()
            with st.container(border=True):
                st.subheader("Phase 3 — 🔍 Critique Agent")
                max_crit = st.session_state.max_critique_rounds

                for cround in range(1, max_crit + 1):
                    with st.container(border=True):
                        st.markdown(f"**Critique Round {cround}/{max_crit}**")
                        with st.expander("Code under review", expanded=(cround == 1)):
                            st.code(final_code, language="python")

                        crit_status = st.empty()
                        crit_status.info("⏳ Critique agent reviewing…")

                        with st.spinner("Analyzing code…"):
                            verdict = critique_code(
                                task=task,
                                code=final_code,
                                output=working_output,
                                api_key_override=_api_key(),
                                model_override=st.session_state.model,
                            )

                        critique_rounds_done = cround

                        if verdict["verdict"] == "APPROVED":
                            crit_status.success("✅ APPROVED — code passed critique review.")
                            _auto_scroll()
                            break

                        elif verdict["verdict"] == "REWRITE":
                            crit_status.warning("⚠️ REWRITE requested")
                            critique_happened = True
                            for issue in verdict["issues"]:
                                st.warning(f"⚠ {issue}")
                            st.info(f"**Rewrite instructions:** {verdict['instructions']}")

                            st.markdown("**Rewriting…**")
                            rw_ph = st.empty()
                            rw_tokens = []

                            try:
                                for token in stream_generate(
                                    task=task,
                                    rewrite_instructions=verdict["instructions"],
                                    api_key_override=_api_key(),
                                    model_override=st.session_state.model,
                                    temperature_override=st.session_state.temperature,
                                    max_tokens_override=st.session_state.max_tokens,
                                ):
                                    rw_tokens.append(token)
                                    rw_ph.code("".join(rw_tokens), language="python")
                                    if len(rw_tokens) % 30 == 0:
                                        _auto_scroll()

                                rw_code = _strip_fences("".join(rw_tokens))
                                rw_result = run_code(rw_code, timeout=st.session_state.sandbox_timeout)

                                if rw_result["success"]:
                                    final_code = rw_code
                                    working_output = rw_result["output"]
                                    st.success("✅ Rewrite passed sandbox validation.")
                                    attempt_timeline.append({
                                        "attempt": gen_attempts + cround,
                                        "status": "rewrite",
                                        "critique_rewrite": True,
                                    })
                                    _auto_scroll()
                                else:
                                    st.warning("⚠️ Rewrite failed sandbox — keeping previous working version.")
                                    with st.expander("Rewrite error", expanded=False):
                                        st.code(rw_result["error"], language="text")
                                    break

                            except Exception as e:
                                st.error(f"Rewrite LLM error: {e}")
                                break
                        else:
                            crit_status.error(f"Critique error: {verdict['issues']}")
                            break

        # ── Phase 4: Benchmark ────────────────────────────────────────────
        if run_success and st.session_state.enable_benchmark and critique_happened and original_code != final_code:
            st.divider()
            with st.container(border=True):
                st.subheader("Phase 4 — 📊 Benchmark")
                with st.spinner("Benchmarking original code…"):
                    before_bench = benchmark_code(original_code, runs=st.session_state.benchmark_runs)
                with st.spinner("Benchmarking optimized code…"):
                    after_bench = benchmark_code(final_code, runs=st.session_state.benchmark_runs)

                if before_bench["success"] and after_bench["success"]:
                    comp = compare(before_bench, after_bench)
                    log_benchmark(task, before_bench, after_bench, comp)
                    st.session_state.benchmark_history.append({
                        "task": task[:60],
                        "before": before_bench,
                        "after": after_bench,
                        "comparison": comp,
                    })
                    col_b1, col_b2, col_b3 = st.columns(3)
                    col_b1.metric("Avg runtime (Before)", f"{before_bench['avg_ms']:.2f} ms")
                    col_b2.metric(
                        "Avg runtime (After)",
                        f"{after_bench['avg_ms']:.2f} ms",
                        delta=f"{comp.get('runtime_delta_pct', 0):.1f}%",
                        delta_color="inverse",
                    )
                    col_b3.metric(
                        "Peak memory (After)",
                        f"{after_bench['peak_kb']:.1f} KB",
                        delta=f"{comp.get('memory_delta_pct', 0):.1f}%",
                        delta_color="inverse",
                    )
                    if comp.get("improved"):
                        st.success("✅ Critique improved the code.")
                    else:
                        st.info("ℹ️ No measurable performance gain from rewrite.")
                else:
                    st.warning("⚠️ Benchmark could not run — skipping.")

        # ── Final Result ──────────────────────────────────────────────────
        if run_success and final_code:
            st.divider()
            with st.container(border=True):
                st.subheader("🎉 Final Result")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Generator attempts", gen_attempts)
                c2.metric("Critique rounds", critique_rounds_done)
                c3.metric("Memories used", memories_used)
                c4.metric("Status", "✅ Success")

                if st.session_state.show_diff and critique_happened and original_code != final_code:
                    st.markdown("#### Code Diff (Original vs After Critique)")
                    st.markdown(
                        _diff_html(
                            original_code, final_code,
                            f"Original (attempt {gen_attempts})",
                            f"After critique (round {critique_rounds_done})",
                        ),
                        unsafe_allow_html=True,
                    )
                else:
                    st.code(final_code, language="python")

                # Attempt timeline chart
                if attempt_timeline:
                    st.markdown("#### Attempt Timeline")
                    colors = {"passed": "green", "error": "red", "rewrite": "orange"}
                    labels = {"passed": "✅ Passed", "error": "❌ Error", "rewrite": "⚠️ Rewrite"}
                    fig_tl = go.Figure()
                    fig_tl.add_trace(go.Scatter(
                        x=[a["attempt"] for a in attempt_timeline],
                        y=[1] * len(attempt_timeline),
                        mode="markers+text",
                        marker=dict(size=24, color=[colors.get(a["status"], "gray") for a in attempt_timeline]),
                        text=[labels.get(a["status"], a["status"]) for a in attempt_timeline],
                        textposition="top center",
                    ))
                    fig_tl.update_layout(
                        height=150, showlegend=False,
                        yaxis=dict(visible=False, range=[0.5, 1.8]),
                        xaxis=dict(title="Attempt", tickmode="linear"),
                        margin=dict(l=0, r=0, t=10, b=30),
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig_tl, use_container_width=True)

                # Action buttons
                ts_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
                download_code = (
                    f'"""\nGenerated by Self-Improving Code Agent\n'
                    f'Task: {task}\nTimestamp: {ts_now}\nModel: {st.session_state.model}\n"""\n\n'
                    f'{final_code}\n\nif __name__ == "__main__":\n    pass  # Add test calls here\n'
                )
                share_md = (
                    f"## Task\n{task}\n\n## Solution\n```python\n{final_code}\n```\n\n"
                    f"## Performance\n- Solved in {gen_attempts} attempt(s)\n"
                    f"- Critique rounds: {critique_rounds_done}\n"
                    f"- Generated by Self-Improving Code Agent\n"
                )
                col_dl, col_cp, col_readme = st.columns(3)
                col_dl.download_button(
                    "⬇ Download .py", data=download_code,
                    file_name=f"agent_output_{ts_now}.py", mime="text/x-python",
                )
                col_cp.download_button(
                    "📋 Shareable summary", data=share_md,
                    file_name="agent_summary.md", mime="text/markdown",
                )
                if col_readme.button("📝 README snippet"):
                    st.code(
                        f"- **{task[:60]}** — Solved in {gen_attempts} attempt(s) "
                        f"with {critique_rounds_done} critique round(s).",
                        language="text",
                    )

            # ── Update session counters ────────────────────────────────────
            st.session_state.tasks_run += 1
            st.session_state.successes += 1
            st.session_state.total_attempts += gen_attempts
            st.session_state.total_critique_rounds += critique_rounds_done
            st.session_state.memories_used += memories_used
            st.session_state.memory_hit_history.append(memories_used > 0)
            st.session_state.session_history.append({
                "task": task[:80],
                "success": True,
                "attempts": gen_attempts,
                "critique_rounds": critique_rounds_done,
                "memories_used": memories_used,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            _save_session()
            _auto_scroll()

        elif run_clicked and not run_success:
            # Counters for failed runs
            st.session_state.tasks_run += 1
            st.session_state.total_attempts += gen_attempts
            st.session_state.memory_hit_history.append(memories_used > 0)
            st.session_state.session_history.append({
                "task": task[:80],
                "success": False,
                "attempts": gen_attempts,
                "critique_rounds": critique_rounds_done,
                "memories_used": memories_used,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            _save_session()
            st.error("❌ Task failed after all retries.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — HUMANEVAL
# ════════════════════════════════════════════════════════════════════════════
with tab_humaneval:
    st.subheader("HumanEval Benchmark Runner")

    with st.expander("📋 All 20 Problems", expanded=False):
        rows = [{"ID": p["id"], "Function": p["entry_point"], "Difficulty": p["difficulty"].upper()} for p in PROBLEMS]
        st.dataframe(rows, use_container_width=True)

    quick_run = st.checkbox("⚡ Quick run — easy problems only (8 problems)", value=False)
    run_eval_btn = st.button("▶ Run Full Benchmark", type="primary", key="run_eval")

    if run_eval_btn:
        problem_ids = EASY_IDS if quick_run else [p["id"] for p in PROBLEMS]
        total_probs = len(problem_ids)
        progress = st.progress(0, text="Starting benchmark…")
        status_area = st.empty()

        def on_problem_start(i, total, name):
            progress.progress(i / total, text=f"Problem {i}/{total} — {name}")
            status_area.info(f"Running: **{name}** ({i}/{total})")

        def on_problem_done(i, total, name, agent_pass, base_pass):
            a = "✅" if agent_pass else "❌"
            b = "✅" if base_pass else "❌"
            status_area.success(f"Done {i}/{total}: **{name}** — Agent: {a} | Baseline: {b}")

        with st.spinner("Running benchmark — this may take a few minutes…"):
            result = run_full_benchmark(
                problem_ids=problem_ids,
                api_key=_api_key(),
                model=st.session_state.model,
                max_retries=st.session_state.max_retries,
                on_problem_start=on_problem_start,
                on_problem_done=on_problem_done,
            )

        st.session_state.humaneval_result = result
        progress.progress(1.0, text="Complete!")
        status_area.empty()

    if st.session_state.humaneval_result:
        res = st.session_state.humaneval_result
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Agent pass@1", f"{res['agent']['pass1_pct']}%")
        c2.metric("Baseline pass@1", f"{res['baseline']['pass1_pct']}%")
        c3.metric("Delta", f"{res['improvement_pct']:+.1f}%",
                  delta_color="normal" if res["improvement_pct"] >= 0 else "inverse")
        c4.metric("Avg agent attempts", res["avg_agent_attempts"])

        fig_bar = go.Figure(data=[
            go.Bar(name="Agent", x=["Overall"], y=[res["agent"]["pass1_pct"]], marker_color="#4CAF50"),
            go.Bar(name="Baseline", x=["Overall"], y=[res["baseline"]["pass1_pct"]], marker_color="#2196F3"),
        ])
        fig_bar.update_layout(title="Agent vs Baseline Pass Rate", barmode="group", height=280,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("#### By Difficulty")
        diff_cols = st.columns(3)
        for i, diff in enumerate(["easy", "medium", "hard"]):
            bd = res.get("by_difficulty", {}).get(diff)
            if bd:
                with diff_cols[i]:
                    with st.container(border=True):
                        st.markdown(f"**{diff.upper()}** ({bd['total']} problems)")
                        st.metric("Agent", f"{bd['agent_pass']}/{bd['total']}")
                        st.metric("Baseline", f"{bd['baseline_pass']}/{bd['total']}")

        st.markdown("#### Per-Problem Results")
        table_data = [{
            "ID": ar["id"],
            "Function": ar.get("function", ""),
            "Difficulty": ar.get("difficulty", "").upper(),
            "Agent": "✅" if ar["passed"] else "❌",
            "Baseline": "✅" if br["passed"] else "❌",
            "Attempts": ar["attempts"],
            "Agent Error": ar["error"][:60] if not ar["passed"] else "",
        } for ar, br in zip(res["agent_results"], res["baseline_results"])]
        st.dataframe(table_data, use_container_width=True)

        resume_line = (
            f"Built and benchmarked a Self-Improving Code Agent achieving "
            f"{res['agent']['pass1_pct']}% pass@1 on {res['total_problems']} HumanEval problems "
            f"vs {res['baseline']['pass1_pct']}% baseline (+{res['improvement_pct']}% delta) "
            f"using Groq Llama 3.3-70B with LangChain-style critique and vector memory."
        )
        st.info(f"📄 **Resume-ready sentence:**\n\n{resume_line}")
        st.download_button("📋 Copy", data=resume_line, file_name="resume_bullet.txt")

    past_runs = load_past_runs()
    if past_runs:
        with st.expander(f"📂 Previous Runs ({len(past_runs)} total)", expanded=False):
            for run in reversed(past_runs):
                ts = run.get("timestamp", "")[:19]
                agent_pct = run.get("agent", {}).get("pass1_pct", 0)
                baseline_pct = run.get("baseline", {}).get("pass1_pct", 0)
                st.markdown(f"**{ts}** — Agent: {agent_pct}% | Baseline: {baseline_pct}%")

            if len(past_runs) >= 3:
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(
                    x=[r.get("timestamp", "")[:10] for r in past_runs],
                    y=[r.get("agent", {}).get("pass1_pct", 0) for r in past_runs],
                    name="Agent", mode="lines+markers",
                ))
                fig_trend.add_trace(go.Scatter(
                    x=[r.get("timestamp", "")[:10] for r in past_runs],
                    y=[r.get("baseline", {}).get("pass1_pct", 0) for r in past_runs],
                    name="Baseline", mode="lines+markers",
                ))
                fig_trend.update_layout(title="Pass@1 Trend", yaxis_title="Pass@1 %", height=280,
                                         paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_trend, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — ANALYTICS
# ════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    st.subheader("Session Analytics")
    total = st.session_state.tasks_run
    suc = st.session_state.successes

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tasks run", total)
    c2.metric("Success rate", f"{round(suc/total*100)}%" if total else "—")
    c3.metric("Avg fix attempts", f"{st.session_state.total_attempts/total:.1f}" if total else "—")
    c4.metric("Avg critique rounds", f"{st.session_state.total_critique_rounds/total:.1f}" if total else "—")
    c5.metric("Memories stored", st.session_state.memories_stored)

    if not st.session_state.session_history:
        st.info("Run some tasks in the Agent tab to see analytics here.")
    else:
        hist = st.session_state.session_history

        fig_att = go.Figure()
        fig_att.add_trace(go.Scatter(
            x=list(range(1, len(hist) + 1)),
            y=[h["attempts"] for h in hist],
            mode="lines+markers", name="Attempts", line=dict(color="#4CAF50"),
        ))
        fig_att.update_layout(title="Generator Attempts per Task", xaxis_title="Task #",
                               yaxis_title="Attempts", height=250,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_att, use_container_width=True)

        cumulative_success = [
            round(sum(1 for x in hist[:i] if x["success"]) / i * 100, 1)
            for i in range(1, len(hist) + 1)
        ]
        fig_sr = go.Figure()
        fig_sr.add_trace(go.Scatter(
            x=list(range(1, len(hist) + 1)), y=cumulative_success,
            fill="tozeroy", name="Success Rate %", line=dict(color="#2196F3"),
        ))
        fig_sr.update_layout(title="Cumulative Success Rate", xaxis_title="Task #",
                              yaxis_title="Success %", height=250, yaxis_range=[0, 110],
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_sr, use_container_width=True)

        if st.session_state.benchmark_history:
            improvements = [1 if b["comparison"].get("improved") else 0 for b in st.session_state.benchmark_history]
            fig_ci = go.Figure(go.Bar(
                x=["Improved", "No gain"],
                y=[sum(improvements), len(improvements) - sum(improvements)],
                marker_color=["#4CAF50", "#F44336"],
            ))
            fig_ci.update_layout(title="Critique Rewrite Impact", height=220,
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_ci, use_container_width=True)

        if st.session_state.memory_hit_history:
            hits = sum(st.session_state.memory_hit_history)
            total_tasks = len(st.session_state.memory_hit_history)
            st.metric("Memory retrieval hit rate",
                      f"{round(hits/total_tasks*100)}%" if total_tasks else "—",
                      help="% of tasks where relevant past failures were found")

        if st.session_state.humaneval_result:
            res = st.session_state.humaneval_result
            diffs = list(res.get("by_difficulty", {}).keys())
            fig_he = go.Figure(data=[
                go.Bar(name="Agent", x=diffs,
                       y=[res["by_difficulty"][d]["agent_pass"] for d in diffs], marker_color="#4CAF50"),
                go.Bar(name="Baseline", x=diffs,
                       y=[res["by_difficulty"][d]["baseline_pass"] for d in diffs], marker_color="#2196F3"),
            ])
            fig_he.update_layout(title="HumanEval — Agent vs Baseline by Difficulty",
                                  barmode="group", height=260,
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_he, use_container_width=True)

        # Task history table
        st.markdown("#### Task History")
        st.dataframe(
            [{"#": i + 1, "Task": h["task"], "✅": h["success"],
              "Attempts": h["attempts"], "Critique": h["critique_rounds"],
              "Memories": h["memories_used"], "Time": h["timestamp"][:19]}
             for i, h in enumerate(hist)],
            use_container_width=True,
        )


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — MEMORY EXPLORER
# ════════════════════════════════════════════════════════════════════════════
with tab_memory:
    st.subheader("Memory Explorer")

    if not CHROMADB_AVAILABLE:
        st.warning("ChromaDB not installed. Run: `pip install chromadb sentence-transformers`")
    else:
        stats = memory_stats()
        oldest, newest = get_oldest_newest_timestamps()
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("Total memories", stats["total_failures_stored"])
        col_s2.metric("Oldest", oldest[:10] if oldest else "—")
        col_s3.metric("Newest", newest[:10] if newest else "—")

        st.divider()
        st.markdown("#### 🔍 Search Memories")
        search_q = st.text_input("Search by task description (semantic search)")
        if search_q.strip():
            results = retrieve_similar_failures(search_q, top_k=5)
            if results:
                for r in results:
                    with st.container(border=True):
                        st.markdown(f"**Similarity:** `{r['similarity']:.2f}` | {r['timestamp'][:19]}")
                        st.markdown(f"**Task:** {r['task']}")
                        with st.expander("Code & Error"):
                            st.code(r["code"], language="python")
                            st.error(r["error"])
            else:
                st.info("No similar memories found.")

        st.divider()
        st.markdown("#### 📂 Browse All Memories")

        mem_data = get_all_memories(page=st.session_state.mem_page, per_page=10)
        total_mems = mem_data["total"]
        total_pages = max(1, (total_mems + 9) // 10)
        st.caption(f"Showing page {st.session_state.mem_page}/{total_pages} ({total_mems} total)")

        for item in mem_data["items"]:
            with st.container(border=True):
                col_info, col_del = st.columns([5, 1])
                with col_info:
                    st.markdown(f"**{item['timestamp'][:19]}** — {item['task'][:80]}")
                    st.caption(f"Error: {item['error'][:100]}")
                with col_del:
                    if st.button("🗑", key=f"del_{item['id']}", help="Delete this memory"):
                        delete_memory_by_id(item["id"])
                        st.toast("Memory deleted.")
                        st.rerun()
                with st.expander("Full details"):
                    st.code(item["code"], language="python")
                    st.error(item["error"])

        col_prev, col_pg, col_next = st.columns([1, 3, 1])
        if col_prev.button("◀ Prev") and st.session_state.mem_page > 1:
            st.session_state.mem_page -= 1
            st.rerun()
        col_pg.markdown(f"<center>Page {st.session_state.mem_page}/{total_pages}</center>", unsafe_allow_html=True)
        if col_next.button("Next ▶") and st.session_state.mem_page < total_pages:
            st.session_state.mem_page += 1
            st.rerun()

        st.divider()
        st.markdown("#### ⚠️ Danger Zone")
        confirm_clear = st.checkbox("I understand this will delete ALL memories permanently")
        if st.button("🗑 Clear All Memory", type="secondary", disabled=not confirm_clear):
            clear_memory()
            st.toast("All memories cleared.")
            st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — SETTINGS
# ════════════════════════════════════════════════════════════════════════════
with tab_settings:
    st.subheader("Settings")
    col_llm, col_agent = st.columns(2)

    with col_llm:
        with st.container(border=True):
            st.markdown("**LLM Settings**")

            def _on_settings_model_change():
                st.session_state["model"] = st.session_state["_s_model_widget"]

            st.selectbox(
                "Model", AVAILABLE_MODELS,
                index=AVAILABLE_MODELS.index(st.session_state.model),
                key="_s_model_widget", on_change=_on_settings_model_change,
            )

            st.session_state.temperature = st.slider(
                "Temperature", 0.0, 1.0, float(st.session_state.temperature), 0.05, key="s_temp"
            )
            st.session_state.max_tokens = st.slider(
                "Max tokens", 512, 4096, int(st.session_state.max_tokens), 128, key="s_maxtok"
            )

    with col_agent:
        with st.container(border=True):
            st.markdown("**Agent Settings**")
            st.session_state.max_retries = st.slider(
                "Max fix retries", 1, 10, st.session_state.max_retries, key="s_retries"
            )
            st.session_state.max_critique_rounds = st.slider(
                "Max critique rounds", 1, 5, st.session_state.max_critique_rounds, key="s_critique"
            )
            st.session_state.sandbox_timeout = st.slider(
                "Sandbox timeout (s)", 5, 60, st.session_state.sandbox_timeout, key="s_timeout"
            )
            st.session_state.benchmark_runs = st.slider(
                "Benchmark runs", 1, 10, st.session_state.benchmark_runs, key="s_bench"
            )

    st.divider()
    col_feat, col_mem_s = st.columns(2)

    with col_feat:
        with st.container(border=True):
            st.markdown("**Feature Toggles**")
            st.session_state.enable_critique = st.toggle(
                "Enable Critique Agent", st.session_state.enable_critique, key="s_crit_tog"
            )
            st.session_state.enable_memory = st.toggle(
                "Enable Vector Memory", st.session_state.enable_memory,
                disabled=not CHROMADB_AVAILABLE, key="s_mem_tog"
            )
            st.session_state.enable_benchmark = st.toggle(
                "Enable Benchmarking", st.session_state.enable_benchmark, key="s_bench_tog"
            )
            st.session_state.show_diff = st.toggle(
                "Show code diff viewer", st.session_state.show_diff, key="s_diff_tog"
            )
            st.session_state.auto_enhance = st.toggle(
                "Auto-enhance task prompts", st.session_state.auto_enhance, key="s_enhance_tog"
            )

    with col_mem_s:
        with st.container(border=True):
            st.markdown("**Memory Settings**")
            st.session_state.mem_threshold = st.slider(
                "Similarity threshold", 0.0, 1.0,
                float(st.session_state.get("mem_threshold", 0.3)), 0.05, key="s_thresh"
            )
            st.session_state.mem_top_k = st.slider(
                "Max memories to retrieve", 1, 10,
                int(st.session_state.get("mem_top_k", 3)), key="s_topk"
            )

    st.divider()
    st.markdown("**Export / Import Settings**")
    settings_export = {k: st.session_state[k] for k in [
        "model", "temperature", "max_tokens", "max_retries", "max_critique_rounds",
        "sandbox_timeout", "benchmark_runs", "enable_critique", "enable_memory",
        "enable_benchmark", "show_diff", "mem_threshold", "mem_top_k",
    ]}
    col_exp, col_imp = st.columns(2)
    col_exp.download_button(
        "📤 Export settings JSON",
        data=json.dumps(settings_export, indent=2),
        file_name="agent_settings.json",
        mime="application/json",
    )
    uploaded_settings = col_imp.file_uploader("📥 Import settings JSON", type="json", key="s_import")
    if uploaded_settings:
        try:
            imported = json.load(uploaded_settings)
            for k, v in imported.items():
                if k in st.session_state:
                    st.session_state[k] = v
            st.success("Settings imported.")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to import settings: {e}")