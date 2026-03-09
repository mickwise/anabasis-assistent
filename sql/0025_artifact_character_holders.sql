-- =============================================================================
-- 0025_artifact_character_holders.sql
--
-- Purpose
--   Store temporal relationships between canonical artifacts and canonical
--   characters in the world-state schema. This table exists to represent who
--   held, wielded, guarded, stole, or was entrusted with an artifact over time.
--
-- Row semantics
--   One row represents one directed artifact-to-character holder relationship
--   fact under a specific relationship type, optionally bounded by a start and
--   end era plus year-in-era range.
--
-- Conventions
--   - Relationships are directed from `artifact_id` to `character_id`, so row
--     meaning is determined jointly by the endpoint order and the
--     `relationship_type` value.
--   - Temporal validity is expressed with optional era FKs plus nonnegative
--     year-in-era integers, and `start_is_approximate` or
--     `end_is_approximate` mark uncertain dating without requiring separate
--     fuzzy-date fields.
--   - `source_confidence` is a normalized numeric score on `[0.0, 1.0]` for the
--     asserted artifact-holder fact.
--
-- Keys & constraints
--   - Primary key: `artifact_character_holder_id`
--   - Natural keys / uniqueness: none enforced; the schema allows multiple rows
--     for the same artifact, character, and relationship type when temporal
--     windows, provenance, or interpretation differ.
--   - Checks: `relationship_type` restricted to the allowed
--     artifact-character holder semantics; `start_year` and `end_year` must be
--     nonnegative when present; `source_confidence` constrained to `[0, 1]`;
--     `notes` must be nonblank when present.
--
-- Relationships
--   - Owns FKs to `artifacts(artifact_id)` and `characters(character_id)`, plus
--     optional FKs to `eras(era_id)` and `events(event_id)` for temporal
--     validity and lifecycle anchoring.
--   - Downstream provenance, inventory, quest, combat, and event
--     interpretation logic should join through this table to connect canonical
--     artifacts with canonical characters over time.
--
-- Audit & provenance
--   This table records creation time via `created_at` and a lightweight
--   confidence score, but it does not store full extraction lineage,
--   adjudication history, or complete provenance chains. Detailed provenance
--   should live in higher-level ingestion or event-sourcing tables when needed.
--
-- Performance
--   Secondary indexes on `artifact_id` and `character_id` support endpoint-
--   centric traversal over artifact-character holder facts.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   companion history tables over changing the meaning of existing endpoint
--   direction, temporal fields, or confidence semantics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS artifact_character_holders (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this artifact-character holder record.
    artifact_character_holder_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Artifact endpoint.
    artifact_id UUID NOT NULL REFERENCES artifacts (artifact_id),

    -- Character endpoint.
    character_id UUID NOT NULL REFERENCES characters (character_id),

    -- Holder relationship semantic.
    relationship_type TEXT NOT NULL DEFAULT 'held_by',

    -- Optional temporal start era.
    start_era_id UUID REFERENCES eras (era_id),

    -- Optional temporal start year-in-era.
    start_year INTEGER,

    -- Whether start timing is approximate.
    start_is_approximate BOOLEAN NOT NULL DEFAULT FALSE,

    -- Optional temporal end era.
    end_era_id UUID REFERENCES eras (era_id),

    -- Optional temporal end year-in-era.
    end_year INTEGER,

    -- Whether end timing is approximate.
    end_is_approximate BOOLEAN NOT NULL DEFAULT FALSE,

    -- Event that established this relation.
    established_by_event_id UUID REFERENCES events (event_id),

    -- Event that ended this relation.
    ended_by_event_id UUID REFERENCES events (event_id),

    -- Optional notes.
    notes TEXT,

    -- Confidence score in [0.0, 1.0].
    source_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT artifact_character_holders_chk_relationship_type
    CHECK (
        relationship_type IN (
            'held_by',
            'wielded_by',
            'guarded_by',
            'stolen_by',
            'entrusted_to'
        )
    ),

    CONSTRAINT artifact_character_holders_chk_year_nonnegative
    CHECK (
        (start_year IS NULL OR start_year >= 0)
        AND (end_year IS NULL OR end_year >= 0)
    ),

    CONSTRAINT artifact_character_holders_chk_source_confidence_range
    CHECK (source_confidence >= 0 AND source_confidence <= 1),

    CONSTRAINT artifact_character_holders_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_artifact_character_holders_artifact_id
ON artifact_character_holders (artifact_id);

CREATE INDEX IF NOT EXISTS idx_artifact_character_holders_character_id
ON artifact_character_holders (character_id);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE artifact_character_holders IS
'Temporal artifact-to-character holder records.';

COMMENT ON COLUMN artifact_character_holders.artifact_character_holder_id IS
'Primary key for this artifact-character holder row (UUID).';

COMMENT ON COLUMN artifact_character_holders.artifact_id IS
'Artifact endpoint.';

COMMENT ON COLUMN artifact_character_holders.character_id IS
'Character endpoint.';

COMMENT ON COLUMN artifact_character_holders.relationship_type IS
'Holder relation semantic (held_by/wielded_by/etc.).';

COMMENT ON COLUMN artifact_character_holders.start_era_id IS
'Optional start era for holder validity.';

COMMENT ON COLUMN artifact_character_holders.start_year IS
'Optional start year-in-era for holder validity.';

COMMENT ON COLUMN artifact_character_holders.start_is_approximate IS
'Whether holder start timing is approximate.';

COMMENT ON COLUMN artifact_character_holders.end_era_id IS
'Optional end era for holder validity.';

COMMENT ON COLUMN artifact_character_holders.end_year IS
'Optional end year-in-era for holder validity.';

COMMENT ON COLUMN artifact_character_holders.end_is_approximate IS
'Whether holder end timing is approximate.';

COMMENT ON COLUMN artifact_character_holders.established_by_event_id IS
'Event that established this holder relation.';

COMMENT ON COLUMN artifact_character_holders.ended_by_event_id IS
'Event that ended this holder relation.';

COMMENT ON COLUMN artifact_character_holders.notes IS
'Optional notes for this holder relation.';

COMMENT ON COLUMN artifact_character_holders.source_confidence IS
'Confidence score in [0.0, 1.0] for this holder assertion.';

COMMENT ON COLUMN artifact_character_holders.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON INDEX idx_artifact_character_holders_artifact_id IS
'Index to accelerate artifact-centric character holder lookups.';

COMMENT ON INDEX idx_artifact_character_holders_character_id IS
'Index to accelerate character-centric artifact holder lookups.';
