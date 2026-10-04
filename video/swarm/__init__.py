"""Shared manim library for the Swarm Observatory film."""
from manim import *  # noqa: F401,F403
from .style import *  # noqa: F401,F403
from .style import Text, MarkupText  # noqa: F401  (oversampled; must shadow manim's)
from .components import *  # noqa: F401,F403
from .scene import SwarmScene, Beat  # noqa: F401
