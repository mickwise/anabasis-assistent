// =============================================================================
// planner_entrypoint.baml
//
// Purpose
// -------
// Define the top-level planner entrypoint for natural-language Discord messages
// in the D&D assistant.
//
// Key behaviors
// -------------
// - Accepts a raw user message plus normalized Discord context.
// - Accepts a world-state snapshot string that may be stubbed initially and
//   expanded later as the campaign-state system matures.
// - Produces a structured planner decision rather than executing tools.
// - Allows the planner to either:
//   (1) ask for clarification,
//   (2) answer directly without tools, or
//   (3) emit one or more tool calls for downstream execution.
//
// Conventions
// -----------
// - This file is planner-only. It does not execute tools.
// - The world state is treated as an external structured summary, not as the
//   entire source of truth.
// - The planner should prefer using tools when the request requires persistent
//   state updates, file ingestion, or database-backed retrieval.
// - The planner may answer directly only when no tool is needed.
//
// Downstream usage
// ----------------
// Discord free-text messages that mention the bot should be routed here.
// The resulting PlannerDecision should then be passed into a separate execution
// layer that validates and runs the requested tool calls.
//
// Notes
// -----
// - This entrypoint is intentionally compatible with an initial stubbed
//   `world_state_snapshot` string.
// - Later, the snapshot can be replaced or supplemented by richer event-based
//   retrieval tools without changing the planner contract.
// =============================================================================


class ToolCall {
    // -----------------------------------------------------------------------------
    // ToolCall
    //
    // Purpose
    // -------
    // Represent one planner-selected tool invocation.
    // -----------------------------------------------------------------------------
    tool_name string @description("Name of the downstream tool the executor should invoke (stable identifier, not natural language).")
    arguments string @description("Serialized arguments payload for the tool call (typically JSON or another tool-specific encoding).")
    reason string? @description("Optional brief justification for why this tool call is needed, for debugging and audit logs.")
    requires_dm_privileges bool @description("True if this tool call should only be executed when the requester has DM privileges in the current Discord context.")
}


class PlannerDecision {
    // -----------------------------------------------------------------------------
    // PlannerDecision
    //
    // Purpose
    // -------
    // Represent the structured output of the planner.
    // -----------------------------------------------------------------------------
    route string @description("Planner routing decision: one of 'message_only', 'clarification', or 'tool_calls'.")
    assistant_message string? @description("Natural-language message to send back immediately when route='message_only'.")
    needs_clarification bool @description("True when the planner cannot safely select tools or answer without asking a follow-up question.")
    clarification_question string? @description("Follow-up question to ask the user when needs_clarification=true and route='clarification'.")
    tool_calls ToolCall[] @description("Ordered list of tool calls the executor should validate and run when route='tool_calls'.")
}


function PlanDiscordMessage(
  user_message: string,
  discord_context: string,
  attachment_summary: string,
  world_state_snapshot: string,
  planner_instructions: string?
) -> PlannerDecision {
    // -----------------------------------------------------------------------------
    // plan_discord_message
    //
    // Summary
    // -------
    // Convert a natural-language Discord request into a structured planning decision.
    //
    // Parameters
    // ----------
    // user_message : string
    //     Raw natural-language message sent by the user.
    // discord_context : string
    //     Normalized serialized Discord context, including DM-vs-guild status,
    //     privilege flags, and any relevant metadata.
    // attachment_summary : string
    //     Structured summary of attachment presence and types.
    // world_state_snapshot : string
    //     Retrieved or synthesized world-state snapshot relevant to the request.
    // planner_instructions : string?
    //     Optional extra planner instructions from the host runtime.
    //
    // Returns
    // -------
    // PlannerDecision
    //     Structured planner output to be consumed by a separate execution layer.
    //
    // Notes
    // -----
    // - None
    // -----------------------------------------------------------------------------
    client CustomOllama
    prompt #"
    {{ _.role("system") }}

    You are the planner for a Discord-based D&D campaign assistant.

    Your job is to decide what should happen next.
    You do NOT execute tools.
    You do NOT mutate state directly.
    You only produce a structured PlannerDecision.

    Core planning rules
    -------------------
    1. Treat Discord context as authoritative for whether the message came from:
    - a guild/server context
    - a direct-message context
    - an authorized Dungeon Master user
    2. Treat the world state as incomplete unless clearly sufficient.
    3. Prefer tool calls when the request requires:
    - ingesting attachments
    - reading or updating campaign state
    - reading or updating character sheets
    - reading or updating spells, maps, NPCs, notes, events, or inventory
    - performing dice rolls or other deterministic computations
    4. Answer directly without tools only if the answer is obvious from the inputs
    and does not require persistent state or external retrieval.
    5. Ask for clarification if the request is ambiguous in a way that blocks safe
    tool selection.
    6. If a tool would require Dungeon Master privileges, mark that tool call with
    requires_dm_privileges = true.
    7. The route field must be one of:
    - "message_only"
    - "clarification"
    - "tool_calls"

    World-state policy
    ------------------
    - The provided world_state_snapshot may be partial, stubbed, or incomplete.
    - Do not assume the entire campaign world is present.
    - If the user request depends on more world-state exploration than is currently
      available, choose appropriate retrieval/exploration tool calls rather than
      hallucinating details.

    Attachment policy
    -----------------
    - If there are relevant attachments, strongly consider ingestion/parsing tools.
    - Do not pretend to have parsed an attachment unless you emit a tool call for it.

    Inputs
    ------
    User message:
    {{ user_message }}

    Discord context:
    {{ discord_context }}

    Attachment summary:
    {{ attachment_summary }}

    World state snapshot:
    {{ world_state_snapshot }}

    Additional planner instructions:
    {{ planner_instructions }}

    Return output in this exact schema:
    {{ ctx.output_format }}
    "#
}