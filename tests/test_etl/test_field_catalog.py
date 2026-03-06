"""
Purpose
-------
Unit tests for the PDF field catalog introspection utilities.

Key behaviors
-------------
- Validates normalization rules for raw PDF form values.
- Verifies pypdf extraction behavior via a fully mocked PdfReader.
- Ensures `dump_pdf_fields` returns deterministic, sorted output.
- Ensures parse failures are wrapped as RuntimeError with useful context.

Conventions
-----------
- Tests do not require real PDFs; all `pypdf.PdfReader` behavior is mocked.
- Determinism is asserted by checking sorted keys and stable field_count.
- Empty values are treated as None: None, empty string, or whitespace-only.

Downstream usage
----------------
Run with pytest:
    pytest -q

These tests guard the deterministic contract expected by mapping/ingestion code
that consumes `FieldDump`.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any, Dict, Optional

import pytest

from etl.character_sheet.field_catalog import (
    FieldDump,
    _extract_with_pypdf,
    _normalize_value,
    dump_pdf_fields,
)
import  etl.character_sheet.field_catalog as field_catalog


class _FakePdfField:
    """
    Purpose
    -------
    Provide a minimal stand-in for a pypdf Field object.

    Key behaviors
    -------------
    - Exposes `.value` and `.default_value` attributes used by the extractor.

    Parameters
    ----------
    value : Any
        Primary field value.
    default_value : Any
        Fallback value when primary value is None.

    Attributes
    ----------
    value : Any
        Primary field value.
    default_value : Any
        Fallback value when primary value is None.

    Notes
    -----
    - This is intentionally tiny: the production code only reads two attributes.
    """

    def __init__(self, value: Any, default_value: Any) -> None:
        self.value = value
        self.default_value = default_value


class _FakePdfReader:
    """
    Purpose
    -------
    Provide a controllable fake PdfReader compatible with the extractor.

    Key behaviors
    -------------
    - Returns a predetermined mapping from `get_fields()`.

    Parameters
    ----------
    fields : dict[str, Any] | None
        Mapping from field name to fake Field object.

    Attributes
    ----------
    _fields : dict[str, Any] | None
        Stored fields returned by `get_fields()`.

    Notes
    -----
    - The production extractor treats falsy return values as "no fields".
    """

    def __init__(self, fields: Optional[Dict[str, Any]]) -> None:
        self._fields = fields

    def get_fields(self) -> Optional[Dict[str, Any]]:
        """
        Return the preconfigured field mapping.

        Parameters
        ----------
        None
            This method accepts no parameters.

        Returns
        -------
        dict[str, Any] | None
            The mapping passed at construction time.

        Notes
        -----
        - Matches the `pypdf.PdfReader.get_fields()` contract used by the code.
        """

        return self._fields


def test_normalize_value_none_returns_none() -> None:
    """
    _normalize_value returns None when input is None.

    Parameters
    ----------
    None
        This test takes no parameters.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - None is treated as empty by the module contract.
    """

    assert _normalize_value(None) is None


def test_normalize_value_strips_whitespace_and_empty_to_none() -> None:
    """
    _normalize_value strips surrounding whitespace and maps empty strings to None.

    Parameters
    ----------
    None
        This test takes no parameters.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - Whitespace-only strings are considered empty.
    """

    assert _normalize_value("  hello  ") == "hello"
    assert _normalize_value("") is None
    assert _normalize_value("   \t\n  ") is None


def test_normalize_value_bytes_decodes_utf8_with_replacement_and_strips() -> None:
    """
    _normalize_value decodes bytes as UTF-8 with replacement and strips whitespace.

    Parameters
    ----------
    None
        This test takes no parameters.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - Invalid bytes must not raise; they should decode with replacement.
    - Result is stripped and mapped to None if empty.
    """

    assert _normalize_value(b"  abc  ") == "abc"

    out = _normalize_value(b"\xff\xfe")
    assert out is not None
    assert isinstance(out, str)

    assert _normalize_value(b"   ") is None


def test_normalize_value_numeric_and_bool_are_stringified() -> None:
    """
    _normalize_value stringifies numeric and boolean values.

    Parameters
    ----------
    None
        This test takes no parameters.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - The module contract emits plain strings; no rich typing is inferred.
    """

    assert _normalize_value(7) == "7"
    assert _normalize_value(3.5) == "3.5"
    assert _normalize_value(True) == "True"


def test_normalize_value_fallback_object_stripping() -> None:
    """
    _normalize_value falls back to str(value) for non-primitive objects.

    Parameters
    ----------
    None
        This test takes no parameters.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - Any object should be representable without raising.
    """

    class _X:
        def __str__(self) -> str:
            return "  X  "

    assert _normalize_value(_X()) == "X"


def test_extract_with_pypdf_returns_empty_dict_when_no_fields(monkeypatch: Any) -> None:
    """
    _extract_with_pypdf returns an empty mapping when PdfReader.get_fields is falsy.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - The production code treats None/{} as "no fields".
    """

    def _fake_reader(_: str) -> _FakePdfReader:
        return _FakePdfReader(fields=None)

    monkeypatch.setattr(field_catalog, "PdfReader", _fake_reader)

    assert _extract_with_pypdf("/tmp/x.pdf") == {}


def test_extract_with_pypdf_prefers_value_over_default_and_normalizes(monkeypatch: Any) -> None:
    """
    _extract_with_pypdf prefers Field.value, falls back to Field.default_value,
    and normalizes values.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - This test exercises the field selection policy and normalization.
    """

    fields: Dict[str, Any] = {
        "A": _FakePdfField(value="  hi ", default_value="ignored"),
        "B": _FakePdfField(value=None, default_value="  dv  "),
        "C": _FakePdfField(value="   ", default_value="  also_ignored  "),
        "D": _FakePdfField(value=None, default_value=None),
        "E": _FakePdfField(value=7, default_value=None),
    }

    def _fake_reader(_: str) -> _FakePdfReader:
        return _FakePdfReader(fields=fields)

    monkeypatch.setattr(field_catalog, "PdfReader", _fake_reader)

    out = _extract_with_pypdf("/tmp/x.pdf")
    assert out["A"] == "hi"
    assert out["B"] == "dv"
    assert out["C"] is None
    assert out["D"] is None
    assert out["E"] == "7"


def test_dump_pdf_fields_returns_sorted_keys_and_correct_count(monkeypatch: Any) -> None:
    """
    dump_pdf_fields returns FieldDump with sorted keys and accurate field_count.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - Determinism requires sorted keys.
    - field_count must equal len(fields).
    """

    fields: Dict[str, Any] = {
        "zeta": _FakePdfField(value="Z", default_value=None),
        "alpha": _FakePdfField(value="A", default_value=None),
        "mid": _FakePdfField(value=None, default_value="M"),
    }

    def _fake_reader(_: str) -> _FakePdfReader:
        return _FakePdfReader(fields=fields)

    monkeypatch.setattr(field_catalog, "PdfReader", _fake_reader)

    dump = dump_pdf_fields("/tmp/sheet.pdf")
    assert isinstance(dump, FieldDump)
    assert dump.pdf_path == "/tmp/sheet.pdf"

    assert list(dump.fields.keys()) == ["alpha", "mid", "zeta"]
    assert dump.field_count == 3
    assert dump.field_count == len(dump.fields)


def test_dump_pdf_fields_wraps_pypdf_exceptions_in_runtime_error(monkeypatch: Any) -> None:
    """
    dump_pdf_fields wraps underlying pypdf failures in a RuntimeError.

    Parameters
    ----------
    monkeypatch : Any
        Pytest monkeypatch fixture.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Raises
    ------
    RuntimeError
        The function under test raises this error, which is asserted.

    Notes
    -----
    - The wrapper message must include a stable prefix and preserve details.
    """

    def _boom(_: str) -> None:
        raise ValueError("parse failed")

    monkeypatch.setattr(field_catalog, "_extract_with_pypdf", _boom)

    with pytest.raises(RuntimeError) as excinfo:
        dump_pdf_fields("/tmp/bad.pdf")

    msg = str(excinfo.value)
    assert msg.startswith("Unable to extract PDF form fields with pypdf.")
    assert "parse failed" in msg


def test_fielddump_is_frozen_dataclass() -> None:
    """
    FieldDump is a frozen dataclass and cannot be mutated.

    Parameters
    ----------
    None
        This test takes no parameters.

    Returns
    -------
    None
        The test asserts behavior via expectations.

    Notes
    -----
    - Immutability is important for stability and safe caching.
    """

    dump = FieldDump(pdf_path="/tmp/x.pdf", field_count=0, fields={})
    with pytest.raises(FrozenInstanceError):
        dump.field_count = 1  # type: ignore[misc]
