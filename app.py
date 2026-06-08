import json
from pathlib import Path

import pandas as pd
import streamlit as st

from Backend.scheduler import BusChargingScheduler
from Backend.report_generator import build_excel_report

from Backend.configurations import (
    CHARGER_CONFIG,
    BUS_CONFIG,
    OPTIMIZATION_WEIGHTS,
    SOLVER_CONFIG,
    ROUTES_CONFIG,
    STATIONS_CONFIG,
    OPERATORS_CONFIG,
    OPERATIONAL_FAILURE_SETTINGS,
    OPERATIONAL_FAILURES,
    REOPTIMIZATION_CONFIG,
)


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
            animation: busMove 60s linear 1 forwards;
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
    """Convert HH:MM text into minutes from midnight.
    
    Args:
        time_text (str): Time value in HH:MM format.
    """
    hour, minute = map(int, time_text.split(":"))
    return hour * 60 + minute


def calculate_journey_minutes(departure_time, final_arrival_time) -> int:
    """Calculate total journey duration across midnight when needed.
    
    Args:
        departure_time (str): Scheduled departure time in HH:MM format.
        final_arrival_time (str): Final arrival time in HH:MM format.
    """
    departure_minute = time_to_minutes(departure_time)
    arrival_minute = time_to_minutes(final_arrival_time)

    if arrival_minute < departure_minute:
        arrival_minute += 24 * 60

    return arrival_minute - departure_minute


def get_default_ui_weights(scenario_data) -> dict:
    """Resolve the default weights shown in the UI.
    
    Args:
        scenario_data (dict): Loaded scenario dictionary.
    """
    optimization = scenario_data.get("optimization", {})

    if optimization.get("consider_individual_scenario_weight", False):
        return {
            **OPTIMIZATION_WEIGHTS,
            **optimization.get("weights", {}),
        }

    return dict(OPTIMIZATION_WEIGHTS)


def is_weight_changed(ui_weights, default_ui_weights) -> bool:
    """Check whether UI-selected weights differ from defaults.
    
    Args:
        ui_weights (dict | None): Optimization weights selected from the Streamlit UI.
        default_ui_weights (dict): Default UI weight values for the selected scenario.
    """
    return any(
        abs(float(ui_weights[weight_name]) - float(default_ui_weights[weight_name])) > 0.0001
        for weight_name in OPTIMIZATION_WEIGHTS
    )


def build_bus_rows(result) -> list[dict]:
    """Build table rows for the bus timetable view.
    
    Args:
        result (dict): Final scheduler result dictionary.
    """
    return [
        {
            "Bus ID": bus["bus_id"],
            "Operator": bus["operator_id"],
            "Route": bus["route_id"],
            "Origin": bus["origin"],
            "Destination": bus["destination"],
            "Departure": bus["departure_time"],
            "Charging Plan": " → ".join(bus["charging_plan"]),
            "Wait Minutes": bus["total_wait_minutes"],
            "Charging Stops": bus["total_charging_stops"],
            "Final Arrival": bus["final_arrival_time"],
            "Journey Minutes": calculate_journey_minutes(
                bus["departure_time"],
                bus["final_arrival_time"],
            ),
        }
        for bus in result["bus_timetables"]
    ]


def build_operator_rows(summary) -> list[dict]:
    """Build table rows for operator-level metrics.
    
    Args:
        summary (dict): Computed summary metrics dictionary.
    """
    return [
        {
            "Operator": operator_id,
            "Bus Count": summary["operator_bus_count"].get(operator_id, 0),
            "Total Wait Minutes": summary["operator_total_wait_minutes"].get(operator_id, 0),
            "Average Wait Minutes": summary["operator_average_wait_minutes"].get(operator_id, 0),
            "Max Wait Minutes": summary["operator_max_wait_minutes"].get(operator_id, 0),
        }
        for operator_id in summary["operator_average_wait_minutes"]
    ]


