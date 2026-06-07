import heapq
from itertools import count


class EventQueue:
    def __init__(self) -> None:
        """Initialize runtime state for this scheduler component.
        """
        self._events = []
        self._counter = count()

    def push(self, minute, event_type, payload) -> None:
        """Push an event into the priority queue.
        
        Args:
            minute (int): Timeline minute used for ordering events.
            event_type (str): Type of event being added or processed.
            payload (dict): Event-specific data stored in the queue.
        """
        heapq.heappush(
            self._events,
            (minute, next(self._counter), event_type, payload),
        )

    def pop_next_batch(self) -> list[dict]:
        """Pop all events scheduled at the next event time.
        """
        if not self._events:
            return None, []

        minute, _, event_type, payload = heapq.heappop(self._events)
        batch = [(event_type, payload)]

        while self._events and self._events[0][0] == minute:
            _, _, event_type, payload = heapq.heappop(self._events)
            batch.append((event_type, payload))

        return minute, batch

    def has_events(self) -> bool:
        """Check whether the queue still contains events.
        """
        return bool(self._events)
