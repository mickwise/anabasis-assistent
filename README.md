# Anabasis Assistant

Anabasis Assistant is a Python-based agent orchestration system for a Discord-first DnD workflow.
It combines:

- typed LLM planning contracts via BAML
- deterministic tool execution (for example dice rolling)
- a normalized Postgres schema for world-state and lore memory
- REPL-style runtime components for structured program execution

The repository is actively evolving and some paths are intentionally stubbed while core architecture is being stabilized.

## What Exists Today

- Discord bot entrypoint with message and slash-command handling in `src/discord_adapter`
- Slash commands: `ping`, `ingest`, and `roll`
- Mention-based free-text route that currently detects roll requests and executes the rolling tool
- Deterministic rolling engine in `src/tools/rolling` with BAML parsing plus invariant checks
- BAML source contracts in `baml_src` and generated client code in `src/baml_client`
- Character-sheet field extraction and spell ingestion helpers in `src/etl/character_sheet`
- Postgres adapter in `src/db/psycopg_adapter.py`
- SQL migration set in `sql/` covering game entities and world-state history tables
- REPL AST, validation, and interpretation modules under `src/rlm/repl`

## Current Limitations

- The Discord planner is still a stub in `src/discord_adapter/discord_main.py` and is not yet wired to the full `PlanDiscordMessage` BAML planner loop.
- The direct execution stub only executes `roll` today.
- `/ingest` is registered but currently flows through generic stub behavior.
- End-to-end character-sheet orchestrator (`ingest_character_sheet.py`) is still empty.

## Architecture Overview

- `src/discord_adapter`: boundary, routing, auth, context normalization, response planning, startup
- `src/tools/rolling`: natural-language roll parsing via BAML and deterministic dice execution
- `baml_src`: planner and tool contracts (`planner_entrypoint.baml`, `tools/*.baml`)
- `src/baml_client`: generated typed clients from BAML contracts
- `src/etl`: deterministic data extraction and transformation modules
- `src/db`: small psycopg3 connection and transaction adapter
- `src/rlm/repl`: AST node model, validators, expression interpreter, step interpreter, runtime state
- `sql`: migration files for spells, characters, organizations, events, artifacts, agreements, and relation tables
- `tests`: unit tests for tooling, ETL helpers, and DB adapter behavior

## Requirements

- Python `3.14+`
- A Discord bot token for runtime bot startup
- For rolling through BAML as currently configured, a local Ollama-compatible endpoint and model:
  - default client points to `http://localhost:11434/v1`
  - default model name is `qwen3.5`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Environment Variables

Minimum for bot startup:

- `DISCORD_BOT_TOKEN`

Common optional Discord settings:

- `DEV_GUILD_ID`
- `DISCORD_ENABLE_MESSAGE_MENTIONS`
- `DISCORD_ENABLE_SLASH_COMMANDS`
- `DISCORD_ENABLE_DM_WORKFLOWS`
- `DISCORD_ENABLE_LLM_ROUTER`
- `DISCORD_AUTHORIZED_DM_USER_IDS`
- `DISCORD_ADMIN_USER_IDS`
- `DISCORD_LOG_LEVEL`

Database settings (for DB/ETL paths):

- `DATABASE_URL`
- or `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`, `PGSSLMODE`

LLM provider settings depend on the selected BAML clients in `baml_src/clients.baml`.

## Running the Bot

```bash
source .venv/bin/activate
python -m discord_adapter.discord_main
```

Current interaction behavior:

- `/ping` responds through the slash command handler
- `/roll` executes the deterministic slash rolling path
- mention-based messages route through planner stub logic
- mention text containing `roll` attempts free-form roll execution

## Running Tests

```bash
source .venv/bin/activate
python -m pytest -q
```

Current local status in this repository state: `54 passed`.

## SQL Schema

Migration files are in `sql/` and currently include:

- game data tables (`spells`, `items`, player and character-sheet tables)
- world-state timeline tables (`eras`, `events`, `event_edges`)
- entity tables (`locations`, `organizations`, `characters`, `artifacts`, `agreements`, `titles`)
- relation and participation tables (membership, control, aliases, event participants, artifact holders, agreement participants)

## Working with BAML

BAML source files live in `baml_src`.
Generated clients in `src/baml_client` should be regenerated after BAML contract changes.
The project comments reference `baml-cli generate` as the generation step.

## Repository Status

This project is a work in progress focused on robust foundations:

- typed planner and tool contracts
- deterministic execution and validation
- query-friendly relational memory schema
- test coverage around core behavior
