#!/usr/bin/env python3
"""
Weekly Shopping List Generator for Nutritional Programs.

Parses a nutritional program PDF, aggregates weekly quantities, compares prices
across multiple store locations, and generates a shopping list with price
comparison and recommendations.

Usage:
  # Generate markdown shopping list for 2 people
  python3 generate_shopping_list.py --program-pdf "path/to/program.pdf" --people 2 --format markdown

  # Update a price from a receipt
  python3 generate_shopping_list.py --update-price bennet_ponte_tresa "carne bianca magra" 8.50 scontrino

  # Generate price history report
  python3 generate_shopping_list.py --report price_history --price-db scripts/price_db.json
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime

try:
    import pdfplumber
except ImportError:
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber

# Add scripts directory to path so we can import from calc_macros
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from calc_macros import (
    FOOD_DB,
    OIL_PATTERN,
    PORTION_PATTERN,
    match_food,
)

# ── Constants ────────────────────────────────────────────────────────────────

DAYS_OF_WEEK = [
    "lunedi",
    "martedi",
    "mercoledi",
    "giovedi",
    "venerdi",
    "sabato",
    "domenica",
]

# Normalize day names (accented variants)
DAY_NORMALIZE = {
    "lunedì": "lunedi",
    "martedì": "martedi",
    "mercoledì": "mercoledi",
    "giovedì": "giovedi",
    "venerdì": "venerdi",
}

# Food categories for grouping the shopping list
FOOD_CATEGORIES = {
    "carne": [
        "carne rossa magra",
        "carne bianca magra",
        "carne bianca",
        "hamburger",
    ],
    "pesce": [
        "pesce magro",
        "pesce azzurro",
        "gamberetti",
        "gamberi",
        "seppie",
        "calamari",
        "polipo",
        "tonno al naturale",
    ],
    "uova_latticini": [
        "albumi",
        "uova",
        "tuorlo",
        "yogurt senza zuccheri",
        "yogurt",
        "ricotta vaccina",
        "mozzarella light",
    ],
    "affettati": [
        "bresaola",
        "fesa",
        "crudo sgrassato",
        "speck sgrassato",
        "affettato magro",
    ],
    "carboidrati": [
        "pasta",
        "riso",
        "riso basmati",
        "avena",
        "fiocchi avena",
        "fette biscottate",
        "gallette",
        "wasa",
        "legumi",
    ],
    "frutta": [
        "banana",
        "frutta fresca",
        "marmellata senza zuccheri",
        "avocado",
    ],
    "verdure": [],
    "condimenti": [
        "olio evo",
        "frutta secca",
    ],
    "bevande": [
        "latte vegetale",
        "latte scremato",
        "succo pompelmo",
    ],
    "integratori": [
        "whey",
        "creatina",
    ],
}

MAX_HISTORY_ENTRIES = 52  # 1 year of weekly data points

STALE_DAYS = 30  # Flag prices older than this


# ── PDF Parsing ──────────────────────────────────────────────────────────────


def extract_text_from_pdf(pdf_path):
    """Extract all text lines from a PDF using pdfplumber."""
    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split("\n"))
    return lines


def parse_nota_secondi(text_lines):
    """
    Parse the NOTA SECONDI table from the PDF.
    Returns dict of day -> {pranzo: (food_key, grams), cena: (food_key, grams)}
    """
    weekly = {}
    in_nota = False

    for line in text_lines:
        low = line.lower().strip()
        if "nota secondi" in low:
            in_nota = True
            continue

        if not in_nota:
            continue

        # Match day lines
        day_match = re.match(
            r"(luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+(.+)",
            low,
        )
        if day_match:
            day_raw = day_match.group(1)
            day = DAY_NORMALIZE.get(day_raw, day_raw)
            rest = day_match.group(2)

            portions = re.findall(r"(\d+)\s*g\s+([^0-9]+?)(?=\s+\d+\s*g|\s*$)", rest)

            pranzo = None
            cena = None

            if len(portions) >= 2:
                pranzo = (
                    match_food(portions[0][1])[0] or "carne bianca",
                    float(portions[0][0]),
                )
                cena = (
                    match_food(portions[1][1])[0] or "pesce magro",
                    float(portions[1][0]),
                )
            elif len(portions) == 1:
                pranzo = (
                    match_food(portions[0][1])[0] or "carne bianca",
                    float(portions[0][0]),
                )

            # Special cases
            if "uova" in rest or "tuorlo" in rest:
                pranzo = ("albumi", 200)

            if "insalata" in rest and "gamberetti" in rest:
                cena = ("gamberetti", 300)

            if "libera" in rest:
                cena = ("carne bianca", 250)

            weekly[day] = {"pranzo": pranzo, "cena": cena}

    return weekly


def parse_fixed_meals(text_lines):
    """
    Parse fixed meals (same every day) from the PDF text.
    Returns dict of food_key -> daily_grams.
    """
    daily_fixed = defaultdict(float)

    in_meal = None
    for line in text_lines:
        low = line.lower().strip()
        if not low:
            continue

        # Stop before NOTA SECONDI
        if "nota secondi" in low:
            break

        # Detect meal sections
        if any(m in low for m in ["col.", "colaz"]):
            in_meal = "colazione"
        elif "sp. 1" in low or "sp.1" in low or "spuntino 1" in low:
            in_meal = "spuntino_1"
        elif "sp. 2" in low or "sp.2" in low:
            in_meal = "spuntino_2"
        elif "pranzo" in low:
            in_meal = "pranzo"
        elif "cena" in low:
            in_meal = "cena"
        elif "post-all" in low or "post all" in low:
            in_meal = "post_workout"
        elif low.startswith("oppure"):
            # Skip alternative meals
            in_meal = "skip"

        if in_meal == "skip":
            continue

        # Extract portions from current line
        portions = PORTION_PATTERN.findall(line)
        for grams_str, food_text in portions:
            grams = float(grams_str)
            food_key, confidence = match_food(food_text)
            if not food_key or confidence <= 0:
                continue

            # For pranzo/cena, only extract carbs and oil (proteins come from NOTA SECONDI)
            if in_meal in ("pranzo", "cena"):
                if food_key not in (
                    "pasta",
                    "riso",
                    "riso basmati",
                    "legumi",
                    "olio evo",
                ):
                    continue

            daily_fixed[food_key] += grams

        # Oil extraction
        oil_match = OIL_PATTERN.search(line)
        if oil_match:
            cucchiai = float(oil_match.group(1).replace(",", "."))
            daily_fixed["olio evo"] += cucchiai * 10  # 1 cucchiaio = ~10g

        # Items without explicit grams
        if "gallette" in low and in_meal == "spuntino_2":
            m = re.search(r"(\d+)\s*gallette", low)
            count = int(m.group(1)) if m else 2
            daily_fixed["gallette"] += count * 10

        if "banana" in low and in_meal == "post_workout":
            daily_fixed["banana"] += 120  # 1 banana media

        if "fette bisc" in low:
            num_match = re.search(r"(\d+)\s*fette", low)
            count = int(num_match.group(1)) if num_match else 4
            daily_fixed["fette biscottate"] += count * 10

    return dict(daily_fixed)


def parse_primo_restrictions(text_lines):
    """
    Parse day restrictions for primo piatto (e.g., 'pasta solo LU-ME-VE').
    Returns number of days with primo (default 7 if no restriction found).
    """
    for line in text_lines:
        low = line.lower().strip()
        if "pranzo" in low and ("solo" in low or "giorni" in low):
            # Count day abbreviations
            days_found = re.findall(
                r"(lu|ma|me|gi|ve|sa|do)", low
            )
            if days_found:
                return len(days_found)
    return 7  # Default: primo every day


def parse_spuntino2_affettato(text_lines):
    """
    Parse spuntino 2 for affettato portions.
    Returns grams of affettato per training day.
    """
    in_sp2 = False
    for line in text_lines:
        low = line.lower().strip()
        if "sp. 2" in low or "sp.2" in low:
            in_sp2 = True
        elif in_sp2:
            # Look for affettato
            if "affettato" in low or "bresaola" in low or "fesa" in low:
                portions = PORTION_PATTERN.findall(line)
                for grams_str, food_text in portions:
                    food_key, _ = match_food(food_text)
                    if food_key in (
                        "affettato magro",
                        "bresaola",
                        "fesa",
                        "crudo sgrassato",
                        "speck sgrassato",
                    ):
                        return food_key, float(grams_str)
            if any(m in low for m in ["pranzo", "cena", "post-all", "nota"]):
                break
    return "affettato magro", 100  # Default


# ── Quantity Aggregation ─────────────────────────────────────────────────────


def aggregate_weekly_quantities(pdf_path, people=1):
    """
    Parse a program PDF and aggregate weekly food quantities.
    Returns dict of food_key -> {"grams": total_weekly, "category": str}
    """
    text_lines = extract_text_from_pdf(pdf_path)

    # 1. Parse NOTA SECONDI (weekly protein rotation)
    weekly_proteins = parse_nota_secondi(text_lines)

    # 2. Parse fixed meals (same every day)
    daily_fixed = parse_fixed_meals(text_lines)

    # 3. Parse primo piatto day restrictions
    primo_days = parse_primo_restrictions(text_lines)

    # 4. Parse spuntino 2 affettato
    affettato_key, affettato_grams = parse_spuntino2_affettato(text_lines)

    # Aggregate everything to weekly totals
    weekly_totals = defaultdict(float)

    # Fixed meals: multiply daily by 7
    for food_key, daily_grams in daily_fixed.items():
        if food_key in ("pasta", "riso", "riso basmati"):
            # Apply primo restrictions
            weekly_totals[food_key] += daily_grams * primo_days
        else:
            weekly_totals[food_key] += daily_grams * 7

    # Weekly proteins from NOTA SECONDI
    for day, meals in weekly_proteins.items():
        if meals.get("pranzo"):
            food_key, grams = meals["pranzo"]
            weekly_totals[food_key] += grams
        if meals.get("cena"):
            food_key, grams = meals["cena"]
            weekly_totals[food_key] += grams

    # Affettato from spuntino 2 (assume 4 training days + 3 rest days)
    # Training days get gallette + affettato
    training_days = 4
    weekly_totals[affettato_key] += affettato_grams * training_days

    # Succo pompelmo from spuntino 1 (daily)
    if "succo pompelmo" not in weekly_totals:
        # Check if spuntino 1 mentions succo pompelmo
        for line in text_lines:
            low = line.lower()
            if "succo" in low and "pompelmo" in low:
                portions = PORTION_PATTERN.findall(line)
                for grams_str, food_text in portions:
                    if "pompelmo" in food_text.lower() or "succo" in food_text.lower():
                        weekly_totals["succo pompelmo"] += float(grams_str) * 7
                        break
                break

    # Multiply by number of people
    result = {}
    for food_key, total_grams in weekly_totals.items():
        if total_grams <= 0:
            continue
        category = get_food_category(food_key)
        result[food_key] = {
            "grams_per_person": round(total_grams, 1),
            "grams_total": round(total_grams * people, 1),
            "kg_total": round(total_grams * people / 1000, 3),
            "category": category,
        }

    return result


def get_food_category(food_key):
    """Determine the category for a food item."""
    for category, foods in FOOD_CATEGORIES.items():
        if food_key in foods:
            return category
    return "altro"


# ── Price Database ───────────────────────────────────────────────────────────


def load_price_db(price_db_path):
    """Load the price database."""
    if not os.path.exists(price_db_path):
        return {"version": "2.0", "locations": {}, "prices": {}}
    with open(price_db_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_price_db(price_db_path, price_db):
    """Save the price database, trimming history to MAX_HISTORY_ENTRIES."""
    # Trim history
    for location in price_db.get("prices", {}):
        for food in price_db["prices"][location]:
            history = price_db["prices"][location][food].get("history", [])
            if len(history) > MAX_HISTORY_ENTRIES:
                price_db["prices"][location][food]["history"] = history[
                    -MAX_HISTORY_ENTRIES:
                ]
    with open(price_db_path, "w", encoding="utf-8") as f:
        json.dump(price_db, f, ensure_ascii=False, indent=2)


def update_price(price_db, location, food, price, source, note=None):
    """
    Update a price in the database, moving the current price to history.
    """
    if location not in price_db.get("prices", {}):
        price_db.setdefault("prices", {})[location] = {}

    food_entry = price_db["prices"][location].get(food, {"current": None, "history": []})

    # Move current to history
    if food_entry.get("current"):
        food_entry.setdefault("history", []).append(food_entry["current"])

    # Set new current
    food_entry["current"] = {
        "min": price,
        "max": price,
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "source": source,
        "unit": food_entry.get("current", {}).get("unit", "kg"),
    }
    if note:
        food_entry["current"]["note"] = note

    price_db["prices"][location][food] = food_entry
    return food_entry


def log_receipt_price(price_db, location, food, exact_price, note=None):
    """Log a price from a receipt (highest reliability source)."""
    return update_price(price_db, location, food, exact_price, "scontrino", note)


def is_price_stale(price_entry):
    """Check if a price is stale (not updated in > STALE_DAYS)."""
    current = price_entry.get("current")
    if not current:
        return True
    updated = current.get("updated")
    if not updated:
        return True
    try:
        updated_date = datetime.strptime(updated, "%Y-%m-%d")
        return (datetime.now() - updated_date).days > STALE_DAYS
    except ValueError:
        return True


# ── Price Calculation ────────────────────────────────────────────────────────


def calculate_prices(weekly_quantities, price_db, locations=None, eur_chf=0.95):
    """
    Calculate prices for the shopping list across locations.
    Returns items with per-location pricing and recommendations.
    """
    all_locations = list(price_db.get("prices", {}).keys())
    if locations:
        all_locations = [loc for loc in locations if loc in price_db.get("prices", {})]

    if not all_locations:
        return {"items": [], "totals": {}, "recommendation": "No locations configured"}

    location_info = price_db.get("locations", {})
    items = []

    for food_key, qty in weekly_quantities.items():
        item = {
            "food": food_key,
            "category": qty["category"],
            "grams_total": qty["grams_total"],
            "kg_total": qty["kg_total"],
            "prices": {},
            "best_location": None,
            "stale_locations": [],
        }

        best_cost_eur = None

        for loc in all_locations:
            loc_prices = price_db.get("prices", {}).get(loc, {})
            food_price = loc_prices.get(food_key, {})
            current = food_price.get("current")

            if not current:
                continue

            # Check staleness
            if is_price_stale(food_price):
                item["stale_locations"].append(loc)

            # Average of min/max
            avg_price = (current["min"] + current["max"]) / 2
            unit = current.get("unit", "kg")

            # Calculate cost based on unit
            if unit == "kg":
                cost = qty["kg_total"] * avg_price
            elif unit == "l":
                # Convert grams to liters (approximate: 1L ≈ 1kg for most liquids)
                cost = qty["kg_total"] * avg_price
            else:
                cost = qty["kg_total"] * avg_price

            # Get currency
            currency = location_info.get(loc, {}).get("currency", "EUR")

            # Normalize to EUR for comparison
            cost_eur = cost
            if currency == "CHF":
                cost_eur = cost * eur_chf

            item["prices"][loc] = {
                "avg_price_per_unit": round(avg_price, 2),
                "min_price": current["min"],
                "max_price": current["max"],
                "cost": round(cost, 2),
                "currency": currency,
                "cost_eur": round(cost_eur, 2),
                "source": current.get("source", "unknown"),
                "updated": current.get("updated", "unknown"),
            }

            if best_cost_eur is None or cost_eur < best_cost_eur:
                best_cost_eur = cost_eur
                item["best_location"] = loc

        items.append(item)

    # Calculate totals per location
    totals = {}
    for loc in all_locations:
        currency = location_info.get(loc, {}).get("currency", "EUR")
        loc_total = sum(
            it["prices"].get(loc, {}).get("cost", 0) for it in items
        )
        loc_total_eur = sum(
            it["prices"].get(loc, {}).get("cost_eur", 0) for it in items
        )
        totals[loc] = {
            "total": round(loc_total, 2),
            "currency": currency,
            "total_eur": round(loc_total_eur, 2),
            "name": location_info.get(loc, {}).get("name", loc),
        }

    # Recommendation: split-buy (buy each item at its best location)
    split_total_eur = 0
    for it in items:
        costs = [
            it["prices"][loc]["cost_eur"]
            for loc in all_locations
            if loc in it["prices"]
        ]
        if costs:
            split_total_eur += min(costs)

    best_single = min(totals.items(), key=lambda x: x[1]["total_eur"]) if totals else None
    recommendation = ""
    if best_single and len(all_locations) > 1:
        recommendation = (
            f"Best single store: {best_single[1]['name']} "
            f"({best_single[1]['total']:.2f} {best_single[1]['currency']}). "
            f"Split-buy estimate: {split_total_eur:.2f} EUR."
        )
    elif best_single:
        recommendation = (
            f"Total at {best_single[1]['name']}: "
            f"{best_single[1]['total']:.2f} {best_single[1]['currency']}"
        )

    return {
        "items": items,
        "totals": totals,
        "recommendation": recommendation,
        "split_buy_total_eur": round(split_total_eur, 2),
    }


# ── Output Formatters ────────────────────────────────────────────────────────


def format_json(weekly_quantities, pricing, people):
    """Output as JSON."""
    return json.dumps(
        {
            "generated": datetime.now().isoformat(),
            "people": people,
            "items": pricing["items"],
            "totals": pricing["totals"],
            "recommendation": pricing["recommendation"],
            "split_buy_total_eur": pricing.get("split_buy_total_eur"),
        },
        ensure_ascii=False,
        indent=2,
    )


def format_markdown(weekly_quantities, pricing, people, locations_info):
    """Output as Markdown table with price comparison."""
    lines = []
    lines.append(f"# Lista della Spesa Settimanale ({people} {'persona' if people == 1 else 'persone'})")
    lines.append(f"*Generata: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

    # Group items by category
    by_category = defaultdict(list)
    for item in pricing["items"]:
        by_category[item["category"]].append(item)

    category_names = {
        "carne": "Carne",
        "pesce": "Pesce",
        "uova_latticini": "Uova e Latticini",
        "affettati": "Affettati",
        "carboidrati": "Carboidrati",
        "frutta": "Frutta",
        "verdure": "Verdure",
        "condimenti": "Condimenti e Grassi",
        "bevande": "Bevande",
        "integratori": "Integratori",
        "altro": "Altro",
    }

    # Get all locations for header
    all_locs = list(pricing["totals"].keys())

    for cat_key in [
        "carne",
        "pesce",
        "uova_latticini",
        "affettati",
        "carboidrati",
        "frutta",
        "condimenti",
        "bevande",
        "integratori",
        "altro",
    ]:
        items = by_category.get(cat_key, [])
        if not items:
            continue

        cat_name = category_names.get(cat_key, cat_key.title())
        lines.append(f"\n## {cat_name}\n")

        # Table header
        loc_headers = []
        for loc in all_locs:
            info = locations_info.get(loc, {})
            name = info.get("name", loc)
            currency = info.get("currency", "EUR")
            loc_headers.append(f"{name} ({currency})")

        header = "| Alimento | Quantita |"
        separator = "|----------|----------|"
        for lh in loc_headers:
            header += f" {lh} |"
            separator += "---------|"
        header += " Migliore |"
        separator += "----------|"

        lines.append(header)
        lines.append(separator)

        for item in sorted(items, key=lambda x: x["food"]):
            food = item["food"].replace("_", " ").title()
            qty_g = item["grams_total"]
            if qty_g >= 1000:
                qty_str = f"{qty_g / 1000:.1f} kg"
            else:
                qty_str = f"{qty_g:.0f} g"

            row = f"| {food} | {qty_str} |"

            for loc in all_locs:
                price_info = item["prices"].get(loc, {})
                if price_info:
                    cost = price_info["cost"]
                    currency = price_info["currency"]
                    stale = " *" if loc in item.get("stale_locations", []) else ""
                    row += f" {cost:.2f}{stale} |"
                else:
                    row += " - |"

            best = item.get("best_location", "")
            if best:
                best_name = locations_info.get(best, {}).get("name", best)
                row += f" {best_name} |"
            else:
                row += " - |"

            lines.append(row)

    # Totals
    lines.append("\n## Totali\n")
    lines.append("| Negozio | Totale | Totale (EUR) |")
    lines.append("|---------|--------|--------------|")
    for loc, total in pricing["totals"].items():
        lines.append(
            f"| {total['name']} | {total['total']:.2f} {total['currency']} | {total['total_eur']:.2f} EUR |"
        )

    if pricing.get("split_buy_total_eur"):
        lines.append(
            f"| **Split-buy** | | **{pricing['split_buy_total_eur']:.2f} EUR** |"
        )

    lines.append(f"\n> {pricing['recommendation']}")

    # Stale price warnings
    stale_items = [
        it for it in pricing["items"] if it.get("stale_locations")
    ]
    if stale_items:
        lines.append("\n### Prezzi da aggiornare (> 30 giorni)\n")
        for item in stale_items:
            locs = ", ".join(
                locations_info.get(loc, {}).get("name", loc)
                for loc in item["stale_locations"]
            )
            lines.append(f"- **{item['food']}**: {locs}")

    return "\n".join(lines)


def format_notion(weekly_quantities, pricing, people):
    """Output as Notion-compatible JSON payload."""
    pages = []
    for item in pricing["items"]:
        properties = {
            "Alimento": item["food"],
            "Categoria": item["category"],
            "Quantita (g)": item["grams_total"],
            "Quantita (kg)": item["kg_total"],
            "Best Location": item.get("best_location", ""),
        }
        for loc, price_info in item.get("prices", {}).items():
            properties[f"Costo {loc}"] = price_info.get("cost", 0)
        pages.append({"properties": properties})

    return json.dumps(
        {
            "generated": datetime.now().isoformat(),
            "people": people,
            "pages": pages,
            "totals": pricing["totals"],
        },
        ensure_ascii=False,
        indent=2,
    )


# ── Price History Report ─────────────────────────────────────────────────────


def generate_price_history_report(price_db, output_path=None):
    """Generate an HTML report showing price history trends."""
    locations_info = price_db.get("locations", {})
    prices = price_db.get("prices", {})

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html><head><meta charset='utf-8'>")
    html_parts.append("<title>Storico Prezzi - Shopping List</title>")
    html_parts.append("<script src='https://cdn.jsdelivr.net/npm/chart.js'></script>")
    html_parts.append("<style>")
    html_parts.append("body { font-family: sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }")
    html_parts.append("table { border-collapse: collapse; width: 100%; margin: 20px 0; }")
    html_parts.append("th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }")
    html_parts.append("th { background: #f5f5f5; }")
    html_parts.append(".stale { color: #e74c3c; font-weight: bold; }")
    html_parts.append(".fresh { color: #27ae60; }")
    html_parts.append("canvas { max-width: 100%; margin: 20px 0; }")
    html_parts.append("</style></head><body>")
    html_parts.append(f"<h1>Storico Prezzi</h1>")
    html_parts.append(f"<p>Generato: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>")

    for loc_id, loc_info in locations_info.items():
        loc_name = loc_info.get("name", loc_id)
        currency = loc_info.get("currency", "EUR")
        html_parts.append(f"<h2>{loc_name} ({loc_info.get('city', '')})</h2>")

        html_parts.append("<table>")
        html_parts.append("<tr><th>Alimento</th><th>Prezzo Attuale</th><th>Fonte</th><th>Aggiornato</th><th>Storico</th></tr>")

        loc_prices = prices.get(loc_id, {})
        for food, entry in sorted(loc_prices.items()):
            current = entry.get("current", {})
            history = entry.get("history", [])
            stale = is_price_stale(entry)

            price_str = f"{current.get('min', '?')}-{current.get('max', '?')} {currency}/{current.get('unit', 'kg')}"
            status_class = "stale" if stale else "fresh"
            updated = current.get("updated", "?")
            source = current.get("source", "?")
            history_count = len(history)

            html_parts.append(
                f"<tr><td>{food}</td><td>{price_str}</td>"
                f"<td>{source}</td>"
                f"<td class='{status_class}'>{updated}</td>"
                f"<td>{history_count} entries</td></tr>"
            )

        html_parts.append("</table>")

    html_parts.append("</body></html>")

    html_content = "\n".join(html_parts)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return output_path
    else:
        return html_content


# ── CLI ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate weekly shopping list from nutritional program PDF"
    )
    parser.add_argument(
        "--program-pdf", help="Path to the nutritional program PDF"
    )
    parser.add_argument(
        "--locations",
        help="Comma-separated list of location IDs (default: all in price_db)",
    )
    parser.add_argument(
        "--people", type=int, default=1, help="Number of people (default: 1)"
    )
    parser.add_argument(
        "--price-db",
        default=os.path.join(SCRIPT_DIR, "price_db.json"),
        help="Path to price database JSON",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    parser.add_argument(
        "--format",
        choices=["json", "markdown", "notion"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--update-price",
        nargs="+",
        metavar=("LOCATION", "FOOD", "PRICE", "SOURCE"),
        help="Update a price: LOCATION FOOD PRICE SOURCE [NOTE]",
    )
    parser.add_argument(
        "--report",
        choices=["price_history"],
        help="Generate a report",
    )
    parser.add_argument(
        "--eur-chf",
        type=float,
        default=0.95,
        help="EUR/CHF exchange rate (default: 0.95)",
    )

    args = parser.parse_args()

    # Handle --update-price
    if args.update_price:
        parts = args.update_price
        if len(parts) < 4:
            print(
                "Error: --update-price requires LOCATION FOOD PRICE SOURCE [NOTE]",
                file=sys.stderr,
            )
            sys.exit(1)
        location = parts[0]
        food = parts[1]
        price = float(parts[2])
        source = parts[3]
        note = parts[4] if len(parts) > 4 else None

        price_db = load_price_db(args.price_db)
        entry = update_price(price_db, location, food, price, source, note)
        save_price_db(args.price_db, price_db)
        print(
            f"Updated {food} at {location}: {price} ({source})",
            file=sys.stderr,
        )
        return

    # Handle --report
    if args.report == "price_history":
        price_db = load_price_db(args.price_db)
        result = generate_price_history_report(price_db, args.output)
        if not args.output:
            print(result)
        else:
            print(f"Report saved to {args.output}", file=sys.stderr)
        return

    # Main flow: generate shopping list
    if not args.program_pdf:
        print("Error: --program-pdf is required", file=sys.stderr)
        parser.print_help(sys.stderr)
        sys.exit(1)

    if not os.path.exists(args.program_pdf):
        print(f"Error: PDF not found: {args.program_pdf}", file=sys.stderr)
        sys.exit(1)

    # Parse PDF and aggregate quantities
    weekly_quantities = aggregate_weekly_quantities(args.program_pdf, args.people)

    # Load price database
    price_db = load_price_db(args.price_db)

    # Parse locations
    locations = None
    if args.locations:
        locations = [loc.strip() for loc in args.locations.split(",")]

    # Calculate prices
    pricing = calculate_prices(
        weekly_quantities, price_db, locations, args.eur_chf
    )

    locations_info = price_db.get("locations", {})

    # Format output
    if args.format == "json":
        output = format_json(weekly_quantities, pricing, args.people)
    elif args.format == "markdown":
        output = format_markdown(weekly_quantities, pricing, args.people, locations_info)
    elif args.format == "notion":
        output = format_notion(weekly_quantities, pricing, args.people)
    else:
        output = format_json(weekly_quantities, pricing, args.people)

    # Write output
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Shopping list saved to {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
