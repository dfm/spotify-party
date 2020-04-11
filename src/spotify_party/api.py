__all__ = ["api_app"]

from typing import Any, Dict

import yarl
from aiohttp import web

from .auth import require_auth
from .data_model import User
from .socket import sio

routes = web.RouteTableDef()


#
# Endpoints
#


@routes.route("*", "/me", name="interface.me")
@require_auth(redirect=False)
async def me(request: web.Request, user: User) -> web.Response:
    return web.json_response(
        dict(user_id=user.user_id, display_name=user.display_name)
    )


@routes.post("/token", name="interface.token")
@require_auth(redirect=False)
async def token(request: web.Request, user: User) -> web.Response:
    return web.json_response({"token": user.auth.access_token})


@routes.post("/transfer", name="interface.transfer")
@require_auth(redirect=False)
async def transfer(request: web.Request, user: User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"})

    await user.set_device_id(device_id)
    if not await user.transfer(request, play=True, check=True):
        return web.json_response({"error": "Unable to transfer"})

    return web.json_response(
        {"playing": await user.currently_playing(request)}
    )


@routes.route("*", "/stop", name="stop")
@require_auth(redirect=False)
async def stop(request: web.Request, user: User) -> web.Response:
    playing_to = await user.playing_to
    if playing_to is not None:
        await playing_to.pause(request)
        await request.config_dict["db"].close_room(playing_to.room_id)
        await sio.emit("close", room=playing_to.room_id)
        return web.Response(body="stopped")

    listening_to = await user.listening_to
    if listening_to is not None:
        await user.stop(request)
        await sio.emit(
            "listeners",
            {"number": len(await listening_to.listeners)},
            room=listening_to.room_id,
        )

    return web.Response(body="stopped")


#
# Broadcaster endpoints
#


@routes.post("/broadcast/start", name="broadcast.start")
@require_auth(redirect=False)
async def broadcast_start(request: web.Request, user: User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"})

    room_name = data.get("room_name", None)
    if room_name is None:
        return web.json_response({"error": "Missing room_name"})

    room_id = await user.play_to(request, device_id, room_name=room_name)
    if room_id is None:
        return web.json_response({"error": "Unable to transfer device"})

    url = yarl.URL(request.config_dict["config"]["base_url"]).with_path(
        f"/listen/{room_id}"
    )
    response: Dict[str, Any] = {"room_id": room_id, "stream_url": str(url)}

    current = await user.currently_playing(request)
    if current is not None:
        response["playing"] = current

    return web.json_response(response)


@routes.post("/broadcast/stop", name="broadcast.stop")
@require_auth(redirect=False)
async def broadcast_stop(request: web.Request, user: User) -> web.Response:
    room = await user.playing_to

    if not await user.stop(request):
        return web.json_response({"error": "Unable to stop playing"})

    if room is not None:
        await sio.emit("close", room=room.room_id)

    return web.json_response({})


@routes.post("/broadcast/pause", name="broadcast.pause")
@require_auth(redirect=False)
async def broadcast_pause(request: web.Request, user: User) -> web.Response:
    room = await user.playing_to
    if room is None:
        return web.json_response({"error": "User is not playing"})

    if not await room.pause(request):
        return web.json_response({"error": "Unable to pause room"})

    return web.json_response({})


@routes.post("/broadcast/change", name="broadcast.change")
@require_auth(redirect=False)
async def broadcast_change(request: web.Request, user: User) -> web.Response:
    data = await request.json()

    uri = data.get("uri", None)
    if uri is None:
        return web.json_response({"error": "Missing uri"})

    room = await user.playing_to
    if room is None:
        return web.json_response({"error": "User not playing"})

    if not await room.play(request, uri, data.get("position_ms", None)):
        return web.json_response({"error": "Unable to change song"})

    await sio.emit(
        "changed",
        {"number": len(await room.listeners), "playing": data},
        room=room.room_id,
    )

    return web.json_response({})


#
# Listener endpoints
#


@routes.post("/listen/start", name="listen.start")
@require_auth(redirect=False)
async def listen_start(request: web.Request, user: User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"})

    # Make sure that the room exists
    room = await request.config_dict["db"].get_room(data.get("room_id", None))
    if room is None:
        return web.json_response({"error": "Invalid room_id"})

    data = await user.listen_to(request, room, device_id=device_id)
    if data is None:
        return web.json_response({"error": "Unable to start listening"})

    data = {"playing": data, "number": len(await room.listeners)}
    await sio.emit("listeners", {"number": data["number"]}, room=room.room_id)

    # It worked!
    return web.json_response(data)


@routes.post("/listen/stop", name="listen.stop")
@require_auth(redirect=False)
async def listen_stop(request: web.Request, user: User) -> web.Response:
    if user.playing_to_id is not None or user.listening_to_id is None:
        return web.json_response({})

    room = await user.listening_to
    await user.stop(request)

    if room is not None:
        await sio.emit(
            "listeners",
            {"number": len(await room.listeners)},
            room=room.room_id,
        )

    return web.json_response({})


@routes.post("/listen/sync", name="listen.sync")
@require_auth(redirect=False)
async def listen_sync(request: web.Request, user: User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"})

    await user.set_device_id(device_id)
    data = await user.sync(request)
    if data is None:
        return web.json_response({"error": "Unable to sync playback"})

    return web.json_response(data)


def api_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    return app
