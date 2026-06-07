import json
from collections import defaultdict

from ortools.sat.python import cp_model

from Backend.summary_metrics import build_summary

from Backend.configurations import (
    SOLVER_CONFIG,
    ROUTES_CONFIG,
    STATIONS_CONFIG,
    OPERATORS_CONFIG,
    REOPTIMIZATION_CONFIG,
)

from Backend.time_utils import TimeUtilities
from Backend.route_utils import RouteUtilities
from Backend.weight_utils import WeightUtilities
from Backend.failure_handler import FailureHandler
from Backend.solver_model import SolverModelBuilder
from Backend.output_builder import ScheduleOutputBuilder
from Backend.reoptimization_runner import ReoptimizationRunner


class BusChargingScheduler(
    TimeUtilities,
    RouteUtilities,
    WeightUtilities,
    FailureHandler,
    SolverModelBuilder,
    ScheduleOutputBuilder,
    ReoptimizationRunner,
):
    def __init__(
        self,
        scenario_path,
        ui_weights=None,
        failure_filter=None,
        fixed_schedule=None,
        reoptimization_enabled=True,
        reoptimization_phase=None,
    ) -> None:
        """Initialize runtime state for this scheduler component.
        
        Args:
            scenario_path (str): Path to the selected scenario JSON file.
            ui_weights (dict | None, optional): Optimization weights selected from the Streamlit UI. Defaults to None.
            failure_filter (list[str] | None, optional): Failure types that should be active in this solve. Defaults to None.
            fixed_schedule (dict | None, optional): Previously committed schedule decisions that must remain unchanged. Defaults to None.
            reoptimization_enabled (bool, optional): Whether event-driven re-optimization is enabled. Defaults to True.
            reoptimization_phase (str | None, optional): Name of the current optimization or re-optimization phase. Defaults to None.
        """
        self.scenario_path = scenario_path
        self.scenario = self._load_json(scenario_path)
        self.ui_weights = ui_weights or {}
        self.failure_filter = failure_filter
        self.fixed_schedule = fixed_schedule or {}
        self.reoptimization_config = REOPTIMIZATION_CONFIG
        self.reoptimization_enabled = (
            reoptimization_enabled
            and REOPTIMIZATION_CONFIG.get("enable_event_driven_reoptimization", False)
        )
        self.reoptimization_phase = reoptimization_phase or {}

        self.routes = {
            route["route_id"]: route
            for route in ROUTES_CONFIG
        }

        self.stations = {
            station["station_id"]: station
            for station in STATIONS_CONFIG
        }

        self.operators = {
            operator["operator_id"]: operator
            for operator in OPERATORS_CONFIG
        }

        self.weights = self._get_weights()

        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.horizon = self._calculate_horizon()

        self.bus_wait_vars = {}
        self.bus_charge_count_vars = {}
        self.bus_arrival_delay_vars = {}
        self.final_arrival_vars = {}

        self.bus_plan_meta = defaultdict(list)

        self.station_intervals = defaultdict(list)
        self.additional_resource_intervals = defaultdict(lambda: {
            "capacity": 0,
            "intervals": [],
        })

    def solve(self, include_timeline=False) -> dict:
        """Run the scheduler and return the optimized result.
        
        Args:
            include_timeline (bool, optional): Whether compact timeline data should be included in the result. Defaults to False.
        """
        if self._should_use_event_driven_reoptimization():
            return self._solve_with_event_driven_reoptimization(
                include_timeline=include_timeline,
            )

        return self._solve_static(
            include_timeline=include_timeline,
        )

    def _solve_static(self, include_timeline=False, phase_name=None) -> object:
        """Run a CP-SAT solve step.
        
        Args:
            include_timeline (bool, optional): Whether compact timeline data should be included in the result. Defaults to False.
            phase_name (_type_, optional): Phase name used by this function. Defaults to None.
        """
        self._build_model()
        self._apply_solver_config()

        status = self.solver.Solve(self.model)

        if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
            return {
                "status": "NO_SOLUTION",
                "message": "No feasible charging schedule found.",
                "summary": {},
                "bus_timetables": [],
                "station_charging_orders": {},
                "timeline": [] if include_timeline else None,
                "reoptimization_phase": self.reoptimization_phase,
            }

        station_orders = self._build_station_orders()
        bus_timetables = self._build_bus_timetables(station_orders)

        result = {
            "status": "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
            "scenario_id": self.scenario["scenario_id"],
            "scenario_name": self.scenario["scenario_name"],
            "objective_value": self.solver.ObjectiveValue(),
            "solver_wall_time_seconds": round(self.solver.WallTime(), 3),
            "optimization_weights": self.weights,
            "operational_failures_applied": self._operational_failures_summary(),
            "reoptimization_phase": self.reoptimization_phase,
            "summary": build_summary(
                bus_timetables=bus_timetables,
                station_orders=station_orders,
                stations=self.stations,
                solver=self.solver,
                final_arrival_vars=self.final_arrival_vars,
                time_to_minutes=self._time_to_minutes,
                minutes_to_time=self._minutes_to_time,
            ),
            "bus_timetables": bus_timetables,
            "station_charging_orders": self._hide_internal_minutes(station_orders),
        }

        if phase_name:
            result["phase_name"] = phase_name

        if include_timeline:
            result["timeline"] = self._build_compact_timeline(station_orders)

        return result

    def _validate_bus(self, bus) -> None:
        """Validate input data before optimization.
        
        Args:
            bus (dict): Bus input or output dictionary.
        """
        if bus["route_id"] not in self.routes:
            raise ValueError(
                f"Invalid route_id: {bus['route_id']}"
            )

        if bus["operator_id"] not in self.operators:
            raise ValueError(
                f"Invalid operator_id: {bus['operator_id']}"
            )

    def _apply_solver_config(self) -> None:
        """Run a CP-SAT solve step.
        """
        self.solver.parameters.max_time_in_seconds = SOLVER_CONFIG[
            "max_solve_time_seconds"
        ]

        self.solver.parameters.num_search_workers = SOLVER_CONFIG[
            "num_search_workers"
        ]

        self.solver.parameters.log_search_progress = SOLVER_CONFIG[
            "log_search_progress"
        ]

        self.solver.parameters.random_seed = SOLVER_CONFIG.get(
            "random_seed",
            42,
        )

    @staticmethod
    def _load_json(file_path) -> object:
        """Load required data for the scheduler.
        
        Args:
            file_path (str): Path of the file being loaded or written.
        """
        with open(file_path, "r") as file:
            return json.load(file)


if __name__ == "__main__":
    scheduler = BusChargingScheduler(
        "Backend/scenarios/scenario_01_even_spacing.json",
    )

    result = scheduler.solve(include_timeline=True)

    print(json.dumps(result, indent=2))
