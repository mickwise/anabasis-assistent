"""
Purpose
-------
Provide response-planning and response-delivery utilities for the Discord
orchestration layer.

Key behaviors
-------------
- Convert execution outcomes into normalized Discord response plans.
- Send responses to either message-based or interaction-based request sources.
- Handle public, ephemeral, and silent visibility modes consistently.
- Gracefully degrade unsupported visibility modes for message-based workflows.
- Support both initial interaction responses and follow-up responses.

Conventions
-----------
- This module operates on normalized orchestration-layer types and discord.py
  message or interaction objects.
- Ephemeral responses are only available for interaction-based workflows.
- Message-based workflows cannot produce true ephemeral replies and therefore
  degrade ephemeral visibility to a normal public reply.
- Silent responses suppress user-facing output entirely.

Downstream usage
----------------
Use `build_response_plan_from_execution()` to translate execution outcomes into
a response plan. Use `send_response_plan_for_message()` or
`send_response_plan_for_interaction()` to deliver the response through
discord.py.
"""

from __future__ import annotations

from typing import Any

import discord

from discord_adapter.discord_types import (
    DiscordRequestContext,
    DiscordResponsePlan,
    ExecutionResult,
    ResponseVisibility,
)


def build_simple_response_plan(
    text: str,
    visibility: ResponseVisibility = ResponseVisibility.PUBLIC,
    should_reply: bool = True,
) -> DiscordResponsePlan:
    """
    Build a simple normalized Discord response plan.

    Parameters
    ----------
    text : str
        User-facing response text.
    visibility : ResponseVisibility
        Desired response visibility policy.
    should_reply : bool
        Whether a response should actually be sent.

    Returns
    -------
    DiscordResponsePlan
        Normalized response plan.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This helper is useful for straightforward success, failure, or
      clarification messages.
    """
    return DiscordResponsePlan(
        text=text,
        visibility=visibility,
        should_reply=should_reply,
    )


def build_response_plan_from_execution(
    execution_result: ExecutionResult,
    success_visibility: ResponseVisibility = ResponseVisibility.PUBLIC,
    failure_visibility: ResponseVisibility = ResponseVisibility.PUBLIC,
) -> DiscordResponsePlan:
    """
    Build a response plan from an execution result.

    Parameters
    ----------
    execution_result : ExecutionResult
        Aggregate tool-execution result.
    success_visibility : ResponseVisibility
        Visibility to use when execution succeeded.
    failure_visibility : ResponseVisibility
        Visibility to use when execution failed.

    Returns
    -------
    DiscordResponsePlan
        Response plan derived from the execution result.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - If the execution result does not provide a summary message, a fallback
      message is generated.
    """
    if execution_result.success:
        text = execution_result.summary_message or "Request completed."
        return DiscordResponsePlan(
            text=text,
            visibility=success_visibility,
            should_reply=True,
            metadata={"execution_success": True},
        )

    text = execution_result.summary_message or "Request failed."
    return DiscordResponsePlan(
        text=text,
        visibility=failure_visibility,
        should_reply=True,
        metadata={"execution_success": False},
    )


def build_noop_response_plan() -> DiscordResponsePlan:
    """
    Build a response plan representing deliberate silence.

    Parameters
    ----------
    None
        This function accepts no parameters.

    Returns
    -------
    DiscordResponsePlan
        Silent response plan.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This is useful for ignored chatter or internal no-op routes.
    """
    return DiscordResponsePlan(
        text="",
        visibility=ResponseVisibility.SILENT,
        should_reply=False,
    )


def _coerce_message_visibility(
    visibility: ResponseVisibility,
) -> ResponseVisibility:
    """
    Coerce a desired visibility policy into one supported by message replies.

    Parameters
    ----------
    visibility : ResponseVisibility
        Desired response visibility.

    Returns
    -------
    ResponseVisibility
        Effective visibility supported by message-based workflows.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Message replies cannot be ephemeral in Discord, so ephemeral is degraded
      to public.
    - Silent remains silent.
    """
    if visibility == ResponseVisibility.EPHEMERAL:
        return ResponseVisibility.PUBLIC

    return visibility


async def send_response_plan_for_message(
    message: discord.Message,
    response_plan: DiscordResponsePlan,
    mention_author: bool = False,
) -> None:
    """
    Send a normalized response plan for a message-based workflow.

    Parameters
    ----------
    message : discord.Message
        Source message to reply to.
    response_plan : DiscordResponsePlan
        Normalized response plan to deliver.
    mention_author : bool
        Whether the reply should mention the author.

    Returns
    -------
    None
        This function returns no value.

    Raises
    ------
    discord.DiscordException
        Raised if discord.py fails to send the reply.

    Notes
    -----
    - Ephemeral visibility is not supported for normal messages and is degraded
      to a normal public reply.
    - Silent responses do not send anything.
    """
    effective_visibility: ResponseVisibility = _coerce_message_visibility(
        response_plan.visibility
    )
    if (
        not response_plan.should_reply
        or effective_visibility == ResponseVisibility.SILENT
    ):
        return

    await message.reply(
        response_plan.text,
        mention_author=mention_author,
    )


async def defer_interaction_if_needed(
    interaction: discord.Interaction[Any],
    *,
    ephemeral: bool = False,
    thinking: bool = True,
) -> bool:
    """
    Defer an interaction response if it has not already been responded to.

    Parameters
    ----------
    interaction : discord.Interaction[Any]
        Interaction to defer.
    ephemeral : bool
        Whether the deferred response should eventually be ephemeral where
        supported.
    thinking : bool
        Whether to use the thinking/deferred-message response mode.

    Returns
    -------
    bool
        True if the interaction was deferred by this function, else False.

    Raises
    ------
    discord.DiscordException
        Raised if discord.py fails while deferring the interaction.

    Notes
    -----
    - In discord.py, an interaction can only be responded to once through
      `interaction.response`, and long-running flows typically call
      `interaction.response.defer()` first.
    """
    if interaction.response.is_done():
        return False

    await interaction.response.defer(
        ephemeral=ephemeral,
        thinking=thinking,
    )
    return True


