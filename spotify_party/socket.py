__all__ = ["setup"]

from aiohttp import web, WSMsgType

from . import player, api


async def socket(request: web.Request) -> web.WebSocketResponse:
    # Get the current user's info
    user = await player.get_current_user(request)
    room = request.app["db"].get_player(user.playing_to)
    is_host = room is not None

    # Make sure that we're getting a websockets request
    ws_current = web.WebSocketResponse()
    ws_ready = ws_current.can_prepare(request)
    if not ws_ready.ok:
        raise web.HTTPNotFound()

    # Set up the connection and send a connected message
    await ws_current.prepare(request)
    await ws_current.send_json(
        {
            "action": "connect",
            "user_id": user.user_id,
            "display_name": user.display_name,
        }
    )
    request.app["websockets"][user.user_id] = ws_current

    # Handle incoming messages
    while True:
        message = await ws_current.receive()

        if message.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
            break

        elif message.type == WSMsgType.text:
            payload = message.json()
            action = payload.get("action", None)

            if is_host:
                uri = payload.get("uri", None)
                if uri is not None and action == "new_track":
                    for listener in room.listeners:
                        await api.call_api(
                            request,
                            "/me/player/play",
                            method="PUT",
                            json=dict(uris=[uri]),
                            user_id=listener,
                        )

                elif action == "pause":
                    for listener in room.listeners:
                        await api.call_api(
                            request,
                            "/me/player/pause",
                            method="PUT",
                            user_id=listener,
                        )

    del request.app["websockets"][user.user_id]

    # FIXME : Need to remove from listeners here too

    return ws_current


def setup(app: web.Application) -> None:
    app.router.add_get("/socket", socket, name="socket")
