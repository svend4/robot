"""ETD Adapter Registry — maps skill IDs and package families to OEM adapters.

Usage::

    from adapters.registry import get_adapter_for_skill, register_adapter

    # Look up the right adapter for a skill ID
    adapter = get_adapter_for_skill('etd.hyundai.wia_welding')
    # → HyundaiWIAAdapter(dry_run=True)

    # Register a custom adapter for your own skill family
    register_adapter('com.mycompany', MyCompanyAdapter)

Built-in registrations (by skill-ID prefix / exact match):

    Prefix / ID                       Adapter
    ─────────────────────────────────────────────────────────
    etd.hyundai.wia_welding           HyundaiWIAAdapter
    etd.hyundai.mobed_transport       HyundaiMobEDAdapter
    etd.hyundai.vest_exoskeleton      HyundaiExoAdapter
    etd.atlas.*                       AtlasAdapter
    etd.pickplace.*                   (generic — NullMiddleware)
    etd.assembly.*                    (generic — NullMiddleware)
    etd.inspect.*                     (generic — NullMiddleware)
    etd.cobot.*                       (generic — NullMiddleware)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional, Type

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from etd_middleware_contract import ETDMiddleware  # noqa: E402

# ── NullMiddleware (generic / test fallback) ──────────────────────────────────

class NullMiddleware(ETDMiddleware):
    """Generic no-op middleware. Returns empty dicts; publishes are no-ops.

    Used as the default when no platform-specific adapter is registered for a
    skill. Skills that only need a telemetry trace can use NullMiddleware and
    rely on AcceptanceMiddleware in tests.
    """

    def read(self, topic: str) -> Dict[str, Any]:
        return {}

    def publish(self, topic: str, message: Dict[str, Any]) -> None:
        pass


# ── Registry ──────────────────────────────────────────────────────────────────

# Maps skill-ID prefix (or exact ID) → adapter class.
# Longer / more-specific prefixes are checked first.
_REGISTRY: Dict[str, Type[ETDMiddleware]] = {}
_EXACT: Dict[str, Type[ETDMiddleware]] = {}


def register_adapter(
    skill_prefix: str,
    adapter_class: Type[ETDMiddleware],
    exact: bool = False,
) -> None:
    """Register *adapter_class* for skills whose ID starts with *skill_prefix*.

    Parameters
    ----------
    skill_prefix:
        Prefix (e.g. ``'etd.hyundai'``) or exact ID (e.g.
        ``'etd.hyundai.wia_welding'``).
    adapter_class:
        An ETDMiddleware subclass. Must be instantiable with no required args.
    exact:
        When True, match only the exact skill ID rather than any ID with
        the given prefix.
    """
    if not issubclass(adapter_class, ETDMiddleware):
        raise TypeError(f"{adapter_class.__name__} must subclass ETDMiddleware")
    if exact:
        _EXACT[skill_prefix] = adapter_class
    else:
        _REGISTRY[skill_prefix] = adapter_class


def get_adapter_class(skill_id: str) -> Type[ETDMiddleware]:
    """Return the adapter class registered for *skill_id*.

    Resolution order:
    1. Exact-match entries (``_EXACT``)
    2. Prefix entries, longest prefix wins
    3. ``NullMiddleware`` as the fallback

    Does not instantiate the adapter — call the returned class to create an
    instance.
    """
    if skill_id in _EXACT:
        return _EXACT[skill_id]
    # Longest matching prefix wins
    best: Optional[str] = None
    for prefix in _REGISTRY:
        if skill_id.startswith(prefix):
            if best is None or len(prefix) > len(best):
                best = prefix
    if best is not None:
        return _REGISTRY[best]
    return NullMiddleware


def get_adapter_for_skill(
    skill_id: str,
    dry_run: bool = True,
    telemetry_sink=None,
    **kwargs: Any,
) -> ETDMiddleware:
    """Instantiate and return the right ETDMiddleware adapter for *skill_id*.

    Parameters
    ----------
    skill_id:
        ETD skill ID, e.g. ``'etd.hyundai.wia_welding'``.
    dry_run:
        Forwarded to the adapter constructor when the adapter accepts it.
    telemetry_sink:
        Forwarded to the adapter constructor when the adapter accepts it.
    **kwargs:
        Extra kwargs forwarded to the adapter constructor.
    """
    cls = get_adapter_class(skill_id)
    # Only forward dry_run / telemetry_sink if the class accepts them
    import inspect
    sig = inspect.signature(cls.__init__)
    ctor_kwargs: Dict[str, Any] = dict(kwargs)
    if 'dry_run' in sig.parameters:
        ctor_kwargs['dry_run'] = dry_run
    if 'telemetry_sink' in sig.parameters and telemetry_sink is not None:
        ctor_kwargs['telemetry_sink'] = telemetry_sink
    return cls(**ctor_kwargs)


def list_registrations() -> list[dict]:
    """Return a list of all registered (prefix/id, adapter_class_name) pairs."""
    entries = []
    for prefix, cls in _REGISTRY.items():
        entries.append({'match': 'prefix', 'key': prefix, 'adapter': cls.__name__})
    for skill_id, cls in _EXACT.items():
        entries.append({'match': 'exact', 'key': skill_id, 'adapter': cls.__name__})
    return sorted(entries, key=lambda e: e['key'])


# ── Built-in registrations ────────────────────────────────────────────────────

def _register_builtins() -> None:
    from adapters.hyundai_wia_adapter import HyundaiWIAAdapter
    from adapters.hyundai_mobed_adapter import HyundaiMobEDAdapter
    from adapters.hyundai_exo_adapter import HyundaiExoAdapter
    from adapters.atlas_adapter import AtlasAdapter

    register_adapter('etd.hyundai.wia_welding',       HyundaiWIAAdapter,    exact=True)
    register_adapter('etd.hyundai.mobed_transport',   HyundaiMobEDAdapter,  exact=True)
    register_adapter('etd.hyundai.vest_exoskeleton',  HyundaiExoAdapter,    exact=True)
    register_adapter('etd.atlas',                     AtlasAdapter)


_register_builtins()
