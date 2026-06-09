"""Operational failures: how disruptions affect the chargers.

Failures are optional (config.FAILURES_ENABLED). They come in two flavours:
  * capacity loss - STATION_CAPACITY_REDUCTION / CHARGER_DOWN make fewer
    chargers usable during a window; modelled as a block on the station,
  * slow charging - SLOW_CHARGING makes charging at a station take longer
    while the failure is active.

Planned failures are known up front and enter the first solve. Dynamic
failures are treated as surprises and trigger re-optimization.
"""

from Backend.configurations import (
    CHARGE_MINUTES,
    STATIONS,
    FAILURES,
    FAILURES_ENABLED,
    PLANNED_FAILURE_TYPES,
    DYNAMIC_FAILURE_TYPES,
)
from Backend.time_utils import TimeUtils


class Failures:
    """Stateless helpers that interpret the configured failure list."""

    @staticmethod
    def all():
        """All configured failures, or none if failures are disabled.

        Returns:
            list[dict]: Failure definitions (see config.FAILURES).
        """
        return list(FAILURES) if FAILURES_ENABLED else []

    @staticmethod
    def window(failure):
        """Start and end of a failure in minutes past midnight.

        Args:
            failure (dict): A failure with 'start' and 'end' clock strings.

        Returns:
            tuple[int, int]: (start_minute, end_minute); end rolls to the next
                day if it is not after start.
        """
        start = TimeUtils.to_minutes(failure["start"])
        end = TimeUtils.to_minutes(failure["end"])
        if end <= start:
            end += 24 * 60
        return start, end

    @staticmethod
    def planned(active):
        """Failures known in advance (folded into the first solve).

        Args:
            active (list[dict]): Failure definitions to split.

        Returns:
            list[dict]: Failures whose type is in PLANNED_FAILURE_TYPES.
        """
        return [f for f in active if f["type"] in PLANNED_FAILURE_TYPES]

    @staticmethod
    def dynamic(active):
        """Failures treated as runtime surprises, ordered by start time.

        Args:
            active (list[dict]): Failure definitions to split.

        Returns:
            list[dict]: Failures whose type is in DYNAMIC_FAILURE_TYPES,
                sorted by start minute.
        """
        dynamic = [f for f in active if f["type"] in DYNAMIC_FAILURE_TYPES]
        return sorted(dynamic, key=lambda f: Failures.window(f)[0])

    @staticmethod
    def blocked_chargers(failure):
        """How many chargers a capacity failure removes.

        Args:
            failure (dict): A failure definition.

        Returns:
            int: Chargers made unavailable (0 if not a capacity failure).
        """
        if failure["type"] == "CHARGER_DOWN":
            return 1
        if failure["type"] == "STATION_CAPACITY_REDUCTION":
            configured = STATIONS[failure["station"]]["chargers"]
            return max(0, configured - failure["available_chargers"])
        return 0

    @staticmethod
    def capacity_blocks(active, station):
        """Blocking intervals at a station from active capacity failures.

        Args:
            active (list[dict]): Currently active failures.
            station (str): Station id to filter on.

        Returns:
            list[tuple[int, int, int]]: (start_minute, end_minute,
                chargers_blocked) for each capacity failure at this station.
        """
        blocks = []
        for failure in active:
            if failure.get("station") != station:
                continue
            blocked = Failures.blocked_chargers(failure)
            if blocked > 0:
                start, end = Failures.window(failure)
                blocks.append((start, end, blocked))
        return blocks

    @staticmethod
    def charge_minutes(active, station):
        """Charging time at a station, accounting for slow charging.

        While a SLOW_CHARGING failure is active at a station, charges there
        take the slow duration. Otherwise the normal CHARGE_MINUTES applies.

        Args:
            active (list[dict]): Currently active failures.
            station (str): Station id being charged at.

        Returns:
            int: Charging duration in minutes for this station.
        """
        for failure in active:
            if failure["type"] == "SLOW_CHARGING" and failure["station"] == station:
                return failure["slow_minutes"]
        return CHARGE_MINUTES
