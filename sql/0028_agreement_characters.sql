-- =============================================================================
-- 0028_agreement_characters.sql
--
-- Purpose
--   Store role-specific links between canonical agreements and canonical
--   characters in the world-state schema. This table exists to represent which
--   characters signed, witnessed, guaranteed, mediated, or were otherwise
--   explicitly associated with an agreement.
--
-- Row semantics
--   One row represents one agreement-to-character participation fact under a
--   specific role type.
--
-- Conventions
--   - Relationships are directed from `agreement_id` to `character_id`, with
--     `role_type` carrying the semantic meaning of the character's involvement
--     in the agreement.
--   - This table is intentionally lightweight and does not model temporal
--     validity windows, signature ordering, or clause-level participation.
--   - `notes` is optional free text for role-specific qualifiers and must be
--     nonblank when present.
--
-- Keys & constraints
--   - Primary key: `(agreement_id, character_id, role_type)`
--   - Natural keys / uniqueness: a given character can appear at most once per
--     agreement for a given participation role.
--   - Checks: `role_type` restricted to the allowed agreement-participant role
--     categories; `notes` must be nonblank when present.
--
-- Relationships
--   - Owns FKs to `agreements(agreement_id)` and `characters(character_id)`.
--   - Downstream diplomacy, treaty interpretation, event reconstruction, and
--     participant-resolution logic should join through this table to identify
--     which canonical characters were involved in a given agreement and in what
--     capacity.
--
-- Audit & provenance
--   This table does not store row timestamps, source-document lineage,
--   extraction metadata, or adjudication history. Detailed provenance for
--   participant-role assignment should live in higher-level ingestion or
--   event-sourcing tables when needed.
--
-- Performance
--   A secondary index on `character_id` supports reverse lookup of agreements
--   by participating character.
--
-- Change management
--   Extend this schema additively: prefer widening the allowed `role_type`
--   domain or adding new nullable metadata columns over changing the meaning of
--   existing participation rows or endpoint semantics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS agreement_characters (

    -- ===========
    -- Identifiers
    -- ===========

    -- Agreement endpoint.
    agreement_id UUID NOT NULL REFERENCES agreements (agreement_id),

    -- Character endpoint.
    character_id UUID NOT NULL REFERENCES characters (character_id),

    -- Character role in the agreement.
    role_type TEXT NOT NULL,

    -- Optional notes.
    notes TEXT,

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT agreement_characters_pk
    PRIMARY KEY (agreement_id, character_id, role_type),

    CONSTRAINT agreement_characters_chk_role_type
    CHECK (
        role_type IN (
            'signatory',
            'witness',
            'guarantor',
            'mediator',
            'subject'
        )
    ),

    CONSTRAINT agreement_characters_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_agreement_characters_character_id
ON agreement_characters (character_id);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE agreement_characters IS
'Character participants in agreements with explicit role labels.';

COMMENT ON COLUMN agreement_characters.agreement_id IS
'Agreement endpoint.';

COMMENT ON COLUMN agreement_characters.character_id IS
'Character endpoint.';

COMMENT ON COLUMN agreement_characters.role_type IS
'Character role in the agreement (signatory/witness/etc.).';

COMMENT ON COLUMN agreement_characters.notes IS
'Optional notes for this participant relation.';

COMMENT ON INDEX idx_agreement_characters_character_id IS
'Index to accelerate agreement lookups by character participant.';
