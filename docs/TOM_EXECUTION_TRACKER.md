# Tom Cross-Media V1 Execution Tracker

Branch: `codex/tom-cross-media-v1`
Primary goal: evolve from YouTube-only summarizer into a cross-media product with a strong, visual unified inbox.

## Guardrails
- Keep `main` untouched; all work stays on this branch.
- Keep existing YouTube flow backward compatible.
- Land changes in small, reviewable PR slices.
- No secrets or local environment artifacts committed.

## Product Scope (V1)
- Sources: YouTube, Podcast URLs, Web article URLs, PDF upload, Book highlights (pasted text), Social thread/post text.
- Core loop: Ingest -> Summary -> Recall. (Deep fact-checking intentionally deferred)
- Home UX: Unified Inbox with mixed media cards.
- Visual style: soft-glass, card-clustered, "interesting to look at" dashboard.

## PR Slice Plan

### Slice 0: Repo safety and execution setup
- [x] Create isolated branch
- [x] Harden `.gitignore` for local artifacts
- [x] Add execution tracker

### Slice 1: Data contracts and API foundation
- [x] Add media-type model and ingestion request schema
- [x] Add `POST /ingest` endpoint (non-breaking)
- [x] Keep `POST /analyze` as compatibility wrapper for YouTube
- [x] Add response shape for mixed-media list cards

### Slice 2: Pipeline compatibility layer
- [x] Keep YouTube extractor path intact
- [x] Add placeholders for non-YouTube extractors with clear error states
- [x] Write YouTube async results back to the linked `content_item` metadata

### Slice 3: Frontend shell redesign
- [x] Replace hero-heavy landing with app-shell layout
- [x] Add left navigation rail + top search bar + main content grid
- [x] Add mixed-media card component and live backend population

### Slice 4: Insight panel interaction
- [x] Implement click-to-open right panel
- [x] Implement Summary-focused detail panel (fact-check tab deferred)
- [x] Add moments and key-points rendering for source insight

### Slice 5: Ingestion UX
- [x] Add Add Source modal (URL/text/file)
- [x] Type detection and validation
- [x] Submission flow tied to `/ingest` and `/uploads`

### Slice 6: Memory + digest
- [x] Add Ask Memory surface (UI + endpoint contract)
- [ ] Add weekly digest list view in UI

### Slice 7: QA and polish
- [ ] Mobile responsiveness pass
- [ ] Visual polish and motion tuning
- [ ] Error and empty-state hardening
- [ ] Smoke test existing YouTube-only path

### Slice 8: Premium lanes + integrations scaffold
- [x] Replace single mixed-list UI with lane-oriented workspace (`video`, `audio`, `reading`)
- [x] Add hover peek interactions with quick actions (`pin`, `tag`, `save`, `open`)
- [x] Add right-side detail drawer with tabbed insight panels
- [x] Add provider discovery API: `GET /integrations/providers`
- [x] Add Readwise bridge scaffold APIs:
  - `POST /integrations/readwise/connect`
  - `POST /integrations/readwise/sync`
  - `GET /integrations/sync-jobs/{job_id}`
- [x] Add lane-optimized listing API: `GET /items/lanes`
- [x] Extend ingestion modes with `highlights_file` and `provider_sync`
- [x] Improve summary extraction fallback for async YouTube results

## Acceptance Gates
- A mixed feed can display at least 6 media-type card variants.
- Existing YouTube URL flow still works end-to-end.
- Item click opens panel with Summary + Key points + Moments content.
- No secret files or local env folders tracked.
- UI is usable on desktop and mobile.

## Working Conventions
- Branches from this line (if needed):
  - `codex/tom-s1-api-foundation`
  - `codex/tom-s2-pipeline`
  - `codex/tom-s3-ui-shell`
- Commit message format: `tom-sX: <what changed>`
- Keep one logical change per commit.
