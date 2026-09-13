from datetime import UTC, datetime

import pytest

from minecraft_ia.assistant import Assistant, Limits, quota_day
from minecraft_ia.db import Item, Recipe
from minecraft_ia.kb import KnowledgeBase, NoteStatus
from minecraft_ia.llm import LLMError, LLMQuotaError, Step, ToolCall
from minecraft_ia.tools import Toolbox

from .test_tools import FakeHttp

PLAYER = "0f1e2d3c-0000-0000-0000-000000000001"
NOON_UTC = datetime(2026, 9, 12, 12, 0, tzinfo=UTC)


class ScriptedLLM:
    def __init__(self, *steps):
        self.steps = list(steps)
        self.seen_messages = []

    def step(self, system, messages, tools):
        self.seen_messages.append(list(messages))
        item = self.steps.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def call(name, **args):
    return Step(text=None, calls=[ToolCall(name, args)], raw=None)


def make(db, kb_root, llm, pause=None, **limits):
    kb = KnowledgeBase(kb_root)
    db.replace_kb_index(kb.documents())
    http = FakeHttp(
        {
            "https://api.modrinth.com/v2/project/aether": {
                "slug": "aether",
                "title": "The Aether",
                "description": "",
                "body": "",
                "wiki_url": None,
                "source_url": None,
                "issues_url": None,
            }
        }
    )
    llms = llm if isinstance(llm, list) else [llm]
    assistant = Assistant(
        db, kb, llms, Toolbox(db, kb, http), Limits(**limits), clock=lambda: NOON_UTC, pause=pause or (lambda _s: None)
    )
    return assistant, kb


def test_quota_day_uses_pacific_midnight():
    assert quota_day(datetime(2026, 9, 12, 6, 59, tzinfo=UTC)) == "2026-09-11"
    assert quota_day(datetime(2026, 9, 12, 7, 0, tzinfo=UTC)) == "2026-09-12"


def test_falls_back_to_next_model_with_fresh_conversation(db, kb_root):
    down = ScriptedLLM(LLMError("503 UNAVAILABLE"))
    backup = ScriptedLLM(
        call("search_knowledge", query="aether portail"),
        call("answer", text="Cadre de glowstone + seau d'eau.", sources=["kb:mods/aether.md"]),
    )
    assistant, _ = make(db, kb_root, [down, backup])
    reply = assistant.ask(PLAYER, "Steve", "Comment aller dans l'Aether ?")
    assert reply.status == "ok"
    assert len(backup.seen_messages[0]) == 1  # conversation neuve : rien du modèle en panne n'est rejoué
    assert db.llm_calls_on("2026-09-12") == 2


def test_all_models_failing_reports_error(db, kb_root):
    llms = [ScriptedLLM(LLMError("503")), ScriptedLLM(LLMQuotaError("429"))]
    reply = make(db, kb_root, llms)[0].ask(PLAYER, "Steve", "q")
    assert reply.status == "error" and "Google" in reply.text


def test_sourced_answer_is_ok_and_recorded(db, kb_root):
    llm = ScriptedLLM(
        call("search_knowledge", query="aether portail"),
        call("answer", text="Cadre de glowstone + seau d'eau.", sources=["kb:mods/aether.md"]),
    )
    assistant, _ = make(db, kb_root, llm)
    reply = assistant.ask(PLAYER, "Steve", "Comment aller dans l'Aether ?")
    assert reply.status == "ok"
    assert reply.sources == ["kb:mods/aether.md"]
    assert db.history(PLAYER, 5)[0].text == "Cadre de glowstone + seau d'eau."
    assert db.llm_calls_on("2026-09-12") == 2


def test_invented_source_becomes_je_sais_pas(db, kb_root):
    llm = ScriptedLLM(call("answer", text="Il faut un portail en diamant.", sources=["https://inventé.example"]))
    reply = make(db, kb_root, llm)[0].ask(PLAYER, "Steve", "Comment aller dans l'Aether ?")
    assert reply.status == "unknown"
    assert reply.text.lower().startswith("je sais pas")
    assert "diamant" not in reply.text


