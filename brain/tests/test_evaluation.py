from minecraft_ia.assistant import Reply
from minecraft_ia.evaluation import load_questions, run_eval


class CannedAssistant:
    def __init__(self, replies):
        self.replies = replies

    def ask(self, player, name, question):
        return self.replies[question]


def test_scores_correct_unknown_and_invented(tmp_path):
    path = tmp_path / "questions.toml"
    path.write_text(
        """
[[question]]
texte = "portail aether ?"
attendu = ["glowstone", "eau"]

[[question]]
texte = "seed du monde ?"
sais_pas = true

[[question]]
texte = "piège ?"
sais_pas = true

[[question]]
texte = "recette table ?"
attendu = ["planches"]
""",
        encoding="utf-8",
    )
    assistant = CannedAssistant(
        {
            "portail aether ?": Reply(1, "Cadre de Glowstone, seau d'EAU.", ["kb:x"], "ok"),
            "seed du monde ?": Reply(2, "Je sais pas.", [], "unknown"),
            "piège ?": Reply(3, "Réponse inventée", ["kb:x"], "ok"),
            "recette table ?": Reply(4, "Je sais pas.", [], "unknown"),
        }
    )
    report = run_eval(assistant, load_questions(path))
    assert (report.total, report.correct, report.unknown, report.invented) == (4, 2, 2, 1)
    assert [r.question for r in report.results if not r.passed] == ["piège ?", "recette table ?"]
