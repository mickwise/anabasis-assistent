"""
Purpose
-------
Parse the spellcasting page fields from the PDF field dump and persist them into
the `player_spells` SQL table.

Key behaviors
-------------
- Reads the `FIELD_MAP["player_spells"]` mapping to locate spellcasting-page PDF
  fields.
- Extracts spellcasting header fields and slot totals from the field dump.
- Iterates over all spell-name fields, resolves each spell in the `spells` table
  to determine its level, and stores per-level spell lists as JSONB arrays.
- Inserts one `player_spells` row and returns its `spells_id` to the pipeline.
- Records missing spell names as structured ingestion warnings.

Conventions
-----------
- This module is deterministic and performs no LLM calls.
- Inputs are assumed to be produced earlier in the pipeline:
  - `field_dump` comes from the PDF field-catalog step.
  - `FIELD_MAP` is loaded from `etl.character_sheet.config`.
- The field map is trusted. If a mapped field name is not present in the field
  dump, this is treated as an unsupported PDF schema and this module raises.
- Empty/whitespace spell fields are ignored.
- Spells are resolved case-insensitively by exact name match.
- Slot expended fields are not present in the current template mapping and are
  stored as NULL.

Downstream usage
----------------
The pipeline orchestrator should call `ingest_spells(conn, field_dump)` after
extracting the PDF field dump and before inserting the owning `character_sheet`
row, so the returned `spells_id` can be set on the character sheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb

from etl.character_sheet.config import FIELD_MAP
from etl.character_sheet.field_catalog import FieldDump

from baml_client.types import CharacterSheetIngestionError
from baml_client.types import CharacterSheetIngestionErrorType


@dataclass(frozen=True)
class SpellExtractionResult:
    """
    Purpose
    -------
    Represent the outcome of ingesting a single spellcasting-page block.

    Key behaviors
    -------------
    - Stores the UUID of the newly inserted `player_spells` row.
    - Carries non-critical ingestion warnings for downstream aggregation.

    Parameters
    ----------
    spells_id : UUID
        Primary key of the inserted `player_spells` row.
    missing_spells : list[CharacterSheetIngestionError]
        Structured warnings emitted during ingestion.

    Attributes
    ----------
    spells_id : UUID
        Primary key of the inserted `player_spells` row.
    missing_spells : list[CharacterSheetIngestionError]
        Structured warnings emitted during ingestion.

    Notes
    -----
    - This result is produced by deterministic host code.
    """

    spells_id: UUID
    missing_spells: List[CharacterSheetIngestionError]


def ingest_spells(conn: Connection[Any], field_dump: FieldDump) -> SpellExtractionResult:
    """
    Insert a `player_spells` row from the spellcasting page fields.

    Parameters
    ----------
    conn : Connection[Any]
        Open psycopg connection used for all reads and writes.
    field_dump : FieldDump
        Field dump produced by the PDF field-catalog step.

    Returns
    -------
    SpellExtractionResult
        The inserted `spells_id` and any structured missing-spell warnings.

    Raises
    ------
    KeyError
        If the field dump does not contain a mapped PDF field name. This
        indicates an unsupported PDF schema for the configured template.

    Notes
    -----
    - This function performs a single insert into `player_spells`.
    - Spell lists are stored per-level (0..9) as JSONB arrays.
    """

    mapping: Dict[str, Any] = FIELD_MAP["player_spells"]

    row: Dict[str, Any] = {}

    row["spellcasting_class"] = _get_text_optional(field_dump, mapping["spellcasting_class"])
    row["spellcasting_ability"] = _get_text_optional(field_dump, mapping["spellcasting_ability"])
    row["spell_save_dc"] = _get_smallint_optional(field_dump, mapping["spell_save_dc"])
    row["spell_attack_bonus"] = _get_smallint_optional(field_dump, mapping["spell_attack_bonus"])

    # The current template mapping may omit spells_known; if so, keep NULL.
    if "spells_known" in mapping:
        row["spells_known"] = _get_smallint_optional(field_dump, mapping["spells_known"])
    else:
        row["spells_known"] = None

    for lvl in range(1, 10):
        total_key = f"slots_{lvl}_total"
        exp_key = f"slots_{lvl}_expended"

        row[total_key] = _get_smallint_optional(field_dump, mapping[total_key])
        row[exp_key] = None

    spells_fields: Tuple[str, ...] = mapping["spells"]
    spells_by_level, missing_spell_names = _resolve_spells_from_sheet(
        conn, field_dump, spells_fields
    )

    for lvl in range(0, 10):
        row[f"spells_{lvl}"] = Jsonb(spells_by_level.get(lvl, []))

    spells_id = _insert_player_spells(conn, row)

    missing_spells: List[CharacterSheetIngestionError] = []
    if missing_spell_names:
        missing_spells.append(
            CharacterSheetIngestionError(
                type=CharacterSheetIngestionErrorType.SpellNotFound,
                message=(
                    "Some spells on the sheet were not found in the spells "
                    "table and were omitted from ingestion."
                ),
                metadata=missing_spell_names,
            )
        )

    return SpellExtractionResult(spells_id=spells_id, missing_spells=missing_spells)


def _resolve_spells_from_sheet(
    conn: Connection[Any],
    field_dump: FieldDump,
    spells_fields: Tuple[str, ...],
) -> Tuple[Dict[int, List[Dict[str, Any]]], List[str]]:
    """
    Resolve all spell-name fields into per-level spell lists.

    Parameters
    ----------
    conn : Connection[Any]
        Open psycopg connection used to query the `spells` table.
    field_dump : FieldDump
        Field dump produced by the PDF field-catalog step.
    spells_fields : tuple[str, ...]
        Tuple of PDF field names that contain spell names.

    Returns
    -------
    tuple[dict[int, list[dict[str, Any]]], list[str]]
        Per-level spell lists and a list of spell names that were not found in
        the `spells` table.

    Raises
    ------
    KeyError
        If the field dump does not contain a mapped PDF field name. This
        indicates an unsupported PDF schema for the configured template.

    Notes
    -----
    - Prepared flags are not available in the current mapping; spells are stored
      with prepared=false.
    - Empty/whitespace spell fields are ignored.
    """

    spells_by_level: Dict[int, List[Dict[str, Any]]] = {lvl: [] for lvl in range(0, 10)}
    missing: List[str] = []

    for field_name in spells_fields:
        spell_name = _get_text_optional(field_dump, field_name)
        if spell_name is None:
            continue

        spell_row = _lookup_spell(conn, spell_name)
        if spell_row is None:
            missing.append(spell_name)
            continue

        spell_id, level = spell_row

        spells_by_level[int(level)].append(
            {
                "spell_id": str(spell_id),
                "spell_name": spell_name,
                "prepared": False,
            }
        )

    for lvl in spells_by_level:
        spells_by_level[lvl] = _dedupe_spell_rows(spells_by_level[lvl])

    return spells_by_level, _dedupe_text(missing)


def _lookup_spell(conn: Connection[Any], spell_name: str) -> Tuple[UUID, int] | None:
    """
    Lookup a spell by name in the `spells` table.

    Parameters
    ----------
    conn : Connection[Any]
        Open psycopg connection used to query the `spells` table.
    spell_name : str
        Spell name as written on the character sheet.

    Returns
    -------
    tuple[UUID, int] | None
        (spell_id, level) if the spell exists, otherwise None.

    Raises
    ------
    Exception
        If the database query fails.

    Notes
    -----
    - Matching is case-insensitive exact match on `spell_name`.
    """

    query = (
        "SELECT spell_id, level "
        "FROM spells "
        "WHERE LOWER(spell_name) = LOWER(%s) "
        "LIMIT 1"
    )

    with conn.cursor() as cur:
        cur.execute(query, (spell_name,))
        row = cur.fetchone()

    if row is None:
        return None

    spell_id, level = row
    return UUID(str(spell_id)), int(level)


def _insert_player_spells(conn: Connection[Any], row: Dict[str, Any]) -> UUID:
    """
    Insert a `player_spells` row and return its primary key.

    Parameters
    ----------
    conn : Connection[Any]
        Open psycopg connection used to insert into `player_spells`.
    row : dict[str, Any]
        Column -> value mapping for the insert.

    Returns
    -------
    UUID
        The generated `player_spells.spells_id`.

    Raises
    ------
    Exception
        If the insert fails.

    Notes
    -----
    - This uses a single INSERT ... RETURNING spells_id statement.
    """

    cols = list(row.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_sql = ", ".join(cols)

    query = (
        f"INSERT INTO player_spells ({col_sql}) "
        f"VALUES ({placeholders}) "
        "RETURNING spells_id"
    )

    with conn.cursor() as cur:
        cur.execute(query, tuple(row[c] for c in cols))
        spells_id = cur.fetchone()[0]

    return UUID(str(spells_id))


def _require_field_value(field_dump: FieldDump, field_name: str) -> Any:
    """
    Return the raw PDF field value for a mapped field name.

    Parameters
    ----------
    field_dump : FieldDump
        Field dump produced by the PDF field-catalog step.
    field_name : str
        PDF form field name.

    Returns
    -------
    Any
        Raw field value from the dump.

    Raises
    ------
    KeyError
        If the field name is not present in the dump.

    Notes
    -----
    - The field map is trusted; missing fields indicate unsupported PDF schema.
    """

    return field_dump[field_name]


def _get_text_optional(field_dump: FieldDump, field_name: str) -> str | None:
    """
    Extract a trimmed text value from a mapped PDF field name.

    Parameters
    ----------
    field_dump : FieldDump
        Field dump produced by the PDF field-catalog step.
    field_name : str
        PDF form field name.

    Returns
    -------
    str | None
        Trimmed text value, or None if missing/empty.

    Raises
    ------
    KeyError
        If the field name is not present in the dump.

    Notes
    -----
    - Empty strings are treated as None.
    """

    raw = _require_field_value(field_dump, field_name)
    s = str(raw).strip()
    if s == "":
        return None
    return s


def _get_smallint_optional(field_dump: FieldDump, field_name: str) -> int | None:
    """
    Extract a SMALLINT-like integer value from a mapped PDF field name.

    Parameters
    ----------
    field_dump : FieldDump
        Field dump produced by the PDF field-catalog step.
    field_name : str
        PDF form field name.

    Returns
    -------
    int | None
        Parsed integer value, or None if missing/unparseable.

    Raises
    ------
    KeyError
        If the field name is not present in the dump.

    Notes
    -----
    - Empty strings are treated as None.
    - Unparseable values are treated as None.
    """

    s = _get_text_optional(field_dump, field_name)
    if s is None:
        return None

    try:
        return int(s.replace(",", ""))
    except ValueError:
        return None


def _dedupe_spell_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate spell JSON rows by `spell_id`, preserving first occurrence.

    Parameters
    ----------
    rows : list[dict[str, Any]]
        Spell rows to deduplicate.

    Returns
    -------
    list[dict[str, Any]]
        Deduplicated rows.

    Raises
    ------
    KeyError
        If a row is missing the `spell_id` key.

    Notes
    -----
    - The first occurrence of each spell_id is preserved.
    """

    seen: set[str] = set()
    out: List[Dict[str, Any]] = []

    for r in rows:
        sid = str(r["spell_id"])
        if sid in seen:
            continue
        seen.add(sid)
        out.append(r)

    return out


def _dedupe_text(xs: List[str]) -> List[str]:
    """
    Deduplicate strings case-insensitively while preserving original order.

    Parameters
    ----------
    xs : list[str]
        Strings to deduplicate.

    Returns
    -------
    list[str]
        Deduplicated strings.

    Raises
    ------
    Exception
        This function does not intentionally raise, but will propagate unexpected
        errors from Python runtime.

    Notes
    -----
    - Deduplication uses `x.strip().lower()` as the key.
    """

    seen: set[str] = set()
    out: List[str] = []

    for x in xs:
        key = x.strip().lower()
        if key == "":
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(x.strip())

    return out
