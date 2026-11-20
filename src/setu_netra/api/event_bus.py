"""
event_bus.py: Single-process in-memory asynchronous EventBus with replay buffer,
monotonically increasing event IDs, SSE streaming, and slow-client backpressure guards.
"""

import asyncio
import collections
import datetime
import json
import logging
import threading
import time
from typing import AsyncGenerator, Deque, Dict, Optional, Set

from setu_netra.api.schemas import TelemetryEvent

logger = logging.getLogger(__name__)


class EventBus:
    """
    Thread-safe, single-process in-memory EventBus.
    
    Guarantees:
    - Exactly 2048-event circular replay buffer.
    - Monotonically increasing event IDs.
    - Bounded per-subscriber queues (max 256 events).
    - Automatic slow-client backpressure mitigation (drop oldest + alert).
    - Thread-safe publication from synchronous workers.
    - SSE formatted serialization with Last-Event-ID replay.
    - 15-second keep-alive heartbeats (: ping\\n\\n).
    """

    def __init__(self, replay_buffer_size: int = 2048, subscriber_queue_size: int = 256):
        self.replay_buffer_size = replay_buffer_size
        self.subscriber_queue_size = subscriber_queue_size
        
        self._lock = threading.Lock()
        self._event_counter = 0
        self._replay_buffer: Deque[TelemetryEvent] = collections.deque(maxlen=replay_buffer_size)
        self._subscribers: Dict[str, asyncio.Queue] = {}
        
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._running = False

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Bind the active asyncio event loop for threadsafe cross-thread dispatch."""
        self._loop = loop
        self._running = True

    def start_heartbeat(self, interval_seconds: float = 15.0) -> None:
        """Start periodic SSE keep-alive heartbeats."""
        if self._heartbeat_task is None and self._loop is not None:
            self._heartbeat_task = self._loop.create_task(self._heartbeat_loop(interval_seconds))

    async def _heartbeat_loop(self, interval_seconds: float) -> None:
        """Periodic background coroutine broadcasting keep-alive pings."""
        try:
            while self._running:
                await asyncio.sleep(interval_seconds)
                self.publish(
                    event_type="HEARTBEAT",
                    source_subsystem="EventBus",
                    payload={"type": "keep_alive", "subscriber_count": len(self._subscribers)},
                    correlation_id="corr_system_heartbeat",
                )
        except asyncio.CancelledError:
            pass
        except Exception as err:
            logger.error(f"Error in EventBus heartbeat loop: {err}")

    def create_event(
        self,
        event_type: str,
        source_subsystem: str,
        payload: Dict,
        correlation_id: str,
        query_id: Optional[str] = None,
    ) -> TelemetryEvent:
        """Construct a TelemetryEvent with atomic sequence numbering and timestamps."""
        with self._lock:
            self._event_counter += 1
            seq_id = self._event_counter

        now = datetime.datetime.now(datetime.timezone.utc)
        return TelemetryEvent(
            event_id=seq_id,
            correlation_id=correlation_id,
            timestamp_ns=time.time_ns(),
            timestamp_iso=now.isoformat(),
            event_type=event_type,
            query_id=query_id,
            source_subsystem=source_subsystem,
            payload=payload,
        )

    def publish_event(self, event: TelemetryEvent) -> None:
        """Thread-safe event publication into the replay buffer and subscriber queues."""
        with self._lock:
            self._replay_buffer.append(event)
            subs = list(self._subscribers.items())

        if not subs:
            return

        def _dispatch():
            for sub_id, queue in subs:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Slow client handling: drop oldest unread event to prevent memory bloat
                    try:
                        _ = queue.get_nowait()
                        # Inject backpressure warning into queue
                        warning_event = self.create_event(
                            event_type="CLIENT_BACKPRESSURE_WARNING",
                            source_subsystem="EventBus",
                            payload={
                                "message": "Client buffer lagged > 256 frames; oldest frames dropped",
                                "sub_id": sub_id,
                                "dropped_at_event_id": event.event_id,
                            },
                            correlation_id=event.correlation_id,
                        )
                        queue.put_nowait(warning_event)
                        queue.put_nowait(event)
                    except Exception:
                        pass

        if self._loop and self._loop.is_running():
            try:
                running_loop = asyncio.get_running_loop()
                if running_loop is self._loop:
                    _dispatch()
                else:
                    self._loop.call_soon_threadsafe(_dispatch)
            except RuntimeError:
                # No running loop in current thread; use threadsafe call
                self._loop.call_soon_threadsafe(_dispatch)
        else:
            # Fallback if loop is not yet running or running in synchronous test harness
            _dispatch()

    def publish(
        self,
        event_type: str,
        source_subsystem: str,
        payload: Dict,
        correlation_id: str,
        query_id: Optional[str] = None,
    ) -> TelemetryEvent:
        """Convenience helper to construct and broadcast an event."""
        event = self.create_event(
            event_type=event_type,
            source_subsystem=source_subsystem,
            payload=payload,
            correlation_id=correlation_id,
            query_id=query_id,
        )
        self.publish_event(event)
        return event

    def get_retained_events(self, after_event_id: Optional[int] = None) -> list[TelemetryEvent]:
        """Retrieve retained events from the circular replay buffer for reconnection replay."""
        with self._lock:
            if after_event_id is None:
                return list(self._replay_buffer)
            return [e for e in self._replay_buffer if e.event_id > after_event_id]

    async def subscribe(
        self,
        sub_id: str,
        last_event_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Async generator yielding SSE formatted strings:
        id: <event_id>\\n
        event: <event_type>\\n
        data: <json>\\n\\n
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.subscriber_queue_size)
        
        with self._lock:
            self._subscribers[sub_id] = queue

        try:
            # 1. Replay missed historical events if Last-Event-ID was provided
            if last_event_id is not None:
                replayed = self.get_retained_events(after_event_id=last_event_id)
                for event in replayed:
                    yield self.format_sse(event)

            # 2. Yield live events
            while self._running:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield self.format_sse(event)
                except asyncio.TimeoutError:
                    # Emit SSE comment ping to keep connection alive
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            with self._lock:
                self._subscribers.pop(sub_id, None)

    @staticmethod
    def format_sse(event: TelemetryEvent) -> str:
        """Format TelemetryEvent into RFC standard SSE string."""
        if event.event_type == "HEARTBEAT":
            # Can be emitted as event or comment
            data_json = json.dumps(event.model_dump())
            return f"id: {event.event_id}\nevent: HEARTBEAT\ndata: {data_json}\n\n"
        data_json = json.dumps(event.model_dump())
        return f"id: {event.event_id}\nevent: {event.event_type}\ndata: {data_json}\n\n"

    def stop(self) -> None:
        """Stop background tasks and clean up subscribers."""
        self._running = False
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        with self._lock:
            self._subscribers.clear()


# Global Singleton
_global_event_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Retrieve or initialize the global EventBus singleton."""
    global _global_event_bus
    with _bus_lock:
        if _global_event_bus is None:
            _global_event_bus = EventBus()
        return _global_event_bus
