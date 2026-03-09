"""
Purpose
-------
Provide non-YAGNI unit coverage for direct dice rolling from normalized
Discord slash-command request contexts.

Key behaviors
-------------
- Verifies successful roll execution for valid `roll` slash commands.
- Verifies deterministic behavior for caller-supplied and seed-based RNG paths.
- Verifies validation and coercion rules for slash-command numeric options.

Conventions
-----------
- Uses lightweight test doubles instead of constructing full Discord boundary
  objects.
- Avoids Discord I/O, persistence, and unrelated integration concerns.
- Assumes downstream callers treat this file as pure unit coverage for
  `tools.rolling.discord_slash_roll` behavior.

Downstream usage
----------------
Run this module under pytest as part of the tooling or direct-command
execution test suite to protect dice-roll command behavior.
"""

from __future__ import annotations

import random
from types import SimpleNamespace
from typing import Any

import pytest

from tools.rolling.discord_slash_roll import _coerce_int_option, roll_from_slash_context
from tools.config import RANDOM_SEED

class TestRollFromSlashContext:
    """
    Purpose
    -------
    Group unit coverage for `roll_from_slash_context` so direct dice-roll
    command behavior is validated in one place.

    Key behaviors
    -------------
    - Verifies successful execution for defaulted and explicit roll options.
    - Verifies validation for missing slash payloads, wrong commands, and
      out-of-bounds numeric inputs.

    Parameters
    ----------
    None
        This pytest test class is not instantiated with custom constructor
        arguments.

    Attributes
    ----------
    None
        This test class stores no instance state; each test builds its own
        inputs.

    Notes
    -----
    - Uses helper-built request-context doubles instead of real Discord types.
    - Keeps coverage focused on unit-level command behavior rather than
      integration concerns.
    """

    @staticmethod
    def _make_context(
        *,
        command_name: str = "roll",
        options: dict[str, Any] | None = None,
        include_slash_command: bool = True,
    ) -> Any:
        """
        Build a lightweight normalized request-context test double.

        Parameters
        ----------
        command_name : str
            Slash command name exposed on the synthetic slash-command payload.
        options : dict[str, Any] | None
            Slash-command options mapping to expose on the synthetic payload.
        include_slash_command : bool
            Whether the returned object should include a slash-command payload
            at all.

        Returns
        -------
        Any
            Simple namespace object exposing the attributes accessed by
            `roll_from_slash_context`.

        Raises
        ------
        None
            This helper does not raise under normal test usage.

        Notes
        -----
        - Returns `SimpleNamespace(slash_command=None)` when the slash payload
          should be absent.
        - Avoids constructing full boundary-layer request objects in unit tests.
        """

        if not include_slash_command:
            return SimpleNamespace(slash_command=None)

        return SimpleNamespace(
            slash_command=SimpleNamespace(
                command_name=command_name,
                options={} if options is None else options,
            )
        )

    def test_roll_uses_defaults_when_options_are_missing(self) -> None:
        """
        Verify default roll parameters are applied when no slash options exist.

        Parameters
        ----------
        None
            This test receives no explicit parameters.

        Returns
        -------
        None
            This test asserts on the returned roll payload.

        Raises
        ------
        AssertionError
            If the returned payload does not match the expected default roll
            behavior.

        Notes
        -----
        - Uses a caller-supplied RNG to make the expected roll sequence exact.
        """

        context = self._make_context()
        rng = random.Random(123)

        result = roll_from_slash_context(context, rng=rng)

        expected_rng = random.Random(123)
        expected_rolls = [expected_rng.randint(1, 20)]

        assert result == {
            "command_name": "roll",
            "count": 1,
            "sides": 20,
            "modifier": 0,
            "rolls": expected_rolls,
            "total": sum(expected_rolls),
        }

    def test_roll_uses_explicit_integer_options(self) -> None:
        """
        Verify explicit integer slash options are preserved in the roll result.

        Parameters
        ----------
        None
            This test receives no explicit parameters.

        Returns
        -------
        None
            This test asserts on the returned roll payload.

        Raises
        ------
        AssertionError
            If explicit count, sides, modifier, or derived totals differ from
            the expected values.

        Notes
        -----
        - Confirms the function uses integer options without additional
          transformation beyond validation.
        """

        context = self._make_context(
            options={
                "count": 3,
                "sides": 6,
                "modifier": 2,
            }
        )
        rng = random.Random(7)

        result = roll_from_slash_context(context, rng=rng)

        expected_rng = random.Random(7)
        expected_rolls = [expected_rng.randint(1, 6) for _ in range(3)]

        assert result == {
            "command_name": "roll",
            "count": 3,
            "sides": 6,
            "modifier": 2,
            "rolls": expected_rolls,
            "total": sum(expected_rolls) + 2,
        }

    def test_roll_normalizes_command_name_before_validation(self) -> None:
        """
        Verify command-name whitespace and casing are normalized before checks.

        Parameters
        ----------
        None
            This test receives no explicit parameters.

        Returns
        -------
        None
            This test asserts on the normalized command name in the result.

        Raises
        ------
        AssertionError
            If the command name is not normalized to lowercase `roll`.

        Notes
        -----
        - Exercises `.strip().lower()` behavior through the public function.
        """

        context = self._make_context(command_name="  RoLl  ")

        result = roll_from_slash_context(context, rng=random.Random(11))

        assert result["command_name"] == "roll"

    def test_roll_ignores_unknown_options(self) -> None:
        """
        Verify unrelated slash options do not alter roll execution semantics.

        Parameters
        ----------
        None
            This test receives no explicit parameters.

        Returns
        -------
        None
            This test asserts on the resulting payload contents.

        Raises
        ------
        AssertionError
            If unknown options leak into the response or alter valid roll
            fields.

        Notes
        -----
        - Confirms this module reads only supported option names.
        """

        context = self._make_context(
            options={
                "count": 2,
                "sides": 8,
                "modifier": 1,
                "flavor": "fire",
                "ephemeral": True,
            }
        )
        rng = random.Random(99)

        result = roll_from_slash_context(context, rng=rng)

        expected_rng = random.Random(99)
        expected_rolls = [expected_rng.randint(1, 8) for _ in range(2)]

        assert result["rolls"] == expected_rolls
        assert result["total"] == sum(expected_rolls) + 1
        assert set(result.keys()) == {
            "command_name",
            "count",
            "sides",
            "modifier",
            "rolls",
            "total",
        }

    def test_roll_uses_seeded_rng_when_rng_is_not_supplied(self) -> None:
        """
        Verify the fallback RNG path uses deterministic seed-based randomness.

        Parameters
        ----------
        None
            This test receives no explicit parameters.

        Returns
        -------
        None
            This test asserts on the seeded roll payload.

        Raises
        ------
        AssertionError
            If the implicit RNG path diverges from `random.Random(RANDOM_SEED)`.

        Notes
        -----
        - Protects the contract that omitted RNG input still yields stable unit
          test behavior.
        """

        context = self._make_context(
            options={
                "count": 4,
                "sides": 10,
                "modifier": -1,
            }
        )

        result = roll_from_slash_context(context)

        expected_rng = random.Random(RANDOM_SEED)
        expected_rolls = [expected_rng.randint(1, 10) for _ in range(4)]

        assert result == {
            "command_name": "roll",
            "count": 4,
            "sides": 10,
            "modifier": -1,
            "rolls": expected_rolls,
            "total": sum(expected_rolls) - 1,
        }

    @pytest.mark.parametrize(
        ("include_slash_command", "command_name", "expected_message"),
        [
            (False, "roll", "Slash command payload is missing from request context"),
            (True, "attack", "Slash command is not 'roll'"),
        ],
    )
    def test_roll_rejects_missing_or_non_roll_commands(
        self,
        include_slash_command: bool,
        command_name: str,
        expected_message: str,
    ) -> None:
        """
        Verify invalid command contexts raise the expected `ValueError`.

        Parameters
        ----------
        include_slash_command : bool
            Whether the synthetic request context includes a slash payload.
        command_name : str
            Command name exposed by the synthetic slash payload.
        expected_message : str
            Regex pattern expected in the raised `ValueError` message.

        Returns
        -------
        None
            This test asserts on the raised exception.

        Raises
        ------
        AssertionError
            If `ValueError` is not raised or the message does not match.

        Notes
        -----
        - Covers both missing slash payloads and wrong command names.
        """

        context = self._make_context(
            command_name=command_name,
            include_slash_command=include_slash_command,
        )

        with pytest.raises(ValueError, match=expected_message):
            roll_from_slash_context(context)

    @pytest.mark.parametrize(
        ("options", "expected_message"),
        [
            ({"count": 0}, "count must be >= 1"),
            ({"count": 101}, "count must be <= 100"),
            ({"sides": 1}, "sides must be >= 2"),
            ({"sides": 1001}, "sides must be <= 1000"),
        ],
    )
    def test_roll_rejects_out_of_bounds_numeric_options(
        self,
        options: dict[str, Any],
        expected_message: str,
    ) -> None:
        """
        Verify numeric bounds are enforced after option coercion.

        Parameters
        ----------
        options : dict[str, Any]
            Slash-command options mapping passed into the synthetic request.
        expected_message : str
            Regex pattern expected in the raised `ValueError` message.

        Returns
        -------
        None
            This test asserts on the raised exception.

        Raises
        ------
        AssertionError
            If out-of-range numeric options are accepted or the error message
            differs.

        Notes
        -----
        - Covers both lower and upper bounds for count and sides.
        """

        context = self._make_context(options=options)

        with pytest.raises(ValueError, match=expected_message):
            roll_from_slash_context(context)

    def test_roll_accepts_string_numeric_options_after_coercion(self) -> None:
        """
        Verify numeric string options are coerced before roll execution.

        Parameters
        ----------
        None
            This test receives no explicit parameters.

        Returns
        -------
        None
            This test asserts on the returned payload after coercion.

        Raises
        ------
        AssertionError
            If string-valued numeric options are not converted into the expected
            integer fields and totals.

        Notes
        -----
        - Exercises whitespace-trimmed numeric-string handling through the
          public API.
        """

        context = self._make_context(
            options={
                "count": " 2 ",
                "sides": "12",
                "modifier": " -3 ",
            }
        )
        rng = random.Random(5)

        result = roll_from_slash_context(context, rng=rng)

        expected_rng = random.Random(5)
        expected_rolls = [expected_rng.randint(1, 12) for _ in range(2)]

        assert result == {
            "command_name": "roll",
            "count": 2,
            "sides": 12,
            "modifier": -3,
            "rolls": expected_rolls,
            "total": sum(expected_rolls) - 3,
        }


