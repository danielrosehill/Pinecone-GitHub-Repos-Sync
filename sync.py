#!/usr/bin/env python3
"""Incrementally sync danielrosehill GitHub repos into Pinecone.

Index: daniel-personal, namespace: github-repos.
- Upserts only repos whose updated_at is newer than what's stored, or that are missing.
- Deletes records for repos that no longer exist or were archived.
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
    """Page through /user/repos (no 1000-cap, unlike `gh repo list`)."""
    out = subprocess.check_output(
        [
            "gh", "api", "--paginate",
            "/user/repos?affiliation=owner&per_page=100",
            "--jq",
            '.[] | select(.archived==false) | '
            '{name, url: .html_url, description, '
            'visibility: (if .private then "private" else "public" end), '
            'createdAt: .created_at, updatedAt: .updated_at}',
        ],
        text=True,
    )
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def to_record(r):
    desc = r.get("description") or ""
    text = (
        f"Repository: {r['name']}. {desc} "
        f"URL: {r['url']}. Visibility: {r['visibility']}."
    ).strip()
    return {
        "_id": r["name"],
        "text": text,
        "repo_name": r["name"],
        "repo_url": r["url"],
        "description": desc,
        "visibility": r["visibility"],
        "created_at": r["createdAt"],
        "updated_at": r["updatedAt"],
    }


def list_existing_ids(index):
    ids = []
    for page in index.list(namespace=NAMESPACE):
        ids.extend(page)
    return ids


def fetch_existing_updated_at(index, ids):
    """Return {id: updated_at} for the given ids, in batches of 100."""
    out = {}
    for i in range(0, len(ids), 100):
        batch = ids[i : i + 100]
        resp = index.fetch(ids=batch, namespace=NAMESPACE)
        vectors = getattr(resp, "vectors", None) or resp.get("vectors", {})
        for vid, v in vectors.items():
            meta = getattr(v, "metadata", None) or v.get("metadata", {}) or {}
            ua = meta.get("updated_at")
            if ua:
                out[vid] = ua
    return out


def main():
    api_key = os.environ["PINECONE_API_KEY"]
    pc = Pinecone(api_key=api_key)
    index = pc.Index(INDEX_NAME)

    repos = fetch_repos()
    print(f"fetched {len(repos)} non-archived repos from GitHub")

    records = [to_record(r) for r in repos]
    current_ids = {r["_id"] for r in records}

    existing_ids = list_existing_ids(index)
    print(f"namespace currently has {len(existing_ids)} records")
    existing_ua = fetch_existing_updated_at(index, existing_ids)

    to_upsert = [
        r for r in records
        if existing_ua.get(r["_id"]) != r["updated_at"]
    ]
    print(f"upserting {len(to_upsert)} new/changed records")

    BATCH = 96
    for i in range(0, len(to_upsert), BATCH):
        index.upsert_records(NAMESPACE, to_upsert[i : i + BATCH])

    stale = sorted(set(existing_ids) - current_ids)
    if stale:
        print(f"deleting {len(stale)} stale records: {stale[:10]}{'...' if len(stale) > 10 else ''}")
        for i in range(0, len(stale), 1000):
            index.delete(ids=stale[i : i + 1000], namespace=NAMESPACE)
    else:
        print("no stale records")


if __name__ == "__main__":
    sys.exit(main())
