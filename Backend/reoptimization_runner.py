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
from Backend.event_queue import charge_duration


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
            frozen = Reoptimizer._freeze(result, failure)
            candidate = Scheduler(
                scenario, active_failures=applied + [failure], frozen=frozen).solve()
            phases.append(Reoptimizer._phase("reoptimized", trigger, failure, candidate))

            if candidate["status"] == "NO_SOLUTION":
                # This failure could not be absorbed; keep the last feasible plan.
                break
            applied.append(failure)
            result = candidate

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
    def _freeze(result, failure):
        """Capture each bus's committed decisions when a failure triggers.

        A bus keeps the charges it has already finished, and any charge in
        progress at a station other than the failed one. The single bus that is
        mid-charge at the failed station when a CHARGER_DOWN hits stays pinned to
        that station but is held until the charger returns - it "pauses there"
        and charges once the charger is back online. Everything a bus has not yet
        started is left free, so the solver can re-route and re-time it around
        the failure.

        Args:
            result (dict): The latest schedule.
            failure (dict): The failure being injected (carries its type,
                station and time window).

        Returns:
            dict: Per-bus committed decisions keyed by bus_id, each with the
                pinned plan prefix, the fixed charge starts and the earliest
                minute any remaining charge may begin.
        """
        station = failure.get("station")
        charger_down = failure.get("type") == "CHARGER_DOWN"
        window_start, window_end = Failures.window(failure)

        frozen = {}
        for bus in result["buses"]:
            if bus["departure_minute"] > window_start:
                continue

            pinned_stations = []
            fixed_events = []
            future_min_start = window_start

            for charge in bus["charges"]:
                start = charge["start_minute"]
                end = start + charge_duration(charge["charge_start"], charge["charge_end"])

                if end <= window_start:
                    # Charge already finished - committed, cannot be undone.
                    pinned_stations.append(charge["station"])
                    fixed_events.append({"station": charge["station"], "start": start})
                    continue

                if start < window_start:
                    # Charge in progress when the failure hits.
                    pinned_stations.append(charge["station"])
                    if charger_down and charge["station"] == station:
                        # Paused: keep the bus at this charger, but let it charge
                        # only once the charger comes back online.
                        future_min_start = window_end
                    else:
                        fixed_events.append({"station": charge["station"], "start": start})

                # This charge and everything after it is re-decided.
                break

            if pinned_stations:
                frozen[bus["bus_id"]] = {
                    "pinned_stations": pinned_stations,
                    "fixed_events": fixed_events,
                    "future_min_start": future_min_start,
                }

        return frozen
