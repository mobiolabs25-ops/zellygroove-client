"""Exercise the published entry point through real MCP stdio, without API calls."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_handshake_tools_and_skill():
    async def check():
        parameters = StdioServerParameters(command=sys.executable,
            args=["-m", "zellygroove_client.mcp_server"],
            env={"PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                 "STUDIO_URL": "https://studio.invalid", "STUDIO_TOKEN": "test-only-credential"})
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listing = await session.list_tools()
                names = {tool.name for tool in listing.tools}
                assert {"studio_credits", "create_song", "get_job", "retry_job"} <= names
                assert not {"publish_track", "build_site", "import_scene"} & names
                result = await session.call_tool("studio_guide", {})
                assert json.loads(result.content[0].text)["name"] == "zellygroove"
    asyncio.run(check())
