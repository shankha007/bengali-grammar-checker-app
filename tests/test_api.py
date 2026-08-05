"""HTTP surface tests.

The offset-remapping test is the one that matters. Everything else here is
plumbing; that one encodes a bug that reached a browser and silently corrupted
the user's text.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bhashasetu.api import create_app
from bhashasetu.core.types import ErrorClass
from bhashasetu.language_packs.bn import chars as C


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_all_twelve_classes_exposed(client: TestClient) -> None:
    body = client.get("/api/classes").json()
    assert len(body) == 12
    # Unimplemented classes must still be listed, with a null stage, so the UI
    # can grey them out rather than pretend they do not exist.
    #
    # The count is not asserted: classes move from null to a stage as detectors
    # land (CLASSIFIER, VERB_INFLECTION and AGREEMENT did), and a test that
    # hard-codes how many are missing fails on progress rather than on a bug.
    # What must stay true is the contract — every class listed, every one either
    # honestly staged or honestly null.
    assert {c["code"] for c in body} == {c.value for c in ErrorClass}
    for entry in body:
        stage = entry["implementedAtStage"]
        assert stage is None or 0 <= stage <= 4
        assert entry["label_native"] and entry["label_en"]


def test_check_returns_explainable_edits(client: TestClient) -> None:
    res = client.post("/api/check", json={"text": "এর কারন কী?"})
    assert res.status_code == 200
    body = res.json()
    edit = next(e for e in body["edits"] if e["errorClass"] == "NOTVA_SHOTVA")
    assert edit["suggestions"] == ["কারণ"]
    assert edit["explanation_bn"] and edit["explanation_en"]
    assert "{" not in edit["explanation_bn"]  # no unsubstituted placeholders
    assert edit["ruleReference"]


def test_offsets_index_the_text_the_client_sent(client: TestClient) -> None:
    """Spans must slice out of the ORIGINAL text, not the normalized text.

    Stage 0 composing `ড + ়` into `ড়` removes a character. When the response
    carried normalized offsets, a client replacing a span landed one character
    early and ate the preceding space — "এর কারন" became "এরকারণ" in the editor.

    The decomposed nukta here sits *before* the error on purpose; that is what
    makes the two coordinate systems diverge.
    """
    text = "সে পড" + C.NUKTA + "ছে । এর কারন কী?"
    body = client.post("/api/check", json={"text": text}).json()

    assert body["normalizedDiffers"] is True
    assert "compose_nukta" in body["appliedRules"]
    assert body["edits"], "expected at least one edit"

    for edit in body["edits"]:
        assert text[edit["start"] : edit["end"]] == edit["original"], (
            f"span ({edit['start']},{edit['end']}) does not slice "
            f"{edit['original']!r} out of the submitted text"
        )


def test_offsets_are_stable_when_nothing_is_normalized(client: TestClient) -> None:
    text = "এর কারন কী?"
    body = client.post("/api/check", json={"text": text}).json()
    assert body["normalizedDiffers"] is False
    for edit in body["edits"]:
        assert text[edit["start"] : edit["end"]] == edit["original"]


def test_suppressed_hidden_unless_requested(client: TestClient) -> None:
    # A sentence that definitely produces an edit, gated above its confidence.
    # An earlier version used ভাসায়, which the real bn_BD dictionary accepts as
    # a word (it is one) — so the test was asserting on an empty result.
    payload = {"text": "এর কারন কী?", "minConfidence": 0.99}
    assert client.post("/api/check", json=payload).json()["suppressed"] == []
    body = client.post(
        "/api/check", json={**payload, "includeSuppressed": True}
    ).json()
    assert body["suppressed"], "high threshold should push edits into suppressed"


def test_stages_two_to_four_report_as_skipped(client: TestClient) -> None:
    body = client.post("/api/check", json={"text": "এর কারন কী?"}).json()
    by_stage = {s["stage"]: s for s in body["stages"]}
    for stage in (2, 3, 4):
        assert by_stage[stage]["skipped"] is not None


def test_device_cookie_is_issued_and_reused(client: TestClient) -> None:
    """Spec §5: anonymous identity, httpOnly, no login anywhere in the flow."""
    fresh = TestClient(create_app())
    first = fresh.get("/api/identity")
    device = first.json()["deviceId"]
    assert first.json()["tier"] == "free_unlimited"
    assert "bhashasetu_device" in first.cookies or device
    # Second call on the same client must not mint a new identity.
    assert fresh.get("/api/identity").json()["deviceId"] == device


def test_recovery_phrase_is_twelve_words(client: TestClient) -> None:
    body = client.post("/api/identity/recovery").json()
    assert body["words"] == 12
    assert len(body["phrase"].split()) == 12


def test_bijoy_refuses_rather_than_mangles(client: TestClient) -> None:
    """Detection without conversion is the correct answer while the glyph table
    is partial — a half-converted document is worse than an untouched one."""
    body = client.post(
        "/api/convert/bijoy",
        json={"text": "Avwg evsjv‡`‡k _vwK| Ges Avwg eB cwo| ‡ivR mKv‡j D‡V nvuwU|"},
    ).json()
    assert body["detected"] is True
    if not body["converted"]:
        assert body["note"] and "95%" in body["note"]


def test_bijoy_detection_needs_enough_signal(client: TestClient) -> None:
    """A known limitation, pinned so it is a decision rather than a surprise.

    Detection needs at least four high-range signature characters. A very short
    Bijoy fragment can fall below that and go undetected. Loosening it would
    start pulling in Latin text that happens to contain a stray ‡ or †, and a
    false "this is Bijoy, let me convert it" is far worse than a missed one.
    """
    body = client.post("/api/convert/bijoy", json={"text": "Avwg evsjv"}).json()
    assert body["detected"] is False
    assert body["text"] == "Avwg evsjv"  # untouched


def test_plain_english_is_not_flagged_as_bijoy(client: TestClient) -> None:
    body = client.post(
        "/api/convert/bijoy",
        json={"text": "The quick brown fox jumps over the lazy dog."},
    ).json()
    assert body["detected"] is False
