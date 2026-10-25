"""Value-free local decision records; a write failure must prevent forwarding."""
import json
import os
from pathlib import Path
from typing import Any


class AuditLog:
    """Append private JSONL without following a final-component symlink."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._append(b"")

    def _append(self, data: bytes) -> None:
        flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "ab", closefd=False) as stream:
                stream.write(data)
                stream.flush()
        finally:
            os.close(fd)

    def write(self, record: dict[str, Any]) -> None:
        """Write a decision containing only policy-controlled identifiers and codes."""
        self._append((json.dumps(record, sort_keys=True) + "\n").encode())
