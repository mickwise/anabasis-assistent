-- =============================================================================
-- 0035_tools.sql
--
-- Purpose
--   Store canonical host-tool registry entries for the assistant runtime. This
--   table exists to give planners, retrieval layers, and operational tooling a
--   durable metadata surface over available deterministic tools without
--   requiring every tool descriptor to be inlined into the model context.
--
-- Row semantics
--   One row represents one canonical callable tool definition exposed by the
--   host runtime, not a tool invocation, audit event, execution trace, or
--   per-session availability override.
--
-- Conventions
--   - `tool_name` is the stable runtime-visible identifier and must be
--     nonblank after trimming.
--   - `tool_type` is a coarse semantic category used for retrieval and routing,
--     not a full substitute for the more specific meaning captured in
--     `tool_summary`.
--   - `module_path` and `callable_name` are optional implementation hints for
--     host-side resolution, debugging, or synchronization; planners should not
--     treat them as authoritative executable code.
--   - Boolean flags are current registry metadata and do not capture temporal
--     change history or per-request authorization outcomes.
--
-- Keys & constraints
--   - Primary key: `tool_id`
--   - Natural keys / uniqueness: `tool_name` is unique across canonical tool
--     definitions.
--   - Checks: nonblank trimmed `tool_name` and `tool_summary`; `tool_type` and
--     `cost_tier` restricted to allowed semantic values; optional
--     implementation pointers and notes must be nonblank when present.
--
-- Relationships
--   - This table does not own outbound foreign keys.
--   - Downstream planner-retrieval, tool-discovery, operator-console, and
--     runtime-registry synchronization code should join or query this table on
--     `tool_name` or `tool_type` to locate candidate tools for a given task.
--
-- Audit & provenance
--   This table records row creation and update timestamps but does not store
--   invocation history, latency metrics, prompt-level usage traces, or rollout
--   history. Those concerns should live in higher-level telemetry or audit
--   tables when needed.
--
-- Performance
--   Secondary indexes on `tool_type`, `is_enabled`, and `cost_tier` support
--   registry browsing, filtered discovery, and low-cost candidate selection.
--
-- Change management
--   Extend this schema additively: prefer new nullable metadata columns or
--   widened allowed `tool_type` values over changing the meaning of existing
--   names, flags, or implementation-pointer semantics.
-- =============================================================================

CREATE TABLE IF NOT EXISTS tools (

    -- ===========
    -- Identifiers
    -- ===========

    -- Surrogate primary key for this tool definition.
    tool_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Stable runtime-visible tool identifier.
    tool_name TEXT UNIQUE NOT NULL,

    -- Coarse tool category used for retrieval/routing.
    tool_type TEXT NOT NULL DEFAULT 'other',

    -- Short tool summary for discovery and selection.
    tool_summary TEXT NOT NULL,

    -- Optional structured-argument contract summary.
    argument_contract TEXT,

    -- Optional return-shape or side-effect summary.
    return_contract TEXT,

    -- Optional implementation module path.
    module_path TEXT,

    -- Optional implementation callable name.
    callable_name TEXT,

    -- Relative planning/execution cost tier.
    cost_tier TEXT NOT NULL DEFAULT 'medium',

    -- Whether the tool is deterministic for the same inputs.
    is_deterministic BOOLEAN NOT NULL DEFAULT TRUE,

    -- Whether the tool performs externally visible side effects.
    is_side_effecting BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether the tool normally requires network access.
    requires_network BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether the tool generally requires elevated DM/admin privileges.
    requires_dm_privileges BOOLEAN NOT NULL DEFAULT FALSE,

    -- Whether this tool is currently enabled for planner discovery/use.
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

    CONSTRAINT tools_chk_tool_name_nonempty
    CHECK (length(btrim(tool_name)) > 0),

    CONSTRAINT tools_chk_tool_summary_nonempty
    CHECK (length(btrim(tool_summary)) > 0),

    CONSTRAINT tools_chk_tool_type
    CHECK (
        tool_type IN (
            'retrieval',
            'ingestion',
            'parser',
            'database',
            'world_state',
            'computation',
            'file_system',
            'image',
            'communication',
            'orchestration',
            'other'
        )
    ),

    CONSTRAINT tools_chk_cost_tier
    CHECK (
        cost_tier IN (
            'low',
            'medium',
            'high'
        )
    ),

    CONSTRAINT tools_chk_argument_contract_nonempty
    CHECK (
        argument_contract IS NULL
        OR length(btrim(argument_contract)) > 0
    ),

    CONSTRAINT tools_chk_return_contract_nonempty
    CHECK (
        return_contract IS NULL
        OR length(btrim(return_contract)) > 0
    ),

    CONSTRAINT tools_chk_module_path_nonempty
    CHECK (module_path IS NULL OR length(btrim(module_path)) > 0),

    CONSTRAINT tools_chk_callable_name_nonempty
    CHECK (callable_name IS NULL OR length(btrim(callable_name)) > 0),

    CONSTRAINT tools_chk_notes_nonempty
    CHECK (notes IS NULL OR length(btrim(notes)) > 0)
);

