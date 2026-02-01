#!/usr/bin/env python3
"""Utility to export/import Jarvis ChromaDB memories.

Usage:
  python tools/jarvis_manage.py export --out memories.json
  python tools/jarvis_manage.py import --in memories.json

This script uses the project's Chroma collection if available.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

import jarvis


def export_memories(out_path: str) -> None:
    col = getattr(jarvis, "_memory_col", None)
    if col is None:
        print(
            "No memory collection available; make sure ChromaDB is installed and initialized."
        )
        sys.exit(2)

    # Query all known memories (Chroma doesn't provide a direct "all" query API uniformly,
    # so rely on the collection's internal API if available: list() or get() methods.
    try:
        if hasattr(col, "get"):
            # Some versions provide .get() to fetch all
            all_items = col.get()
            docs = all_items.get("documents", [])
            metas = all_items.get("metadatas", [])
            ids = all_items.get("ids", [])
            records = []
            for i, d, m in zip(ids, docs, metas):
                records.append({"id": i, "text": d, "meta": m})
        elif hasattr(col, "peek"):
            # fallback to peek(n) pattern if present
            recs = col.peek(n=10000)
            records = [{"id": r[0], "text": r[1], "meta": r[2]} for r in recs]
        else:
            # Last resort: no public API; warn and exit
            print(
                "Chroma collection does not expose a compatible export API in this environment."
            )
            sys.exit(3)
    except Exception as e:
        print("Error reading memories:", e)
        sys.exit(4)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"Exported {len(records)} memory records to {out_path}")


def import_memories(in_path: str) -> None:
    col = getattr(jarvis, "_memory_col", None)
    if col is None:
        print(
            "No memory collection available; make sure ChromaDB is installed and initialized."
        )
        sys.exit(2)

    with open(in_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    for rec in records:
        _id = rec.get("id") or f"imported_{int(time.time()*1000)}"
        text = rec.get("text")
        meta = rec.get("meta") or {}
        try:
            col.add(ids=[_id], documents=[text], metadatas=[meta])
        except Exception as e:
            print("Failed to add record", _id, e)

    try:
        jarvis._chroma_client.persist()
    except Exception:
        pass

    print(f"Imported {len(records)} memory records from {in_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Manage Jarvis memory (ChromaDB export/import)"
    )
    sub = parser.add_subparsers(dest="cmd")
    pexp = sub.add_parser("export")
    pexp.add_argument("--out", required=True)
    pimp = sub.add_parser("import")
    pimp.add_argument("--in", dest="infile", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "export":
        export_memories(args.out)
    elif args.cmd == "import":
        import_memories(args.infile)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
