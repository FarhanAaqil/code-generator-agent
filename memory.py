import os
import json
import datetime
from config import MEMORY_DIR, MEMORY_COLLECTION, MEMORY_TOP_K, MEMORY_SIMILARITY_THRESHOLD

CHROMADB_AVAILABLE = False
_client = None
_collection = None

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    CHROMADB_AVAILABLE = True
except ImportError:
    pass


def _get_collection():
    global _client, _collection
    if not CHROMADB_AVAILABLE:
        return None
    if _collection is None:
        _client = chromadb.PersistentClient(path=MEMORY_DIR)
        ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        _collection = _client.get_or_create_collection(
            name=MEMORY_COLLECTION,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def store_failure(task: str, code: str, error: str) -> bool:
    """Embed and store a failure in ChromaDB."""
    col = _get_collection()
    if col is None:
        return False
    try:
        doc_text = f"TASK: {task}\nERROR: {error}"
        entry_id = f"fail_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        col.add(
            documents=[doc_text],
            metadatas=[{
                "task": task[:500],
                "code": code[:2000],
                "error": error[:500],
                "timestamp": datetime.datetime.utcnow().isoformat()
            }],
            ids=[entry_id]
        )
        return True
    except Exception:
        return False


def retrieve_similar_failures(task: str, top_k: int = None) -> list:
    """
    Semantic search for similar past failures.
    Returns list of {task, code, error, similarity, timestamp}
    """
    col = _get_collection()
    if col is None:
        return []
    if top_k is None:
        top_k = MEMORY_TOP_K
    try:
        count = col.count()
        if count == 0:
            return []
        k = min(top_k, count)
        results = col.query(
            query_texts=[f"TASK: {task}"],
            n_results=k,
            include=["metadatas", "distances"]
        )
        failures = []
        for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # similarity = 1 - (distance / 2) for cosine space
            similarity = round(1.0 - (dist / 2.0), 4)
            if similarity >= MEMORY_SIMILARITY_THRESHOLD:
                failures.append({
                    "task": meta.get("task", ""),
                    "code": meta.get("code", ""),
                    "error": meta.get("error", ""),
                    "timestamp": meta.get("timestamp", ""),
                    "similarity": similarity
                })
        return failures
    except Exception:
        return []


def build_memory_context(task: str, top_k: int = None) -> str:
    """Build formatted memory context block for LLM injection."""
    failures = retrieve_similar_failures(task, top_k)
    if not failures:
        return ""
    lines = ["### Past Failures (learn from these):\n"]
    for i, f in enumerate(failures, 1):
        lines.append(f"[Memory {i}] Similarity: {f['similarity']:.2f}")
        lines.append(f"Task: {f['task']}")
        lines.append(f"Code that failed:\n{f['code']}")
        lines.append(f"Error: {f['error']}\n")
    return "\n".join(lines)


def memory_stats() -> dict:
    """Return stats about stored memories."""
    col = _get_collection()
    if col is None:
        return {"total_failures_stored": 0, "memory_dir": MEMORY_DIR, "available": False}
    try:
        count = col.count()
        size_bytes = 0
        for root, dirs, files in os.walk(MEMORY_DIR):
            for fname in files:
                try:
                    size_bytes += os.path.getsize(os.path.join(root, fname))
                except Exception:
                    pass
        return {
            "total_failures_stored": count,
            "memory_dir": MEMORY_DIR,
            "disk_size_kb": round(size_bytes / 1024, 1),
            "available": True
        }
    except Exception:
        return {"total_failures_stored": 0, "memory_dir": MEMORY_DIR, "available": True}


def clear_memory() -> bool:
    """Delete and recreate the failures collection."""
    global _collection, _client
    col = _get_collection()
    if col is None:
        return False
    try:
        _client.delete_collection(MEMORY_COLLECTION)
        _collection = None
        _get_collection()
        return True
    except Exception:
        return False


def get_all_memories(page: int = 1, per_page: int = 10) -> dict:
    """Paginated retrieval of all memories."""
    col = _get_collection()
    if col is None:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}
    try:
        total = col.count()
        if total == 0:
            return {"items": [], "total": 0, "page": page, "per_page": per_page}
        all_data = col.get(include=["metadatas", "documents"], limit=10000)
        items = []
        for entry_id, meta in zip(all_data["ids"], all_data["metadatas"]):
            items.append({
                "id": entry_id,
                "task": meta.get("task", ""),
                "code": meta.get("code", ""),
                "error": meta.get("error", ""),
                "timestamp": meta.get("timestamp", "")
            })
        # Sort newest first
        items.sort(key=lambda x: x["timestamp"], reverse=True)
        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        return {"items": items[start:end], "total": total, "page": page, "per_page": per_page}
    except Exception:
        return {"items": [], "total": 0, "page": page, "per_page": per_page}


def get_oldest_newest_timestamps() -> dict:
    """Return oldest and newest entry timestamps."""
    col = _get_collection()
    if col is None:
        return {"oldest": None, "newest": None}
    try:
        all_data = col.get(include=["metadatas"], limit=10000)
        timestamps = [m.get("timestamp", "") for m in all_data["metadatas"] if m.get("timestamp")]
        if not timestamps:
            return {"oldest": None, "newest": None}
        timestamps.sort()
        return {"oldest": timestamps[0], "newest": timestamps[-1]}
    except Exception:
        return {"oldest": None, "newest": None}


def delete_memory_by_id(entry_id: str) -> bool:
    """Delete a single memory entry by ID."""
    col = _get_collection()
    if col is None:
        return False
    try:
        col.delete(ids=[entry_id])
        return True
    except Exception:
        return False
