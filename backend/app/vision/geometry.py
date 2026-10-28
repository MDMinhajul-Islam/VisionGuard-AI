from __future__ import annotations

import cv2
import numpy as np


def polygon_area(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    return abs(sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )) / 2


def bbox_zone_overlap(
    bbox: tuple[float, float, float, float],
    polygon: list[tuple[float, float]],
) -> float:
    """Intersection divided by zone area for normalized coordinates."""
    if polygon_area(polygon) <= 0:
        raise ValueError("zone polygon must have non-zero area")
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        return 0.0
    box = np.asarray([(x1, y1), (x2, y1), (x2, y2), (x1, y2)], dtype=np.float32)
    zone = np.asarray(polygon, dtype=np.float32)
    zone_hull = cv2.convexHull(zone)
    intersection, _ = cv2.intersectConvexConvex(zone_hull, box)
    return float(max(0.0, intersection) / polygon_area(polygon))

