/// Purpose
/// -------
/// Defines typed LLM parsing for D&D 5e spell blocks provided via Discord
/// attachments (image or PDF) into a single insert-ready record for the Postgres
/// `spells` table.
///
/// Key behaviors
/// -------------
/// - Accepts a document reference (URL or local path) produced by the Discord
///   ingestion pipeline.
/// - Extracts spell fields (name, level, cast time, range, duration, components,
///   damage, save) into a single `SpellInsertRow`.
/// - Enforces output compatibility with DB constraints (enums, required fields,
///   and component invariants).
/// - Captures “At Higher Levels” text inside `details` (not as extra rows).
///
/// Conventions
/// -----------
/// - Output must be strictly machine-parseable and conform to schema.
/// - Do not normalize cast_time/range/duration; copy the human-readable strings.
/// - Do not invent mechanical fields not present in the source; use nulls when
///   the document does not specify a nullable column.
/// - `details` must be non-empty and include a short summary plus the visible
///   rules text (best effort), including an explicit “At Higher Levels:” section
///   when present.
///
/// Downstream usage
/// ----------------
/// Discord bot downloads attachment -> calls `ParseSpellSource(source_ref, hint)`
/// -> host validates and inserts returned `SpellInsertRow` into Postgres.
///
/// Notes
/// -----
/// - This module performs structured parsing only and does not execute gameplay
///   effects.


enum DamageType {
  /// Purpose
  /// -------
  /// Enumerated damage types allowed by the `spells.damage_type` CHECK constraint.
  ///
  /// Notes
  /// -----
  /// - Values are uppercase to match the host-side enum mapping expectations.
  ACID
  BLUDGEONING
  COLD
  FIRE
  FORCE
  LIGHTNING
  NECROTIC
  PIERCING
  POISON
  PSYCHIC
  RADIANT
  SLASHING
  THUNDER
}


enum SaveAbility {
  /// Purpose
  /// -------
  /// Enumerated save abilities allowed by the `spells.save_ability` CHECK constraint.
  ///
  /// Notes
  /// -----
  /// - Values are uppercase and represent the six standard ability scores.
  STR
  DEX
  CON
  INT
  WIS
  CHA
}


class SpellInsertRow {
  /// Purpose
  /// -------
  /// Represents one insertable record matching the Postgres `spells` table columns.
  /// The host should insert exactly one row per parsed spell.
  ///
  /// Fields
  /// ------
  /// - spell_name: spell name as printed in the source (non-empty)
  /// - level: integer in [0, 9] (use 0 for cantrips)
  /// - cast_time: human-readable casting time (non-empty)
  /// - range: human-readable range (non-empty)
  /// - duration: human-readable duration (non-empty)
  /// - damage: dice expression (e.g., "3d8", "1d4+1") or null if not specified
  /// - damage_type: one of DamageType or null if not specified
  /// - is_elemental: true only for elemental damage types (see invariants)
  /// - save_ability: one of SaveAbility or null if no saving throw
  /// - component_verbal/component_somatic/component_material: V/S/M flags
  /// - material_components: raw material text if present; else null
  /// - is_ritual: true if the spell is marked as ritual
  /// - details: non-empty summary + rules text (best effort)
  ///
  /// Invariants
  /// ----------
  /// - `level` must be within [0, 9].
  /// - At least one of component_verbal/component_somatic/component_material is true.
  /// - If component_material is false then material_components must be null.
  /// - If is_elemental is true, damage_type must be one of:
  ///   ACID, COLD, FIRE, LIGHTNING, POISON, THUNDER.
  /// - If damage_type is null, is_elemental must be false.
  ///
  /// Notes
  /// -----
  /// - Nullable fields mirror nullable DB columns and must not be fabricated.
  spell_name string @description("Spell title as printed at the top of the block (e.g., 'Arms of Hadar'). Copy exact capitalization/punctuation.")
  level int @description("Spell level parsed from the header line like '1st-level conjuration'. Use 0 if the header says 'cantrip'.")
  cast_time string @description("Value on the 'Casting Time:' line (e.g., '1 action', '1 bonus action', '1 reaction, which you take when ...'). Copy as written.")
  range string @description("Value on the 'Range:' line (e.g., 'Self (10-foot radius)', '60 feet', 'Touch'). Copy as written.")
  duration string @description("Value on the 'Duration:' line (e.g., 'Instantaneous', 'Concentration, up to 1 minute'). Copy as written.")

  damage string? @description("Dice expression for primary damage if explicitly stated (e.g., '2d6', '1d4+1'). Extract from rules text like 'takes 2d6 necrotic damage'. Null if no damage dice are specified.")
  damage_type DamageType? @description("Damage type associated with `damage` when present (e.g., 'necrotic' -> NECROTIC). Null if no damage type is specified or if `damage` is null.")
  is_elemental bool @description("True only when `damage_type` is one of ACID/COLD/FIRE/LIGHTNING/POISON/THUNDER. Otherwise false (including when `damage_type` is null).")

