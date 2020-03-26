__all__ = [
    "User",
    "Room",
    "Database",
]

import secrets
from typing import Union, Set

from aiohttp_spotify import SpotifyAuth


class User:
    def __init__(self, user_id: str, display_name: str, auth: SpotifyAuth):
        self.user_id = user_id
        self.display_name = display_name
        self.auth = auth
        self.listening_to: Union[str, None] = None
        self.playing_to: Union[str, None] = None
        self.socket = None


class Room:
    def __init__(self, room_id: str, host: User):
        host.playing_to = room_id
        self.room_id = room_id
        self.host_id = host.user_id
        self.listeners: Set[str] = set()


class Database:
    def __init__(self):
        self.users = dict()
        self.rooms = dict()

    def update_auth(self, user_id: str, auth: SpotifyAuth) -> None:
        user = self.get_user(user_id)
        if user is None:
            raise KeyError(user_id)
        user.auth = auth

    def add_user(self, *args, **kwargs) -> User:
        user = User(*args, **kwargs)
        self.users[user.user_id] = user
        return user

    def get_user(self, user_id: str) -> Union[User, None]:
        return self.users.get(user_id, None)

    def add_room(self, host: User) -> Room:
        if host.listening_to is not None:
            self.stop_listening(host.user_id)
        room_id = secrets.token_urlsafe()
        while room_id in self.rooms:
            room_id = secrets.token_urlsafe()
        room = self.rooms[room_id] = Room(room_id, host)
        return room

    def get_room(self, room_id: str) -> Union[Room, None]:
        return self.rooms.get(room_id, None)

    def stop(self, user_id: str) -> None:
        self.stop_listening(user_id)
        self.stop_playing(user_id)

    def stop_listening(self, user_id: str) -> None:
        user = self.get_user(user_id)
        if user is None or user.listening_to is None:
            return
        room = self.get_room(user.listening_to)
        if room is not None:
            room.listeners.remove(user_id)
        user.listening_to = None

    def stop_playing(self, user_id: str) -> None:
        user = self.get_user(user_id)
        if user is None or user.playing_to is None:
            return
        room = self.get_room(user.playing_to)
        if room is not None:
            for listener in list(room.listeners):
                self.stop_listening(listener)
            self.rooms.pop(room.room_id)
        user.playing_to = None

    def listen_to(self, user_id: str, room_id: str) -> None:
        self.stop_playing(user_id)
        self.stop_listening(user_id)
        user = self.get_user(user_id)
        room = self.get_room(room_id)
        if user is None or room is None:
            raise ValueError("invalid room_id")
        if room.host_id == user.user_id:
            raise ValueError("host can't listen to their own stream")
        user.listening_to = room_id
        room.listeners.add(user_id)
