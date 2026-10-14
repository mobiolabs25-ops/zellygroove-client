"""Public agent clients expose account creation tools, never operator interfaces."""
import asyncio
import io
import json

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from zellygroove_client.connect import run
from zellygroove_client.mcp_server import StudioError, StudioTools, build_server


OPERATOR_TOOLS = {"publish_track", "build_site", "set_youtube_id", "preview_playlist", "preview_lounge",
                  "import_scene", "draw_groove_scene"}


def test_default_mcp_and_cli_do_not_advertise_or_invoke_operator_tools():
    calls = []
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(
        lambda request: calls.append(request) or httpx.Response(200, json={}))))
    server = build_server(tools)
    assert not OPERATOR_TOOLS & {t.name for t in asyncio.run(server.list_tools())}
    help_text = io.StringIO()
    assert run([], tools, help_text) == 0
    for name in OPERATOR_TOOLS:
        assert f"{name}(" not in help_text.getvalue()
        assert run([name], tools, io.StringIO()) == 1
        with pytest.raises(ToolError, match="Unknown tool"):
            asyncio.run(server.call_tool(name, {}))
    assert calls == []






def test_credit_and_model_metadata_use_the_same_read_only_api_in_mcp_and_cli():
    balance = {"enabled": True, "exempt": False, "granted": 120, "reserved": 10, "spent": 40, "available": 70,
               "period": {"expires_at": "2026-11-15T00:00:00Z"}}
    models = [{"name": "basic", "choice": {"id": "basic", "label": "기본"}, "generation_credits": 2,
               "available": True, "locked": False, "cost_krw": 999, "upstream": "private"}]
    def answer(request):
        assert request.method == "GET"
        return httpx.Response(200, json=balance if request.url.path == "/api/settings/credits" else models)
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(answer)))
    for name in ("studio_credits", "list_models"):
        output = io.StringIO()
        assert run([name], tools, output) == 0
        cli = json.loads(output.getvalue())
        result = asyncio.run(build_server(tools).call_tool(name, {}))
        decoded = [json.loads(part.text) for part in result.content] if isinstance(cli, list) else json.loads(result.content[0].text)
        assert decoded == cli
        if name == "studio_credits":
            assert cli == balance
        else:
            assert cli[0]["generation_credits"] == 2
            assert "cost_krw" not in cli[0] and "upstream" not in cli[0]


def test_model_choice_is_forwarded_to_the_existing_song_request():
    def answer(request):
        assert request.url.path == "/api/jobs"
        assert json.loads(request.content)["generation_mode"] == "basic"
        return httpx.Response(202, json={"job_id": "j-20261015-000000-abcdef"})
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(answer)))
    assert run(["create_song", "artist_id=null", "instrumental=true", "prompt=piano", "generation_mode=basic"], tools, io.StringIO()) == 0


def test_job_read_cancel_and_retry_are_distinct_operations():
    job_id = "j-20261015-000000-abcdef"
    calls = []
    def answer(request):
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/retry"):
            return httpx.Response(202, json={"job_id": "j-20261015-000001-abcdef"})
        if request.url.path.endswith("/cancel"):
            return httpx.Response(200, json={"status": "cancelled"})
        return httpx.Response(200, json={"id": job_id, "kind": "song", "status": "failed", "candidates": [],
                                         "request": {"private": "not for tools"}, "error": "failed"})
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(answer)))
    for name in ("get_job", "cancel_job", "retry_job"):
        output = io.StringIO()
        assert run([name, f"job_id={job_id}"], tools, output) == 0
        assert "private" not in output.getvalue()
    assert calls == [("GET", f"/api/jobs/{job_id}"), ("POST", f"/api/jobs/{job_id}/cancel"), ("POST", f"/api/jobs/{job_id}/retry")]
    assert tools.get_job(job_id)["status"] == "failed"
    assert "timed_out" not in tools.get_job(job_id)
    with pytest.raises(StudioError, match="올바르지 않은 id"):
        tools.retry_job("../settings/users")


def test_track_detail_has_a_browser_link_without_credentials_or_internal_request():
    track_id = "t-20261015-000000-abcdef"
    def answer(request):
        assert request.url.path == f"/api/tracks/{track_id}"
        return httpx.Response(200, json={"id": track_id, "title": "Piano", "status": "kept", "request": {"adapter": "private"}})
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(answer)))
    output = io.StringIO()
    assert run(["get_track", f"track_id={track_id}"], tools, output) == 0
    track = json.loads(output.getvalue())
    assert track["title"] == "Piano" and track["url"] == f"https://studio.test/ui/#/tracks/{track_id}"
    assert "request" not in track


def test_rate_limit_reports_retry_after_without_automatic_requests(capsys):
    calls = []
    def answer(request):
        calls.append(request)
        return httpx.Response(429, json={"detail": "요청이 많습니다"}, headers={"Retry-After": "60"})
    tools = StudioTools(httpx.Client(base_url="https://studio.test", transport=httpx.MockTransport(answer)))
    assert run(["studio_credits"], tools, io.StringIO()) == 1
    assert len(calls) == 1 and "60초" in capsys.readouterr().err
