"""
Purpose
-------
Test the `tools.rolling` module's minimal bridge between BAML parsing and
deterministic roll execution.

Key behaviors
-------------
- Verifies `parse_message_to_roll_plan` forwards inputs to the BAML client call.
- Verifies `execute_roll_plan` enforces core invariants and applies 5e semantics
  (repeat, flat modifier once per instance, advantage/disadvantage only for d20).
- Verifies `roll` composes parsing + execution.

Conventions
-----------
- Tests avoid any dependency on a real BAML runtime by monkeypatching the
  imported `b` object inside `tools.rolling`.
- Randomness is controlled via a seeded `random.Random` instance.

Downstream usage
----------------
Run with `pytest` as part of the project test suite to ensure changes to the
BAML bridge or execution semantics remain compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Any, List, cast
import pytest

from baml_client.types import RollPlan

from tools.rolling import rolling


@dataclass(frozen=True)
class _FakeMode:
    """
    Purpose
    -------
    Provide a minimal enum-like object compatible with `plan.mode.value`.

    Key behaviors
    -------------
    - Exposes a `value` attribute used by `execute_roll_plan`.

    Parameters
    ----------
    value : str
        One of "NORMAL", "ADVANTAGE", or "DISADVANTAGE".

    Attributes
    ----------
    value : str
        Schema string representing the roll mode.

    Notes
    -----
    - This mirrors the single attribute accessed by `rolling.py`.
    """

    value: str


@dataclass(frozen=True)
class _FakeDiceTerm:
    """
    Purpose
    -------
    Provide a minimal dice term compatible with `plan.dice` access.

    Key behaviors
    -------------
    - Exposes `count` and `sides` attributes.

    Parameters
    ----------
    count : int
        Number of dice.
    sides : int
        Sides per die.

    Attributes
    ----------
    count : int
        Number of dice.
    sides : int
        Sides per die.

    Notes
    -----
    - This mirrors the attributes accessed by `rolling.py`.
    """

    count: int
    sides: int


@dataclass
class _FakeRollPlan:
    """
    Purpose
    -------
    Provide a minimal RollPlan-like object for execution tests.

    Key behaviors
    -------------
    - Matches the attributes read by `execute_roll_plan`.

    Parameters
    ----------
    dice : list[_FakeDiceTerm]
        Dice terms rolled per instance.
    modifier : int
        Flat modifier applied once per instance.
    repeat : int
        Number of independent instances.
    mode : _FakeMode
        Roll mode used for d20 handling.
    label : str | None
        Optional label.

    Attributes
    ----------
    dice : list[_FakeDiceTerm]
        Dice terms.
    modifier : int
        Flat modifier.
    repeat : int
        Repeat count.
    mode : _FakeMode
        Roll mode.
    label : str | None
        Optional label.

    Notes
    -----
    - The production code annotates with `baml_client.types.RollPlan`, but the
      runtime behavior depends only on these attributes.
    """

    dice: List[_FakeDiceTerm]
    modifier: int
    repeat: int
    mode: _FakeMode
    label: str | None = None


def test_parse_message_to_roll_plan_forwards_to_baml(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure `parse_message_to_roll_plan` forwards the message and context to BAML.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Pytest fixture used to replace the imported BAML client.

    Returns
    -------
    None
        This test asserts expected call forwarding.

    Raises
    ------
    AssertionError
        Raised if arguments are not forwarded or return value mismatches.

    Notes
    -----
    - We monkeypatch `tools.rolling.b` because it is imported at module import
      time and then referenced directly.
    """

    called: dict[str, Any] = {}

    class _BamlStub:
        def Roll(self, request: str, context: str | None) -> Any:
            called["request"] = request
            called["context"] = context
            return "PLAN"

    monkeypatch.setattr(rolling, "b", _BamlStub())

    out = rolling.parse_message_to_roll_plan("roll perception +5", context="ctx")

    assert out == "PLAN"
    assert called["request"] == "roll perception +5"
    assert called["context"] == "ctx"


def test_execute_roll_plan_repeats_and_applies_modifier_once_per_instance() -> None:
    """
    Ensure `repeat` creates independent instances and `modifier` applies once.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test asserts totals follow repeat/modifier semantics.

    Raises
    ------
    AssertionError
        Raised if totals or instance count do not match the plan.

    Notes
    -----
    - We use a seeded RNG so this test is deterministic.
    """

    plan = _FakeRollPlan(
        dice=[_FakeDiceTerm(count=1, sides=6)],
        modifier=2,
        repeat=3,
        mode=_FakeMode("NORMAL"),
        label="Test",
    )

    rng = random.Random(12345)
    result = rolling.execute_roll_plan(cast(RollPlan, plan), rng=rng)

    assert result["label"] == "Test"
    assert result["repeat"] == 3
    assert len(result["instances"]) == 3

    for inst in result["instances"]:
        assert inst["total"] == inst["total_before_modifier"] + 2


