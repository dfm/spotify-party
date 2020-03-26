__all__ = ["routes"]

from aiohttp import web
import aiohttp_jinja2
import aiohttp_session

from . import db, api

routes = web.RouteTableDef()


@routes.get("/", name="index")
async def index(request: web.Request) -> web.Response:
    return aiohttp_jinja2.render_template("splash.html", request, {})


@routes.get("/about", name="about")
async def about(request: web.Request) -> web.Response:
    return web.Response(body="about page")


@routes.get("/me", name="me")
@api.require_auth
async def me(request: web.Request, user: db.User) -> web.Response:
    return web.json_response(
        dict(user_id=user.user_id, display_name=user.display_name)
    )


@routes.get("/login", name="login")
async def login(request: web.Request) -> web.Response:
    return web.HTTPTemporaryRedirect(
        location=request.app.router["new"].url_for()
    )


@routes.get("/logout", name="logout")
async def logout(request: web.Request) -> web.Response:
    session = await aiohttp_session.get_session(request)
    if "sp_user_id" in session:
        del session["sp_user_id"]
    return web.HTTPTemporaryRedirect(
        location=request.app.router["index"].url_for()
    )


@routes.post("/token", name="token")
@api.require_auth
async def token(request: web.Request, user: db.User) -> web.Response:
    return web.json_response({"token": user.auth.access_token})
