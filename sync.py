#!/usr/bin/env python3
"""Sync danielrosehill GitHub repos into Pinecone (daniel-personal / github-repos).

Upserts non-archived repos; deletes records whose repos no longer exist or were archived.
"""
import json
import os
import subprocess
import sys

from pinecone import Pinecone

INDEX_NAME = "daniel-personal"
NAMESPACE = "github-repos"
GH_USER = "danielrosehill"


def fetch_repos():
    out = subprocess.check_output(
        [
            "gh", "repo", "list", GH_USER,
            "--limit", "2000",
            "--no-archived",
            "--json", "name,url,description,visibility,createdAt,updatedAt",
        ],
        text=True,
    )
    return json.loads(out)


def to_record(r):
    desc = r.get("description") or ""
    text = (
        f"Repository: {r['name']}. {desc} "
        f"URL: {r['url']}. Visibility: {r['visibility'].lower()}."
    ).strip()
    return {
        "_id": r["name"],
        "text": text,
        "repo_name": r["name"],
        "repo_url": r["url"],
        "description": desc,
        "visibility": r["visibility"].lower(),
        "created_at": r["createdAt"],
        "updated_at": r["updatedAt"],
    }


def list_existing_ids(index):
    ids = set()
    for page in index.list(namespace=NAMESPACE):
        ids.update(page)
    return ids


def main():
    api_key = os.environ["PINECONE_API_KEY"]
    pc = Pinecone(api_key=api_key)
    index = pc.Index(INDEX_NAME)

    repos = fetch_repos()
    print(f"fetched {len(repos)} non-archived repos")

    records = [to_record(r) for r in repos]
    current_ids = {r["_id"] for r in records}

    BATCH = 96
    for i in range(0, len(records), BATCH):
        index.upsert_records(NAMESPACE, records[i : i + BATCH])
    print(f"upserted {len(records)} records")

    existing = list_existing_ids(index)
    stale = sorted(existing - current_ids)
    if stale:
        print(f"deleting {len(stale)} stale records: {stale[:10]}{'...' if len(stale) > 10 else ''}")
        for i in range(0, len(stale), 1000):
            index.delete(ids=stale[i : i + 1000], namespace=NAMESPACE)
    else:
        print("no stale records")


if __name__ == "__main__":
    sys.exit(main())
