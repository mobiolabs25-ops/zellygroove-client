"""Small, server-discovered MCP facade. Contains no operator implementation or secrets."""
import base64
from copy import deepcopy
import hashlib
import json
import math
import re
from urllib.parse import quote

import httpx

from .mcp_operation_paths import resolve_path

MAX_UPLOAD = 200 * 1024 * 1024
MAX_JSON = 16 * 1024 * 1024


class CapabilityClient:
    def __init__(self, tools, *, operator=False):
        from .mcp_server import StudioError
        self.tools, self.client, self.operator, self.error = tools, tools.client, operator, StudioError

    def discover(self, query='', group='', offset=0, limit=20, operation_id=None):
        if operation_id is not None:
            if not isinstance(operation_id, str) or not re.fullmatch(r'[a-z0-9_.-]{1,200}', operation_id):
                raise self.error('기능 ID를 확인해 주세요')
            return self.tools._call('GET', '/api/mcp/capabilities/' + operation_id,
                                    params={'operator_surface': self.operator})
        return self.tools._call('GET', '/api/mcp/capabilities', params={
            'query': query, 'group': group, 'offset': offset, 'limit': limit, 'operator_surface': self.operator})

    def _request(self, row, arguments):
        if not isinstance(arguments, dict) or set(arguments) - {'path', 'query', 'body', 'upload', 'consent_version', 'melody_options'}:
            raise self.error('인자는 path, query, body, upload, consent_version, melody_options만 사용할 수 있습니다')
        try:
            path = resolve_path(row, arguments.get('path'))
        except ValueError as error:
            raise self.error(str(error)) from None
        query = arguments.get('query', {})
        if (not isinstance(query, dict) or len(query) > 50 or any(not isinstance(k, str) or len(k) > 100
                or type(v) not in (str, int, float, bool, type(None)) or isinstance(v, float) and not math.isfinite(v) for k, v in query.items())):
            raise self.error('조회 인자는 단순한 이름과 값으로 지정해 주세요')
        method = row.get('method')
        if method not in ('GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'):
            raise self.error('지원하지 않는 기능 메서드입니다')
        if method in ('GET', 'HEAD') and set(arguments) & {'body', 'upload', 'consent_version', 'melody_options'}:
            raise self.error('조회 요청에 변경 본문이나 파일을 넣을 수 없습니다')
        headers = {'X-Studio-MCP-Operation': row['id']}
        content = None
        if 'upload' in arguments:
            upload = arguments['upload']
            if not row.get('upload') or 'body' in arguments or not isinstance(upload, dict) or set(upload) != {'data_base64', 'content_type'}:
                raise self.error('이 기능의 파일 입력 형식을 확인해 주세요')
            encoded, kind = upload['data_base64'], upload['content_type']
            if not isinstance(encoded, str) or len(encoded) > (MAX_UPLOAD + 2) // 3 * 4 or not isinstance(kind, str) or not re.fullmatch(r'[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+', kind):
                raise self.error('파일은 200 MiB 이하의 base64와 올바른 content_type이 필요합니다')
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, UnicodeError):
                raise self.error('파일의 base64 형식이 올바르지 않습니다') from None
            if not content or len(content) > MAX_UPLOAD:
                raise self.error('파일 크기를 확인해 주세요')
            headers['content-type'] = kind
        elif 'body' in arguments:
            if not isinstance(arguments['body'], dict):
                raise self.error('본문은 JSON 객체여야 합니다')
            try:
                content = json.dumps(arguments['body'], ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
            except (ValueError, TypeError, RecursionError):
                raise self.error('본문을 JSON으로 표현할 수 없습니다') from None
            if len(content) > MAX_JSON:
                raise self.error('JSON 본문은 16 MiB까지입니다')
            headers['content-type'] = 'application/json'
        elif method not in ('GET', 'HEAD') and not row.get('upload'):
            # Several existing no-option actions depend on the shared JSON-body
            # parser. The empty object works for them and bodyless handlers alike.
            content = b'{}'
            headers['content-type'] = 'application/json'
        consent = arguments.get('consent_version')
        if consent is not None:
            if not isinstance(consent, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', consent):
                raise self.error('파일 사용 동의 버전을 확인해 주세요')
            headers['X-Score-Upload-Consent'] = consent
        if 'melody_options' in arguments:
            options = arguments['melody_options']
            if row['path'] != '/api/jobs/from-audio' or not isinstance(options, dict) or any(not isinstance(v, str) for v in options.values()):
                raise self.error('멜로디 기반 노래 설정을 확인해 주세요')
            headers['X-Melody-Options'] = quote(json.dumps(options, ensure_ascii=False, separators=(',', ':')))
            if len(headers['X-Melody-Options']) > 16000:
                raise self.error('멜로디 기반 노래 설정이 너무 깁니다')
        request = self.client.build_request(method, path, params={k: v for k, v in query.items() if v is not None},
                                            content=content, headers=headers)
        if len(request.url.query) > 8192:
            raise self.error('조회 인자가 너무 깁니다')
        return request

    def _result(self, response):
        try:
            data = response.json()
        except ValueError:
            data = None
        if response.is_success:
            if response.status_code == 204:
                return {'ok': True}
            if data is None:
                raise self.error('JSON 응답이 아닙니다. 파일 조회 기능의 주소를 사용해 주세요')
            return data
        detail = data.get('detail') if isinstance(data, dict) else None
        if isinstance(data, dict) and isinstance(data.get('errors'), dict):
            detail = '; '.join(f'{key}: {value}' for key, value in data['errors'].items())
        message = str(detail or f'스튜디오가 요청을 거절했습니다 ({response.status_code})')
        after = response.headers.get('Retry-After', '')
        if response.status_code == 429 and after.isdigit() and len(after) <= 6:
            message += f' {after}초 뒤에 다시 조회하세요. 자동 재시도하지 않습니다.'
        raise self.error(message, status_code=response.status_code)

    def _execute(self, row, arguments, confirmation=None):
        if row.get('mode') == 'browser':
            target = row.get('browser_path', '')
            if not isinstance(target, str) or not target.startswith('/') or target.startswith('//'):
                raise self.error('화면 연결 주소를 확인할 수 없습니다')
            return {'status': 'browser_required', 'operation_id': row['id'], 'reason': row['reason'],
                    'url': str(self.client.base_url).rstrip('/') + '/ui/#' + target}
        if row.get('mode') not in ('direct', 'resource'):
            raise self.error('이 기능은 MCP 실행 대상이 아닙니다')
        request = self._request(row, arguments)
        if request.method not in ('GET', 'HEAD'):
            if confirmation is None:
                receipt = self.tools._call('POST', '/api/mcp/confirmations', {
                    'operation_id': row['id'], 'path': arguments.get('path', {}), 'query': request.url.query.decode(),
                    'content_type': request.headers.get('content-type', ''),
                    'body_hash': hashlib.sha256(request.content).hexdigest(), 'operator_surface': self.operator,
                    'metadata': {key: request.headers[key] for key in ('x-score-upload-consent', 'x-melody-options') if key in request.headers}})
                confirmation = receipt['confirmation']
                if row.get('confirmation_required'):
                    summary = deepcopy(arguments)
                    if 'upload' in summary:
                        summary['upload'] = {'content_type': summary['upload']['content_type'], 'bytes': len(request.content)}
                    return {'status': 'confirmation_required', 'operation_id': row['id'], 'title': row['title'],
                            'arguments': summary, **receipt,
                            'instruction': '사용자가 이 변경을 확인한 후 같은 인자와 confirmation으로 한 번 실행하세요.'}
            if not isinstance(confirmation, str) or not re.fullmatch('[a-f0-9]{64}', confirmation):
                raise self.error('변경 확인 값을 확인해 주세요')
            request.headers['X-Studio-MCP-Confirmation'] = confirmation
        try:
            if row['mode'] == 'resource':
                response = self.client.send(request, stream=True, follow_redirects=False)
                try:
                    if not response.is_success and not response.is_redirect:
                        response.read()
                        return self._result(response)
                    return {'url': str(request.url), 'authentication_required': True,
                            'operation_id': row['id'], 'note': '같은 계정의 인증으로 열어야 합니다. URL에 토큰을 붙이지 마세요.'}
                finally:
                    response.close()
            response = self.client.send(request, follow_redirects=False)
            return self._result(response)
        except httpx.TransportError as error:
            raise self.error('스튜디오 연결에 실패했습니다. 변경 결과가 불명확하면 상태부터 조회하세요. 자동 재시도하지 않습니다.') from error

    def action(self, operation_id, arguments=None, confirmation=None):
        row = self.discover(operation_id=operation_id)
        if row.get('id') != operation_id:
            raise self.error('기능 응답이 요청과 일치하지 않습니다')
        return self._execute(row, {} if arguments is None else arguments, confirmation)

    def batch(self, calls):
        if not isinstance(calls, list) or not 1 <= len(calls) <= 8:
            raise self.error('조회 배치는 1~8개입니다')
        rows, checked = {}, []
        for call in calls:
            if not isinstance(call, dict) or set(call) - {'operation_id', 'arguments'} or 'operation_id' not in call:
                raise self.error('배치 항목의 형식을 확인해 주세요')
            identity, arguments = call['operation_id'], call.get('arguments', {})
            if not isinstance(identity, str):
                raise self.error('기능 ID를 확인해 주세요')
            if identity not in rows:
                rows[identity] = self.discover(operation_id=identity)
            row = rows[identity]
            if row.get('id') != identity or row.get('method') != 'GET' or row.get('mode') != 'direct':
                raise self.error('배치는 JSON 조회 기능만 사용할 수 있습니다')
            self._request(row, arguments)  # Validate the whole batch before executing any read.
            checked.append((row, arguments))
        cache, results = {}, []
        for row, arguments in checked:
            key = json.dumps([row['id'], arguments], sort_keys=True, ensure_ascii=True, allow_nan=False)
            if key not in cache:
                cache[key] = self._execute(row, arguments)
            results.append({'operation_id': row['id'], 'result': deepcopy(cache[key])})
        return {'results': results, 'requested': len(calls), 'executed': len(cache), 'cache_hits': len(calls) - len(cache)}
