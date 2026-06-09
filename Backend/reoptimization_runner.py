"""Event-driven re-optimization for dynamic operational failures.

Flow:
  1. Solve once with only the planned failures (known up front).
  2. For each dynamic failure, in time order: when its start time is reached,
     freeze every decision already made before then and re-solve the rest with
     that failure now active.

The core Scheduler is reused unchanged; only its inputs (active failures and
frozen decisions) differ between phases. With failures disabled this collapses
to a single normal solve.
"""

from Backend.failure_handler import Failures
from Backend.scheduler import Scheduler
from Backend.time_utils import TimeUtils


class Reoptimizer:
    """Runs the initial solve plus a re-solve per dynamic failure."""

    @staticmethod
    def run(scenario):
        """Produce a schedule, re-optimizing for each dynamic failure.

        Args:
            scenario (Scenario): The scenario to schedule.

        Returns:
            dict: The final schedule (same shape as Scheduler.solve) plus a
                'phases' list describing each solve step.
        """
        active = Failures.all()
        planned = Failures.planned(active)
        dynamic = Failures.dynamic(active)

        result = Scheduler(scenario, active_failures=planned).solve()
        phases = [Reoptimizer._phase("initial", None, None, result)]

        applied = list(planned)
        for failure in dynamic:
            if result["status"] == "NO_SOLUTION":
                break
            trigger, _ = Failures.window(failure)
            applied.append(failure)
            frozen = Reoptimizer._freeze(result, trigger)
            result = Scheduler(scenario, active_failures=applied, frozen=frozen).solve()
            phases.append(Reoptimizer._phase("reoptimized", trigger, failure, result))

        result["phases"] = phases
        return result

    @staticmethod
    def _phase(name, trigger, failure, result):
        """Summarize one solve step for the UI.

        Args:
            name (str): 'initial' or 'reoptimized'.
            trigger (int | None): Minute the re-solve was triggered, if any.
            failure (dict | None): The failure that triggered the re-solve.
            result (dict): The schedule produced by this step.

        Returns:
            dict: A compact phase summary.
        """
        return {
            "phase": name,
            "trigger_time": TimeUtils.to_clock(trigger) if trigger is not None else None,
            "failure_id": failure["id"] if failure else None,
            "failure_type": failure["type"] if failure else None,
            "status": result["status"],
            "total_wait_minutes": result["total_wait_minutes"],
        }

    @staticmethod
    def _freeze(result, freeze_minute):
        """Capture decisions that happen before the freeze time.

        Args:
            result (dict): The latest schedule.
            freeze_minute (int): Minute at which the new failure begins.

        Returns:
            dict: Per-bus committed decisions keyed by bus_id.
        """
        frozen = {}
        for bus in result["buses"]:
            if bus["departure_minute"] > freeze_minute:
                continue
            started = [
                {"station": charge["station"], "start": charge["start_minute"]}
                for charge in bus["charges"]
                if charge["start_minute"] < freeze_minute
            ]
            frozen[bus["bus_id"]] = {
                "plan": bus["plan"],
                "events": started,
                "freeze_minute": freeze_minute,
            }
        return frozen
