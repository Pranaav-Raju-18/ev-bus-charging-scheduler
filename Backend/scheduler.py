"""CP-SAT scheduler: choose each bus's charging plan and the charger order.

The model is deliberately small:
  1. every bus picks exactly one feasible charging plan,
  2. each charge occupies the station's charger for its duration,
  3. AddCumulative enforces the hard rule (only N chargers per station),
  4. the objective is the weighted sum of the three soft rules.

Operational failures, when active, only change inputs the model already uses:
how many chargers a station has during a window, and how long a charge takes.
The model structure stays the same.
"""

from ortools.sat.python import cp_model

from Backend.configurations import ROUTES, STATIONS, OPERATORS, SOLVER
from Backend.route_utils import RouteMap
from Backend.time_utils import TimeUtils
from Backend.failure_handler import Failures


class Scheduler:
    """Builds and solves the charging schedule for one scenario."""

    def __init__(self, scenario, active_failures=None, frozen=None):
        """Create a scheduler.

        Args:
            scenario (Scenario): Demand and weights to schedule.
            active_failures (list[dict] | None): Failures in force for this
                solve. Defaults to none.
            frozen (dict | None): Already-committed decisions to keep fixed
                during re-optimization, keyed by bus_id. Defaults to none.
        """
        self.scenario = scenario
        self.weights = scenario.weights
        self.active_failures = active_failures or []
        self.frozen = frozen or {}

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.horizon = self._horizon()

        self.options = {}        # bus_id -> list of plan-option dicts
        self.bus_wait = {}       # bus_id -> IntVar (total wait)
        self.charger_use = {station: [] for station in STATIONS}

    def solve(self):
        """Build the model, solve it and return the schedule.

        Returns:
            dict: {status, total_wait_minutes, buses, stations, ...}. 'buses'
                is the per-bus timetable; 'stations' is the per-station order.
        """
        for bus in self.scenario.buses:
            self._add_bus(bus)
        self._block_failed_chargers()
        self._limit_chargers()
        self._set_objective()

        self.solver.parameters.max_time_in_seconds = SOLVER["max_seconds"]
        self.solver.parameters.num_search_workers = SOLVER["workers"]
        status = self.solver.Solve(self.model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {
                "status": "NO_SOLUTION",
                "scenario_id": self.scenario.id,
                "scenario_name": self.scenario.name,
                "weights": self.weights,
                "total_wait_minutes": 0,
                "buses": [],
                "stations": {station: [] for station in STATIONS},
            }
        return self._build_result(status)

    def _add_bus(self, bus):
        """Add the variables and constraints for one bus.

        Args:
            bus (dict): Bus record with bus_id, operator_id, route_id and
                departure ('HH:MM').
        """
        bus_id = bus["bus_id"]
        route = ROUTES[bus["route_id"]]
        departure = TimeUtils.to_minutes(bus["departure"])

        picks = []
        plan_waits = []
        options = []

        for index, plan in enumerate(RouteMap.charging_plans(route)):
            pick = self.model.NewBoolVar(f"{bus_id}_plan{index}")
            events, wait_expr = self._add_plan(bus_id, route, departure, plan, pick)
            picks.append(pick)
            plan_waits.append(wait_expr)
            options.append({"pick": pick, "plan": plan, "events": events})

        self.model.AddExactlyOne(picks)

        wait = self.model.NewIntVar(0, self.horizon, f"{bus_id}_wait")
        for pick, wait_expr in zip(picks, plan_waits):
            self.model.Add(wait == wait_expr).OnlyEnforceIf(pick)

        self.bus_wait[bus_id] = wait
        self.options[bus_id] = options
        self._apply_frozen(bus_id)

    def _add_plan(self, bus_id, route, departure, plan, pick):
        """Add charge timing variables for one candidate plan.

        Args:
            bus_id (str): Bus identifier.
            route (dict): Route definition.
            departure (int): Departure time in minutes.
            plan (list[str]): Stations this plan charges at, in order.
            pick (IntVar): Boolean that is 1 when this plan is chosen.

        Returns:
            tuple[list[dict], LinearExpr]: per-station event records and the
                plan's total-wait expression.
        """
        events = []
        wait_terms = []
        previous_stop = route["stops"][0]
        free_again = departure        # when the bus is free to drive on

        for position, station in enumerate(plan):
            arrival = free_again + RouteMap.travel_minutes(route, previous_stop, station)
            earliest = departure + RouteMap.travel_minutes(route, route["stops"][0], station)

            start = self.model.NewIntVar(earliest, self.horizon, f"{bus_id}_{station}_start")
            self.model.Add(start >= arrival).OnlyEnforceIf(pick)

            duration = Failures.charge_minutes(self.active_failures, station)
            interval = self.model.NewOptionalFixedSizeIntervalVar(
                start, duration, pick, f"{bus_id}_{station}_charge")
            self.charger_use[station].append((interval, 1))

            wait_terms.append(start - arrival)
            events.append({"station": station, "start": start, "duration": duration})

            previous_stop = station
            free_again = start + duration

        return events, sum(wait_terms)

    def _apply_frozen(self, bus_id):
        """Pin a bus's already-committed decisions during re-optimization.

        Args:
            bus_id (str): Bus identifier.
        """
        commit = self.frozen.get(bus_id)
        if not commit:
            return

        for option in self.options[bus_id]:
            if option["plan"] != commit["plan"]:
                continue
            self.model.Add(option["pick"] == 1)
            for event, fixed in zip(option["events"], commit["events"]):
                self.model.Add(event["start"] == fixed["start"])
            for event in option["events"][len(commit["events"]):]:
                self.model.Add(event["start"] >= commit["freeze_minute"])

    def _block_failed_chargers(self):
        """Add fixed blocking intervals for active capacity failures."""
        for station in STATIONS:
            for start, end, blocked in Failures.capacity_blocks(self.active_failures, station):
                interval = self.model.NewIntervalVar(
                    start, end - start, end, f"block_{station}_{start}")
                self.charger_use[station].append((interval, blocked))

    def _limit_chargers(self):
        """Enforce the hard rule: a station serves only its chargers at once."""
        for station, uses in self.charger_use.items():
            if not uses:
                continue
            intervals = [interval for interval, _ in uses]
            demands = [demand for _, demand in uses]
            self.model.AddCumulative(intervals, demands, STATIONS[station]["chargers"])

    def _set_objective(self):
        """Minimize the weighted sum of the three soft rules."""
        waits = list(self.bus_wait.values())
        worst_wait = self.model.NewIntVar(0, self.horizon, "worst_wait")
        self.model.AddMaxEquality(worst_wait, waits)

        self.model.Minimize(
            self._weight("individual") * worst_wait
            + self._weight("operator") * self._operator_fairness()
            + self._weight("network") * sum(waits)
        )

    def _weight(self, name):
        """Integer weight for the objective (CP-SAT needs integer coefficients).

        Args:
            name (str): Weight key ('individual', 'operator' or 'network').

        Returns:
            int: The weight scaled by 100 and rounded.
        """
        return round(self.weights[name] * 100)

    def _operator_fairness(self):
        """Spread between the busiest and least-busy operator's total wait.

        Returns:
            IntVar | int: max-minus-min operator wait, or 0 when fewer than
                two operators are present.
        """
        totals = []
        for operator_id in OPERATORS:
            buses = [b["bus_id"] for b in self.scenario.buses if b["operator_id"] == operator_id]
            if not buses:
                continue
            total = self.model.NewIntVar(0, self.horizon * len(buses), f"op_{operator_id}")
            self.model.Add(total == sum(self.bus_wait[b] for b in buses))
            totals.append(total)

        if len(totals) <= 1:
            return 0

        span = self.horizon * len(self.scenario.buses)
        high = self.model.NewIntVar(0, span, "op_high")
        low = self.model.NewIntVar(0, span, "op_low")
        gap = self.model.NewIntVar(0, span, "op_gap")
        self.model.AddMaxEquality(high, totals)
        self.model.AddMinEquality(low, totals)
        self.model.Add(gap == high - low)
        return gap

    def _horizon(self):
        """A safe upper bound on any minute the schedule could reach.

        Returns:
            int: Upper bound used as the domain limit for time variables.
        """
        latest_departure = max(
            TimeUtils.to_minutes(bus["departure"]) for bus in self.scenario.buses)
        longest_route = max(
            RouteMap.travel_minutes(route, route["stops"][0], route["stops"][-1])
            for route in ROUTES.values())
        slack = (len(self.scenario.buses) + len(STATIONS)) * 60
        return latest_departure + longest_route + slack

    def _build_result(self, status):
        """Turn the solved model into per-bus and per-station tables.

        Args:
            status (int): CP-SAT status code (OPTIMAL or FEASIBLE).

        Returns:
            dict: {status, total_wait_minutes, buses, stations, ...}.
        """
        buses = []
        stations = {station: [] for station in STATIONS}
        total_wait = 0

        for bus in self.scenario.buses:
            bus_id = bus["bus_id"]
            route = ROUTES[bus["route_id"]]
            departure = TimeUtils.to_minutes(bus["departure"])
            option = next(o for o in self.options[bus_id]
                          if self.solver.Value(o["pick"]) == 1)

            charges = []
            clock = departure
            previous_stop = route["stops"][0]
            for event in option["events"]:
                station = event["station"]
                reached = clock + RouteMap.travel_minutes(route, previous_stop, station)
                start = self.solver.Value(event["start"])
                end = start + event["duration"]
                charges.append({
                    "station": station,
                    "reached": TimeUtils.to_clock(reached),
                    "charge_start": TimeUtils.to_clock(start),
                    "charge_end": TimeUtils.to_clock(end),
                    "start_minute": start,
                    "wait_minutes": start - reached,
                })
                stations[station].append({
                    "bus_id": bus_id,
                    "operator_id": bus["operator_id"],
                    "charge_start": TimeUtils.to_clock(start),
                    "charge_end": TimeUtils.to_clock(end),
                    "start_minute": start,
                    "wait_minutes": start - reached,
                })
                clock = end
                previous_stop = station

            arrival = clock + RouteMap.travel_minutes(route, previous_stop, route["stops"][-1])
            bus_total_wait = self.solver.Value(self.bus_wait[bus_id])
            total_wait += bus_total_wait
            buses.append({
                "bus_id": bus_id,
                "operator_id": bus["operator_id"],
                "route_id": bus["route_id"],
                "origin": route["stops"][0],
                "destination": route["stops"][-1],
                "departure": bus["departure"],
                "departure_minute": departure,
                "plan": option["plan"],
                "charges": charges,
                "total_wait_minutes": bus_total_wait,
                "arrival": TimeUtils.to_clock(arrival),
            })

        for rows in stations.values():
            rows.sort(key=lambda row: row["start_minute"])

        return {
            "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "scenario_id": self.scenario.id,
            "scenario_name": self.scenario.name,
            "weights": self.weights,
            "total_wait_minutes": total_wait,
            "buses": buses,
            "stations": stations,
        }
