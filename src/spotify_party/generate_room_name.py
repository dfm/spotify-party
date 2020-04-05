__all__ = ["generate_room_name"]

import random

import pkg_resources

with open(
    pkg_resources.resource_filename(__name__, "wordlists/descriptors.txt")
) as f:
    descriptors = ["-".join(word.strip().split()) for word in f]

with open(
    pkg_resources.resource_filename(__name__, "wordlists/genres.txt")
) as f:
    genres = ["-".join(word.strip().split()) for word in f]


def generate_room_name() -> str:
    return random.choice(descriptors) + "-" + random.choice(genres)
