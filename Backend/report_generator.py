"""Excel export of a schedule, with visual validation against the hard rules.

Everything here is derived from the schedule result plus the static config, so
no other module needs to change. Sheets produced:

  Summary            headline + fairness + validation metrics
  Hard Rule Checks   one PASS/FAIL row per hard rule
  Range Checks       per-bus longest leg vs the 240 km limit
  Bus Timetable      one row per charge
  Station Order      per-station charging order
  Operator Metrics   per-operator wait
  Station Metrics    per-station load
  Event Log          heap-ordered chronological charge events
  Bus Timeline       per-bus km-vs-time grid (travel / wait / charge / arrived)
  Charger Timeline   per-charger occupancy grid (bus id / OVERLAP)

The two timeline sheets mirror the original report: leading validation columns
plus one column per 5-minute slot, coloured by activity.
"""

import io

import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from Backend.configurations import STATIONS, ROUTES, OPERATORS, CHARGE_MINUTES, BATTERY_RANGE_KM
from Backend.route_utils import RouteMap
from Backend.time_utils import TimeUtils
from Backend.event_queue import charging_event_stream, count_charger_overlaps, charge_duration

SLOT_MINUTES = 5            # width of one timeline column

HEADER_FILL = "1F1F1F"
HEADER_FONT = "FFFFFF"
TRAVEL_FILL = "9DC3E6"
WAIT_FILL = "F4B183"
CHARGING_FILL = "A9D18E"
ARRIVED_FILL = "D9D9D9"
ISSUE_FILL = "FF6666"
IDLE_FILL = "FFFFFF"

THIN_BORDER = Border(
    left=Side(style="thin", color="D9D9D9"),
    right=Side(style="thin", color="D9D9D9"),
    top=Side(style="thin", color="D9D9D9"),
    bottom=Side(style="thin", color="D9D9D9"),
)
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)

BUS_TIMELINE_FIXED_COLUMNS = 11
CHARGER_TIMELINE_FIXED_COLUMNS = 3


