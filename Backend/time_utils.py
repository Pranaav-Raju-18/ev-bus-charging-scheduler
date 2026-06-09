"""Conversions between 'HH:MM' clock strings and integer minutes.

The whole engine works in minutes past midnight, which keeps the arithmetic
simple. These helpers translate to and from the clock strings used in the
scenario files and the UI.
"""


class TimeUtils:
    """Stateless time-format helpers."""

    @staticmethod
    def to_minutes(clock):
        """Convert a 'HH:MM' clock string to minutes past midnight.

        Args:
            clock (str): Time of day in 24-hour 'HH:MM' format.

        Returns:
            int: Minutes elapsed since 00:00.
        """
        hours, minutes = clock.split(":")
        return int(hours) * 60 + int(minutes)

    @staticmethod
    def to_clock(minutes):
        """Convert minutes past midnight to a 'HH:MM' string.

        Args:
            minutes (int): Minutes since 00:00 (may exceed a day).

        Returns:
            str: Time formatted as 24-hour 'HH:MM'.
        """
        return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"
