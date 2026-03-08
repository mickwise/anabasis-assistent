-- =============================================================================
-- 0017_character_aliases.sql
--
-- Purpose
--   Store alternate, former, honorific, translated, title-like, and secret
--   names for canonical characters in the world-state schema. This table exists
--   so the system can resolve multiple surface names back to a single canonical
--   character entity, optionally scoped to a historical validity window.
--
-- Row semantics
--   One row represents one alias fact for one canonical character, optionally
--   bounded by a start and end era plus year-in-era range.
--
-- Conventions
--   - `alias_name` is stored as free text but must be nonblank after trimming.
--   - Temporal validity is modeled with optional era FKs plus nonnegative
--     year-in-era integers, rather than a single absolute date type.
--   - Rows are append-oriented historical facts; prefer inserting a new row for
--     a distinct alias period or alias type rather than overwriting prior
--     meaning.
--
-- Keys & constraints
--   - Primary key: `character_alias_id`
--   - Natural keys / uniqueness: `(character_id, alias_name)` is unique so the
--     same canonical character cannot carry the same alias text twice.
--   - Checks: nonblank trimmed `alias_name`; `alias_type` restricted to the
--     allowed alias categories; `start_year` and `end_year` must be
--     nonnegative when present; `notes` must be nonblank when present.
--
-- Relationships
--   - Owns FKs to `characters(character_id)` and optionally to `eras(era_id)`
--     through `start_era_id` and `end_era_id`.
--   - Downstream name-resolution, search, and ingestion logic should join this
--     table to `characters` on `character_id` to map observed alias strings
--     back to the canonical character entity.
--
-- Audit & provenance
--   This table records creation time via `created_at` but does not store
--   source-document lineage, adjudication metadata, or extraction provenance.
--   Full provenance for alias assignment should live in higher-level ingestion
--   or event-sourcing tables if required.
--
-- Performance
--   A secondary index on `alias_name` supports alias-to-character lookup during
--   parsing, normalization, and user-facing search flows.
--
-- Change management
--   Extend alias semantics additively: prefer adding new nullable metadata
--   columns or widening the allowed `alias_type` domain without changing row
--   meaning or reinterpreting existing temporal fields.
-- =============================================================================

CREATE TABLE IF NOT EXISTS character_aliases (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this character alias.
    character_alias_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Owning character.
    character_id UUID NOT NULL REFERENCES characters (character_id),

    -- Alias text.
    alias_name TEXT NOT NULL,

    -- Alias classification.
    alias_type TEXT NOT NULL DEFAULT 'epithet',

    -- Optional temporal start era.
    start_era_id UUID REFERENCES eras (era_id),

    -- Optional temporal start year-in-era.
    start_year INTEGER,

    -- Optional temporal end era.
    end_era_id UUID REFERENCES eras (era_id),

    -- Optional temporal end year-in-era.
    end_year INTEGER,

    -- Optional notes.
    notes TEXT,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT character_aliases_uq_character_alias
    UNIQUE (character_id, alias_name),

    CONSTRAINT character_aliases_chk_alias_name_nonempty
    CHECK (length(btrim(alias_name)) > 0),

    CONSTRAINT character_aliases_chk_alias_type
    CHECK (
        alias_type IN (
            'epithet',
            'title_name',
            'former_name',
            'honorific',
            'translated_name',
            'secret_name'
        )
    ),

    CONSTRAINT character_aliases_chk_year_nonnegative
    CHECK (
        (start_year IS NULL OR start_year >= 0)
        AND (end_year IS NULL OR end_year >= 0)
    ),

    CONSTRAINT character_aliases_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_character_aliases_alias_name
ON character_aliases (alias_name);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE character_aliases IS
'One row per alternate or honorific character name, optionally time-bounded.';

COMMENT ON COLUMN character_aliases.character_alias_id IS
'Primary key for this character alias row (UUID).';

COMMENT ON COLUMN character_aliases.character_id IS
'Owning character.';

COMMENT ON COLUMN character_aliases.alias_name IS
'Alias text for the character.';

COMMENT ON COLUMN character_aliases.alias_type IS
'Alias category (epithet/honorific/etc.).';

COMMENT ON COLUMN character_aliases.start_era_id IS
'Optional start era for alias validity.';

COMMENT ON COLUMN character_aliases.start_year IS
'Optional start year-in-era for alias validity.';

COMMENT ON COLUMN character_aliases.end_era_id IS
'Optional end era for alias validity.';

COMMENT ON COLUMN character_aliases.end_year IS
'Optional end year-in-era for alias validity.';

COMMENT ON COLUMN character_aliases.notes IS
'Optional notes for this alias record.';

COMMENT ON COLUMN character_aliases.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON INDEX idx_character_aliases_alias_name IS
'Index to accelerate alias-based character lookup.';
