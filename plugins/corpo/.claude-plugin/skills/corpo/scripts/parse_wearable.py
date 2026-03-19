#!/usr/bin/env python3
"""
Wearable Data Parser — WHOOP & CGM (FreeStyle Libre)
Parses exported CSV data from WHOOP and FreeStyle Libre CGM into structured JSON
for integration with the health assistant memory system.

Usage:
  # WHOOP cycles/recovery
  python3 parse_wearable.py whoop --cycles <cycles.csv> --output <output.json>

  # WHOOP with all exports
  python3 parse_wearable.py whoop --cycles <cycles.csv> --sleeps <sleeps.csv> --workouts <workouts.csv> --output <output.json>

  # CGM data (FreeStyle Libre)
  python3 parse_wearable.py cgm --input <glucose_data.csv> --output <output.json>

  # Summary only (no full data dump)
  python3 parse_wearable.py whoop --cycles <cycles.csv> --summary

  # Merge into existing memory
  python3 parse_wearable.py whoop --cycles <cycles.csv> --merge-memory <nutrizionista_memory.json>
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict
from statistics import mean, median, stdev

# ── WHOOP Parser ─────────────────────────────────────────────────────────────


def parse_whoop_cycles(filepath):
    """Parse WHOOP physiological cycles CSV."""
    cycles = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cycle = {}
            for key, val in row.items():
                key_clean = (
                    key.strip()
                    .lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("%", "pct")
                )
                if val and val.strip():
                    try:
                        cycle[key_clean] = float(val) if "." in val else int(val)
                    except (ValueError, TypeError):
                        cycle[key_clean] = val.strip()
                else:
                    cycle[key_clean] = None
            cycles.append(cycle)
    return cycles


def parse_whoop_sleeps(filepath):
    """Parse WHOOP sleep CSV."""
    sleeps = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sleep = {}
            for key, val in row.items():
                key_clean = (
                    key.strip()
                    .lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("%", "pct")
                )
                if val and val.strip():
                    try:
                        sleep[key_clean] = float(val) if "." in val else int(val)
                    except (ValueError, TypeError):
                        sleep[key_clean] = val.strip()
                else:
                    sleep[key_clean] = None
            sleeps.append(sleep)
    return sleeps


def parse_whoop_workouts(filepath):
    """Parse WHOOP workouts CSV."""
    workouts = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            workout = {}
            for key, val in row.items():
                key_clean = (
                    key.strip()
                    .lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace("%", "pct")
                )
                if val and val.strip():
                    try:
                        workout[key_clean] = float(val) if "." in val else int(val)
                    except (ValueError, TypeError):
                        workout[key_clean] = val.strip()
                else:
                    workout[key_clean] = None
            workouts.append(workout)
    return workouts


def extract_date(record):
    """Try to extract a date from a WHOOP record."""
    for key in ["cycle_start_time", "sleep_onset", "start_time", "date"]:
        val = record.get(key)
        if val and isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
            except (ValueError, TypeError):
                # Try simpler formats
                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                    try:
                        return datetime.strptime(val[:10], fmt).date()
                    except (ValueError, TypeError):
                        continue
    return None


def summarize_whoop(cycles, sleeps=None, workouts=None):
    """Generate summary statistics from WHOOP data."""
    summary = {
        "total_cycles": len(cycles),
        "date_range": {},
        "recovery": {},
        "hrv": {},
        "rhr": {},
        "sleep": {},
        "strain": {},
        "workouts": {},
        "trends": {},
        "alerts": [],
    }

    # Extract numeric values
    recovery_vals = []
    hrv_vals = []
    rhr_vals = []
    strain_vals = []

    dated_recovery = []
    dated_hrv = []
    dated_rhr = []

    for c in cycles:
        date = extract_date(c)

        for key in ["recovery_score", "recovery", "recovery_pct"]:
            v = c.get(key)
            if v is not None and isinstance(v, (int, float)):
                recovery_vals.append(v)
                if date:
                    dated_recovery.append((date, v))
                break

        for key in ["hrv_rmssd_ms", "hrv", "hrv_ms", "heart_rate_variability_rmssd"]:
            v = c.get(key)
            if v is not None and isinstance(v, (int, float)):
                hrv_vals.append(v)
                if date:
                    dated_hrv.append((date, v))
                break

        for key in ["resting_heart_rate_bpm", "rhr", "resting_heart_rate"]:
            v = c.get(key)
            if v is not None and isinstance(v, (int, float)):
                rhr_vals.append(v)
                if date:
                    dated_rhr.append((date, v))
                break

        for key in ["day_strain", "strain", "strain_score"]:
            v = c.get(key)
            if v is not None and isinstance(v, (int, float)):
                strain_vals.append(v)
                break

    # Date range
    dates = [extract_date(c) for c in cycles]
    dates = [d for d in dates if d]
    if dates:
        summary["date_range"] = {
            "start": str(min(dates)),
            "end": str(max(dates)),
            "days": (max(dates) - min(dates)).days,
        }

    # Stats helper
    def stats(vals, name):
        if not vals:
            return {}
        result = {
            "count": len(vals),
            "mean": round(mean(vals), 1),
            "median": round(median(vals), 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
        }
        if len(vals) > 1:
            result["stdev"] = round(stdev(vals), 1)
        return result

    summary["recovery"] = stats(recovery_vals, "recovery")
    summary["hrv"] = stats(hrv_vals, "hrv")
    summary["rhr"] = stats(rhr_vals, "rhr")
    summary["strain"] = stats(strain_vals, "strain")

    # Trends — last 7 days vs previous 7 days
    if dated_hrv and len(dated_hrv) >= 14:
        sorted_hrv = sorted(dated_hrv, key=lambda x: x[0])
        last7 = [v for d, v in sorted_hrv[-7:]]
        prev7 = [v for d, v in sorted_hrv[-14:-7]]
        if last7 and prev7:
            summary["trends"]["hrv_7d_change"] = round(mean(last7) - mean(prev7), 1)
            summary["trends"]["hrv_7d_direction"] = (
                "improving" if mean(last7) > mean(prev7) else "declining"
            )

    if dated_rhr and len(dated_rhr) >= 14:
        sorted_rhr = sorted(dated_rhr, key=lambda x: x[0])
        last7 = [v for d, v in sorted_rhr[-7:]]
        prev7 = [v for d, v in sorted_rhr[-14:-7]]
        if last7 and prev7:
            summary["trends"]["rhr_7d_change"] = round(mean(last7) - mean(prev7), 1)
            summary["trends"]["rhr_7d_direction"] = (
                "improving" if mean(last7) < mean(prev7) else "worsening"
            )

    if dated_recovery and len(dated_recovery) >= 14:
        sorted_rec = sorted(dated_recovery, key=lambda x: x[0])
        last7 = [v for d, v in sorted_rec[-7:]]
        prev7 = [v for d, v in sorted_rec[-14:-7]]
        if last7 and prev7:
            summary["trends"]["recovery_7d_change"] = round(
                mean(last7) - mean(prev7), 1
            )

    # Alerts
    if recovery_vals:
        low_recovery = [v for v in recovery_vals if v < 33]
        if len(low_recovery) > len(recovery_vals) * 0.3:
            summary["alerts"].append(
                f"WARNING: {len(low_recovery)}/{len(recovery_vals)} days ({round(len(low_recovery)/len(recovery_vals)*100)}%) with recovery < 33%"
            )

    if hrv_vals and min(hrv_vals) < 30:
        summary["alerts"].append(
            f"CRITICAL: HRV dropped to {min(hrv_vals)}ms — indicates severe physiological stress"
        )

    if rhr_vals:
        rhr_max = max(rhr_vals)
        rhr_min = min(rhr_vals)
        if rhr_max - rhr_min > 15:
            summary["alerts"].append(
                f"WARNING: RHR range {rhr_min}-{rhr_max} bpm ({rhr_max - rhr_min} bpm spread) — high variability suggests unstable recovery"
            )

    # Sleep summary
    if sleeps:
        summary["sleep"]["total_nights"] = len(sleeps)
        sleep_durations = []
        sleep_performances = []
        sleep_consistencies = []
        for s in sleeps:
            for key in [
                "total_sleep_duration_min",
                "total_in_bed_duration_min",
                "sleep_duration",
            ]:
                v = s.get(key)
                if v is not None and isinstance(v, (int, float)):
                    sleep_durations.append(v)
                    break
            for key in [
                "sleep_performance_pct",
                "sleep_performance",
                "sleep_efficiency",
            ]:
                v = s.get(key)
                if v is not None and isinstance(v, (int, float)):
                    sleep_performances.append(v)
                    break
            for key in ["sleep_consistency_pct", "sleep_consistency", "consistency"]:
                v = s.get(key)
                if v is not None and isinstance(v, (int, float)):
                    sleep_consistencies.append(v)
                    break

        if sleep_durations:
            summary["sleep"]["avg_duration_min"] = round(mean(sleep_durations), 0)
            summary["sleep"]["avg_duration_hours"] = round(
                mean(sleep_durations) / 60, 1
            )
        if sleep_performances:
            summary["sleep"]["avg_performance_pct"] = round(mean(sleep_performances), 1)
        if sleep_consistencies:
            summary["sleep"]["avg_consistency_pct"] = round(
                mean(sleep_consistencies), 1
            )

    # Workout summary
    if workouts:
        summary["workouts"]["total"] = len(workouts)
        activity_counts = defaultdict(int)
        for w in workouts:
            for key in ["sport", "activity", "activity_name", "workout_type"]:
                v = w.get(key)
                if v and isinstance(v, str):
                    activity_counts[v] += 1
                    break
        summary["workouts"]["by_activity"] = dict(
            sorted(activity_counts.items(), key=lambda x: -x[1])[:10]
        )

    return summary


# ── CGM Parser (FreeStyle Libre) ─────────────────────────────────────────────


def parse_cgm_csv(filepath):
    """Parse FreeStyle Libre or generic CGM CSV export."""
    readings = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        # Skip header rows (FreeStyle Libre has metadata rows before actual data)
        lines = f.readlines()

    # Find the actual data header
    header_idx = None
    for i, line in enumerate(lines):
        if (
            "glucose" in line.lower()
            or "mg/dl" in line.lower()
            or "timestamp" in line.lower()
        ):
            header_idx = i
            break
    if header_idx is None:
        # Try first row
        header_idx = 0

    reader = csv.DictReader(lines[header_idx:])
    for row in reader:
        reading = {}
        for key, val in row.items():
            if not key:
                continue
            key_clean = key.strip().lower().replace(" ", "_")
            if val and val.strip():
                try:
                    reading[key_clean] = float(val) if "." in val else int(val)
                except (ValueError, TypeError):
                    reading[key_clean] = val.strip()
        if reading:
            readings.append(reading)

    return readings


def extract_glucose_value(reading):
    """Extract glucose value from a CGM reading."""
    for key in [
        "historic_glucose_mg/dl",
        "glucose_mg/dl",
        "glucose",
        "scan_glucose_mg/dl",
        "glucose_value",
        "value",
        "bg",
        "sgv",
    ]:
        v = reading.get(key)
        if v is not None and isinstance(v, (int, float)) and 20 < v < 500:
            return v
    return None


def extract_cgm_timestamp(reading):
    """Extract timestamp from a CGM reading."""
    for key in ["device_timestamp", "timestamp", "date", "time", "datetime"]:
        v = reading.get(key)
        if v and isinstance(v, str):
            for fmt in [
                "%d-%m-%Y %H:%M",
                "%m-%d-%Y %H:%M",
                "%Y-%m-%d %H:%M",
                "%d/%m/%Y %H:%M",
                "%m/%d/%Y %H:%M",
                "%Y/%m/%d %H:%M",
                "%d-%m-%Y %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
            ]:
                try:
                    return datetime.strptime(v.strip(), fmt)
                except (ValueError, TypeError):
                    continue
    return None


def summarize_cgm(readings):
    """Generate summary statistics from CGM data."""
    glucose_values = []
    hourly_readings = defaultdict(list)
    daily_readings = defaultdict(list)

    for r in readings:
        gv = extract_glucose_value(r)
        ts = extract_cgm_timestamp(r)
        if gv is not None:
            glucose_values.append(gv)
            if ts:
                hourly_readings[ts.hour].append(gv)
                daily_readings[ts.date()].append(gv)

    if not glucose_values:
        return {"error": "No valid glucose readings found"}

    # Standard ranges
    hypo_threshold = 70
    hyper_threshold = 180
    target_low = 70
    target_high = 140

    hypo_count = sum(1 for v in glucose_values if v < hypo_threshold)
    hyper_count = sum(1 for v in glucose_values if v > hyper_threshold)
    in_range = sum(1 for v in glucose_values if target_low <= v <= target_high)

    summary = {
        "total_readings": len(glucose_values),
        "date_range": {},
        "overall": {
            "mean_mg_dl": round(mean(glucose_values), 1),
            "median_mg_dl": round(median(glucose_values), 1),
            "min_mg_dl": round(min(glucose_values), 1),
            "max_mg_dl": round(max(glucose_values), 1),
            "stdev_mg_dl": (
                round(stdev(glucose_values), 1) if len(glucose_values) > 1 else 0
            ),
        },
        "time_in_range": {
            "target_range": f"{target_low}-{target_high} mg/dL",
            "tir_pct": round(in_range / len(glucose_values) * 100, 1),
            "hypo_pct": round(hypo_count / len(glucose_values) * 100, 1),
            "hyper_pct": round(hyper_count / len(glucose_values) * 100, 1),
            "hypo_count": hypo_count,
            "hyper_count": hyper_count,
        },
        "hourly_pattern": {},
        "alerts": [],
    }

    # Date range
    dates = list(daily_readings.keys())
    if dates:
        summary["date_range"] = {
            "start": str(min(dates)),
            "end": str(max(dates)),
            "days": len(dates),
        }

    # Hourly pattern
    for hour in sorted(hourly_readings.keys()):
        vals = hourly_readings[hour]
        summary["hourly_pattern"][f"{hour:02d}:00"] = {
            "mean": round(mean(vals), 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1),
            "readings": len(vals),
        }

    # Alerts
    if summary["time_in_range"]["hypo_pct"] > 10:
        summary["alerts"].append(
            f"CRITICAL: {summary['time_in_range']['hypo_pct']}% readings below {hypo_threshold} mg/dL — significant hypoglycemia"
        )

    # Morning hypoglycemia detection (06-11)
    morning_vals = []
    for h in range(6, 12):
        morning_vals.extend(hourly_readings.get(h, []))
    if morning_vals:
        morning_hypo = sum(1 for v in morning_vals if v < hypo_threshold)
        morning_hypo_pct = round(morning_hypo / len(morning_vals) * 100, 1)
        summary["morning_06_11"] = {
            "mean": round(mean(morning_vals), 1),
            "min": round(min(morning_vals), 1),
            "hypo_pct": morning_hypo_pct,
            "readings": len(morning_vals),
        }
        if morning_hypo_pct > 20:
            summary["alerts"].append(
                f"WARNING: Morning (06-11) hypoglycemia at {morning_hypo_pct}% — mean {round(mean(morning_vals), 1)} mg/dL, min {round(min(morning_vals), 1)}"
            )

    # Estimated HbA1c (eAG formula)
    eag = summary["overall"]["mean_mg_dl"]
    estimated_hba1c = round((eag + 46.7) / 28.7, 1)
    summary["estimated_hba1c"] = estimated_hba1c

    return summary


# ── Directory auto-discovery ─────────────────────────────────────────────────


def discover_csvs(directory, patterns=None):
    """Recursively find CSV files in a directory, optionally matching filename patterns."""
    csvs = []
    for root, dirs, files in os.walk(directory):
        for f in sorted(files):
            if f.lower().endswith(".csv"):
                if patterns:
                    if any(p in f.lower() for p in patterns):
                        csvs.append(os.path.join(root, f))
                else:
                    csvs.append(os.path.join(root, f))
    return csvs


def auto_discover_whoop(directory):
    """Auto-discover WHOOP CSV files in a directory by filename patterns."""
    all_csvs = discover_csvs(directory)
    cycles_file = None
    sleeps_file = None
    workouts_file = None

    for f in all_csvs:
        fname = os.path.basename(f).lower()
        if "cycle" in fname or "physiological" in fname:
            cycles_file = f
        elif "sleep" in fname:
            sleeps_file = f
        elif "workout" in fname:
            workouts_file = f

    return cycles_file, sleeps_file, workouts_file


def auto_discover_cgm(directory):
    """Auto-discover CGM CSV files in a directory. Returns most recent file."""
    all_csvs = discover_csvs(directory)
    if not all_csvs:
        return None
    # Return the most recently modified CSV
    return max(all_csvs, key=os.path.getmtime)


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Parse WHOOP or CGM wearable data")
    subparsers = parser.add_subparsers(dest="source", help="Data source")

    # WHOOP subcommand
    whoop_parser = subparsers.add_parser("whoop", help="Parse WHOOP export CSVs")
    whoop_parser.add_argument(
        "--dir", help="Directory to auto-discover WHOOP CSVs (e.g., garmin-data/)"
    )
    whoop_parser.add_argument(
        "--cycles", help="Path to physiological cycles CSV (overrides --dir)"
    )
    whoop_parser.add_argument("--sleeps", help="Path to sleep CSV (overrides --dir)")
    whoop_parser.add_argument(
        "--workouts", help="Path to workouts CSV (overrides --dir)"
    )
    whoop_parser.add_argument("--output", help="Output JSON path")
    whoop_parser.add_argument(
        "--summary", action="store_true", help="Print summary only"
    )
    whoop_parser.add_argument(
        "--merge-memory", help="Path to nutrizionista_memory.json to merge into"
    )

    # CGM subcommand
    cgm_parser = subparsers.add_parser(
        "cgm", help="Parse CGM (FreeStyle Libre) export CSV"
    )
    cgm_parser.add_argument(
        "--dir", help="Directory to auto-discover CGM CSVs (e.g., glicemia-monitor/)"
    )
    cgm_parser.add_argument(
        "--input", help="Path to glucose data CSV (overrides --dir)"
    )
    cgm_parser.add_argument("--output", help="Output JSON path")
    cgm_parser.add_argument("--summary", action="store_true", help="Print summary only")
    cgm_parser.add_argument(
        "--merge-memory", help="Path to nutrizionista_memory.json to merge into"
    )

    args = parser.parse_args()

    if not args.source:
        parser.print_help()
        sys.exit(1)

    if args.source == "whoop":
        # Auto-discover from --dir if individual files not specified
        if args.dir and not (args.cycles or args.sleeps or args.workouts):
            discovered_cycles, discovered_sleeps, discovered_workouts = (
                auto_discover_whoop(args.dir)
            )
            if not args.cycles:
                args.cycles = discovered_cycles
            if not args.sleeps:
                args.sleeps = discovered_sleeps
            if not args.workouts:
                args.workouts = discovered_workouts
            if discovered_cycles or discovered_sleeps or discovered_workouts:
                found = [
                    f
                    for f in [discovered_cycles, discovered_sleeps, discovered_workouts]
                    if f
                ]
                print(
                    f"Auto-discovered {len(found)} WHOOP CSV(s) in {args.dir}:",
                    file=sys.stderr,
                )
                for f in found:
                    print(f"  → {os.path.basename(f)}", file=sys.stderr)
            else:
                print(f"No WHOOP CSVs found in {args.dir}", file=sys.stderr)
                sys.exit(1)

        result = {"source": "whoop", "parsed_at": datetime.now().isoformat()}

        if args.cycles:
            cycles = parse_whoop_cycles(args.cycles)
            result["cycles"] = cycles if not args.summary else []
            result["cycles_count"] = len(cycles)
        else:
            cycles = []

        sleeps = parse_whoop_sleeps(args.sleeps) if args.sleeps else None
        workouts = parse_whoop_workouts(args.workouts) if args.workouts else None

        if sleeps:
            result["sleeps_count"] = len(sleeps)
            if not args.summary:
                result["sleeps"] = sleeps
        if workouts:
            result["workouts_count"] = len(workouts)
            if not args.summary:
                result["workouts"] = workouts

        result["summary"] = summarize_whoop(cycles, sleeps, workouts)

        if args.summary:
            print(
                json.dumps(result["summary"], indent=2, ensure_ascii=False, default=str)
            )
        elif args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"WHOOP data saved to {args.output}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        if args.merge_memory:
            _merge_wearable_to_memory(args.merge_memory, "whoop", result["summary"])

    elif args.source == "cgm":
        # Auto-discover from --dir if --input not specified
        input_file = args.input
        if not input_file and args.dir:
            input_file = auto_discover_cgm(args.dir)
            if input_file:
                print(
                    f"Auto-discovered CGM file: {os.path.basename(input_file)}",
                    file=sys.stderr,
                )
            else:
                print(f"No CGM CSVs found in {args.dir}", file=sys.stderr)
                sys.exit(1)

        if not input_file:
            print("Error: provide --input or --dir", file=sys.stderr)
            sys.exit(1)

        readings = parse_cgm_csv(input_file)
        result = {
            "source": "cgm_freestyle_libre",
            "parsed_at": datetime.now().isoformat(),
            "total_readings": len(readings),
            "summary": summarize_cgm(readings),
        }
        if not args.summary:
            result["readings"] = readings

        if args.summary:
            print(
                json.dumps(result["summary"], indent=2, ensure_ascii=False, default=str)
            )
        elif args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            print(f"CGM data saved to {args.output}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

        if args.merge_memory:
            _merge_wearable_to_memory(args.merge_memory, "cgm", result["summary"])


def _merge_wearable_to_memory(memory_path, source, summary):
    """Merge wearable summary into nutrizionista_memory.json."""
    if not os.path.exists(memory_path):
        print(f"Memory file not found: {memory_path}", file=sys.stderr)
        return

    with open(memory_path, "r") as f:
        memory = json.load(f)

    # Add or update wearable_data section
    if "wearable_data" not in memory:
        memory["wearable_data"] = {}

    memory["wearable_data"][source] = {
        "last_updated": datetime.now().isoformat(),
        "summary": summary,
    }

    with open(memory_path, "w") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False, default=str)

    print(f"Merged {source} summary into {memory_path}")


if __name__ == "__main__":
    main()
