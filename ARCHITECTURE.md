# Bus Charging Scheduler Documentation

## Table of Contents

1. [Framework / Approach Chosen](#framework--approach-chosen)
2. [Why CP-SAT Was Chosen](#why-cp-sat-was-chosen)
3. [Other Approaches Considered](#other-approaches-considered)
4. [Data Structure Design](#data-structure-design)
   - [System-Level Configuration](#1-system-level-configuration)
   - [Scenario-Level Input](#2-scenario-level-input)
   - [Why This Design Was Chosen](#why-this-design-was-chosen)
5. [Future Changes Anticipated](#future-changes-anticipated)
   - [Operational Failure Types Supported](#operational-failure-types-supported)
6. [How to Change a Weight](#how-to-change-a-weight)
   - [Change Weight Globally](#1-change-weight-globally)
   - [Change Weight for One Scenario](#2-change-weight-for-one-scenario)
7. [How to Add a New Rule](#how-to-add-a-new-rule)
   - [Example New Rule: Priority Buses](#example-new-rule-priority-buses)
8. [Assumptions Made](#assumptions-made)

---
### Framework / Approach Chosen

I used **Google OR-Tools CP-SAT** as the constraint solver for the scheduler.

### Why CP-SAT is the Right Fit
This is a constraint optimization problem because the scheduler must satisfy fixed rules while optimizing multiple goals.

### Other Approaches Considered

| Approach | Why Not Chosen |
|---|---|
| **Custom heuristic / greedy logic** | Greedy logic only considers the current bus or immediate charger availability. It can make a locally good decision but create higher waiting time later for other buses.There is a high possbility of logic miss whcih might result in high network time.|
| **PuLP / Linear Programming** | PuLP is useful for linear optimization problems like minimizing cost or time with linear equations. But this problem is time-based scheduling with charger overlap, capacity, and boolean decisions. Using PuLP would require manually creating many time-slot and overlap constraints. |
| **Z3** | Z3 is good for logical constraint problems, such as checking whether a valid arrangement exists. But this problem needs more than feasibility. It also needs scheduling, charger capacity handling, and weighted optimization. |

### Why CP-SAT Was Chosen

CP-SAT is a better fit because it supports:

1. **Boolean decisions**  
   Example: should this bus choose charging plan A or plan B?

2. **Time-based scheduling**  
   Example: when should a bus start and finish charging?

3. **Cumulative capacity constraints**  
   Example: only N buses can charge at a station if the station has N chargers.

4. **Optimization objective**  
   Example: minimize total wait, max wait, operator fairness gap, arrival delay, and unnecessary charging stops.

Because CP-SAT covers discrete decisions, time-based scheduling, capacity constraints, and optimization in one model, it is the best fit compared to greedy logic, PuLP, or Z3.

---

### Data Structure Design

The data structure is split into two parts:

1. **System-level configuration**
2. **Scenario-level input**

This separation avoids repeating fixed infrastructure details in every scenario file and keeps the scheduler reusable.


### 1. System-Level Configuration

System-level configuration is stored in `Backend/configurations.py`.

It contains data that is common across all scenarios:

- Optimization weights
- Bus range and speed
- Charging duration and charger turnaround time
- Routes and station distances
- Charging station capacity
- Operators
- Solver settings

For example, if the charger count at a station changes, we only update `STATIONS_CONFIG`. The solver automatically uses the new value across all scenarios, without changing the scheduling code.


### 2. Scenario-Level Input

Scenario-specific data is stored as JSON files under `Backend/scenarios/`.

Each scenario contains only the changing demand data as per the scenario such as : 

- Total number buses and their departure and destination point
- Time of departure

The scenario file does not repeat optimization weights, route distances, station capacity or charger duration


### Why This Design Was Chosen

This design keeps the system flexible and avoids hardcoding assumptions inside the scheduler.

Examples:

- To add more buses, update only the scenario JSON.
- To change charger count, update only `STATIONS_CONFIG`.
- To change optimization priority, update only `OPTIMIZATION_WEIGHTS`.

This makes the scheduler logic reusable across multiple scenarios and keeps future changes mostly configuration-driven.

---

### Future Changes Anticipated

While designing the data structure, I kept the system configurable so that common future changes can be handled without changing the scheduler code.

| Future Change | How the Design Handles It Without Code Changes |
|---|---|
| **Add new chargers to one or all stations** | Update `charger_count` in `STATIONS_CONFIG`. The solver automatically uses the updated station capacity while applying charger constraints. |
| **Add charger setup / buffer time** | Update `charger_setup_duration_minutes` in `CHARGER_CONFIG`. The scheduler automatically adds this buffer to the actual charging duration. |
| **Change route distance or station sequence** | Update `ROUTES_CONFIG`. The solver recalculates travel time, route order, and range feasibility from the route configuration. |
| **Use different weights for per scenario** | Can set the weights directly from the UI. |
| **Add a new route to the system eg: Bengaluru to Coimbatore** | Adding the route to the `ROUTES_CONFIG` in `configuration` is enough |
| **Add a new operator** | Adding the operator to the `OPERATORS_CONFIG` in `configuration` is enough |
| **Stations sharing multiple route** | The stations can be shared without making changes to the scheduler.|
| **Change charging duration** | Update `charging_duration_minutes` in `CHARGER_CONFIG`. All charging intervals automatically use the new duration. |
| **Add a new charging station to the route** | The routes can be added to the `ROUTE_CONFG`, no code change required.  |
| **Require a timeline report for charger and bus data** | A downloadable Excel report has been added so the bus schedule, charging events, station order, and metrics can be validated and reviewed outside the app. This makes it easier to analyze the scenario in a timeline-style view. |
| **Add minimum reserve range / safety buffer** | Update `minimum_required_range_km` in `BUS_CONFIG`. The scheduler automatically reduces the usable range by this value while generating valid charging plans. For example, if `maximum_range_km = 240` and `minimum_required_range_km = 20`, the bus will be allowed to travel only up to `220 km` between charges. |
| **Change bus range** | Update `maximum_range_km` in `BUS_CONFIG`. The solver automatically uses the new range while generating valid charging plans. |
| **Add a new scenario** | Create a new scenario JSON with different buses, operators, routes, and departure times. No scheduler code change is needed. |
| **Handle operational failures at charging stations** | Add failures under `OPERATIONAL_FAILURES` in the configuration file and enable them using `OPERATIONAL_FAILURE_SETTINGS`. |

| **Handle operational failures at charging stations** | Add failures under `OPERATIONAL_FAILURES` in the configuration file and enable them using `OPERATIONAL_FAILURE_SETTINGS`. |

#### Operational Failure Types Supported

| Failure Type | Meaning |
|---|---|
| `STATION_CAPACITY_REDUCTION` | Reduces the available chargers at a station for a given time window. Example: Station B has 2 chargers, but only 1 is available due to maintenance. |
| `CHARGER_DOWN` | Represents one or more chargers being unavailable at a station for a given time window. |
| `SLOW_CHARGING` | Increases charging duration at a station for a given time window. Example: voltage drop causes charging to take longer. |

---

***How you'd change a weight (with a code example)***

### How to Change a Weight

Optimization weights can be changed in two ways:

1. Change the weight globally for all scenarios
2. Override the weight only for a specific scenario


### 1. Change Weight Globally

If the weight should apply to all scenarios, update `OPTIMIZATION_WEIGHTS` in `Backend/configurations.py`.

Example:

```python
OPTIMIZATION_WEIGHTS = {
    "individual_wait_weight": 1.0,
    "operator_fairness_weight": 1.0,
    "network_wait_weight": 2.0,
}
```

### 2. Change Weight for One Scenario

If only one scenario needs a different optimization priority, update that specific scenario JSON file under `Backend/scenarios/`.

For example, in `scenario_04_operator_heavy.json`, the requirement is to give more importance to operator fairness compared to the other scenarios. To handle this, the flag `consider_individual_scenario_weight` is set to `true`.

When this flag is enabled, the scenario-specific weights override the base weights configured in `Backend/configurations.py`.

```json
"optimization": {
  "consider_individual_scenario_weight": true,
  "weights": {
    "individual_wait_weight": 1.0,
    "operator_fairness_weight": 2.0,
    "network_wait_weight": 1.0
  }
}
```
---

### How to Add a New Rule

The scheduler is designed so that new operational rules can be added in a structured way.

1. If the rule is only a data/configuration change, it can be handled through `configurations.py` or the scenario JSON. 

Example : Adding an extra station to the route or modifying the number of chargers in any/all of the stations.

```python
STATIONS_CONFIG = [
  {
    "station_id": "E",
    "station_name": "Station E",
    "charger_count": 2
  }]
```

2. If the rule changes the solver behavior, a new constraint or objective term can be added in `scheduler.py`. The input can be fed in through the scenario json.

### Example New Rule: Priority Buses

A future requirement may be that some buses should get higher priority than others.

This can be handled by adding an optional `priority` field in the scenario JSON.

```json
{
  "bus_id": "bus-BK-01",
  "operator_id": "kpn",
  "route_id": "route_01",
  "scheduled_departure_time": "19:00",
  "priority": 3
}
```

The priority configuration can be added to the `configuration.py` file as

```python
PRIORITY_CONFIG = {
    1 : "normal priority",
    2 : "high priority",
    3 : "critical priority"
    }
```
If priority is not provided, the scheduler can treat it as normal priority.

Then the objective function can be modified to handle this priority as a constraint

```python
self.model.Minimize(
    self._weight("individual_wait_weight") * max_bus_wait
    + self._weight("operator_fairness_weight") * operator_fairness
    + self._weight("network_wait_weight") * total_network_wait
    + self._weight("priority") * total_priority
    + total_final_arrival_time
)
```
So the solver will try harder to reduce wait time for the priority bus.

---

### Assumptions Made

| Assumption | Reason |
|---|---|
| **Tie-breaker for equally good schedules** | If multiple feasible schedules have similar objective values for wait time and fairness, the solver prefers the one with lower arrival delay, fewer charging stops, and earlier final arrival time. |
| **Travel speed is constant** | Assumed 60 km/h, so 1 km is treated as 1 minute of travel time. This keeps travel time deterministic and easy to validate. |
| **All buses are treated equally** | Current optimization balances wait, fairness, delay, and charging stops. Priority buses can be added later as a new objective rule. |\
| **The solver may return FEASIBLE or OPTIMAL** | If the time limit(currently set to 1 min) is reached, the solver may return a valid feasible solution without proving it is globally optimal. |
| **The scheduler runs as a static planning problem, not a live real-time dispatcher** | The full scenario input is available before solving, so I assumed the scheduler can optimize using the complete bus list rather than reacting one bus at a time. |
| **There can be interruption/operational level failures** | Charger down, reduced capacity, and slow charging are operating conditions, not scenario demand. So they are configured globally and can be enabled or disabled without editing every scenario. |
| **All time calculations are done in minutes** | Internally, times like `19:00` are converted to minutes. This makes travel, charging, waiting, and arrival calculations simpler and avoids complex datetime handling. |
| **No additional charger setup delay in the baseline case** | Assumed the given 25-minute charging window includes the normal charging operation. No extra buffer is added between two buses by default. However, the design includes `charger_setup_duration_minutes` in `CHARGER_CONFIG`, currently set to `0`, so a setup/buffer time can be added later without changing the scheduler logic. |
| **No dwell time at pass-through stations** | If a bus passes through a station without charging, I assumed it does not spend extra time there. Only travel, waiting, and charging affect the timeline. |
| **Charging duration does not depend on remaining battery** | treated every selected charging stop as a fixed 25-minute full-charge event, regardless of how much range the bus had left when it reached the station. |
| **No minimum reserve range is required** | I assumed the bus can use the full 240 km range before needing to recharge. So `minimum_required_range_km` is set to `0`, meaning the scheduler only checks that distance between charges does not exceed 240 km. No additional safety buffer like 10 km or 20 km is reserved. |
## Event-driven CP-SAT Re-optimization

The core scheduler remains a pure OR-Tools CP-SAT optimizer. One additional production-style behavior is added on top of the base model:

- `STATION_CAPACITY_REDUCTION` is treated as a planned operational constraint and is included in the first solve.
- `CHARGER_DOWN` and `SLOW_CHARGING` are treated as dynamic operational failures.
- The scheduler first solves without knowing these dynamic failures.
- When the configured dynamic failure start time is reached, completed and already-started decisions are frozen.
- CP-SAT is rebuilt and re-solved for the remaining schedule with the newly active failure included.

This keeps the solution fully CP-SAT based while making the engine closer to a real operational scheduler.
