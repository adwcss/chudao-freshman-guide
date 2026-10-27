"""Build code-native SVG stroke geometry from the generated mascot asset.

Development-only: Pillow and NumPy. The PNG is read for analysis and never
modified. The shipped application only needs the generated JSON and stdlib.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]


def edges(values):
    padded = np.pad(values, 1, mode="edge")
    a, b, c = padded[:-2, :-2], padded[:-2, 1:-1], padded[:-2, 2:]
    d, f = padded[1:-1, :-2], padded[1:-1, 2:]
    g, h, i = padded[2:, :-2], padded[2:, 1:-1], padded[2:, 2:]
    gx, gy = -a + c - 2*d + 2*f - g + i, -a - 2*b - c + g + 2*h + i
    magnitude = np.hypot(gx, gy)
    direction = (np.arctan2(gy, gx) * 180 / np.pi + 180) % 180
    result = np.zeros_like(magnitude)
    directions = [((direction < 22.5) | (direction >= 157.5), (0, 1)),
                  ((direction >= 22.5) & (direction < 67.5), (1, 1)),
                  ((direction >= 67.5) & (direction < 112.5), (1, 0)),
                  ((direction >= 112.5) & (direction < 157.5), (1, -1))]
    for mask, shift in directions:
        before, after = np.roll(magnitude, shift, (0, 1)), np.roll(magnitude, tuple(-x for x in shift), (0, 1))
        keep = mask & (magnitude >= before) & (magnitude >= after)
        result[keep] = magnitude[keep]
    result[[0, -1], :] = 0
    result[:, [0, -1]] = 0
    return result


def simplify(points, epsilon=.7):
    if len(points) < 3:
        return points
    data = np.array(points, dtype=float)
    start, end = data[0], data[-1]
    direction = end - start
    length = np.linalg.norm(direction)
    distances = (np.abs(direction[0]*(start[1]-data[:, 1]) - (start[0]-data[:, 0])*direction[1])/length
                 if length else np.linalg.norm(data - start, axis=1))
    index = int(distances.argmax())
    if distances[index] <= epsilon:
        return [points[0], points[-1]]
    return simplify(points[:index+1], epsilon)[:-1] + simplify(points[index:], epsilon)


def build(name="school-mascot"):
    original = Image.open(ROOT / f"frontend/assets/{name}.png").convert("RGBA")
    width = 650
    height = round(original.height * width / original.width)
    analysis = original.resize((width, height), Image.Resampling.LANCZOS)
    alpha = np.asarray(analysis.getchannel("A").filter(ImageFilter.GaussianBlur(.65)), dtype=float)
    white = Image.new("RGBA", analysis.size, "white")
    white.alpha_composite(analysis)
    grey = np.asarray(white.convert("L").filter(ImageFilter.GaussianBlur(.65)), dtype=float)
    magnitude = edges(grey)
    silhouette = edges(alpha)
    weak = (magnitude > 25) | (silhouette > 50)
    strong = (magnitude > 82) | (silhouette > 120)
    stack = list(zip(*np.where(strong)))
    pixels = set(stack)
    offsets = [(y, x) for y in (-1, 0, 1) for x in (-1, 0, 1) if y or x]
    while stack:
        y, x = stack.pop()
        for dy, dx in offsets:
            neighbor = (y+dy, x+dx)
            if 0 <= neighbor[0] < height and 0 <= neighbor[1] < width and weak[neighbor] and neighbor not in pixels:
                pixels.add(neighbor)
                stack.append(neighbor)
    def neighbors(point):
        return [(point[0]+dy, point[1]+dx) for dy, dx in offsets if (point[0]+dy, point[1]+dx) in pixels]
    starts = sorted(point for point in pixels if len(neighbors(point)) <= 1)
    polylines = []
    # Trace each edge pixel once; choosing the straightest continuation keeps
    # the long hair/cape contours continuous without hundreds of tiny branches.
    for start in starts + sorted(pixels):
        if start not in pixels:
            continue
        points, point, direction = [], start, (0, 1)
        while point in pixels:
            pixels.remove(point)
            points.append((point[1], point[0]))
            choices = neighbors(point)
            if not choices:
                break
            following = max(choices, key=lambda p: (p[0]-point[0])*direction[0] + (p[1]-point[1])*direction[1])
            direction = (following[0]-point[0], following[1]-point[1])
            point = following
        if len(points) >= 11:
            polylines.append(simplify(points))
    polylines.sort(key=lambda points: min(y for x, y in points))
    paths = ["M" + " L".join(f"{x},{y}" for x, y in points) for points in polylines]
    if not 50 < len(paths) <= 1600:
        raise ValueError(f"Unexpected stroke count: {len(paths)}")
    output = ROOT / "frontend/assets" / ("mascot-lines.json" if name=="school-mascot" else name+"-lines.json")
    output.write_text(json.dumps({"viewBox": [0, 0, width, height], "paths": paths}, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"asset": name, "strokes": len(paths), "viewBox": [width, height], "bytes": output.stat().st_size}))


if __name__ == "__main__":
    import sys
    for name in sys.argv[1:] or ["school-mascot"]:
        build(name)
