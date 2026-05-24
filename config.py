import os

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"
AVAILABLE_MODELS = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "gpt-4o", "gpt-3.5-turbo"]
TEMPERATURE = 0.1
MAX_TOKENS = 2048

# --- Agent ---
MAX_RETRIES = 5
MAX_CRITIQUE_ROUNDS = 3
SANDBOX_TIMEOUT = 10

# --- Benchmark ---
BENCHMARK_RUNS = 5
BENCHMARK_TIMEOUT = 15

# --- Paths ---
LOG_DIR = "logs"
MEMORY_DIR = "memory_db"

# --- Memory ---
MEMORY_COLLECTION = "failures"
MEMORY_TOP_K = 3
MEMORY_SIMILARITY_THRESHOLD = 0.3

# --- Ensure dirs exist ---
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MEMORY_DIR, exist_ok=True)
