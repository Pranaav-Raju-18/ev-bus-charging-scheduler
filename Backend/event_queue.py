"""Priority event queue for chronological event processing."""

import heapq
from itertools import count


class EventQueue:
    """Min-heap based event queue that batches events with the same timestamp."""

    def __init__(self):
        self._events = []
        self._counter = count()

    def push(self, minute, event_type, payload):
        """Add an event to the queue."""
        heapq.heappush(
            self._events,
            (minute, next(self._counter), event_type, payload),
        )

    def pop_next_batch(self):
        """Return all events scheduled for the earliest timestamp."""
        if not self._events:
            return None, []

        minute, _, event_type, payload = heapq.heappop(self._events)
        batch = [(event_type, payload)]

        while self._events and self._events[0][0] == minute:
            _, _, event_type, payload = heapq.heappop(self._events)
            batch.append((event_type, payload))

        return minute, batch

    def has_events(self):
        """Return whether any events remain in the queue."""
        return bool(self._events)
