"""Client-safe path validation shared with the server's audited capability catalogue."""
import re
from urllib.parse import quote

PARAMETER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)(?::[^}]+)?\}')


def resolve_path(row, parameters=None):
    template = row.get('path', '')
    if not isinstance(template, str) or not template.startswith('/api/') or any(c in template for c in ('?', '#', '\\', '%', '\r', '\n')):
        raise ValueError('올바르지 않은 기능 주소입니다')
    parameters = {} if parameters is None else parameters
    names = set(PARAMETER.findall(template))
    if not isinstance(parameters, dict) or set(parameters) != names:
        raise ValueError('경로 인자를 확인해 주세요')
    values = {}
    for name, value in parameters.items():
        if type(value) not in (str, int):
            raise ValueError('경로 인자는 문자열 또는 정수여야 합니다')
        value = str(value)
        if (not value or len(value) > 300 or value in ('.', '..')
                or any(char in value for char in '/\\%?#') or any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise ValueError('경로 인자에 사용할 수 없는 값입니다')
        values[name] = quote(value, safe='')
    path = PARAMETER.sub(lambda match: values[match[1]], template)
    if any(part in ('.', '..') for part in path.split('/')) or '{' in path or '}' in path:
        raise ValueError('올바르지 않은 기능 주소입니다')
    return path
