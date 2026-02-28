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
- Core loop: Ingest -> Summary -> Fact-check -> Recall.
- Home UX: Unified Inbox with mixed media cards.
- Visual style: soft-glass, card-clustered, "interesting to look at" dashboard.

## PR Slice Plan

### Slice 0: Repo safety and execution setup
- [x] Create isolated branch
- [x] Harden `.gitignore` for local artifacts
- [x] Add execution tracker

### Slice 1: Data contracts and API foundation
- [ ] Add media-type model and ingestion request schema
- [ ] Add `POST /ingest` endpoint (non-breaking)
- [ ] Keep `POST /analyze` as compatibility wrapper for YouTube
- [ ] Add response shape for mixed-media list cards

### Slice 2: Pipeline compatibility layer
- [ ] Generalize analysis task input from `youtube_url` to `content_item`
- [ ] Keep YouTube extractor path intact
- [ ] Add placeholders for non-YouTube extractors with clear error states

### Slice 3: Frontend shell redesign
- [ ] Replace hero-heavy landing with app-shell layout
- [ ] Add left navigation rail + top search bar + main content grid
- [ ] Add mixed-media card component and dummy-state population

### Slice 4: Insight panel interaction
- [ ] Implement click-to-open right panel
- [ ] Implement Summary and Fact-check tabs as floating/action pills
- [ ] Add source evidence rendering and verdict badges

### Slice 5: Ingestion UX
- [ ] Add Add Source modal (URL/text/file)
- [ ] Type detection and validation
- [ ] Submission flow tied to `/ingest`

### Slice 6: Memory + digest
- [ ] Add Ask Memory surface (UI + endpoint contract)
- [ ] Add weekly digest list view in UI

### Slice 7: QA and polish
- [ ] Mobile responsiveness pass
- [ ] Visual polish and motion tuning
- [ ] Error and empty-state hardening
- [ ] Smoke test existing YouTube-only path

## Acceptance Gates
- A mixed feed can display at least 6 media-type card variants.
- Existing YouTube URL flow still works end-to-end.
- Item click opens panel with Summary + Fact-check content.
- No secret files or local env folders tracked.
- UI is usable on desktop and mobile.

## Working Conventions
- Branches from this line (if needed):
  - `codex/tom-s1-api-foundation`
  - `codex/tom-s2-pipeline`
  - `codex/tom-s3-ui-shell`
- Commit message format: `tom-sX: <what changed>`
- Keep one logical change per commit.
