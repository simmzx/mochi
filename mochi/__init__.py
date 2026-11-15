"""MOCHI: a self-evolving multi-agent system for oncology target discovery.

Public API
----------
>>> import mochi
>>> agent = mochi.initialize()
>>> result = agent.run("DPEP1")
>>> print(result.ranking[0]["gene"])

The package is a faithful re-implementation of the MOCHI architecture
(Manager, Dev, Critic, Tool Creation agents + a self-evolving Tool Ocean and a
TF-IDF reasoning-template library) specialised for downstream effector-target
discovery, with a deterministic offline engine so the workflow can be run and
audited without an LLM API key.
"""

from __future__ import annotations

__version__ = "1.1.0"

from .core import RunResult, Mochi  # noqa: E402
from .settings import SETTINGS, Settings  # noqa: E402


def initialize(**kwargs) -> Mochi:
    """Create the multi-agent system (mirrors MOCHI's ``initialize_mochi``)."""
    return Mochi(**kwargs)


def run_task(task: str, target: str, **kwargs) -> RunResult:
    """Convenience wrapper: initialise and run one target-discovery task."""
    agent = Mochi(**{k: v for k, v in kwargs.items() if k in ("verbose", "force_offline", "params", "settings")})
    return agent.run(target=target, task=task)


__all__ = ["Mochi", "RunResult", "Settings", "SETTINGS", "initialize", "run_task", "__version__"]
