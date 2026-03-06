"""
Purpose
-------
Provide authorization policy helpers for the Discord orchestration layer.

Key behaviors
-------------
- Evaluate whether a request is authorized for general use, Dungeon Master-only
  use, or admin-only use.
- Separate Discord direct-message scope from Dungeon Master authorization.
- Centralize policy decisions so routers, planners, and tool executors do not
  reimplement authorization logic.
- Expose small helper functions for common policy checks.

Conventions
-----------
- This module does not inspect raw discord.py objects. It operates only on the
  normalized internal types defined in `discord_types.py`.
- `guild_id is None` or direct-message scope means the transport context is a
  Discord DM, not that the user is authorized as a Dungeon Master.
- Authorization is currently config- and context-based, not database-backed.
- Rejection reasons should be explicit and user-safe.

Downstream usage
----------------
Use `authorize_request()` as the main entrypoint when a route or tool needs
authorization. Use the helper predicates for narrower checks in routers or
executors when appropriate.
"""

from __future__ import annotations

from discord_adapter.discord_types import (
    AuthorizationResult,
    DiscordRequestContext,
    PrivilegeLevel,
    ToolCall,
)


def is_direct_message_context(context: DiscordRequestContext) -> bool:
    """
    Return whether the request originated in a Discord direct-message context.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.

    Returns
    -------
    bool
        True if the request originated outside a guild, else False.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This checks transport scope only.
    - Direct-message scope does not imply Dungeon Master authorization.
    """
    return context.is_direct_message


def is_dm_authorized(context: DiscordRequestContext) -> bool:
    """
    Return whether the requester is authorized for Dungeon Master-only
    workflows.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.

    Returns
    -------
    bool
        True if the requester has Dungeon Master or admin privileges.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This uses the explicit privilege result embedded in the normalized
      context.
    - Dungeon Master authorization is distinct from Discord DM transport scope.
    """
    return context.privilege_level in {
        PrivilegeLevel.DM,
        PrivilegeLevel.ADMIN,
    }


def is_admin_authorized(context: DiscordRequestContext) -> bool:
    """
    Return whether the requester has admin-level authorization.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.

    Returns
    -------
    bool
        True if the requester has admin privileges, else False.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Admin privilege is the highest built-in privilege tier in the current
      type system.
    """
    return context.privilege_level == PrivilegeLevel.ADMIN


def can_use_dm_workflows(
    context: DiscordRequestContext,
    enable_dm_workflows: bool,
) -> AuthorizationResult:
    """
    Evaluate whether the request may access direct-message workflows.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    enable_dm_workflows : bool
        Feature flag controlling whether DM workflows are enabled globally.

    Returns
    -------
    AuthorizationResult
        Authorization outcome for direct-message workflow access.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This function answers whether DM-context workflows are allowed at all.
    - It does not by itself grant Dungeon Master-only privileges.
    """
    if not enable_dm_workflows and context.is_direct_message:
        return AuthorizationResult(
            is_authorized=False,
            privilege_level=PrivilegeLevel.DENIED,
            reason="Direct-message workflows are disabled.",
        )

    return AuthorizationResult(
        is_authorized=True,
        privilege_level=context.privilege_level,
        reason="Direct-message workflow policy passed.",
    )


def authorize_general_request(
    context: DiscordRequestContext,
    enable_dm_workflows: bool,
) -> AuthorizationResult:
    """
    Authorize a request for general non-privileged use.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    enable_dm_workflows : bool
        Feature flag controlling whether DM workflows are enabled globally.

    Returns
    -------
    AuthorizationResult
        Authorization result for general request processing.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This is the broadest authorization gate and is appropriate for normal
      slash commands or natural-language routing before tool-specific checks.
    - User-level, Dungeon Master-level, and admin-level requesters all pass
      this check unless DM workflows are globally disabled for DM-context
      requests.
    """
    dm_policy = can_use_dm_workflows(
        context=context,
        enable_dm_workflows=enable_dm_workflows,
    )
    if not dm_policy.is_authorized:
        return dm_policy

    if context.privilege_level == PrivilegeLevel.DENIED:
        return AuthorizationResult(
            is_authorized=False,
            privilege_level=PrivilegeLevel.DENIED,
            reason="Requester is not authorized to use this application.",
        )

    return AuthorizationResult(
        is_authorized=True,
        privilege_level=context.privilege_level,
        reason="General request authorization passed.",
    )


