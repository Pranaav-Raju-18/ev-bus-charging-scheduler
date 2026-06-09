"""A time-ordered event queue built on a binary heap (heapq).

The scheduler returns each station's charging sessions grouped by station. To
read the whole network as one chronological stream - and to validate the
"one bus per charger" rule with a single sweep over time - we merge every
start/finish event into one ordered sequence.

A heap gives the next-earliest event in O(log n) without sorting everything up
front. Equal-minute events are ordered first by an explicit priority (so a
charge that ends exactly when another begins is freed before the new one is
checked) and then by a monotonic counter (stable insertion order).
"""

import heapq
from itertools import count

from Backend.configurations import STATIONS, CHARGE_MINUTES
from Backend.time_utils import TimeUtils


class EventQueue:
    """A min-heap of (minute, priority, sequence, kind, payload) events."""

    def __init__(self):
        """Create an empty event queue."""
        self._heap = []
        self._counter = count()

    def push(self, minute, kind, payload, priority=0):
        """Add an event to the queue.

        Args:
            minute (int): Event time in minutes past midnight (heap key).
            kind (str): Event type, e.g. 'CHARGE_START' or 'CHARGE_END'.
            payload (dict): Arbitrary data carried with the event.
            priority (int, optional): Tie-break among same-minute events;
                lower goes first. Defaults to 0.
        """
        heapq.heappush(self._heap, (minute, priority, next(self._counter), kind, payload))

    def pop(self):
        """Remove and return the earliest event.

        Returns:
            tuple[int, str, dict]: (minute, kind, payload) of the next event.
        """
        minute, _priority, _sequence, kind, payload = heapq.heappop(self._heap)
        return minute, kind, payload

    def __len__(self):
        """Number of events still queued.

        Returns:
            int: Remaining event count.
        """
        return len(self._heap)

    def drain(self):
        """Yield every event in chronological order, emptying the queue.

        Yields:
            tuple[int, str, dict]: (minute, kind, payload) for each event.
        """
        while self._heap:
            yield self.pop()


def charge_duration(start_clock, end_clock):
    """Charging duration in minutes between two clock strings.

    Args:
        start_clock (str): Charge start time as 'HH:MM'.
        end_clock (str): Charge end time as 'HH:MM'.

    Returns:
        int: Duration in minutes, wrapping correctly across midnight.
    """
    minutes = (TimeUtils.to_minutes(end_clock) - TimeUtils.to_minutes(start_clock)) % (24 * 60)
    return minutes or CHARGE_MINUTES


def charging_event_stream(result):
    """Merge every charging start/finish into one heap-ordered stream.

    Args:
        result (dict): A schedule result with a 'stations' mapping.

    Returns:
        list[tuple[int, str, dict]]: (minute, kind, payload) events in
            chronological order. 'kind' is 'CHARGE_START' or 'CHARGE_END';
            'payload' carries bus_id, operator_id and station. At an equal
            minute, ends are emitted before starts.
    """
    queue = EventQueue()
    for station in STATIONS:
        for event in result["stations"].get(station, []):
            start = event["start_minute"]
            end = start + charge_duration(event["charge_start"], event["charge_end"])
            payload = {
                "bus_id": event["bus_id"],
                "operator_id": event["operator_id"],
                "station": station,
            }
            queue.push(end, "CHARGE_END", payload, priority=0)
            queue.push(start, "CHARGE_START", payload, priority=1)
    return list(queue.drain())


def count_charger_overlaps(result):
    """Count 'one bus per charger' violations via a time sweep.

    Walks the chronological stream and keeps a running count of buses charging
    at each station. A CHARGE_START that arrives while the station is already at
    its charger capacity is a violation.

    Args:
        result (dict): A schedule result.

    Returns:
        int: Number of overlapping charging sessions (0 means the rule holds).
    """
    busy = {station: 0 for station in STATIONS}
    overlaps = 0
    for _minute, kind, payload in charging_event_stream(result):
        station = payload["station"]
        if kind == "CHARGE_START":
            if busy[station] >= STATIONS[station]["chargers"]:
                overlaps += 1
            busy[station] += 1
        else:
            busy[station] = max(0, busy[station] - 1)
    return overlaps
