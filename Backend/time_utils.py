"""Time conversion helpers used across scheduling and reporting."""


class TimeUtilsMixin:
    """Provide HH:MM to minute conversion and display formatting."""

    @staticmethod
    def _time_to_minutes(time_text):
        hour, minute = map(int, time_text.split(":"))
        return hour * 60 + minute

    @staticmethod
    def _minutes_to_time(minutes):
        hour = (minutes // 60) % 24
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _time_to_minutes_after(time_text, minimum_minute):
        candidate_minute = TimeUtilsMixin._time_to_minutes(time_text)

        while candidate_minute < minimum_minute:
            candidate_minute += 24 * 60

        return candidate_minute
