"""
Purpose
-------
Provide an introspection utility for fillable character-sheet PDFs.
It discovers raw AcroForm field identifiers and their current values for manual inspection.

Key behaviors
-------------
- Opens a PDF and extracts all form field names and values via `pypdf` (AcroForm).

Conventions
-----------
- Output JSON is deterministic: field keys are sorted.
- Empty means: None, empty string, or whitespace-only string.
- Values are emitted as plain strings when present; no rich typing is inferred.

Downstream usage
----------------
Call `dump_pdf_fields(pdf_path)` to extract fields, then use the returned
mapping to author or update `field_map.py` (a hand-maintained mapping from
PDF field identifiers to internal ETL keys).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from pypdf import PdfReader


@dataclass(frozen=True)
class FieldDump:
    """
    Purpose
    -------
    Represent the extracted form-field catalog for a single PDF in a stable,
    serializable shape.

    Key behaviors
    -------------
    - Stores normalized field values as plain strings or None.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF that was inspected.
    field_count : int
        Number of distinct form field names extracted.
    fields : dict[str, str | None]
        Mapping from PDF field name to its normalized value (string or None).

    Attributes
    ----------
    pdf_path : str
        Path to the PDF that was inspected.
    field_count : int
        Number of distinct form field names extracted.
    fields : dict[str, str | None]
        Mapping from PDF field name to its normalized value (string or None).

    Notes
    -----
    - `field_count` should equal `len(fields)`.
    """

    pdf_path: str
    field_count: int
    fields: Dict[str, str | None]


def _normalize_value(value: Any) -> str | None:
    """
    Normalize a raw PDF form value into a string or None.

    Parameters
    ----------
    value : Any
        Raw value returned by the PDF form-field API.

    Returns
    -------
    str | None
        Trimmed string when non-empty, otherwise None.

    Notes
    -----
    - If the input is None, returns None.
    - If the input is a string, strips surrounding whitespace
      and returns None when the result is empty.
    - If the input is bytes or bytearray, attempts UTF-8 decoding with replacement
      for invalid bytes, then strips whitespace and returns None when empty.
    - If UTF-8 decoding fails unexpectedly, falls back to `str(value)` for bytes-like inputs.
    - If the input is an int, float, or bool, converts via `str(value)`,
      strips whitespace, and returns None when empty.
    - For any other object, converts via `str(value)`, strips whitespace,
      and returns None when empty.
    """

    if value is None:
        return None

    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed if trimmed else None

    if isinstance(value, (bytes, bytearray)):
        try:
            trimmed_b = bytes(value).decode("utf-8", errors="replace").strip()
        except Exception:  # pylint: disable=broad-exception-caught
            trimmed_b = str(value).strip()
        return trimmed_b if trimmed_b else None

    if isinstance(value, (int, float, bool)):
        s = str(value).strip()
        return s if s else None

    s2 = str(value).strip()
    return s2 if s2 else None


def _extract_with_pypdf(pdf_path: str) -> Dict[str, str | None]:
    """
    Extract PDF form fields using `pypdf`.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF.

    Returns
    -------
    dict[str, str | None]
        Mapping from field name to normalized value.

    Raises
    ------
    Exception
        Raised when `pypdf` cannot parse the PDF or retrieve fields.

    Notes
    -----
    - `PdfReader.get_fields()` returns a mapping from field name to `Field` objects.
    - Values are read from `Field.value` when present, otherwise `Field.default_value`.
    """

    reader: PdfReader = PdfReader(pdf_path)

    raw_fields: Dict[str, Any] | None = reader.get_fields()
    if not raw_fields:
        return {}

    out: Dict[str, str | None] = {}
    for name, field in raw_fields.items():
        raw_value = field.value
        if raw_value is None:
            raw_value = field.default_value
        out[name] = _normalize_value(raw_value)
    return out


def dump_pdf_fields(pdf_path: str) -> FieldDump:
    """
    Dump all form fields from a fillable PDF.

    Parameters
    ----------
    pdf_path : str
        Path to the PDF to inspect.

    Returns
    -------
    FieldDump
        Structured dump containing normalized fields.

    Raises
    ------
    RuntimeError
        Raised when `pypdf` cannot successfully read fields.

    Notes
    -----
    - Uses `pypdf` AcroForm introspection via `PdfReader.get_fields()`.
    """

    try:
        fields: Dict[str, str | None] = _extract_with_pypdf(pdf_path)
        return FieldDump(
            pdf_path=pdf_path,
            field_count=len(fields),
            fields=dict(sorted(fields.items(), key=lambda kv: kv[0])),
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        raise RuntimeError(f"Unable to extract PDF form fields with pypdf. Details: {e}") from e