def authorize_dm_only_request(
    context: DiscordRequestContext,
    enable_dm_workflows: bool,
) -> AuthorizationResult:
    """
    Authorize a request for Dungeon Master-only workflows.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    enable_dm_workflows : bool
        Feature flag controlling whether DM workflows are enabled globally.

    Returns
    -------
    AuthorizationResult
        Authorization result for Dungeon Master-only access.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - This does not require the request to originate in a Discord DM.
    - A guild-scoped request may still be Dungeon Master-authorized if the
      user's privilege level permits it.
    """
    general_result = authorize_general_request(
        context=context,
        enable_dm_workflows=enable_dm_workflows,
    )
    if not general_result.is_authorized:
        return general_result

    if not is_dm_authorized(context):
        return AuthorizationResult(
            is_authorized=False,
            privilege_level=PrivilegeLevel.DENIED,
            reason="This action requires Dungeon Master authorization.",
        )

    return AuthorizationResult(
        is_authorized=True,
        privilege_level=context.privilege_level,
        reason="Dungeon Master authorization passed.",
    )


def authorize_admin_only_request(
    context: DiscordRequestContext,
    enable_dm_workflows: bool,
) -> AuthorizationResult:
    """
    Authorize a request for admin-only workflows.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    enable_dm_workflows : bool
        Feature flag controlling whether DM workflows are enabled globally.

    Returns
    -------
    AuthorizationResult
        Authorization result for admin-only access.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Admin-only actions are intentionally stricter than Dungeon Master-only
      actions.
    """
    general_result = authorize_general_request(
        context=context,
        enable_dm_workflows=enable_dm_workflows,
    )
    if not general_result.is_authorized:
        return general_result

    if not is_admin_authorized(context):
        return AuthorizationResult(
            is_authorized=False,
            privilege_level=PrivilegeLevel.DENIED,
            reason="This action requires admin authorization.",
        )

    return AuthorizationResult(
        is_authorized=True,
        privilege_level=context.privilege_level,
        reason="Admin authorization passed.",
    )


def authorize_tool_call(
    context: DiscordRequestContext,
    tool_call: ToolCall,
    enable_dm_workflows: bool,
) -> AuthorizationResult:
    """
    Authorize execution of a specific tool call.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    tool_call : ToolCall
        Tool invocation candidate selected by a direct route or planner.
    enable_dm_workflows : bool
        Feature flag controlling whether DM workflows are enabled globally.

    Returns
    -------
    AuthorizationResult
        Authorization result for the specific tool call.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Tool-level authorization is stricter than general request authorization
      when the tool explicitly requires Dungeon Master privileges.
    - More granular tool policies can later be layered on top of this helper.
    """
    if tool_call.requires_dm_privileges:
        return authorize_dm_only_request(
            context=context,
            enable_dm_workflows=enable_dm_workflows,
        )

    return authorize_general_request(
        context=context,
        enable_dm_workflows=enable_dm_workflows,
    )


def authorize_request(
    context: DiscordRequestContext,
    enable_dm_workflows: bool,
    requires_dm_privileges: bool = False,
    requires_admin_privileges: bool = False,
) -> AuthorizationResult:
    """
    Authorize a request according to explicit privilege requirements.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    enable_dm_workflows : bool
        Feature flag controlling whether DM workflows are enabled globally.
    requires_dm_privileges : bool
        Whether the action requires Dungeon Master authorization.
    requires_admin_privileges : bool
        Whether the action requires admin authorization.

    Returns
    -------
    AuthorizationResult
        Authorization outcome for the requested action.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Admin requirement dominates Dungeon Master requirement.
    - This is the most general authorization entrypoint in the module.
    """
    if requires_admin_privileges:
        return authorize_admin_only_request(
            context=context,
            enable_dm_workflows=enable_dm_workflows,
        )

    if requires_dm_privileges:
        return authorize_dm_only_request(
            context=context,
            enable_dm_workflows=enable_dm_workflows,
        )

    return authorize_general_request(
        context=context,
        enable_dm_workflows=enable_dm_workflows,
    )
