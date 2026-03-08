-- =============================================================================
-- 0016_characters.sql
--
-- Purpose
--   Store canonical characters in the world-state schema. This table exists to
--   model persistent named persons, beings, and notable figures that can
--   participate in events, organizations, lineages, and narrative state.
--
-- Row semantics
--   One row represents one canonical character entity, not a relationship,
--   title-holding episode, organization membership, or event occurrence.
--
-- Conventions
--   - `character_name` is stored as free text but must be nonblank after
--     trimming.
--   - `created_at` and `updated_at` are UTC `TIMESTAMPTZ` audit fields, and the
--     boolean status flags are current-state summary attributes rather than
--     versioned historical facts.
--   - `is_divine` and `is_mortal` are not both allowed to be false, so each
--     character must be classified as divine, mortal, or both.
--
-- Keys & constraints
--   - Primary key: `character_id`
--   - Natural keys / uniqueness: `character_name` is unique across canonical
--     characters.
--   - Checks: nonblank trimmed `character_name` and `biography_summary`;
--     `age_years` must be nonnegative when present; `status_notes` must be
--     nonblank when present; `birth_event_id` and `death_event_id` cannot point
--     to the same event; `is_divine` and `is_mortal` cannot both be false.
--
-- Relationships
--   - Owns optional FKs to `events(event_id)` through `birth_event_id` and
--     `death_event_id`, plus an optional FK to
--     `organizations(organization_id)` through `lineage_organization_id`.
--   - Downstream alias, relationship, title, membership, participation, and
--     genealogy tables should join to this table on `character_id` to reference
--     the canonical character entity.
--
-- Audit & provenance
--   This table records row creation and update timestamps but does not store
--   source-document lineage, extraction metadata, or adjudication history.
--   Detailed provenance for character facts should live in higher-level
--   ingestion or event-sourcing tables when needed.
--
-- Performance
--   Secondary indexes on `lineage_organization_id`, `birth_event_id`, and
--   `death_event_id` support lineage-based lookup and event-to-character
--   traversal for lifecycle queries.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or new
--   relationship tables over changing the meaning of existing flags, lifecycle
--   event references, or canonical-name semantics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS characters (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for the character.
    character_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Canonical character name.
    character_name TEXT UNIQUE NOT NULL,

    -- Preferred display label if distinct from canonical name.
    display_name TEXT,

    -- Optional epithet.
    epithet TEXT,

    -- Species/people/race label.
    species TEXT,

    -- Sex/gender label as represented in lore.
    sex_or_gender TEXT,

    -- Optional age in years (if known).
    age_years INTEGER,

    -- Optional concise status notes.
    status_notes TEXT,

    -- Short biography summary.
    biography_summary TEXT NOT NULL,

    -- Birth event pointer.
    birth_event_id UUID REFERENCES events (event_id),

    -- Death event pointer.
    death_event_id UUID REFERENCES events (event_id),

    -- Optional lineage/house/clan pointer.
    lineage_organization_id UUID REFERENCES organizations (organization_id),

    -- Whether this figure is legendary.
    is_legendary BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this figure is disputed.
    is_disputed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this figure is divine.
    is_divine BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this figure is mortal.
    is_mortal BOOLEAN NOT NULL DEFAULT TRUE,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UTC timestamp recording row update.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT characters_chk_character_name_nonempty
    CHECK (length(btrim(character_name)) > 0),

    CONSTRAINT characters_chk_biography_summary_nonempty
    CHECK (length(btrim(biography_summary)) > 0),

    CONSTRAINT characters_chk_age_nonnegative
    CHECK (age_years IS NULL OR age_years >= 0),

    CONSTRAINT characters_chk_status_notes_nonempty
    CHECK (status_notes IS NULL OR length(btrim(status_notes)) > 0),

    CONSTRAINT characters_chk_birth_death_distinct
    CHECK (
        birth_event_id IS NULL
        OR death_event_id IS NULL
        OR birth_event_id <> death_event_id
    ),

    CONSTRAINT characters_chk_divine_mortal_not_both_false
    CHECK (is_divine = TRUE OR is_mortal = TRUE)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_characters_lineage_organization_id
ON characters (lineage_organization_id);

CREATE INDEX IF NOT EXISTS idx_characters_birth_event_id
ON characters (birth_event_id);

CREATE INDEX IF NOT EXISTS idx_characters_death_event_id
ON characters (death_event_id);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE characters IS
'One row per named person/being/notable figure,
with event pointers for birth/death and lineage hinting.';

COMMENT ON COLUMN characters.character_id IS
'Primary key for the character row (UUID).';

COMMENT ON COLUMN characters.character_name IS
'Canonical character name.';

COMMENT ON COLUMN characters.display_name IS
'Preferred display label if distinct from canonical name.';

COMMENT ON COLUMN characters.epithet IS
'Optional epithet for this character.';

COMMENT ON COLUMN characters.species IS
'Species/people/race label for this character.';

COMMENT ON COLUMN characters.sex_or_gender IS
'Sex/gender label as represented in lore.';

COMMENT ON COLUMN characters.age_years IS
'Optional age in years if known.';

COMMENT ON COLUMN characters.status_notes IS
'Optional concise status notes.';

COMMENT ON COLUMN characters.biography_summary IS
'Short biography summary.';

COMMENT ON COLUMN characters.birth_event_id IS
'Event pointer for birth.';

COMMENT ON COLUMN characters.death_event_id IS
'Event pointer for death.';

COMMENT ON COLUMN characters.lineage_organization_id IS
'Optional pointer to lineage/house/clan organization.';

COMMENT ON COLUMN characters.is_legendary IS
'Whether this figure is legendary.';

COMMENT ON COLUMN characters.is_disputed IS
'Whether this figure is disputed.';

COMMENT ON COLUMN characters.is_divine IS
'Whether this figure is divine.';

COMMENT ON COLUMN characters.is_mortal IS
'Whether this figure is mortal.';

COMMENT ON COLUMN characters.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN characters.updated_at IS
'UTC timestamp recording row update.';

COMMENT ON INDEX idx_characters_lineage_organization_id IS
'Index to accelerate lookup of characters by lineage/house/clan.';

COMMENT ON INDEX idx_characters_birth_event_id IS
'Index to accelerate birth-event to character lookups.';

COMMENT ON INDEX idx_characters_death_event_id IS
'Index to accelerate death-event to character lookups.';
