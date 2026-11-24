import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

# Provide lightweight stubs for optional third-party modules if not installed in test env
for _mod in (
    "PyPDF2",
    "email_validator",
    "fpdf",
    "groq",
    "mailjet_rest",
    "Gsheet",
):
    if _mod not in sys.modules:
        stub = types.ModuleType(_mod)
        stub.PdfReader = MagicMock()
        stub.EmailNotValidError = Exception
        stub.validate_email = MagicMock()
        stub.FPDF = MagicMock()
        stub.Groq = MagicMock()
        stub.Client = MagicMock()
        stub.gsheet = MagicMock()
        sys.modules[_mod] = stub

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app


def test_latin1_safe_replaces_non_latin_characters():
    result = app._latin1_safe("Summary — ₹500 • Clause")
    assert result.encode("latin-1") is not None
    assert "Summary" in result
    assert "Clause" in result


def test_get_groq_client_raises_when_missing_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    try:
        app._get_groq_client()
        assert False, "Expected RuntimeError when GROQ_API_KEY is missing"
    except RuntimeError as exc:
        assert "GROQ_API_KEY" in str(exc)
