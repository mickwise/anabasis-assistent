"""
Purpose
-------
Provide the main Discord application entrypoint for the general bot
orchestration workflow.

Key behaviors
-------------
- Load Discord runtime configuration.
- Construct and configure the discord.py bot instance.
- Initialize the message and slash-command handlers.
- Register baseline slash commands on the application command tree.
- Wire the bot's message event into the shared message-handling pipeline.
- Sync the command tree during startup.

Conventions
-----------
- This module owns process-level Discord startup and top-level wiring only.
- This module does not implement planner logic, tool execution logic, or
  attachment downloading/parsing logic.
- All heavy downstream behavior is delegated through injected async callables.
- The bot uses a hybrid workflow: slash commands for direct execution and
  mention-based messages for planner routing.

Downstream usage
----------------
Run this module as the Discord process entrypoint after implementing concrete
planner and tool-execution callables.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import cast

from dotenv import load_dotenv

import discord
from discord.ext import commands

from discord_adapter.discord_config import DiscordConfig, load_discord_config
from discord_adapter.discord_types import (
    DiscordRequestContext,
    ExecutionResult,
    PlannerOutput,
    RouteDecision,
    ToolCall,
)
from discord_adapter.message_handler import MessageHandler
from discord_adapter.slash_commands import SlashCommandHandler, register_default_slash_commands
from tools.rolling.discord_slash_roll import roll_from_slash_context
from tools.rolling.rolling import roll_async as run_freeform_roll_async


LOGGER = logging.getLogger(__name__)


async def _planner_stub(
    context: DiscordRequestContext,
    route_decision: RouteDecision,
) -> PlannerOutput:
    """
    Provide a placeholder planner implementation for early Discord wiring.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    route_decision : RouteDecision
        Planner route decision produced by the shared router.

    Returns
    -------
    PlannerOutput
        Placeholder planner output.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Replace this stub with the real LLM planner integration.
    - This stub currently recognizes free-form messages starting with `roll`
      and routes them into the rolling tool.
    """
    _ = route_decision

    request_text: str = context.raw_text.strip()
    normalized_text = re.sub(r"<@!?\d+>", "", request_text).strip()
    if re.search(r"\broll\b", normalized_text.lower()) is not None:
        return PlannerOutput(
            tool_calls=(
                ToolCall(
                    tool_name="roll",
                    arguments={
                        "request": normalized_text,
                        "context": None,
                    },
                    reason="Detected free-form roll request.",
                    requires_dm_privileges=False,
                ),
            ),
            assistant_message=None,
            needs_clarification=False,
            clarification_question=None,
        )

    return PlannerOutput(
        tool_calls=(),
        assistant_message=(
            "Planner stub reached successfully. Replace this with the real "
            "LLM routing layer."
        ),
        needs_clarification=False,
        clarification_question=None,
    )


async def _direct_execution_stub(
    context: DiscordRequestContext,
    route_decision: RouteDecision,
) -> ExecutionResult:
    """
    Provide a placeholder direct-execution implementation for early Discord
    wiring.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    route_decision : RouteDecision
        Direct-command route decision produced by the shared router.

    Returns
    -------
    ExecutionResult
        Placeholder execution result.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Replace this stub with the real direct tool-execution layer.
    - This stub currently supports actual execution for the `roll` tool call
      and reports placeholders for unsupported tool names.
    """
    if not route_decision.direct_tool_calls:
        summary_message = "Direct execution stub reached with no tool calls."
        return ExecutionResult(
            success=True,
            records=(),
            summary_message=summary_message,
            metadata={
                "user_id": context.user_id,
                "route_kind": route_decision.route_kind.value,
            },
        )

    records: list[dict[str, object]] = []
    unsupported_tools: list[str] = []
    last_roll_result: dict[str, object] | None = None

    for tool_call in route_decision.direct_tool_calls:
        if tool_call.tool_name == "roll":
            try:
                roll_result = roll_from_slash_context(context=context)
            except ValueError as exc:
                return ExecutionResult(
                    success=False,
                    records=(),
                    summary_message=f"Roll command failed: {exc}",
                    metadata={
                        "user_id": context.user_id,
                        "route_kind": route_decision.route_kind.value,
                        "tool_name": tool_call.tool_name,
                    },
                )

            records.append(
                {
                    "tool_name": "roll",
                    "result": roll_result,
                }
            )
            last_roll_result = roll_result
            continue

        unsupported_tools.append(tool_call.tool_name)
        records.append(
            {
                "tool_name": tool_call.tool_name,
                "status": "unsupported_in_stub",
            }
        )

    if last_roll_result is not None:
        count = int(last_roll_result["count"])
        sides = int(last_roll_result["sides"])
        modifier = int(last_roll_result["modifier"])
        total = int(last_roll_result["total"])
        modifier_text = f"{modifier:+d}" if modifier != 0 else ""
        summary_message = (
            f"Roll result: {count}d{sides}{modifier_text} = {total}"
        )
    else:
        summary_message = "Direct execution stub reached. No supported tools executed."

    if unsupported_tools:
        summary_message += (
            " Unsupported in stub: " + ", ".join(unsupported_tools)
        )

    return ExecutionResult(
        success=last_roll_result is not None,
        records=tuple(records),
        summary_message=summary_message,
        metadata={
            "user_id": context.user_id,
            "route_kind": route_decision.route_kind.value,
            "unsupported_tools": tuple(unsupported_tools),
        },
    )


async def _planner_execution_stub(
    context: DiscordRequestContext,
    planner_output: PlannerOutput,
) -> ExecutionResult:
    """
    Provide a placeholder planner-execution implementation for early Discord
    wiring.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized Discord request context.
    planner_output : PlannerOutput
        Output returned by the planner layer.

    Returns
    -------
    ExecutionResult
        Placeholder execution result.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Replace this stub with the real planner-selected tool execution layer.
    - This stub currently executes the `roll` tool by calling
      `tools.rolling.rolling.roll(...)`.
    """
    if not planner_output.tool_calls:
        summary_message = (
            planner_output.assistant_message
            or "Planner execution stub reached with no tool calls."
        )
        return ExecutionResult(
            success=True,
            records=(),
            summary_message=summary_message,
            metadata={"user_id": context.user_id},
        )

    roll_result: dict[str, object] | None = None
    unsupported_tools: list[str] = []

    for tool_call in planner_output.tool_calls:
        if tool_call.tool_name != "roll":
            unsupported_tools.append(tool_call.tool_name)
            continue

        request_value = tool_call.arguments.get("request", context.raw_text)
        request_text = (
            request_value if isinstance(request_value, str) else context.raw_text
        )
        context_value = tool_call.arguments.get("context")
        roll_context = context_value if isinstance(context_value, str) else None

        try:
            roll_result = await asyncio.wait_for(
                run_freeform_roll_async(
                    message=request_text,
                    context=roll_context,
                ),
                timeout=30.0,
            )
        except asyncio.TimeoutError:
            return ExecutionResult(
                success=False,
                records=(),
                summary_message=(
                    "Planner roll execution timed out after 30 seconds."
                ),
                metadata={
                    "user_id": context.user_id,
                    "tool_name": "roll",
                    "timeout_seconds": 30,
                },
            )
        except Exception as exc: # pylint: disable=broad-exception-caught
            return ExecutionResult(
                success=False,
                records=(),
                summary_message=f"Planner roll execution failed: {exc}",
                metadata={
                    "user_id": context.user_id,
                    "tool_name": "roll",
                },
            )

    if roll_result is not None:
        instances = roll_result.get("instances")
        totals: list[int] = []
        if isinstance(instances, list):
            for instance in instances:
                if isinstance(instance, dict):
                    total_value = instance.get("total")
                    if isinstance(total_value, int):
                        totals.append(total_value)
        totals_text = ", ".join(str(total) for total in totals) if totals else "unknown"
        summary_message = f"Roll result totals: {totals_text}"
    else:
        summary_message = "Planner execution stub reached. No supported tools executed."

    if unsupported_tools:
        summary_message += (
            " Unsupported in stub: " + ", ".join(unsupported_tools)
        )

    return ExecutionResult(
        success=roll_result is not None,
        records=(),
        summary_message=summary_message,
        metadata={
            "user_id": context.user_id,
            "unsupported_tools": tuple(unsupported_tools),
        },
    )


def build_intents(config: DiscordConfig) -> discord.Intents:
    """
    Build the discord.py intents required by the configured bot workflow.

    Parameters
    ----------
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    discord.Intents
        Configured Discord intents.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Guild and message intents are enabled for the hybrid bot workflow.
    - Message-content intent is enabled because mention-based free-text
      handling requires message content visibility.
    """
    _ = config

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    return intents


class DiscordBot(commands.Bot):
    """
    Purpose
    -------
    Provide the top-level discord.py bot implementation for the general
    Discord orchestration workflow.

    Key behaviors
    -------------
    - Store loaded runtime configuration.
    - Initialize message and slash-command handlers.
    - Register baseline slash commands on startup.
    - Sync the application command tree.
    - Forward message events into the shared message handler.

    Parameters
    ----------
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Attributes
    ----------
    config : DiscordConfig
        Loaded runtime configuration.
    message_handler : MessageHandler
        Shared message-based orchestration handler.
    slash_handler : SlashCommandHandler
        Shared slash-command orchestration handler.

    Notes
    -----
    - This class is intentionally thin and focused on top-level wiring.
    - Planner and execution behavior are still delegated through handler
      dependencies.
    """

    def __init__(self, config: DiscordConfig) -> None:
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=build_intents(config),
        )
        self.config = config
        self.message_handler = MessageHandler(
            config=config,
            planner_callable=_planner_stub,
            direct_execution_callable=_direct_execution_stub,
            planner_execution_callable=_planner_execution_stub,
        )
        self.slash_handler = SlashCommandHandler(
            config=config,
            direct_execution_callable=_direct_execution_stub,
        )

    async def setup_hook(self) -> None:
        """
        Perform asynchronous bot setup during startup.

        Parameters
        ----------
        None
            This method accepts no explicit parameters beyond `self`.

        Returns
        -------
        None
            This method returns no value.

        Raises
        ------
        discord.DiscordException
            Raised if command registration or sync fails.

        Notes
        -----
        - Slash commands are registered here before syncing.
        - Development-guild sync is used when configured for faster command
          iteration.
        """
        register_default_slash_commands(
            tree=self.tree,
            slash_handler=self.slash_handler,
        )

        if self.config.runtime.dev_guild_id is not None:
            guild = discord.Object(id=self.config.runtime.dev_guild_id)
            await self.tree.sync(guild=guild)
            LOGGER.info(
                "Synced slash commands to development guild %s",
                guild.id,
            )
            return

        await self.tree.sync()
        LOGGER.info("Synced global slash commands")

    async def on_ready(self) -> None:
        """
        Log successful bot startup.

        Parameters
        ----------
        None
            This method accepts no explicit parameters beyond `self`.

        Returns
        -------
        None
            This method returns no value.

        Raises
        ------
        RuntimeError
            This method does not raise RuntimeError directly.

        Notes
        -----
        - discord.py may call this more than once across reconnects.
        """
        if self.user is None:
            LOGGER.info("Discord bot connected, but user is not yet available.")
            return

        LOGGER.info(
            "Logged in as %s (%s)",
            self.user.name,
            self.user.id,
        )

    async def on_message(self, message: discord.Message) -> None: # pylint: disable=arguments-differ
        """
        Forward raw Discord messages into the shared message-handling pipeline.

        Parameters
        ----------
        message : discord.Message
            Raw discord.py message event.

        Returns
        -------
        None
            This method returns no value.

        Raises
        ------
        discord.DiscordException
            Raised if Discord reply sending fails.
        RuntimeError
            Raised if downstream message orchestration fails unexpectedly.

        Notes
        -----
        - Bot-authored messages are ignored by the downstream message handler.
        - This method intentionally does not call traditional prefix-command
          processing because the application is built around slash commands and
          mention-based natural-language routing.
        """
        bot_user_id = self.user.id if self.user is not None else None
        await self.message_handler.handle_message(
            message=message,
            bot_user_id=bot_user_id,
        )


def build_bot(config: DiscordConfig) -> DiscordBot:
    """
    Construct the configured Discord bot instance.

    Parameters
    ----------
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    DiscordBot
        Configured bot instance.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - Bot construction is kept in a helper so startup code remains small and
      testable.
    """
    return DiscordBot(config=config)


def configure_logging(config: DiscordConfig) -> None:
    """
    Configure process-level logging for the Discord bot.

    Parameters
    ----------
    config : DiscordConfig
        Loaded Discord runtime configuration.

    Returns
    -------
    None
        This function returns no value.

    Raises
    ------
    ValueError
        Raised if the configured log level is invalid for the standard logging
        module.

    Notes
    -----
    - Logging is configured once at process startup.
    """
    level_name = config.runtime.log_level.upper()
    level = cast(int, getattr(logging, level_name))
    logging.basicConfig(level=level)


def main() -> None:
    """
    Load configuration, construct the bot, and start the Discord client.

    Parameters
    ----------
    None
        This function accepts no parameters.

    Returns
    -------
    None
        This function returns no value.

    Raises
    ------
    RuntimeError
        Raised if required configuration is missing or invalid.
    discord.DiscordException
        Raised if discord.py fails during bot startup.

    Notes
    -----
    - This is the process entrypoint for the Discord application.
    - Replace the planner and execution stubs before using this in production.
    """
    load_dotenv()
    config = load_discord_config()
    configure_logging(config)
    bot = build_bot(config)
    bot.run(config.secrets.bot_token)


if __name__ == "__main__":
    main()
