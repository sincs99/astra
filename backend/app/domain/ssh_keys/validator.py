"""SSH-Public-Key-Validierung und Fingerprint-Berechnung (M28).

Unterstuetzte Key-Typen:
  - ssh-rsa
  - ssh-ed25519
  - ecdsa-sha2-nistp256
  - ecdsa-sha2-nistp384
  - ecdsa-sha2-nistp521

Fingerprint-Format: SHA256, base64-kodiert (ohne Padding), z.B.
  SHA256:abc123...
Das entspricht dem Format von `ssh-keygen -l -E sha256`.
"""

import base64
import hashlib
import struct

SUPPORTED_KEY_TYPES = {
    "ssh-rsa",
    "ssh-ed25519",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
}


class SshKeyValidationError(Exception):
    pass


def validate_and_parse(public_key: str) -> tuple[str, str]:
    """Validiert einen SSH-Public-Key und gibt (key_type, fingerprint) zurueck.

    Args:
        public_key: Der vollstaendige Public-Key-String (z.B. "ssh-ed25519 AAAA... optionaler Kommentar")

    Returns:
        (key_type, fingerprint) – z.B. ("ssh-ed25519", "SHA256:abc123...")

    Raises:
        SshKeyValidationError: Wenn der Key ungueltig ist.
    """
    if not public_key or not public_key.strip():
        raise SshKeyValidationError("Public key darf nicht leer sein")

    parts = public_key.strip().split()
    if len(parts) < 2:
        raise SshKeyValidationError("Ungueltiges Key-Format: Typ und Key-Body erwartet")

    key_type = parts[0]
    key_body_b64 = parts[1]

    if key_type not in SUPPORTED_KEY_TYPES:
        raise SshKeyValidationError(
            f"Nicht unterstuetzter Key-Typ '{key_type}'. "
            f"Unterstuetzt: {', '.join(sorted(SUPPORTED_KEY_TYPES))}"
        )

    # Base64-Body decodieren und strukturell pruefen
    try:
        key_bytes = base64.b64decode(key_body_b64, validate=True)
    except Exception:
        raise SshKeyValidationError("Key-Body ist kein gueltiges Base64")

    if len(key_bytes) < 4:
        raise SshKeyValidationError("Key-Body ist zu kurz")

    # Ersten String-Token aus dem Binary-Format lesen und mit dem Typ-Header vergleichen
    try:
        _verify_key_type_in_body(key_type, key_bytes)
    except SshKeyValidationError:
        raise
    except Exception:
        raise SshKeyValidationError("Key-Body hat ungueltiges Binaerformat")

    fingerprint = _compute_fingerprint(key_bytes)
    return key_type, fingerprint


def compute_fingerprint(public_key: str) -> str:
    """Berechnet den SHA256-Fingerprint fuer einen validierten Public Key.

    Convenience-Funktion – ruft validate_and_parse intern auf.
    """
    _, fingerprint = validate_and_parse(public_key)
    return fingerprint


def _read_length_prefixed_string(data: bytes, offset: int) -> tuple[bytes, int]:
    """Liest einen laengenpraefixierten String aus SSH-Binaerdaten."""
    if offset + 4 > len(data):
        raise SshKeyValidationError("Unerwartetes Ende der Key-Daten")
    length = struct.unpack(">I", data[offset : offset + 4])[0]
    offset += 4
    if offset + length > len(data):
        raise SshKeyValidationError("Unerwartetes Ende der Key-Daten")
    value = data[offset : offset + length]
    return value, offset + length


def _verify_key_type_in_body(expected_type: str, key_bytes: bytes) -> None:
    """Prueft, ob der erste Token im SSH-Binaerformat dem erwarteten Key-Typ entspricht."""
    token, _ = _read_length_prefixed_string(key_bytes, 0)
    actual_type = token.decode("ascii", errors="replace")
    if actual_type != expected_type:
        raise SshKeyValidationError(
            f"Key-Header '{expected_type}' stimmt nicht mit Key-Typ im Body '{actual_type}' ueberein"
        )


def _compute_fingerprint(key_bytes: bytes) -> str:
    """Berechnet SHA256-Fingerprint im OpenSSH-Format: 'SHA256:<base64>'."""
    digest = hashlib.sha256(key_bytes).digest()
    b64 = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{b64}"
