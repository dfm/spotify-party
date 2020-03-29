__all__ = ["sio"]

from functools import wraps
from typing import Mapping, Any, Callable, Awaitable

import socketio
import aiohttp_session
from aiohttp import web

from . import db, api


sio = socketio.AsyncServer(async_mode="aiohttp")


#
# Authentication helper
#


def require_user(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
    @wraps(func)
    async def wrapped(sid: str, *args) -> Mapping[str, str]:
        request = sio.environ["aiohttp.request"]
        session = await aiohttp_session.get_session(request)
        user = await request.app["db"].get_user(session.get("sp_user_id"))
        if user is None:
            return {"error": "authentication required"}
        return await func(user, sid, *args)

    return wrapped


#
# Actions
#


async def close_room(room_id: str) -> None:
    request = sio.environ["aiohttp.request"]
    dbc = request.app["db"]

    # Pause playback for all the listeners
    for listener in await dbc.get_listeners(room_id):
        if listener.paused:
            continue
        await api.call_api(request, listener, "/me/player/pause", method="PUT")

    # Update the database
    await dbc.close_room(room_id)

    # Tell the clients about the closing
    await sio.emit("closed", room=room_id)


async def pause_room(room_id: str) -> None:
    request = sio.environ["aiohttp.request"]
    dbc = request.app["db"]

    # Pause playback for all the listeners
    for listener in await dbc.get_listeners(room_id):
        if listener.paused:
            continue
        await api.call_api(request, listener, "/me/player/pause", method="PUT")

    # Update the database
    await dbc.pause_room(room_id)

    # Tell the clients about the closing
    await sio.emit("paused", room=room_id)


async def sync_user(request: web.Request, user: db.User) -> None:
    room = await user.listening_to
    if room is None:
        return

    # Get the host's current state
    response = await api.call_api(
        request, room.host, "/me/player/currently-playing"
    )
    if response is None:
        return
    data = response.json()
    uri = data.get("item", {}).get("uri", None)
    position_ms = data.get("progress_ms", None)
    is_playing = data.get("is_playing", False)

    # Update the user's state
    if is_playing and uri is not None and position_ms is not None:
        await api.call_api(
            request,
            user,
            "/me/player/play",
            method="PUT",
            json=dict(uris=[uri], position_ms=position_ms),
        )


#
# Handle events
#


@sio.event
async def connect(sid: str, environ: Mapping[str, Any]) -> bool:
    # Check that this user is authenticated
    request = environ["aiohttp.request"]
    session = await aiohttp_session.get_session(request)
    user = await request.app["db"].get_user(session.get("sp_user_id"))
    return user is not None


@sio.event
async def disconnect(sid: str) -> None:
    # if user.socket_id == sid:
    #     request = sio.environ["aiohttp.request"]
    #     user.socket_id = None
    #     request.app["db"].stop(user.user_id)
    print("disconnect ", sid)


#
# Host specific events
#


@sio.event
@require_user
async def new_room(
    user: db.User, sid: str, data: Mapping[str, Any]
) -> Mapping[str, str]:
    if user.playing_to_id is not None:
        await close_room(user.playing_to_id)
        await sio.leave_room(sid, user.playing_to_id)
    room_id = await sio.environ["aiohttp.request"].app["db"].add_room(user)
    await sio.enter_room(sid, room_id)
    return {"room_id": room_id}


@sio.event
@require_user
async def play(
    user: db.User, sid: str, data: Mapping[str, str]
) -> Mapping[str, str]:
    device_id = data.get("device_id", None)
    if device_id is None:
        return {"error": "Missing device_id"}

    # Transfer playback
    request = sio.environ["aiohttp.request"]
    await api.call_api(
        request,
        user,
        "/me/player",
        method="PUT",
        json=dict(device_ids=[device_id]),
    )

    # Create a new URL if required
    room_id = user.playing_to_id
    if room_id is None:
        room_id = await request.app["db"].add_room(user)
        await sio.enter_room(sid, room_id)

    return {"room_id": room_id}


@sio.event
@require_user
async def close(
    user: db.User, sid: str, data: Mapping[str, str]
) -> Mapping[str, str]:
    if user.playing_to_id is not None:
        await close_room(user.playing_to_id)
        await sio.leave_room(sid, user.playing_to_id)
    return {}


#
# General events
#


@sio.event
@require_user
async def pause(user: db.User, sid: str) -> Mapping[str, str]:
    room_id = user.playing_to_id
    if room_id is not None:
        await sio.emit("paused", room=room_id)
    await sio.environ["aiohttp.request"].app["db"].pause_user(user.user_id)
    return {}


#
# Listener events
#


@sio.event
@require_user
async def listen(
    user: db.User, sid: str, data: Mapping[str, Any]
) -> Mapping[str, str]:
    request = sio.environ["aiohttp.request"]
    room = await request.app["db"].get_room(data.get("room_id", None))
    if room is None:
        return {"error": "Invalid room"}

    # Update the database
    await request.app["db"].listen_to(user.user_id, room.room_id)

    # Synchronize the accounts
    await sync_user(request, user)

    return {}


@sio.event
@require_user
async def stop(
    user: db.User, sid: str, data: Mapping[str, Any]
) -> Mapping[str, str]:
    if user.listening_to_id is not None:
        pass
    return {}


@sio.event
@require_user
async def sync(
    user: db.User, sid: str, data: Mapping[str, Any]
) -> Mapping[str, str]:
    await sync_user(sio.environ["aiohttp.request"], user)
    return {}


#     request = sio.environ["aiohttp.request"]
#     request.app["db"].stop(user.user_id)
#     try:
#         room = request.app["db"].listen_to(
#             user.user_id, data.get("room_id", None)
#         )
#     except ValueError:
#         return

#     # Save the socket ID
#     if user.socket_id is not None:
#         sio.emit("close", to=user.socket_id)
#     user.socket_id = sid

#     # Transfer the playback and start playing
#     device_id = data.get("device_id", None)
#     if device_id is not None:
#         await api.call_api(
#             request,
#             user,
#             "/me/player",
#             method="PUT",
#             json=dict(device_ids=[device_id]),
#         )
#     if room.current_uri is not None:
#         await api.call_api(
#             request,
#             user,
#             "/me/player/play",
#             method="PUT",
#             json=dict(uris=[room.current_uri]),
#         )

#     await sio.enter_room(sid, room.room_id)


# @sio.event
# @require_user
# async def changed(user: db.User, sid: str, uri: str) -> None:
#     request = sio.environ["aiohttp.request"]
#     room = await user.playing_to
#     if room is None:
#         return

#     for listener in await room.listeners:
#         await api.call_api(
#             request,
#             listener,
#             "/me/player/play",
#             method="PUT",
#             json=dict(uris=[uri]),
#         )

#     await sio.emit("changed", uri, room=room.room_id)


# @sio.event
# @require_user
# async def paused(user: db.User, sid: str, uri: str) -> None:
#     request = sio.environ["aiohttp.request"]
#     room = await user.playing_to
#     if room is None:
#         return

#     for listener in await room.listeners:
#         await api.call_api(
#             request, listener, "/me/player/pause", method="PUT",
#         )

#     await sio.emit("changed", uri, room=room.room_id)


# @api.require_auth
# async def socket(request: web.Request, user: db.User) -> web.WebSocketResponse:
#     # Get the current user's info
#     room = request.app["db"].get_room(user.playing_to)
#     is_host = room is not None

#     # Make sure that we're getting a websockets request
#     ws_current = web.WebSocketResponse()
#     ws_ready = ws_current.can_prepare(request)
#     if not ws_ready.ok:
#         raise web.HTTPNotFound()

#     # Set up the connection and send a connected message
#     await ws_current.prepare(request)
#     await ws_current.send_json(
#         {
#             "action": "connect",
#             "user_id": user.user_id,
#             "display_name": user.display_name,
#         }
#     )
#     request.app["websockets"][user.user_id] = ws_current

#     # Handle incoming messages
#     while True:
#         message = await ws_current.receive()

#         if message.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
#             break

#         elif message.type == WSMsgType.text:
#             payload = message.json()
#             action = payload.get("action", None)

#             if is_host:
#                 uri = payload.get("uri", None)
#                 if uri is not None and action == "new_track":
#                     for listener in room.listeners:
#                         await api.call_api(
#                             request,
#                             request.app["db"].get_user(listener),
#                             "/me/player/play",
#                             method="PUT",
#                             json=dict(uris=[uri]),
#                         )

#                 elif action == "pause":
#                     for listener in room.listeners:
#                         await api.call_api(
#                             request,
#                             request.app["db"].get_user(listener),
#                             "/me/player/pause",
#                             method="PUT",
#                             user_id=listener,
#                         )

#     del request.app["websockets"][user.user_id]

#     # FIXME : Need to remove from listeners here too

#     return ws_current


# def setup(app: web.Application) -> None:
#     app.router.add_get("/socket", socket, name="socket")
