-- =============================================================================
-- 0006_eras.sql
--
-- Purpose
--   Define the canonical list of historical eras within the campaign lore
--   to anchor world-state facts, event timestamps, and timeline-facing
--   displays. This table gives the rest of the schema a stable temporal
--   vocabulary so downstream records can refer to named periods rather
--   than repeating free-form era labels.
--
-- Row semantics
--   One row represents one named era in the campaign timeline, such as a
--   major historical age or narrative period. It is a reference entity,
--   not an event, observation, or world-state fact.
--
-- Conventions
--   - `era_code` and `era_name` are stored as canonical text labels and
--     must be non-blank after trimming.
--   - `created_at` is recorded as a UTC `TIMESTAMPTZ` using `NOW()` per
--     repository audit conventions.
--   - Era definitions are expected to be low-churn reference data;
--     changes should be deliberate because downstream facts may depend on
--     stable era meanings and ordering.
--
-- Keys & constraints
--   - Primary key: `era_id`
--   - Natural keys / uniqueness: `era_code`, `era_name`, and
--     `sort_order` are each unique so every era has one stable label and
--     one stable timeline position.
--   - Checks: trimmed `era_code` and `era_name` must be non-empty to
--     prevent placeholder or whitespace-only era records.
--
-- Relationships
--   - This table currently owns no foreign keys, but downstream temporal
--     tables are expected to reference `eras.era_id` when they need a
--     structured era dimension.
--   - Other tables should join to `eras` by `era_id` for relational
--     integrity, while `sort_order` supports ordered timeline renders and
--     chronological queries.
--
-- Audit & provenance
--   This table stores only lightweight provenance via `created_at`. It
--   does not record who inserted or revised an era, nor the narrative or
--   source document that motivated the definition; that richer lineage is
--   expected to live in migrations, seed data, or higher-level content
--   management workflows.
--
-- Performance
--   A secondary index on `sort_order` supports ordered timeline scans and
--   UI queries that list eras chronologically. Uniqueness constraints on
--   `era_code`, `era_name`, and `sort_order` also back common lookup and
--   validation paths.
--
-- Change management
--   Extend this schema in an add-only way where possible, especially once
--   downstream tables begin referencing `era_id`. Avoid reusing
--   `sort_order`, renaming canonical labels casually, or changing era
--   semantics in place without a coordinated data migration.
-- =============================================================================

CREATE TABLE IF NOT EXISTS eras (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this era definition.
    era_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Short era code (e.g., "E1", "E2").
    era_code TEXT UNIQUE NOT NULL,

    -- Canonical era name (e.g., "First Era").
    era_name TEXT UNIQUE NOT NULL,

    -- Ordering key for timeline sorting.
    sort_order SMALLINT UNIQUE NOT NULL,

    -- Optional human-readable summary for this era.
    summary TEXT,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT eras_chk_era_code_nonempty
    CHECK (length(btrim(era_code)) > 0),

    CONSTRAINT eras_chk_era_name_nonempty
    CHECK (length(btrim(era_name)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_eras_sort_order
ON eras (sort_order);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE eras IS
'One row per named timeline frame used to anchor world-state temporal fields.';

COMMENT ON COLUMN eras.era_id IS
'Primary key for the era definition (UUID).';

COMMENT ON COLUMN eras.era_code IS
'Short era code (e.g., E1, E2).';

COMMENT ON COLUMN eras.era_name IS
'Canonical era name (e.g., First Era).';

COMMENT ON COLUMN eras.sort_order IS
'Ordering key for timeline sorting across eras.';

COMMENT ON COLUMN eras.summary IS
'Optional human-readable summary of the era.';

COMMENT ON COLUMN eras.created_at IS
'UTC timestamp recording when this era row was created.';

COMMENT ON INDEX idx_eras_sort_order IS
'Index to accelerate era timeline ordering.';
