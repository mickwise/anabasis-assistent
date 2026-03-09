"""
Purpose
-------
Handle direct dice rolling for normalized Discord slash-command requests.

Key behaviors
-------------
- Accept a normalized Discord slash-command request context.
- Execute a die roll only when the slash command is `roll`.
- Return a structured payload suitable for direct-command execution responses.

Conventions
-----------
- Uses a caller-supplied `random.Random` when provided.
- Falls back to deterministic seed-based randomness from `tools.config`.
- This module performs no Discord I/O and no persistence.

Downstream usage
----------------
Call `roll_from_slash_context(context)` inside your direct-command execution
layer. If the incoming slash command is not `roll`, this module raises
`ValueError`.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

from discord_adapter.discord_types import DiscordRequestContext
from tools.config import RANDOM_SEED


def roll_from_slash_context(
    context: DiscordRequestContext,
    rng: random.Random | None = None,
) -> Dict[str, Any]:
    """
    Roll dice from a normalized Discord slash-command request.

    Parameters
    ----------
    context : DiscordRequestContext
        Normalized request context produced by the Discord boundary layer.
    rng : random.Random | None
        Optional RNG. If omitted, a deterministic seeded RNG is used.

    Returns
    -------
    dict
        Structured result with keys:
        - command_name: str
        - count: int
        - sides: int
        - modifier: int
        - rolls: list[int]
        - total: int

    Raises
    ------
    ValueError
        If the request is not a slash command, command name is not `roll`, or
        numeric options are invalid.

    Notes
    -----
    - Supported slash options (all optional):
        * `count` (int, default 1)
        * `sides` (int, default 20)
        * `modifier` (int, default 0)
    - Unknown options are ignored by this module.
    """

    if context.slash_command is None:
        raise ValueError("Slash command payload is missing from request context")

    command_name: str = context.slash_command.command_name.strip().lower()
    if command_name != "roll":
        raise ValueError("Slash command is not 'roll'")

    options: Dict[str, Any] = context.slash_command.options

    count: int = _coerce_int_option(options.get("count"), default=1)
    sides: int = _coerce_int_option(options.get("sides"), default=20)
    modifier: int = _coerce_int_option(options.get("modifier"), default=0)

    if count < 1:
        raise ValueError("count must be >= 1")
    if count > 100:
        raise ValueError("count must be <= 100")
    if sides < 2:
        raise ValueError("sides must be >= 2")
    if sides > 1000:
        raise ValueError("sides must be <= 1000")

    effective_rng: random.Random = rng if rng is not None else random.Random(RANDOM_SEED)

    rolls: List[int] = [effective_rng.randint(1, sides) for _ in range(count)]
    total: int = sum(rolls) + modifier

    return {
        "command_name": command_name,
        "count": count,
        "sides": sides,
        "modifier": modifier,
        "rolls": rolls,
        "total": total,
    }


def _coerce_int_option(value: Any, default: int) -> int:
    """
    Coerce an incoming slash-command option to integer.

    Parameters
    ----------
    value : Any
        Raw option value from normalized slash-command options.
    default : int
        Default integer when value is None.

    Returns
    -------
    int
        Coerced integer value.

    Raises
    ------
    ValueError
        If conversion fails.
    """

    if value is None:
        return default

    if isinstance(value, bool):
        raise ValueError("boolean is not a valid integer option")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            raise ValueError("empty string is not a valid integer option")
        try:
            return int(stripped)
        except ValueError as err:
            raise ValueError(f"invalid integer option: {value}") from err

    raise ValueError(f"unsupported option type for integer coercion: {type(value)!r}")
