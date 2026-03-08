-- =============================================================================
-- 0014_organization_relationships.sql
--
-- Purpose
--   Store directed semantic relationships between canonical organizations in
--   the world-state schema. This table exists to represent non-alias,
--   non-membership, non-event structural facts such as alliance, rivalry,
--    vassalage, succession, tributary status, merger lineage, and council-level
--   coordination between organization entities.
--
-- Row semantics
--   One row represents one directed relationship assertion from a left
--   organization to a right organization under a specific relationship type,
--   optionally bounded by a start and end era plus year-in-era range.
--
-- Conventions
--   - Relationships are directed, so inverse semantics such as `vassal_of` and
--     `overlord_of` must be modeled explicitly rather than inferred
--     automatically.
--   - Temporal validity is expressed with optional era FKs plus nonnegative
--     year-in-era integers instead of a single absolute date type.
--   - `source_confidence` is a normalized numeric score on `[0.0, 1.0]` for the
--     asserted relation fact.
--
-- Keys & constraints
--   - Primary key: `(left_organization_id, right_organization_id,
--     relationship_type)`
--   - Natural keys / uniqueness: a given directed organization pair can appear
--     at most once for a given relationship semantic.
--   - Checks: no self-loops; `relationship_type` restricted to the allowed
--     inter-organization relation categories; `source_confidence` constrained
--     to `[0, 1]`; `start_year` and `end_year` must be nonnegative when
--     present; `notes` must be nonblank when present.
--
-- Relationships
--   - Owns FKs to `organizations(organization_id)` twice, through
--     `left_organization_id` and `right_organization_id`, plus optional FKs to
--     `eras(era_id)` and `events(event_id)` for validity and lifecycle
--     anchoring.
--   - Downstream diplomacy, conflict, succession, world-state reasoning, and
--     graph traversal logic should join through the two organization endpoints
--     to interpret the directed organization-to-organization structure.
--
-- Audit & provenance
--   This table records creation time via `created_at` and lightweight
--   confidence and note fields, but it does not store full extraction lineage,
--   adjudication history, or source-document provenance. Detailed provenance
--   should live in higher-level ingestion or event-sourcing tables when needed.
--
-- Performance
--   Secondary indexes on `right_organization_id` and `relationship_type`
--   support reverse-edge traversal and semantic filtering over the
--   organization relationship graph.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   expanded allowed relationship types over changing the meaning of existing
--   edge directions, temporal fields, or confidence semantics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS organization_relationships (

    -- =========
    -- Endpoints
    -- =========

    -- Source organization in this directed relation.
    left_organization_id UUID NOT NULL REFERENCES organizations (
        organization_id
    ),

    -- Target organization in this directed relation.
    right_organization_id UUID NOT NULL REFERENCES organizations (
        organization_id
    ),

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

    CONSTRAINT organization_relationships_pk
    PRIMARY KEY (
        left_organization_id,
        right_organization_id,
        relationship_type
    ),

    CONSTRAINT organization_relationships_chk_no_self_loop
    CHECK (left_organization_id <> right_organization_id),

    CONSTRAINT organization_relationships_chk_relationship_type
    CHECK (
        relationship_type IN (
            'allied_with',
            'at_war_with',
            'vassal_of',
            'overlord_of',
            'rival_of',
            'trade_partner_of',
            'tributary_of',
            'founded_from',
            'successor_of',
            'merged_into',
            'split_from',
            'member_of_council_with'
        )
    ),

    CONSTRAINT organization_relationships_chk_source_confidence_range
    CHECK (source_confidence >= 0 AND source_confidence <= 1),

    CONSTRAINT organization_relationships_chk_year_nonnegative
    CHECK (
        (start_year IS NULL OR start_year >= 0)
        AND (end_year IS NULL OR end_year >= 0)
    ),

    CONSTRAINT organization_relationships_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_organization_relationships_right_org_id
ON organization_relationships (right_organization_id);

CREATE INDEX IF NOT EXISTS idx_organization_relationships_relationship_type
ON organization_relationships (relationship_type);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE organization_relationships IS
'Directed organization-to-organization relationships
(alliances, vassalage, rivalry, succession, etc.).';

COMMENT ON COLUMN organization_relationships.left_organization_id IS
'Source organization in this directed relation.';

COMMENT ON COLUMN organization_relationships.right_organization_id IS
'Target organization in this directed relation.';

COMMENT ON COLUMN organization_relationships.relationship_type IS
'Relation semantic for this organization pair.';

COMMENT ON COLUMN organization_relationships.notes IS
'Optional notes for this relation.';

COMMENT ON COLUMN organization_relationships.source_confidence IS
'Confidence score in [0.0, 1.0] for this relation assertion.';

COMMENT ON COLUMN organization_relationships.start_era_id IS
'Optional start era for relation validity.';

COMMENT ON COLUMN organization_relationships.start_year IS
'Optional start year-in-era for relation validity.';

COMMENT ON COLUMN organization_relationships.end_era_id IS
'Optional end era for relation validity.';

COMMENT ON COLUMN organization_relationships.end_year IS
'Optional end year-in-era for relation validity.';

COMMENT ON COLUMN organization_relationships.established_by_event_id IS
'Event that established this relation.';

COMMENT ON COLUMN organization_relationships.ended_by_event_id IS
'Event that ended this relation.';

COMMENT ON COLUMN organization_relationships.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON INDEX idx_organization_relationships_right_org_id IS
'Index to accelerate reverse traversal of organization relationships.';

COMMENT ON INDEX idx_organization_relationships_relationship_type IS
'Index to accelerate filtering by organization relationship semantic.';
