"""Anonymous identity (spec §5).

No login, no email, no password - but progress has to survive a cache clear and
a device change, otherwise every streak dies and the whole gamification layer is
decoration.

Three pieces:

* `new_device_id()`   - UUIDv7, written to BOTH localStorage and an httpOnly
                        cookie by the frontend (Phase 3). Time-ordered so it
                        indexes well as a primary key.
* recovery phrase     - 12 words, 88 bits of entropy + 8-bit checksum. The
                        phrase itself is NEVER stored; only `secret_hash`.
* `upgrade_anonymous_to_account` - built now, unused now. Every identity-bearing
                        table already carries a nullable `user_id`, so the day
                        accounts arrive is a data migration, not a rewrite.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import uuid

from bhashasetu.core.wordlist import INDEX, RECOVERY_WORDLIST_VERSION, WORDS

PHRASE_WORDS = 12
_ENTROPY_BYTES = PHRASE_WORDS - 1  # last word is the checksum


def new_device_id() -> str:
    """UUIDv7 (RFC 9562 §5.7).

    Python 3.13 has no `uuid.uuid7`, so it is built here rather than pulling a
    dependency for 20 lines of bit-shifting.
    """
    ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF
    rand = secrets.token_bytes(10)

    value = ms << 80
    value |= 0x7 << 76  # version 7
    value |= (int.from_bytes(rand[:2], "big") & 0x0FFF) << 64  # rand_a
    tail = int.from_bytes(rand[2:], "big") & ((1 << 62) - 1)
    value |= 0b10 << 62  # RFC 9562 variant
    value |= tail
    return str(uuid.UUID(int=value))


def device_id_timestamp_ms(device_id: str) -> int:
    """Recover the creation time embedded in a UUIDv7. Useful for cohorting
    without storing a separate created_at the user never consented to."""
    return uuid.UUID(device_id).int >> 80


# ---------------------------------------------------------------------------
# Recovery phrase


def _checksum(payload: bytes) -> int:
    return hashlib.sha256(payload).digest()[0]


def generate_recovery_phrase() -> tuple[str, str]:
    """Return `(phrase, secret_hash)`.

    Store `secret_hash`. Show `phrase` to the user exactly once. There is no
    recovery-of-the-recovery: if they lose the phrase and clear the device, the
    progress is gone, and the UI must say so plainly.
    """
    payload = secrets.token_bytes(_ENTROPY_BYTES)
    words = [WORDS[b] for b in payload] + [WORDS[_checksum(payload)]]
    return " ".join(words), _secret_hash(payload)


class InvalidRecoveryPhrase(ValueError):
    pass


def parse_recovery_phrase(phrase: str) -> str:
    """Validate a user-typed phrase and return its `secret_hash` for lookup.

    Tolerant of case, extra whitespace, and the punctuation people paste along
    with it. Not tolerant of a bad checksum - a typo must fail loudly rather than
    silently resolve to nobody's account.
    """
    cleaned = phrase.replace(",", " ").replace("\n", " ").strip().lower()
    words = [w for w in cleaned.split(" ") if w]
    if len(words) != PHRASE_WORDS:
        raise InvalidRecoveryPhrase(
            f"expected {PHRASE_WORDS} words, got {len(words)}"
        )

    unknown = [w for w in words if w not in INDEX]
    if unknown:
        raise InvalidRecoveryPhrase(f"not in the wordlist: {', '.join(unknown)}")

    payload = bytes(INDEX[w] for w in words[:-1])
    if INDEX[words[-1]] != _checksum(payload):
        raise InvalidRecoveryPhrase("checksum word does not match - check for a typo")
    return _secret_hash(payload)


def _secret_hash(payload: bytes) -> str:
    """Domain-separated, salted with a deployment pepper when one is configured.

    A recovery phrase is a bearer credential. Hashing it with a bare sha256 means
    a leaked database is directly replayable; the pepper (held outside the DB)
    is what makes it not.
    """
    pepper = os.environ.get("BHASHASETU_RECOVERY_PEPPER", "").encode("utf-8")
    return hmac.new(
        pepper or b"bhashasetu-dev-pepper",
        b"recovery-v%d|" % RECOVERY_WORDLIST_VERSION + payload,
        hashlib.sha256,
    ).hexdigest()


def verify_recovery_phrase(phrase: str, expected_hash: str) -> bool:
    try:
        return hmac.compare_digest(parse_recovery_phrase(phrase), expected_hash)
    except InvalidRecoveryPhrase:
        return False
