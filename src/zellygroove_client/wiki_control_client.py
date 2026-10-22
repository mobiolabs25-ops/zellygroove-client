"""Small HTTP adapter for the token-side Wiki live-control tools.

The server owns command validation and access checks. This adapter constructs only
fixed local API paths; a queued response is returned as queued, never as success.
"""
import re
from urllib.parse import quote

ARTIST_ID = re.compile(r"^[A-Za-z0-9_-]{1,160}$")
COMMAND_ID = re.compile(r"^[A-Za-z0-9_-]{8,100}$")


class WikiControlClient:
    def __init__(self, call):
        """`call(method, path, body=None)` is StudioTools._call or an equivalent."""
        self.call = call

    @staticmethod
    def _artist(artist_id):
        if not isinstance(artist_id, str) or not ARTIST_ID.fullmatch(artist_id):
            raise ValueError("올바르지 않은 아티스트 ID입니다")
        return quote(artist_id, safe="")

    @staticmethod
    def _id(value):
        if not isinstance(value, str) or not COMMAND_ID.fullmatch(value):
            raise ValueError("올바르지 않은 명령 또는 탭 ID입니다")
        return value

    def list_tabs(self, artist_id):
        artist = self._artist(artist_id)
        return self.call("GET", f"/api/musician-wiki/control/artists/{artist}/tabs")

    def send(self, artist_id, command, tab_id=None, command_id=None):
        self._artist(artist_id)
        if not isinstance(command, dict):
            raise ValueError("Wiki 명령은 객체여야 합니다")
        body = {"artist_id": artist_id, "command": command}
        if tab_id is not None:
            body["tab_id"] = self._id(tab_id)
        if command_id is not None:
            body["command_id"] = self._id(command_id)
        return self.call("POST", "/api/musician-wiki/control/send", body)

    def status(self, artist_id, command_id):
        artist = self._artist(artist_id)
        command = self._id(command_id)
        return self.call("GET", f"/api/musician-wiki/control/artists/{artist}/commands/{command}")
