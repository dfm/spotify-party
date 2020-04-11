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
    Optional,
    Union,
)

from aiohttp import ClientResponseError, web
from aiohttp_spotify import SpotifyAuth

from .auth import call_api, update_auth

if TYPE_CHECKING:
    from . import db

DEFAULT_RETRIES = 3


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

    async def __aenter__(self) -> None:
        pass

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.update()

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

    async def update(self) -> None:
        await self.database.update(self)

    async def update_auth(self, request: web.Request) -> None:
        changed, auth = await update_auth(request, self.auth)
        self.auth = auth
        # if changed:
        #     await self.database.update_auth(self, auth)
        #     self.auth = auth

    async def set_device_id(self, device_id: str) -> None:
        # await self.database.set_device_id(self.user_id, device_id)
        self.device_id = device_id

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

    async def stop(self, request: web.Request) -> bool:
        """Like pause, but update the database too"""
        room = await self.playing_to
        if room is None:
            flag = await self.pause(request)
        else:
            flag = await room.stop(request)

        # await self.database.stop(self.user_id)

        return flag

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
    ) -> Union[Mapping[str, Any], None]:
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

        return data

    async def listen_to(
        self,
        request: web.Request,
        room: "Room",
        device_id: str,
        *,
        retries: int = DEFAULT_RETRIES,
    ) -> Union[Mapping[str, Any], None]:
        await self.set_device_id(device_id)

        await self.stop(request)

        # await self.database.listen_to(self.user_id, room.room_id)
        self.listening_to_id = room.room_id
        self.paused = False

        return await self.sync(request, retries=retries)

    async def play_to(
        self, request: web.Request, device_id: str, *, room_name: str
    ) -> Optional[str]:
        await self.set_device_id(device_id)

        await self.stop(request)

        # await self.transfer(request)
        flag = await self.play(request, {})
        if not flag:
            return None

        room_id = f"{self.user_id}/{room_name}"
        # await self.database.add_room(self, room_id)

        self.listening_to_id = None
        self.playing_to_id = room_id
        self.paused = False

        return room_id


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
        success = True
        for user in await self.listeners:
            if user is None or user.paused:
                continue
            flag = await user.pause(request)
            if not flag:
                success = False
        return success

    async def stop(self, request: web.Request) -> bool:
        if self.room_id is None:
            return False
        success = await self.host.pause(request)
        success = success and await self.pause(request)
        await self.host.database.close_room(self.room_id)
        return success
