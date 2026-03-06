// =============================================================================
// character_sheet_ingestion.baml
//
// Purpose
// -------
// Defines typed LLM functions that act as the agent-facing wrapper around a
// deterministic character-sheet ingestion pipeline.
//
// Key behaviors
// -------------
// - Explains how the host runtime should accept a user-provided PDF and turn it
//   into a local file path inside the bot container.
// - Translates deterministic ingestion outputs into a user-facing summary.
// - Never parses PDFs itself and never performs any database writes.
//
// Conventions
// -----------
// - Host code is responsible for receiving the PDF (Discord attachment), saving
//   it to disk, then calling the deterministic ingester with that local path.
// - UnsupportedPDFSchema is the only critical error that must set ingested=false.
// - ItemNotFound and SpellNotFound are non-critical and should be reported as
//   warnings while ingested remains true.
// - Outputs must be strictly machine-parseable.
//
// Downstream usage
// ----------------
// Discord bot flow:
// 1) User uploads PDF as an attachment.
// 2) Bot downloads it and saves it to a container-local path (for example,
//    /tmp/anabasis_uploads/<uuid>.pdf).
// 3) Bot runs deterministic ingestion (your Python code) using the saved path.
// 4) Bot calls SummarizeCharacterSheetIngestion(...) to generate the message
//    shown to the user.
// =============================================================================

class CharacterSheetIngestionResult {
    /// CharacterSheetIngestionResult
    ///
    /// Purpose
    /// -------
    /// Represents the deterministic host runtime outcome of attempting to ingest a
    /// single character-sheet PDF.
    ///
    /// Fields
    /// ------
    /// - ingested: true if and only if the sheet was ingested successfully enough
    ///   to persist core character data.
    /// - errors: optional list of structured errors and warnings.
    ///
    /// Invariants
    /// ----------
    /// - If any error has type UnsupportedPDFSchema, then ingested must be false.
    /// - ItemNotFound and SpellNotFound do not imply ingested=false.
    ///
    /// Notes
    /// -----
    /// This object is produced by deterministic host code, not by the LLM.
    ingested bool @description("True iff the host deterministically ingested core character data; false only for critical failures like unsupported schema.")
    errors CharacterSheetIngestionError[]? @description("Optional list of structured errors/warnings emitted by deterministic host ingestion.")
}


class CharacterSheetIngestionError {
    /// CharacterSheetIngestionError
    ///
    /// Purpose
    /// -------
    /// Encodes a single ingestion error or warning emitted by deterministic host
    /// code.
    ///
    /// Fields
    /// ------
    /// - type: categorized error type.
    /// - message: human-readable detail produced by host code.
    /// - metadata: optional list payload used for structured followups (for example,
    ///   missing item names).
    ///
    /// Notes
    /// -----
    /// The LLM must not invent new errors; it may only summarize these.
    type CharacterSheetIngestionErrorType @description("Machine-readable category for this issue (critical vs warning).")
    message string @description("Human-readable detail produced by host code; used for summarization.")
    metadata string[]? @description("Optional list payload (e.g., missing item/spell names) for structured reporting.")
}


enum CharacterSheetIngestionErrorType {
    /// CharacterSheetIngestionErrorType
    ///
    /// Purpose
    /// -------
    /// Categorizes deterministic ingestion issues into critical failures and
    /// non-critical warnings.
    ///
    /// Variants
    /// --------
    /// - UnsupportedPDFSchema: critical; the uploaded PDF template cannot be
    ///   parsed.
    /// - ItemNotFound: warning; some parsed equipment items were not found in DB.
    /// - SpellNotFound: warning; some parsed spells were not found in DB.
    ///
    /// Notes
    /// -----
    /// Host code defines which conditions produce each variant.
    UnsupportedPDFSchema
    ItemNotFound
    SpellNotFound
}


