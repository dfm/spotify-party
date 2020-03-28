__all__ = ["create_tables", "User", "Room", "Database"]

import pathlib
import secrets
import sqlite3
import pkg_resources
from typing import Union, Iterable

import aiosqlite
from aiohttp_spotify import SpotifyAuth


def create_tables(filename: Union[str, pathlib.Path]) -> None:
    with open(
        pkg_resources.resource_filename(__name__, "schema.sql"), "r"
    ) as f:
        schema = f.read()
    with sqlite3.connect(filename) as connection:
        connection.executescript(schema)


class User:
    def __init__(
        self,
        database: "Database",
        user_id: str,
        display_name: str,
        access_token: str,
        refresh_token: str,
        expires_at: int,
        listening_to: Union[str, None],
        playing_to: Union[str, None],
        paused: int,
    ):
        self.database = database
        self.user_id = user_id
        self.display_name = display_name
        self.auth = SpotifyAuth(access_token, refresh_token, expires_at)
        self.listening_to_id = listening_to
        self.playing_to_id = playing_to
        self.paused = bool(paused)

    @classmethod
    def from_row(
        cls, database: "Database", row: Union[Iterable, None]
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


class Room:
    def __init__(self, host: User):
        self.host = host
        self.room_id = host.playing_to_id
        self.host_id = host.user_id

    @classmethod
    def from_row(
        cls, database: "Database", row: Union[Iterable, None]
    ) -> Union["Room", None]:
        if row is None:
            return None
        return cls(User(database, *row))

    # @property
    # async def host(self) -> Union[User]

    @property
    async def listeners(self) -> Iterable[Union[User, None]]:
        return await self.host.database.get_listeners(self.room_id)


class Database:
    def __init__(self, filename: Union[str, pathlib.Path]):
        self.filename = filename

    async def update_auth(self, user: User, auth: SpotifyAuth) -> None:
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                """UPDATE users SET
                    access_token=?,
                    refresh_token=?,
                    expores_at=?
                WHERE user_id=?""",
                (
                    auth.access_token,
                    auth.refresh_token,
                    auth.expires_at,
                    user.user_id,
                ),
            )
            await conn.commit()

    async def add_user(
        self, user_id: str, display_name: str, auth: SpotifyAuth
    ) -> Union[User, None]:
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                """
                INSERT INTO users(
                    user_id,display_name,access_token,refresh_token,expires_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    access_token=excluded.access_token,
                    refresh_token=excluded.refresh_token,
                    expires_at=excluded.expires_at
                """,
                (
                    user_id,
                    display_name,
                    auth.access_token,
                    auth.refresh_token,
                    auth.expires_at,
                ),
            )
            await conn.commit()
        return await self.get_user(user_id)

    async def get_user(self, user_id: Union[str, None]) -> Union[User, None]:
        if user_id is None:
            return None
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                "SELECT * FROM users WHERE user_id=?", (user_id,)
            ) as cursor:
                return User.from_row(self, await cursor.fetchone())

    async def pause_user(self, user_id: Union[str, None]) -> None:
        if user_id is None:
            return
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET paused=1 WHERE user_id=?", (user_id,)
            )
            await conn.commit()

    async def listen_to(
        self, user_id: Union[str, None], room_id: Union[str, None]
    ) -> None:
        if user_id is None or room_id is None:
            return
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET listening_to=?, paused=0 WHERE user_id=?",
                (room_id, user_id),
            )
            await conn.commit()

    async def get_room(self, room_id: Union[str, None]) -> Union[Room, None]:
        if room_id is None:
            return None
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                "SELECT * FROM users WHERE playing_to=?", (room_id,)
            ) as cursor:
                return Room.from_row(self, await cursor.fetchone())

    async def add_room(self, host: User) -> str:
        room_id = secrets.token_urlsafe()
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET playing_to=?, paused=0 WHERE user_id=?",
                (room_id, host.user_id),
            )
            await conn.commit()
        return room_id

    async def pause_room(self, room_id: str) -> None:
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET paused=1 WHERE playing_to=?", (room_id,),
            )
            await conn.commit()

    async def close_room(self, room_id: str) -> None:
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET playing_to=NULL WHERE playing_to=?",
                (room_id,),
            )
            await conn.execute(
                "UPDATE users SET listening_to=NULL WHERE listening_to=?",
                (room_id,),
            )
            await conn.commit()

    async def get_listeners(
        self, room_id: Union[str, None]
    ) -> Iterable[Union[User, None]]:
        if room_id is None:
            return []
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                "SELECT * FROM users WHERE playing_to=?", (room_id,)
            ) as cursor:
                return list(User.from_row(self, row) for row in cursor)


# class User:
#     def __init__(self, user_id: str, display_name: str, auth: SpotifyAuth):
#         self.user_id = user_id
#         self.display_name = display_name
#         self.auth = auth
#         self.listening_to: Union[str, None] = None
#         self.playing_to: Union[str, None] = None
#         self.socket_id: Union[str, None] = None


# class Room:
#     def __init__(self, room_id: str, host: User):
#         host.playing_to = room_id
#         self.room_id = room_id
#         self.host_id = host.user_id
#         self.listeners: Set[str] = set()
#         self.current_uri: Union[str, None] = None


# class Database:
#     def __init__(self):
#         self.users = dict()
#         self.rooms = dict()

#     def update_auth(self, user_id: str, auth: SpotifyAuth) -> None:
#         user = self.get_user(user_id)
#         if user is None:
#             raise KeyError(user_id)
#         user.auth = auth

#     def add_user(self, *args, **kwargs) -> User:
#         user = User(*args, **kwargs)
#         self.users[user.user_id] = user
#         return user

#     def get_user(self, user_id: Union[str, None]) -> Union[User, None]:
#         if user_id is None:
#             return None
#         return self.users.get(user_id, None)

#     def add_room(self, host: User) -> Room:
#         if host.listening_to is not None:
#             self.stop_listening(host.user_id)
#         room_id = secrets.token_urlsafe()
#         while room_id in self.rooms:
#             room_id = secrets.token_urlsafe()
#         room = self.rooms[room_id] = Room(room_id, host)
#         return room

#     def get_room(self, room_id: Union[str, None]) -> Union[Room, None]:
#         if room_id is None:
#             return None
#         return self.rooms.get(room_id, None)

#     def stop(self, user_id: str) -> None:
#         self.stop_listening(user_id)
#         self.stop_playing(user_id)

#     def stop_listening(self, user_id: str) -> None:
#         user = self.get_user(user_id)
#         if user is None or user.listening_to is None:
#             return
#         room = self.get_room(user.listening_to)
#         if room is not None:
#             room.listeners.remove(user_id)
#         user.listening_to = None

#     def stop_playing(self, user_id: str) -> None:
#         user = self.get_user(user_id)
#         if user is None or user.playing_to is None:
#             return
#         room = self.get_room(user.playing_to)
#         if room is not None:
#             for listener in list(room.listeners):
#                 self.stop_listening(listener)
#             self.rooms.pop(room.room_id)
#         user.playing_to = None

#     def listen_to(self, user_id: str, room_id: str) -> Room:
#         self.stop_playing(user_id)
#         self.stop_listening(user_id)
#         user = self.get_user(user_id)
#         room = self.get_room(room_id)
#         if user is None or room is None:
#             raise ValueError("invalid room_id")
#         if room.host_id == user.user_id:
#             raise ValueError("host can't listen to their own stream")
#         user.listening_to = room_id
#         room.listeners.add(user_id)
#         return room
