__all__ = ["setup"]

import aiohttp_session
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


async def token(request: web.Request) -> web.Response:
    """A view to access the token from the web player"""
    token = await api.get_token(request)
    return web.json_response(dict(token=token))


async def get_current_user(request: web.Request) -> db.User:
    await api.require_auth(request)
    session = await aiohttp_session.get_session(request)
    user = request.app["db"].get_user(session["sp_user_id"])
    if user is None:
        raise web.HTTPUnauthorized()
    return user


async def get_player(request: web.Request) -> db.Player:
    # Check to make sure that that player exists
    player = request.app["db"].get_player(request.match_info["player_id"])
    if player is None:
        raise web.HTTPNotFound()
    return player


async def new(request: web.Request) -> web.Response:
    user = await get_current_user(request)
    player = request.app["db"].add_player(user)
    return web.HTTPTemporaryRedirect(
        location=request.app.router["play"].url_for(player_id=player.player_id)
    )


async def play(request: web.Request) -> web.Response:
    user = await get_current_user(request)
    player = await get_player(request)

    # If the current user isn't the owner, redirect to listen
    if player.owner_id != user.user_id:
        raise web.HTTPTemporaryRedirect(
            location=request.app.router["listen"].url_for(
                player_id=player.player_id
            )
        )

    return aiohttp_jinja2.render_template(
        "player.html",
        request,
        dict(socket_url=get_socket_url(request), is_host=True),
    )


async def listen(request: web.Request) -> web.Response:
    user = await get_current_user(request)
    player = await get_player(request)

    # If the current user is the owner, redirect to play
    if user.user_id == player.owner_id:
        raise web.HTTPTemporaryRedirect(
            location=request.app.router["play"].url_for(
                player_id=player.player_id
            )
        )

    request.app["db"].listen_to(user.user_id, player.player_id)
    return aiohttp_jinja2.render_template(
        "player.html",
        request,
        dict(socket_url=get_socket_url(request), is_host=False),
    )


async def sync(request: web.Request) -> web.Response:
    user = await get_current_user(request)
    if user.listening_to is None:
        raise web.HTTPBadRequest()

    player = request.app["db"].get_player(user.listening_to)
    if player is None:
        raise web.HTTPNotFound()

    # Get the host's currently playing track
    play_info = await api.call_api(
        request, "/me/player/currently-playing", user_id=player.owner_id
    )

    # Start playing
    uri = play_info.get("item", {}).get("uri", None)
    position_ms = play_info.get("progress_ms", None)
    if position_ms is None:
        position_ms = 0
    if uri is not None and play_info.get("is_playing", False):
        await api.call_api(
            request,
            "/me/player/play",
            method="PUT",
            json=dict(uris=[uri], position_ms=position_ms),
        )

    return web.json_response(play_info)


def setup(app: web.Application) -> None:
    app.add_routes(
        [
            web.post("/player/token", token, name="token"),
            web.get("/player/new", new, name="new"),
            web.get("/player/play/{player_id}", play, name="play"),
            web.get("/player/listen/{player_id}", listen, name="listen"),
            web.get("/player/sync", sync, name="sync"),
        ]
    )
