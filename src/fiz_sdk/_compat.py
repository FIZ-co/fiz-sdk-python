"""Typing constructs as Python 3.13 ships them, from typing_extensions before."""

import sys

if sys.version_info >= (3, 13):
    from typing import NotRequired, ReadOnly, Self, TypedDict, Unpack
else:
    from typing_extensions import NotRequired, ReadOnly, Self, TypedDict, Unpack

__all__ = ["NotRequired", "ReadOnly", "Self", "TypedDict", "Unpack"]
