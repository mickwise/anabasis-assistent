"""
Purpose
-------
Route normalized Discord requests into the correct execution path for the
application.

Key behaviors
-------------
- Evaluate whether a request should be ignored, rejected, executed directly, or
  sent to the LLM planner.
- Apply authorization policy before route selection.
- Route slash commands into direct tool calls.
- Route mention-based free-text messages into the planner path.
- Keep routing policy separate from Discord transport, tool execution, and
  planner implementation.

Conventions
-----------
- This module operates only on normalized internal types.
- This module does not inspect raw discord.py objects.
- This module does not execute tools and does not call the planner directly.
- Slash commands are treated as direct routes.
- Mention-based free-text messages are treated as planner routes when enabled.

Downstream usage
----------------
Use `route_request()` as the main entrypoint after building a
`DiscordRequestContext`. The returned `RouteDecision` should be passed to the
planner layer or direct tool execution layer as appropriate.
"""

from __future__ import annotations

from typing import Tuple
from dataclasses import dataclass

from discord_adapter.attachment_utils import request_has_supported_attachments
from discord_adapter.discord_auth import authorize_request
from discord_adapter.discord_config import DiscordConfig
from discord_adapter.discord_types import (
    AuthorizationResult,
    DiscordRequestContext,
    RouteDecision,
    RouteKind,
    ToolCall,
)


@dataclass(frozen=True)
class RoutingPolicy:
    """
    Purpose
    -------
    Hold the high-level routing policy knobs used by the Discord router.

    Key behaviors
    -------------
    - Control whether mention-based messages are routed.
    - Control whether slash commands are routed.
    - Control whether free-text planner routing is enabled.

    Parameters
    ----------
    enable_message_mentions : bool
        Whether mention-based message routing is enabled.
    enable_slash_commands : bool
        Whether slash-command routing is enabled.
    enable_llm_router : bool
        Whether free-text requests may be sent to the LLM planner.

    Attributes
    ----------
    enable_message_mentions : bool
        Mention-routing enablement flag.
    enable_slash_commands : bool
        Slash-command enablement flag.
    enable_llm_router : bool
        Planner-routing enablement flag.

    Notes
    -----
    - This object is derived from `DiscordConfig.features`.
    """

    enable_message_mentions: bool
    enable_slash_commands: bool
    enable_llm_router: bool


def build_routing_policy(config: DiscordConfig) -> RoutingPolicy:
    """
    Build the effective routing policy from loaded Discord configuration.

    Parameters
    ----------
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    RoutingPolicy
        Effective routing policy.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This helper exists so the router can depend on a narrow policy object
      instead of the full config tree.
    """
    return RoutingPolicy(
        enable_message_mentions=config.features.enable_message_mentions,
        enable_slash_commands=config.features.enable_slash_commands,
        enable_llm_router=config.features.enable_llm_router,
    )


def _build_rejected_decision(reason: str) -> RouteDecision:
    """
    Build a rejected routing decision.

    Parameters
    ----------
    reason : str
        Human-readable reason for rejection.

    Returns
    -------
    RouteDecision
        Rejected route decision.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Rejected decisions are intended for requests that should surface a
      user-visible failure or authorization error.
    """
    return RouteDecision(
        route_kind=RouteKind.REJECTED,
        reason=reason,
        direct_tool_calls=(),
        planner_prompt_override=None,
    )


def _build_noop_decision(reason: str) -> RouteDecision:
    """
    Build a no-op routing decision.

    Parameters
    ----------
    reason : str
        Human-readable reason for no-op handling.

    Returns
    -------
    RouteDecision
        No-op route decision.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - No-op decisions are intended for ignored chatter or disabled paths where
      no user-facing response is necessary.
    """
    return RouteDecision(
        route_kind=RouteKind.NO_OP,
        reason=reason,
        direct_tool_calls=(),
        planner_prompt_override=None,
    )


def _build_planner_decision(
    reason: str,
    planner_prompt_override: str | None = None,
) -> RouteDecision:
    """
    Build a planner routing decision.

    Parameters
    ----------
    reason : str
        Human-readable explanation for planner routing.
    planner_prompt_override : str | None
        Optional planner prompt override.

    Returns
    -------
    RouteDecision
        Planner route decision.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Planner routing is used for free-text natural-language requests.
    """
    return RouteDecision(
        route_kind=RouteKind.LLM_PLANNER,
        reason=reason,
        direct_tool_calls=(),
        planner_prompt_override=planner_prompt_override,
    )


def _build_direct_command_decision(
    reason: str,
    tool_calls: Tuple[ToolCall, ...],
) -> RouteDecision:
    """
    Build a direct-command routing decision.

    Parameters
    ----------
    reason : str
        Human-readable explanation for direct routing.
    tool_calls : tuple[ToolCall, ...]
        Tool calls to execute directly.

    Returns
    -------
    RouteDecision
        Direct-command route decision.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Direct-command routes bypass the planner layer.
    """
    return RouteDecision(
        route_kind=RouteKind.DIRECT_COMMAND,
        reason=reason,
        direct_tool_calls=tool_calls,
        planner_prompt_override=None,
    )


def _authorize_context(
    context: DiscordRequestContext,
    config: DiscordConfig,
) -> AuthorizationResult:
    """
    Authorize a normalized request context for general routing.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    AuthorizationResult
        General authorization result for the request.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - More specific tool-level authorization should happen later, after route
      selection, if needed.
    """
    return authorize_request(
        context=context,
        enable_dm_workflows=config.features.enable_dm_workflows,
        requires_dm_privileges=False,
        requires_admin_privileges=False,
    )