class Report:
    """Builds a downloadable Excel workbook from a schedule result."""

    @staticmethod
    def to_excel(result):
        """Render a schedule result as an .xlsx workbook in memory.

        Args:
            result (dict): A schedule from Scheduler.solve / Reoptimizer.run.

        Returns:
            bytes: The Excel workbook contents.
        """
        tabular = {
            "Summary": Report._summary_sheet,
            "Hard Rule Checks": Report._hard_rule_sheet,
            "Range Checks": Report._range_sheet,
            "Bus Timetable": Report._bus_sheet,
            "Station Order": Report._station_sheet,
            "Operator Metrics": Report._operator_sheet,
            "Station Metrics": Report._station_metric_sheet,
            "Event Log": Report._event_log_sheet,
        }

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for name, builder in tabular.items():
                builder(result).to_excel(writer, sheet_name=name, index=False)
            Report._bus_timeline_dataframe(result).to_excel(writer, sheet_name="Bus Timeline", index=False)
            Report._charger_timeline_dataframe(result).to_excel(writer, sheet_name="Charger Timeline", index=False)

            for name in tabular:
                Report._style_header(writer.sheets[name])
            Report._style_bus_timeline(writer.sheets["Bus Timeline"])
            Report._style_charger_timeline(writer.sheets["Charger Timeline"])

        return buffer.getvalue()

    # --- tabular sheets ----------------------------------------------------

    @staticmethod
    def _summary_sheet(result):
        """Headline, fairness and validation numbers.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per metric.
        """
        buses = result["buses"]
        waits = [bus["total_wait_minutes"] for bus in buses]
        max_leg, headroom = Report._range_extremes(result)
        overlaps = count_charger_overlaps(result)
        operator_avg = Report._operator_average_wait(result)
        fairness_gap = round(max(operator_avg.values()) - min(operator_avg.values()), 2) if operator_avg else 0

        rows = [
            ("Scenario", result["scenario_name"]),
            ("Status", result["status"]),
            ("Buses", len(buses)),
            ("Total wait (min)", sum(waits)),
            ("Average wait per bus (min)", round(sum(waits) / len(buses), 2) if buses else 0),
            ("Max single-bus wait (min)", max(waits) if waits else 0),
            ("Buses that waited", sum(1 for w in waits if w > 0)),
            ("Total charging stops", sum(len(bus["plan"]) for bus in buses)),
            ("Operator fairness gap (min)", fairness_gap),
            ("Longest leg between charges (km)", max_leg),
            ("Range headroom (km)", headroom),
            ("Charger double-bookings", overlaps),
            ("All hard rules satisfied", "YES" if overlaps == 0 and max_leg <= BATTERY_RANGE_KM else "NO"),
        ]
        return pd.DataFrame(rows, columns=["Metric", "Value"])

    @staticmethod
    def _hard_rule_sheet(result):
        """One PASS/FAIL row per hard rule for quick validation.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: Rule, Result, Detail.
        """
        max_leg, headroom = Report._range_extremes(result)
        overlaps = count_charger_overlaps(result)
        durations = sorted({
            charge_duration(charge["charge_start"], charge["charge_end"])
            for bus in result["buses"]
            for charge in bus["charges"]
        })
        backtracks = Report._backtrack_count(result)

        rows = [
            ("Battery range: every leg <= 240 km",
             "PASS" if max_leg <= BATTERY_RANGE_KM else "FAIL",
             f"longest leg {max_leg} km, headroom {headroom} km"),
            ("One bus per charger at a time",
             "PASS" if overlaps == 0 else "FAIL",
             f"{overlaps} overlapping charging sessions"),
            ("Charging duration fixed",
             "PASS" if durations and min(durations) >= CHARGE_MINUTES else "FAIL",
             f"observed durations (min): {durations or [CHARGE_MINUTES]}"),
            ("Stations visited in route order (no backtracking)",
             "PASS" if backtracks == 0 else "FAIL",
             f"{backtracks} out-of-order charging plans"),
        ]
        return pd.DataFrame(rows, columns=["Hard Rule", "Result", "Detail"])

    @staticmethod
    def _range_sheet(result):
        """Per-bus longest leg vs the battery range.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per bus.
        """
        rows = []
        for bus in result["buses"]:
            route = ROUTES[bus["route_id"]]
            checkpoints = [bus["origin"]] + list(bus["plan"]) + [bus["destination"]]
            legs = [RouteMap.distance_km(route, checkpoints[i], checkpoints[i + 1])
                    for i in range(len(checkpoints) - 1)]
            longest = max(legs)
            rows.append({
                "Bus": bus["bus_id"],
                "Operator": bus["operator_id"],
                "Charging Plan": " -> ".join(bus["plan"]),
                "Legs (km)": " | ".join(str(leg) for leg in legs),
                "Longest Leg (km)": longest,
                "Range Headroom (km)": BATTERY_RANGE_KM - longest,
                "Within 240 km": "Yes" if longest <= BATTERY_RANGE_KM else "No",
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _bus_sheet(result):
        """One row per charge, giving each bus's full timeline.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: Flattened per-charge timetable.
        """
        rows = []
        for bus in result["buses"]:
            for charge in bus["charges"]:
                rows.append({
                    "Bus": bus["bus_id"],
                    "Operator": bus["operator_id"],
                    "Departure": bus["departure"],
                    "Station": charge["station"],
                    "Reached": charge["reached"],
                    "Charge start": charge["charge_start"],
                    "Charge end": charge["charge_end"],
                    "Wait (min)": charge["wait_minutes"],
                    "Arrival": bus["arrival"],
                    "Total wait (min)": bus["total_wait_minutes"],
                })
        return pd.DataFrame(rows)

    @staticmethod
    def _station_sheet(result):
        """Per-station charging order.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per charge, ordered per station.
        """
        rows = []
        for station in STATIONS:
            for order, charge in enumerate(result["stations"].get(station, []), start=1):
                rows.append({
                    "Station": station,
                    "Order": order,
                    "Bus": charge["bus_id"],
                    "Operator": charge["operator_id"],
                    "Charge start": charge["charge_start"],
                    "Charge end": charge["charge_end"],
                    "Wait (min)": charge["wait_minutes"],
                })
        return pd.DataFrame(rows)

    @staticmethod
    def _operator_sheet(result):
        """Per-operator wait metrics.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per operator.
        """
        waits = {}
        for bus in result["buses"]:
            waits.setdefault(bus["operator_id"], []).append(bus["total_wait_minutes"])
        return pd.DataFrame([
            {
                "Operator": operator_id,
                "Bus Count": len(values),
                "Total Wait (min)": sum(values),
                "Average Wait (min)": round(sum(values) / len(values), 2),
                "Max Wait (min)": max(values),
            }
            for operator_id, values in waits.items()
        ])

    @staticmethod
    def _station_metric_sheet(result):
        """Per-station load metrics.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per station.
        """
        rows = []
        for station in STATIONS:
            sessions = result["stations"].get(station, [])
            waits = [event["wait_minutes"] for event in sessions]
            rows.append({
                "Station": station,
                "Chargers": STATIONS[station]["chargers"],
                "Sessions": len(sessions),
                "Total Wait (min)": sum(waits),
                "Average Wait (min)": round(sum(waits) / len(waits), 2) if waits else 0,
                "Max Wait (min)": max(waits) if waits else 0,
                "Charging Minutes": len(sessions) * CHARGE_MINUTES,
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _event_log_sheet(result):
        """Chronological charging event log, ordered by the heap merge.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: Time-ordered CHARGE_START / CHARGE_END events.
        """
        rows = []
        for minute, kind, payload in charging_event_stream(result):
            rows.append({
                "Time": TimeUtils.to_clock(minute),
                "Minute": minute,
                "Event": kind,
                "Bus": payload["bus_id"],
                "Operator": payload["operator_id"],
                "Station": payload["station"],
            })
        return pd.DataFrame(rows)

    # --- bus timeline (km vs time) ----------------------------------------

    @staticmethod
    def _bus_timeline_rows(result):
        """Build each bus's activity track with kilometres-since-last-charge.

        Args:
            result (dict): A schedule result.

        Returns:
            list[dict]: Per-bus records carrying metadata plus an 'activities'
                list of TRAVEL / WAIT / CHARGING spans with km bookkeeping.
        """
        records = []
        for bus in result["buses"]:
            route = ROUTES[bus["route_id"]]
            route_distance = sum(route["segment_km"])
            current_station = bus["origin"]
            current_minute = bus["departure_minute"]
            since_charge = 0
            covered = 0
            max_between = 0
            activities = []

            for charge in bus["charges"]:
                station = charge["station"]
                reached = current_minute + RouteMap.travel_minutes(route, current_station, station)
                charge_start = charge["start_minute"]
                charge_end = charge_start + charge_duration(charge["charge_start"], charge["charge_end"])
                travel = RouteMap.distance_km(route, current_station, station)

                activities.append({
                    "activity": "TRAVEL", "from": current_station, "to": station,
                    "station": station, "charger": "",
                    "start_minute": current_minute, "end_minute": reached,
                    "start_km": since_charge, "distance_km": travel,
                })
                since_charge += travel
                covered += travel
                max_between = max(max_between, since_charge)

                if charge_start > reached:
                    activities.append({
                        "activity": "WAIT", "from": "", "to": station,
                        "station": station, "charger": "",
                        "start_minute": reached, "end_minute": charge_start,
                        "start_km": since_charge, "distance_km": 0,
                    })

                activities.append({
                    "activity": "CHARGING", "from": "", "to": station,
                    "station": station, "charger": f"{station}-1",
                    "start_minute": charge_start, "end_minute": charge_end,
                    "start_km": since_charge, "distance_km": 0,
                })
                current_station = station
                current_minute = charge_end
                since_charge = 0

            final_travel = RouteMap.distance_km(route, current_station, bus["destination"])
            final_arrival = current_minute + final_travel
            activities.append({
                "activity": "TRAVEL", "from": current_station, "to": bus["destination"],
                "station": bus["destination"], "charger": "",
                "start_minute": current_minute, "end_minute": final_arrival,
                "start_km": since_charge, "distance_km": final_travel,
            })
            since_charge += final_travel
            covered += final_travel
            max_between = max(max_between, since_charge)

            records.append({
                "bus_id": bus["bus_id"],
                "operator_id": bus["operator_id"],
                "route_id": bus["route_id"],
                "departure_time": bus["departure"],
                "final_arrival_time": TimeUtils.to_clock(final_arrival),
                "charging_plan": bus["plan"],
                "route_distance_km": route_distance,
                "distance_covered_km": round(covered, 2),
                "completed": "YES" if round(covered, 2) == round(route_distance, 2) else "NO",
                "max_km_between_charges": round(max_between, 2),
                "range_valid": "YES" if max_between <= BATTERY_RANGE_KM else "NO",
                "activities": activities,
                "departure_minute": bus["departure_minute"],
                "final_arrival_minute": final_arrival,
            })
        return records

    @staticmethod
    def _bus_timeline_dataframe(result):
        """Bus timeline grid: metadata columns plus one column per 5-min slot.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per bus.
        """
        data = Report._bus_timeline_rows(result)
        if not data:
            return pd.DataFrame()

        start = Report._floor_to_slot(min(record["departure_minute"] for record in data))
        end = Report._ceil_to_slot(max(record["final_arrival_minute"] for record in data))
        slots = list(range(start, end + 1, SLOT_MINUTES))

        rows = []
        for record in data:
            row = {
                "Bus ID": record["bus_id"],
                "Operator": record["operator_id"],
                "Route": record["route_id"],
                "Departure": record["departure_time"],
                "Final Arrival": record["final_arrival_time"],
                "Route Distance km": record["route_distance_km"],
                "Distance Covered km": record["distance_covered_km"],
                "Completed?": record["completed"],
                "Max Km Between Charges": record["max_km_between_charges"],
                "Range Valid?": record["range_valid"],
                "Charging Plan": " -> ".join(record["charging_plan"]),
            }
            for slot_start in slots:
                row[TimeUtils.to_clock(slot_start)] = Report._bus_timeline_cell(
                    record, slot_start, slot_start + SLOT_MINUTES)
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _bus_timeline_cell(record, slot_start, slot_end):
        """Text for one bus/slot cell: activity tag plus km read-out.

        Args:
            record (dict): A bus timeline record (see _bus_timeline_rows).
            slot_start (int): Slot start minute.
            slot_end (int): Slot end minute.

        Returns:
            str: Cell text, '' when the bus is idle in this slot.
        """
        if slot_start >= record["final_arrival_minute"]:
            return f"ARR\n{record['route_distance_km']}km total"

        for activity in record["activities"]:
            if slot_start < activity["end_minute"] and slot_end > activity["start_minute"]:
                if activity["activity"] == "TRAVEL":
                    start_km, end_km = Report._km_range_for_slot(activity, slot_start, slot_end)
                    return f"T:{activity['from']}->{activity['to']}\n{start_km}-{end_km}km"
                if activity["activity"] == "WAIT":
                    return f"W:{activity['station']}\n{round(activity['start_km'], 1)}km"
                return f"C:{activity['station']}/{activity['charger']}\nRESET->0km"
        return ""

    @staticmethod
    def _km_range_for_slot(activity, slot_start, slot_end):
        """Kilometres covered during the part of a travel activity in a slot.

        Args:
            activity (dict): A TRAVEL activity span.
            slot_start (int): Slot start minute.
            slot_end (int): Slot end minute.

        Returns:
            tuple[float, float]: (start_km, end_km) since the last charge.
        """
        duration = max(activity["end_minute"] - activity["start_minute"], 1)
        clipped_start = max(slot_start, activity["start_minute"])
        clipped_end = min(slot_end, activity["end_minute"])
        start_ratio = (clipped_start - activity["start_minute"]) / duration
        end_ratio = (clipped_end - activity["start_minute"]) / duration
        start_km = activity["start_km"] + activity["distance_km"] * start_ratio
        end_km = activity["start_km"] + activity["distance_km"] * end_ratio
        return round(start_km, 1), round(end_km, 1)

    # --- charger timeline -------------------------------------------------

    @staticmethod
    def _charger_events(result):
        """Charging sessions per charger, flagged for overlaps.

        Args:
            result (dict): A schedule result.

        Returns:
            dict[str, list[dict]]: charger id -> sessions, each carrying
                start_minute, end_minute, bus_id and an 'overlap' flag.
        """
        by_charger = {}
        for station in STATIONS:
            for event in result["stations"].get(station, []):
                charger_id = f"{station}-1"
                start = event["start_minute"]
                end = start + charge_duration(event["charge_start"], event["charge_end"])
                by_charger.setdefault(charger_id, []).append({
                    "bus_id": event["bus_id"],
                    "start_minute": start,
                    "end_minute": end,
                    "overlap": "NO",
                })

        for sessions in by_charger.values():
            sessions.sort(key=lambda item: item["start_minute"])
            for index in range(1, len(sessions)):
                if sessions[index]["start_minute"] < sessions[index - 1]["end_minute"]:
                    sessions[index]["overlap"] = "YES"
                    sessions[index - 1]["overlap"] = "YES"
        return by_charger

    @staticmethod
    def _charger_timeline_dataframe(result):
        """Charger timeline grid: which bus holds each charger in each slot.

        Args:
            result (dict): A schedule result.

        Returns:
            pandas.DataFrame: One row per charger.
        """
        by_charger = Report._charger_events(result)
        charger_ids = [
            f"{station}-{number}"
            for station in STATIONS
            for number in range(1, STATIONS[station]["chargers"] + 1)
        ]
        all_sessions = [s for sessions in by_charger.values() for s in sessions]
        if not all_sessions:
            return pd.DataFrame()

        start = Report._floor_to_slot(min(s["start_minute"] for s in all_sessions))
        end = Report._ceil_to_slot(max(s["end_minute"] for s in all_sessions))
        slots = list(range(start, end + 1, SLOT_MINUTES))

        rows = []
        for charger_id in charger_ids:
            sessions = by_charger.get(charger_id, [])
            row = {
                "Station": charger_id.split("-")[0],
                "Charger": charger_id,
                "Overlap Check": "YES" if any(s["overlap"] == "YES" for s in sessions) else "NO",
            }
            for slot_start in slots:
                row[TimeUtils.to_clock(slot_start)] = Report._charger_timeline_cell(
                    sessions, slot_start, slot_start + SLOT_MINUTES)
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _charger_timeline_cell(sessions, slot_start, slot_end):
        """Text for one charger/slot cell.

        Args:
            sessions (list[dict]): Sessions on this charger.
            slot_start (int): Slot start minute.
            slot_end (int): Slot end minute.

        Returns:
            str: Bus id occupying the charger, 'OVERLAP' if more than one, or ''.
        """
        active = [s for s in sessions
                  if slot_start < s["end_minute"] and slot_end > s["start_minute"]]
        if not active:
            return ""
        if len(active) > 1:
            return "OVERLAP"
        return active[0]["bus_id"]

    # --- shared metric helpers --------------------------------------------

    @staticmethod
    def _range_extremes(result):
        """Longest leg between charges and the resulting range headroom.

        Args:
            result (dict): A schedule result.

        Returns:
            tuple[int, int]: (longest leg km, 240 - longest leg).
        """
        longest = 0
        for bus in result["buses"]:
            route = ROUTES[bus["route_id"]]
            checkpoints = [bus["origin"]] + list(bus["plan"]) + [bus["destination"]]
            for i in range(len(checkpoints) - 1):
                longest = max(longest, RouteMap.distance_km(route, checkpoints[i], checkpoints[i + 1]))
        return longest, BATTERY_RANGE_KM - longest

    @staticmethod
    def _backtrack_count(result):
        """Count buses whose charging plan is not in route order.

        Args:
            result (dict): A schedule result.

        Returns:
            int: Number of plans that backtrack (0 = rule holds).
        """
        count = 0
        for bus in result["buses"]:
            stops = ROUTES[bus["route_id"]]["stops"]
            positions = [stops.index(station) for station in bus["plan"]]
            if positions != sorted(positions):
                count += 1
        return count

    @staticmethod
    def _operator_average_wait(result):
        """Average wait per operator.

        Args:
            result (dict): A schedule result.

        Returns:
            dict[str, float]: operator id -> average wait minutes.
        """
        waits = {}
        for bus in result["buses"]:
            waits.setdefault(bus["operator_id"], []).append(bus["total_wait_minutes"])
        return {operator: sum(values) / len(values) for operator, values in waits.items()}

    # --- styling -----------------------------------------------------------

    @staticmethod
    def _floor_to_slot(minute):
        """Round a minute down to the start of its 5-minute slot.

        Args:
            minute (int): A time in minutes.

        Returns:
            int: The slot start minute.
        """
        return minute - (minute % SLOT_MINUTES)

    @staticmethod
    def _ceil_to_slot(minute):
        """Round a minute up to the next 5-minute slot boundary.

        Args:
            minute (int): A time in minutes.

        Returns:
            int: The slot boundary minute.
        """
        remainder = minute % SLOT_MINUTES
        return minute if remainder == 0 else minute + (SLOT_MINUTES - remainder)

    @staticmethod
    def _style_header(worksheet):
        """Dark header row, wrapped text and roomy columns.

        Args:
            worksheet (openpyxl.worksheet.worksheet.Worksheet): Sheet to style.
        """
        for cell in worksheet[1]:
            cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
            cell.font = Font(color=HEADER_FONT, bold=True)
            cell.alignment = CENTER
            cell.border = THIN_BORDER
        for column_cells in worksheet.columns:
            width = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=8)
            worksheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(width + 3, 40)
        worksheet.freeze_panes = "A2"

    @staticmethod
    def _style_bus_timeline(worksheet):
        """Colour the bus timeline by activity and flag invalid buses.

        Args:
            worksheet (openpyxl.worksheet.worksheet.Worksheet): The sheet.
        """
        Report._style_timeline_header(worksheet)
        fixed = BUS_TIMELINE_FIXED_COLUMNS
        for row in worksheet.iter_rows(min_row=2):
            if len(row) < fixed:
                continue
            if row[7].value != "YES" or row[9].value != "YES":
                for cell in row[:fixed]:
                    cell.fill = PatternFill("solid", fgColor=ISSUE_FILL)
            for cell in row[fixed:]:
                Report._paint_timeline_cell(cell, Report._bus_cell_fill(str(cell.value or "")))
        Report._size_timeline(worksheet, fixed, fixed_width=14, slot_width=16, row_height=34)

    @staticmethod
    def _style_charger_timeline(worksheet):
        """Colour the charger timeline and flag overlapping chargers.

        Args:
            worksheet (openpyxl.worksheet.worksheet.Worksheet): The sheet.
        """
        Report._style_timeline_header(worksheet)
        fixed = CHARGER_TIMELINE_FIXED_COLUMNS
        for row in worksheet.iter_rows(min_row=2):
            if len(row) < fixed:
                continue
            if row[2].value == "YES":
                for cell in row[:fixed]:
                    cell.fill = PatternFill("solid", fgColor=ISSUE_FILL)
            for cell in row[fixed:]:
                value = str(cell.value or "")
                fill = ISSUE_FILL if value == "OVERLAP" else (CHARGING_FILL if value else IDLE_FILL)
                Report._paint_timeline_cell(cell, fill)
        Report._size_timeline(worksheet, fixed, fixed_width=14, slot_width=13, row_height=28)

    @staticmethod
    def _bus_cell_fill(value):
        """Pick the fill colour for a bus timeline cell from its text.

        Args:
            value (str): Cell text.

        Returns:
            str: Hex colour.
        """
        if value.startswith("T:"):
            return TRAVEL_FILL
        if value.startswith("W:"):
            return WAIT_FILL
        if value.startswith("C:"):
            return CHARGING_FILL
        if value.startswith("ARR"):
            return ARRIVED_FILL
        if value:
            return ISSUE_FILL
        return IDLE_FILL

    @staticmethod
    def _paint_timeline_cell(cell, fill):
        """Apply fill, centre alignment and a thin border to a cell.

        Args:
            cell (openpyxl.cell.cell.Cell): The cell to style.
            fill (str): Hex colour.
        """
        cell.fill = PatternFill("solid", fgColor=fill)
        cell.alignment = CENTER
        cell.border = THIN_BORDER

    @staticmethod
    def _style_timeline_header(worksheet):
        """Dark, wrapped header row for a timeline sheet.

        Args:
            worksheet (openpyxl.worksheet.worksheet.Worksheet): The sheet.
        """
        worksheet.freeze_panes = "A2"
        for cell in worksheet[1]:
            cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
            cell.font = Font(color=HEADER_FONT, bold=True)
            cell.alignment = CENTER
            cell.border = THIN_BORDER

    @staticmethod
    def _size_timeline(worksheet, fixed, fixed_width, slot_width, row_height):
        """Set row heights and column widths for a timeline sheet.

        Args:
            worksheet (openpyxl.worksheet.worksheet.Worksheet): The sheet.
            fixed (int): Number of leading metadata columns.
            fixed_width (int): Width for the metadata columns.
            slot_width (int): Width for the per-slot columns.
            row_height (int): Height for the data rows.
        """
        for row_number in range(2, worksheet.max_row + 1):
            worksheet.row_dimensions[row_number].height = row_height
        for column_number in range(1, worksheet.max_column + 1):
            width = fixed_width if column_number <= fixed else slot_width
            worksheet.column_dimensions[get_column_letter(column_number)].width = width
