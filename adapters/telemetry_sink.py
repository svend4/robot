"""ETD Telemetry Sink — configurable output for the skill telemetry pipeline.

Sinks:
    NullSink    — discards all events (tests / silent mode)
    ConsoleSink — prints JSON to stdout (development / debug)
    FileSink    — appends JSON Lines to a file
    MQTTSink    — publishes to an MQTT broker (requires paho-mqtt; stubs
                  to ConsoleSink when the library is not installed)
    MultiSink   — fan-out to multiple sinks in parallel

Usage::
    from adapters.telemetry_sink import FileSink, MultiSink, ConsoleSink

    sink = MultiSink([FileSink('telemetry/run.jsonl'), ConsoleSink()])
    sink.emit('skill.started', {'skill_id': 'etd.hyundai.wia_welding'})
    sink.close()
"""
from __future__ import annotations

import datetime
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class TelemetrySink(ABC):
    """Abstract base for all ETD telemetry output sinks."""

    @abstractmethod
    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        """Record one telemetry event with its payload."""

    def close(self) -> None:
        """Release any held resources. No-op by default."""


class NullSink(TelemetrySink):
    """Discards all events. Use in unit tests and benchmarks."""

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        pass


class ConsoleSink(TelemetrySink):
    """Prints each event as a compact JSON line to stdout."""

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        print(json.dumps({'event': event, **payload}, ensure_ascii=False))


class FileSink(TelemetrySink):
    """Appends each event as a JSON Line to a file.

    Parent directories are created automatically. The file is opened in
    append mode so existing runs are preserved.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self._path.open('a', encoding='utf-8')

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        entry = {'event': event, 'timestamp': _now(), **payload}
        self._fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


class MQTTSink(TelemetrySink):
    """Publishes each event to an MQTT broker.

    Falls back to stdout when paho-mqtt is not installed or the broker is
    unreachable at construction time — so the skill pipeline is never blocked
    by a missing telemetry backend.

    Topic: ``<topic_prefix>/<event.replace('.', '/')>``
    """

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        topic_prefix: str = 'etd/telemetry',
    ) -> None:
        self._broker = broker
        self._port = port
        self._prefix = topic_prefix
        self._client = self._connect()

    def _connect(self):
        try:
            import paho.mqtt.client as mqtt  # type: ignore[import]
            client = mqtt.Client()
            client.connect(self._broker, self._port)
            return client
        except Exception:
            return None

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        msg = json.dumps(
            {'event': event, 'timestamp': _now(), **payload}, ensure_ascii=False
        )
        if self._client is not None:
            ros_topic = f'{self._prefix}/{event.replace(".", "/")}'
            self._client.publish(ros_topic, msg)
        else:
            print(msg)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass


class MultiSink(TelemetrySink):
    """Fan-out to multiple sinks.

    If one sink raises during emit(), the exception is swallowed so the
    remaining sinks still receive the event.
    """

    def __init__(self, sinks: List[TelemetrySink]) -> None:
        self._sinks = list(sinks)

    def emit(self, event: str, payload: Dict[str, Any]) -> None:
        for sink in self._sinks:
            try:
                sink.emit(event, payload)
            except Exception:
                pass

    def close(self) -> None:
        for sink in self._sinks:
            try:
                sink.close()
            except Exception:
                pass


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
