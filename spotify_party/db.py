__all__ = [
    "User",
    "Player",
    "Database",
]

import secrets
from typing import Union, Set


class User:
    def __init__(
        self,
        user_id: str,
        display_name: str,
        access_token: str,
        refresh_token: str,
        expires_at: float,
    ) -> None:
        self.user_id = user_id
        self.display_name = display_name
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.listening_to: Union[str, None] = None
        self.playing_to: Union[str, None] = None
        self.socket = None


class Player:
    def __init__(self, player_id: str, owner: User) -> None:
        owner.playing_to = player_id
        self.player_id = player_id
        self.owner_id = owner.user_id
        self.listeners: Set[str] = set()


class Database:
    def __init__(self):
        self.users = dict()
        self.players = dict()

    def add_user(self, *args, **kwargs) -> User:
        user = User(*args, **kwargs)
        self.users[user.user_id] = user
        return user

    def get_user(self, user_id: str) -> Union[User, None]:
        return self.users.get(user_id, None)

    def add_player(self, owner: User) -> Player:
        if owner.listening_to is not None:
            self.stop_listening(owner.user_id)
        player_id = secrets.token_urlsafe()
        while player_id in self.players:
            player_id = secrets.token_urlsafe()
        player = self.players[player_id] = Player(player_id, owner)
        return player

    def get_player(self, player_id: str) -> Union[Player, None]:
        return self.players.get(player_id, None)

    def stop(self, user_id: str) -> None:
        self.stop_listening(user_id)
        self.stop_playing(user_id)

    def stop_listening(self, user_id: str) -> None:
        user = self.get_user(user_id)
        if user is None or user.listening_to is None:
            return
        player = self.get_player(user.listening_to)
        if player is not None:
            player.listeners.remove(user_id)
        user.listening_to = None

    def stop_playing(self, user_id: str) -> None:
        user = self.get_user(user_id)
        if user is None or user.playing_to is None:
            return
        player = self.get_player(user.playing_to)
        if player is not None:
            for listener in list(player.listeners):
                self.stop_listening(listener)
            self.players.pop(player.player_id)
        user.playing_to = None

    def listen_to(self, user_id: str, player_id: str) -> None:
        self.stop_playing(user_id)
        self.stop_listening(user_id)
        user = self.get_user(user_id)
        player = self.get_player(player_id)
        if user is None or player is None:
            raise ValueError("invalid player_id")
        if player.owner_id == user.user_id:
            raise ValueError("owner can't listen to their own stream")
        user.listening_to = player_id
        player.listeners.add(user_id)
