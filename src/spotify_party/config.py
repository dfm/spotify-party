__all__ = ["get_config"]

from typing import Any, Mapping, MutableMapping

import toml

schema: Mapping[str, Any] = dict(
    spotify_client_id=(str, None),
    spotify_client_secret=(str, None),
    spotify_redirect_uri=(str, None),
    base_url=(str, None),
    database_filename=(str, None),
    port=(int, 5000),
    admins=(list, []),
)


class ValidationError(Exception):
    pass


def validate_config(config: MutableMapping[str, Any]) -> Mapping[str, Any]:
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


def get_config(filename: str) -> Mapping[str, Any]:
    return validate_config(toml.load(filename))
