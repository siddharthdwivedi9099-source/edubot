"""
Ingest the generated knowledge-base articles into the Chroma vector store.

Run this AFTER `generate_kb.py` and AFTER you have set the LLM/embedding
provider in `.env`. With the default (Ollama + nomic-embed-text) you must have
the embedding model pulled first:

    ollama pull nomic-embed-text

Usage:
    python scripts/ingest_kb.py            # ingest all
    python scripts/ingest_kb.py --reset    # wipe collection first
    python scripts/ingest_kb.py --limit 50 # ingest only first 50 (smoke test)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Make `app` importable when running this script directly
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.rag import ingest_articles, reset_collection, collection_size  # noqa: E402
from app.models.schemas import KBArticle  # noqa: E402

KB_FILE = ROOT / "app" / "data" / "kb_articles.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest KB articles into Chroma")
    parser.add_argument("--reset", action="store_true", help="Wipe collection first")
    parser.add_argument("--limit", type=int, default=0, help="Ingest only N articles")
    parser.add_argument("--batch", type=int, default=64, help="Batch size for ingestion")
    args = parser.parse_args()

    if not KB_FILE.exists():
        sys.exit(f"❌ KB file not found at {KB_FILE}. Run generate_kb.py first.")

    raw = json.loads(KB_FILE.read_text(encoding="utf-8"))
    if args.limit:
        raw = raw[: args.limit]

    articles = [KBArticle(**a) for a in raw]
    print(f"📚 Loaded {len(articles)} articles from {KB_FILE.name}")

    if args.reset:
        print("🧹 Resetting Chroma collection…")
        reset_collection()

    # Ingest in batches so embedding calls don't blow up memory / context
    total = 0
    for i in range(0, len(articles), args.batch):
        chunk = articles[i : i + args.batch]
        n = ingest_articles(chunk)
        total += n
        print(f"   …ingested {total}/{len(articles)} (chunks added: {n})")

    print(f"✅ Done. Collection now contains {collection_size()} chunks.")


if __name__ == "__main__":
    main()
