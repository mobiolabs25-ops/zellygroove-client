import pytest

from zellygroove_client.wiki_control_client import WikiControlClient


def test_fixed_paths_and_queued_result_is_not_promoted_to_success():
    calls = []

    def call(method, path, body=None):
        calls.append((method, path, body))
        return {"status": "queued", "id": "command_123"}

    client = WikiControlClient(call)
    assert client.list_tabs("ines") == {"status": "queued", "id": "command_123"}
    assert client.send("ines", {"type": "reset"}, "tab_123456", "command_123") == {"status": "queued", "id": "command_123"}
    assert client.status("ines", "command_123") == {"status": "queued", "id": "command_123"}
    assert calls == [
        ("GET", "/api/musician-wiki/control/artists/ines/tabs", None),
        ("POST", "/api/musician-wiki/control/send", {"artist_id": "ines", "command": {"type": "reset"}, "tab_id": "tab_123456", "command_id": "command_123"}),
        ("GET", "/api/musician-wiki/control/artists/ines/commands/command_123", None),
    ]


@pytest.mark.parametrize("artist", ["../other", "a/b", "", "한글", "x" * 161])
def test_invalid_artist_cannot_change_path(artist):
    client = WikiControlClient(lambda *args: None)
    with pytest.raises(ValueError):
        client.list_tabs(artist)


@pytest.mark.parametrize("identifier", ["../tabs", "a/b", "", "x" * 101])
def test_invalid_target_and_command_ids_cannot_change_path(identifier):
    client = WikiControlClient(lambda *args: None)
    with pytest.raises(ValueError):
        client.status("ines", identifier)
    with pytest.raises(ValueError):
        client.send("ines", {"type": "reset"}, identifier)


def test_cli_dispatches_wiki_commands_and_mcp_exposes_same_contract():
    import asyncio
    import io
    import json
    import httpx
    from zellygroove_client.connect import run
    from zellygroove_client.mcp_server import StudioTools, build_server
    calls = []
    def answer(request):
        calls.append(request)
        return httpx.Response(200, json={'status': 'queued', 'id': 'command_123'})
    tools = StudioTools(httpx.Client(base_url='https://studio.test', transport=httpx.MockTransport(answer)))
    out = io.StringIO()
    assert run(['send_musician_wiki_command', 'artist_id=ines', 'command={"type":"reset"}',
                'command_id=command_123'], tools, out) == 0
    assert json.loads(out.getvalue())['status'] == 'queued'
    assert json.loads(calls[-1].content)['command'] == {'type': 'reset'}
    result = asyncio.run(build_server(tools).call_tool('list_musician_wiki_tabs', {'artist_id': 'ines'}))
    assert not result.is_error
    assert calls[-1].url.path == '/api/musician-wiki/control/artists/ines/tabs'
