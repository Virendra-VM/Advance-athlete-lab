# Science knowledge base — source and citation policy

The AI coach is **grounded by retrieval, not fine-tuning**. Every claim it makes about
training principles should trace back to a chunk in this knowledge base, or be phrased as
the coach's own judgement about the athlete's data.

## What lives in the KB

| Layer | Location | Notes |
| --- | --- | --- |
| Corpus files | `backend/data/science_corpus/*.json` | Source of truth, version-controlled |
| Tables | `science_sources`, `science_chunks` | Upserted by slug + chunk key |
| Ingest | `backend/scripts/science_ingest/ingest.py` | Idempotent; removes deleted chunks |
| Retrieval | `app/services/science_kb.retrieve_science()` | BM25 + sport/topic tag boosts |
| API | `GET /api/science/search`, `GET /api/science/sources`, `POST /api/science/reindex` | Auth required |

The corpus is seeded automatically on first boot (`ensure_corpus_loaded`), so a fresh
install has a working KB without manual steps.

## Source policy (hard rules)

Allowed:

- Coach-written playbooks we own (`Advance Athlete Lab coaching team`).
- Open public-health guidelines with a clear licence (e.g. WHO physical activity
  guidelines, CC BY-NC-SA 3.0 IGO), **paraphrased** with the licence recorded.
- Open-access reviews and position stands whose licence permits redistribution.

Not allowed:

- Copyrighted or paywalled books, journal PDFs, or coaching products.
- Scraped content of unknown provenance.
- Any chunk without `license` and `title` metadata — the ingest script fails on this.

Every source record carries `title`, `authors`, `year`, `publisher`, `license`, and `url`
so the coach can attribute a claim, and so a source can be pulled if its licence changes.

## Chunk schema

```json
{
  "key": "intensity-distribution",
  "heading": "Polarized vs pyramidal intensity distribution",
  "audience": "endurance",           // endurance | strength | shared
  "sport_tags": ["run", "ride"],     // run | ride | swim | triathlon | strength | general
  "topic_tags": ["intensity", "weekly-structure"],
  "body": "One self-contained idea, 80–200 words."
}
```

Keep chunks self-contained: retrieval returns them without surrounding context, so a
chunk that starts with "As mentioned above…" is unusable.

## Citation policy for generated output

1. Retrieved chunks are injected into the prompt with stable labels `[S1] … [Sn]`.
2. The model may cite only those labels. It must not invent titles, authors, or years.
3. If no chunk supports a claim, the model states the reasoning as coaching judgement or
   says the evidence is unclear — it does not fabricate a reference.
4. Plans and advice persist the contributing source slugs (`training_plans.citations`,
   `coach_messages.citations`) so any output can be audited after the fact.
5. Safety and referral chunks are retrieval-boosted so red-flag guidance stays reachable
   even for vaguely worded questions.

## Scope limits baked into the corpus

`aal-safety-and-load` defines the coach's boundaries: no diagnosis, no rehabilitation
protocols, no clinical nutrition, referral for red flags and special populations. These
are enforced twice — as retrieved text in the prompt, and deterministically by
`app/services/coach_safety.py`, which can reject or downgrade a generated plan before the
athlete ever sees it.

## Adding a source

```bash
# 1. add backend/data/science_corpus/<slug>.json
# 2. validate without writing
python scripts/science_ingest/ingest.py --dry-run
# 3. ingest and smoke-test retrieval
python scripts/science_ingest/ingest.py --query "how do I progress weekly mileage" --sport run
```
