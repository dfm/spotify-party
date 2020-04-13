__all__ = ["api_app"]

import json
import traceback
from functools import partial, wraps
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional

import yarl
from aiohttp import web

from .auth import require_auth
from .data_model import User
from .socket import sio

routes = web.RouteTableDef()


def endpoint(
    handler: Optional[
        Callable[[web.Request, User, Mapping[str, Any]], Awaitable]
    ] = None,
    *,
    required_data: Mapping[str, Callable] = {},
    optional_data: Mapping[str, Callable] = {},
):
    if handler is None:
        return partial(
            _endpoint, required_data=required_data, optional_data=optional_data
        )
    return _endpoint(
        handler, required_data=required_data, optional_data=optional_data
    )


def _endpoint(
    handler: Callable[[web.Request, User, Mapping[str, Any]], Awaitable],
    *,
    required_data: Mapping[str, Callable] = {},
    optional_data: Mapping[str, Callable] = {},
) -> Callable[[web.Request], Awaitable]:
    @require_auth(redirect=False)
    @wraps(handler)
    async def wrapped(request: web.Request, user: User) -> web.Response:
        try:
            original_data = await request.json()
        except json.decoder.JSONDecodeError:
            original_data = {}
        data: Dict[str, Any] = dict()

        # Make sure that the required data was included
        for key, mapper in required_data.items():
            if key not in original_data:
                raise web.HTTPBadRequest(
                    text=f"Missing required field: '{key}'"
                )
            try:
                data[key] = mapper(original_data.pop(key))
            except TypeError:
                raise web.HTTPBadRequest(
                    text=f"Invalid type for field: '{key}'"
                )

        # Map the rest of the data
        for key, value in original_data.items():
            if key not in optional_data:
                raise web.HTTPBadRequest(text=f"Invalid field: '{key}'")
            try:
                data[key] = optional_data[key](value)
            except TypeError:
                raise web.HTTPBadRequest(
                    text=f"Invalid type for field: '{key}'"
                )

        return await handler(request, user, data)

    return wrapped


#
# Endpoints
#


@routes.route("*", "/me", name="interface.me")
@require_auth
async def me(request: web.Request, user: User) -> web.Response:
    return web.json_response(
        dict(user_id=user.user_id, display_name=user.display_name)
    )


@routes.post("/token", name="interface.token")
@require_auth(redirect=False)
async def token(request: web.Request, user: User) -> web.Response:
    return web.json_response({"token": user.auth.access_token})


@routes.post("/transfer", name="interface.transfer")
@endpoint(required_data=dict(device_id=str))
async def transfer(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:
    user.device_id = data["device_id"]
    if not await user.transfer(request, play=True, check=True):
        return web.json_response({"error": "Unable to transfer"})

    return web.json_response(
        {"playing": await user.currently_playing(request)}
    )


@routes.route("*", "/stop", name="stop")
@require_auth
async def stop(request: web.Request, user: User) -> web.Response:
    user.paused = True
    return web.Response(body="stopped")


#
# Broadcaster endpoints
#


@routes.post("/broadcast/start", name="broadcast.start")
@endpoint(required_data=dict(device_id=str, room_name=str))
async def broadcast_start(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:
    user.device_id = data["device_id"]
    room_name = data["room_name"]

    # Start the playback on the correct device
    if not await user.play(request, {}):
        raise web.HTTPNotFound(text="Unable to start playback")

    # Update the properties of this user
    user.paused = False
    user.listening_to_id = None
    room_id = user.playing_to_id = f"{user.user_id}/{room_name}"

    # Construct the stream URL
    url = yarl.URL(request.config_dict["config"]["base_url"]).with_path(
        f"/listen/{room_id}"
    )
    response: Dict[str, Any] = {
        "room_id": room_id,
        "stream_url": str(url),
        "playing": None,
        "number": 0,
    }

    # Get the currently playing track
    current = await user.currently_playing(request)
    if current is not None:
        response["playing"] = current

        # Start playback for listeners
        room = await user.playing_to
        if room is not None:
            await room.play(
                request, current["uri"], current.get("position_ms", None)
            )

            response["number"] = len(await room.listeners)

        # Update the info for the listeners
        await sio.emit("changed", response, room=room_id)

    return web.json_response(response)


@routes.post("/broadcast/stop", name="broadcast.stop")
@endpoint(required_data=dict(device_id=str))
async def broadcast_stop(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:
    user.device_id = data["device_id"]
    user.paused = True
    if not await user.pause(request):
        raise web.HTTPNotFound(text="Unable to pause playback")
    return web.json_response({})


@routes.post("/broadcast/pause", name="broadcast.pause")
@require_auth(redirect=False)
async def broadcast_pause(request: web.Request, user: User) -> web.Response:
    user.paused = True

    # Here we're pausing the playback of the listeners
    # We're not going to bother checking for success because the host doesn't
    # care too much if we can't pause all the user playback.
    room = await user.playing_to
    if room:
        await room.pause(request)

    return web.json_response({})


@routes.post("/broadcast/change", name="broadcast.change")
@endpoint(
    required_data=dict(uri=str, name=str, type=str, id=str),
    optional_data=dict(position_ms=int),
)
async def broadcast_change(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:

    room = await user.playing_to
    if room is None:
        raise web.HTTPUnauthorized(text="This user is not currently playing")

    user.paused = False
    await room.play(request, data["uri"], data.get("position_ms", None))
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
@endpoint(required_data=dict(device_id=str, room_id=str))
async def listen_start(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:
    user.device_id = data["device_id"]
    room_id = data["room_id"]

    # Make sure that the room exists
    room = await request.config_dict["db"].get_room(room_id)
    if room is None:
        raise web.HTTPBadRequest(text="Invalid room_id")

    # Update the user state
    user.paused = False
    user.listening_to_id = room_id
    user.playing_to_id = None

    # Sync the playback
    response = await user.sync(request)
    if not response:
        raise web.HTTPNotFound(text="The broadcast is paused")

    # Increment the number of listeners
    response["number"] += 1

    # It worked!
    return web.json_response(response)


@routes.post("/listen/stop", name="listen.stop")
@endpoint(required_data=dict(device_id=str))
async def listen_stop(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:
    user.device_id = data["device_id"]
    user.paused = True
    if not await user.pause(request):
        raise web.HTTPNotFound(text="Unable to pause playback")
    return web.json_response({})


@routes.post("/listen/sync", name="listen.sync")
@endpoint(required_data=dict(device_id=str))
async def listen_sync(
    request: web.Request, user: User, data: Mapping[str, Any]
) -> web.Response:
    user.device_id = data["device_id"]

    response = await user.sync(request)
    if response is None:
        raise web.HTTPNotFound(text="The broadcast is paused")

    return web.json_response(response)


#
# App setup
#


@web.middleware
async def error_middleware(
    request: web.Request, handler: Callable[[web.Request], Awaitable]
) -> web.Response:
    try:
        return await handler(request)
    except web.HTTPException as ex:
        return web.json_response({"error": ex.text}, status=ex.status)
    except Exception:
        traceback.print_exc()
        return web.json_response(
            {"error": "Something went horribly wrong"}, status=500
        )


def api_app() -> web.Application:
    app = web.Application(middlewares=[error_middleware])
    app.add_routes(routes)
    return app
