from Backend.configurations import BUS_CONFIG


class RouteUtilities:
    def _distance_between(self, route, from_station, to_station) -> object:
        """Calculate distance-related values.
        
        Args:
            route (_type_): Route used by this function.
            from_station (_type_): From station used by this function.
            to_station (_type_): To station used by this function.
        """
        cumulative = self._cumulative_distance(route)
        return cumulative[to_station] - cumulative[from_station]

    def _travel_time_between(self, route, from_station, to_station) -> object:
        """Convert or compare schedule time values.
        
        Args:
            route (_type_): Route used by this function.
            from_station (_type_): From station used by this function.
            to_station (_type_): To station used by this function.
        """
        distance = self._distance_between(route, from_station, to_station)
        return round((distance / BUS_CONFIG["speed_kmph"]) * 60)

    def _cumulative_distance(self, route) -> object:
        """Calculate distance-related values.
        
        Args:
            route (_type_): Route used by this function.
        """
        total_distance = 0
        cumulative = {route["station_sequence"][0]: 0}

        for segment in route["station_distances_in_km"]:
            total_distance += segment["distance_km"]
            cumulative[segment["to_station"]] = total_distance

        return cumulative

    def _route_distance(self, route) -> object:
        """Calculate route, station, or distance information.
        
        Args:
            route (_type_): Route used by this function.
        """
        return sum(
            segment["distance_km"]
            for segment in route["station_distances_in_km"]
        )

    def _calculate_horizon(self) -> object:
        """Handle calculate horizon logic.
        """
        latest_departure = max(
            self._time_to_minutes(bus["scheduled_departure_time"])
            for bus in self.scenario["buses"]
        )

        max_route_distance = max(
            self._route_distance(route)
            for route in self.routes.values()
        )

        route_time = round(
            (max_route_distance / BUS_CONFIG["speed_kmph"]) * 60
        )

        max_charging_time = len(self.stations) * self._max_charging_time()

        latest_operational_failure_end = max(
            [
                self._failure_window_minutes(failure)[1]
                for failure in self._operational_failures()
                if "end_time" in failure
            ]
            + [0]
        )

        waiting_buffer = 300

        return max(
            latest_departure + route_time + max_charging_time + waiting_buffer,
            latest_operational_failure_end + route_time + max_charging_time + waiting_buffer,
        )