class CharacterSheetIngestionSummary {
    /// CharacterSheetIngestionSummary
    ///
    /// Purpose
    /// -------
    /// User-facing summary derived from a deterministic ingestion result.
    ///
    /// Fields
    /// ------
    /// - user_message: short Discord-ready message summarizing success/warnings.
    /// - ingested: mirrors the deterministic result.ingested.
    /// - has_warnings: true iff there exists any non-critical warning.
    /// - critical_error: true iff any error is UnsupportedPDFSchema.
    /// - missing_items: optional aggregated list of missing item names.
    /// - missing_spells: optional aggregated list of missing spell names.
    ///
    /// Invariants
    /// ----------
    /// - critical_error is true iff any error has type UnsupportedPDFSchema.
    /// - has_warnings is true iff any error has a non-critical type.
    ///
    /// Notes
    /// -----
    /// This is the object the bot should use to format responses and UI.
    user_message string @description("Discord-ready summary message derived from the deterministic result.")
    ingested bool @description("Mirrors the deterministic result.ingested.")
    has_warnings bool @description("True iff any non-critical warnings exist (ItemNotFound/SpellNotFound).")
    critical_error bool @description("True iff any error is UnsupportedPDFSchema; implies ingested=false.")
    missing_items string[]? @description("Aggregated list of equipment/item names missing from the database, if provided by metadata.")
    missing_spells string[]? @description("Aggregated list of spell names missing from the database, if provided by metadata.")
}


function SummarizeCharacterSheetIngestion(
    result : CharacterSheetIngestionResult
) -> CharacterSheetIngestionSummary {
    /// function SummarizeCharacterSheetIngestion(result : CharacterSheetIngestionResult)
    ///     -> CharacterSheetIngestionSummary
    ///
    /// Summary
    /// -------
    /// Converts a deterministic CharacterSheetIngestionResult into a structured,
    /// user-facing CharacterSheetIngestionSummary.
    ///
    /// Inputs
    /// ------
    /// - result: deterministic ingestion output from host code.
    ///
    /// Output contract
    /// ---------------
    /// - Must output ONLY a CharacterSheetIngestionSummary (no prose).
    /// - Must follow schema exactly (use {{ ctx.output_format }}).
    /// - Must not invent missing items/spells beyond what appears in metadata.
    ///
    /// Failure / ambiguity policy
    /// --------------------------
    /// - If metadata is absent for a warning, keep the warning but omit list
    ///   entries.
    /// - If errors is null/empty, treat as no warnings.
    client CustomOllama
    prompt #"
    You are a deterministic summarizer for a DnD character-sheet ingestion system.

    You will be given a CharacterSheetIngestionResult produced by host code that ran
    an entirely deterministic ingestion pipeline.

    Your job:
    - Produce a CharacterSheetIngestionSummary that is safe to show to a Discord user.
    - Keep the summary factual and tied to the structured result.
    - UnsupportedPDFSchema is critical.
    - ItemNotFound and SpellNotFound are non-critical warnings.

    Rules:
    - critical_error is true if and only if any error has type UnsupportedPDFSchema.
    - ingested should match result.ingested.
    - has_warnings is true if and only if there exists any non-critical error.
    - missing_items must aggregate all item names appearing in metadata for errors of
      type ItemNotFound.
    - missing_spells must aggregate all spell names appearing in metadata for errors
      of type SpellNotFound.
    - If metadata is missing for an ItemNotFound or SpellNotFound error, omit that
      list entry but still report a warning in user_message.

    User message requirements:
    - If critical_error is true, start with: "I could not ingest that character sheet."
    - Otherwise start with: "Character sheet ingested."
    - If there are warnings, include a second sentence indicating that some items or
      spells were not found in the database and that the user can add them or rename
      them.
    - If there are no warnings, keep user_message to one sentence.
    - Do not mention implementation details like SQL, config files, or field maps.

    Input:
    {{ result }}

    Output:
    Return output in this exact schema:
    {{ ctx.output_format }}
    "#
}
