"""Loading and validating a scenario.

A scenario is the *demand*: which buses run, for which operator, on which
route, and when they depart. The fixed world (route, stations, chargers)
lives in config.py, so a scenario file stays small.
"""

import json

from Backend.configurations import ROUTES, OPERATORS, WEIGHTS


class Scenario:
    """One scheduling situation read from a scenario JSON file."""

    def __init__(self, data):
        """Wrap parsed scenario data and expose the fields the engine needs.

        Args:
            data (dict): Parsed scenario JSON (see Scenario.load).
        """
        self.id = data["scenario_id"]
        self.name = data["scenario_name"]
        self.buses = data["buses"]
        self.weights = Scenario._resolve_weights(data)

    @staticmethod
    def load(path):
        """Read and validate a scenario JSON file.

        Args:
            path (str): Filesystem path to the scenario JSON.

        Returns:
            Scenario: A validated scenario ready to schedule.
        """
        with open(path) as handle:
            scenario = Scenario(json.load(handle))
        scenario._validate()
        return scenario

    def _validate(self):
        """Ensure every bus references a known route and operator.

        Raises:
            ValueError: If a bus has an unknown route_id or operator_id.
        """
        for bus in self.buses:
            if bus["route_id"] not in ROUTES:
                raise ValueError(f"Unknown route_id: {bus['route_id']}")
            if bus["operator_id"] not in OPERATORS:
                raise ValueError(f"Unknown operator_id: {bus['operator_id']}")

    @staticmethod
    def _resolve_weights(data):
        """Merge the default weights with any per-scenario overrides.

        Args:
            data (dict): Parsed scenario JSON; may carry a 'weights' object.

        Returns:
            dict[str, float]: Final weights keyed by 'individual', 'operator'
                and 'network'.
        """
        weights = dict(WEIGHTS)
        weights.update(data.get("weights", {}))
        return weights