class TestCoerceIntOption:
    """
    Purpose
    -------
    Group unit coverage for `_coerce_int_option` so slash-option integer
    normalization rules are validated independently.

    Key behaviors
    -------------
    - Verifies supported coercion paths for defaults, integers, and strings.
    - Verifies invalid booleans, empty strings, and unsupported types are
      rejected.

    Parameters
    ----------
    None
        This pytest test class is not instantiated with custom constructor
        arguments.

    Attributes
    ----------
    None
        This test class stores no instance state; each test supplies its own
        inputs.

    Notes
    -----
    - Keeps helper-level coercion coverage separate from full command tests.
    - Makes failure causes more localized when integer-option parsing changes.
    """

    @pytest.mark.parametrize(
        ("value", "default", "expected"),
        [
            (None, 9, 9),
            (4, 0, 4),
            ("7", 0, 7),
            ("  -12 ", 0, -12),
        ],
    )
    def test_coerce_int_option_returns_expected_integer(
        self,
        value: Any,
        default: int,
        expected: int,
    ) -> None:
        """
        Verify supported option shapes coerce into the expected integer.

        Parameters
        ----------
        value : Any
            Raw option value supplied to `_coerce_int_option`.
        default : int
            Default integer used when `value` is `None`.
        expected : int
            Expected integer result after coercion.

        Returns
        -------
        None
            This test asserts on the coercion result.

        Raises
        ------
        AssertionError
            If a supported input does not produce the expected integer.

        Notes
        -----
        - Covers the valid coercion contract for `None`, `int`, and numeric
          `str` inputs.
        """

        assert _coerce_int_option(value, default=default) == expected

    @pytest.mark.parametrize(
        ("value", "expected_message"),
        [
            (True, "boolean is not a valid integer option"),
            (False, "boolean is not a valid integer option"),
            ("   ", "empty string is not a valid integer option"),
            ("abc", "invalid integer option: abc"),
            (1.5, "unsupported option type for integer coercion"),
            ([1], "unsupported option type for integer coercion"),
            ({"value": 1}, "unsupported option type for integer coercion"),
        ],
    )
    def test_coerce_int_option_rejects_invalid_values(
        self,
        value: Any,
        expected_message: str,
    ) -> None:
        """
        Verify invalid option values raise `ValueError` with the right message.

        Parameters
        ----------
        value : Any
            Raw option value supplied to `_coerce_int_option`.
        expected_message : str
            Regex pattern expected in the raised `ValueError` message.

        Returns
        -------
        None
            This test asserts on the raised exception.

        Raises
        ------
        AssertionError
            If invalid input is accepted or the error message differs.

        Notes
        -----
        - Covers booleans, empty strings, malformed numeric strings, and
          unsupported container or float inputs.
        """

        with pytest.raises(ValueError, match=expected_message):
            _coerce_int_option(value, default=0)
