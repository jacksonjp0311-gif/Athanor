from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import numpy as np

@dataclass
class DeltaPhiEstimate:
    dphi: np.ndarray
    coherence: np.ndarray
    h7: float
    summary: Dict[str, Any]

@dataclass
class TelemetryBatch:
    traj: np.ndarray  # shape: (T, D)
    meta: Dict[str, Any]

@dataclass
class Candidate:
    id: str
    genome: np.ndarray
    telemetry: Optional[TelemetryBatch] = None
    dphi: Optional[DeltaPhiEstimate] = None
    score_q: float = 0.0
    score_f: float = 0.0
    verdict: str = ""PENDING""
    reason: str = """"
    tags: Dict[str, Any] = field(default_factory=dict)
