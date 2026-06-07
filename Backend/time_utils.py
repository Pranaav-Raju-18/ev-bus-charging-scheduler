class TimeUtilities:
    @staticmethod
    def _time_to_minutes(time_text) -> object:
        """Convert or compare schedule time values.
        
        Args:
            time_text (str): Time value in HH:MM format.
        """
        hour, minute = map(int, time_text.split(":"))
        return hour * 60 + minute

    @staticmethod
    def _minutes_to_time(minutes) -> str:
        """Convert or compare schedule time values.
        
        Args:
            minutes (_type_): Minutes used by this function.
        """
        hour = (minutes // 60) % 24
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _time_to_minutes_after(time_text, minimum_minute) -> object:
        """Convert or compare schedule time values.
        
        Args:
            time_text (str): Time value in HH:MM format.
            minimum_minute (_type_): Minimum minute represented in minutes.
        """
        candidate_minute = TimeUtilities._time_to_minutes(time_text)

        while candidate_minute < minimum_minute:
            candidate_minute += 24 * 60

        return candidate_minute
