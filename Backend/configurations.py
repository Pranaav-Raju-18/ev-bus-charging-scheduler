"""System-level configuration for the bus charging scheduler.

Everything that describes the fixed world lives here: the route, the charging
stations, the operators, the battery limits, the optimization weights, the
solver budget and the optional operational failures.

Design rule: growing or tuning the world (more buses, stations, chargers,
operators, routes, different distances or weights) should be an edit in this
file or in a scenario JSON, never a change to the engine code.
"""

# --- Physical constants ----------------------------------------------------

BATTERY_RANGE_KM = 240   # how far a bus can drive on a full charge
CHARGE_MINUTES = 25      # time to charge back to full (fixed)
SPEED_KMPH = 60          # constant speed, so 1 km takes 1 minute

# --- Route(s) --------------------------------------------------------------
# Each route is an ordered list of stops plus the distance of every segment
# between consecutive stops. The two endpoints are start/finish only; the
# inner stops that also appear in STATIONS are the ones with chargers.

ROUTES = {
    "route_01": {
        "name": "Bengaluru to Kochi",
        "stops": ["Bengaluru", "A", "B", "C", "D", "Kochi"],
        "segment_km": [100, 120, 100, 120, 100],
    },
    "route_02": {
        "name": "Kochi to Bengaluru",
        "stops": ["Kochi", "D", "C", "B", "A", "Bengaluru"],
        "segment_km": [100, 120, 100, 120, 100],
    },
}

# --- Charging stations -----------------------------------------------------
# Only these stops have chargers. Change "chargers" to add capacity.

STATIONS = {
    "A": {"chargers": 1},
    "B": {"chargers": 1},
    "C": {"chargers": 1},
    "D": {"chargers": 1},
}

# --- Operators -------------------------------------------------------------

OPERATORS = {
    "kpn": "KPN",
    "freshbus": "Freshbus",
    "flixbus": "Flixbus",
}

# --- Optimization weights (tunable) ---------------------------------------
# The three soft rules from the brief. Higher value = more important.
# Override per scenario in the scenario JSON, or live from the UI sliders.

WEIGHTS = {
    "individual": 1.0,   # keep the single worst bus wait low
    "operator": 1.0,     # keep operators' total waits balanced
    "network": 1.0,      # keep the whole fleet's total wait low
}

# --- Solver settings -------------------------------------------------------

SOLVER = {
    "max_seconds": 30,   # time budget per solve
    "workers": 8,        # parallel search workers
}

# --- Operational failures (optional) --------------------------------------
# Real-world disruptions. Disabled by default so the base scenarios stay
# clean. Enable to see the scheduler plan around (and re-optimize for) them.

FAILURES_ENABLED = False

FAILURES = [
    {
        "id": "failure-001",
        "type": "STATION_CAPACITY_REDUCTION",
        "station": "B",
        "available_chargers": 0,
        "start": "20:00",
        "end": "22:00",
        "reason": "Maintenance reduces chargers at Station B",
    },
    {
        "id": "failure-002",
        "type": "CHARGER_DOWN",
        "station": "D",
        "start": "21:00",
        "end": "22:30",
        "reason": "A charger at Station D is offline",
    },
    {
        "id": "failure-003",
        "type": "SLOW_CHARGING",
        "station": "D",
        "slow_minutes": 40,
        "start": "21:00",
        "end": "23:00",
        "reason": "Voltage drop at Station D slows charging",
    },
]

# Planned failures are known up front and go into the first solve. Dynamic
# failures behave like surprises: the scheduler plans without them, then
# re-optimizes the remaining schedule when each one's start time is reached.
PLANNED_FAILURE_TYPES = ["STATION_CAPACITY_REDUCTION"]
DYNAMIC_FAILURE_TYPES = ["CHARGER_DOWN", "SLOW_CHARGING"]
