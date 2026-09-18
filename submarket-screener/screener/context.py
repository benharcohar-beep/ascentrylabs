"""Shared run context handed to every data source module."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cache import Cache
from .config import MarketConfig, Weights


@dataclass
class Context:
    cache: Cache
    market: MarketConfig
    weights: Weights
    output_dir: Path
    use_osrm: bool = False       # opt in to drive distance via the public OSRM demo server
    verbose: bool = True

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"  {msg}", flush=True)
