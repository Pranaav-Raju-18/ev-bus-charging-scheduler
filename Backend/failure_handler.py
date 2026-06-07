from collections import defaultdict

from Backend.configurations import (
    CHARGER_CONFIG,
    OPERATIONAL_FAILURE_SETTINGS,
    OPERATIONAL_FAILURES,
)


class FailureHandler:
    def _operational_failures(self) -> object:
        """Apply operational failure logic to the schedule.
        """
        if not self._include_operational_failures():
            return []

        failures = self._all_enabled_operational_failures()
        failure_filter = getattr(self, "failure_filter", None)

        if not failure_filter:
            return failures

        allowed_ids = failure_filter.get("operational_failure_ids")
        allowed_types = failure_filter.get("types")

        if allowed_ids is not None:
            allowed_ids = set(allowed_ids)
            failures = [
                failure
                for failure in failures
                if failure.get("operational_failure_id") in allowed_ids
            ]

        if allowed_types is not None:
            allowed_types = set(allowed_types)
            failures = [
                failure
                for failure in failures
                if failure.get("type") in allowed_types
            ]

        return failures

    def _all_enabled_operational_failures(self) -> object:
        """Apply operational failure logic to the schedule.
        """
        if not self._include_operational_failures():
            return []

        return OPERATIONAL_FAILURES

    def _include_operational_failures(self) -> object:
        """Apply operational failure logic to the schedule.
        """
        return OPERATIONAL_FAILURE_SETTINGS.get(
            "include_operational_failures",
            False,
        )

    def _failure_window_minutes(self, failure) -> tuple:
        """Convert or compare minute-based timeline values.
        
        Args:
            failure (dict): Operational failure configuration dictionary.
        """
        earliest_departure = min(
            self._time_to_minutes(bus["scheduled_departure_time"])
            for bus in self.scenario["buses"]
        )

        start_minute = self._time_to_minutes(failure["start_time"])
        end_minute = self._time_to_minutes(failure["end_time"])

        while start_minute < earliest_departure:
            start_minute += 24 * 60
            end_minute += 24 * 60

        if end_minute <= start_minute:
            end_minute += 24 * 60

        return start_minute, end_minute

    def _operational_failures_summary(self) -> dict:
        """Apply operational failure logic to the schedule.
        """
        if not self._include_operational_failures():
            return {
                "enabled": False,
                "failures": [],
            }

        failures = []

        for failure in self._operational_failures():
            start_minute, end_minute = self._failure_window_minutes(failure)

            failures.append({
                "operational_failure_id": failure.get("operational_failure_id"),
                "type": failure.get("type"),
                "station_id": failure.get("station_id"),
                "charger_id": failure.get("charger_id"),
                "start_time": failure.get("start_time"),
                "end_time": failure.get("end_time"),
                "start_minute": start_minute,
                "end_minute": end_minute,
                "available_chargers": failure.get("available_chargers"),
                "charging_duration_minutes": failure.get("charging_duration_minutes"),
                "affected_chargers": failure.get("affected_chargers"),
                "reason": failure.get("reason"),
            })

        return {
            "enabled": True,
            "failures": failures,
        }

    def _slow_charging_operational_failures(self, station_id) -> list:
        """Apply operational failure logic to the schedule.
        
        Args:
            station_id (str): Charging station identifier.
        """
        failures = [
            failure
            for failure in self._operational_failures()
            if failure.get("type") == "SLOW_CHARGING"
            and failure.get("station_id") == station_id
        ]

        return sorted(
            failures,
            key=lambda failure: self._failure_window_minutes(failure)[0],
        )

    def _normal_charging_time(self) -> object:
        """Convert or compare schedule time values.
        """
        return (
            CHARGER_CONFIG["charging_duration_minutes"]
            + CHARGER_CONFIG.get("charger_setup_duration_minutes", 0)
        )

    def _max_charging_time(self) -> object:
        """Convert or compare schedule time values.
        """
        slow_durations = [
            failure["charging_duration_minutes"]
            + CHARGER_CONFIG.get("charger_setup_duration_minutes", 0)
            for failure in self._operational_failures()
            if failure.get("type") == "SLOW_CHARGING"
        ]

        return max([self._normal_charging_time()] + slow_durations)

    def _charger_unavailable_windows(self) -> object:
        """Build or validate charger availability and assignment data.
        """
        unavailable_windows = defaultdict(list)

        for failure in self._operational_failures():
            failure_type = failure.get("type")
            station_id = failure.get("station_id")

            if station_id not in self.stations:
                continue

            start_minute, end_minute = self._failure_window_minutes(failure)

            if failure_type == "CHARGER_DOWN":
                unavailable_windows[failure["charger_id"]].append(
                    (start_minute, end_minute)
                )

            elif failure_type == "STATION_CAPACITY_REDUCTION":
                configured_chargers = self.stations[station_id]["charger_count"]
                available_chargers = failure["available_chargers"]
                unavailable_count = max(0, configured_chargers - available_chargers)

                for charger_number in range(
                    configured_chargers - unavailable_count + 1,
                    configured_chargers + 1,
                ):
                    charger_id = f"{station_id}-{charger_number}"
                    unavailable_windows[charger_id].append(
                        (start_minute, end_minute)
                    )

        return unavailable_windows

    def _charger_has_conflict(
        self,
        charger_id,
        start_minute,
        end_minute,
        unavailable_windows,
    ) -> bool:
        """Build or validate charger availability and assignment data.
        
        Args:
            charger_id (str): Physical charger identifier.
            start_minute (int): Start time represented as timeline minutes.
            end_minute (int): End time represented as timeline minutes.
            unavailable_windows (_type_): Unavailable windows used by this function.
        """
        return any(
            start_minute < unavailable_end and end_minute > unavailable_start
            for unavailable_start, unavailable_end in unavailable_windows.get(charger_id, [])
        )
