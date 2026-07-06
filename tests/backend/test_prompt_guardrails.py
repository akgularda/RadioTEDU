import unittest
from pathlib import Path


FORBIDDEN = [
    "Backlink Broadcast",
    "Thinking Frequencies",
    "OpenAIR",
    "Grok and Roll",
    "Archive Broadcast",
    "demo_tracks.json",
    "generate_demo_data.py",
    "RADIOTEDU_MODE=demo",
    "fake listeners",
    "fake donations",
    "fake analytics",
]


class PromptGuardrailTests(unittest.TestCase):
    def test_forbidden_demo_terms_do_not_appear_in_project_files(self) -> None:
        root = Path(__file__).resolve().parents[2]
        texts = []
        for path in root.rglob("*"):
            if path.is_dir() or any(part in {".git", "node_modules", "__pycache__", ".venv", "tests", "__tests__"} for part in path.parts):
                continue
            if path.suffix.lower() not in {".py", ".ts", ".tsx", ".css", ".html", ".md", ".json", ".example", ".txt"}:
                continue
            texts.append(path.read_text(encoding="utf-8", errors="ignore"))
        combined = "\n".join(texts)
        for term in FORBIDDEN:
            self.assertNotIn(term, combined)


if __name__ == "__main__":
    unittest.main()
