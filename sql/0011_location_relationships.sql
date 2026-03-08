-- =============================================================================
-- 0011_location_relationships.sql
--
-- Purpose
--   Store directed semantic relationships between canonical locations in the
--   world-state schema. This table exists to represent non-alias, non-event
--   structural facts such as containment, adjacency, directional position,
--   hydrological flow, and route connectivity between place entities.
--
-- Row semantics
--   One row represents one directed relationship assertion from a left location
--   to a right location under a specific relationship type, optionally bounded
--   by a start and end era plus year-in-era range.
--
-- Conventions
--   - Relationships are directed, so inverse semantics such as `contains` and
--     `part_of` must be modeled explicitly rather than inferred automatically.
--   - Temporal validity is expressed with optional era FKs plus nonnegative
--     year-in-era integers instead of a single absolute date type.
--   - `source_confidence` is a normalized numeric score on `[0.0, 1.0]` for the
--     asserted relation fact.
--
-- Keys & constraints
--   - Primary key: `(left_location_id, right_location_id, relationship_type)`
--   - Natural keys / uniqueness: a given directed location pair can appear at
--     most once for a given relationship semantic.
--   - Checks: no self-loops; `relationship_type` restricted to the allowed
--     structural relation categories; `source_confidence` constrained to
--     `[0, 1]`; `start_year` and `end_year` must be nonnegative when present;
--     `notes` must be nonblank when present.
--
-- Relationships
--   - Owns FKs to `locations(location_id)` twice, through `left_location_id`
--     and `right_location_id`, plus optional FKs to `eras(era_id)` and
--     `events(event_id)` for validity and lifecycle anchoring.
--   - Downstream traversal, map generation, world-state reasoning, and query
--     logic should join through the two location endpoints to interpret the
--     directed graph of place-to-place structure.
--
-- Audit & provenance
--   This table records creation time via `created_at` and lightweight
--   confidence and note fields, but it does not store full extraction lineage,
--   adjudication history, or source-document provenance. Detailed provenance
--   should live in higher-level ingestion or event-sourcing tables when needed.
--
-- Performance
--   Secondary indexes on `right_location_id` and `relationship_type` support
--   reverse-edge traversal and semantic filtering over the location graph.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   expanded allowed relationship types over changing the meaning of existing
--   edge directions, temporal fields, or confidence semantics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS location_relationships (

    -- =========
    -- Endpoints
    -- =========

    -- Source location in this directed relation.
    left_location_id UUID NOT NULL REFERENCES locations (location_id),

    -- Target location in this directed relation.
    right_location_id UUID NOT NULL REFERENCES locations (location_id),

    -- Relation semantic.
    relationship_type TEXT NOT NULL,

    -- Optional notes.
    notes TEXT,

    -- Confidence score in [0.0, 1.0].
    source_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,

    -- Optional temporal start era.
    start_era_id UUID REFERENCES eras (era_id),

    -- Optional temporal start year-in-era.
    start_year INTEGER,

    -- Optional temporal end era.
    end_era_id UUID REFERENCES eras (era_id),

    -- Optional temporal end year-in-era.
    end_year INTEGER,

    -- Event that established this relation.
    established_by_event_id UUID REFERENCES events (event_id),

    -- Event that ended this relation.
    ended_by_event_id UUID REFERENCES events (event_id),

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT location_relationships_pk
    PRIMARY KEY (left_location_id, right_location_id, relationship_type),

    CONSTRAINT location_relationships_chk_no_self_loop
    CHECK (left_location_id <> right_location_id),

    CONSTRAINT location_relationships_chk_relationship_type
    CHECK (
        relationship_type IN (
            'contains',
            'part_of',
            'adjacent_to',
            'upstream_of',
            'downstream_of',
            'north_of',
            'south_of',
            'east_of',
            'west_of',
            'nearby',
            'connected_by_route',
            'separated_by'
        )
    ),

    CONSTRAINT location_relationships_chk_source_confidence_range
    CHECK (source_confidence >= 0 AND source_confidence <= 1),

    CONSTRAINT location_relationships_chk_year_nonnegative
    CHECK (
        (start_year IS NULL OR start_year >= 0)
        AND (end_year IS NULL OR end_year >= 0)
    ),

    CONSTRAINT location_relationships_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_location_relationships_right_location_id
ON location_relationships (right_location_id);

CREATE INDEX IF NOT EXISTS idx_location_relationships_relationship_type
ON location_relationships (relationship_type);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE location_relationships IS
'Directed location-to-location relationships
(contains, adjacent_to, directional, hydrological, etc.).';

COMMENT ON COLUMN location_relationships.left_location_id IS
'Source location in this directed relation.';

COMMENT ON COLUMN location_relationships.right_location_id IS
'Target location in this directed relation.';

COMMENT ON COLUMN location_relationships.relationship_type IS
'Relation semantic for this location pair.';

COMMENT ON COLUMN location_relationships.notes IS
'Optional notes for this relation.';

COMMENT ON COLUMN location_relationships.source_confidence IS
'Confidence score in [0.0, 1.0] for this relation assertion.';

COMMENT ON COLUMN location_relationships.start_era_id IS
'Optional start era for relation validity.';

COMMENT ON COLUMN location_relationships.start_year IS
'Optional start year-in-era for relation validity.';

COMMENT ON COLUMN location_relationships.end_era_id IS
'Optional end era for relation validity.';

COMMENT ON COLUMN location_relationships.end_year IS
'Optional end year-in-era for relation validity.';

COMMENT ON COLUMN location_relationships.established_by_event_id IS
'Event that established this relation.';

COMMENT ON COLUMN location_relationships.ended_by_event_id IS
'Event that ended this relation.';

COMMENT ON COLUMN location_relationships.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON INDEX idx_location_relationships_right_location_id IS
'Index to accelerate reverse traversal of location relationships.';

COMMENT ON INDEX idx_location_relationships_relationship_type IS
'Index to accelerate filtering by location relationship semantic.';
