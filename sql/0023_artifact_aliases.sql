-- =============================================================================
-- 0023_artifact_aliases.sql
--
-- Purpose
--   Store alternate, former, translated, and honorific names for canonical
--   artifacts in the world-state schema. This table exists so the system can
--   resolve multiple surface names back to a single canonical artifact entity
--   without duplicating artifact-level records.
--
-- Row semantics
--   One row represents one alias fact for one canonical artifact.
--
-- Conventions
--   - `alias_name` is stored as free text but must be nonblank after trimming.
--   - Alias semantics are intentionally lightweight here: this table does not
--     model temporal validity windows, so aliases are treated as artifact-level
--     naming facts rather than dated name episodes.
--   - Rows are append-oriented alias facts; prefer inserting a new row for a
--     distinct alias string or alias category rather than overloading `notes`.
--
-- Keys & constraints
--   - Primary key: `artifact_alias_id`
--   - Natural keys / uniqueness: `(artifact_id, alias_name)` is unique so the
--     same canonical artifact cannot carry the same alias text twice.
--   - Checks: nonblank trimmed `alias_name`; `alias_type` restricted to the
--     allowed alias categories; `notes` must be nonblank when present.
--
-- Relationships
--   - Owns an FK to `artifacts(artifact_id)` through `artifact_id`.
--   - Downstream name-resolution, search, parsing, and ingestion logic should
--     join this table to `artifacts` on `artifact_id` to map observed alias
--     strings back to the canonical artifact entity.
--
-- Audit & provenance
--   This table records creation time via `created_at` but does not store
--   source-document lineage, adjudication metadata, extraction provenance, or
--   temporal validity. Full provenance for alias assignment should live in
--   higher-level ingestion or event-sourcing tables if required.
--
-- Performance
--   A secondary index on `alias_name` supports alias-to-artifact lookup during
--   normalization, entity resolution, and user-facing search flows.
--
-- Change management
--   Extend alias semantics additively: prefer adding new nullable metadata
--   columns or widening the allowed `alias_type` domain over changing the
--   meaning of existing alias rows or canonical artifact identity.
-- =============================================================================

CREATE TABLE IF NOT EXISTS artifact_aliases (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this artifact alias.
    artifact_alias_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Owning artifact.
    artifact_id UUID NOT NULL REFERENCES artifacts (artifact_id),

    -- Alias text.
    alias_name TEXT NOT NULL,

    -- Alias classification.
    alias_type TEXT NOT NULL DEFAULT 'alternate_name',

    -- Optional notes.
    notes TEXT,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT artifact_aliases_uq_artifact_alias UNIQUE (
        artifact_id, alias_name
    ),

    CONSTRAINT artifact_aliases_chk_alias_name_nonempty
    CHECK (length(btrim(alias_name)) > 0),

    CONSTRAINT artifact_aliases_chk_alias_type
    CHECK (
        alias_type IN (
            'alternate_name',
            'former_name',
            'translated_name',
            'honorific_name'
        )
    ),

    CONSTRAINT artifact_aliases_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_artifact_aliases_alias_name
ON artifact_aliases (alias_name);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE artifact_aliases IS
'One row per alternate or former artifact name.';

COMMENT ON COLUMN artifact_aliases.artifact_alias_id IS
'Primary key for this artifact alias row (UUID).';

COMMENT ON COLUMN artifact_aliases.artifact_id IS
'Owning artifact.';

COMMENT ON COLUMN artifact_aliases.alias_name IS
'Alias text for the artifact.';

COMMENT ON COLUMN artifact_aliases.alias_type IS
'Alias category (alternate/former/etc.).';

COMMENT ON COLUMN artifact_aliases.notes IS
'Optional notes for this alias record.';

COMMENT ON COLUMN artifact_aliases.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON INDEX idx_artifact_aliases_alias_name IS
'Index to accelerate alias-based artifact lookup.';
