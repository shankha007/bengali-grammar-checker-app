"""Anonymous identity + the account-upgrade path (spec §5)."""

from __future__ import annotations

import sqlite3
import uuid

import pytest

from bhashasetu.core import storage
from bhashasetu.core.identity import (
    InvalidRecoveryPhrase,
    device_id_timestamp_ms,
    generate_recovery_phrase,
    new_device_id,
    parse_recovery_phrase,
    verify_recovery_phrase,
)
from bhashasetu.core.wordlist import WORDS


def test_wordlist_is_exactly_256_unique_words() -> None:
    assert len(WORDS) == 256
    assert len(set(WORDS)) == 256
    assert all(w.isascii() and w.islower() for w in WORDS)


def test_device_id_is_uuid7_and_time_ordered() -> None:
    a = new_device_id()
    b = new_device_id()
    assert uuid.UUID(a).version == 7
    assert uuid.UUID(b).version == 7
    # RFC 9562 variant bits
    assert uuid.UUID(a).variant == uuid.RFC_4122
    # Time-ordered, but only to millisecond resolution: two ids minted in the
    # same millisecond differ solely in their random bits and have no defined
    # relative order. Asserting otherwise makes the test flaky on fast machines.
    assert device_id_timestamp_ms(a) <= device_id_timestamp_ms(b)
    assert a != b


def test_recovery_phrase_roundtrip() -> None:
    phrase, secret_hash = generate_recovery_phrase()
    assert len(phrase.split()) == 12
    assert parse_recovery_phrase(phrase) == secret_hash
    assert verify_recovery_phrase(phrase, secret_hash)


def test_recovery_phrase_is_whitespace_and_case_tolerant() -> None:
    phrase, secret_hash = generate_recovery_phrase()
    messy = "  " + phrase.upper().replace(" ", ",  ") + "\n"
    assert verify_recovery_phrase(messy, secret_hash)


def test_recovery_phrase_rejects_a_typo() -> None:
    phrase, secret_hash = generate_recovery_phrase()
    words = phrase.split()
    # Swap one word for a different valid word - checksum must catch it.
    words[0] = WORDS[(WORDS.index(words[0]) + 1) % 256]
    assert not verify_recovery_phrase(" ".join(words), secret_hash)


@pytest.mark.parametrize(
    "bad",
    ["", "able acid", "able acid acre also amber amid ankle apple apron arch arena",
     "not a real word here at all so this must fail loudly ok"],
)
def test_recovery_phrase_rejects_malformed_input(bad: str) -> None:
    with pytest.raises(InvalidRecoveryPhrase):
        parse_recovery_phrase(bad)


# --- storage ---------------------------------------------------------------

@pytest.fixture()
def conn() -> sqlite3.Connection:
    return storage.connect(":memory:")


def test_every_user_is_free_unlimited(conn: sqlite3.Connection) -> None:
    """Spec §2: build the entitlement plumbing, hard-code the tier."""
    device = new_device_id()
    storage.ensure_device(conn, device)
    assert storage.tier_for(conn, device) == "free_unlimited"


def test_upgrade_anonymous_to_account_binds_every_table(
    conn: sqlite3.Connection,
) -> None:
    device = new_device_id()
    storage.ensure_device(conn, device)
    conn.execute(
        "INSERT INTO documents(doc_id, device_id, title) VALUES(?,?,?)",
        ("d1", device, "খসড়া"),
    )
    conn.execute(
        "INSERT INTO error_events(device_id, error_class, stage) VALUES(?,?,?)",
        (device, "NOTVA_SHOTVA", 1),
    )

    touched = storage.upgrade_anonymous_to_account(conn, device, "user-1")
    assert touched >= 5  # devices, documents, error_events, streaks, entitlements

    for table in ("devices", "documents", "error_events", "streaks", "entitlements"):
        rows = conn.execute(
            f"SELECT COUNT(*) c FROM {table} WHERE device_id = ? AND user_id IS NULL",
            (device,),
        ).fetchone()
        assert rows["c"] == 0, f"{table} still has unbound rows"


def test_upgrade_is_idempotent(conn: sqlite3.Connection) -> None:
    device = new_device_id()
    storage.ensure_device(conn, device)
    storage.upgrade_anonymous_to_account(conn, device, "user-1")
    assert storage.upgrade_anonymous_to_account(conn, device, "user-1") == 0


def test_upgrade_refuses_to_steal_another_users_device(
    conn: sqlite3.Connection,
) -> None:
    device = new_device_id()
    storage.ensure_device(conn, device)
    storage.upgrade_anonymous_to_account(conn, device, "user-1")
    with pytest.raises(PermissionError):
        storage.upgrade_anonymous_to_account(conn, device, "user-2")


def test_recovery_hash_resolves_back_to_the_device(conn: sqlite3.Connection) -> None:
    device = new_device_id()
    storage.ensure_device(conn, device)
    phrase, secret_hash = generate_recovery_phrase()
    storage.attach_recovery(conn, device, secret_hash)
    assert storage.device_for_recovery_hash(conn, parse_recovery_phrase(phrase)) == device


def test_document_body_is_null_unless_explicitly_saved(
    conn: sqlite3.Connection,
) -> None:
    """Spec §10: no text persisted server-side unless the user saves it."""
    device = new_device_id()
    storage.ensure_device(conn, device)
    conn.execute(
        "INSERT INTO documents(doc_id, device_id) VALUES(?,?)", ("d1", device)
    )
    row = conn.execute("SELECT body FROM documents WHERE doc_id='d1'").fetchone()
    assert row["body"] is None