def test_execute_roll_plan_advantage_records_raw_rolls_for_d20_terms() -> None:
    """
    Ensure advantage on d20 rolls two dice and keeps the higher for each d20 die.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test asserts raw_rolls length and kept roll semantics.

    Raises
    ------
    AssertionError
        Raised if raw_rolls/kept rolls do not match advantage semantics.

    Notes
    -----
    - This test validates only the d20 behavior; non-d20 terms are unaffected.
    """

    plan = _FakeRollPlan(
        dice=[_FakeDiceTerm(count=2, sides=20)],
        modifier=0,
        repeat=1,
        mode=_FakeMode("ADVANTAGE"),
        label=None,
    )

    rng = random.Random(7)
    result = rolling.execute_roll_plan(cast(RollPlan, plan), rng=rng)

    inst = result["instances"][0]
    term = inst["terms"][0]

    assert term["sides"] == 20
    assert term["count"] == 2
    assert term["raw_rolls"] is not None
    assert len(term["raw_rolls"]) == 4
    assert len(term["rolls"]) == 2

    a1, b1, a2, b2 = term["raw_rolls"]
    assert term["rolls"][0] == max(a1, b1)
    assert term["rolls"][1] == max(a2, b2)


def test_execute_roll_plan_disadvantage_keeps_lower_for_d20_terms() -> None:
    """
    Ensure disadvantage on d20 rolls two dice and keeps the lower.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test asserts kept-roll semantics for disadvantage.

    Raises
    ------
    AssertionError
        Raised if kept rolls do not match disadvantage semantics.

    Notes
    -----
    - Uses a seeded RNG for determinism.
    """

    plan = _FakeRollPlan(
        dice=[_FakeDiceTerm(count=1, sides=20)],
        modifier=0,
        repeat=1,
        mode=_FakeMode("DISADVANTAGE"),
    )

    rng = random.Random(99)
    result = rolling.execute_roll_plan(cast(RollPlan, plan), rng=rng)

    term = result["instances"][0]["terms"][0]
    a, b = term["raw_rolls"]
    assert term["rolls"][0] == min(a, b)


def test_execute_roll_plan_raises_on_repeat_less_than_one() -> None:
    """
    Ensure `repeat < 1` is rejected.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test asserts `ValueError` is raised.

    Raises
    ------
    AssertionError
        Raised if `ValueError` is not raised.

    Notes
    -----
    - This enforces the RollPlan invariant `repeat >= 1`.
    """

    plan = _FakeRollPlan(
        dice=[_FakeDiceTerm(count=1, sides=6)],
        modifier=0,
        repeat=0,
        mode=_FakeMode("NORMAL"),
    )

    with pytest.raises(ValueError, match="plan\\.repeat"):
        rolling.execute_roll_plan(cast(RollPlan, plan), rng=random.Random(1))


def test_execute_roll_plan_raises_on_empty_dice() -> None:
    """
    Ensure an empty dice list is rejected.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test asserts `ValueError` is raised.

    Raises
    ------
    AssertionError
        Raised if `ValueError` is not raised.

    Notes
    -----
    - The executor requires at least one DiceTerm.
    """

    plan = _FakeRollPlan(
        dice=[],
        modifier=0,
        repeat=1,
        mode=_FakeMode("NORMAL"),
    )

    with pytest.raises(ValueError, match="plan\\.dice"):
        rolling.execute_roll_plan(cast(RollPlan, plan), rng=random.Random(1))


def test_execute_roll_plan_raises_when_advantage_without_d20() -> None:
    """
    Ensure advantage/disadvantage is rejected if no d20 term exists.

    Parameters
    ----------
    None

    Returns
    -------
    None
        This test asserts `ValueError` is raised.

    Raises
    ------
    AssertionError
        Raised if `ValueError` is not raised.

    Notes
    -----
    - This mirrors the schema intent that mode affects only d20 terms.
    """

    plan = _FakeRollPlan(
        dice=[_FakeDiceTerm(count=1, sides=6)],
        modifier=0,
        repeat=1,
        mode=_FakeMode("ADVANTAGE"),
    )

    with pytest.raises(ValueError, match="d20"):
        rolling.execute_roll_plan(cast(RollPlan, plan), rng=random.Random(1))


def test_roll_composes_parse_and_execute(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Ensure `roll` calls BAML parsing and then executes the returned plan.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Fixture used to replace the BAML client with a stub.

    Returns
    -------
    None
        This test asserts the composed call path works.

    Raises
    ------
    AssertionError
        Raised if the result does not reflect the stubbed plan.

    Notes
    -----
    - This is intentionally minimal and validates only the happy path.
    """

    plan = _FakeRollPlan(
        dice=[_FakeDiceTerm(count=1, sides=4)],
        modifier=1,
        repeat=2,
        mode=_FakeMode("NORMAL"),
        label="Magic Missile",
    )

    class _BamlStub:
        def Roll(self, request: str, context: str | None) -> Any: # pylint: disable=unused-argument
            return plan

    monkeypatch.setattr(rolling, "b", _BamlStub())

    rng = random.Random(5)
    result = rolling.roll("cast magic missile", context=None, rng=rng)

    assert result["label"] == "Magic Missile"
    assert result["repeat"] == 2
    assert len(result["instances"]) == 2
