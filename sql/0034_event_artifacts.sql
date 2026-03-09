-- =============================================================================
-- 0034_event_artifacts.sql
--
-- Purpose
--   Define the join table that records which canonical artifacts participate in
--   an event and in what role. This exists so event-level world-state facts can
--   represent multi-artifact participation, role semantics, and per-link
--   confidence without overloading the core events table.
--
-- Row semantics
--   One row represents one event-to-artifact participation fact for a specific
--   role_type. This is a relational fact table rather than an artifact entity
--   table: one event may involve many artifacts, and one artifact may appear in
--   many events under different roles.
--
-- Conventions
--   - event_id and artifact_id are UUID foreign keys and follow the
--     repository's standard surrogate-key conventions.
--   - role_type is stored as lowercase TEXT and constrained to a closed
--     enum-like domain via CHECK rather than a dedicated Postgres ENUM type.
--   - is_primary marks whether this participation link should be treated as a
--     primary role association for the event, but does not enforce uniqueness
--     of primaries at the schema level.
--   - source_confidence is stored as NUMERIC(4,3) on the closed interval
--     [0.000, 1.000].
--   - notes is optional free text but, when present, must be non-blank after
--     trimming.
--
-- Keys & constraints
--   - Primary key: (event_id, artifact_id, role_type)
--   - Natural keys / uniqueness: The same artifact may be attached to the same
--     event more than once only when the role_type differs.
--   - Checks: role_type must be one of created, forged, wielded, used, stolen,
--     hidden, destroyed, discovered, or transferred; source_confidence must lie
--     in [0,1]; notes must be NULL or trimmed non-empty text.
--
-- Relationships
--   - Owns foreign keys to events(event_id) and artifacts(artifact_id).
--   - Downstream joins should typically enter from events via event_id to
--     recover all linked artifacts, or from artifacts via artifact_id to
--     recover all events in which an artifact participated.
--   - role_type and is_primary are intended to support downstream narrative,
--     search, ranking, and extraction-quality logic over participant links.
--
-- Audit & provenance
--   This table stores the current event-artifact relationship, an optional
--   local note, and a per-link confidence score. Full source-document lineage,
--   extraction traces, and ingestion provenance are expected to live in
--   upstream pipeline artifacts or dedicated provenance tables rather than
--   here.
--
-- Performance
--   - The composite primary key supports uniqueness enforcement and event-
--     anchored lookups.
--   - Secondary index idx_event_artifacts_artifact_id supports reverse lookups
--     from an artifact to all linked events.
--   - Secondary index idx_event_artifacts_role_type supports filtering and
--     aggregation by participant role.
--
-- Change management
--   Extend role semantics additively by widening the CHECK constraint while
--   keeping existing role labels stable. Prefer nullable column additions and
--   new indexes over key-shape changes so downstream joins, loaders, and
--   extraction code remain compatible.
-- =============================================================================

CREATE TABLE IF NOT EXISTS event_artifacts (

    -- ===========
    -- Endpoints
    -- ===========

    -- Event endpoint.
    event_id UUID NOT NULL REFERENCES events (event_id),

    -- Artifact endpoint.
    artifact_id UUID NOT NULL REFERENCES artifacts (artifact_id),

    -- Artifact role in the event.
    role_type TEXT NOT NULL,

    -- Whether this role is primary for this event.
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,

    -- Optional notes.
    notes TEXT,

    -- Confidence score in [0.0, 1.0].
    source_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT event_artifacts_pk
    PRIMARY KEY (event_id, artifact_id, role_type),

    CONSTRAINT event_artifacts_chk_role_type
    CHECK (
        role_type IN (
            'created',
            'forged',
            'wielded',
            'used',
            'stolen',
            'hidden',
            'destroyed',
            'discovered',
            'transferred'
        )
    ),

    CONSTRAINT event_artifacts_chk_source_confidence_range
    CHECK (source_confidence >= 0 AND source_confidence <= 1),

    CONSTRAINT event_artifacts_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_event_artifacts_artifact_id
ON event_artifacts (artifact_id);

CREATE INDEX IF NOT EXISTS idx_event_artifacts_role_type
ON event_artifacts (role_type);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE event_artifacts IS
'Artifact participants in events with explicit role labels and confidence.';

COMMENT ON COLUMN event_artifacts.event_id IS
'Event endpoint.';

COMMENT ON COLUMN event_artifacts.artifact_id IS
'Artifact endpoint.';

COMMENT ON COLUMN event_artifacts.role_type IS
'Artifact role in the event.';

COMMENT ON COLUMN event_artifacts.is_primary IS
'Whether this role is primary for this event.';

COMMENT ON COLUMN event_artifacts.notes IS
'Optional notes for this participant relation.';

COMMENT ON COLUMN event_artifacts.source_confidence IS
'Confidence score in [0.0, 1.0] for this participant assertion.';

COMMENT ON INDEX idx_event_artifacts_artifact_id IS
'Index to accelerate event lookup by artifact participant.';

COMMENT ON INDEX idx_event_artifacts_role_type IS
'Index to accelerate filtering by artifact participant role.';
