__all__ = ["setup", "require"]

import os
import time
import secrets
from functools import wraps
from typing import Union

import yarl
import aiohttp_session
from aiohttp import web, ClientSession


SPOTIFY_CLIENT_ID = os.environ["SPOTIFY_CLIENT_ID"]
SPOTIFY_CLIENT_SECRET = os.environ["SPOTIFY_CLIENT_SECRET"]


def redirect_uri(request: web.Request) -> str:
    return str(
        request.url.with_path(str(request.app.router["callback"].url_for()))
    )


def default_redirect(request: web.Request) -> str:
    return str(request.app.router["index"].url_for())


async def handle_error(request: web.Request, error: str) -> web.Response:
    raise web.HTTPInternalServerError(
        text="Unhandled OAuth2 Error: {0}".format()
    )


async def handle_code(request: web.Request, code: str) -> str:
    session = await aiohttp_session.get_session(request)

    params = dict(headers={"Accept": "application/json"})
    params["data"] = dict(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        grant_type="authorization_code",
        code=code,
        redirect_uri=redirect_uri(request),
    )

    async with ClientSession() as client:
        async with client.post(
            "https://accounts.spotify.com/api/token", **params
        ) as response:
            response = await response.json()

    token = session["access_token"] = response["access_token"]
    session["refresh_token"] = response["refresh_token"]
    session["expires_at"] = time.time() + int(response["expires_in"])

    return token


async def auth(request: web.Request) -> web.Response:
    session = await aiohttp_session.get_session(request)

    # Get the current redirect URL
    session["redirect"] = request.query.get(
        "redirect", default_redirect(request)
    )

    # Generate a state token
    state = secrets.token_urlsafe()
    session["state"] = state

    # Construct the API OAuth2 URL
    location = yarl.URL("https://accounts.spotify.com/authorize").with_query(
        client_id=SPOTIFY_CLIENT_ID,
        response_type="code",
        redirect_uri=redirect_uri(request),
        state=state,
        scope="streaming,user-read-email,user-read-private",
    )

    return web.HTTPTemporaryRedirect(location=str(location))


async def callback(request: web.Request) -> web.Response:
    session = await aiohttp_session.get_session(request)

    state = session.get("state", None)
    returned_state = request.query.get("state", None)
    if None in (state, returned_state) or state != returned_state:
        raise web.HTTPBadRequest()

    if "error" in request.query:
        return handle_error(
            request, request.query.get("error", "unknown error")
        )

    await handle_code(request, request.query["code"])

    return web.HTTPTemporaryRedirect(
        location=session.get("redirect", default_redirect(request))
    )


async def token(request: web.Request) -> web.Response:
    session = await aiohttp_session.get_session(request)

    auth_url = str(request.app.router["auth"].url_for())

    if "access_token" not in session or "refresh_token" not in session:
        return web.HTTPTemporaryRedirect(location=auth_url)

    current_time = time.time()
    if session.get("expires_at", current_time) - current_time <= 60:
        try:
            token = await handle_code(request, session["refresh_token"])
        except Exception:
            return web.HTTPTemporaryRedirect(location=auth_url)
    else:
        token = session["access_token"]

    return web.json_response(dict(token=token))


def setup(app: web.Application) -> None:
    # Add the routes
    app.add_routes(
        [
            web.get("/spotify/auth", auth, name="auth"),
            web.get("/spotify/callback", callback, name="callback"),
            web.get("/spotify/token", token, name="token"),
        ]
    )


async def require(request: web.Request) -> None:
    session = await aiohttp_session.get_session(request)

    auth_url = str(request.app.router["auth"].url_for())

    if "access_token" not in session or "refresh_token" not in session:
        raise web.HTTPTemporaryRedirect(location=auth_url)

    current_time = time.time()
    if session.get("expires_at", current_time) - current_time <= 60:
        await handle_code(request, session["refresh_token"])
