__all__ = ["sio"]

from typing import Any, Mapping

import aiohttp_session
import socketio

sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")


@sio.event
async def connect(sid: str, environ: Mapping[str, Any]) -> bool:
    # Check that this user is authenticated
    request = environ["aiohttp.request"]
    session = await aiohttp_session.get_session(request)
    user = await request.config_dict["db"].get_user(session.get("sp_user_id"))
    if user is None:
        return False

    # Re-join the correct room if this is a re-connect
    if user.listening_to_id is not None:
        sio.enter_room(sid, user.listening_to_id)
    elif user.playing_to_id is not None:
        sio.enter_room(sid, user.playing_to_id)

    return True


@sio.event
async def disconnect(sid: str) -> None:
    request = sio.environ[sid]["aiohttp.request"]
    session = await aiohttp_session.get_session(request)
    user = await request.config_dict["db"].get_user(session.get("sp_user_id"))
    if user is None:
        return
    async with user:
        user.paused = True


@sio.event
async def join(sid: str, room_id: str) -> None:
    sio.enter_room(sid, room_id)


@sio.event
async def leave(sid: str, room_id: str) -> None:
    sio.leave_room(sid, room_id)
