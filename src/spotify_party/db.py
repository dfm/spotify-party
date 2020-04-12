__all__ = ["create_tables", "Database"]

import pathlib
import sqlite3
from typing import Iterable, List, Union

import aiosqlite
import pkg_resources
from aiohttp_spotify import SpotifyAuth

from .data_model import Room, User


def create_tables(filename: Union[str, pathlib.Path]) -> None:
    with open(
        pkg_resources.resource_filename(__name__, "schema.sql"), "r"
    ) as f:
        schema = f.read()
    with sqlite3.connect(filename) as connection:
        connection.executescript(schema)


class Database:
    def __init__(self, filename: Union[str, pathlib.Path]):
        self.filename = filename

    async def update(self, user: User) -> None:
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                """UPDATE users SET
                    display_name=?,
                    access_token=?,
                    refresh_token=?,
                    expires_at=?,
                    listening_to=?,
                    playing_to=?,
                    paused=?,
                    device_id=?
                WHERE user_id=?""",
                (
                    user.display_name,
                    user.auth.access_token,
                    user.auth.refresh_token,
                    user.auth.expires_at,
                    user.listening_to_id,
                    user.playing_to_id,
                    int(user.paused),
                    user.device_id,
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

    async def get_room(self, room_id: Union[str, None]) -> Union[Room, None]:
        if room_id is None:
            return None
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                "SELECT * FROM users WHERE playing_to=?", (room_id,)
            ) as cursor:
                return Room.from_row(self, await cursor.fetchone())

    async def add_room(self, host: User, room_id: str) -> str:
        async with aiosqlite.connect(self.filename) as conn:
            await conn.execute(
                "UPDATE users SET playing_to=?, paused=0 WHERE user_id=?",
                (room_id, host.user_id),
            )
            await conn.commit()
        return room_id

    async def get_all_rooms(self) -> Iterable:
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                """
                SELECT DISTINCT
                    playing_to
                FROM users
                WHERE
                    playing_to IS NOT NULL
                    AND paused=0
                """
            ) as cursor:
                return await cursor.fetchall()

    async def get_listeners(
        self, room_id: Union[str, None]
    ) -> List[Union[User, None]]:
        if room_id is None:
            return []
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                "SELECT * FROM users WHERE listening_to=? AND paused=0",
                (room_id,),
            ) as cursor:
                return [User.from_row(self, row) async for row in cursor]

    async def get_room_stats(self) -> Iterable:
        async with aiosqlite.connect(self.filename) as conn:
            async with conn.execute(
                """
                SELECT
                    main.user_id,
                    main.display_name,
                    main.playing_to,
                    count(other.user_id)
                FROM users AS main
                LEFT JOIN users AS other ON
                    main.playing_to = other.listening_to
                WHERE
                    main.playing_to IS NOT NULL
                    AND main.paused=0
                """
            ) as cursor:
                return await cursor.fetchall()
