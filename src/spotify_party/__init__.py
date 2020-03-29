__all__ = ["app_factory", "create_tables", "get_config"]

from .app import app_factory
from .config import get_config
from .db import create_tables

__uri__ = "https://github.com/dfm/spotify-party"
__author__ = "Daniel Foreman-Mackey"
__email__ = "foreman.mackey@gmail.com"
__license__ = "MIT"
__description__ = "Listen to music with your friends"
