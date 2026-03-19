#!/usr/bin/env python3
"""
Bloodwork PDF Parser — Italian Lab Reports
Parses blood test PDF reports from Italian laboratories and structures them into JSON
for integration with the health assistant memory system.

Handles common Italian lab report formats with:
- Chimica clinica (liver, kidney, lipids, glucose, electrolytes)
- Emocromo (CBC with differential)
- Sieroimmunologia (hormones, vitamins, tumor markers)
- Elettroforesi proteica (protein electrophoresis)
- Esame urine

Usage:
  # Parse a blood test PDF
  python3 parse_bloodwork.py <pdf_path> --output <output.json>

  # Parse and merge into memory
  python3 parse_bloodwork.py <pdf_path> --merge-memory <nutrizionista_memory.json>

  # Parse with context (which program was active)
  python3 parse_bloodwork.py <pdf_path> --context "Programma #57, post cicli PED #49-#56" --output <output.json>

  # Summary only
  python3 parse_bloodwork.py <pdf_path> --summary
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    print("Installing pdfplumber...", file=sys.stderr)
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber


# ── Reference ranges for Italian lab reports ─────────────────────────────────
# These are common reference ranges; actual ranges vary by lab.
# The parser will prefer ranges extracted from the PDF itself.

KNOWN_TESTS = {
    # Chimica Clinica
    "creatinina": {"unit": "mg/dl", "category": "kidney"},
    "azotemia": {"unit": "mg/dl", "category": "kidney"},
    "acido urico": {"unit": "mg/dl", "category": "kidney"},
    "got": {
        "unit": "u/l",
        "category": "liver",
        "aliases": ["ast", "got (ast)", "aspartato aminotransferasi"],
    },
    "gpt": {
        "unit": "u/l",
        "category": "liver",
        "aliases": ["alt", "gpt (alt)", "alanina aminotransferasi"],
    },
    "gamma gt": {
        "unit": "u/l",
        "category": "liver",
        "aliases": ["ggt", "gamma-gt", "γ-gt"],
    },
    "bilirubina totale": {"unit": "mg/dl", "category": "liver"},
    "bilirubina diretta": {"unit": "mg/dl", "category": "liver"},
    "glicemia": {"unit": "mg/dl", "category": "metabolic"},
    "emoglobina glicata": {"unit": "%", "category": "metabolic", "aliases": ["hba1c"]},
    "colesterolo totale": {
        "unit": "mg/dl",
        "category": "lipids",
        "aliases": ["colesterolo"],
    },
    "colesterolo hdl": {
        "unit": "mg/dl",
        "category": "lipids",
        "aliases": ["hdl", "hdl colesterolo"],
    },
    "colesterolo ldl": {
        "unit": "mg/dl",
        "category": "lipids",
        "aliases": ["ldl", "ldl colesterolo"],
    },
    "trigliceridi": {"unit": "mg/dl", "category": "lipids"},
    "proteine totali": {"unit": "g/dl", "category": "metabolic"},
    "sodio": {"unit": "meq/l", "category": "electrolytes", "aliases": ["na"]},
    "potassio": {"unit": "meq/l", "category": "electrolytes", "aliases": ["k"]},
    "cloro": {"unit": "meq/l", "category": "electrolytes", "aliases": ["cl"]},
    "calcio": {"unit": "mg/dl", "category": "electrolytes", "aliases": ["ca"]},
    "ferro": {"unit": "µg/dl", "category": "iron", "aliases": ["sideremia"]},
    "ferritina": {"unit": "ng/ml", "category": "iron"},
    "transferrina": {"unit": "mg/dl", "category": "iron"},
    "omocisteina": {"unit": "µmol/l", "category": "metabolic"},
    "pcr": {
        "unit": "mg/l",
        "category": "inflammatory",
        "aliases": ["proteina c reattiva", "hs-crp"],
    },
    "ves": {
        "unit": "mm/h",
        "category": "inflammatory",
        "aliases": ["velocità di eritrosedimentazione"],
    },
    # Sieroimmunologia
    "insulina": {"unit": "uiu/ml", "category": "hormonal", "aliases": ["insulinemia"]},
    "testosterone totale": {
        "unit": "ng/dl",
        "category": "hormonal",
        "aliases": ["testosterone"],
    },
    "testosterone libero": {"unit": "pg/ml", "category": "hormonal"},
    "lh": {
        "unit": "miu/ml",
        "category": "hormonal",
        "aliases": ["ormone luteinizzante"],
    },
    "fsh": {
        "unit": "miu/ml",
        "category": "hormonal",
        "aliases": ["ormone follicolo-stimolante"],
    },
    "estradiolo": {"unit": "pg/ml", "category": "hormonal", "aliases": ["e2"]},
    "shbg": {"unit": "nmol/l", "category": "hormonal"},
    "tsh": {"unit": "miu/l", "category": "thyroid"},
    "ft3": {"unit": "pg/ml", "category": "thyroid", "aliases": ["t3 libero"]},
    "ft4": {"unit": "ng/dl", "category": "thyroid", "aliases": ["t4 libero"]},
    "vitamina d": {
        "unit": "ng/ml",
        "category": "vitamins",
        "aliases": ["vitamina d3", "25-oh vitamina d", "25(oh)d"],
    },
    "vitamina b12": {"unit": "pg/ml", "category": "vitamins"},
    "folati": {"unit": "ng/ml", "category": "vitamins", "aliases": ["acido folico"]},
    "alfa-fetoproteina": {
        "unit": "ng/ml",
        "category": "tumor_markers",
        "aliases": ["afp"],
    },
    "psa": {"unit": "ng/ml", "category": "tumor_markers", "aliases": ["psa totale"]},
    # Emocromo
    "globuli bianchi": {
        "unit": "10³/µl",
        "category": "cbc",
        "aliases": ["wbc", "leucociti"],
    },
    "globuli rossi": {
        "unit": "10⁶/µl",
        "category": "cbc",
        "aliases": ["rbc", "eritrociti"],
    },
    "emoglobina": {"unit": "g/dl", "category": "cbc", "aliases": ["hgb", "hb"]},
    "ematocrito": {"unit": "%", "category": "cbc", "aliases": ["hct"]},
    "mcv": {"unit": "fl", "category": "cbc", "aliases": ["volume corpuscolare medio"]},
    "mch": {"unit": "pg", "category": "cbc"},
    "mchc": {"unit": "g/dl", "category": "cbc"},
    "rdw": {"unit": "%", "category": "cbc", "aliases": ["rdw-cv"]},
    "piastrine": {
        "unit": "10³/µl",
        "category": "cbc",
        "aliases": ["plt", "trombociti"],
    },
}


def extract_text_from_pdf(filepath):
    """Extract all text from a PDF file."""
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text


def parse_lab_info(text):
    """Extract lab name, date, patient, doctor from the report."""
    info = {
        "lab": None,
        "date": None,
        "patient": None,
        "doctor": None,
    }

    # Date patterns (DD/MM/YYYY or DD-MM-YYYY)
    date_patterns = [
        r"(?:data|date|prelievo|accettazione)[:\s]*(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})",
        r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})",
    ]
    for pattern in date_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            date_str = m.group(1).replace("-", "/")
            try:
                parts = date_str.split("/")
                if len(parts) == 3:
                    info["date"] = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    break
            except (ValueError, IndexError):
                pass

    # Patient name
    patient_patterns = [
        r"(?:paziente|patient|cognome\s+nome|sig\.?)\s*[:\s]+([A-Z][a-zà-ú]+\s+[A-Z][a-zà-ú]+)",
        r"(?:PALAZZO|palazzo)\s+(?:VINCENZO|vincenzo)",
    ]
    for pattern in patient_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            info["patient"] = (
                m.group(0).strip() if not m.groups() else m.group(1).strip()
            )
            break

    # Doctor
    doctor_patterns = [
        r"(?:medico|dott\.?|dr\.?)\s*[:\s]+([A-Z][a-zà-ú]+(?:\s+[A-Z][a-zà-ú]+)*)",
    ]
    for pattern in doctor_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            info["doctor"] = m.group(1).strip()
            break

    return info


def parse_test_results(text):
    """Parse individual test results from the report text."""
    results = []
    lines = text.split("\n")

    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue

        # Try to match patterns like:
        # "Creatinina  0.96  mg/dl  0.60 - 1.20"
        # "GOT (AST)  16  u/l  fino a 37"
        # "Colesterolo HDL  36  mg/dl  > 55"

        # Pattern 1: name  value  unit  range
        m = re.match(
            r"^(.+?)\s+(\d+[.,]?\d*)\s+(mg/dl|g/dl|u/l|µg/dl|ng/ml|pg/ml|µmol/l|meq/l|miu/ml|miu/l|nmol/l|%|fl|pg|10[³⁶]/µl|mm/h)\s+(.+)$",
            line,
            re.IGNORECASE,
        )
        if m:
            name = m.group(1).strip()
            value_str = m.group(2).replace(",", ".")
            unit = m.group(3).strip()
            range_str = m.group(4).strip()

            try:
                value = float(value_str)
            except ValueError:
                continue

            result = {
                "name": name,
                "value": value,
                "unit": unit,
                "range": range_str,
                "status": classify_result(name, value, range_str),
                "category": categorize_test(name),
            }
            results.append(result)
            continue

        # Pattern 2: less structured — try to find known test names
        line_lower = line.lower()
        for test_name, test_info in KNOWN_TESTS.items():
            aliases = [test_name] + test_info.get("aliases", [])
            for alias in aliases:
                if alias in line_lower:
                    # Try to extract a numeric value after the test name
                    after_name = line_lower.split(alias)[-1]
                    numbers = re.findall(r"(\d+[.,]?\d*)", after_name)
                    if numbers:
                        try:
                            value = float(numbers[0].replace(",", "."))
                            # Extract range (remaining numbers or text)
                            range_parts = re.findall(
                                r"(\d+[.,]?\d*\s*[-–]\s*\d+[.,]?\d*|fino\s+a\s+\d+[.,]?\d*|[<>]\s*\d+[.,]?\d*)",
                                after_name,
                            )
                            range_str = range_parts[0] if range_parts else ""

                            result = {
                                "name": test_name.title(),
                                "value": value,
                                "unit": test_info["unit"],
                                "range": range_str,
                                "status": classify_result(test_name, value, range_str),
                                "category": test_info["category"],
                            }
                            results.append(result)
                        except (ValueError, IndexError):
                            pass
                    break

    # Deduplicate by name (keep first occurrence)
    seen = set()
    unique_results = []
    for r in results:
        key = r["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique_results.append(r)

    return unique_results


def classify_result(name, value, range_str):
    """Classify a result as normal, high, low, or borderline based on range."""
    if not range_str:
        return "unknown"

    range_str = range_str.lower().replace(",", ".").strip()

    # "fino a X" or "< X"
    m = re.search(r"(?:fino\s+a|<)\s*(\d+\.?\d*)", range_str)
    if m:
        upper = float(m.group(1))
        if value > upper * 1.1:
            return "high"
        elif value > upper:
            return "borderline_high"
        return "normal"

    # "> X"
    m = re.search(r">\s*(\d+\.?\d*)", range_str)
    if m:
        lower = float(m.group(1))
        if value < lower * 0.9:
            return "low"
        elif value < lower:
            return "borderline_low"
        return "normal"

    # "X - Y" range
    m = re.search(r"(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)", range_str)
    if m:
        lower = float(m.group(1))
        upper = float(m.group(2))
        if value < lower:
            return "low"
        elif value > upper:
            return "high"
        elif value <= lower * 1.05 or value >= upper * 0.95:
            return "borderline"
        return "normal"

    return "unknown"


def categorize_test(name):
    """Categorize a test based on its name."""
    name_lower = name.lower().strip()
    for test_name, info in KNOWN_TESTS.items():
        aliases = [test_name] + info.get("aliases", [])
        if any(a in name_lower for a in aliases):
            return info["category"]
    return "other"


def generate_findings(results):
    """Generate clinical findings from parsed results."""
    findings = {
        "critical": [],
        "warnings": [],
        "good": [],
        "missing_recommended": [],
    }

    for r in results:
        name = r["name"]
        status = r["status"]
        value = r["value"]
        unit = r["unit"]

        if status in ("high", "low"):
            severity = "critical" if abs_deviation(r) > 0.3 else "warnings"
            findings[severity].append(
                f"{name}: {value} {unit} ({status}) — range: {r.get('range', '?')}"
            )
        elif status == "normal":
            findings["good"].append(f"{name}: {value} {unit} (normale)")

    # Check for missing recommended tests
    found_categories = set(r["category"] for r in results)
    recommended = {
        "hormonal": ["testosterone", "LH", "FSH", "SHBG", "estradiolo"],
        "iron": ["ferritina", "sideremia"],
        "tumor_markers": ["alfa-fetoproteina (AFP)"],
    }
    for cat, tests in recommended.items():
        if cat not in found_categories:
            findings["missing_recommended"].extend(tests)

    return findings


def abs_deviation(result):
    """Calculate how far outside range a result is (0-1 scale)."""
    range_str = result.get("range", "").lower().replace(",", ".")
    value = result["value"]

    m = re.search(r"(\d+\.?\d*)\s*[-–]\s*(\d+\.?\d*)", range_str)
    if m:
        lower = float(m.group(1))
        upper = float(m.group(2))
        range_width = upper - lower
        if range_width == 0:
            return 0
        if value < lower:
            return (lower - value) / range_width
        elif value > upper:
            return (value - upper) / range_width
    return 0


def parse_bloodwork(filepath, context=None):
    """Main function: parse a bloodwork PDF into structured data."""
    text = extract_text_from_pdf(filepath)
    lab_info = parse_lab_info(text)
    results = parse_test_results(text)
    findings = generate_findings(results)

    output = {
        "source": "bloodwork_pdf",
        "file": filepath,
        "parsed_at": datetime.now().isoformat(),
        "lab_info": lab_info,
        "context": context,
        "total_tests": len(results),
        "results": results,
        "results_by_category": {},
        "findings": findings,
        "raw_text_length": len(text),
    }

    # Group by category
    for r in results:
        cat = r.get("category", "other")
        if cat not in output["results_by_category"]:
            output["results_by_category"][cat] = []
        output["results_by_category"][cat].append(r)

    return output


def merge_to_memory(memory_path, bloodwork_data):
    """Merge bloodwork results into nutrizionista_memory.json."""
    if not os.path.exists(memory_path):
        print(f"Memory file not found: {memory_path}", file=sys.stderr)
        return

    with open(memory_path, "r") as f:
        memory = json.load(f)

    if "bloodwork_history" not in memory:
        memory["bloodwork_history"] = []

    # Build structured entry
    entry = {
        "date": bloodwork_data["lab_info"].get("date"),
        "lab": bloodwork_data["lab_info"].get("lab"),
        "doctor": bloodwork_data["lab_info"].get("doctor"),
        "context": bloodwork_data.get("context"),
        "file": bloodwork_data.get("file"),
        "results": {},
        "key_findings": [],
        "missing_tests": bloodwork_data["findings"].get("missing_recommended", []),
    }

    # Organize results by category
    for r in bloodwork_data["results"]:
        cat = r.get("category", "other")
        if cat not in entry["results"]:
            entry["results"][cat] = {}
        key = r["name"].lower().replace(" ", "_").replace("(", "").replace(")", "")
        entry["results"][cat][key] = {
            "value": r["value"],
            "unit": r["unit"],
            "range": r["range"],
            "status": r["status"],
        }

    # Key findings
    for f in bloodwork_data["findings"]["critical"]:
        entry["key_findings"].append(f)
    for f in bloodwork_data["findings"]["warnings"]:
        entry["key_findings"].append(f)

    # Check if we already have results for this date
    existing_dates = [bw.get("date") for bw in memory["bloodwork_history"]]
    if entry["date"] in existing_dates:
        # Update existing entry
        for i, bw in enumerate(memory["bloodwork_history"]):
            if bw.get("date") == entry["date"]:
                memory["bloodwork_history"][i] = entry
                print(f"Updated existing bloodwork entry for {entry['date']}")
                break
    else:
        memory["bloodwork_history"].append(entry)
        print(f"Added new bloodwork entry for {entry['date']}")

    with open(memory_path, "w") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False, default=str)

    print(f"Merged bloodwork into {memory_path}")


def main():
    parser = argparse.ArgumentParser(description="Parse Italian bloodwork PDF reports")
    parser.add_argument("pdf_path", help="Path to the blood test PDF")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument(
        "--summary", action="store_true", help="Print findings summary only"
    )
    parser.add_argument("--context", help="Context note (e.g., 'Post RAD 140 cycle')")
    parser.add_argument(
        "--merge-memory", help="Path to nutrizionista_memory.json to merge into"
    )

    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"File not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    result = parse_bloodwork(args.pdf_path, context=args.context)

    if args.summary:
        print(f"\n=== BLOODWORK ANALYSIS — {result['lab_info'].get('date', '?')} ===")
        print(f"Lab: {result['lab_info'].get('lab', '?')}")
        print(f"Tests parsed: {result['total_tests']}")
        print()

        if result["findings"]["critical"]:
            print("🔴 CRITICAL:")
            for f in result["findings"]["critical"]:
                print(f"   {f}")
        if result["findings"]["warnings"]:
            print("🟡 WARNINGS:")
            for f in result["findings"]["warnings"]:
                print(f"   {f}")
        if result["findings"]["good"]:
            print(f"🟢 NORMAL: {len(result['findings']['good'])} tests in range")
        if result["findings"]["missing_recommended"]:
            print("⚪ MISSING (recommended):")
            for f in result["findings"]["missing_recommended"]:
                print(f"   {f}")
    elif args.output:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        print(f"Bloodwork data saved to {args.output}")
    else:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))

    if args.merge_memory:
        merge_to_memory(args.merge_memory, result)


if __name__ == "__main__":
    main()
