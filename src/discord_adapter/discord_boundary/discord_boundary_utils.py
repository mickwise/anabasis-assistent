"""
Purpose
-------
Provide small, reusable utilities and data structures for the Discord
orchestration layer.

Key behaviors
-------------
- Load Discord runtime configuration from environment variables.
- Normalize Discord attachments into a transport-friendly internal model.
- Validate attachment type and size before downstream ingestion.
- Build the exact Discord intents required for mention-based messages and slash
  commands.

Conventions
-----------
- This module owns only lightweight orchestration helpers.
- Environment variables use the exact names supplied by the project:
  DISCORD_APPLICATION_ID, DISCORD_PUBLIC_KEY, DISCORD_BOT_TOKEN.
- For the current Gateway-based discord.py architecture, only the bot token is
  required at runtime. The application ID and public key are still loaded and
  preserved for future use.
- Supported uploads are PDFs and common web image formats.

Downstream usage
----------------
Import this module from the Discord main orchestrator. Use
`load_discord_config()` once at startup, `build_intents()` when constructing the
bot, and `coerce_and_validate_attachment()` before dispatching work to the
downstream ingestion pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

import discord
from discord_adapter.discord_boundary.config import (
    SUPPORTED_DOCUMENT_CONTENT_TYPES,
    SUPPORTED_IMAGE_CONTENT_TYPES,
    MAX_ATTACHMENT_SIZE,
    SUPPORTED_IMAGE_SUFFIXES,
    SUPPORTED_DOCUMENT_SUFFIXES
)


@dataclass(frozen=True)
class DiscordConfig:
    """
    Purpose
    -------
    Hold Discord credentials and runtime settings required by the orchestration
    layer.

    Key behaviors
    -------------
    - Stores the bot token required to connect through the Discord Gateway.
    - Preserves application metadata for future interaction-endpoint or install
      workflows.
    - Carries the optional development guild ID used for fast command syncing.

    Parameters
    ----------
    application_id : str
        Discord application ID taken from the environment.
    public_key : str
        Discord public key taken from the environment.
    bot_token : str
        Discord bot token used to authenticate the Gateway connection.
    dev_guild_id : int | None
        Optional guild ID used for development-only slash-command sync.
    max_attachment_size_bytes : int
        Maximum accepted upload size in bytes.

    Attributes
    ----------
    application_id : str
        Discord application ID.
    public_key : str
        Discord public key.
    bot_token : str
        Discord bot token.
    dev_guild_id : int | None
        Optional development guild ID.
    max_attachment_size_bytes : int
        Maximum accepted upload size in bytes.

    Notes
    -----
    - The public key is not used by the current Gateway-only bot file.
    - The bot token is the only credential strictly required to run this
      orchestrator today.
    """

    application_id: str
    public_key: str
    bot_token: str
    dev_guild_id: int | None = None
    max_attachment_size_bytes: int = MAX_ATTACHMENT_SIZE


@dataclass(frozen=True)
class AttachmentRef:
    """
    Purpose
    -------
    Represent a validated Discord attachment in a normalized, downstream-safe
    format.

    Key behaviors
    -------------
    - Stores the metadata needed by later downloader or parser code.
    - Classifies uploads as `pdf` or `image`.
    - Avoids passing raw discord.py models deeper into the application.

    Parameters
    ----------
    filename : str
        Original uploaded filename.
    url : str
        Discord CDN URL for the attachment.
    content_type : str | None
        MIME type reported by Discord, if present.
    size_bytes : int
        Attachment size in bytes.
    source_kind : str
        Normalized source type, typically `pdf` or `image`.

    Attributes
    ----------
    filename : str
        Original uploaded filename.
    url : str
        Discord CDN URL for the attachment.
    content_type : str | None
        MIME type reported by Discord.
    size_bytes : int
        Attachment size in bytes.
    source_kind : str
        Normalized source type.

    Notes
    -----
    - This class does not download the file.
    - Downstream code can assume the attachment has already passed validation if
      it receives this object from `coerce_and_validate_attachment()`.
    """

    filename: str
    url: str
    content_type: str | None
    size_bytes: int
    source_kind: str


def load_discord_config() -> DiscordConfig:
    """
    Load Discord configuration from environment variables.

    Parameters
    ----------
    None
        This function accepts no parameters.

    Returns
    -------
    DiscordConfig
        Parsed Discord configuration object.

    Raises
    ------
    RuntimeError
        Raised if DISCORD_BOT_TOKEN is missing from the environment.

    Notes
    -----
    - DISCORD_APPLICATION_ID and DISCORD_PUBLIC_KEY are optional for this
      Gateway-only orchestrator, but they are still loaded if present.
    - DEV_GUILD_ID is optional and enables fast slash-command iteration.
    """
    application_id = os.getenv("DISCORD_APPLICATION_ID", "")
    public_key = os.getenv("DISCORD_PUBLIC_KEY", "")
    bot_token = os.getenv("DISCORD_BOT_TOKEN", "")
    dev_guild_raw = os.getenv("DEV_GUILD_ID")

    if not bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required.")

    dev_guild_id = int(dev_guild_raw) if dev_guild_raw else None

    return DiscordConfig(
        application_id=application_id,
        public_key=public_key,
        bot_token=bot_token,
        dev_guild_id=dev_guild_id,
    )


def build_intents() -> discord.Intents:
    """
    Build the Discord intents required for the hybrid bot workflow.

    Parameters
    ----------
    None
        This function accepts no parameters.

    Returns
    -------
    discord.Intents
        Intents configured for guilds, messages, and message content.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - `message_content` is required for mention-based natural-language message
      handling.
    - Presence and member intents are intentionally not enabled.
    """
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    return intents


def infer_source_kind(filename: str, content_type: str | None) -> str:
    """
    Infer the normalized source kind for an uploaded attachment.

    Parameters
    ----------
    filename : str
        Original attachment filename.
    content_type : str | None
        MIME type reported by Discord, if present.

    Returns
    -------
    str
        `pdf`, `image`, or `unknown`.

    Raises
    ------
    RuntimeError
        This function does not raise RuntimeError directly.

    Notes
    -----
    - MIME type is preferred over suffix when available.
    - Filename suffix is used as a fallback because MIME metadata can be absent.
    """
    if content_type in SUPPORTED_DOCUMENT_CONTENT_TYPES:
        return "pdf"

    if content_type in SUPPORTED_IMAGE_CONTENT_TYPES:
        return "image"

    suffix: str = Path(filename).suffix.lower()
    if suffix in SUPPORTED_DOCUMENT_SUFFIXES:
        return "pdf"

    if suffix in SUPPORTED_IMAGE_SUFFIXES:
        return "image"

    return "unknown"


def coerce_and_validate_attachment(
    attachment: discord.Attachment,
    max_attachment_size_bytes: int,
) -> AttachmentRef:
    """
    Convert a discord.py attachment into a validated AttachmentRef.

    Parameters
    ----------
    attachment : discord.Attachment
        Attachment object received from discord.py.
    max_attachment_size_bytes : int
        Maximum accepted file size in bytes.

    Returns
    -------
    AttachmentRef
        Validated, normalized attachment reference.

    Raises
    ------
    ValueError
        Raised if the attachment type is unsupported or the file is too large.

    Notes
    -----
    - Only PDF and common image formats are accepted.
    - This function validates metadata only. It does not download file bytes.
    """
    source_kind = infer_source_kind(
        filename=attachment.filename,
        content_type=attachment.content_type,
    )

    if source_kind not in {"pdf", "image"}:
        raise ValueError(
            "Unsupported file type. Only PDF, PNG, JPG, JPEG, and WEBP are "
            "accepted."
        )

    if attachment.size > max_attachment_size_bytes:
        raise ValueError("Attachment exceeds the configured size limit.")

    return AttachmentRef(
        filename=attachment.filename,
        url=attachment.url,
        content_type=attachment.content_type,
        size_bytes=attachment.size,
        source_kind=source_kind,
    )
