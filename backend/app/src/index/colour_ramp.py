import numpy as np
from rio_tiler.colormap import cmap, ColorMaps

import json
import sys

from typing import Annotated, Dict, Optional, Literal

import numpy
import matplotlib
from rio_tiler.colormap import parse_color
from rio_tiler.colormap import cmap as default_cmap
from fastapi import HTTPException, Query

def _linear_ramp(
    stops: list[tuple[float, tuple[int, int, int, int]]],
    n: int = 256,
) -> dict[int, tuple[int, int, int, int]]:
    """
    Build a smooth 256-entry LUT from a list of (position, rgba) stops.
    Position is 0.0 - 1.0 representing the normalised value range.
    Interpolates linearly between stops in RGB space.
    """
    positions = np.array([s[0] for s in stops])
    colours   = np.array([s[1] for s in stops], dtype=np.float32)
    indices   = np.linspace(0, 1, n)

    lut = {}
    for i, t in enumerate(indices):
        # Find surrounding stops
        idx = np.searchsorted(positions, t, side="right")
        idx = np.clip(idx, 1, len(stops) - 1)

        lo, hi = idx - 1, idx
        t0, t1 = positions[lo], positions[hi]

        # Normalise t between the two stops
        alpha = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
        alpha = float(np.clip(alpha, 0, 1))

        colour = colours[lo] * (1 - alpha) + colours[hi] * alpha
        lut[int(i)] = tuple(int(c) for c in np.clip(colour, 0, 255))

    return lut

def ColorMapParams(
    colormap_name: Annotated[  # type: ignore
        Literal[tuple(default_cmap.list())],
        Query(description="Colormap name"),
    ] = None,
    colormap: Annotated[
        str,
        Query(description="JSON encoded custom Colormap"),
    ] = None,
    colormap_type: Annotated[
        Literal["explicit", "linear"],
        Query(description="User input colormap type."),
    ] = "explicit",
) -> Optional[Dict]:
    """Colormap Dependency."""
    if colormap_name:
        return default_cmap.get(colormap_name)

    if colormap:
        try:
            cm = json.loads(
                colormap,
                object_hook=lambda x: {int(k): parse_color(v) for k, v in x.items()},
            )
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail="Could not parse the colormap value."
            )

        if colormap_type == "linear":
            # input colormap has to start from 0 to 255 ?
            cm = matplotlib.colors.LinearSegmentedColormap.from_list(
                'custom',
                [
                    (k / 255, matplotlib.colors.to_hex([v / 255 for v in rgba]))
                    for (k, rgba) in cm.items()
                ],
                256,
            )
            x = numpy.linspace(0, 1, 256)
            cmap_vals = cm(x)[:, :]
            cmap_uint8 = (cmap_vals * 255).astype('uint8')
            cm = {idx: value.tolist() for idx, value in enumerate(cmap_uint8)}

        return cm

    return None


# Colour stop definitions
# Position 0.0 = minimum value, 1.0 = maximum value

CUSTOM_COLOUR_RAMPS: dict[str, list[tuple[float, tuple[int, int, int, int]]]] = {
    "erp": [
        (0.00, (10,  12,  16,  255)),     # transparent — zero population
        (0.05, (20,  10,  40,  255)),   # dark purple — very low
        (0.20, (80,  20,  120, 255)),   # purple
        (0.45, (180, 50,  50,  255)),   # red
        (0.70, (230, 120, 20,  255)),   # orange
        (1.00, (255, 240, 100, 255)),   # bright yellow — peak density
    ],
    "unemployment_rate": [
        (0.00, (26,  152, 80,  255)),   # green — low unemployment
        (0.25, (102, 189, 99,  255)),
        (0.50, (255, 255, 191, 255)),   # yellow — moderate
        (0.75, (253, 141, 60,  255)),
        (1.00, (215, 48,  31,  255)),   # red — high unemployment
    ],
    "seifa": [
        (0.00, (215, 48,  39,  255)),   # red — most disadvantaged
        (0.25, (253, 174, 97,  255)),
        (0.50, (255, 255, 191, 255)),   # yellow — middle
        (0.75, (166, 217, 106, 255)),
        (1.00, (26,  152, 80,  255)),   # green — least disadvantaged
    ],
    "housing_price": [
        (0.00, (240, 249, 232, 255)),   # light — affordable
        (0.25, (186, 228, 188, 255)),
        (0.50, (123, 204, 196, 255)),
        (0.75, (67,  162, 202, 255)),
        (1.00, (8,   104, 172, 255)),   # dark blue — expensive
    ],
    "liveability": [
        (0.00, (68,  1,   84,  255)),   # dark purple — low liveability
        (0.25, (59,  82,  139, 255)),
        (0.50, (33,  145, 140, 255)),   # teal
        (0.75, (94,  201, 98,  255)),
        (1.00, (253, 231, 37,  255)),   # yellow — high liveability
    ],
}

def register_colourmaps() -> ColorMaps:
    active_cmap = cmap
    for name, stops in CUSTOM_COLOUR_RAMPS.items():
        lut = _linear_ramp(stops)
        active_cmap = active_cmap.register({name: lut})
    return active_cmap