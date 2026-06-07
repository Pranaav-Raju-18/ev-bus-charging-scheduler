from collections import defaultdict


def build_summary(
    bus_timetables,
    station_orders,
    stations,
    solver,
    final_arrival_vars,
    time_to_minutes,
    minutes_to_time,
) -> dict:
    """Build scenario, station, and operator summary metrics.
    
    Args:
        bus_timetables (_type_): Bus timetables used by this function.
        station_orders (dict): Station-wise charging order output.
        stations (_type_): Stations used by this function.
        solver (_type_): OR-Tools CP-SAT solver instance.
        final_arrival_vars (_type_): Final arrival vars used by this function.
        time_to_minutes (_type_): Time to minutes represented in minutes.
        minutes_to_time (_type_): Minutes to time used by this function.
    """
    total_buses = len(bus_timetables)

    if total_buses == 0:
        return _empty_summary()

    total_wait = sum(
        bus["total_wait_minutes"]
        for bus in bus_timetables
    )

    max_wait = max(
        bus["total_wait_minutes"]
        for bus in bus_timetables
    )

    buses_with_wait = sum(
        1
        for bus in bus_timetables
        if bus["total_wait_minutes"] > 0
    )

    total_arrival_delay = sum(
        bus["arrival_delay_minutes"]
        for bus in bus_timetables
    )

    max_arrival_delay = max(
        bus["arrival_delay_minutes"]
        for bus in bus_timetables
    )

    total_charging_stops = sum(
        bus["total_charging_stops"]
        for bus in bus_timetables
    )

    operational_failure_charging_events = sum(
        1
        for bus in bus_timetables
        for event in bus["charging_events"]
        if event["operational_failure_id"]
    )

    slow_charging_events = sum(
        1
        for bus in bus_timetables
        for event in bus["charging_events"]
        if event["charging_mode"] == "SLOW_CHARGING"
    )

    operator_wait = defaultdict(list)

    for bus in bus_timetables:
        operator_wait[bus["operator_id"]].append(
            bus["total_wait_minutes"],
        )

    operator_bus_count = {
        operator_id: len(waits)
        for operator_id, waits in operator_wait.items()
    }

    operator_total_wait = {
        operator_id: sum(waits)
        for operator_id, waits in operator_wait.items()
    }

    operator_average_wait = {
        operator_id: round(sum(waits) / len(waits), 2)
        for operator_id, waits in operator_wait.items()
    }

    operator_max_wait = {
        operator_id: max(waits)
        for operator_id, waits in operator_wait.items()
    }

    operator_fairness_gap = (
        max(operator_average_wait.values()) - min(operator_average_wait.values())
        if operator_average_wait
        else 0
    )

    simulation_start_minute = min(
        time_to_minutes(bus["departure_time"])
        for bus in bus_timetables
    )

    simulation_end_minute = max(
        solver.Value(final_arrival_vars[bus["bus_id"]])
        for bus in bus_timetables
    )

    simulation_duration = simulation_end_minute - simulation_start_minute

    return {
        "total_buses": total_buses,
        "total_wait_minutes": total_wait,
        "average_wait_per_bus": round(total_wait / total_buses, 2),
        "max_bus_wait_minutes": max_wait,
        "buses_with_wait": buses_with_wait,
        "buses_with_wait_percent": round(
            (buses_with_wait / total_buses) * 100,
            2,
        ),
        "total_arrival_delay_minutes": total_arrival_delay,
        "average_arrival_delay_per_bus": round(
            total_arrival_delay / total_buses,
            2,
        ),
        "max_arrival_delay_minutes": max_arrival_delay,
        "total_charging_stops": total_charging_stops,
        "average_charging_stops_per_bus": round(
            total_charging_stops / total_buses,
            2,
        ),
        "operational_failure_charging_events": operational_failure_charging_events,
        "slow_charging_events": slow_charging_events,
        "operator_bus_count": operator_bus_count,
        "operator_total_wait_minutes": operator_total_wait,
        "operator_average_wait_minutes": operator_average_wait,
        "operator_max_wait_minutes": operator_max_wait,
        "operator_fairness_gap_minutes": round(
            operator_fairness_gap,
            2,
        ),
        "station_metrics": _build_station_metrics(
            station_orders,
            stations,
            simulation_duration,
        ),
        "simulation_start_time": minutes_to_time(
            simulation_start_minute,
        ),
        "simulation_end_time": minutes_to_time(
            simulation_end_minute,
        ),
        "simulation_duration_minutes": simulation_duration,
    }


def _build_station_metrics(
    station_orders,
    stations,
    simulation_duration,
) -> object:
    """Build or validate station-level scheduling data.
    
    Args:
        station_orders (dict): Station-wise charging order output.
        stations (_type_): Stations used by this function.
        simulation_duration (_type_): Simulation duration used by this function.
    """
    station_metrics = {}

    for station_id, station in stations.items():
        events = station_orders.get(station_id, [])
        charger_count = station["charger_count"]
        total_sessions = len(events)

        total_wait = sum(
            event["wait_minutes"]
            for event in events
        )

        max_wait = max(
            [event["wait_minutes"] for event in events],
            default=0,
        )

        total_charging_minutes = sum(
            event["charging_ended_at_minute"]
            - event["charging_started_at_minute"]
            for event in events
        )

        slow_charging_sessions = sum(
            1
            for event in events
            if event["charging_mode"] == "SLOW_CHARGING"
        )

        operational_failure_sessions = sum(
            1
            for event in events
            if event["operational_failure_id"]
        )

        available_charger_minutes = (
            charger_count * simulation_duration
            if simulation_duration > 0
            else 0
        )

        utilization_percent = (
            round(
                (total_charging_minutes / available_charger_minutes) * 100,
                2,
            )
            if available_charger_minutes
            else 0
        )

        station_metrics[station_id] = {
            "charger_count": charger_count,
            "total_charging_sessions": total_sessions,
            "slow_charging_sessions": slow_charging_sessions,
            "operational_failure_sessions": operational_failure_sessions,
            "total_wait_minutes": total_wait,
            "average_wait_minutes": round(
                total_wait / total_sessions,
                2,
            ) if total_sessions else 0,
            "max_wait_minutes": max_wait,
            "total_charging_minutes": total_charging_minutes,
            "charger_utilization_percent": utilization_percent,
        }

    return station_metrics


def _empty_summary() -> dict:
    """Build summary metrics from the schedule.
    """
    return {
        "total_buses": 0,
        "total_wait_minutes": 0,
        "average_wait_per_bus": 0,
        "max_bus_wait_minutes": 0,
        "buses_with_wait": 0,
        "buses_with_wait_percent": 0,
        "total_arrival_delay_minutes": 0,
        "average_arrival_delay_per_bus": 0,
        "max_arrival_delay_minutes": 0,
        "total_charging_stops": 0,
        "average_charging_stops_per_bus": 0,
        "operational_failure_charging_events": 0,
        "slow_charging_events": 0,
        "operator_bus_count": {},
        "operator_total_wait_minutes": {},
        "operator_average_wait_minutes": {},
        "operator_max_wait_minutes": {},
        "operator_fairness_gap_minutes": 0,
        "station_metrics": {},
        "simulation_start_time": None,
        "simulation_end_time": None,
        "simulation_duration_minutes": 0,
    }
