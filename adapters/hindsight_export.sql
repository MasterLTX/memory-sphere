-- hindsight_export.sql
--
-- Produce the four input files this project expects, from a Hindsight
-- (pgvector) database.  READ-ONLY: every statement here is a COPY ... TO.
-- No INSERT / UPDATE / DELETE, no schema changes.
--
-- Usage
--   psql "$DATABASE_URL" -v bank="'coding-agent::my-workspace'" -f hindsight_export.sql
--   psql "$DATABASE_URL" -v bank="'coding-agent::my-workspace'" -f hindsight_export.sql
--
-- Output lands in data/input/.  If your schema differs, the only hard requirement
-- is the column order described in sphere/pipeline/build_sphere.py.

\set ON_ERROR_STOP on

-- NOTE: TAB separator.  The embedding column is pgvector's text form, e.g. [0.1,0.2,...]
--       which contains no tabs, so tab-separated output is safe.

-- 1) embeddings.tsv : id <tab> fact_type <tab> created_date <tab> [v1,v2,...]
\copy (SELECT id::text, fact_type, to_char(created_at,'YYYY-MM-DD') AS dt, embedding::text FROM memory_units WHERE embedding IS NOT NULL AND bank_id = :bank) TO 'data/input/embeddings.tsv'

-- 2) links.tsv : from_id <tab> to_id <tab> weight <tab> link_type
--    Edges pointing at units that no longer exist are harmless: the loader drops
--    them and reports how many it dropped.
\copy (SELECT from_unit_id::text, to_unit_id::text, weight, link_type FROM memory_links WHERE bank_id = :bank) TO 'data/input/links.tsv'

-- 3) ent_count.tsv : unit_id <tab> entity_count
\copy (SELECT unit_id::text, count(*) FROM unit_entities ue JOIN memory_units mu ON mu.id = ue.unit_id WHERE mu.bank_id = :bank GROUP BY 1) TO 'data/input/ent_count.tsv'

-- 4) models.tsv : name <tab> [v1,v2,...]   (optional; used as "mountain markers")
\copy (SELECT name, embedding::text FROM mental_models WHERE embedding IS NOT NULL) TO 'data/input/models.tsv'

-- 5) texts.tsv : id <tab> text   (optional; only used by the "one memory's journey" page.
--    Leave it out if your memory text is private -- nothing else depends on it.)
-- \copy (SELECT id::text, replace(left(text,200), chr(10), ' ') FROM memory_units WHERE bank_id = :bank) TO 'data/input/texts.tsv'