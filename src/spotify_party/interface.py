__all__ = ["routes"]

from aiohttp import web

from . import api, db

routes = web.RouteTableDef()


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
    await user.update_auth(request)
    return web.json_response({"token": user.auth.access_token})


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

    return web.json_response(
        {
            "room_id": room_id,
            "stream_url": str(
                request.url.join(
                    request.app.router["listen"].url_for(room_id=room_id)
                )
            ),
        }
    )


@routes.put("/api/close", name="interface.close")
@api.require_auth(redirect=False)
async def close(request: web.Request, user: db.User) -> web.Response:
    if not await user.stop(request):
        return web.json_response(
            {"error": "Unable to stop playing"}, status=404
        )
    return web.HTTPNoContent()


@routes.put("/api/change", name="interface.change")
@api.require_auth(redirect=False)
async def change(request: web.Request, user: db.User) -> web.Response:
    data = await request.json()
    print(data)

    uri = data.get("uri", None)
    if uri is None:
        return web.json_response({"error": "Missing uri"}, status=400)

    room = await user.playing_to
    if room is None:
        return web.json_response({"error": "User not playing"}, status=403)

    if not await room.play(request, uri, data.get("position_ms", None)):
        return web.json_response({"error": "Unable to change song"})

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

    if not await user.listen_to(request, room, device_id=device_id):
        return web.json_response({"error": "Unable to start listening"})

    # It worked!
    return web.HTTPNoContent()


@routes.put("/api/pause", name="interface.pause")
@api.require_auth(redirect=False)
async def pause(request: web.Request, user: db.User) -> web.Response:
    room = await user.playing_to
    if room is None:
        if not await user.stop(request):
            return web.json_response({"error": "Unable to pause"})
        return web.HTTPNoContent()

    if not await room.pause(request):
        return web.json_response({"error": "Unable to pause room"})
    return web.HTTPNoContent()


@routes.put("/api/sync", name="interface.sync")
@api.require_auth(redirect=False)
async def sync(request: web.Request, user: db.User) -> web.Response:
    data = await request.json()

    if not await user.sync(request):
        return web.json_response(
            {"error": "Unable to sync playback"}, status=404
        )

    return web.HTTPNoContent()