async def send_response_plan_for_interaction(
    interaction: discord.Interaction[Any],
    response_plan: DiscordResponsePlan,
) -> None:
    """
    Send a normalized response plan for an interaction-based workflow.

    Parameters
    ----------
    interaction : discord.Interaction[Any]
        Source interaction to respond to.
    response_plan : DiscordResponsePlan
        Normalized response plan to deliver.

    Returns
    -------
    None
        This function returns no value.

    Raises
    ------
    discord.DiscordException
        Raised if discord.py fails to send the response or follow-up.

    Notes
    -----
    - If the interaction has not been responded to yet, this function uses
      `interaction.response.send_message(...)`.
    - If the interaction has already been responded to or deferred, this
      function uses `interaction.followup.send(...)`.
    - Ephemeral responses are interaction-only behavior.
    """
    if (
        not response_plan.should_reply
        or response_plan.visibility == ResponseVisibility.SILENT
    ):
        return

    ephemeral: bool = response_plan.visibility == ResponseVisibility.EPHEMERAL

    if not interaction.response.is_done():
        await interaction.response.send_message(
            response_plan.text,
            ephemeral=ephemeral,
        )
        return

    await interaction.followup.send(
        response_plan.text,
        ephemeral=ephemeral,
    )


async def send_error_response_for_message(
    message: discord.Message,
    error_text: str,
    mention_author: bool = False,
) -> None:
    """
    Send a standardized error reply for a message-based workflow.

    Parameters
    ----------
    message : discord.Message
        Source message to reply to.
    error_text : str
        User-facing error text.
    mention_author : bool
        Whether the reply should mention the author.

    Returns
    -------
    None
        This function returns no value.

    Raises
    ------
    discord.DiscordException
        Raised if discord.py fails to send the reply.

    Notes
    -----
    - This helper is intentionally small so higher-level modules can keep error
      handling uniform.
    """
    response_plan: DiscordResponsePlan = build_simple_response_plan(
        text=error_text,
        visibility=ResponseVisibility.PUBLIC,
        should_reply=True,
    )
    await send_response_plan_for_message(
        message=message,
        response_plan=response_plan,
        mention_author=mention_author,
    )


async def send_error_response_for_interaction(
    interaction: discord.Interaction[Any],
    error_text: str,
    visibility: ResponseVisibility = ResponseVisibility.EPHEMERAL,
) -> None:
    """
    Send a standardized error response for an interaction-based workflow.

    Parameters
    ----------
    interaction : discord.Interaction[Any]
        Source interaction to respond to.
    error_text : str
        User-facing error text.
    visibility : ResponseVisibility
        Desired visibility for the error response.

    Returns
    -------
    None
        This function returns no value.

    Raises
    ------
    discord.DiscordException
        Raised if discord.py fails to send the response.

    Notes
    -----
    - Ephemeral is the default because interaction-driven errors are often best
      kept private to the caller.
    """
    response_plan: DiscordResponsePlan = build_simple_response_plan(
        text=error_text,
        visibility=visibility,
        should_reply=True,
    )
    await send_response_plan_for_interaction(
        interaction=interaction,
        response_plan=response_plan,
    )


def build_unauthorized_response_plan(
    reason: str = "You are not authorized to perform this action.",
    visibility: ResponseVisibility = ResponseVisibility.EPHEMERAL,
) -> DiscordResponsePlan:
    """
    Build a standardized authorization-failure response plan.

    Parameters
    ----------
    reason : str
        User-facing explanation of the authorization failure.
    visibility : ResponseVisibility
        Desired visibility policy for the response.

    Returns
    -------
    DiscordResponsePlan
        Authorization-failure response plan.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - For interaction-based flows, ephemeral is usually the correct default.
    - For message-based flows, ephemeral will later degrade to public.
    """
    return DiscordResponsePlan(
        text=reason,
        visibility=visibility,
        should_reply=True,
        metadata={"response_kind": "unauthorized"},
    )


def build_clarification_response_plan(
    question: str,
    visibility: ResponseVisibility = ResponseVisibility.PUBLIC,
) -> DiscordResponsePlan:
    """
    Build a response plan asking the user for clarification.

    Parameters
    ----------
    question : str
        Clarification question to present to the user.
    visibility : ResponseVisibility
        Desired visibility policy for the clarification prompt.

    Returns
    -------
    DiscordResponsePlan
        Clarification response plan.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This helper is intended for planner outputs that need more information
      before tool execution can continue.
    """
    return DiscordResponsePlan(
        text=question,
        visibility=visibility,
        should_reply=True,
        metadata={"response_kind": "clarification"},
    )


def choose_default_visibility_for_context(
    context: DiscordRequestContext,
    prefer_private_errors: bool = True,
) -> ResponseVisibility:
    """
    Choose a default response visibility policy for a request context.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    prefer_private_errors : bool
        Whether user-specific responses should prefer private visibility where
        supported.

    Returns
    -------
    ResponseVisibility
        Suggested default visibility policy.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Interaction-based flows can support ephemeral responses.
    - Message-based flows should generally remain public because normal message
      replies cannot be ephemeral.
    """
    if not prefer_private_errors:
        return ResponseVisibility.PUBLIC

    if context.event_source.value == "slash_command":
        return ResponseVisibility.EPHEMERAL

    return ResponseVisibility.PUBLIC
