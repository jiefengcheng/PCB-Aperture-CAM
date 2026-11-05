"""Corrupt a source coordinate without accidentally changing its FS declaration."""
import re


def mutate_source_coordinate(body):
    match = re.search(rb'(?m)^X(-?\d+)', body)
    if match is None:
        raise ValueError('SOURCE_COORDINATE_CONTROL_NOT_FOUND')
    position = match.end(1) - 1
    replacement = b'1' if body[position:position + 1] == b'0' else b'0'
    return body[:position] + replacement + body[position + 1:]
