SUPPORTED_IMAGE_CONTENT_TYPES: frozenset = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
    }
)

SUPPORTED_DOCUMENT_CONTENT_TYPES: frozenset = frozenset(
    {
        "application/pdf",
    }
)

SUPPORTED_IMAGE_SUFFIXES: frozenset = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
    }
)

SUPPORTED_DOCUMENT_SUFFIXES: frozenset = frozenset(
    {
        ".pdf",
    }
)

MAX_ATTACHMENT_SIZE: int = 15 * 1024 * 1024
