-- =============================================================================
-- 0036_llm_functions.sql
--
-- Purpose
--   Store canonical LLM-function registry entries for the assistant runtime.
--   This table exists to give planners, retrieval layers, and operational
--   tooling a durable metadata surface over available model-backed functions
--   without forcing every LLM function descriptor into the planner context.
--
-- Row semantics
--   One row represents one canonical model-backed function definition exposed
--   by the host runtime, not a model invocation, prompt trace, completion log,
--   or per-session execution outcome.
--
-- Conventions
--   - `function_name` is the stable runtime-visible identifier and must be
--     nonblank after trimming.
--   - `function_type` is a coarse semantic category used for retrieval and
--     routing, not a full substitute for the more specific meaning captured in
--     `function_summary`.
--   - `baml_module_name` is an optional source-contract hint for host-side
--     synchronization and debugging rather than a planner-facing requirement.
--   - Boolean flags are current registry metadata and do not capture temporal
--     rollout history, provider behavior drift, or per-request quality.
--
-- Keys & constraints
--   - Primary key: `llm_function_id`
--   - Natural keys / uniqueness: `function_name` is unique across canonical
--     LLM-function definitions.
--   - Checks: nonblank trimmed `function_name` and `function_summary`;
--     `function_type` and `cost_tier` restricted to allowed semantic values;
--     optional contract, module, model, and notes fields must be nonblank when
--     present.
--
-- Relationships
--   - This table does not own outbound foreign keys.
--   - Downstream planner-retrieval, model-discovery, operator-console, and
--     runtime-registry synchronization code should query this table on
--     `function_name`, `function_type`, or recursion/enablement flags to
--     locate suitable model-backed functions for a given task.
--
-- Audit & provenance
--   This table records row creation and update timestamps but does not store
--   invocation traces, token usage, quality scores, or provider-specific
--   response telemetry. Those concerns should live in higher-level telemetry
--   or audit tables when needed.
--
-- Performance
--   Secondary indexes on `function_type`, `returns_child_program`, and
--   `is_enabled` support registry browsing, recursive-call discovery, and
--   enabled-only candidate selection.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   widened allowed `function_type` values over changing the meaning of
--   existing names, recursion semantics, or enablement flags.
-- =============================================================================

CREATE TABLE IF NOT EXISTS llm_functions (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this LLM-function definition.
    llm_function_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Stable runtime-visible function identifier.
    function_name TEXT UNIQUE NOT NULL,

    -- Coarse LLM-function category used for retrieval/routing.
    function_type TEXT NOT NULL DEFAULT 'other',

    -- Short function summary for discovery and selection.
    function_summary TEXT NOT NULL,

    -- Optional structured-argument contract summary.
    argument_contract TEXT,

    -- Optional return-shape summary.
    return_contract TEXT,

    -- Optional BAML source module name.
    baml_module_name TEXT,

    -- Optional preferred model/provider family label.
    model_family TEXT,

    -- Relative planning/execution cost tier.
    cost_tier TEXT NOT NULL DEFAULT 'medium',

    -- Whether this function is expected to return a child REPL program.
    returns_child_program BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this function is expected to return structured output.
    requires_structured_output BOOLEAN NOT NULL DEFAULT TRUE,

    -- Whether this function is currently enabled for planner discovery/use.
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Optional free-text notes.
    notes TEXT,

    -- UTC timestamp recording row creation.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- UTC timestamp recording row update.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- ===========
    -- Constraints
    -- ===========

    CONSTRAINT llm_functions_chk_function_name_nonempty
    CHECK (length(btrim(function_name)) > 0),

    CONSTRAINT llm_functions_chk_function_summary_nonempty
    CHECK (length(btrim(function_summary)) > 0),

    CONSTRAINT llm_functions_chk_function_type
    CHECK (
        function_type IN (
            'planner',
            'recursive_planner',
            'parser',
            'summarizer',
            'extractor',
            'classifier',
            'generator',
            'retrieval_helper',
            'other'
        )
    ),

    CONSTRAINT llm_functions_chk_cost_tier
    CHECK (
        cost_tier IN (
            'low',
            'medium',
            'high'
        )
    ),

    CONSTRAINT llm_functions_chk_argument_contract_nonempty
    CHECK (
        argument_contract IS NULL
        OR length(btrim(argument_contract)) > 0
    ),

    CONSTRAINT llm_functions_chk_return_contract_nonempty
    CHECK (
        return_contract IS NULL
        OR length(btrim(return_contract)) > 0
    ),

    CONSTRAINT llm_functions_chk_baml_module_name_nonempty
    CHECK (
        baml_module_name IS NULL
        OR length(btrim(baml_module_name)) > 0
    ),

    CONSTRAINT llm_functions_chk_model_family_nonempty
    CHECK (model_family IS NULL OR length(btrim(model_family)) > 0),

    CONSTRAINT llm_functions_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_llm_functions_function_type
ON llm_functions (function_type);

CREATE INDEX IF NOT EXISTS idx_llm_functions_returns_child_program
ON llm_functions (returns_child_program);

CREATE INDEX IF NOT EXISTS idx_llm_functions_is_enabled
ON llm_functions (is_enabled);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE llm_functions IS
'One row per canonical model-backed function definition used for
planner discovery and runtime registry metadata.';

COMMENT ON COLUMN llm_functions.llm_function_id IS
'Primary key for this LLM-function definition row (UUID).';

COMMENT ON COLUMN llm_functions.function_name IS
'Stable runtime-visible LLM-function identifier.';

COMMENT ON COLUMN llm_functions.function_type IS
'Coarse LLM-function category for retrieval and routing.';

COMMENT ON COLUMN llm_functions.function_summary IS
'Short summary of what the model-backed function does and when to use it.';

COMMENT ON COLUMN llm_functions.argument_contract IS
'Optional summary of accepted structured arguments.';

COMMENT ON COLUMN llm_functions.return_contract IS
'Optional summary of return shape.';

COMMENT ON COLUMN llm_functions.baml_module_name IS
'Optional BAML source module name for host/runtime synchronization.';

COMMENT ON COLUMN llm_functions.model_family IS
'Optional preferred model/provider family label.';

COMMENT ON COLUMN llm_functions.cost_tier IS
'Relative planning/execution cost tier (low/medium/high).';

COMMENT ON COLUMN llm_functions.returns_child_program IS
'Whether this function is expected to return a child REPL program.';

COMMENT ON COLUMN llm_functions.requires_structured_output IS
'Whether this function is expected to return structured output.';

COMMENT ON COLUMN llm_functions.is_enabled IS
'Whether this function is currently enabled for planner discovery/use.';

COMMENT ON COLUMN llm_functions.notes IS
'Optional notes about function behavior, rollout, or operational caveats.';

COMMENT ON COLUMN llm_functions.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN llm_functions.updated_at IS
'UTC timestamp recording row update.';

COMMENT ON INDEX idx_llm_functions_function_type IS
'Index to accelerate discovery and filtering by LLM-function category.';

COMMENT ON INDEX idx_llm_functions_returns_child_program IS
'Index to accelerate discovery of recursive child-program generators.';

COMMENT ON INDEX idx_llm_functions_is_enabled IS
'Index to accelerate enabled-only LLM-function discovery queries.';
