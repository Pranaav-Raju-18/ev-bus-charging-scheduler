from collections import defaultdict

from Backend.event_queue import EventQueue


class ScheduleOutputBuilder:
    def _build_bus_timetables(self, station_orders) -> object:
        """Convert or compare schedule time values.
        
        Args:
            station_orders (dict): Station-wise charging order output.
        """
        charger_map = self._charger_lookup(station_orders)
        bus_timetables = []

        for bus in self.scenario["buses"]:
            bus_id = bus["bus_id"]
            route = self.routes[bus["route_id"]]
            selected_plan = self._selected_plan(bus_id)

            current_time = self._time_to_minutes(
                bus["scheduled_departure_time"],
            )

            charging_events = []

            for event in selected_plan["events"]:
                reached_at = current_time + event["travel_time"]
                start = self.solver.Value(event["start"])
                end = self.solver.Value(event["end"])
                station_id = event["station_id"]
                selected_mode = self._selected_charging_mode(event)

                charging_events.append({
                    "station_id": station_id,
                    "charger_id": charger_map[(bus_id, station_id, start)],
                    "reached_at": self._minutes_to_time(reached_at),
                    "started_at": self._minutes_to_time(start),
                    "ended_at": self._minutes_to_time(end),
                    "wait_minutes": self.solver.Value(event["wait"]),
                    "charging_mode": selected_mode["mode_type"],
                    "charger_blocked_minutes": selected_mode["duration_minutes"],
                    "operational_failure_id": selected_mode["operational_failure_id"],
                    "operational_failure_reason": selected_mode["reason"],
                })

                current_time = end

            bus_timetables.append({
                "bus_id": bus_id,
                "operator_id": bus["operator_id"],
                "route_id": bus["route_id"],
                "origin": route["station_sequence"][0],
                "destination": route["station_sequence"][-1],
                "departure_time": bus["scheduled_departure_time"],
                "charging_plan": selected_plan["plan"],
                "charging_events": charging_events,
                "total_wait_minutes": self.solver.Value(
                    self.bus_wait_vars[bus_id],
                ),
                "total_charging_stops": self.solver.Value(
                    self.bus_charge_count_vars[bus_id],
                ),
                "arrival_delay_minutes": self.solver.Value(
                    self.bus_arrival_delay_vars[bus_id],
                ),
                "final_arrival_time": self._minutes_to_time(
                    self.solver.Value(self.final_arrival_vars[bus_id]),
                ),
            })

        return bus_timetables

    def _build_station_orders(self) -> object:
        """Build or validate station-level scheduling data.
        """
        station_orders = defaultdict(list)

        for bus in self.scenario["buses"]:
            selected_plan = self._selected_plan(bus["bus_id"])

            for event in selected_plan["events"]:
                start = self.solver.Value(event["start"])
                end = self.solver.Value(event["end"])
                selected_mode = self._selected_charging_mode(event)

                station_orders[event["station_id"]].append({
                    "bus_id": bus["bus_id"],
                    "operator_id": bus["operator_id"],
                    "charging_started_at": self._minutes_to_time(start),
                    "charging_ended_at": self._minutes_to_time(end),
                    "charging_started_at_minute": start,
                    "charging_ended_at_minute": end,
                    "wait_minutes": self.solver.Value(event["wait"]),
                    "charging_mode": selected_mode["mode_type"],
                    "charger_blocked_minutes": selected_mode["duration_minutes"],
                    "operational_failure_id": selected_mode["operational_failure_id"],
                    "operational_failure_reason": selected_mode["reason"],
                })

        sorted_orders = {
            station_id: sorted(
                events,
                key=lambda event: event["charging_started_at_minute"],
            )
            for station_id, events in station_orders.items()
        }

        return self._assign_charger_ids(sorted_orders)

    def _assign_charger_ids(self, station_orders) -> object:
        """Build or validate charger availability and assignment data.
        
        Args:
            station_orders (dict): Station-wise charging order output.
        """
        charger_available_at = {
            station_id: {
                f"{station_id}-{charger_number}": 0
                for charger_number in range(
                    1,
                    self.stations[station_id]["charger_count"] + 1,
                )
            }
            for station_id in self.stations
        }

        unavailable_windows = self._charger_unavailable_windows()

        for station_id, events in station_orders.items():
            for event in events:
                start_minute = event["charging_started_at_minute"]
                end_minute = event["charging_ended_at_minute"]

                candidate_chargers = sorted(
                    charger_available_at[station_id],
                    key=lambda charger_id: charger_available_at[station_id][charger_id],
                )

                assigned_charger = None

                for charger_id in candidate_chargers:
                    if charger_available_at[station_id][charger_id] > start_minute:
                        continue

                    if self._charger_has_conflict(
                        charger_id,
                        start_minute,
                        end_minute,
                        unavailable_windows,
                    ):
                        continue

                    assigned_charger = charger_id
                    break

                if assigned_charger is None:
                    raise ValueError(
                        f"No available physical charger found at station {station_id} "
                        f"from {self._minutes_to_time(start_minute)} "
                        f"to {self._minutes_to_time(end_minute)}. "
                        "This means the station-level CP-SAT capacity and physical charger assignment are inconsistent."
                    )

                event["charger_id"] = assigned_charger
                charger_available_at[station_id][assigned_charger] = end_minute

        return station_orders

    def _selected_charging_mode(self, event) -> object:
        """Handle selected charging mode logic.
        
        Args:
            event (_type_): Event used by this function.
        """
        return next(
            mode
            for mode in event["charging_modes"]
            if self.solver.Value(mode["mode_var"]) == 1
        )

    def _selected_plan(self, bus_id) -> object:
        """Build or evaluate valid charging plans.
        
        Args:
            bus_id (str): Unique bus identifier.
        """
        return next(
            plan
            for plan in self.bus_plan_meta[bus_id]
            if self.solver.Value(plan["plan_var"]) == 1
        )

    def _charger_lookup(self, station_orders) -> object:
        """Build or validate charger availability and assignment data.
        
        Args:
            station_orders (dict): Station-wise charging order output.
        """
        return {
            (
                event["bus_id"],
                station_id,
                event["charging_started_at_minute"],
            ): event["charger_id"]
            for station_id, events in station_orders.items()
            for event in events
        }

    def _charging_session_id(self, bus_id, station_id, charger_id, start_minute) -> str:
        """Handle charging session id logic.
        
        Args:
            bus_id (str): Unique bus identifier.
            station_id (str): Charging station identifier.
            charger_id (str): Physical charger identifier.
            start_minute (int): Start time represented as timeline minutes.
        """
        return f"{bus_id}_{station_id}_{charger_id}_{start_minute}"

    def _build_compact_timeline(self, station_orders) -> object:
        """Convert or compare schedule time values.
        
        Args:
            station_orders (dict): Station-wise charging order output.
        """
        queue = EventQueue()

        for station_id, events in station_orders.items():
            for event in events:
                session_id = self._charging_session_id(
                    event["bus_id"],
                    station_id,
                    event["charger_id"],
                    event["charging_started_at_minute"],
                )

                queue.push(
                    event["charging_started_at_minute"],
                    "CHARGING_STARTED",
                    {
                        "bus_id": event["bus_id"],
                        "operator_id": event["operator_id"],
                        "station_id": station_id,
                        "charger_id": event["charger_id"],
                        "charging_session_id": session_id,
                        "end_time": event["charging_ended_at"],
                        "wait_minutes": event["wait_minutes"],
                        "charging_mode": event["charging_mode"],
                        "operational_failure_id": event["operational_failure_id"],
                    },
                )

                queue.push(
                    event["charging_ended_at_minute"],
                    "CHARGING_COMPLETED",
                    {
                        "bus_id": event["bus_id"],
                        "station_id": station_id,
                        "charger_id": event["charger_id"],
                        "charging_session_id": session_id,
                    },
                )

        timeline = []

        while queue.has_events():
            minute, events = queue.pop_next_batch()

            timeline.append({
                "minute": minute,
                "time": self._minutes_to_time(minute),
                "events": [
                    {
                        "event_type": event_type,
                        **payload,
                    }
                    for event_type, payload in events
                ],
            })

        return timeline

    def _hide_internal_minutes(self, station_orders) -> object:
        """Convert or compare minute-based timeline values.
        
        Args:
            station_orders (dict): Station-wise charging order output.
        """
        return {
            station_id: [
                {
                    "bus_id": event["bus_id"],
                    "operator_id": event["operator_id"],
                    "charger_id": event["charger_id"],
                    "charging_started_at": event["charging_started_at"],
                    "charging_ended_at": event["charging_ended_at"],
                    "wait_minutes": event["wait_minutes"],
                    "charging_mode": event["charging_mode"],
                    "charger_blocked_minutes": event["charger_blocked_minutes"],
                    "operational_failure_id": event["operational_failure_id"],
                    "operational_failure_reason": event["operational_failure_reason"],
                }
                for event in events
            ]
            for station_id, events in station_orders.items()
        }
