"""Streamlit UI for the lightweight bus charging scheduler.

Same look and layout as the main app (theme, sidebar, four tabs, metric cards,
animated loader, re-optimization trace), but driven by the lightweight backend.
The Input Data Structure tab shows the lightweight config.py values as raw JSON.
"""

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from Backend.config import (
    BATTERY_RANGE_KM,
    CHARGE_MINUTES,
    SPEED_KMPH,
    ROUTES,
    STATIONS,
    OPERATORS,
    WEIGHTS,
    SOLVER,
    FAILURES_ENABLED,
    FAILURES,
    PLANNED_FAILURE_TYPES,
    DYNAMIC_FAILURE_TYPES,
)
from Backend.scenario import Scenario
from Backend.reoptimizer import Reoptimizer
from Backend.report import Report

SCENARIO_FOLDER = Path("Backend/scenarios")


st.set_page_config(
    page_title="Bus Charging Scheduler",
    layout="wide",
)


st.markdown(
    """
    <style>
        .stApp {
            background-color: #FFFFFF;
        }

        h1, h2, h3 {
            color: #1F1F1F;
            font-weight: 800;
        }

        section[data-testid="stSidebar"] {
            background-color: #F5B400;
        }

        section[data-testid="stSidebar"] * {
            color: #1F1F1F;
        }

        section[data-testid="stSidebar"] div[data-testid="stSidebarUserContent"] {
            padding-top: 1.5rem;
        }

        section[data-testid="stSidebar"] h3 {
            background-color: #1F1F1F;
            color: #F5B400 !important;
            padding: 0.55rem 0.8rem;
            border-radius: 10px;
            margin-top: 1.2rem;
            margin-bottom: 0.6rem;
            font-size: 1.05rem;
        }

        section[data-testid="stSidebar"] p {
            font-size: 0.95rem;
            font-weight: 600;
        }

        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
            background-color: #FFFFFF;
            color: #1F1F1F;
            border: 2px solid #1F1F1F;
            border-radius: 8px;
        }

        section[data-testid="stSidebar"] label {
            font-weight: 700;
        }

        section[data-testid="stSidebar"] div[data-testid="stAlert"] {
            background-color: rgba(255, 255, 255, 0.45);
            border: 1px solid rgba(31, 31, 31, 0.25);
            border-radius: 10px;
        }

        section[data-testid="stSidebar"] div[data-testid="stAlert"] p {
            color: #1F1F1F !important;
            font-weight: 800;
        }

        div.stButton > button {
            background-color: #1F1F1F !important;
            color: #FFFFFF !important;
            border: 2px solid #FFFFFF !important;
            border-radius: 10px;
            padding: 0.6rem 1.2rem;
            font-weight: 800;
            transition: all 0.2s ease-in-out;
        }

        div.stButton > button p {
            color: #FFFFFF !important;
            font-weight: 800 !important;
        }

        div.stButton > button span {
            color: #FFFFFF !important;
            font-weight: 800 !important;
        }

        div.stButton > button:hover {
            background-color: #000000 !important;
            color: #FFFFFF !important;
            border: 2px solid #FFFFFF !important;
            transform: scale(1.02);
        }

        div.stButton > button:hover p {
            color: #FFFFFF !important;
        }

        div.stButton > button:hover span {
            color: #FFFFFF !important;
        }

        div.stButton > button:active {
            background-color: #000000 !important;
            color: #FFFFFF !important;
            border: 2px solid #FFFFFF !important;
        }

        div.stButton > button:active p {
            color: #FFFFFF !important;
        }

        div.stButton > button:active span {
            color: #FFFFFF !important;
        }

        div.stDownloadButton > button {
            background-color: #1F1F1F;
            color: #F5B400;
            border: 2px solid #F5B400;
            border-radius: 10px;
            padding: 0.6rem 1.2rem;
            font-weight: 800;
            transition: all 0.2s ease-in-out;
        }

        div.stDownloadButton > button:hover {
            background-color: #F5B400;
            color: #1F1F1F;
            border: 2px solid #1F1F1F;
            transform: scale(1.02);
        }

        div[data-testid="stMetric"] {
            background-color: #F8F8F8;
            border-left: 6px solid #F5B400;
            padding: 1rem;
            border-radius: 10px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
            min-height: 145px;
        }

        div[data-testid="stMetricLabel"] {
            color: #1F1F1F;
            font-weight: 700;
            white-space: normal;
        }

        div[data-testid="stMetricValue"] {
            color: #1F1F1F;
            font-weight: 900;
            font-size: 2.1rem;
            white-space: nowrap;
            overflow: visible;
        }

        div[data-testid="stMetricDelta"] {
            color: #1F1F1F;
            font-weight: 700;
        }

        button[data-baseweb="tab"] {
            font-weight: 700;
            color: #1F1F1F;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            border-bottom: 4px solid #F5B400;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid #E0E0E0;
            border-radius: 10px;
        }

        details {
            border: 1px solid #E0E0E0;
            border-radius: 10px;
        }

        details summary {
            font-weight: 700;
            color: #1F1F1F;
        }

        div[data-testid="stAlert"] {
            border-radius: 10px;
        }

        .metric-note {
            font-size: 0.82rem;
            font-weight: 600;
            color: #555555;
            margin-top: -0.7rem;
            padding-left: 0.2rem;
        }

        .sidebar-config-card {
            background-color: rgba(255, 255, 255, 0.48);
            border: 1px solid rgba(31, 31, 31, 0.25);
            border-radius: 10px;
            padding: 0.75rem 0.85rem;
            margin-bottom: 0.75rem;
        }

        .sidebar-config-title {
            font-size: 0.92rem;
            font-weight: 900;
            margin-bottom: 0.35rem;
        }

        .sidebar-config-text {
            font-size: 0.9rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        .reopt-card {
            border-left: 6px solid #F5B400;
            background-color: #F8F8F8;
            padding: 0.95rem 1rem;
            border-radius: 10px;
            margin-bottom: 0.8rem;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        }

        .reopt-card-title {
            font-weight: 900;
            color: #1F1F1F;
            margin-bottom: 0.35rem;
        }

        .reopt-card-text {
            font-weight: 650;
            color: #333333;
            margin-bottom: 0.15rem;
        }

        .reopt-injection-card {
            border-left: 6px solid #D9534F;
            background-color: #FFF4F4;
            padding: 0.95rem 1rem;
            border-radius: 10px;
            margin-bottom: 0.8rem;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
        }

        .optimizer-loader-card {
            background-color: #F8F8F8;
            border-left: 6px solid #F5B400;
            border-radius: 12px;
            padding: 1rem 1.2rem;
            margin: 0.8rem 0 1rem 0;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.08);
        }

        .optimizer-loader-title {
            color: #1F1F1F;
            font-size: 1rem;
            font-weight: 900;
            margin-bottom: 0.45rem;
        }

        .optimizer-loader-text {
            color: #444444;
            font-size: 0.9rem;
            font-weight: 650;
            margin-bottom: 0.75rem;
        }

        .bus-track {
            position: relative;
            height: 36px;
            border-bottom: 3px solid #1F1F1F;
            overflow: hidden;
        }

        .bus-track::before {
            content: "";
            position: absolute;
            left: 0;
            right: 0;
            bottom: 7px;
            height: 4px;
            background: repeating-linear-gradient(
                to right,
                #1F1F1F 0 26px,
                transparent 26px 42px
            );
            opacity: 0.9;
        }

        .bus-icon {
            position: absolute;
            left: -52px;
            bottom: 0;
            font-size: 1.7rem;
            animation: busMove 30s linear 1 forwards;
        }

        .charger-node {
            position: absolute;
            right: 4px;
            bottom: -2px;
            font-size: 1.75rem;
        }

        @keyframes busMove {
            0% {
                left: -52px;
            }

            100% {
                left: calc(100% - 38px);
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def time_to_minutes(time_text) -> int:
    """Convert 'HH:MM' text into minutes from midnight.

    Args:
        time_text (str): Time value in 'HH:MM' format.

    Returns:
        int: Minutes since 00:00.
    """
    hour, minute = map(int, time_text.split(":"))
    return hour * 60 + minute


def calculate_journey_minutes(departure_time, arrival_time) -> int:
    """Total journey duration in minutes, rolling over midnight if needed.

    Args:
        departure_time (str): Departure clock 'HH:MM'.
        arrival_time (str): Final arrival clock 'HH:MM'.

    Returns:
        int: Minutes between departure and arrival.
    """
    departure = time_to_minutes(departure_time)
    arrival = time_to_minutes(arrival_time)
    if arrival < departure:
        arrival += 24 * 60
    return arrival - departure


def build_summary(result) -> dict:
    """Compute headline metrics from a lightweight schedule result.

    Args:
        result (dict): Schedule from Reoptimizer.run / Scheduler.solve.

    Returns:
        dict: Aggregated metrics used by the Summary tab and others.
    """
    buses = result["buses"]
    waits = [bus["total_wait_minutes"] for bus in buses]
    stops = [len(bus["plan"]) for bus in buses]
    journeys = [calculate_journey_minutes(bus["departure"], bus["arrival"]) for bus in buses]
    total = len(buses)

    starts = [time_to_minutes(bus["departure"]) for bus in buses]
    ends = [time_to_minutes(bus["departure"]) + journey for bus, journey in zip(buses, journeys)]
    start_minute = min(starts)
    end_minute = max(ends)

    return {
        "total_buses": total,
        "total_wait": sum(waits),
        "average_wait": round(sum(waits) / total, 2) if total else 0,
        "max_wait": max(waits) if waits else 0,
        "buses_with_wait": sum(1 for w in waits if w > 0),
        "buses_with_wait_percent": round(sum(1 for w in waits if w > 0) / total * 100, 1) if total else 0,
        "total_stops": sum(stops),
        "average_stops": round(sum(stops) / total, 2) if total else 0,
        "max_journey": max(journeys) if journeys else 0,
        "start_time": f"{start_minute // 60 % 24:02d}:{start_minute % 60:02d}",
        "end_time": f"{end_minute // 60 % 24:02d}:{end_minute % 60:02d}",
        "duration": end_minute - start_minute,
    }


def build_bus_rows(result) -> list:
    """Rows for the bus timetable table.

    Args:
        result (dict): Schedule result.

    Returns:
        list[dict]: One row per bus.
    """
    return [
        {
            "Bus ID": bus["bus_id"],
            "Operator": bus["operator_id"],
            "Route": bus["route_id"],
            "Origin": bus["origin"],
            "Destination": bus["destination"],
            "Departure": bus["departure"],
            "Charging Plan": " -> ".join(bus["plan"]),
            "Wait Minutes": bus["total_wait_minutes"],
            "Charging Stops": len(bus["plan"]),
            "Final Arrival": bus["arrival"],
            "Journey Minutes": calculate_journey_minutes(bus["departure"], bus["arrival"]),
        }
        for bus in result["buses"]
    ]


def build_operator_rows(result) -> list:
    """Rows for operator-level metrics.

    Args:
        result (dict): Schedule result.

    Returns:
        list[dict]: One row per operator that has buses.
    """
    waits = {}
    for bus in result["buses"]:
        waits.setdefault(bus["operator_id"], []).append(bus["total_wait_minutes"])
    return [
        {
            "Operator": operator_id,
            "Bus Count": len(values),
            "Total Wait Minutes": sum(values),
            "Average Wait Minutes": round(sum(values) / len(values), 2),
            "Max Wait Minutes": max(values),
        }
        for operator_id, values in waits.items()
    ]


def build_station_rows(result) -> list:
    """Rows for station-level metrics.

    Args:
        result (dict): Schedule result.

    Returns:
        list[dict]: One row per station.
    """
    duration = build_summary(result)["duration"]
    rows = []
    for station_id in STATIONS:
        sessions = result["stations"].get(station_id, [])
        waits = [event["wait_minutes"] for event in sessions]
        chargers = STATIONS[station_id]["chargers"]
        charging_minutes = len(sessions) * CHARGE_MINUTES
        capacity_minutes = chargers * duration if duration else 0
        rows.append({
            "Station": station_id,
            "Chargers": chargers,
            "Sessions": len(sessions),
            "Total Wait Minutes": sum(waits),
            "Average Wait Minutes": round(sum(waits) / len(waits), 2) if waits else 0,
            "Max Wait Minutes": max(waits) if waits else 0,
            "Total Charging Minutes": charging_minutes,
            "Utilization %": round(charging_minutes / capacity_minutes * 100, 1) if capacity_minutes else 0,
        })
    return rows


def build_dynamic_failure_rows() -> list:
    """Rows for the configured dynamic failures.

    Returns:
        list[dict]: One row per dynamic failure (empty if failures disabled).
    """
    if not FAILURES_ENABLED:
        return []
    return [
        {
            "Failure ID": failure.get("id"),
            "Type": failure.get("type"),
            "Station": failure.get("station"),
            "Start Time": failure.get("start"),
            "End Time": failure.get("end"),
            "Reason": failure.get("reason", "-"),
        }
        for failure in FAILURES
        if failure.get("type") in DYNAMIC_FAILURE_TYPES
    ]


def render_optimizer_loader(message) -> None:
    """Show the animated bus loader while CP-SAT runs.

    Args:
        message (str): Short status message shown above the animation.
    """
    st.markdown(
        f"""
        <div class="optimizer-loader-card">
            <div class="optimizer-loader-title">Running optimizer</div>
            <div class="optimizer-loader-text">{message}</div>
            <div class="bus-track">
                <div class="bus-icon">🚌</div>
                <div class="charger-node">🔌</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_reoptimization_trace(result) -> None:
    """Render the re-optimization phases as cards.

    Args:
        result (dict): Schedule result with a 'phases' list.
    """
    phases = result.get("phases", [])

    if len(phases) <= 1:
        st.info(
            "Event-driven re-optimization did not run for this scenario. "
            "Enable CHARGER_DOWN or SLOW_CHARGING in config.FAILURES to trigger it."
        )
        return

    st.markdown("### Event-driven CP-SAT Re-optimization Trace")

    for index, phase in enumerate(phases, start=1):
        if phase.get("failure_id"):
            card_class = "reopt-injection-card"
            title = f"Phase {index}: Failure injected at {phase.get('trigger_time')} -> {phase.get('failure_type')}"
            details = [
                f"Failure ID: {phase.get('failure_id')}",
                f"Re-optimized status: {phase.get('status')}",
                f"Re-optimized total wait: {phase.get('total_wait_minutes')} minutes",
            ]
        else:
            card_class = "reopt-card"
            title = "Phase 1: Initial CP-SAT plan before dynamic failure injection"
            details = [
                f"Status: {phase.get('status')}",
                f"Initial total wait: {phase.get('total_wait_minutes')} minutes",
                "Dynamic failures are not considered in this initial phase.",
            ]

        details_html = "".join(f'<div class="reopt-card-text">{detail}</div>' for detail in details)
        st.markdown(
            f'<div class="{card_class}"><div class="reopt-card-title">{title}</div>{details_html}</div>',
            unsafe_allow_html=True,
        )


# --- Title -----------------------------------------------------------------

st.title("Bus Charging Scheduler")


# --- Sidebar ---------------------------------------------------------------

scenario_files = sorted(SCENARIO_FOLDER.glob("*.json"))

if not scenario_files:
    st.error("No scenario files found in Backend/scenarios.")
    st.stop()

scenario_names = [path.name for path in scenario_files]
selected_scenario_name = st.sidebar.selectbox("Select Scenario", scenario_names)
selected_scenario_path = SCENARIO_FOLDER / selected_scenario_name

with open(selected_scenario_path) as handle:
    scenario_data = json.load(handle)

scenario = Scenario.load(str(selected_scenario_path))

st.sidebar.markdown("### Selected Scenario")
st.sidebar.write(scenario.name)

st.sidebar.markdown("### Optimization Weights")
ui_weights = {}
for weight_name in WEIGHTS:
    ui_weights[weight_name] = st.sidebar.slider(
        label=weight_name,
        min_value=0.0,
        max_value=3.0,
        value=float(scenario.weights.get(weight_name, WEIGHTS[weight_name])),
        step=0.1,
        format="%.1f",
        key=f"{selected_scenario_name}_{weight_name}",
    )
scenario.weights = ui_weights

run_scheduler = st.sidebar.button("Run Scheduler", type="primary", use_container_width=True)

st.sidebar.markdown("### Configuration")
st.sidebar.markdown(
    f"""
    <div class="sidebar-config-card">
        <div class="sidebar-config-title">Solver Time</div>
        <div class="sidebar-config-text">Max solve time: {SOLVER["max_seconds"]} seconds</div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("### Operational Failures")
if FAILURES_ENABLED:
    st.sidebar.warning(f"Enabled | {len(FAILURES)} configured")
else:
    st.sidebar.success("Disabled")


# --- Tabs ------------------------------------------------------------------

summary_tab, station_order_tab, input_data_tab, other_metrics_tab = st.tabs([
    "Summary & Bus Timetable",
    "Station Charging Orders",
    "Input Data Structure",
    "Other Metrics",
])


with input_data_tab:
    st.subheader("Input Data Structure")
    st.markdown("### 1. Global Configuration (config.py)")

    config_tabs = st.tabs([
        "Battery & Charging",
        "Optimization Weights",
        "Solver",
        "Routes",
        "Stations",
        "Operators",
        "Operational Failures",
        "Selected UI Weights",
    ])

    with config_tabs[0]:
        st.json({
            "battery_range_km": BATTERY_RANGE_KM,
            "charge_minutes": CHARGE_MINUTES,
            "speed_kmph": SPEED_KMPH,
        })
    with config_tabs[1]:
        st.json(WEIGHTS)
    with config_tabs[2]:
        st.json(SOLVER)
    with config_tabs[3]:
        st.json(ROUTES)
    with config_tabs[4]:
        st.json(STATIONS)
    with config_tabs[5]:
        st.json(OPERATORS)
    with config_tabs[6]:
        st.markdown("#### Failures Enabled")
        st.json({"enabled": FAILURES_ENABLED,
                 "planned_types": PLANNED_FAILURE_TYPES,
                 "dynamic_types": DYNAMIC_FAILURE_TYPES})
        st.markdown("#### Failure Data")
        st.json(FAILURES)
    with config_tabs[7]:
        st.json(ui_weights)

    st.markdown("### 2. Selected Scenario File")
    st.json(scenario_data)


# --- Run -------------------------------------------------------------------

# Auto-run on first open or when the scenario changes. Moving the weight
# sliders does NOT trigger a solve - the new weights apply only when the user
# clicks Run Scheduler.
scenario_changed = st.session_state.get("run_scenario") != selected_scenario_name
should_run = run_scheduler or scenario_changed

if should_run:
    loader = summary_tab.empty()
    with loader.container():
        render_optimizer_loader(
            f"CP-SAT is solving the selected scenario. Maximum solve time is {SOLVER['max_seconds']} seconds."
        )
    with st.spinner("Solving..."):
        result = Reoptimizer.run(scenario)
    loader.empty()
    st.session_state["result"] = result
    st.session_state["run_scenario"] = selected_scenario_name
    st.session_state["run_weights"] = dict(ui_weights)
else:
    result = st.session_state["result"]

weights_changed = (not should_run) and ui_weights != st.session_state.get("run_weights")


if result["status"] == "NO_SOLUTION":
    st.error("No feasible charging schedule found.")
    st.stop()

summary = build_summary(result)


with summary_tab:
    if weights_changed:
        st.info(
            "Weights changed. Click Run Scheduler in the sidebar to re-optimize. "
            "The results below still use the last run's weights."
        )

    if len(result.get("phases", [])) > 1:
        st.warning(
            "Dynamic failure injection was triggered during the run. "
            "Open the Other Metrics tab to see the re-optimization trace."
        )

    st.subheader("Summary Metrics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Buses", summary["total_buses"])
    col2.metric("Total Wait", f"{summary['total_wait']} min")
    col3.metric("Avg Wait / Bus", f"{summary['average_wait']} min")
    col4.metric("Max Bus Wait", f"{summary['max_wait']} min")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Buses With Wait", summary["buses_with_wait"], delta=f"{summary['buses_with_wait_percent']}%")
    col6.metric("Charging Stops", summary["total_stops"])
    col7.metric("Avg Stops / Bus", summary["average_stops"])
    col8.metric("Max Journey Time", f"{summary['max_journey']} min")
    col8.markdown(
        "<div class='metric-note'>Includes travel + charging + wait time</div>",
        unsafe_allow_html=True,
    )

    st.subheader("Bus Timetable")
    st.dataframe(pd.DataFrame(build_bus_rows(result)), use_container_width=True, hide_index=True)

    st.subheader("Per-Bus Charging Details")
    for bus in result["buses"]:
        with st.expander(f"{bus['bus_id']} | {bus['operator_id']}"):
            charges_df = pd.DataFrame([
                {
                    "Station": charge["station"],
                    "Reached": charge["reached"],
                    "Charge Start": charge["charge_start"],
                    "Charge End": charge["charge_end"],
                    "Wait Minutes": charge["wait_minutes"],
                }
                for charge in bus["charges"]
            ])
            if not charges_df.empty:
                st.dataframe(charges_df, use_container_width=True, hide_index=True)
            else:
                st.info("This bus has no charging events.")


with station_order_tab:
    st.subheader("Station Metrics")
    st.dataframe(pd.DataFrame(build_station_rows(result)), use_container_width=True, hide_index=True)

    st.subheader("Station Charging Orders")
    station_ids = list(STATIONS.keys())
    station_tabs = st.tabs([f"Station {station_id}" for station_id in station_ids])
    for tab, station_id in zip(station_tabs, station_ids):
        with tab:
            sessions = result["stations"].get(station_id, [])
            station_df = pd.DataFrame([
                {
                    "Order": index + 1,
                    "Bus ID": event["bus_id"],
                    "Operator": event["operator_id"],
                    "Charge Start": event["charge_start"],
                    "Charge End": event["charge_end"],
                    "Wait Minutes": event["wait_minutes"],
                }
                for index, event in enumerate(sessions)
            ])
            if not station_df.empty:
                st.dataframe(station_df, use_container_width=True, hide_index=True)
            else:
                st.info("No buses charged at this station.")


with other_metrics_tab:
    st.subheader("Simulation Window")
    st.dataframe(
        pd.DataFrame([{
            "Start Time": summary["start_time"],
            "End Time": summary["end_time"],
            "Duration Minutes": summary["duration"],
        }]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Optimization Weights Used")
    st.dataframe(
        pd.DataFrame([{"Weight": key, "Value": value} for key, value in result["weights"].items()]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Configured Dynamic Failures")
    dynamic_rows = build_dynamic_failure_rows()
    if dynamic_rows:
        st.dataframe(pd.DataFrame(dynamic_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No dynamic failures configured. CHARGER_DOWN and SLOW_CHARGING trigger event-driven re-optimization.")

    render_reoptimization_trace(result)

    st.subheader("Operator Metrics")
    st.dataframe(pd.DataFrame(build_operator_rows(result)), use_container_width=True, hide_index=True)

    st.download_button(
        label="Download Excel Report",
        data=Report.to_excel(result),
        file_name=f"{result['scenario_id']}_scheduler_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