def build_station_rows(summary) -> list[dict]:
    """Build table rows for station-level metrics.
    
    Args:
        summary (dict): Computed summary metrics dictionary.
    """
    return [
        {
            "Station": station_id,
            "Chargers": metrics["charger_count"],
            "Sessions": metrics["total_charging_sessions"],
            "Slow Charging Sessions": metrics.get("slow_charging_sessions", 0),
            "Failure-Affected Sessions": metrics.get("operational_failure_sessions", 0),
            "Total Wait Minutes": metrics["total_wait_minutes"],
            "Average Wait Minutes": metrics["average_wait_minutes"],
            "Max Wait Minutes": metrics["max_wait_minutes"],
            "Total Charging Minutes": metrics["total_charging_minutes"],
            "Utilization %": metrics["charger_utilization_percent"],
        }
        for station_id, metrics in summary["station_metrics"].items()
    ]



def build_excel_report_for_download(result) -> bytes:
    """Build the Excel report without re-running the optimizer.
    
    Args:
        result (dict): Final scheduler result dictionary.
    """
    return build_excel_report(result)


def render_optimizer_loader(message) -> None:
    """Render an animated bus loader while CP-SAT is running.

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


def get_dynamic_failures() -> list[dict]:
    """Return failures that should be injected during runtime re-optimization.
    """
    if not OPERATIONAL_FAILURE_SETTINGS.get(
        "include_operational_failures",
        False,
    ):
        return []

    dynamic_failure_types = set(
        REOPTIMIZATION_CONFIG.get(
            "dynamic_failure_types",
            ["CHARGER_DOWN", "SLOW_CHARGING"],
        )
    )

    return [
        failure
        for failure in OPERATIONAL_FAILURES
        if failure.get("type") in dynamic_failure_types
    ]


def build_dynamic_failure_rows() -> list[dict]:
    """Build table rows for configured dynamic failures.
    """
    return [
        {
            "Failure ID": failure.get("operational_failure_id"),
            "Type": failure.get("type"),
            "Station": failure.get("station_id"),
            "Charger": failure.get("charger_id", "-"),
            "Start Time": failure.get("start_time"),
            "End Time": failure.get("end_time"),
            "Reason": failure.get("reason", "-"),
        }
        for failure in get_dynamic_failures()
    ]


def build_reoptimization_phase_rows(result) -> list[dict]:
    """Build table rows for every re-optimization phase.
    
    Args:
        result (dict): Final scheduler result dictionary.
    """
    reoptimization_summary = result.get("reoptimization_summary", {})

    return [
        {
            "Phase": phase.get("phase"),
            "Trigger Time": phase.get("trigger_time") or "-",
            "Triggered Failure": (
                phase.get("triggered_failure", {}) or {}
            ).get("operational_failure_id", "-"),
            "Failure Type": (
                phase.get("triggered_failure", {}) or {}
            ).get("type", "-"),
            "Active Failure IDs": ", ".join(phase.get("active_failure_ids", [])),
            "Frozen Decisions": phase.get("frozen_decision_count", 0),
            "Status": phase.get("status"),
            "Total Wait Minutes": phase.get("total_wait_minutes"),
            "Solver Time Seconds": phase.get("solver_wall_time_seconds"),
        }
        for phase in reoptimization_summary.get("phases", [])
    ]


def render_reoptimization_timeline(result) -> None:
    """Render the dynamic failure injection trace in Streamlit.
    
    Args:
        result (dict): Final scheduler result dictionary.
    """
    reoptimization_summary = result.get("reoptimization_summary")

    if not reoptimization_summary:
        st.info(
            "Event-driven re-optimization did not run for this scenario. "
            "Enable CHARGER_DOWN or SLOW_CHARGING in the configured operational failures to trigger it."
        )
        return

    st.markdown("### Event-driven CP-SAT Re-optimization Trace")

    st.info(
        "This trace shows the dynamic failure being injected during the logical run. "
        "The first CP-SAT phase creates the initial plan. When the configured dynamic failure time is reached, "
        "the failure is injected and CP-SAT re-solves the remaining schedule."
    )

    for index, phase in enumerate(reoptimization_summary.get("phases", []), start=1):
        triggered_failure = phase.get("triggered_failure")

        if triggered_failure:
            card_class = "reopt-injection-card"
            title = (
                f"Phase {index}: Failure injected at {phase.get('trigger_time')} "
                f"→ {triggered_failure.get('type')}"
            )
            details = [
                f"Failure ID: {triggered_failure.get('operational_failure_id')}",
                f"Station: {triggered_failure.get('station_id')}",
                f"Charger: {triggered_failure.get('charger_id', '-')}",
                f"Reason: {triggered_failure.get('reason', '-')}",
                f"Frozen decisions before failure time: {phase.get('frozen_decision_count', 0)}",
                f"Re-optimized status: {phase.get('status')}",
                f"Re-optimized total wait: {phase.get('total_wait_minutes')} minutes",
                f"Re-solve time: {phase.get('solver_wall_time_seconds')} seconds",
            ]
        else:
            card_class = "reopt-card"
            title = "Phase 1: Initial CP-SAT plan before dynamic failure injection"
            details = [
                f"Status: {phase.get('status')}",
                f"Initial total wait: {phase.get('total_wait_minutes')} minutes",
                f"Solve time: {phase.get('solver_wall_time_seconds')} seconds",
                "Dynamic failures are not considered in this initial phase.",
            ]

        details_html = "".join(
            f'<div class="reopt-card-text">{detail}</div>'
            for detail in details
        )

        st.markdown(
            f"""
            <div class="{card_class}">
                <div class="reopt-card-title">{title}</div>
                {details_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.dataframe(
        pd.DataFrame(build_reoptimization_phase_rows(result)),
        use_container_width=True,
        hide_index=True,
    )


st.title("Bus Charging Scheduler")


scenario_files = sorted(SCENARIO_FOLDER.glob("*.json"))

if not scenario_files:
    st.error("No scenario files found in Backend/scenarios.")
    st.stop()


scenario_names = [
    scenario_file.name
    for scenario_file in scenario_files
]


selected_scenario_name = st.sidebar.selectbox(
    "Select Scenario",
    scenario_names,
)


selected_scenario_path = SCENARIO_FOLDER / selected_scenario_name


with open(selected_scenario_path, "r") as file:
    scenario_data = json.load(file)


default_ui_weights = get_default_ui_weights(scenario_data)


st.sidebar.markdown("### Selected Scenario")
st.sidebar.write(
    scenario_data.get(
        "scenario_name",
        selected_scenario_name,
    )
)


st.sidebar.markdown("### Optimization Weights")

ui_weights = {}

for weight_name in OPTIMIZATION_WEIGHTS:
    ui_weights[weight_name] = st.sidebar.slider(
        label=weight_name,
        min_value=0.0,
        max_value=3.0,
        value=float(default_ui_weights.get(weight_name, OPTIMIZATION_WEIGHTS[weight_name])),
        step=0.1,
        format="%.1f",
        key=f"{selected_scenario_name}_{weight_name}",
    )


run_scheduler = st.sidebar.button(
    "Run Scheduler",
    type="primary",
    use_container_width=True,
)

weights_changed = is_weight_changed(
    ui_weights,
    default_ui_weights,
)

should_run_scheduler = (
    not weights_changed
    or run_scheduler
)


st.sidebar.markdown("### Configuration")

st.sidebar.markdown(
    f"""
    <div class="sidebar-config-card">
        <div class="sidebar-config-title">Solver Time</div>
        <div class="sidebar-config-text">Max solve time: {SOLVER_CONFIG["max_solve_time_seconds"]} seconds</div>
    </div>
    """,
    unsafe_allow_html=True,
)


st.sidebar.markdown("### Operational Failures")

operational_failures_enabled = OPERATIONAL_FAILURE_SETTINGS.get(
    "include_operational_failures",
    False,
)

if operational_failures_enabled:
    st.sidebar.warning(
        f"Enabled | {len(OPERATIONAL_FAILURES)} configured"
    )
else:
    st.sidebar.success("Disabled")


input_data_tab, summary_tab, station_order_tab, other_metrics_tab = st.tabs([
    "Input Data Structure",
    "Summary & Bus Timetable",
    "Station Charging Orders",
    "Other Metrics",
])

summary_loading_placeholder = summary_tab.empty()
station_loading_placeholder = station_order_tab.empty()
metrics_loading_placeholder = other_metrics_tab.empty()


with input_data_tab:
    st.subheader("Input Data Structure")

    st.markdown("### 1. Global Configuration")

    config_tabs = st.tabs([
        "Bus Config",
        "Charger Config",
        "Optimization Weights",
        "Solver Config",
        "Routes",
        "Stations",
        "Operators",
        "Operational Failures",
        "Re-optimization",
        "Selected UI Weights",
    ])

    with config_tabs[0]:
        st.json(BUS_CONFIG)

    with config_tabs[1]:
        st.json(CHARGER_CONFIG)

    with config_tabs[2]:
        st.json(OPTIMIZATION_WEIGHTS)

    with config_tabs[3]:
        st.json(SOLVER_CONFIG)

    with config_tabs[4]:
        st.json(ROUTES_CONFIG)

    with config_tabs[5]:
        st.json(STATIONS_CONFIG)

    with config_tabs[6]:
        st.json(OPERATORS_CONFIG)

    with config_tabs[7]:
        st.markdown("#### Operational Failure Settings")
        st.json(OPERATIONAL_FAILURE_SETTINGS)

        st.markdown("#### Operational Failure Data")
        st.json(OPERATIONAL_FAILURES)

    with config_tabs[8]:
        st.json(REOPTIMIZATION_CONFIG)

    with config_tabs[9]:
        st.json(ui_weights)

    st.markdown("### 2. Selected Scenario File")
    st.json(scenario_data)


if not should_run_scheduler:
    with summary_tab:
        st.info(
            "Weights were adjusted. Click Run Scheduler from the sidebar to recalculate the schedule."
        )

    with station_order_tab:
        st.info(
            "Station metrics and charging orders will appear after clicking Run Scheduler."
        )

    with other_metrics_tab:
        st.info(
            "Additional metrics and Excel download will appear after clicking Run Scheduler."
        )

    st.stop()


max_solve_time = SOLVER_CONFIG["max_solve_time_seconds"]


dynamic_failures = get_dynamic_failures()
reoptimization_enabled = REOPTIMIZATION_CONFIG.get(
    "enabled",
    False,
)

if should_run_scheduler:
    optimizer_message = summary_loading_placeholder

    with station_loading_placeholder.container():
        st.info(
            "Station charging orders are being recalculated for the selected scenario."
        )

    with metrics_loading_placeholder.container():
        st.info(
            "Other metrics and the Excel download will appear after the fresh optimization run completes."
        )

    try:
        if reoptimization_enabled and dynamic_failures:
            with optimizer_message.status(
                "Event-driven CP-SAT run in progress...",
                expanded=True,
            ) as run_status:
                render_optimizer_loader(
                    "Building the initial CP-SAT schedule. Dynamic failures will be injected when their configured time is reached."
                )

                st.write(
                    "Phase 1: Building the initial CP-SAT schedule without dynamic failures."
                )

                for failure in dynamic_failures:
                    st.write(
                        f"Queued dynamic failure: {failure.get('type')} "
                        f"at {failure.get('start_time')} "
                        f"for Station {failure.get('station_id')}."
                    )

                scheduler = BusChargingScheduler(
                    scenario_path=str(selected_scenario_path),
                    ui_weights=ui_weights,
                )

                result = scheduler.solve(
                    include_timeline=False,
                )

                if result.get("reoptimization_summary"):
                    for phase in result["reoptimization_summary"].get("phases", []):
                        triggered_failure = phase.get("triggered_failure")

                        if triggered_failure:
                            st.write(
                                f"Injected {triggered_failure.get('type')} "
                                f"at {phase.get('trigger_time')} "
                                f"and re-ran CP-SAT for the remaining schedule."
                            )

                    run_status.update(
                        label="Event-driven CP-SAT re-optimization completed.",
                        state="complete",
                        expanded=True,
                    )
                else:
                    run_status.update(
                        label="CP-SAT completed. No dynamic failure injection was triggered.",
                        state="complete",
                        expanded=True,
                    )
        else:
            with optimizer_message:
                render_optimizer_loader(
                    f"CP-SAT is solving the selected scenario. Maximum solve time is {max_solve_time} seconds."
                )

                scheduler = BusChargingScheduler(
                    scenario_path=str(selected_scenario_path),
                    ui_weights=ui_weights,
                )

                result = scheduler.solve(
                    include_timeline=False,
                )

        optimizer_message.empty()
        summary_loading_placeholder.empty()
        station_loading_placeholder.empty()
        metrics_loading_placeholder.empty()

    except ValueError as error:
        optimizer_message.empty()
        station_loading_placeholder.empty()
        metrics_loading_placeholder.empty()
        st.error(str(error))
        st.stop()


if result["status"] == "NO_SOLUTION":
    st.error(result["message"])
    st.stop()


summary = result["summary"]

journey_times = [
    calculate_journey_minutes(
        bus["departure_time"],
        bus["final_arrival_time"],
    )
    for bus in result["bus_timetables"]
]

max_journey_time = max(journey_times) if journey_times else 0


with summary_tab:
    if result.get("reoptimization_summary"):
        dynamic_failures_processed = result["reoptimization_summary"].get(
            "dynamic_failures_processed",
            0,
        )

        st.warning(
            f"Dynamic failure injection was triggered during the run. "
            f"Processed dynamic failures: {dynamic_failures_processed}. "
            "Open the Other Metrics tab to see the event-driven re-optimization trace."
        )

    st.subheader("Summary Metrics")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Total Buses",
        summary["total_buses"],
    )

    col2.metric(
        "Total Wait",
        f"{summary['total_wait_minutes']} min",
    )

    col3.metric(
        "Avg Wait / Bus",
        f"{summary['average_wait_per_bus']} min",
    )

    col4.metric(
        "Max Bus Wait",
        f"{summary['max_bus_wait_minutes']} min",
    )

    col5, col6, col7, col8 = st.columns(4)

    col5.metric(
        "Buses With Wait",
        summary["buses_with_wait"],
        delta=f"{summary['buses_with_wait_percent']}%",
    )

    col6.metric(
        "Charging Stops",
        summary["total_charging_stops"],
    )

    col7.metric(
        "Avg Stops / Bus",
        summary["average_charging_stops_per_bus"],
    )

    col8.metric(
        "Max Journey Time",
        f"{max_journey_time} min",
    )

    col8.markdown(
        "<div class='metric-note'>Includes travel + charging + wait time</div>",
        unsafe_allow_html=True,
    )

    st.subheader("Bus Timetable")

    st.dataframe(
        pd.DataFrame(build_bus_rows(result)),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Per-Bus Charging Details")

    for bus in result["bus_timetables"]:
        with st.expander(
            f"{bus['bus_id']} | {bus['operator_id']}"
        ):
            charging_events_df = pd.DataFrame(
                bus["charging_events"],
            )

            if not charging_events_df.empty:
                st.dataframe(
                    charging_events_df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.info("This bus has no charging events.")


with station_order_tab:
    st.subheader("Station Metrics")

    st.dataframe(
        pd.DataFrame(build_station_rows(summary)),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Station Charging Orders")

    station_ids = list(
        result["station_charging_orders"].keys()
    )

    if station_ids:
        station_tabs = st.tabs([
            f"Station {station_id}"
            for station_id in station_ids
        ])

        for tab, station_id in zip(station_tabs, station_ids):
            with tab:
                station_order_df = pd.DataFrame(
                    result["station_charging_orders"][station_id],
                )

                st.dataframe(
                    station_order_df,
                    use_container_width=True,
                    hide_index=True,
                )
    else:
        st.info("No station charging orders available.")


with other_metrics_tab:
    st.subheader("Simulation Window")

    simulation_window_df = pd.DataFrame([
        {
            "Start Time": summary["simulation_start_time"],
            "End Time": summary["simulation_end_time"],
            "Duration Minutes": summary["simulation_duration_minutes"],
        }
    ])

    st.dataframe(
        simulation_window_df,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Optimization Weights Used")

    weight_rows = [
        {
            "Weight": key,
            "Value": value,
        }
        for key, value in result["optimization_weights"].items()
    ]

    st.dataframe(
        pd.DataFrame(weight_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Configured Dynamic Failures")

    dynamic_failure_rows = build_dynamic_failure_rows()

    if dynamic_failure_rows:
        st.dataframe(
            pd.DataFrame(dynamic_failure_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No dynamic failures configured. CHARGER_DOWN and SLOW_CHARGING trigger event-driven re-optimization.")

    render_reoptimization_timeline(result)

    st.subheader("Operator Metrics")

    st.dataframe(
        pd.DataFrame(build_operator_rows(summary)),
        use_container_width=True,
        hide_index=True,
    )

    excel_file = build_excel_report_for_download(result)

    st.download_button(
        label="Download Excel Report",
        data=excel_file,
        file_name=f"{result['scenario_id']}_scheduler_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
