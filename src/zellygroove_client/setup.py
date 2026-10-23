"""Register only this service, preserving all existing agent configuration."""
import argparse
import re
import shutil
import subprocess

from .auth import service_url, token_path
from .mcp_server import StudioError

SOURCE = "git+https://github.com/mobiolabs25-ops/zellygroove-client@v0.3.1"
SERVER_NAME = "zellygroove"


def setup(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="zellygroove setup")
    parser.add_argument("--client", choices=("auto", "claude", "codex", "both"), default="auto")
    parser.add_argument("--artist", help="Artist ID for a separate, fixed-artist conversation connection")
    options = parser.parse_args(argv)
    selected, artist_id = options.client, options.artist
    if artist_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", artist_id):
        raise StudioError("올바른 아티스트 ID가 필요합니다.")
    server_name = f"{SERVER_NAME}_{artist_id}" if artist_id else SERVER_NAME
    clients = [name for name in ("claude", "codex") if shutil.which(name)] if selected == "auto" else (
        ["claude", "codex"] if selected == "both" else [selected])
    if not clients:
        raise StudioError("Claude Code 또는 Codex CLI를 먼저 설치하세요. Desktop 설정은 README를 참고하세요.")
    uvx = shutil.which("uvx")
    if not uvx or any(not shutil.which(name) for name in clients):
        raise StudioError("uvx와 선택한 Claude Code/Codex CLI가 PATH에 있어야 합니다.")
    from .connect import install_skill
    for name in clients:
        executable = shutil.which(name)
        # Do not display get output: an older configuration may contain a literal token.
        aliases = (server_name,) if artist_id else (SERVER_NAME, "mobio-studio", "mobio_studio")
        existing = next((alias for alias in aliases
                         if subprocess.run([executable, "mcp", "get", alias], capture_output=True, timeout=30).returncode == 0), None)
        if existing:
            print(f"{name}: 기존 {existing} 연결을 유지합니다. 변경이 필요하면 해당 항목을 검토하세요.")
        else:
            env_flag = "-e" if name == "claude" else "--env"
            command = [executable, "mcp", "add"]
            if name == "claude":
                command += ["-s", "user"]
            command += [server_name, env_flag, f"STUDIO_URL={service_url()}", env_flag,
                        f"STUDIO_TOKEN_FILE={token_path().absolute()}"]
            if artist_id:
                command += [env_flag, f"STUDIO_ARTIST_ID={artist_id}"]
            command += ["--", uvx, "--python", "3.11", "--from", SOURCE, "zellygroove-mcp"]
            result = subprocess.run(command, capture_output=True, timeout=60)
            if result.returncode:
                raise StudioError(f"{name} MCP 등록에 실패했습니다. 해당 CLI의 mcp add 도움말을 확인하세요.")
            print(f"{name}: {server_name} MCP를 등록했습니다.")
        installed = install_skill(name)
        print(f"{name}: 스킬 설치 완료 ({installed}).")
    print("토큰이 없다면 본인 터미널에서 zellygroove login을 실행한 뒤 에이전트를 다시 시작하세요.")
    return 0
