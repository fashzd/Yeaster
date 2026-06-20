"""Yeaster strategy skills — the brain's stages as standalone, composable units.

Each skill is a thin in-process wrapper over an existing module (no self-HTTP),
exposing a uniform contract: JSON params in → evidence pack out. The internal
pipeline keeps calling the modules directly; these are an additive surface for
external consumers (Track 2 / other agents).
"""