def _route_slash_command(
    context: DiscordRequestContext,
    policy: RoutingPolicy,
) -> RouteDecision:
    """
    Route a slash-command request.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    policy : RoutingPolicy
        Effective routing policy.

    Returns
    -------
    RouteDecision
        Routing decision for the slash command.

    Raises
    ------
    RuntimeError
        Raised if the normalized context is inconsistent with slash-command
        routing expectations.

    Notes
    -----
    - Slash commands are executed directly and do not pass through the planner.
    - Command options are forwarded as normalized tool arguments.
    """
    if not policy.enable_slash_commands:
        return _build_noop_decision("Slash-command routing is disabled.")

    if context.slash_command is None:
        raise RuntimeError(
            "Slash-command context is missing normalized slash command data."
        )

    tool_call: ToolCall = ToolCall(
        tool_name=context.slash_command.command_name,
        arguments=dict(context.slash_command.options),
        reason="Direct slash-command execution.",
        requires_dm_privileges=False,
    )

    return _build_direct_command_decision(
        reason="Slash command routed to direct execution.",
        tool_calls=(tool_call,),
    )


def _route_message(
    context: DiscordRequestContext,
    policy: RoutingPolicy,
) -> RouteDecision:
    """
    Route a mention-based message request.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    policy : RoutingPolicy
        Effective routing policy.

    Returns
    -------
    RouteDecision
        Routing decision for the message.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Only explicit mention-based messages are eligible for planner routing.
    - Free-text messages are routed to the planner when enabled.
    """
    if not policy.enable_message_mentions:
        return _build_noop_decision("Mention-based routing is disabled.")

    if not context.mention_triggered:
        return _build_noop_decision(
            "Message did not explicitly mention the bot."
        )

    if not policy.enable_llm_router:
        return _build_rejected_decision(
            "Natural-language routing is currently disabled."
        )

    prompt_override: str | None = None
    if context.is_direct_message:
        prompt_override = (
            "The request originated in a Discord DM context. Treat this as a "
            "private context. Do not assume the user is Dungeon Master "
            "authorized unless the authorization flags say so."
        )

    return _build_planner_decision(
        reason="Mention-based free-text request routed to planner.",
        planner_prompt_override=prompt_override,
    )


def _should_reject_empty_request(
    context: DiscordRequestContext,
) -> bool:
    """
    Return whether a request is effectively empty.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.

    Returns
    -------
    bool
        True if the request contains no usable text, command, or attachments.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This check is intentionally conservative and is used to avoid pointless
      planner or direct-command work.
    """
    has_text: bool = context.raw_text.strip() != ""
    has_slash_command: bool = context.slash_command is not None
    has_attachments: bool = len(context.attachments) > 0

    return not (has_text or has_slash_command or has_attachments)


def route_request(
    context: DiscordRequestContext,
    config: DiscordConfig,
) -> RouteDecision:
    """
    Route a normalized Discord request into the correct execution path.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    RouteDecision
        Top-level routing decision for the request.

    Raises
    ------
    RuntimeError
        Raised if the request context is structurally inconsistent with the
        expected event source.

    Notes
    -----
    - This is the main entrypoint for routing.
    - Authorization is applied before route selection.
    - Attachment presence does not force any one route; attachments are simply
      part of the context available to later handlers or planner logic.
    """
    if _should_reject_empty_request(context):
        return _build_noop_decision("Request contained no actionable content.")

    authorization_result: AuthorizationResult = _authorize_context(
        context=context,
        config=config,
    )
    if not authorization_result.is_authorized:
        return _build_rejected_decision(authorization_result.reason)

    policy: RoutingPolicy = build_routing_policy(config)

    if context.slash_command is not None:
        return _route_slash_command(
            context=context,
            policy=policy,
        )

    if context.event_source.value == "message":
        return _route_message(
            context=context,
            policy=policy,
        )

    return _build_noop_decision(
        "No routing policy matched the normalized request."
    )


def route_request_with_attachment_hint(
    context: DiscordRequestContext,
    config: DiscordConfig,
) -> RouteDecision:
    """
    Route a request while optionally enriching the planner prompt for attachment
    contexts.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    RouteDecision
        Routing decision for the request, optionally enriched for attachment
        contexts.

    Raises
    ------
    RuntimeError
        Propagated from the core routing path if the request context is
        structurally inconsistent.

    Notes
    -----
    - This helper is useful when you want free-text planner routing to be more
      explicit about attachment presence.
    - Direct-command routes are returned unchanged.
    """
    decision: RouteDecision = route_request(context=context, config=config)

    if decision.route_kind != RouteKind.LLM_PLANNER:
        return decision

    if not request_has_supported_attachments(context):
        return decision

    base_override: str = decision.planner_prompt_override or ""
    attachment_hint: str = (
        " The request includes one or more supported attachments. Consider "
        "whether the correct action involves an ingestion, parsing, or vision "
        "tool."
    )
    merged_override: str = (base_override + attachment_hint).strip()

    return RouteDecision(
        route_kind=decision.route_kind,
        reason=decision.reason,
        direct_tool_calls=decision.direct_tool_calls,
        planner_prompt_override=merged_override,
    )
