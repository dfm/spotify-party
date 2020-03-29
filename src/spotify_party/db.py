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

    async def unpause_user(self, user_id: Union[str, None]) -> None:
        if user_id is None:
            return
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET paused=0 WHERE user_id=?", (user_id,)
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

    async def stop_listening(self, user_id: Union[str, None]) -> None:
        if user_id is None:
            return
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET listening_to=NULL WHERE user_id=?",
                (user_id,),
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
                "SELECT * FROM users WHERE listening_to=?", (room_id,)
            ) as cursor:
                return [User.from_row(self, row) async for row in cursor]