  save_ability SaveAbility? @description("Set if the spell text says the target must make an ability saving throw (e.g., 'Strength saving throw' -> STR). Null if there is no saving throw.")

  component_verbal bool @description("True if the 'Components:' line includes 'V'. Example: 'Components: V, S' -> true.")
  component_somatic bool @description("True if the 'Components:' line includes 'S'. Example: 'Components: V, S' -> true.")
  component_material bool @description("True if the 'Components:' line includes 'M'. If the block shows materials in parentheses, set this true.")
  material_components string? @description("If component_material is true and the block lists materials (usually in parentheses after 'M'), copy that materials text verbatim (without inventing). Null if no materials text is visible.")

  is_ritual bool @description("True if the header or component line marks the spell as a ritual (often '(ritual)' next to the level/school). Otherwise false.")

  details string @description("Non-empty: include (1) a 2–5 sentence mechanical summary and (2) the visible rules text best-effort. Must include an explicit 'At Higher Levels:' paragraph if present.")
}


function ParseSpellSource(source_ref: string, hint: string?) -> SpellInsertRow {
    ///
    /// Summary
    /// -------
    /// Parses a single spell rules block from a Discord attachment into an
    /// insert-ready `SpellInsertRow` for Postgres.
    ///
    /// Inputs
    /// ------
    /// - source_ref: URL or local filesystem path to an image or PDF attachment.
    /// - hint: optional operator hint to resolve ambiguity; must not override
    ///   visible text.
    ///
    /// Output contract
    /// ---------------
    /// - Must output ONLY a `SpellInsertRow` (no prose, no extra keys).
    /// - Must follow the schema exactly (use {{ ctx.output_format }}).
    /// - Must obey all constraints/invariants documented on `SpellInsertRow`.
    ///
    /// Failure / ambiguity policy
    /// --------------------------
    /// - Choose the simplest valid interpretation consistent with visible text.
    /// - Never invent values for nullable fields; prefer null.
    /// - If the source does not contain required fields, still produce
    ///   best-effort required strings from the visible header lines; do not
    ///   fabricate mechanics.
    ///
    /// Notes
    /// -----
    /// - “At Higher Levels” (or cantrip scaling) must be included in `details`.
    /// - The host application is responsible for final validation and DB
    ///   insertion.

    client CustomOllama
    prompt #"
    You are parsing a D&D 5e spell rules block from a Discord attachment (image or
    PDF). Your task is to extract the spell into a SpellInsertRow that can be
    inserted into a Postgres table.

    Hard requirements (DB compatibility)
    ------------------------------------
    1) Output ONLY a SpellInsertRow, no extra keys, no narrative.
    2) Required non-empty strings:
       - spell_name, cast_time, range, duration, details
    3) level must be an integer in [0, 9].
    4) save_ability must be one of STR/DEX/CON/INT/WIS/CHA or null.
    5) damage_type must be one of:
       ACID, BLUDGEONING, COLD, FIRE, FORCE, LIGHTNING, NECROTIC, PIERCING,
       POISON, PSYCHIC, RADIANT, SLASHING, THUNDER
       or null.
    6) Component flags: at least one of component_verbal / component_somatic /
       component_material must be true.
    7) If component_material is true and the image provides materials text, put it
       in material_components. If no materials text is shown, material_components
       may be null.
    8) is_elemental:
       - true only if damage_type is one of ACID/COLD/FIRE/LIGHTNING/POISON/THUNDER
       - otherwise false (including when damage_type is null).

    What to extract (best-effort)
    -----------------------------
    - spell_name
    - level:
    - if the screenshot says "cantrip", use 0
    - otherwise parse spell level 1..9
    - cast_time, range, duration: copy as written (human-readable strings)
    - components:
    - parse V/S/M flags from the components line
    - parse ritual if the spell is marked as ritual
    - damage and damage_type:
    - if the rules explicitly specify damage dice + type, set them
    - if damage exists but dice expression is embedded in text, extract the dice
      expression as damage (e.g., "3d8", "1d4+1", "2d6")
    - if no damage, set both damage and damage_type to null
    - save_ability:
    - if a saving throw is required, set it (STR/DEX/CON/INT/WIS/CHA)
    - else null

    details policy (must be non-empty)
    ----------------------------------
    details must contain:
    1) Summary:
    - 2 to 5 sentences summarizing what the spell does mechanically.
    - Include important qualifiers (targets, conditions, concentration, duration).
    2) Visible rules text:
      - Paste the spell text as visible in the image/PDF (best effort).
    3) If present, include an explicit "At Higher Levels:" paragraph:
       - If the screenshot has an "At Higher Levels" clause (or equivalent text),
         include it verbatim if possible, otherwise paraphrase faithfully.
       - For cantrips with scaling text, include the scaling info in the same way.

    Input
    -----
    source_ref: {{ source_ref }}
    hint: {{ hint }}

    Return output in this exact schema:
    {{ ctx.output_format }}
    "#
}
