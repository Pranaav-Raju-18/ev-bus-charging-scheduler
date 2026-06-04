import heapq
from itertools import count


class EventQueue:
    def __init__(self):
        self._events = []
        self._counter = count()

    def push(self, minute, event_type, payload):
        heapq.heappush(
            self._events,
            (minute, next(self._counter), event_type, payload),
        )

    def pop_next_batch(self):
        if not self._events:
            return None, []

        minute, _, event_type, payload = heapq.heappop(self._events)
        batch = [(event_type, payload)]

        while self._events and self._events[0][0] == minute:
            _, _, event_type, payload = heapq.heappop(self._events)
            batch.append((event_type, payload))

        return minute, batch

    def has_events(self):
        return bool(self._events)