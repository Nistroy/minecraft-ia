import json
import stat

import pytest

from minecraft_ia.mcp_links import LinkError, LinkStore


@pytest.fixture
def store(tmp_path):
    return LinkStore(tmp_path / "mcp-links.json")


def test_add_returns_token_but_stores_only_its_hash(store):
    token = store.add("bob")
    assert len(token) >= 32
    raw = store.path.read_text(encoding="utf-8")
    assert token not in raw and "bob" in json.loads(raw)
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert store.match(token) == "bob"
    assert store.match(token[:-1] + "x") is None and store.match("") is None


@pytest.mark.parametrize("name", ["", "Bob Smith", "a" * 33, "../x"])
def test_rejects_invalid_names(store, name):
    with pytest.raises(LinkError):
        store.add(name)


def test_duplicate_name_is_refused(store):
    store.add("bob")
    with pytest.raises(LinkError):
        store.add("bob")


def test_revoke_and_names(store):
    bob, alice = store.add("bob"), store.add("alice")
    assert store.names() == ["alice", "bob"]
    store.revoke("bob")
    assert store.match(bob) is None and store.match(alice) == "alice"
    with pytest.raises(LinkError):
        store.revoke("bob")


def test_running_server_sees_changes_without_restart(tmp_path):
    path = tmp_path / "mcp-links.json"
    server_side = LinkStore(path)
    assert server_side.match("x" * 43) is None  # fichier absent : aucun lien
    token = LinkStore(path).add("bob")
    assert server_side.match(token) == "bob"
    LinkStore(path).revoke("bob")
    assert server_side.match(token) is None
