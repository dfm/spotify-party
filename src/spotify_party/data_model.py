__all__ = ["User", "Room"]

import asyncio
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    NamedTuple,
    Optional,
    Union,
)

from aiohttp import ClientResponseError, web
from aiohttp_spotify import SpotifyAuth

from .auth import call_api, update_auth
from .socket import sio

if TYPE_CHECKING:
    from . import db

DEFAULT_RETRIES = 3


class UserData(NamedTuple):
    user_id: str
    display_name: str
    access_token: str
    refresh_token: str
    expires_at: int
    listening_to_id: Optional[str]
    playing_to_id: Optional[str]
    paused: bool
    device_id: Optional[str]


class User:
    def __init__(
        self,
        database: "db.Database",
        user_id: str,
        display_name: str,
        access_token: str,
        refresh_token: str,
        expires_at: int,
        listening_to: Union[str, None],
        playing_to: Union[str, None],
        paused: int,
        device_id: Union[str, None],
    ):
        self.database = database
        self.user_id = user_id
        self.display_name = display_name
        self.auth = SpotifyAuth(access_token, refresh_token, expires_at)
        self.listening_to_id = listening_to
        self.playing_to_id = playing_to
        self.paused = bool(paused)
        self.device_id = device_id

        self._context_data: Optional[UserData] = None

    async def __aenter__(self) -> None:
        self._context_data = self.data

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        old_data = self._context_data
        new_data = self.data

        if old_data is None or new_data is None:
            raise ValueError("User updated outside a context")

        # The broadcast room changed
        if new_data.playing_to_id != old_data.playing_to_id:
            if old_data.playing_to_id is not None:
                await sio.emit("pause", room=old_data.playing_to_id)

        # The room is the same, but the playing state changed
        elif (
            old_data.paused != new_data.paused
            and new_data.playing_to_id is not None
        ):
            if new_data.paused:
                await sio.emit("pause", room=new_data.playing_to_id)
            else:
                await sio.emit("unpause", room=new_data.playing_to_id)

        # The user was previously listening
        if new_data.listening_to_id != old_data.listening_to_id:
            await self._send_listeners_to_room(old_data.listening_to_id, -1)
            await self._send_listeners_to_room(new_data.listening_to_id, 1)

        elif (
            old_data.paused != new_data.paused
            and new_data.listening_to_id is not None
        ):
            if new_data.paused:
                await self._send_listeners_to_room(
                    new_data.listening_to_id, -1
                )
            else:
                await self._send_listeners_to_room(new_data.listening_to_id, 1)

        if self.data != self._context_data:
            await self.update()

        self._context_data = None

    async def _send_listeners_to_room(
        self, room_id: Optional[str], delta: int = 0
    ) -> None:
        if room_id is None:
            return
        listeners = await self.database.get_listeners(room_id)
        await sio.emit(
            "listeners",
            {"number": max(len(listeners) + delta, 0)},
            room=room_id,
        )

    @property
    def data(self):
        return UserData(
            self.user_id,
            self.display_name,
            self.auth.access_token,
            self.auth.refresh_token,
            self.auth.expires_at,
            self.listening_to_id,
            self.playing_to_id,
            self.paused,
            self.device_id,
        )

    async def update(self) -> None:
        await self.database.update(self)

    @classmethod
    def from_row(
        cls, database: "db.Database", row: Union[Iterable, None]
    ) -> Union["User", None]:
        if row is None:
            return None
        return cls(database, *row)

    @property
    async def listening_to(self) -> Union["Room", None]:
        return await self.database.get_room(self.listening_to_id)

    @property
    async def playing_to(self) -> Union["Room", None]:
        return await self.database.get_room(self.playing_to_id)

    async def update_auth(self, request: web.Request) -> None:
        changed, auth = await update_auth(request, self.auth)
        if changed:
            self.auth = auth

    async def transfer(
        self, request: web.Request, *, play: bool = False, check: bool = True
    ) -> bool:
        if self.device_id is None:
            return False

        # No active device: transfer first
        try:
            await call_api(
                request,
                self,
                "/me/player",
                method="PUT",
                json=dict(device_ids=[self.device_id], play=play),
            )
        except ClientResponseError as e:
            print(f"'/me/player' returned {e.status}")
            return False

        if check:
            await asyncio.sleep(1)
            response = await call_api(request, self, "/me/player/devices")
            if response is None:
                return False
            return any(
                device.get("is_active", False)
                and (device.get("id", None) == self.device_id)
                for device in response.json().get("devices", [])
            )

        return True

    async def pause(
        self, request: web.Request, *, retries: int = DEFAULT_RETRIES
    ) -> bool:
        try:
            await call_api(request, self, "/me/player/pause", method="PUT")

        except ClientResponseError as e:
            if e.status not in (403, 404):
                raise
            return False

        return True

    async def play(
        self,
        request: web.Request,
        data: Mapping[str, Any],
        *,
        retries: int = DEFAULT_RETRIES,
    ) -> bool:
        try:
            await call_api(
                request,
                self,
                "/me/player/play",
                method="PUT",
                params=dict(device_id=self.device_id),
                json=data,
            )

        except ClientResponseError as e:
            if e.status not in (403, 404):
                raise

            flag = await self.transfer(request, play=True, check=False)
            if flag and retries > 0:
                await asyncio.sleep(1)
                return await self.play(request, data, retries=retries - 1)

            return False

        return True

    async def currently_playing(
        self, request: web.Request
    ) -> Union[Dict[str, Any], None]:
        if self.paused:
            return None

        response = await call_api(
            request, self, "/me/player/currently-playing"
        )
        if response is None or response.status == 204:
            return None
        data = response.json()
        item = data.get("item", {})
        return {
            "uri": item.get("uri", None),
            "name": item.get("name", None),
            "type": item.get("type", None),
            "id": item.get("id", None),
            "position_ms": data.get("progress_ms", None),
            "is_playing": data.get("is_playing", False),
        }

    async def sync(
        self, request: web.Request, *, retries: int = DEFAULT_RETRIES
    ) -> Union[Dict[str, Any], None]:
        room = await self.listening_to
        if room is None:
            return None

        data = await room.host.currently_playing(request)
        if data is None:
            return None

        if (
            data.pop("is_playing")
            and data["uri"] is not None
            and data["position_ms"] is not None
        ):
            await self.play(
                request,
                dict(uris=[data["uri"]], position_ms=data["position_ms"]),
                retries=retries,
            )
        else:
            await self.pause(request, retries=retries)

        listeners = await room.listeners
        return dict(number=len(listeners), playing=data)


class Room:
    def __init__(self, host: User):
        self.host = host
        self.room_id = host.playing_to_id
        self.host_id = host.user_id

    @classmethod
    def from_row(
        cls, database: "db.Database", row: Union[Iterable, None]
    ) -> Union["Room", None]:
        if row is None:
            return None
        return cls(User(database, *row))

    @property
    async def listeners(self) -> List[Union[User, None]]:
        return await self.host.database.get_listeners(self.room_id)

    async def play(
        self, request: web.Request, uri: str, position_ms: Optional[int] = None
    ) -> bool:
        data: MutableMapping[str, Any] = dict(uris=[uri])
        if position_ms is not None:
            data["position_ms"] = position_ms

        success = True
        for user in await self.listeners:
            if user is None or user.paused:
                continue
            flag = await user.play(request, data)
            if not flag:
                success = False
        return success

    async def pause(self, request: web.Request) -> bool:
        flag = True
        for user in await self.listeners:
            if user is None or user.paused:
                continue
            flag &= await user.pause(request)
        return flag