-- =======
-- Indexes
-- =======

CREATE INDEX IF NOT EXISTS idx_tools_tool_type
ON tools (tool_type);

CREATE INDEX IF NOT EXISTS idx_tools_is_enabled
ON tools (is_enabled);

CREATE INDEX IF NOT EXISTS idx_tools_cost_tier
ON tools (cost_tier);

-- ==================
-- Comments (catalog)
-- ==================

COMMENT ON TABLE tools IS
'One row per canonical host tool definition used for
planner discovery and runtime registry metadata.';

COMMENT ON COLUMN tools.tool_id IS
'Primary key for this tool definition row (UUID).';

COMMENT ON COLUMN tools.tool_name IS
'Stable runtime-visible tool identifier.';

COMMENT ON COLUMN tools.tool_type IS
'Coarse tool category for retrieval and routing.';

COMMENT ON COLUMN tools.tool_summary IS
'Short summary of what the tool does and when to use it.';

COMMENT ON COLUMN tools.argument_contract IS
'Optional summary of accepted structured arguments.';

COMMENT ON COLUMN tools.return_contract IS
'Optional summary of return shape or side effects.';

COMMENT ON COLUMN tools.module_path IS
'Optional implementation module path for host/runtime synchronization.';

COMMENT ON COLUMN tools.callable_name IS
'Optional implementation callable name for host/runtime synchronization.';

COMMENT ON COLUMN tools.cost_tier IS
'Relative planning/execution cost tier (low/medium/high).';

COMMENT ON COLUMN tools.is_deterministic IS
'Whether this tool is deterministic for the same inputs.';

COMMENT ON COLUMN tools.is_side_effecting IS
'Whether this tool produces externally visible side effects.';

COMMENT ON COLUMN tools.requires_network IS
'Whether this tool normally requires network access.';

COMMENT ON COLUMN tools.requires_dm_privileges IS
'Whether this tool generally requires elevated DM/admin privileges.';

COMMENT ON COLUMN tools.is_enabled IS
'Whether this tool is currently enabled for planner discovery/use.';

COMMENT ON COLUMN tools.notes IS
'Optional notes about tool behavior, rollout, or operational caveats.';

COMMENT ON COLUMN tools.created_at IS
'UTC timestamp recording row creation.';

COMMENT ON COLUMN tools.updated_at IS
'UTC timestamp recording row update.';

COMMENT ON INDEX idx_tools_tool_type IS
'Index to accelerate discovery and filtering by tool category.';

COMMENT ON INDEX idx_tools_is_enabled IS
'Index to accelerate enabled-only tool discovery queries.';

COMMENT ON INDEX idx_tools_cost_tier IS
'Index to accelerate cost-aware tool selection queries.';
