"""Route geometry: distances, travel times and feasible charging plans.

A "charging plan" is the ordered set of stations a bus charges at. Because a
bus can only drive BATTERY_RANGE_KM between charges, only some station
combinations are valid. RouteMap returns the smallest valid combinations,
since any extra charge only adds load to the shared chargers.
"""

from itertools import combinations

from Backend.configurations import STATIONS, SPEED_KMPH, BATTERY_RANGE_KM


class RouteMap:
    """Stateless helpers that read a route definition (see config.ROUTES)."""

    @staticmethod
    def cumulative_km(route):
        """Distance of every stop from the route's origin.

        Args:
            route (dict): Route with 'stops' (list[str]) and 'segment_km'
                (list[int]).

        Returns:
            dict[str, int]: Stop name -> kilometres from the origin.
        """
        distance = 0
        result = {route["stops"][0]: 0}
        for index, segment in enumerate(route["segment_km"]):
            distance += segment
            result[route["stops"][index + 1]] = distance
        return result

    @staticmethod
    def distance_km(route, start_stop, end_stop):
        """Kilometres between two stops on the same route.

        Args:
            route (dict): Route definition.
            start_stop (str): Name of the earlier stop.
            end_stop (str): Name of the later stop.

        Returns:
            int: Distance from start_stop to end_stop in km.
        """
        cumulative = RouteMap.cumulative_km(route)
        return cumulative[end_stop] - cumulative[start_stop]

    @staticmethod
    def travel_minutes(route, start_stop, end_stop):
        """Driving time between two stops at the constant speed.

        Args:
            route (dict): Route definition.
            start_stop (str): Name of the earlier stop.
            end_stop (str): Name of the later stop.

        Returns:
            int: Minutes to drive from start_stop to end_stop.
        """
        km = RouteMap.distance_km(route, start_stop, end_stop)
        return round(km / SPEED_KMPH * 60)

    @staticmethod
    def charging_plans(route):
        """Smallest charging-station sets that keep the bus within range.

        Args:
            route (dict): Route definition.

        Returns:
            list[list[str]]: Each inner list is an ordered charging plan; all
                returned plans use the same (minimum) number of charges.
        """
        stations = [stop for stop in route["stops"] if stop in STATIONS]

        feasible = []
        for size in range(1, len(stations) + 1):
            for combo in combinations(stations, size):
                plan = [stop for stop in route["stops"] if stop in combo]
                if RouteMap._within_range(route, plan):
                    feasible.append(plan)
            if feasible:                 # stop at the first size that works
                break
        return feasible

    @staticmethod
    def _within_range(route, plan):
        """Check that no leg of a plan exceeds the battery range.

        Args:
            route (dict): Route definition.
            plan (list[str]): Ordered charging stops between origin and end.

        Returns:
            bool: True if every leg is within BATTERY_RANGE_KM.
        """
        checkpoints = [route["stops"][0]] + plan + [route["stops"][-1]]
        return all(
            RouteMap.distance_km(route, checkpoints[i], checkpoints[i + 1])
            <= BATTERY_RANGE_KM
            for i in range(len(checkpoints) - 1)
        )