def test_model_unknown_keeps_explanation(db, kb_root):
    llm = ScriptedLLM(call("answer", text="Rien dans les fiches.", sources=[], unknown=True))
    reply = make(db, kb_root, llm)[0].ask(PLAYER, "Steve", "Quel est le seed ?")
    assert reply.status == "unknown" and "Rien dans les fiches." in reply.text


def test_item_markers_kept_only_if_seen_by_a_tool_and_extracted(db, kb_root):
    db.replace_exact_data(
        [
            Item("minecraft:crafting_table", "minecraft", "block", "Crafting Table", "Établi"),
            Item("minecraft:diamond", "minecraft", "item", "Diamond", "Diamant"),
        ],
        [
            Recipe(
                "minecraft:crafting_table",
                "minecraft",
                "minecraft:crafting_shaped",
                "minecraft:crafting_table",
                ["#minecraft:planks"],
                "{}",
            )
        ],
    )
    llm = ScriptedLLM(
        call("item_recipes", item_id="minecraft:crafting_table"),
        call(
            "answer",
            text="4 planches [[#minecraft:planks]] en carré : établi [[minecraft:crafting_table]]. "
            "Pas de diamant [[minecraft:diamond]].",
            sources=["data:recipe:minecraft:crafting_table"],
        ),
    )
    reply = make(db, kb_root, llm)[0].ask(PLAYER, "Steve", "Comment faire un établi ?")
    assert reply.status == "ok"
    # diamant : existe dans les jars mais aucun outil ne l'a renvoyé → icône retirée, mot gardé
    assert (
        reply.text == "4 planches [[#minecraft:planks]] en carré : établi [[minecraft:crafting_table]]. Pas de diamant."
    )
    assert db.history(PLAYER, 1)[0].text == reply.text


def test_plain_text_is_nudged_then_round_limit(db, kb_root):
    llm = ScriptedLLM(
        Step(text="blabla", calls=[], raw=None),
        call("search_knowledge", query="x"),
        call("search_knowledge", query="y"),
    )
    assistant, _ = make(db, kb_root, llm, max_tool_rounds=3)
    reply = assistant.ask(PLAYER, "Steve", "question")
    assert reply.status == "unknown"
    assert any(m.role == "user" and "answer" in (m.text or "") for m in llm.seen_messages[1])


def test_player_quota(db, kb_root):
    llm = ScriptedLLM(call("answer", text="x", sources=[], unknown=True))
    assistant, _ = make(db, kb_root, llm, questions_per_player_per_day=1)
    assistant.ask(PLAYER, "Steve", "q1")
    reply = assistant.ask(PLAYER, "Steve", "q2")
    assert reply.status == "quota" and reply.answer_id is None
    assert "09h00" in reply.text  # minuit Pacifique = 9h à Paris ce jour-là


def test_global_llm_budget(db, kb_root):
    db.add_llm_calls("2026-09-12", 10)
    reply = make(db, kb_root, ScriptedLLM(), llm_calls_per_day=10)[0].ask(PLAYER, "Steve", "q")
    assert reply.status == "quota"


@pytest.mark.parametrize("question", ["", "   ", "x" * 300])
def test_invalid_question(db, kb_root, question):
    reply = make(db, kb_root, ScriptedLLM(), max_question_chars=256)[0].ask(PLAYER, "Steve", question)
    assert reply.status == "invalid"


def test_llm_quota_error_is_reported(db, kb_root):
    reply = make(db, kb_root, ScriptedLLM(LLMQuotaError("429")))[0].ask(PLAYER, "Steve", "q")
    assert reply.status == "error" and "Google" in reply.text


def test_notes_saved_after_answer_with_answer_id(db, kb_root):
    llm = ScriptedLLM(
        call("modrinth_project", slug="aether"),
        call("save_note", mod="aether", fact="Portail au glowstone.", source="https://modrinth.com/mod/aether"),
        call("answer", text="Glowstone.", sources=["https://modrinth.com/mod/aether"]),
    )
    assistant, kb = make(db, kb_root, llm)
    reply = assistant.ask(PLAYER, "Steve", "portail aether ?")
    [note] = kb.notes()
    assert note.meta["reponse"] == reply.answer_id
    assert note.meta["version"] == "1.21.1-1.5.11-fabric"
    assert db.search_kb("glowstone", 5)  # index reconstruit


