__all__ = ["setup"]

from aiohttp import web
import aiohttp_jinja2

from . import api, db


def get_socket_url(request: web.Request) -> str:
    socket_url = request.url.with_path(
        str(request.app.router["socket"].url_for())
    )
    return str(
        socket_url.with_scheme("ws" if socket_url.scheme == "http" else "wss")
    )


@api.require_auth
async def new(request: web.Request, user: db.User) -> web.Response:
    room = request.app["db"].add_room(user)
    return web.HTTPTemporaryRedirect(
        location=request.app.router["room"].url_for(room_id=room.room_id)
    )


@api.require_auth
async def room_view(request: web.Request, user: db.User) -> web.Response:
    room = request.app["db"].get_room(request.match_info["room_id"])
    if room is None:
        raise web.HTTPNotFound()

    # Is the current user the host?
    is_host = room.host_id == user.user_id

    return aiohttp_jinja2.render_template(
        "room.html",
        request,
        dict(
            socket_url=get_socket_url(request),
            is_host=is_host,
            is_logged_in=True,
        ),
    )


# @api.require_auth
# async def sync(request: web.Request, user: db.User) -> web.Response:
#     if user.listening_to is None:
#         raise web.HTTPBadRequest()

#     room = request.app["db"].get_room(user.listening_to)
#     if player is None:
#         raise web.HTTPNotFound()

#     # Get the host's currently playing track
#     play_info = await api.call_api(
#         request, "/me/player/currently-playing", user_id=player.owner_id
#     )

#     # Start playing
#     uri = play_info.get("item", {}).get("uri", None)
#     position_ms = play_info.get("progress_ms", None)
#     if position_ms is None:
#         position_ms = 0
#     if uri is not None and play_info.get("is_playing", False):
#         await api.call_api(
#             request,
#             "/me/player/play",
#             method="PUT",
#             json=dict(uris=[uri], position_ms=position_ms),
#         )

#     return web.json_response(play_info)


def setup(app: web.Application) -> None:
    app.add_routes(
        [
            web.get("/new", new, name="new"),
            web.get("/room/{room_id}", room_view, name="room"),
            # web.get("/sync", sync, name="sync"),
        ]
    )
