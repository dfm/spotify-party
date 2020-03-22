from aiohttp import web
from spotify_party import app_factory

if __name__ == "__main__":
    web.run_app(app_factory("config/config.dev.json"), port=5000)
