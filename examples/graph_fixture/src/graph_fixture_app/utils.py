"""Utility helpers."""

import json


def normalize(value: str) -> str:
    return value.strip().title()


def to_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True)
