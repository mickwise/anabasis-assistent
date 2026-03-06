"""
Purpose
-------
Define the shared type layer for the Discord orchestration system.

Key behaviors
-------------
- Provide stable dataclasses and enums used across Discord message handling,
  slash-command handling, LLM routing, tool execution, and response delivery.
- Unify guild messages, DM messages, and slash-command interactions into one
  common context shape.
- Separate context extraction, route planning, authorization, tool execution,
  and response generation through explicit typed envelopes.

Conventions
-----------
- These types are transport-oriented and intentionally lightweight.
- This module does not import discord.py objects directly; downstream modules
  should translate discord.py models into these internal types.
- `guild_id is None` means the originating context is a Discord DM, but that
  alone does not imply Dungeon Master authorization.
- Attachments are represented by normalized metadata only. File downloading and
  parsing belong in later modules.

Downstream usage
----------------
Import these types from all Discord orchestration modules. Context builders
should emit `DiscordRequestContext`, routers should emit `RouteDecision`,
planner layers should emit `PlannerOutput`, and execution layers should return
`ExecutionResult` and `DiscordResponsePlan`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Tuple, Dict


class EventSource(str, Enum):
    """
    Purpose
    -------
    Identify which Discord surface produced an incoming request.

    Key behaviors
    -------------
    - Distinguishes message-based ingestion from slash-command interactions.
    - Provides a stable routing discriminator for higher-level orchestrators.

    Parameters
    ----------
    This enum defines constant values and therefore accepts no constructor
    parameters in normal use.

    Attributes
    ----------
    MESSAGE : EventSource
        A normal Discord message event.
    SLASH_COMMAND : EventSource
        A slash-command interaction event.
    COMPONENT : EventSource
        A component interaction, such as a button or select menu.
    MODAL : EventSource
        A modal submission interaction.

    Notes
    -----
    - This enum is intended to be serialized and logged as a simple string.
    - Additional event types can be added later without breaking existing code
      that switches on known values.
    """

    MESSAGE = "message"
    SLASH_COMMAND = "slash_command"
    COMPONENT = "component"
    MODAL = "modal"


class ConversationScope(str, Enum):
    """
    Purpose
    -------
    Describe the high-level Discord conversation scope in which a request was
    created.

    Key behaviors
    -------------
    - Distinguishes guild traffic from direct-message traffic.
    - Supports authorization and routing policies that depend on scope.

    Parameters
    ----------
    This enum defines constant values and therefore accepts no constructor
    parameters in normal use.

    Attributes
    ----------
    GUILD : ConversationScope
        Request originated in a guild channel.
    DIRECT_MESSAGE : ConversationScope
        Request originated in a direct-message context.

    Notes
    -----
    - `DIRECT_MESSAGE` means the transport scope is private, not that the user
      is necessarily authorized for Dungeon Master-only workflows.
    """

    GUILD = "guild"
    DIRECT_MESSAGE = "direct_message"


class PrivilegeLevel(str, Enum):
    """
    Purpose
    -------
    Represent the authorization tier granted to a request after policy
    evaluation.

    Key behaviors
    -------------
    - Separates plain user access from Dungeon Master-only access.
    - Gives routing and tool execution layers a simple privilege signal.

    Parameters
    ----------
    This enum defines constant values and therefore accepts no constructor
    parameters in normal use.

    Attributes
    ----------
    USER : PrivilegeLevel
        Standard user-level access.
    DM : PrivilegeLevel
        Authorized Dungeon Master access.
    ADMIN : PrivilegeLevel
        Higher-trust application or campaign administration access.
    DENIED : PrivilegeLevel
        Request is not authorized for the intended action.

    Notes
    -----
    - `DM` refers to Dungeon Master authorization, not merely Discord direct
      messages.
    - `ADMIN` is included now so later campaign-management features do not
      require a breaking type change.
    """

    USER = "user"
    DM = "dm"
    ADMIN = "admin"
    DENIED = "denied"


class RouteKind(str, Enum):
    """
    Purpose
    -------
    Classify the top-level execution path chosen for an incoming request.

    Key behaviors
    -------------
    - Distinguishes direct slash-command execution from LLM-planned execution.
    - Allows the main router to branch cleanly without inspecting raw Discord
      payloads.

    Parameters
    ----------
    This enum defines constant values and therefore accepts no constructor
    parameters in normal use.

    Attributes
    ----------
    DIRECT_COMMAND : RouteKind
        A slash command or equivalent direct action should be executed without
        planner involvement.
    LLM_PLANNER : RouteKind
        A natural-language request should be passed to the planner model.
    REJECTED : RouteKind
        The request should not be executed.
    NO_OP : RouteKind
        The request does not require any action.

    Notes
    -----
    - `NO_OP` is useful for ignored chatter, unsupported mentions, or internal
      events that should not produce a user-visible error.
    """

    DIRECT_COMMAND = "direct_command"
    LLM_PLANNER = "llm_planner"
    REJECTED = "rejected"
    NO_OP = "no_op"


class ResponseVisibility(str, Enum):
    """
    Purpose
    -------
    Describe how a user-facing Discord response should be delivered.

    Key behaviors
    -------------
    - Distinguishes public responses from private or silent ones.
    - Gives response handlers a stable policy signal independent of transport.

    Parameters
    ----------
    This enum defines constant values and therefore accepts no constructor
    parameters in normal use.

    Attributes
    ----------
    PUBLIC : ResponseVisibility
        Response should be visible in the channel or thread.
    EPHEMERAL : ResponseVisibility
        Response should be visible only to the invoking user where Discord
        supports ephemeral replies.
    SILENT : ResponseVisibility
        No user-visible response should be sent.

    Notes
    -----
    - Ephemeral responses are only available for interaction-based flows.
    - Message-based flows may have to degrade unsupported visibilities.
    """

    PUBLIC = "public"
    EPHEMERAL = "ephemeral"
    SILENT = "silent"


@dataclass(frozen=True)
class AttachmentRef:
    """
    Purpose
    -------
    Represent a normalized attachment supplied through Discord.

    Key behaviors
    -------------
    - Stores the metadata required for downstream download and parsing.
    - Shields the rest of the application from raw discord.py attachment
      objects.

    Parameters
    ----------
    attachment_id : str | None
        Discord attachment identifier if available.
    filename : str
        Original uploaded filename.
    url : str
        Discord-hosted URL for downloading the attachment.
    content_type : str | None
        MIME type reported by Discord, if available.
    size_bytes : int
        Attachment size in bytes.
    source_kind : str
        Normalized source category such as `pdf`, `image`, or `unknown`.

    Attributes
    ----------
    attachment_id : str | None
        Stable Discord attachment identifier if provided by the upstream layer.
    filename : str
        Original uploaded filename.
    url : str
        Discord CDN or attachment URL.
    content_type : str | None
        MIME type reported by Discord.
    size_bytes : int
        Attachment size in bytes.
    source_kind : str
        Normalized source category for downstream routing.

    Notes
    -----
    - This object contains metadata only and does not imply the file has been
      downloaded or validated.
    - `source_kind` should come from a single normalization function elsewhere
      in the codebase.
    """

    attachment_id: str | None
    filename: str
    url: str
    content_type: str | None
    size_bytes: int
    source_kind: str


@dataclass(frozen=True)
class SlashCommandInvocation:
    """
    Purpose
    -------
    Represent a normalized slash-command invocation independent of discord.py
    internals.

    Key behaviors
    -------------
    - Captures the command name, subcommand path, and parsed options.
    - Provides direct-command routing enough information to call a handler.

    Parameters
    ----------
    command_name : str
        Top-level slash-command name.
    subcommand_path : tuple[str, ...]
        Optional nested subcommand path.
    options : dict[str, Any]
        Parsed command options normalized into plain Python values.

    Attributes
    ----------
    command_name : str
        Top-level slash-command name.
    subcommand_path : tuple[str, ...]
        Nested subcommand path, if any.
    options : dict[str, Any]
        Normalized slash-command option payload.

    Notes
    -----
    - Keep option values JSON-friendly where possible.
    - Attachment options should be converted into `AttachmentRef` objects by
      the context layer before reaching routers or planners.
    """

    command_name: str
    subcommand_path: Tuple[str, ...] = ()
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscordRequestContext:
    """
    Purpose
    -------
    Hold the canonical request context extracted from a Discord event.

    Key behaviors
    -------------
    - Unifies message events and interaction events into one stable internal
      shape.
    - Carries enough information for routing, authorization, planning, tool
      execution, and response generation.
    - Makes DM-vs-guild scope explicit through structured fields instead of
      repeated ad hoc checks.

    Parameters
    ----------
    event_source : EventSource
        Source surface that produced the request.
    conversation_scope : ConversationScope
        Whether the request originated in a guild or a direct message.
    user_id : int
        Discord user ID for the requester.
    username : str | None
        Human-readable username or display name if known.
    channel_id : int
        Discord channel ID in which the request originated.
    guild_id : int | None
        Guild ID if the request was created in a guild; otherwise None.
    message_id : int | None
        Message ID if the request originated from a message event.
    interaction_id : int | None
        Interaction ID if the request originated from an interaction.
    raw_text : str
        Free-text content supplied by the user.
    mention_triggered : bool
        Whether the bot was explicitly mentioned in a message flow.
    attachments : tuple[AttachmentRef, ...]
        Normalized attachment metadata associated with the request.
    slash_command : SlashCommandInvocation | None
        Parsed slash-command metadata for interaction-based direct execution.
    is_dm_authorized : bool
        Whether the requester is authorized for Dungeon Master-only workflows.
    privilege_level : PrivilegeLevel
        Authorization result after policy evaluation.
    metadata : dict[str, Any]
        Additional normalized metadata not captured by the fixed fields.

    Attributes
    ----------
    event_source : EventSource
        Event family that produced the request.
    conversation_scope : ConversationScope
        Guild vs direct-message scope.
    user_id : int
        Requesting Discord user ID.
    username : str | None
        Human-readable user label if known.
    channel_id : int
        Originating Discord channel ID.
    guild_id : int | None
        Originating guild ID or None for direct messages.
    message_id : int | None
        Message ID when applicable.
    interaction_id : int | None
        Interaction ID when applicable.
    raw_text : str
        User-supplied free text.
    mention_triggered : bool
        Whether the bot mention triggered the route.
    attachments : tuple[AttachmentRef, ...]
        Attachment metadata associated with the request.
    slash_command : SlashCommandInvocation | None
        Slash-command payload when applicable.
    is_dm_authorized : bool
        Explicit Dungeon Master authorization flag.
    privilege_level : PrivilegeLevel
        Effective privilege level for the request.
    metadata : dict[str, Any]
        Additional normalized metadata.

    Notes
    -----
    - `guild_id is None` implies `conversation_scope == DIRECT_MESSAGE` by
      convention.
    - `is_dm_authorized` is distinct from being in a Discord DM context.
    - Downstream modules should treat this object as the single source of truth
      for request-level authorization and scope.
    """

    event_source: EventSource
    conversation_scope: ConversationScope
    user_id: int
    username: str | None
    channel_id: int
    guild_id: int | None
    message_id: int | None
    interaction_id: int | None
    raw_text: str
    mention_triggered: bool
    attachments: Tuple[AttachmentRef, ...] = ()
    slash_command: SlashCommandInvocation | None = None
    is_dm_authorized: bool = False
    privilege_level: PrivilegeLevel = PrivilegeLevel.USER
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_direct_message(self) -> bool:
        """
        Return whether the request originated in a Discord direct-message scope.

        Parameters
        ----------
        None
            This property accepts no parameters.

        Returns
        -------
        bool
            True if the request originated outside a guild, else False.

        Raises
        ------
        AttributeError
            Not raised directly by this property.

        Notes
        -----
        - This is a convenience view over `conversation_scope`.
        """
        return self.conversation_scope == ConversationScope.DIRECT_MESSAGE

    @property
    def has_attachments(self) -> bool:
        """
        Return whether the request includes one or more attachments.

        Parameters
        ----------
        None
            This property accepts no parameters.

        Returns
        -------
        bool
            True if at least one attachment is present, else False.

        Raises
        ------
        AttributeError
            Not raised directly by this property.

        Notes
        -----
        - This is a convenience property for routers and tool selectors.
        """
        return len(self.attachments) > 0


@dataclass(frozen=True)
class ToolCall:
    """
    Purpose
    -------
    Represent a single normalized tool invocation requested by a direct command
    handler or planner model.

    Key behaviors
    -------------
    - Encodes the target tool name and its structured arguments.
    - Carries optional human-readable reasoning for logging and audit.

    Parameters
    ----------
    tool_name : str
        Registered tool name to execute.
    arguments : dict[str, Any]
        Structured tool arguments.
    reason : str | None
        Optional explanation of why the tool should be executed.
    requires_dm_privileges : bool
        Whether the tool requires Dungeon Master authorization.

    Attributes
    ----------
    tool_name : str
        Registered tool name to execute.
    arguments : dict[str, Any]
        Structured tool arguments.
    reason : str | None
        Optional explanation or planner note.
    requires_dm_privileges : bool
        Whether the tool requires elevated authorization.

    Notes
    -----
    - `arguments` should be fully normalized and execution-ready.
    - Authorization checks should not rely solely on this object; the request
      context remains authoritative.
    """

    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    requires_dm_privileges: bool = False


@dataclass(frozen=True)
class PlannerOutput:
    """
    Purpose
    -------
    Represent the normalized output of the LLM planner for a natural-language
    Discord request.

    Key behaviors
    -------------
    - Captures the planner's chosen tool calls.
    - Allows the planner to return user-facing clarification or refusal text.
    - Keeps planner reasoning structurally separate from execution results.

    Parameters
    ----------
    tool_calls : tuple[ToolCall, ...]
        Ordered tool calls selected by the planner.
    assistant_message : str | None
        Optional text to send directly to the user.
    needs_clarification : bool
        Whether the planner concluded that execution should pause pending user
        clarification.
    clarification_question : str | None
        Follow-up question for the user when clarification is required.

    Attributes
    ----------
    tool_calls : tuple[ToolCall, ...]
        Ordered tool calls selected by the planner.
    assistant_message : str | None
        Optional user-facing message.
    needs_clarification : bool
        Clarification flag.
    clarification_question : str | None
        Follow-up clarification prompt if applicable.

    Notes
    -----
    - `tool_calls` may be empty if the planner decides only a message is needed.
    - Multi-tool execution is allowed by design.
    """

    tool_calls: Tuple[ToolCall, ...] = ()
    assistant_message: str | None = None
    needs_clarification: bool = False
    clarification_question: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    """
    Purpose
    -------
    Represent the routing decision produced by the Discord router for one
    incoming request.

    Key behaviors
    -------------
    - Chooses the top-level execution path.
    - Carries direct tool calls for slash-command execution when applicable.
    - Carries a rejection or no-op explanation when the request should not
      proceed.

    Parameters
    ----------
    route_kind : RouteKind
        Top-level route classification.
    reason : str
        Human-readable explanation of why this route was selected.
    direct_tool_calls : tuple[ToolCall, ...]
        Tool calls to execute immediately for direct-command routes.
    planner_prompt_override : str | None
        Optional planner override text for special routing cases.

    Attributes
    ----------
    route_kind : RouteKind
        Top-level route classification.
    reason : str
        Human-readable route explanation.
    direct_tool_calls : tuple[ToolCall, ...]
        Immediate tool calls for direct execution.
    planner_prompt_override : str | None
        Optional planner override text.

    Notes
    -----
    - For direct slash commands, `direct_tool_calls` should usually be
      populated.
    - For natural-language messages, the route will usually be `LLM_PLANNER`
      with no direct tool calls.
    """

    route_kind: RouteKind
    reason: str
    direct_tool_calls: Tuple[ToolCall, ...] = ()
    planner_prompt_override: str | None = None


@dataclass(frozen=True)
class ToolExecutionRecord:
    """
    Purpose
    -------
    Store the result of a single executed tool call.

    Key behaviors
    -------------
    - Records whether execution succeeded or failed.
    - Carries structured output for later response formatting or logging.

    Parameters
    ----------
    tool_call : ToolCall
        Tool call that was executed.
    success : bool
        Whether execution succeeded.
    output : dict[str, Any]
        Structured tool output.
    error_message : str | None
        Error text if execution failed.

    Attributes
    ----------
    tool_call : ToolCall
        Tool call that was executed.
    success : bool
        Whether execution succeeded.
    output : dict[str, Any]
        Structured output returned by the tool.
    error_message : str | None
        Failure text if execution did not succeed.

    Notes
    -----
    - `output` should stay JSON-friendly where possible.
    - A failed execution may still produce partial structured output.
    """

    tool_call: ToolCall
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    """
    Purpose
    -------
    Represent the aggregate outcome of executing one or more tool calls.

    Key behaviors
    -------------
    - Aggregates individual tool execution records.
    - Separates internal execution success from user-facing response text.
    - Gives response formatting layers enough information to build final output.

    Parameters
    ----------
    success : bool
        Whether the overall execution should be treated as successful.
    records : tuple[ToolExecutionRecord, ...]
        Per-tool execution records.
    summary_message : str | None
        Optional execution summary for the user.
    metadata : dict[str, Any]
        Additional structured execution metadata.

    Attributes
    ----------
    success : bool
        Aggregate execution success flag.
    records : tuple[ToolExecutionRecord, ...]
        Per-tool execution records.
    summary_message : str | None
        Optional user-facing execution summary.
    metadata : dict[str, Any]
        Additional structured metadata.

    Notes
    -----
    - `success` may be False even if some individual tool calls succeeded.
    - Keep `summary_message` concise; richer formatting belongs in the response
      layer.
    """

    success: bool
    records: Tuple[ToolExecutionRecord, ...] = ()
    summary_message: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiscordResponsePlan:
    """
    Purpose
    -------
    Represent the final response policy the Discord output layer should apply.

    Key behaviors
    -------------
    - Decouples business logic from Discord transport details.
    - Tells the response layer what text to send, how visible it should be, and
      whether attachments should be included.

    Parameters
    ----------
    text : str
        Primary response text to send.
    visibility : ResponseVisibility
        Desired visibility policy.
    should_reply : bool
        Whether a Discord response should be sent at all.
    attachment_urls : tuple[str, ...]
        Optional outbound attachment URLs to include or reference.
    metadata : dict[str, Any]
        Additional response-layer metadata.

    Attributes
    ----------
    text : str
        Primary user-facing response text.
    visibility : ResponseVisibility
        Desired visibility policy.
    should_reply : bool
        Whether to send a response.
    attachment_urls : tuple[str, ...]
        Optional outbound attachment references.
    metadata : dict[str, Any]
        Additional response metadata.

    Notes
    -----
    - Transport-specific adapters may need to degrade unsupported visibility
      modes depending on whether the source was a message or an interaction.
    - This object does not itself send anything to Discord.
    """

    text: str
    visibility: ResponseVisibility = ResponseVisibility.PUBLIC
    should_reply: bool = True
    attachment_urls: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorizationResult:
    """
    Purpose
    -------
    Capture the output of a request authorization policy evaluation.

    Key behaviors
    -------------
    - Carries the effective privilege level and a human-readable reason.
    - Makes authorization decisions easy to log and propagate into context
      objects.

    Parameters
    ----------
    is_authorized : bool
        Whether the request is authorized for the attempted action.
    privilege_level : PrivilegeLevel
        Effective privilege level granted by policy.
    reason : str
        Human-readable explanation of the authorization outcome.

    Attributes
    ----------
    is_authorized : bool
        Authorization outcome flag.
    privilege_level : PrivilegeLevel
        Effective granted privilege level.
    reason : str
        Human-readable policy explanation.

    Notes
    -----
    - This object is intentionally generic so it can be reused for both broad
      request authorization and tool-specific authorization checks.
    """

    is_authorized: bool
    privilege_level: PrivilegeLevel
    reason: str
