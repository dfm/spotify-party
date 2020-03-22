__all__ = ["app_factory"]

import base64

from cryptography import fernet

from aiohttp import web
import aiohttp_session
from aiohttp_session.cookie_storage import EncryptedCookieStorage
import jinja2
import aiohttp_jinja2

from . import config, auth, player
from .client_session import client_session


@aiohttp_jinja2.template("index.html")
async def index(request: web.Request) -> web.Response:
    await auth.require_auth(request)
    return {}


def app_factory(config_filename: str) -> web.Application:
    app = web.Application()

    app["config"] = config.get_config(config_filename)

    # Set up the user session
    secret_key = base64.urlsafe_b64decode(fernet.Fernet.generate_key())
    aiohttp_session.setup(app, EncryptedCookieStorage(secret_key))

    # Set up the templating engine
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader("./templates"))
    app["static_root_url"] = "/static"

    # Set up the authentication subapp
    auth.setup(app)

    # Set up the player app
    player.setup(app)

    # And the routes for the main app
    app.add_routes(
        [web.get("/", index, name="index"), web.static("/static", "./static")]
    )

    # Add the client session for outgoing connections
    app.cleanup_ctx.append(client_session)

    return app
