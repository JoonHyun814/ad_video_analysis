"""RAFT flow (H,W,2) → FlowStats. 분류 없이 raw 값만 반환."""
from __future__ import annotations

import numpy as np

from ..optical_flow.motion_type import FlowStats


def flow_to_stats(flow_hw2: np.ndarray) -> FlowStats:
    """dense flow (H,W,2) → FlowStats raw 값."""
    u = flow_hw2[:, :, 0]
    v = flow_hw2[:, :, 1]
    pan_x = float(np.mean(u))
    pan_y = float(np.mean(v))
    zoom_score = float(np.mean(np.gradient(u, axis=1) + np.gradient(v, axis=0)))
    rotation_score = float(np.mean(np.gradient(v, axis=1) - np.gradient(u, axis=0)))
    mag = np.sqrt(u**2 + v**2)
    return FlowStats(
        zoom_score=zoom_score, pan_x=pan_x, pan_y=pan_y,
        rotation_score=rotation_score,
        flow_var=float(np.var(mag)),
        mean_mag=float(np.mean(mag)),
        n_valid=u.size,
    )
