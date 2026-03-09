-- =============================================================================
-- 0029_agreement_organizations.sql
--
-- Purpose
--   Define the join table that records which organizations participate in each
--   agreement and in what capacity. This exists so agreement-level world-state
--   facts can represent multi-party organizational involvement without
--   overloading the core agreements table.
--
-- Row semantics
--   One row represents one organization-to-agreement participation fact for a
--   specific role_type. This is a relational fact table, not an entity table:
--   the same agreement may have multiple organizations, and the same
--   organization may appear in multiple agreements under different roles.
--
-- Conventions
--   - agreement_id and organization_id are UUID foreign keys and follow the
--     repository's standard surrogate-key conventions.
--   - role_type is stored as lowercase TEXT and constrained to a closed
--     enum-like set via CHECK rather than a dedicated Postgres ENUM type.
--   - notes is optional free text but, when present, must be non-blank after
--     trimming.
--
-- Keys & constraints
--   - Primary key: (agreement_id, organization_id, role_type)
--   - Natural keys / uniqueness: The schema allows the same organization to be
--     attached to the same agreement more than once only when the role_type
--     differs.
--   - Checks: role_type must be one of signatory, guarantor, enforcer,
--     beneficiary, mediator, or observer; notes must be NULL or trimmed
--     non-empty text.
--
-- Relationships
--   - Owns foreign keys to agreements(agreement_id) and
--     organizations(organization_id).
--   - Downstream joins should typically enter from agreements via agreement_id
--     to recover all participating organizations, or from organizations via
--     organization_id to recover all agreements in which an organization
--     participates.
--
-- Audit & provenance
--   This table stores only the current relational participation fact and an
--   optional local note. Source-document lineage, extraction metadata, and
--   broader ingestion provenance are expected to live in upstream pipeline logs
--   or dedicated provenance tables rather than here.
--
-- Performance
--   - The composite primary key supports uniqueness enforcement and agreement-
--     anchored lookups.
--   - Secondary index idx_agreement_organizations_organization_id supports
--     reverse lookups from an organization to all linked agreements.
--
-- Change management
--   Extend role semantics additively by widening the CHECK constraint and
--   keeping existing labels stable. Add new nullable columns or new indexes in
--   preference to changing key shape so downstream joins and loaders remain
--   compatible.
-- =============================================================================

CREATE TABLE IF NOT EXISTS agreement_organizations (

    -- ===========
    -- Identifiers
    -- ===========

    -- Agreement endpoint.
    agreement_id UUID NOT NULL REFERENCES agreements (agreement_id),

    -- Organization endpoint.
    organization_id UUID NOT NULL REFERENCES organizations (organization_id),

    -- Organization role in the agreement.
    role_type TEXT NOT NULL,

    -- Optional notes.
    notes TEXT,

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT agreement_organizations_pk
    PRIMARY KEY (agreement_id, organization_id, role_type),

    CONSTRAINT agreement_organizations_chk_role_type
    CHECK (
        role_type IN (
            'signatory',
            'guarantor',
            'enforcer',
            'beneficiary',
            'mediator',
            'observer'
        )
    ),

    CONSTRAINT agreement_organizations_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_agreement_organizations_organization_id
ON agreement_organizations (organization_id);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE agreement_organizations IS
'Organization participants in agreements with explicit role labels.';

COMMENT ON COLUMN agreement_organizations.agreement_id IS
'Agreement endpoint.';

COMMENT ON COLUMN agreement_organizations.organization_id IS
'Organization endpoint.';

COMMENT ON COLUMN agreement_organizations.role_type IS
'Organization role in the agreement (signatory/guarantor/etc.).';

COMMENT ON COLUMN agreement_organizations.notes IS
'Optional notes for this participant relation.';

COMMENT ON INDEX idx_agreement_organizations_organization_id IS
'Index to accelerate agreement lookups by organization participant.';
