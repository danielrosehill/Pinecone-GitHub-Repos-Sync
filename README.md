# Pinecone-GitHub-Repos-Sync

Daily GitHub Action that mirrors `danielrosehill`'s non-archived GitHub repos into the Pinecone index `daniel-personal`, namespace `github-repos`.

- Upsert is keyed on repo name (`_id`), so renames create a new record (the old one is removed by the stale-deletion pass).
- Archived repos are excluded at fetch time and removed on the next run.
- Repos deleted on GitHub are removed from Pinecone on the next run.

## Required secrets

- `PINECONE_API_KEY`
- `GH_REPO_LIST_TOKEN` — PAT with `repo` scope (needs to read private repos for `visibility`); a fine-grained token with read-only metadata is enough if you only want public repos.

## Manual run

`gh workflow run "Sync GitHub repos to Pinecone"` from the repo, or use the Actions tab.
