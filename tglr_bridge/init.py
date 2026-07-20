"""Compatibility module for bounded TGLR bridge initialization."""

from .bridge import TGLRBridge


def create_bridge():
    return TGLRBridge()
