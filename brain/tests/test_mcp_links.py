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


def test_provision_creates_then_rotates(store):
    first = store.provision("steve")
    assert store.match(first) == "steve" and store.names() == ["steve"]
    second = store.provision("steve")
    assert store.match(second) == "steve" and store.match(first) is None


def test_revoked_player_cannot_self_provision_until_re_added(store):
    store.provision("steve")
    store.revoke("steve")
    assert store.names() == []
    with pytest.raises(LinkError):
        store.provision("steve")
    token = store.add("steve")  # nistroy rouvre l'accès à la main
    assert store.match(token) == "steve"
    assert store.match(store.provision("steve")) == "steve"


def test_block_prevents_auto_provision_even_without_existing_link(store):
    store.block("steve-jeu")
    with pytest.raises(LinkError):
        store.provision("steve-jeu")
    active = store.provision("alex-jeu")
    store.block("alex-jeu")
    assert store.match(active) is None and store.names() == []
    with pytest.raises(LinkError):
        store.block("Pas Valide")
