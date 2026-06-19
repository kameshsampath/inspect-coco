"""PEM normalization and base64 transport utilities for Docker credential deployment."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path


def normalize_pem(raw: str) -> str:
    """Fix PEM files where newlines were stripped (common in CI secret mounts).

    Handles cases where Jenkins, GitHub Actions, or other CI systems
    store PEM content as a single line by stripping internal newlines.
    """
    raw = raw.strip()

    # Already properly formatted
    if "\n" in raw and raw.startswith("-----BEGIN"):
        return raw

    # Single-line PEM: reconstruct proper format
    if "-----BEGIN" in raw and "\n" not in raw:
        # Extract header and footer
        match = re.match(r"(-----BEGIN [A-Z ]+-----)(.+?)(-----END [A-Z ]+-----)", raw)
        if match:
            header, body, footer = match.groups()
            # Insert newlines every 64 chars in the base64 body
            body_lines = [body[i : i + 64] for i in range(0, len(body), 64)]
            return f"{header}\n" + "\n".join(body_lines) + f"\n{footer}\n"

    return raw


def pem_to_base64_payload(pem_path: str | Path) -> str:
    """Read, normalize, and base64-encode a PEM file for safe shell transport.

    The base64 encoding avoids issues with special characters in echo/heredoc
    and prevents podman cp corruption bugs.
    """
    content = Path(pem_path).read_text()
    normalized = normalize_pem(content)
    return base64.b64encode(normalized.encode()).decode()


def remote_key_path(connection_name: str, pem_content: str) -> str:
    """Generate deterministic remote path for a deployed private key.

    Path format: /root/.snowflake/private_key_{name}_{hash[:8]}.p8
    The hash prevents collisions when multiple connections are deployed.
    """
    hash_prefix = hashlib.sha256(pem_content.encode()).hexdigest()[:8]
    return f"/root/.snowflake/private_key_{connection_name}_{hash_prefix}.p8"
