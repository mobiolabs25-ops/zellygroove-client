import asyncio
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from zellygroove_client.artist_mcp import ArtistMCP, build_artist_server
from zellygroove_client.mcp_server import StudioError, StudioTools
from zellygroove_client import connect, setup


ARTIST = 'ines_vauclair'
ROOM = str(uuid4())
TOOLS = {'open_artist_conversation', 'read_artist_conversation', 'artist_tool',
         'save_artist_reply', 'create_conversation_song', 'save_artist_memory',
         'list_artist_memories', 'update_artist_memory', 'delete_artist_memory'}


def surface(handler):
    return ArtistMCP(StudioTools(httpx.Client(base_url='https://studio.invalid',
        headers={'Authorization': 'Bearer test-only-credential'},
        transport=httpx.MockTransport(handler))), ARTIST)


def test_public_artist_stdio_exposes_only_scoped_tools():
    async def check():
        params = StdioServerParameters(command=sys.executable,
            args=['-m', 'zellygroove_client.mcp_server'],
            env={'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src'),
                 'STUDIO_URL': 'https://studio.invalid', 'STUDIO_TOKEN': 'test-only-credential',
                 'STUDIO_ARTIST_ID': ARTIST})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                initialized = await client.initialize()
                assert initialized.server_info.name == 'zelly-artist'
                assert {t.name for t in (await client.list_tools()).tools} == TOOLS
    asyncio.run(check())


def test_history_protocol_uses_pat_fixed_artist_and_revision():
    requests = []
    request_id = str(uuid4())
    def answer(request):
        requests.append(request)
        assert request.headers['Authorization'] == 'Bearer test-only-credential'
        return httpx.Response(200, json={'id': ROOM, 'conversation_artist_id': ARTIST})
    client = surface(answer)
    client.open_artist_conversation(request_id)
    assert json.loads(requests[-1].content) == {'id': request_id,
        'conversation_artist_id': ARTIST, 'model_source': 'external', 'parent_session_id': None}
    client.read_artist_conversation(ROOM)
    assert requests[-1].url.path == f'/api/song-agent/sessions/{ROOM}/context'
    client.save_artist_reply(ROOM, request_id, 2, '안녕', {'message': 'Bonsoir'}, 'codex')
    assert json.loads(requests[-1].content) == {'request_id': request_id, 'expected_turn': 2,
        'message': '안녕', 'answer': {'message': 'Bonsoir'}, 'client': 'codex'}
    client.create_conversation_song(ROOM, 3)
    assert json.loads(requests[-1].content) == {'draft_revision': 3}


def test_other_artist_room_is_rejected_before_write():
    requests = []
    def answer(request):
        requests.append(request)
        return httpx.Response(200, json={'conversation_artist_id': 'nora_whitlock'})
    with pytest.raises(StudioError, match='연결된 아티스트'):
        surface(answer).save_artist_reply(ROOM, str(uuid4()), 0, '안녕', {}, 'codex')
    assert len(requests) == 1 and requests[0].method == 'GET'


@pytest.mark.parametrize('status, detail', [(401, '로그인 필요'), (403, 'Groovy Pro 필요'),
    (409, '대화가 변경됨'), (429, '쓰기 한도')])
def test_refusal_is_preserved_without_retry_or_credentials_fallback(status, detail):
    calls = []
    def answer(request):
        calls.append(request)
        return httpx.Response(status, json={'detail': detail}, headers={'Retry-After': '60'})
    with pytest.raises(StudioError, match=detail):
        surface(answer).open_artist_conversation(str(uuid4()))
    assert len(calls) == 1


@pytest.mark.parametrize('identity', ['../settings', 'x/y', 'x?y', 'x#y', ''])
def test_invalid_artist_never_reaches_api(identity):
    with pytest.raises(StudioError):
        build_artist_server(None, identity)


def test_invalid_room_or_memory_never_reaches_api():
    client = surface(lambda _: pytest.fail('unexpected API request'))
    with pytest.raises(StudioError):
        client.read_artist_conversation('../settings')
    with pytest.raises(StudioError):
        client.delete_artist_memory('../settings', 1)


def test_artist_cli_cannot_call_general_generation(monkeypatch, capsys):
    monkeypatch.setenv('STUDIO_ARTIST_ID', ARTIST)
    tools = StudioTools(httpx.Client(transport=httpx.MockTransport(lambda _: pytest.fail('API called'))))
    out = io.StringIO()
    assert connect.run(['tools'], tools, out) == 0
    assert 'open_artist_conversation' in out.getvalue()
    assert 'create_song(' not in out.getvalue()
    assert connect.run(['create_song', 'artist_id=nora_whitlock'], tools) == 1
    assert '없는 도구' in capsys.readouterr().err


def test_setup_artist_preserves_general_connection_and_uses_token_file(monkeypatch, tmp_path):
    monkeypatch.setattr(setup.shutil, 'which', lambda name: f'/usr/bin/{name}')
    monkeypatch.setattr(connect, 'install_skill', lambda _: tmp_path / 'SKILL.md')
    monkeypatch.setenv('STUDIO_URL', 'https://zellygroove.com')
    monkeypatch.setenv('STUDIO_TOKEN_FILE', str(tmp_path / 'token.json'))
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=1 if 'get' in args else 0)
    monkeypatch.setattr(setup.subprocess, 'run', run)
    assert setup.setup(['--client', 'codex', '--artist', ARTIST]) == 0
    assert calls[0][-1] == f'zellygroove_{ARTIST}'
    assert calls[-1][:4] == ['/usr/bin/codex', 'mcp', 'add', f'zellygroove_{ARTIST}']
    assert f'STUDIO_ARTIST_ID={ARTIST}' in calls[-1]
    assert f'STUDIO_TOKEN_FILE={tmp_path / "token.json"}' in calls[-1]
    assert all('remove' not in args for args in calls)
