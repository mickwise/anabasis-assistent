-- =============================================================================
-- 0022_artifacts.sql
--
-- Purpose
--   Store canonical artifacts in the world-state schema. This table exists to
--   model persistent named objects such as relics, weapons, ships, maps,
--   regalia, and other notable items that can participate in events, ownership,
--   location tracking, and narrative state.
--
-- Row semantics
--   One row represents one canonical artifact entity, not a transfer event,
--   holder relationship episode, or location-history record.
--
-- Conventions
--   - `artifact_name` is stored as free text but must be nonblank after
--     trimming.
--   - `created_at` and `updated_at` are UTC `TIMESTAMPTZ` audit fields, and the
--     status and boolean flags are current-state summary attributes rather than
--     fully versioned historical facts.
--   - Current holder state is split across character and organization
--     dimensions, and at most one of `current_character_holder_id` or
--     `current_organization_holder_id` may be populated in the same row.
--
-- Keys & constraints
--   - Primary key: `artifact_id`
--   - Natural keys / uniqueness: `artifact_name` is unique across canonical
--     artifacts.
--   - Checks: nonblank trimmed `artifact_name` and `artifact_summary`;
--     `artifact_type` and `artifact_status` restricted to allowed categories;
--     `source_confidence` constrained to `[0, 1]`; holder columns cannot both
--     be populated simultaneously.
--
-- Relationships
--   - Owns optional FKs to `events(event_id)` through `origin_event_id`,
--     `locations(location_id)` through `current_location_id`,
--     `characters(character_id)` through `current_character_holder_id`, and
--     `organizations(organization_id)` through
--     `current_organization_holder_id`.
--   - Downstream alias, ownership-history, transfer, quest, and event
--     participation tables should join to this table on `artifact_id` to
--     reference the canonical artifact entity.
--
-- Audit & provenance
--   This table records row creation and update timestamps plus a lightweight
--   confidence score, but it does not store source-document lineage,
--   adjudication history, or full custody provenance. Detailed provenance for
--   artifact facts should live in higher-level ingestion or event-sourcing
--   tables when needed.
--
-- Performance
--   Secondary indexes on `artifact_type`, `artifact_status`,
--   `current_location_id`, `current_character_holder_id`, and
--   `current_organization_holder_id` support category filtering and endpoint-
--   centric lookup for current artifact state.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   companion relationship-history tables over changing the meaning of existing
--   holder pointers, status flags, or canonical artifact identity.
-- =============================================================================

CREATE TABLE IF NOT EXISTS artifacts (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this artifact.
    artifact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Canonical artifact name.
    artifact_name TEXT UNIQUE NOT NULL,

    -- Artifact class/category.
    artifact_type TEXT NOT NULL DEFAULT 'other',

    -- Short artifact summary.
    artifact_summary TEXT NOT NULL,

    -- Optional long-form details.
    artifact_details TEXT,

    -- Event where the artifact originated.
    origin_event_id UUID REFERENCES events (event_id),

    -- Current or last known location pointer.
    current_location_id UUID REFERENCES locations (location_id),

    -- Current or last known character holder pointer.
    current_character_holder_id UUID REFERENCES characters (character_id),

    -- Current or last known organization holder pointer.
    current_organization_holder_id UUID REFERENCES organizations (
        organization_id
    ),

    -- Artifact lifecycle state.
    artifact_status TEXT NOT NULL DEFAULT 'extant',

    -- Whether this artifact is legendary.
    is_legendary BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this artifact is divine.
    is_divine BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether artifact identity/history is disputed.
    is_disputed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Confidence score in [0.0, 1.0].
    source_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UTC timestamp recording row update.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT artifacts_chk_artifact_name_nonempty
    CHECK (length(btrim(artifact_name)) > 0),

    CONSTRAINT artifacts_chk_artifact_summary_nonempty
    CHECK (length(btrim(artifact_summary)) > 0),

    CONSTRAINT artifacts_chk_artifact_type
    CHECK (
        artifact_type IN (
            'shard',
            'weapon',
            'ship',
            'relic',
            'map',
            'philosophers_stone',
            'regalia',
            'tome',
            'other'
        )
    ),

    CONSTRAINT artifacts_chk_artifact_status
    CHECK (
        artifact_status IN (
            'extant',
            'lost',
            'destroyed',
            'sealed',
            'unknown'
        )
    ),

    CONSTRAINT artifacts_chk_source_confidence_range
    CHECK (source_confidence >= 0 AND source_confidence <= 1),

    CONSTRAINT artifacts_chk_single_holder_dimension
    CHECK (
        current_character_holder_id IS NULL
        OR current_organization_holder_id IS NULL
    )
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_artifacts_artifact_type
ON artifacts (artifact_type);

CREATE INDEX IF NOT EXISTS idx_artifacts_artifact_status
ON artifacts (artifact_status);

CREATE INDEX IF NOT EXISTS idx_artifacts_current_location_id
ON artifacts (current_location_id);

CREATE INDEX IF NOT EXISTS idx_artifacts_current_character_holder_id
ON artifacts (current_character_holder_id);

CREATE INDEX IF NOT EXISTS idx_artifacts_current_organization_holder_id
ON artifacts (current_organization_holder_id);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE artifacts IS
'One row per named artifact/relic/object with current known
holder/location pointers and lifecycle state.';

COMMENT ON COLUMN artifacts.artifact_id IS
'Primary key for this artifact row (UUID).';

COMMENT ON COLUMN artifacts.artifact_name IS
'Canonical artifact name.';

COMMENT ON COLUMN artifacts.artifact_type IS
'Artifact category (shard/weapon/ship/relic/etc.).';

COMMENT ON COLUMN artifacts.artifact_summary IS
'Short summary for this artifact.';

COMMENT ON COLUMN artifacts.artifact_details IS
'Optional long-form details or lore notes for this artifact.';

COMMENT ON COLUMN artifacts.origin_event_id IS
'Event where this artifact originated.';

COMMENT ON COLUMN artifacts.current_location_id IS
'Current or last known location pointer.';

COMMENT ON COLUMN artifacts.current_character_holder_id IS
'Current or last known character holder pointer.';

COMMENT ON COLUMN artifacts.current_organization_holder_id IS
'Current or last known organization holder pointer.';

COMMENT ON COLUMN artifacts.artifact_status IS
'Artifact lifecycle state (extant/lost/destroyed/sealed/unknown).';

COMMENT ON COLUMN artifacts.is_legendary IS
'Whether this artifact is primarily legendary.';

COMMENT ON COLUMN artifacts.is_divine IS
'Whether this artifact is divine.';

COMMENT ON COLUMN artifacts.is_disputed IS
'Whether artifact identity/history is disputed.';

COMMENT ON COLUMN artifacts.source_confidence IS
'Confidence score in [0.0, 1.0] for this artifact assertion.';

COMMENT ON COLUMN artifacts.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN artifacts.updated_at IS
'UTC timestamp recording row update.';

COMMENT ON INDEX idx_artifacts_artifact_type IS
'Index to accelerate filtering by artifact category.';

COMMENT ON INDEX idx_artifacts_artifact_status IS
'Index to accelerate filtering by artifact lifecycle state.';

COMMENT ON INDEX idx_artifacts_current_location_id IS
'Index to accelerate lookup by current/last-known artifact location.';

COMMENT ON INDEX idx_artifacts_current_character_holder_id IS
'Index to accelerate lookup by current/last-known character holder.';

COMMENT ON INDEX idx_artifacts_current_organization_holder_id IS
'Index to accelerate lookup by current/last-known organization holder.';
