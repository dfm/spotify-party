__all__ = ["get_config"]

import json
from typing import Any, Dict


schema = dict(
    spotify_client_id=(str, None), spotify_client_secret=(str, None),
)


class ValidationError(Exception):
    pass


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    new_config = dict()
    for name, (converter, default) in schema.items():
        value = config.pop(name, default)
        if value is None:
            raise ValidationError(f"missing value for '{name}'")
        try:
            new_config[name] = converter(value)
        except TypeError:
            raise ValidationError(f"invalid type for '{name}'")

    remaining = list(config.keys())
    if len(remaining):
        raise ValidationError(
            f"unrecognized configuration arguments: {remaining}"
        )

    return new_config


def get_config(filename: str) -> Dict[str, Any]:
    with open(filename, "r") as f:
        config = json.load(f)
    return validate_config(config)
