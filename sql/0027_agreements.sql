-- =============================================================================
-- 0027_agreements.sql
--
-- Purpose
--   Store canonical agreements in the world-state schema. This table exists to
--   model named treaties, pacts, accords, ceasefires, charters, vassalage
--   arrangements, and other formalized compacts that can structure relations
--   between world entities over time.
--
-- Row semantics
--   One row represents one canonical agreement entity, not a party-specific
--   participation row, signature act, enforcement event, or clause-level term.
--
-- Conventions
--   - `agreement_name` is stored as free text but must be nonblank after
--     trimming.
--   - Temporal validity is expressed with optional era FKs plus nonnegative
--     year-in-era integers, and `start_is_approximate` or
--     `end_is_approximate` mark uncertain dating without requiring separate
--     fuzzy-date fields.
--   - `agreement_status` is a current-state summary attribute, while
--     `establishing_event_id` and `terminating_event_id` anchor lifecycle facts
--     when known.
--
-- Keys & constraints
--   - Primary key: `agreement_id`
--   - Natural keys / uniqueness: `agreement_name` is unique across canonical
--     agreements.
--   - Checks: nonblank trimmed `agreement_name` and `terms_summary`;
--     `agreement_type` and `agreement_status` restricted to allowed semantic
--     categories; `start_year` and `end_year` must be nonnegative when
--     present; `source_confidence` constrained to `[0, 1]`; `notes` must be
--     nonblank when present.
--
-- Relationships
--   - Owns optional FKs to `events(event_id)` through
--     `establishing_event_id` and `terminating_event_id`, plus optional FKs to
--     `eras(era_id)` through `start_era_id` and `end_era_id`.
--   - Downstream agreement-party, diplomacy, succession, conflict-resolution,
--     and event interpretation tables should join to this table on
--     `agreement_id` to reference the canonical agreement entity.
--
-- Audit & provenance
--   This table records row creation and update timestamps plus a lightweight
--   confidence score, but it does not store clause-level provenance,
--   signatory-level evidence, or adjudication history. Detailed provenance for
--   agreement facts should live in higher-level ingestion or event-sourcing
--   tables when needed.
--
-- Performance
--   Secondary indexes on `agreement_type`, `agreement_status`,
--   `(start_era_id, start_year)`, and `establishing_event_id` support category
--   filtering, temporal agreement queries, and traversal from lifecycle events.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   companion party or clause tables over changing the meaning of existing
--   lifecycle fields, temporal semantics, or canonical agreement identity.
-- =============================================================================

CREATE TABLE IF NOT EXISTS agreements (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this agreement.
    agreement_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Canonical agreement name.
    agreement_name TEXT UNIQUE NOT NULL,

    -- Agreement class/category.
    agreement_type TEXT NOT NULL DEFAULT 'treaty',

    -- Agreement lifecycle status.
    agreement_status TEXT NOT NULL DEFAULT 'active',

    -- Event where this agreement was established.
    establishing_event_id UUID REFERENCES events (event_id),

    -- Event where this agreement terminated/was superseded.
    terminating_event_id UUID REFERENCES events (event_id),

    -- Summary of terms.
    terms_summary TEXT NOT NULL,

    -- Optional notes.
    notes TEXT,

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

    -- Confidence score in [0.0, 1.0].
    source_confidence NUMERIC(4, 3) NOT NULL DEFAULT 0.500,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UTC timestamp recording row update.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT agreements_chk_agreement_name_nonempty
    CHECK (length(btrim(agreement_name)) > 0),

    CONSTRAINT agreements_chk_terms_summary_nonempty
    CHECK (length(btrim(terms_summary)) > 0),

    CONSTRAINT agreements_chk_agreement_type
    CHECK (
        agreement_type IN (
            'treaty',
            'pact',
            'accord',
            'ceasefire',
            'trade_agreement',
            'alliance',
            'vassalage',
            'religious_compact',
            'charter',
            'other'
        )
    ),

    CONSTRAINT agreements_chk_agreement_status
    CHECK (
        agreement_status IN (
            'draft',
            'active',
            'expired',
            'broken',
            'superseded'
        )
    ),

    CONSTRAINT agreements_chk_year_nonnegative
    CHECK (
        (start_year IS NULL OR start_year >= 0)
        AND (end_year IS NULL OR end_year >= 0)
    ),

    CONSTRAINT agreements_chk_source_confidence_range
    CHECK (source_confidence >= 0 AND source_confidence <= 1),

    CONSTRAINT agreements_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_agreements_agreement_type
ON agreements (agreement_type);

CREATE INDEX IF NOT EXISTS idx_agreements_agreement_status
ON agreements (agreement_status);

CREATE INDEX IF NOT EXISTS idx_agreements_start_era_year
ON agreements (start_era_id, start_year);

CREATE INDEX IF NOT EXISTS idx_agreements_establishing_event_id
ON agreements (establishing_event_id);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE agreements IS
'One row per named agreement/treaty/pact with
temporal validity and establishing event linkage.';

COMMENT ON COLUMN agreements.agreement_id IS
'Primary key for this agreement row (UUID).';

COMMENT ON COLUMN agreements.agreement_name IS
'Canonical agreement name.';

COMMENT ON COLUMN agreements.agreement_type IS
'Agreement category (treaty/pact/accord/etc.).';

COMMENT ON COLUMN agreements.agreement_status IS
'Agreement lifecycle status (active/expired/broken/etc.).';

COMMENT ON COLUMN agreements.establishing_event_id IS
'Event where this agreement was established.';

COMMENT ON COLUMN agreements.terminating_event_id IS
'Event where this agreement terminated or was superseded.';

COMMENT ON COLUMN agreements.terms_summary IS
'Summary of terms and obligations.';

COMMENT ON COLUMN agreements.notes IS
'Optional notes for this agreement.';

COMMENT ON COLUMN agreements.start_era_id IS
'Optional start era for agreement validity.';

COMMENT ON COLUMN agreements.start_year IS
'Optional start year-in-era for agreement validity.';

COMMENT ON COLUMN agreements.start_is_approximate IS
'Whether agreement start timing is approximate.';

COMMENT ON COLUMN agreements.end_era_id IS
'Optional end era for agreement validity.';

COMMENT ON COLUMN agreements.end_year IS
'Optional end year-in-era for agreement validity.';

COMMENT ON COLUMN agreements.end_is_approximate IS
'Whether agreement end timing is approximate.';

COMMENT ON COLUMN agreements.source_confidence IS
'Confidence score in [0.0, 1.0] for this agreement assertion.';

COMMENT ON COLUMN agreements.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN agreements.updated_at IS
'UTC timestamp recording row update.';

COMMENT ON INDEX idx_agreements_agreement_type IS
'Index to accelerate filtering by agreement category.';

COMMENT ON INDEX idx_agreements_agreement_status IS
'Index to accelerate filtering by agreement lifecycle status.';

COMMENT ON INDEX idx_agreements_start_era_year IS
'Index to accelerate temporal agreement queries by era/year.';

COMMENT ON INDEX idx_agreements_establishing_event_id IS
'Index to accelerate traversal from establishing events to agreements.';
