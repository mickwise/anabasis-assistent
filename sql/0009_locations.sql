-- =============================================================================
-- 0009_locations.sql
--
-- Purpose
--   Store the canonical place dimension for the Anabasis world-state schema.
--   This table defines stable location entities such as continents, cities,
--   temples, vaults, and other named places so downstream tables can attach
--   events, factions, characters, and session-derived facts to a shared place
--   reference.
--
-- Row semantics
--   One row represents one canonical location entity, not a transient visit,
--   scene, rumor, or map annotation. A row is the durable identity of a place
--   in the world model, optionally linked into a containment hierarchy.
--
-- Conventions
--   - Location identity is surrogate-keyed by UUID, while `location_name`
--     serves as the canonical human-readable name and must be unique.
--   - `created_at` and `updated_at` are stored as UTC `TIMESTAMPTZ` values via
--     `NOW()` under repository timestamp conventions.
--   - Rows are intended to be updated in place as canonical place metadata is
--     refined; this table is not append-only and does not store historical
--     versions of a location record.
--
-- Keys & constraints
--   - Primary key: `location_id`
--   - Checks: non-empty trimmed `location_name` and `location_summary`,
--     enumerated `location_type`, and a self-parent guard preventing
--     `parent_location_id = location_id`
--
-- Relationships
--   - Owns self-referential FK `parent_location_id -> locations.location_id`
--     for containment hierarchies and optional event FKs
--     `founding_event_id -> events.event_id` and
--     `destruction_event_id -> events.event_id`.
--   - Downstream tables should join to `locations.location_id` when attaching
--     world facts to a canonical place; hierarchy-aware queries can recurse on
--     `parent_location_id` to move between local and enclosing geography.
--
-- Audit & provenance
--   This table stores only lightweight row timestamps and canonicalized place
--   attributes. It does not capture extraction lineage, source text spans,
--   adjudication history, or temporal revision history; those should live in
--   dedicated provenance, ingestion, or event/fact tables.
--
-- Performance
--   B-tree indexes on `location_type`, `parent_location_id`, and `is_active`
--   support common browse and filter patterns such as listing places by class,
--   traversing containment trees, and restricting queries to currently active
--   locations. No partitioning is used because this is a relatively small
--   dimension-style table.
--
-- Change management
--   Extend this schema in an additive way where possible: add nullable columns,
--   new indexes, or new downstream relationship tables without changing the
--   meaning of existing columns. If `location_type` needs new categories,
--   update the CHECK constraint carefully so existing loaders and enums remain
--   synchronized.
-- =============================================================================

CREATE TABLE IF NOT EXISTS locations (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for the location.
    location_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Canonical location name.
    location_name TEXT UNIQUE NOT NULL,

    -- Location class/category.
    location_type TEXT NOT NULL DEFAULT 'other',

    -- Canonical parent pointer (for containment hierarchy).
    parent_location_id UUID REFERENCES locations (location_id),

    -- Short location summary.
    location_summary TEXT NOT NULL,

    -- Optional geographic notes.
    geographic_notes TEXT,

    -- Optional political notes.
    political_notes TEXT,

    -- Whether this place is primarily legendary.
    is_legendary BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this place is ruined.
    is_ruined BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this place is currently active/inhabited.
    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    -- Founding event pointer.
    founding_event_id UUID REFERENCES events (event_id),

    -- Destruction/collapse event pointer.
    destruction_event_id UUID REFERENCES events (event_id),

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UTC timestamp recording row update.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT locations_chk_location_name_nonempty
    CHECK (length(btrim(location_name)) > 0),

    CONSTRAINT locations_chk_location_summary_nonempty
    CHECK (length(btrim(location_summary)) > 0),

    CONSTRAINT locations_chk_location_type
    CHECK (
        location_type IN (
            'world',
            'continent',
            'region',
            'river_valley',
            'forest',
            'plateau',
            'estuary',
            'island',
            'sea',
            'city',
            'port',
            'settlement',
            'fortress',
            'temple',
            'monastery',
            'vault',
            'tomb',
            'mountain_pass',
            'college',
            'other'
        )
    ),

    CONSTRAINT locations_chk_parent_not_self
    CHECK (parent_location_id IS NULL OR parent_location_id <> location_id)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_locations_location_type
ON locations (location_type);

CREATE INDEX IF NOT EXISTS idx_locations_parent_location_id
ON locations (parent_location_id);

CREATE INDEX IF NOT EXISTS idx_locations_is_active
ON locations (is_active);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE locations IS
'One row per canonical place entity (geographic or built),
with optional parent containment pointer.';

COMMENT ON COLUMN locations.location_id IS
'Primary key for the location row (UUID).';

COMMENT ON COLUMN locations.location_name IS
'Canonical location name.';

COMMENT ON COLUMN locations.location_type IS
'Location class/category (continent/city/vault/etc.).';

COMMENT ON COLUMN locations.parent_location_id IS
'Canonical parent location pointer for containment hierarchy.';

COMMENT ON COLUMN locations.location_summary IS
'Short summary of this location.';

COMMENT ON COLUMN locations.geographic_notes IS
'Optional geographic notes (terrain, climate, waterways, etc.).';

COMMENT ON COLUMN locations.political_notes IS
'Optional political notes (claims/disputes/context).';

COMMENT ON COLUMN locations.is_legendary IS
'Whether this place is primarily legendary.';

COMMENT ON COLUMN locations.is_ruined IS
'Whether this place is ruined.';

COMMENT ON COLUMN locations.is_active IS
'Whether this place is currently active/inhabited.';

COMMENT ON COLUMN locations.founding_event_id IS
'Event that founded or established this place.';

COMMENT ON COLUMN locations.destruction_event_id IS
'Event that destroyed or collapsed this place.';

COMMENT ON COLUMN locations.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN locations.updated_at IS
'UTC timestamp recording row update.';

COMMENT ON INDEX idx_locations_location_type IS
'Index to accelerate filtering and browsing by location type.';

COMMENT ON INDEX idx_locations_parent_location_id IS
'Index to accelerate hierarchical traversal of locations.';

COMMENT ON INDEX idx_locations_is_active IS
'Index to accelerate filtering by active/ruined location status.';
