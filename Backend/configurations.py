"""Configuration values for routes, chargers, operators, failures, and solver settings."""

CHARGER_CONFIG = {
    "charging_duration_minutes": 25,
    "charging_policy": "charge_to_full",
    "charger_setup_duration_minutes": 0,
}

BUS_CONFIG = {
    "maximum_range_km": 240,
    "speed_kmph": 60,
    "initial_range_km": 240,
    "minimum_required_range_km": 0,
}

OPTIMIZATION_WEIGHTS = {
    "individual_wait_weight": 1.0,
    "operator_fairness_weight": 1.0,
    "network_wait_weight": 1.0,
}

SOLVER_CONFIG = {
    "max_solve_time_seconds": 60,
    "num_search_workers": 8,
    "random_seed": 42,
    "log_search_progress": False,
}

ROUTES_CONFIG = [
    {
        "route_id": "route_01",
        "station_sequence": ["Bengaluru", "A", "B", "C", "D", "Kochi"],
        "station_distances_in_km": [
            {"from_station": "Bengaluru", "to_station": "A", "distance_km": 100},
            {"from_station": "A", "to_station": "B", "distance_km": 120},
            {"from_station": "B", "to_station": "C", "distance_km": 100},
            {"from_station": "C", "to_station": "D", "distance_km": 120},
            {"from_station": "D", "to_station": "Kochi", "distance_km": 100},
        ],
    },
    {
        "route_id": "route_02",
        "station_sequence": ["Kochi", "D", "C", "B", "A", "Bengaluru"],
        "station_distances_in_km": [
            {"from_station": "Kochi", "to_station": "D", "distance_km": 100},
            {"from_station": "D", "to_station": "C", "distance_km": 120},
            {"from_station": "C", "to_station": "B", "distance_km": 100},
            {"from_station": "B", "to_station": "A", "distance_km": 120},
            {"from_station": "A", "to_station": "Bengaluru", "distance_km": 100},
        ],
    },
]

STATIONS_CONFIG = [
    {"station_id": "A", "station_name": "Station A", "charger_count": 1},
    {"station_id": "B", "station_name": "Station B", "charger_count": 1},
    {"station_id": "C", "station_name": "Station C", "charger_count": 1},
    {"station_id": "D", "station_name": "Station D", "charger_count": 1},
]

OPERATORS_CONFIG = [
    {"operator_id": "kpn", "operator_name": "KPN"},
    {"operator_id": "flixbus", "operator_name": "Flixbus"},
    {"operator_id": "freshbus", "operator_name": "Freshbus"},
]

OPERATIONAL_FAILURE_SETTINGS = {
    "include_operational_failures": False,
}

OPERATIONAL_FAILURES = [
    {
        "operational_failure_id": "failure-001",
        "type": "STATION_CAPACITY_REDUCTION",
        "station_id": "B",
        "start_time": "20:00",
        "end_time": "22:00",
        "available_chargers": 0,
        "reason": "Only 1 charger is available at Station B due to maintenance",
    },
    {
        "operational_failure_id": "failure-002",
        "type": "CHARGER_DOWN",
        "station_id": "D",
        "charger_id": "D-1",
        "start_time": "02:00",
        "end_time": "03:30",
        "reason": "Specific charger D-1 is down due to communication failure",
    },
    {
        "operational_failure_id": "failure-003",
        "type": "SLOW_CHARGING",
        "station_id": "D",
        "start_time": "21:00",
        "end_time": "23:00",
        "charging_duration_minutes": 40,
        "affected_chargers": 1,
        "reason": "Voltage drop at Station D increases charging time",
    },
]


REOPTIMIZATION_CONFIG = {
    "enable_event_driven_reoptimization": True,
    "planned_failure_types": ["STATION_CAPACITY_REDUCTION"],
    "dynamic_failure_types": ["CHARGER_DOWN", "SLOW_CHARGING"],
}
