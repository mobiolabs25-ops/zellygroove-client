"""Credentials stay on the user's computer and are bound to the selected service."""
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .mcp_server import DEFAULT_URL, StudioError
from .words import chosen, language, learn, say


def service_url() -> str:
    value = os.environ.get("STUDIO_URL", DEFAULT_URL).strip().rstrip("/")
    parsed = urlsplit(value)
    local = parsed.hostname in ("localhost", "127.0.0.1", "::1")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise StudioError(say("STUDIO_URL에는 인증 정보, 쿼리 또는 #을 넣지 마세요.", "Do not put credentials, a query or # in STUDIO_URL."))
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise StudioError(say("서비스 주소는 HTTPS여야 합니다. 로컬 개발 주소만 HTTP를 허용합니다.", "The service address must be HTTPS. Only a local development address may use HTTP."))
    return value


def token_path() -> Path:
    return Path(os.environ.get("STUDIO_TOKEN_FILE", "~/.config/zellygroove/token.json")).expanduser()


def saved_token(url: str) -> str:
    explicit = os.environ.get("STUDIO_TOKEN", "").strip()
    if explicit:
        return explicit
    path = token_path()
    if not path.exists():
        return ""
    try:
        info = path.stat()
        if os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.getuid()):
            raise StudioError(say("토큰 파일은 본인 소유의 0600 권한이어야 합니다.", "The token file must be yours with 0600 permissions."))
        if info.st_size > 16384:
            raise ValueError("oversized credentials")
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored.get("studio_url") != url:
            raise StudioError(say("저장된 토큰의 서비스 주소와 STUDIO_URL이 다릅니다. 해당 서비스에 다시 login 하세요.", "The saved token is for another service than STUDIO_URL. Run login again for that service."))
        token = stored.get("token")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("missing token")
        learn(stored.get("lang"))   # the account's language, as last heard
        return token.strip()
    except (OSError, ValueError, AttributeError) as error:
        raise StudioError(say("토큰 파일을 읽을 수 없습니다. login으로 다시 저장하세요.", "The token file cannot be read. Save it again with login.")) from error


def client_from_env(*, require_token: bool = True) -> httpx.Client:
    url = service_url()
    # Offline help and setup never read credentials.
    token = saved_token(url) if require_token else ""
    if require_token and not token:
        raise StudioError(say("먼저 터미널에서 zellygroove login을 실행하세요. 설정 → 연결에서 본인 토큰을 발급받습니다.", "First run zellygroove login in your terminal. Get your token under Settings → Connect."))
    return httpx.Client(base_url=url, timeout=httpx.Timeout(10.0, read=400.0), follow_redirects=False,
                        headers={**({"Authorization": f"Bearer {token}"} if token else {}), **asked_language()})


def asked_language() -> dict:
    """STUDIO_LANG, when set, is said to the service: its answers then come in it, whatever the account's language."""
    return {"X-Studio-Lang": chosen()} if chosen() else {}


def login() -> int:
    url = service_url()
    if not sys.stdin.isatty():
        raise StudioError(say("login은 본인 터미널에서 실행하세요. 토큰은 채팅이나 명령 인자로 보내지 마세요.", "Run login in your own terminal. Never send the token in a chat or as a command argument."))
    print(say(f"{url}/ui/#/settings/connect 에서 본인 토큰을 발급받으세요.", f"Get your token at {url}/en/#/settings/connect"))
    token = getpass.getpass(say("접근 토큰 (표시되지 않음): ", "Access token (hidden): ")).strip()
    if not token or "\n" in token or "\r" in token:
        raise StudioError(say("올바른 접근 토큰이 필요합니다.", "A valid access token is needed."))
    with httpx.Client(base_url=url, timeout=20, follow_redirects=False,
                      headers={"Authorization": f"Bearer {token}", **asked_language()}) as client:
        from .mcp_server import StudioTools
        StudioTools(client)._call("GET", "/api/settings/account")
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            json.dump({"studio_url": url, "token": token, "lang": language()}, stream)
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(say("연결 확인 완료. 토큰을 본인 컴퓨터에 저장했습니다.", "Connected. The token is saved on this computer."))
    return 0
