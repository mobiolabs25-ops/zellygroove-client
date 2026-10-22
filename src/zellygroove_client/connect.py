"""Using the studio from Claude or Codex: what to register, the command-line form of the same tools, and the skill that tells
an agent how the studio is used. One text for all three, kept here beside the tools it describes, and handed out by the
settings page (/api/settings/connect), by the MCP server (studio_guide) and by the command line (zellygroove guide).

    zellygroove                              # the tools, one line each
    zellygroove plan_playlist theme="rain at the harbour" count=3
    zellygroove wait_playlist playlist_id=p-20261005-162058-985f36
    zellygroove guide                        # the skill's text
    zellygroove install-skill claude         # or codex: writes the skill where that agent looks for skills

It talks to the studio at $STUDIO_URL, as whoever $STUDIO_TOKEN is: an access token she made on the studio's settings page."""

import asyncio
import json
import os
import sys
from pathlib import Path

from .mcp_server import StudioError, StudioTools, build_server

SKILL_NAME = "zellygroove"
SKILL_HOMES = {"claude": Path(".claude") / "skills", "codex": Path(".codex") / "skills"}
ALIASES = {"studio_status": "status", "studio_usage": "usage", "studio_credits": "credits", "studio_plans": "plans", "studio_downloads": "downloads",
           "studio_guide": "guide"}   # tool name -> the StudioTools function it calls

CAPABILITY_METHODS = {'studio_capabilities': 'discover', 'studio_action': 'action', 'studio_read_batch': 'batch'}
WIKI_METHODS = {'list_musician_wiki_tabs': 'list_tabs', 'send_musician_wiki_command': 'send',
                'get_musician_wiki_command_status': 'status'}

from importlib.resources import files

GUIDE = files("zellygroove_client").joinpath("SKILL.md").read_text(encoding="utf-8")


def install_skill(agent: str, home: Path | None = None) -> Path:
    """Write the skill where this agent looks for a person's skills. Returns the file written."""
    if agent not in SKILL_HOMES:
        raise StudioError(f"claude 또는 codex 여야 합니다: {agent!r}")
    path = (home or Path.home()) / SKILL_HOMES[agent] / SKILL_NAME / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") != GUIDE:
        raise StudioError(f"기존 스킬 내용이 다릅니다. 덮어쓰기 전에 직접 검토하세요: {path}")
    path.write_text(GUIDE, encoding="utf-8")
    return path


def _value(text: str):
    """A value typed on the command line: JSON when it is JSON (3, true, null, ["a"]), otherwise the text itself."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def run(argv: list[str], tools: StudioTools, out=None, home: Path | None = None) -> int:
    out = out or sys.stdout
    artist_id = os.environ.get("STUDIO_ARTIST_ID", "").strip()
    if artist_id:
        from .artist_mcp import ArtistMCP, build_artist_server
        server, surface = build_artist_server(tools, artist_id), ArtistMCP(tools, artist_id)
    else:
        server, surface = build_server(tools), tools
    listed = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    if not argv or argv[0] in ("tools", "-h", "--help"):
        for name, tool in listed.items():
            asked = ", ".join(f"{key}{'' if key in (tool.input_schema.get('required') or []) else '?'}" for key in tool.input_schema.get("properties") or {})
            print(f"{name}({asked})  {' '.join((tool.description or '').split())[:110]}", file=out)
        print("\nzellygroove login | setup --client auto|claude|codex|both | <tool> key=value | guide | install-skill claude|codex", file=out)
        return 0
    name, rest = argv[0], argv[1:]
    try:
        if name == "guide":
            print(GUIDE, file=out)
            return 0
        if name == "install-skill":
            print(install_skill(rest[0] if rest else "", home), file=out)
            return 0
        if name not in listed:
            raise StudioError(f"없는 도구입니다: {name}. `zellygroove` 로 목록을 보세요")
        if any("=" not in word for word in rest):
            raise StudioError("값은 key=value 로 적습니다. 예: zellygroove plan_playlist theme=\"rain\" count=3")
        asked = {key: _value(value) for key, value in (word.split("=", 1) for word in rest)}
        unknown = set(asked) - set(listed[name].input_schema.get("properties") or {})
        if unknown:
            raise StudioError(f"{name} 에 없는 항목입니다: {', '.join(sorted(unknown))}")
        if name in CAPABILITY_METHODS:
            from .mcp_actions_client import CapabilityClient
            answer = getattr(CapabilityClient(tools, operator=False), CAPABILITY_METHODS[name])(**asked)
        elif name in WIKI_METHODS:
            from .wiki_control_client import WikiControlClient
            answer = getattr(WikiControlClient(tools._call), WIKI_METHODS[name])(**asked)
        else:
            answer = getattr(surface, ALIASES.get(name, name))(**asked)
    except (StudioError, TypeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    print(json.dumps(answer, ensure_ascii=False, indent=2), file=out)
    return 0


def main() -> int:
    from .auth import client_from_env
    from . import __version__
    args = sys.argv[1:]
    if args and args[0] in ("login", "setup"):
        try:
            if args[0] == "login":
                from .auth import login
                return login()
            from .setup import setup
            return setup(args[1:])
        except (StudioError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
    if args == ["--version"]:
        print(__version__)
        return 0
    offline = not args or args[0] in ("tools", "-h", "--help", "guide", "install-skill", "studio_guide")
    try:
        with client_from_env(require_token=not offline) as client:
            return run(args, StudioTools(client))
    except StudioError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
