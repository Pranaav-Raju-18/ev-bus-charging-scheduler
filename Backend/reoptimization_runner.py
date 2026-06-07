class ReoptimizationRunner:
    def _should_use_event_driven_reoptimization(self) -> bool:
        """Handle event-driven schedule re-optimization.
        """
        if not self.reoptimization_enabled:
            return False

        if not self._include_operational_failures():
            return False

        return bool(self._dynamic_operational_failures())

    def _solve_with_event_driven_reoptimization(self, include_timeline=False) -> object:
        """Run a CP-SAT solve step.
        
        Args:
            include_timeline (bool, optional): Whether compact timeline data should be included in the result. Defaults to False.
        """
        planned_ids = {
            failure["operational_failure_id"]
            for failure in self._planned_operational_failures()
        }

        original_failure_filter = self.failure_filter
        self.failure_filter = {"operational_failure_ids": planned_ids}

        current_result = self._solve_static(
            include_timeline=include_timeline,
            phase_name="Initial CP-SAT plan with planned failures only",
        )

        self.failure_filter = original_failure_filter

        if current_result["status"] == "NO_SOLUTION":
            return current_result

        phases = [{
            "phase": "initial_plan",
            "trigger_time": None,
            "triggered_failure": None,
            "active_failure_ids": sorted(planned_ids),
            "frozen_decision_count": 0,
            "status": current_result["status"],
            "total_wait_minutes": current_result["summary"].get("total_wait_minutes", 0),
            "solver_wall_time_seconds": current_result.get("solver_wall_time_seconds", 0),
        }]

        active_dynamic_ids = set()

        for failure in self._dynamic_operational_failures():
            failure_start_minute, _ = self._failure_window_minutes(failure)
            active_dynamic_ids.add(failure["operational_failure_id"])
            active_failure_ids = planned_ids | active_dynamic_ids
            fixed_schedule = self._build_fixed_schedule(
                result=current_result,
                freeze_minute=failure_start_minute,
            )

            next_scheduler = self.__class__(
                scenario_path=self.scenario_path,
                ui_weights=self.ui_weights,
                failure_filter={"operational_failure_ids": active_failure_ids},
                fixed_schedule=fixed_schedule,
                reoptimization_enabled=False,
                reoptimization_phase={
                    "triggered_failure": failure,
                    "trigger_minute": failure_start_minute,
                },
            )

            next_result = next_scheduler._solve_static(
                include_timeline=include_timeline,
                phase_name=f"Re-optimized after {failure['operational_failure_id']}",
            )

            phases.append({
                "phase": "reoptimized_plan",
                "trigger_time": self._minutes_to_time(failure_start_minute),
                "trigger_minute": failure_start_minute,
                "triggered_failure": {
                    "operational_failure_id": failure["operational_failure_id"],
                    "type": failure["type"],
                    "station_id": failure.get("station_id"),
                    "charger_id": failure.get("charger_id"),
                    "reason": failure.get("reason"),
                },
                "active_failure_ids": sorted(active_failure_ids),
                "frozen_decision_count": self._count_frozen_decisions(fixed_schedule),
                "status": next_result["status"],
                "total_wait_minutes": next_result.get("summary", {}).get("total_wait_minutes", 0),
                "solver_wall_time_seconds": next_result.get("solver_wall_time_seconds", 0),
            })

            if next_result["status"] == "NO_SOLUTION":
                current_result["reoptimization_summary"] = self._reoptimization_summary(
                    phases=phases,
                    final_strategy="kept_previous_feasible_plan_because_reoptimization_failed",
                )
                return current_result

            current_result = next_result

        current_result["reoptimization_summary"] = self._reoptimization_summary(
            phases=phases,
            final_strategy="event_driven_cp_sat_reoptimization",
        )
        current_result["operational_failures_applied"] = self._operational_failures_summary()
        return current_result

    def _planned_operational_failures(self) -> object:
        """Apply operational failure logic to the schedule.
        """
        planned_types = set(self.reoptimization_config.get(
            "planned_failure_types",
            ["STATION_CAPACITY_REDUCTION"],
        ))

        return [
            failure
            for failure in self._all_enabled_operational_failures()
            if failure.get("type") in planned_types
        ]

    def _dynamic_operational_failures(self) -> list:
        """Apply operational failure logic to the schedule.
        """
        dynamic_types = set(self.reoptimization_config.get(
            "dynamic_failure_types",
            ["CHARGER_DOWN", "SLOW_CHARGING"],
        ))

        return sorted(
            [
                failure
                for failure in self._all_enabled_operational_failures()
                if failure.get("type") in dynamic_types
            ],
            key=lambda failure: self._failure_window_minutes(failure)[0],
        )

    def _build_fixed_schedule(self, result, freeze_minute) -> object:
        """Handle build fixed schedule logic.
        
        Args:
            result (dict): Final scheduler result dictionary.
            freeze_minute (_type_): Freeze minute represented in minutes.
        """
        fixed_schedule = {}

        for bus in result.get("bus_timetables", []):
            departure_minute = self._time_to_minutes(bus["departure_time"])
            final_arrival_minute = self._time_to_minutes_after(
                bus["final_arrival_time"],
                departure_minute,
            )

            if departure_minute > freeze_minute:
                continue

            fixed_events = []

            for event in bus.get("charging_events", []):
                started_at_minute = self._time_to_minutes_after(
                    event["started_at"],
                    departure_minute,
                )
                ended_at_minute = self._time_to_minutes_after(
                    event["ended_at"],
                    started_at_minute,
                )
                reached_at_minute = self._time_to_minutes_after(
                    event["reached_at"],
                    departure_minute,
                )

                if started_at_minute < freeze_minute:
                    fixed_events.append({
                        "station_id": event["station_id"],
                        "start": started_at_minute,
                        "end": ended_at_minute,
                        "wait": started_at_minute - reached_at_minute,
                    })

            fixed_schedule[bus["bus_id"]] = {
                "plan": list(bus["charging_plan"]),
                "events": fixed_events,
                "min_future_start_minute": freeze_minute,
                "final_arrival_minute": final_arrival_minute
                if final_arrival_minute <= freeze_minute
                else None,
            }

        return fixed_schedule

    def _count_frozen_decisions(self, fixed_schedule) -> object:
        """Handle count frozen decisions logic.
        
        Args:
            fixed_schedule (dict | None): Previously committed schedule decisions that must remain unchanged.
        """
        return sum(
            1 + len(details.get("events", []))
            for details in fixed_schedule.values()
        )

    def _reoptimization_summary(self, phases, final_strategy) -> dict:
        """Build summary metrics from the schedule.
        
        Args:
            phases (_type_): Phases used by this function.
            final_strategy (_type_): Final strategy used by this function.
        """
        dynamic_failures = self._dynamic_operational_failures()

        return {
            "enabled": True,
            "strategy": final_strategy,
            "description": (
                "Initial CP-SAT solve considers planned failures only. "
                "When CHARGER_DOWN or SLOW_CHARGING reaches its configured start time, "
                "completed decisions are frozen and CP-SAT re-solves the remaining schedule."
            ),
            "planned_failure_types": self.reoptimization_config.get(
                "planned_failure_types",
                ["STATION_CAPACITY_REDUCTION"],
            ),
            "dynamic_failure_types": self.reoptimization_config.get(
                "dynamic_failure_types",
                ["CHARGER_DOWN", "SLOW_CHARGING"],
            ),
            "dynamic_failures_processed": len(dynamic_failures),
            "phases": phases,
        }
