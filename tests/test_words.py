"""The client's own messages follow STUDIO_LANG, then the account's language, then this computer's (2026-11-13)."""
import json

import httpx
import pytest

from zellygroove_client import auth, words
from zellygroove_client.mcp_server import StudioError, StudioTools


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    for name in ("STUDIO_TOKEN", "STUDIO_URL", "STUDIO_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("STUDIO_TOKEN_FILE", str(tmp_path / "token.json"))
    monkeypatch.setattr(words, "_learned", None)


def tools(headers, language=None):
    def answer(request):
        return httpx.Response(404, json={"detail": "not found"}, headers=headers)
    return StudioTools(httpx.Client(base_url="https://zellygroove.com", transport=httpx.MockTransport(answer),
                                    headers={"Authorization": "Bearer t", **({"X-Studio-Lang": language} if language else {})}))


def test_this_computers_locale_before_anything_is_known(monkeypatch):
    assert words.language() == "ko"                                  # nothing says: Korean, as before
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    assert words.say("한국어", "English") == "English"
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    assert words.say("한국어", "English") == "한국어"


def test_the_accounts_language_is_learned_from_the_service_and_studio_lang_wins(monkeypatch):
    monkeypatch.setenv("LANG", "ko_KR.UTF-8")
    with pytest.raises(StudioError):
        tools({"content-language": "en"})._call("GET", "/api/tracks/x")
    assert words.language() == "en"
    with pytest.raises(StudioError):
        tools({})._call("GET", "/api/tracks/x")                      # a Korean account says nothing
    assert words.language() == "ko"
    monkeypatch.setenv("STUDIO_LANG", "en")
    assert words.language() == "en" and auth.asked_language() == {"X-Studio-Lang": "en"}
    with pytest.raises(StudioError, match="Cannot reach Zelly Groove"):
        StudioTools(httpx.Client(base_url="https://zellygroove.com", transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("x")))))._call("GET", "/api/health")


def test_the_saved_token_keeps_the_accounts_language():
    path = auth.token_path()
    path.write_text(json.dumps({"studio_url": auth.DEFAULT_URL, "token": "test-only-credential", "lang": "en"}))
    path.chmod(0o600)
    assert auth.saved_token(auth.DEFAULT_URL) == "test-only-credential" and words.language() == "en"
