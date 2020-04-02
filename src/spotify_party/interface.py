__all__ = ["routes", "sio"]

from typing import Any, Dict, Mapping

import aiohttp_session
import socketio
import yarl
from aiohttp import web

from . import api, db

routes = web.RouteTableDef()
sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")


@sio.event
async def connect(sid: str, environ: Mapping[str, Any]) -> bool:
    # Check that this user is authenticated
    request = environ["aiohttp.request"]
    session = await aiohttp_session.get_session(request)
    user = await request.app["db"].get_user(session.get("sp_user_id"))
    if user is None:
        return False
    return True


@sio.event
async def disconnect(sid: str) -> None:
    pass


@sio.event
async def join(sid: str, room_id: str) -> None:
    sio.enter_room(sid, room_id)


@sio.event
async def leave(sid: str, room_id: str) -> None:
    sio.leave_room(sid, room_id)


#
# Endpoints
#


@routes.route("*", "/api/me", name="interface.me")
@api.require_auth(redirect=False)
async def me(request: web.Request, user: db.User) -> web.Response:
    return web.json_response(
        dict(user_id=user.user_id, display_name=user.display_name)
    )


@routes.post("/api/token", name="interface.token")
@api.require_auth(redirect=False)
async def token(request: web.Request, user: db.User) -> web.Response:
    return web.json_response({"token": user.auth.access_token})


@routes.put("/api/transfer", name="interface.transfer")
@api.require_auth(redirect=False)
async def transfer(request: web.Request, user: db.User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"}, status=400)

    await user.set_device_id(device_id)
    if not await user.transfer(request, play=True, check=True):
        return web.json_response({"error": "Unable to transfer"}, status=404)

    return web.json_response({"token": user.auth.access_token})


@routes.route("*", "/stop", name="stop")
@api.require_auth(redirect=False)
async def stop(request: web.Request, user: db.User) -> web.Response:
    playing_to = await user.playing_to
    if playing_to is not None:
        await playing_to.pause(request)
        await request.app["db"].close_room(playing_to.room_id)
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

    return web.HTTPTemporaryRedirect(
        location=request.app.router["index"].url_for()
    )


#
# Broadcaster endpoints
#


@routes.put("/api/stream", name="interface.stream")
@api.require_auth(redirect=False)
async def stream(request: web.Request, user: db.User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"}, status=400)

    room_id = await user.play_to(
        request, device_id, room_id=data.get("room_id", None)
    )
    if room_id is None:
        return web.json_response(
            {"error": "Unable to transfer device"}, status=404
        )

    url = yarl.URL(request.app["config"]["base_url"]).with_path(
        f"/listen/{room_id}"
    )
    response: Dict[str, Any] = {"room_id": room_id, "stream_url": str(url)}

    current = await user.currently_playing(request)
    if current is not None:
        response["playing"] = current

    return web.json_response(response)


@routes.put("/api/close", name="interface.close")
@api.require_auth(redirect=False)
async def close(request: web.Request, user: db.User) -> web.Response:
    room = await user.playing_to

    if not await user.stop(request):
        return web.json_response(
            {"error": "Unable to stop playing"}, status=404
        )

    if room is not None:
        await sio.emit("close", room=room.room_id)

    return web.HTTPNoContent()


@routes.put("/api/change", name="interface.change")
@api.require_auth(redirect=False)
async def change(request: web.Request, user: db.User) -> web.Response:
    data = await request.json()

    uri = data.get("uri", None)
    if uri is None:
        return web.json_response({"error": "Missing uri"}, status=400)

    room = await user.playing_to
    if room is None:
        return web.json_response({"error": "User not playing"}, status=403)

    if not await room.play(request, uri, data.get("position_ms", None)):
        return web.json_response({"error": "Unable to change song"})

    await sio.emit(
        "changed",
        {"number": len(await room.listeners), "playing": data},
        room=room.room_id,
    )

    return web.HTTPNoContent()


#
# Listener endpoints
#


@routes.put("/api/listen", name="interface.listen")
@api.require_auth(redirect=False)
async def listen(request: web.Request, user: db.User) -> web.Response:
    data = await request.json()

    # A device ID is required
    device_id = data.get("device_id", None)
    if device_id is None:
        return web.json_response({"error": "Missing device_id"}, status=400)

    # Make sure that the room exists
    room = await request.app["db"].get_room(data.get("room_id", None))
    if room is None:
        return web.json_response({"error": "Invalid room_id"}, status=404)

    data = await user.listen_to(request, room, device_id=device_id)
    if data is None:
        return web.json_response({"error": "Unable to start listening"})

    data = {"playing": data, "number": len(await room.listeners)}
    await sio.emit("listeners", {"number": data["number"]}, room=room.room_id)

    # It worked!
    return web.json_response(data)


@routes.put("/api/pause", name="interface.pause")
@api.require_auth(redirect=False)
async def pause(request: web.Request, user: db.User) -> web.Response:
    room = await user.playing_to
    if room is None:
        room = await user.listening_to

        if not await user.stop(request):
            return web.json_response({"error": "Unable to pause"})

        if room is not None:
            await sio.emit(
                "listeners",
                {"number": len(await room.listeners)},
                room=room.room_id,
            )

        return web.HTTPNoContent()

    if not await room.pause(request):
        return web.json_response({"error": "Unable to pause room"})

    return web.HTTPNoContent()


@routes.put("/api/sync", name="interface.sync")
@api.require_auth(redirect=False)
async def sync(request: web.Request, user: db.User) -> web.Response:
    data = await user.sync(request)
    if data is None:
        return web.json_response(
            {"error": "Unable to sync playback"}, status=404
        )
    return web.json_response(data)
