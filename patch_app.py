"""
Run once from the project folder:  python patch_app.py
Fixes two deprecation warnings in app.py:
  1. use_container_width=True/False  →  width='stretch'/'content'  (buttons only)
  2. datetime.datetime.utcnow()      →  datetime.datetime.now(datetime.timezone.utc)
"""
import re, shutil, sys

TARGET = "app.py"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

original = src

# ── 1. datetime.utcnow() ─────────────────────────────────────────────────────
src = src.replace(
    "datetime.datetime.utcnow()",
    "datetime.datetime.now(datetime.timezone.utc)"
)

# ── 2. use_container_width on buttons / inputs (NOT plotly charts) ────────────
# We only want to replace it inside st.button / st.download_button /
# st.number_input / st.text_input  etc.  NOT inside st.plotly_chart().
# Strategy: replace every occurrence that is NOT preceded by "plotly_chart"
# on the same logical line.

def fix_ucw(text):
    lines = text.splitlines(keepends=True)
    out = []
    for line in lines:
        # Leave plotly_chart lines alone
        if "plotly_chart" in line or "dataframe" in line or "image" in line:
            out.append(line)
            continue
        line = line.replace("use_container_width=True",  "width='stretch'")
        line = line.replace("use_container_width=False", "width='content'")
        out.append(line)
    return "".join(out)

src = fix_ucw(src)

if src == original:
    print("Nothing to patch — file already up to date.")
    sys.exit(0)

# Back up original
shutil.copy(TARGET, TARGET + ".bak")
print(f"Backup saved: {TARGET}.bak")

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

# Count replacements
dt_count  = original.count("datetime.datetime.utcnow()")
ucw_count = original.count("use_container_width=True") + original.count("use_container_width=False")
print(f"✅ Fixed {dt_count} utcnow() call(s)")
print(f"✅ Fixed {ucw_count} use_container_width occurrence(s)")
print("Done — restart Streamlit.")
