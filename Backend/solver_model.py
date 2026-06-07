from itertools import combinations

from Backend.configurations import (
    CHARGER_CONFIG,
    BUS_CONFIG,
)


class SolverModelBuilder:
    def _build_model(self) -> None:
        """Handle build model logic.
        """
        for bus in self.scenario["buses"]:
            self._validate_bus(bus)
            self._create_bus_constraints(bus)

        self._add_fixed_schedule_constraints()
        self._add_capacity_blocking_operational_failures()
        self._add_station_capacity_constraints()
        self._add_additional_resource_constraints()
        self._add_objective()


    def _add_fixed_schedule_constraints(self) -> None:
        """Add a CP-SAT constraint to the model.
        """
        fixed_schedule = getattr(self, "fixed_schedule", {})

        if not fixed_schedule:
            return

        for bus_id, fixed in fixed_schedule.items():
            if bus_id not in self.bus_plan_meta:
                continue

            selected_plan = self._matching_fixed_plan(bus_id, fixed.get("plan", []))

            if not selected_plan:
                continue

            self.model.Add(selected_plan["plan_var"] == 1)

            fixed_events = fixed.get("events", [])

            for index, fixed_event in enumerate(fixed_events):
                if index >= len(selected_plan["events"]):
                    continue

                model_event = selected_plan["events"][index]

                if model_event["station_id"] != fixed_event["station_id"]:
                    continue

                self.model.Add(model_event["start"] == fixed_event["start"])
                self.model.Add(model_event["end"] == fixed_event["end"])
                self.model.Add(model_event["wait"] == fixed_event["wait"])

            min_future_start = fixed.get("min_future_start_minute")

            if min_future_start is not None:
                for event in selected_plan["events"][len(fixed_events):]:
                    self.model.Add(event["start"] >= min_future_start)

            final_arrival = fixed.get("final_arrival_minute")

            if final_arrival is not None:
                self.model.Add(self.final_arrival_vars[bus_id] == final_arrival)

    def _matching_fixed_plan(self, bus_id, fixed_plan) -> object:
        """Build or evaluate valid charging plans.
        
        Args:
            bus_id (str): Unique bus identifier.
            fixed_plan (_type_): Fixed plan used by this function.
        """
        fixed_plan_key = tuple(fixed_plan)

        for plan in self.bus_plan_meta[bus_id]:
            if tuple(plan["plan"]) == fixed_plan_key:
                return plan

        return None

    def _create_bus_constraints(self, bus) -> None:
        """Add a CP-SAT constraint to the model.
        
        Args:
            bus (dict): Bus input or output dictionary.
        """
        bus_id = bus["bus_id"]
        route = self.routes[bus["route_id"]]
        departure = self._time_to_minutes(bus["scheduled_departure_time"])
        valid_plans = self._generate_valid_plans(route)

        if not valid_plans:
            raise ValueError(f"No valid charging plan found for {bus_id}")

        plan_vars = []
        plan_wait_totals = []
        plan_charge_counts = []

        self.final_arrival_vars[bus_id] = self.model.NewIntVar(
            0,
            self.horizon,
            f"final_arrival_{bus_id}",
        )

        for plan_index, plan in enumerate(valid_plans):
            plan_var = self.model.NewBoolVar(
                f"select_{bus_id}_plan_{plan_index}",
            )

            plan_vars.append(plan_var)

            events = []
            wait_vars = []
            previous_station = route["station_sequence"][0]
            previous_time = departure

            for station_id in plan:
                start = self.model.NewIntVar(
                    0,
                    self.horizon,
                    f"start_{bus_id}_{plan_index}_{station_id}",
                )

                end = self.model.NewIntVar(
                    0,
                    self.horizon,
                    f"end_{bus_id}_{plan_index}_{station_id}",
                )

                wait = self.model.NewIntVar(
                    0,
                    self.horizon,
                    f"wait_{bus_id}_{plan_index}_{station_id}",
                )

                travel_time = self._travel_time_between(
                    route,
                    previous_station,
                    station_id,
                )

                reached_time = previous_time + travel_time

                self.model.Add(start >= reached_time).OnlyEnforceIf(plan_var)
                self.model.Add(wait == start - reached_time).OnlyEnforceIf(plan_var)
                self.model.Add(wait == 0).OnlyEnforceIf(plan_var.Not())

                wait_vars.append(wait)

                charging_modes = self._create_charging_mode_intervals(
                    bus_id=bus_id,
                    plan_index=plan_index,
                    station_id=station_id,
                    start=start,
                    end=end,
                    plan_var=plan_var,
                )

                events.append({
                    "station_id": station_id,
                    "from_station": previous_station,
                    "travel_time": travel_time,
                    "start": start,
                    "end": end,
                    "wait": wait,
                    "charging_modes": charging_modes,
                })

                previous_station = station_id
                previous_time = end

            arrival = self.model.NewIntVar(
                0,
                self.horizon,
                f"arrival_{bus_id}_{plan_index}",
            )

            final_travel_time = self._travel_time_between(
                route,
                previous_station,
                route["station_sequence"][-1],
            )

            self.model.Add(
                arrival == previous_time + final_travel_time
            ).OnlyEnforceIf(plan_var)

            self.model.Add(
                self.final_arrival_vars[bus_id] == arrival
            ).OnlyEnforceIf(plan_var)

            plan_wait_total = self.model.NewIntVar(
                0,
                self.horizon,
                f"plan_wait_{bus_id}_{plan_index}",
            )

            self.model.Add(plan_wait_total == sum(wait_vars)).OnlyEnforceIf(plan_var)
            self.model.Add(plan_wait_total == 0).OnlyEnforceIf(plan_var.Not())
            plan_wait_totals.append(plan_wait_total)

            plan_charge_count = self.model.NewIntVar(
                0,
                len(self.stations),
                f"charge_count_{bus_id}_{plan_index}",
            )

            self.model.Add(plan_charge_count == len(plan)).OnlyEnforceIf(plan_var)
            self.model.Add(plan_charge_count == 0).OnlyEnforceIf(plan_var.Not())
            plan_charge_counts.append(plan_charge_count)

            self.bus_plan_meta[bus_id].append({
                "plan": plan,
                "plan_var": plan_var,
                "events": events,
            })

        self.model.AddExactlyOne(plan_vars)

        self.bus_wait_vars[bus_id] = self.model.NewIntVar(
            0,
            self.horizon,
            f"total_wait_{bus_id}",
        )

        self.model.Add(
            self.bus_wait_vars[bus_id] == sum(plan_wait_totals)
        )

        self.bus_charge_count_vars[bus_id] = self.model.NewIntVar(
            0,
            len(self.stations),
            f"total_charge_count_{bus_id}",
        )

        self.model.Add(
            self.bus_charge_count_vars[bus_id] == sum(plan_charge_counts)
        )

        route_distance = self._route_distance(route)

        ideal_travel_time = round(
            (route_distance / BUS_CONFIG["speed_kmph"]) * 60,
        )

        self.bus_arrival_delay_vars[bus_id] = self.model.NewIntVar(
            0,
            self.horizon,
            f"arrival_delay_{bus_id}",
        )

        self.model.Add(
            self.bus_arrival_delay_vars[bus_id]
            == self.final_arrival_vars[bus_id] - departure - ideal_travel_time
        )

    def _create_charging_mode_intervals(
        self,
        bus_id,
        plan_index,
        station_id,
        start,
        end,
        plan_var,
    ) -> object:
        """Create or process CP-SAT charging intervals.
        
        Args:
            bus_id (str): Unique bus identifier.
            plan_index (_type_): Plan index used by this function.
            station_id (str): Charging station identifier.
            start (_type_): Start used by this function.
            end (_type_): End used by this function.
            plan_var (_type_): Plan var used by this function.
        """
        mode_definitions = self._charging_mode_definitions(station_id)
        mode_vars = []
        charging_modes = []

        if len(mode_definitions) == 1 and mode_definitions[0]["mode_type"] == "NORMAL_ALL_TIME":
            mode = mode_definitions[0]

            interval = self.model.NewOptionalIntervalVar(
                start,
                mode["duration_minutes"],
                end,
                plan_var,
                f"interval_{bus_id}_{plan_index}_{station_id}_normal",
            )

            self.station_intervals[station_id].append((interval, 1))

            return [{
                "mode_var": plan_var,
                "mode_type": "NORMAL",
                "operational_failure_id": None,
                "duration_minutes": mode["duration_minutes"],
                "window_start": None,
                "window_end": None,
                "reason": None,
            }]

        for mode_index, mode in enumerate(mode_definitions):
            mode_var = self.model.NewBoolVar(
                f"mode_{bus_id}_{plan_index}_{station_id}_{mode_index}",
            )

            mode_vars.append(mode_var)

            self.model.AddImplication(mode_var, plan_var)

            self.model.Add(
                start >= mode["window_start_minute"]
            ).OnlyEnforceIf(mode_var)

            self.model.Add(
                start <= mode["window_end_minute"] - 1
            ).OnlyEnforceIf(mode_var)

            interval = self.model.NewOptionalIntervalVar(
                start,
                mode["duration_minutes"],
                end,
                mode_var,
                f"interval_{bus_id}_{plan_index}_{station_id}_{mode_index}",
            )

            self.station_intervals[station_id].append((interval, 1))

            if mode["resource_key"]:
                self.additional_resource_intervals[mode["resource_key"]]["capacity"] = mode[
                    "resource_capacity"
                ]

                self.additional_resource_intervals[mode["resource_key"]]["intervals"].append(
                    (interval, 1)
                )

            charging_modes.append({
                "mode_var": mode_var,
                "mode_type": mode["mode_type"],
                "operational_failure_id": mode.get("operational_failure_id"),
                "duration_minutes": mode["duration_minutes"],
                "window_start": self._minutes_to_time(mode["window_start_minute"]),
                "window_end": self._minutes_to_time(mode["window_end_minute"])
                if mode["window_end_minute"] < self.horizon
                else None,
                "reason": mode.get("reason"),
            })

        self.model.Add(sum(mode_vars) == plan_var)

        return charging_modes

    def _charging_mode_definitions(self, station_id) -> object:
        """Handle charging mode definitions logic.
        
        Args:
            station_id (str): Charging station identifier.
        """
        normal_duration = self._normal_charging_time()
        slow_failures = self._slow_charging_operational_failures(station_id)

        if not slow_failures:
            return [{
                "mode_type": "NORMAL_ALL_TIME",
                "duration_minutes": normal_duration,
                "window_start_minute": 0,
                "window_end_minute": self.horizon,
                "resource_key": None,
                "resource_capacity": None,
            }]

        station_charger_count = self.stations[station_id]["charger_count"]
        mode_definitions = []
        cursor = 0

        for failure in slow_failures:
            failure_id = failure["operational_failure_id"]
            start_minute, end_minute = self._failure_window_minutes(failure)

            if cursor < start_minute:
                mode_definitions.append({
                    "mode_type": "NORMAL",
                    "duration_minutes": normal_duration,
                    "window_start_minute": cursor,
                    "window_end_minute": start_minute,
                    "resource_key": None,
                    "resource_capacity": None,
                    "operational_failure_id": None,
                    "reason": None,
                })

            affected_chargers = min(
                failure.get("affected_chargers", station_charger_count),
                station_charger_count,
            )

            normal_chargers_available = station_charger_count - affected_chargers

            slow_duration = (
                failure["charging_duration_minutes"]
                + CHARGER_CONFIG.get("charger_setup_duration_minutes", 0)
            )

            if normal_chargers_available > 0:
                mode_definitions.append({
                    "mode_type": "NORMAL_DURING_SLOW_CHARGING",
                    "duration_minutes": normal_duration,
                    "window_start_minute": start_minute,
                    "window_end_minute": end_minute,
                    "resource_key": (station_id, failure_id, "normal_chargers"),
                    "resource_capacity": normal_chargers_available,
                    "operational_failure_id": failure_id,
                    "reason": failure.get("reason"),
                })

            if affected_chargers > 0:
                mode_definitions.append({
                    "mode_type": "SLOW_CHARGING",
                    "duration_minutes": slow_duration,
                    "window_start_minute": start_minute,
                    "window_end_minute": end_minute,
                    "resource_key": (station_id, failure_id, "slow_chargers"),
                    "resource_capacity": affected_chargers,
                    "operational_failure_id": failure_id,
                    "reason": failure.get("reason"),
                })

            cursor = max(cursor, end_minute)

        if cursor < self.horizon:
            mode_definitions.append({
                "mode_type": "NORMAL",
                "duration_minutes": normal_duration,
                "window_start_minute": cursor,
                "window_end_minute": self.horizon,
                "resource_key": None,
                "resource_capacity": None,
                "operational_failure_id": None,
                "reason": None,
            })

        return mode_definitions

    def _add_capacity_blocking_operational_failures(self) -> None:
        """Apply operational failure logic to the schedule.
        """
        for failure in self._operational_failures():
            failure_type = failure.get("type")

            if failure_type == "STATION_CAPACITY_REDUCTION":
                self._add_station_capacity_reduction(failure)

            elif failure_type == "CHARGER_DOWN":
                self._add_charger_down(failure)

    def _add_station_capacity_reduction(self, failure) -> None:
        """Build or validate station-level scheduling data.
        
        Args:
            failure (dict): Operational failure configuration dictionary.
        """
        station_id = failure["station_id"]

        if station_id not in self.stations:
            raise ValueError(f"Invalid station_id in operational failure: {station_id}")

        configured_chargers = self.stations[station_id]["charger_count"]
        available_chargers = failure["available_chargers"]
        unavailable_chargers = max(0, configured_chargers - available_chargers)

        if unavailable_chargers == 0:
            return

        self._add_station_blocking_interval(
            station_id=station_id,
            failure=failure,
            demand=unavailable_chargers,
            name=f"capacity_reduction_{failure['operational_failure_id']}",
        )

    def _add_charger_down(self, failure) -> None:
        """Build or validate charger availability and assignment data.
        
        Args:
            failure (dict): Operational failure configuration dictionary.
        """
        station_id = failure["station_id"]

        if station_id not in self.stations:
            raise ValueError(f"Invalid station_id in operational failure: {station_id}")

        self._add_station_blocking_interval(
            station_id=station_id,
            failure=failure,
            demand=1,
            name=f"charger_down_{failure['operational_failure_id']}",
        )

    def _add_station_blocking_interval(
        self,
        station_id,
        failure,
        demand,
        name,
    ) -> None:
        """Build or validate station-level scheduling data.
        
        Args:
            station_id (str): Charging station identifier.
            failure (dict): Operational failure configuration dictionary.
            demand (_type_): Demand used by this function.
            name (str): Human-readable name used in output or solver variables.
        """
        start_minute, end_minute = self._failure_window_minutes(failure)
        duration = end_minute - start_minute

        if duration <= 0:
            raise ValueError(f"Invalid operational failure time window for {name}")

        start = self.model.NewIntVar(start_minute, start_minute, f"{name}_start")
        end = self.model.NewIntVar(end_minute, end_minute, f"{name}_end")

        interval = self.model.NewIntervalVar(
            start,
            duration,
            end,
            f"{name}_interval",
        )

        self.station_intervals[station_id].append((interval, demand))

    def _add_station_capacity_constraints(self) -> None:
        """Build or validate station-level scheduling data.
        """
        for station_id, interval_demands in self.station_intervals.items():
            intervals = [interval for interval, _ in interval_demands]
            demands = [demand for _, demand in interval_demands]

            self.model.AddCumulative(
                intervals,
                demands,
                self.stations[station_id]["charger_count"],
            )

    def _add_additional_resource_constraints(self) -> None:
        """Add a CP-SAT constraint to the model.
        """
        for resource in self.additional_resource_intervals.values():
            intervals = [interval for interval, _ in resource["intervals"]]
            demands = [demand for _, demand in resource["intervals"]]

            if intervals:
                self.model.AddCumulative(
                    intervals,
                    demands,
                    resource["capacity"],
                )

    def _add_objective(self) -> None:
        """Build the CP-SAT optimization objective.
        """
        max_bus_wait = self.model.NewIntVar(0, self.horizon, "max_bus_wait")

        self.model.AddMaxEquality(
            max_bus_wait,
            list(self.bus_wait_vars.values()),
        )

        total_network_wait = sum(self.bus_wait_vars.values())
        total_arrival_delay = sum(self.bus_arrival_delay_vars.values())
        total_charging_stops = sum(self.bus_charge_count_vars.values())
        total_final_arrival_time = sum(self.final_arrival_vars.values())
        operator_fairness = self._operator_fairness_penalty()

        self.model.Minimize(
            self._weight("individual_wait_weight") * max_bus_wait
            + self._weight("operator_fairness_weight") * operator_fairness
            + self._weight("network_wait_weight") * total_network_wait
            + self._weight("arrival_delay_weight", 1.0) * total_arrival_delay
            + self._weight("charging_stop_weight", 0.2) * total_charging_stops
            + total_final_arrival_time
        )

    def _operator_fairness_penalty(self) -> object:
        """Handle operator fairness penalty logic.
        """
        operator_wait_vars = []

        for operator_id in self.operators:
            bus_ids = [
                bus["bus_id"]
                for bus in self.scenario["buses"]
                if bus["operator_id"] == operator_id
            ]

            if not bus_ids:
                continue

            operator_wait = self.model.NewIntVar(
                0,
                self.horizon * len(bus_ids),
                f"operator_wait_{operator_id}",
            )

            self.model.Add(
                operator_wait == sum(
                    self.bus_wait_vars[bus_id]
                    for bus_id in bus_ids
                )
            )

            operator_wait_vars.append(operator_wait)

        if len(operator_wait_vars) <= 1:
            return 0

        max_operator_wait = self.model.NewIntVar(
            0,
            self.horizon * len(self.scenario["buses"]),
            "max_operator_wait",
        )

        min_operator_wait = self.model.NewIntVar(
            0,
            self.horizon * len(self.scenario["buses"]),
            "min_operator_wait",
        )

        penalty = self.model.NewIntVar(
            0,
            self.horizon * len(self.scenario["buses"]),
            "operator_fairness_penalty",
        )

        self.model.AddMaxEquality(max_operator_wait, operator_wait_vars)
        self.model.AddMinEquality(min_operator_wait, operator_wait_vars)
        self.model.Add(penalty == max_operator_wait - min_operator_wait)

        return penalty

    def _generate_valid_plans(self, route) -> object:
        """Build or evaluate valid charging plans.
        
        Args:
            route (_type_): Route used by this function.
        """
        charging_stations = [
            station
            for station in route["station_sequence"]
            if station in self.stations
        ]

        valid_plans = []

        for size in range(1, len(charging_stations) + 1):
            for plan in combinations(charging_stations, size):
                ordered_plan = [
                    station
                    for station in route["station_sequence"]
                    if station in plan
                ]

                if self._is_range_valid(route, ordered_plan):
                    valid_plans.append(ordered_plan)

        return valid_plans

    def _is_range_valid(self, route, plan) -> bool:
        """Handle is range valid logic.
        
        Args:
            route (_type_): Route used by this function.
            plan (list[str]): Candidate charging plan for a bus.
        """
        allowed_range = (
            BUS_CONFIG["maximum_range_km"]
            - BUS_CONFIG["minimum_required_range_km"]
        )

        checkpoints = (
            [route["station_sequence"][0]]
            + list(plan)
            + [route["station_sequence"][-1]]
        )

        return all(
            self._distance_between(
                route,
                checkpoints[index],
                checkpoints[index + 1],
            ) <= allowed_range
            for index in range(len(checkpoints) - 1)
        )
