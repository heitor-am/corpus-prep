"""UUID v7 (RFC 9562) — sortable IDs por timestamp."""

from __future__ import annotations

import os
import time
from uuid import UUID


def uuid7() -> UUID:
    """Gera um UUIDv7 (sortable por tempo de criação).

    Layout RFC 9562:
        48 bits  unix_ts_ms
         4 bits  version (= 0b0111)
        12 bits  rand_a
         2 bits  variant (= 0b10)
        62 bits  rand_b
    """
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF
    rand_b = int.from_bytes(os.urandom(8), "big") & ((1 << 62) - 1)

    bits = (
        (ts_ms << 80)
        | (0x7 << 76)
        | (rand_a << 64)
        | (0b10 << 62)
        | rand_b
    )
    return UUID(int=bits)