def test_votes_update_notes_and_down_vote_retries_once(db, kb_root):
    kb = KnowledgeBase(kb_root)
    note = kb.add_note("aether", "Portail au briquet.", "https://x", "1", today="2026-09-12")
    llm = ScriptedLLM(
        call("search_knowledge", query="briquet"),
        call("answer", text="Briquet.", sources=[f"note:{note.path}"]),
        call("answer", text="Je ne trouve rien d'autre.", sources=[], unknown=True),
    )
    assistant, kb = make(db, kb_root, llm)
    first = assistant.ask(PLAYER, "Steve", "portail ?")
    assert assistant.vote(first.answer_id, "someone-else", up=False) is None  # seul l'auteur vote
    retry = assistant.vote(first.answer_id, PLAYER, up=False)
    assert kb.note(note.path).meta["statut"] == NoteStatus.CONTESTED
    assert retry.status == "unknown" and retry.answer_id != first.answer_id
    assert "Briquet." in llm.seen_messages[-1][0].text  # le LLM sait ce qui a été jugé faux
    assert assistant.vote(first.answer_id, PLAYER, up=False) is None  # une seule relance
    assert db.questions_on(PLAYER, "2026-09-12") == 1  # la relance ne coûte pas de question


def test_up_vote_confirms_notes(db, kb_root):
    kb = KnowledgeBase(kb_root)
    note = kb.add_note("aether", "Portail au glowstone.", "https://x", "1", today="2026-09-12")
    llm = ScriptedLLM(
        call("search_knowledge", query="glowstone"), call("answer", text="Glowstone.", sources=[f"note:{note.path}"])
    )
    assistant, kb = make(db, kb_root, llm)
    reply = assistant.ask(PLAYER, "Steve", "portail ?")
    assert assistant.vote(reply.answer_id, PLAYER, up=True) is None
    assert kb.note(note.path).meta["statut"] == NoteStatus.PLAYER_CONFIRMED
    assert db.history(PLAYER, 1)[0].vote is True


def test_prefetch_lets_model_answer_in_one_call(db, kb_root):
    llm = ScriptedLLM(call("answer", text="Cadre de glowstone + seau d'eau.", sources=["kb:mods/aether.md"]))
    assistant, _ = make(db, kb_root, llm)
    reply = assistant.ask(PLAYER, "Steve", "Comment aller dans l'Aether ?")
    assert reply.status == "ok" and reply.sources == ["kb:mods/aether.md"]
    assert "seau d'eau" in llm.seen_messages[0][0].text  # contenu de la fiche fourni d'avance
    assert db.llm_calls_on("2026-09-12") == 1


def test_per_minute_quota_waits_then_retries_same_model(db, kb_root):
    waits = []
    llm = ScriptedLLM(
        LLMQuotaError("429", retry_after=8.0, per_minute=True),
        call("answer", text="Glowstone.", sources=["kb:mods/aether.md"]),
    )
    backup = ScriptedLLM()
    assistant, _ = make(db, kb_root, [llm, backup], pause=waits.append)
    reply = assistant.ask(PLAYER, "Steve", "Comment aller dans l'Aether ?")
    assert reply.status == "ok" and waits == [8.0] and not backup.seen_messages


def test_daily_quota_or_long_wait_falls_back_without_waiting(db, kb_root):
    waits = []
    daily = ScriptedLLM(LLMQuotaError("429", retry_after=3.0, per_minute=False))
    slow = ScriptedLLM(LLMQuotaError("429", retry_after=60.0, per_minute=True))
    backup = ScriptedLLM(call("answer", text="Glowstone.", sources=["kb:mods/aether.md"]))
    assistant, _ = make(db, kb_root, [daily, slow, backup], pause=waits.append)
    reply = assistant.ask(PLAYER, "Steve", "Comment aller dans l'Aether ?")
    assert reply.status == "ok" and waits == []
