import hashlib
import json

import httpx
import pytest

from zellygroove_client.mcp_actions_client import CapabilityClient
from zellygroove_client.mcp_server import StudioError, StudioTools


def fixture(operation, responder=None):
    calls = []
    def answer(request):
        calls.append(request)
        if '/mcp/capabilities/' in request.url.path:
            return httpx.Response(200, json=operation)
        if request.url.path == '/api/mcp/confirmations':
            return httpx.Response(200, json={'confirmation': 'a' * 64, 'expires_in': 300})
        return responder(request) if responder else httpx.Response(200, json={'ok': True})
    tools = StudioTools(httpx.Client(base_url='https://studio.test', transport=httpx.MockTransport(answer)))
    return CapabilityClient(tools), calls


def descriptor(**values):
    return {'id': 'delete.scores.score_id', 'path': '/api/scores/{score_id}', 'method': 'DELETE',
            'mode': 'direct', 'confirmation_required': True, 'upload': False,
            'browser_path': '/scores', 'title': '악보 삭제', 'reason': 'same permissions', **values}


def test_destructive_action_prepares_then_submits_only_the_exact_confirmed_request():
    client, calls = fixture(descriptor())
    args = {'path': {'score_id': 's-20261022-000000-abcdef'}}
    prepared = client.action('delete.scores.score_id', args)
    assert prepared['status'] == 'confirmation_required'
    assert all(request.method == 'GET' or request.url.path.endswith('/confirmations') for request in calls)
    assert client.action('delete.scores.score_id', args, prepared['confirmation']) == {'ok': True}
    sent = calls[-1]
    assert sent.method == 'DELETE' and sent.url.path == '/api/scores/s-20261022-000000-abcdef'
    assert sent.headers['x-studio-mcp-confirmation'] == 'a' * 64
    proof = json.loads(next(request.content for request in calls if request.url.path.endswith('/confirmations')))
    assert proof['body_hash'] == hashlib.sha256(sent.content).hexdigest()


def test_human_handoff_does_not_call_the_operation():
    client, calls = fixture(descriptor(id='post.billing.toss.checkout', mode='browser', browser_path='/settings/billing'))
    result = client.action('post.billing.toss.checkout', {})
    assert result['status'] == 'browser_required'
    assert result['url'] == 'https://studio.test/ui/#/settings/billing'
    assert len(calls) == 1


@pytest.mark.parametrize('args', [{'url': 'https://outside.test'}, {'headers': {'authorization': 'stolen'}},
                                  {'path': {'score_id': '../settings/users'}}, {'path': {'score_id': '%2fapi'}},
                                  {'path': {'score_id': 'x'}, 'query': {'a': {'url': 'x'}}}])
def test_invalid_arguments_never_execute(args):
    client, calls = fixture(descriptor())
    with pytest.raises(StudioError):
        client.action('delete.scores.score_id', args)
    assert all('/mcp/capabilities/' in request.url.path for request in calls)


def test_resource_link_is_authenticated_without_returning_file_or_redirect_credentials():
    client, calls = fixture(descriptor(id='get.scores.file', method='GET', path='/api/scores/{score_id}/file',
        mode='resource', confirmation_required=False), lambda request: httpx.Response(307, headers={
            'location': 'https://bucket.test/private?secret=not-for-the-model'}))
    result = client.action('get.scores.file', {'path': {'score_id': 's-123'}})
    assert result['authentication_required'] is True
    assert result['url'] == 'https://studio.test/api/scores/s-123/file'
    assert 'secret' not in json.dumps(result)
    assert len(calls) == 2


def test_role_is_rechecked_and_403_is_not_retried():
    client, calls = fixture(descriptor(id='get.scores', path='/api/scores', method='GET', confirmation_required=False),
                            lambda request: httpx.Response(403, json={'detail': '권한이 변경되었습니다'}))
    with pytest.raises(StudioError, match='권한이 변경'):
        client.action('get.scores', {})
    assert len(calls) == 2


def test_batch_only_accepts_reads_and_reuses_identical_reads_within_one_request():
    client, calls = fixture(descriptor(id='get.scores', path='/api/scores', method='GET', confirmation_required=False))
    asked = [{'operation_id': 'get.scores', 'arguments': {}}] * 2
    result = client.batch(asked)
    assert result['requested'] == 2 and result['executed'] == 1 and result['cache_hits'] == 1
    assert sum(request.url.path == '/api/scores' for request in calls) == 1
    result['results'][0]['result']['ok'] = False
    assert result['results'][1]['result']['ok'] is True
    client.batch(asked)
    assert sum(request.url.path == '/api/scores' for request in calls) == 2
    client, calls = fixture(descriptor())
    with pytest.raises(StudioError):
        client.batch([{'operation_id': 'delete.scores.score_id', 'arguments': {'path': {'score_id': 's-1'}}}])
    assert not any(request.method == 'DELETE' for request in calls)


def test_cli_dispatches_capability_actions_and_mcp_accepts_list_results():
    import asyncio
    from io import StringIO
    from zellygroove_client.connect import run
    from zellygroove_client.mcp_server import build_server
    client, calls = fixture(descriptor(id='get.scores', path='/api/scores', method='GET', confirmation_required=False),
                            lambda request: httpx.Response(200, json=[{'id': 'sc-one'}]))
    out = StringIO()
    assert run(['studio_action', 'operation_id=get.scores'], client.tools, out) == 0
    assert json.loads(out.getvalue()) == [{'id': 'sc-one'}]
    result = asyncio.run(build_server(client.tools).call_tool('studio_action', {'operation_id': 'get.scores'}))
    assert result.is_error is False
    assert 'sc-one' in str(result)


def test_upload_metadata_is_bound_to_receipt_and_never_reads_a_local_path():
    import base64
    client, calls = fixture(descriptor(id='post.score-transcriptions', path='/api/score-transcriptions', method='POST',
                                      upload=True, confirmation_required=False))
    args = {'upload': {'data_base64': base64.b64encode(b'audio').decode(), 'content_type': 'audio/wav'},
            'consent_version': '2026-10-12.1', 'query': {'choice': 'piano'}}
    client.action('post.score-transcriptions', args)
    receipt = json.loads(next(r.content for r in calls if r.url.path.endswith('/confirmations')))
    assert receipt['metadata'] == {'x-score-upload-consent': '2026-10-12.1'}
    assert calls[-1].content == b'audio'
    assert receipt['query'] == calls[-1].url.query.decode()
    with pytest.raises(StudioError):
        client.action('post.score-transcriptions', {'upload': {'path': '/etc/passwd', 'content_type': 'audio/wav'}})


def test_raw_transcription_preserves_json_text_query_and_upload():
    client, calls = fixture(descriptor(id='post.score-transcriptions', method='POST', path='/api/score-transcriptions',
                                      upload=True, confirmation_required=False))
    arrangement = {'preset': 'piano', 'treble': 3, 'bass': 2}
    client.action('post.score-transcriptions', {'query': {'arrangement': json.dumps(arrangement)},
        'upload': {'data_base64': 'YXVkaW8=', 'content_type': 'audio/wav'}, 'consent_version': '2026-10-12.1'})
    assert json.loads(calls[-1].url.params['arrangement']) == arrangement
    assert calls[-1].content == b'audio'
