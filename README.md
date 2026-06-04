# Bus Charging Scheduler

A Python + Streamlit application for optimizing electric bus charging schedules across a fixed highway route using Google OR-Tools CP-SAT.

The scheduler decides where and when each bus should charge while respecting battery range, charger capacity, route order, charging duration, and operational constraints. 
The base scenario JSON represents static planning data, but real-world operations can also include runtime interruptions such as charger downtime, slow charging, voltage drops, or station capacity reduction. To bring that dynamic dimension into the system, the scheduler supports operational failure injection and event-driven CP-SAT re-optimization. 
It also generates an Excel report with timeline-style validation for buses and chargers.

---

## Table of Contents

1. [Problem Statement](#problem-statement)
2. [Framework / Approach Chosen](#framework--approach-chosen)
3. [Why CP-SAT Was Chosen](#why-cp-sat-was-chosen)
4. [How to Run the Project](#how-to-run-the-project)
5. [Project Structure](#project-structure)
6. [How to Change a Weight](#how-to-change-a-weight)
   - [Change Weight Globally](#1-change-weight-globally)
   - [Change Weight from UI](#2-change-weight-from-ui)
   - [Change Weight for One Scenario](#3-change-weight-for-one-scenario)
7. [How to Add a New Rule](#how-to-add-a-new-rule)
   - [Case 1: Configuration-Only Rule](#case-1-configuration-only-rule)
   - [Case 2: Rule That Changes Solver Behavior](#case-2-rule-that-changes-solver-behavior)
   - [Example New Rule: Priority Buses](#example-new-rule-priority-buses)
8. [Event-driven CP-SAT Re-optimization](#event-driven-cp-sat-re-optimization)
9. [Excel Timeline Report](#excel-timeline-report)
   - [Bus Timeline Km](#bus-timeline-km)
   - [Charger Timeline View](#charger-timeline-view)

---

## Problem Statement

The objective is to build a bus charging scheduler that can plan charging stops for multiple electric buses travelling between Bengaluru and Kochi.

The scheduler must ensure:

- Each bus completes the full route.
- A bus does not exceed its maximum range between two full charges.
- Charging station capacity is respected.
- No charger is assigned to overlapping buses.
- Waiting time is minimized.
- Operator-level fairness can be considered.
- The final output is easy to validate through UI and Excel reports.

---

## Framework / Approach Chosen

I used **Google OR-Tools CP-SAT** as the constraint solver for the scheduler.

This is a constraint optimization problem because the scheduler must satisfy fixed rules while optimizing multiple goals.

The scheduler uses:

- Python for backend logic
- Google OR-Tools CP-SAT for optimization
- Streamlit for UI
- Pandas and OpenPyXL for Excel report generation

---

## Why CP-SAT Was Chosen

CP-SAT is a good fit because it supports both constraint satisfaction and optimization.

The problem has many discrete decisions such as:

- Which charging plan should a bus choose?
- At what time should the bus start charging?
- Which charger should be assigned?
- How should charger capacity be respected?
- How should wait time be minimized?

CP-SAT supports these requirements directly.

It supports:

1. **Boolean decisions**  
   Example: should this bus choose charging plan A or plan B?

2. **Time-based scheduling**  
   Example: when should a bus start and finish charging?

3. **Cumulative capacity constraints**  
   Example: only N buses can charge at a station if the station has N chargers.

4. **Optimization objective**  
   Example: minimize max bus wait, total network wait, operator fairness gap, arrival delay, and unnecessary charging stops.

Because CP-SAT covers discrete decisions, time-based scheduling, capacity constraints, and optimization in one model, it is a strong fit compared to greedy logic, PuLP, or Z3.

## How to Run the Project

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the Streamlit app

```bash
streamlit run app.py
```

### 3. Use the application

After the app opens:

1. Select a scenario from the sidebar.
2. Adjust optimization weights if needed.
3. Click `Run Scheduler`.
4. Review summary metrics, bus timetable, and station charging orders.
5. Download the Excel report for timeline validation.

---

## Project Structure

```text
bus-charging-scheduler/
├── app.py
├── requirements.txt
├── README.md
└── Backend/
    ├── __init__.py
    ├── configurations.py
    ├── scheduler.py
    ├── solver_model.py
    ├── route_utils.py
    ├── time_utils.py
    ├── weight_utils.py
    ├── failure_handler.py
    ├── output_builder.py
    ├── event_queue.py
    ├── summary_metrics.py
    ├── report_generator.py
    └── scenarios/
        ├── scenario_01_even_spacing.json
        ├── scenario_02_bunched_start.json
        ├── scenario_03_asymmetric_load.json
        ├── scenario_04_operator_heavy.json
        └── scenario_05_worst_case_convergence.json
```

### Module Responsibilities

| File | Responsibility |
|---|---|
| `app.py` | Streamlit UI. Handles scenario selection, weight sliders, result display, and Excel download. |
| `Backend/configurations.py` | Stores global configuration such as bus range, speed, routes, stations, charger settings, solver settings, operators, and operational failures. |
| `Backend/scheduler.py` | Main coordinator class. Loads scenario data, initializes solver components, runs optimization, and returns final output. |
| `Backend/solver_model.py` | Builds the CP-SAT optimization model, including bus constraints, charging intervals, station capacity constraints, valid charging plans, and objective function. |
| `Backend/route_utils.py` | Handles route distance, cumulative distance, travel time, and solver horizon calculation. |
| `Backend/time_utils.py` | Handles time conversion between `HH:MM` format and integer minutes. |
| `Backend/weight_utils.py` | Handles optimization weight loading, validation, scenario-specific override, and UI weight override. |
| `Backend/failure_handler.py` | Handles operational failure logic such as charger down, station capacity reduction, slow charging, and unavailable charger windows. |
| `Backend/output_builder.py` | Builds bus timetables, station charging orders, charger assignments, compact timeline output, and hides internal minute fields. |
| `Backend/event_queue.py` | Provides a small event queue abstraction for timeline-style event ordering. |
| `Backend/summary_metrics.py` | Builds summary metrics such as total wait, average wait, max wait, station metrics, operator metrics, and simulation duration. |
| `Backend/report_generator.py` | Generates the Excel report, including timeline summary, bus timeline km view, charger timeline view, summary, operator metrics, and station orders. |
| `Backend/scenarios/` | Contains scenario JSON files with bus demand, operator, route, departure time, and optional scenario-specific weights. |

### Why This Structure Was Chosen

The code is split by responsibility so that each module has a clear purpose.

- `scheduler.py` acts as the main coordinator.
- `solver_model.py` contains the optimization logic.
- Utility modules such as `route_utils.py`, `time_utils.py`, and `weight_utils.py` keep repeated logic separate.
- `failure_handler.py` isolates operational failure handling.
- `output_builder.py` separates solver output formatting from solver model creation.
- `report_generator.py` focuses only on Excel report generation.

This makes the project easier to read, test, debug, and extend when new rules are added.

## How to Change a Weight

Optimization weights control how the solver prioritizes different objectives.

Weights can be changed in three ways:

1. Change the weight globally for all scenarios.
2. Change the weight directly from the UI.
3. Override the weight only for a specific scenario.

---

### 1. Change Weight Globally

If the weight should apply to all scenarios, update `OPTIMIZATION_WEIGHTS` in:

```text
Backend/configurations.py
```

Example:

```python
OPTIMIZATION_WEIGHTS = {
    "individual_wait_weight": 1.0,
    "operator_fairness_weight": 1.0,
    "network_wait_weight": 2.0,
}
```

In this example, `network_wait_weight` is increased, so the solver gives more importance to reducing total network wait.

---

### 2. Change Weight from UI

The Streamlit UI provides sliders for optimization weights.

The user can adjust the weights from the sidebar and click:

```text
Run Scheduler
```

The UI weight values are passed to the scheduler and used in the objective calculation.

The priority order is:

```text
Base configuration weights
        ↓
Scenario-specific weights
        ↓
UI slider weights
```

So the UI slider values have the highest priority.

---

### 3. Change Weight for One Scenario

If only one scenario needs a different optimization priority, update that specific scenario JSON file under:

```text
Backend/scenarios/
```

Example:

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

In this example, operator fairness is given more importance for that scenario.

---

## How to Add a New Rule

Adding a new rule depends on the type of rule.

Some rules are configuration-only.  
Some rules go beyond configuration and require changes in the solver model.

---

### Case 1: Configuration-Only Rule

If the rule only changes data, then we can update `configurations.py` or the scenario JSON.

Example: adding a new charging station.

```python
STATIONS_CONFIG = [
    {
        "station_id": "E",
        "station_name": "Station E",
        "charger_count": 2,
    }
]
```

If this station is added to `ROUTES_CONFIG`, the scheduler can consider it while generating valid charging plans.

---

### Case 2: Rule That Changes Solver Behavior

If the rule changes how decisions are made, then configuration alone is not enough.

In that case, the rule must be added inside `scheduler.py` as:

- a new decision variable,
- a new constraint,
- a new objective penalty,
- or a combination of these.

---

### Example New Rule: Priority Buses

A future requirement may be that some buses should get higher priority than others.

This cannot be solved only through configuration because the solver must know how to treat priority during optimization.

The scenario JSON can include the new input:

```json
{
  "bus_id": "bus-BK-01",
  "operator_id": "kpn",
  "route_id": "route_01",
  "scheduled_departure_time": "19:00",
  "priority": 3
}
```

The priority configuration can be added to `configurations.py`:

```python
PRIORITY_CONFIG = {
    1: "normal priority",
    2: "high priority",
    3: "critical priority",
}
```

Then `scheduler.py` must be updated to include this priority in the objective.

Example:

```python
self.model.Minimize(
    self._weight("individual_wait_weight") * max_bus_wait
    + self._weight("operator_fairness_weight") * operator_fairness
    + self._weight("network_wait_weight") * total_network_wait
    + self._weight("priority_weight") * total_priority_wait
    + total_final_arrival_time
)
```

This makes the solver try harder to reduce wait time for higher-priority buses.

So the data can come from configuration or scenario JSON, but the optimization behavior must be implemented in the solver.

---

## Event-driven CP-SAT Re-optimization

The scenario JSON represents static planning data. In the real world, we may know the planned bus schedules in advance, but we may not know real-time delays, charger interruptions, voltage drops, or other operational issues that can affect the schedule during execution.

To bring that real-world dimension into the system, I added support for injecting operational failures into the scheduler. This makes the scheduler more suitable for real-world operations because it is not limited to producing only one static schedule from fixed input data.

### Failure Handling Strategy

The system handles operational failures in two ways:

| Failure Type | Handling Strategy | Reason |
|---|---|---|
| `STATION_CAPACITY_REDUCTION` | Considered during the initial CP-SAT solve | This represents planned maintenance or known capacity reduction, so it can be treated as a static input constraint before scheduling starts. |
| `CHARGER_DOWN` | Injected dynamically at the configured failure time | This behaves like an unexpected runtime failure, so the scheduler first creates the base schedule and re-optimizes when the failure time is reached. |
| `SLOW_CHARGING` | Injected dynamically at the configured failure time | This represents a runtime degradation in charging performance, so the scheduler re-solves the remaining schedule from that point. |

### Re-optimization Flow

```text
Scenario input
    ↓
Initial CP-SAT solve without dynamic failures
    ↓
Logical run reaches configured dynamic failure time
    ↓
Failure is injected into the system
    ↓
Completed and already-started decisions are frozen
    ↓
CP-SAT re-solves the remaining schedule
    ↓
Final optimized schedule is returned
```

### Why This Was Added

Most static schedulers assume all information is available before the schedule starts. But in real charging operations, some issues are known upfront while others happen only during execution.

This feature keeps the implementation fully CP-SAT based while adding a production-style behavior on top of it. The Streamlit UI also shows an event-driven re-optimization trace, so the user can see:

- The initial CP-SAT planning phase.
- The dynamic failure queued for injection.
- The exact failure injected during the logical run.
- The triggered failure type, station, charger, and reason.
- The re-optimized CP-SAT phase after the failure.
- The wait time and solver time for each phase.

This makes the solution easier to explain and closer to a real operational scheduling system.

---
## Excel Timeline Report

The project generates a downloadable Excel report.

The report includes:

1. **Timeline Summary**
2. **Bus Timeline Km**
3. **Charger Timeline View**
4. **Summary**
5. **Operator Metrics**
6. **Bus Timetable**
7. **Bus Charging Events**
8. **Station Orders**

---

### Bus Timeline Km

The `Bus Timeline Km` sheet shows the bus activity over time.

Each row represents one bus.

Each time column represents a time slot.

The cell shows:

- Travel activity
- Wait activity
- Charging activity
- Arrival status
- Distance covered since the last full charge

Example:

```text
T:Bengaluru->B
210-215km
```

When the bus charges, the distance resets:

```text
C:B/B-1
RESET→0km
```

This makes it easy to visually validate that:

- Distance increases during travel.
- Distance holds during wait.
- Charging resets distance to zero.
- No travel leg exceeds the maximum allowed range.
- The bus completes the full route.

---

### Charger Timeline View

The `Charger Timeline View` sheet shows charger occupancy over time.

Each row represents one charger.

Each time column represents a time slot.

The cell shows which bus is occupying that charger.

This makes it easy to visually validate that:

- No two buses use the same charger at the same time.
- Charger capacity is respected.
- Charger usage is understandable without reading raw solver output.

