"""ETD Middleware Contract — abstract base class for OEM middleware adapters.

All production OEM adapters must subclass ETDMiddleware and implement:
    read(topic)             → dict  — pull latest value from a middleware topic
    publish(topic, message) → None  — push a message to a middleware topic

Adapters are validated at load time via load_middleware_adapter(), which calls
validate() and raises RuntimeError if required_topics are unreachable.

Usage::
    from etd_middleware_contract import ETDMiddleware, load_middleware_adapter

    class MyOEMAdapter(ETDMiddleware):
        required_topics = ['state.safety_state', 'command.skill_intent']

        def read(self, topic: str) -> dict:
            ...

        def publish(self, topic: str, message: dict) -> None:
            ...

    mw = load_middleware_adapter(MyOEMAdapter())
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ETDMiddleware(ABC):
    """Abstract base for all ETD OEM middleware adapters."""

    required_topics: List[str] = []

    @abstractmethod
    def read(self, topic: str) -> Dict[str, Any]:
        """Return the latest value for *topic* as a dict.

        Return an empty dict for unknown topics rather than raising, so callers
        can apply defaults safely.
        """

    @abstractmethod
    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        """Send *message* to *topic*.

        Fire-and-forget: callers do not wait for acknowledgement.
        Raise RuntimeError on fatal transport errors only.
        """

    def validate(self) -> None:
        """Check that all required_topics are available on this adapter.

        Called once at load time by load_middleware_adapter(). Override to add
        platform-specific connectivity checks (ping broker, check ROS graph, …).
        """
        unavailable = [t for t in self.required_topics if not self._is_topic_available(t)]
        if unavailable:
            raise RuntimeError(
                f"{type(self).__name__}: required topics not available: {unavailable}"
            )

    def _is_topic_available(self, topic: str) -> bool:
        """Return True if *topic* is reachable on the underlying middleware.

        Default implementation returns True (optimistic). Override with a live
        probe when the adapter can test connectivity at init time.
        """
        return True


def load_middleware_adapter(adapter: ETDMiddleware) -> ETDMiddleware:
    """Validate and return an ETD middleware adapter.

    Calls adapter.validate() — raises RuntimeError if validation fails, or
    TypeError if *adapter* is not an ETDMiddleware subclass.

    Returns the adapter unchanged so callers can chain::

        mw = load_middleware_adapter(HyundaiWIAAdapter())
    """
    if not isinstance(adapter, ETDMiddleware):
        raise TypeError(
            f"Expected ETDMiddleware subclass, got {type(adapter).__name__}"
        )
    adapter.validate()
    return adapter
