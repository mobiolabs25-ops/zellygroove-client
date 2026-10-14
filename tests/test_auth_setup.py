import asyncio
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from zellygroove_client import auth, connect
from zellygroove_client import setup as registration
from zellygroove_client.mcp_server import StudioError, StudioTools, build_server


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    monkeypatch.delenv("STUDIO_TOKEN", raising=False)
    monkeypatch.delenv("STUDIO_URL", raising=False)
    monkeypatch.setenv("STUDIO_TOKEN_FILE", str(tmp_path / "token.json"))


def test_missing_credentials_fail_before_any_request():
    with pytest.raises(StudioError, match="login"):
        auth.client_from_env()


@pytest.mark.parametrize("url", ["http://example.com", "https://user:password@example.com", "https://example.com?token=x", "https://example.com#x"])
def test_unsafe_urls_are_refused(url, monkeypatch):
    monkeypatch.setenv("STUDIO_URL", url)
    with pytest.raises(StudioError):
        auth.service_url()


def save_token():
    path = auth.token_path()
    path.write_text(json.dumps({"studio_url": auth.DEFAULT_URL, "token": "test-only-credential"}))
    path.chmod(0o600)
    return path


def test_token_is_origin_bound_and_never_follows_redirects():
    save_token()
    with auth.client_from_env() as client:
        assert client.headers["authorization"] == "Bearer test-only-credential"
        assert client.follow_redirects is False
    with pytest.raises(StudioError, match="주소"):
        auth.saved_token("https://another.example.com")


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_world_readable_token_is_refused():
    save_token().chmod(0o644)
    with pytest.raises(StudioError, match="0600"):
        auth.saved_token(auth.DEFAULT_URL)


def test_login_validates_token_then_writes_private_file_without_echo(monkeypatch, capsys):
    monkeypatch.setattr(auth.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(auth.getpass, "getpass", lambda _: "test-only-credential")
    actual_client = httpx.Client
    requests = []
    def answer(request):
        requests.append(request)
        return httpx.Response(200, json={"operator": False})
    monkeypatch.setattr(auth.httpx, "Client", lambda **kwargs: actual_client(transport=httpx.MockTransport(answer), **kwargs))
    assert auth.login() == 0
    assert len(requests) == 1 and requests[0].url.path == "/api/settings/account"
    assert auth.saved_token(auth.DEFAULT_URL) == "test-only-credential"
    assert "test-only-credential" not in capsys.readouterr().out
    if os.name == "posix":
        assert auth.token_path().stat().st_mode & 0o777 == 0o600


def test_rejected_login_does_not_replace_saved_token(monkeypatch):
    original = save_token().read_bytes()
    monkeypatch.setattr(auth.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(auth.getpass, "getpass", lambda _: "rejected-test-credential")
    actual_client = httpx.Client
    monkeypatch.setattr(auth.httpx, "Client", lambda **kwargs: actual_client(transport=httpx.MockTransport(
        lambda _: httpx.Response(401, json={"detail": "인증 실패"})), **kwargs))
    with pytest.raises(StudioError, match="인증 실패"):
        auth.login()
    assert auth.token_path().read_bytes() == original


def test_setup_registers_only_selected_client_without_literal_token(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(registration.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = []
    def execute(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if "get" in args else 0)
    monkeypatch.setattr(registration.subprocess, "run", execute)
    monkeypatch.setenv("STUDIO_TOKEN", "test-only-credential")
    assert registration.setup(["--client", "codex"]) == 0
    add = calls[-1]
    assert add[:4] == ["/usr/bin/codex", "mcp", "add", "zellygroove"]
    assert "test-only-credential" not in str(calls)
    assert any(arg.startswith("STUDIO_TOKEN_FILE=") for arg in add)
    assert add[-1] == "zellygroove-mcp"
    assert (tmp_path / ".codex/skills/zellygroove/SKILL.md").exists()
    assert not (tmp_path / ".claude").exists()


def test_setup_preserves_existing_registration_and_modified_skill(monkeypatch, tmp_path):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(registration.shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = []
    def execute(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(registration.subprocess, "run", execute)
    skill = tmp_path / ".claude/skills/zellygroove/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("user customization")
    with pytest.raises(StudioError, match="기존 스킬"):
        registration.setup(["--client", "claude"])
    assert all("add" not in command for command in calls)
    assert skill.read_text() == "user customization"


def test_help_and_guide_are_offline_even_with_invalid_saved_credentials(monkeypatch, capsys):
    auth.token_path().write_text("invalid")
    monkeypatch.setattr(connect.sys, "argv", ["zellygroove", "--help"])
    assert connect.main() == 0
    assert "studio_credits" in capsys.readouterr().out


def test_public_client_has_no_operator_methods_even_for_operator_credentials():
    tools = StudioTools(httpx.Client(base_url="https://studio.test", headers={"authorization": "Bearer operator-test"}))
    names = {tool.name for tool in asyncio.run(build_server(tools).list_tools())}
    for name in ("publish_track", "build_site", "set_youtube_id", "preview_playlist", "preview_lounge", "import_scene", "draw_groove_scene"):
        assert name not in names and not hasattr(tools, name)
    for name in names:
        assert hasattr(tools, connect.ALIASES.get(name, name)), name


def test_permission_refusal_is_reported_without_a_retry(capsys):
    calls = []
    def answer(request):
        calls.append(request)
        return httpx.Response(403, json={"detail": "접근 권한 없음"})
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(answer)))
    assert connect.run(["studio_credits"], tools, io.StringIO()) == 1
    assert len(calls) == 1
    assert "접근 권한 없음" in capsys.readouterr().err
