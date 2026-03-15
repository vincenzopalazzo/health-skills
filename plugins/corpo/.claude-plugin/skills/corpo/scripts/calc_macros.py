#!/usr/bin/env python3
"""
Macro & Calorie Calculator for Nutritional Programs.
Parses meal plan text from PDFs and calculates daily kcal, protein, carbs, fats.

Usage:
  python3 calc_macros.py <programs_data.json> --output <output.json>
  python3 calc_macros.py --pdf-dir <base_directory> --output <output.json>

Can be used standalone or integrated with extract_programs.py output.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

try:
    import pdfplumber
except ImportError:
    os.system("pip install pdfplumber --break-system-packages -q")
    import pdfplumber


# ── Nutritional Database (per 100g raw unless noted) ─────────────────────────
# Values: (kcal, protein_g, carbs_g, fat_g) per 100g
FOOD_DB = {
    # Proteins - Meat
    "carne rossa magra": (120, 22.0, 0, 3.5),  # vitello/manzo magro
    "carne bianca magra": (110, 23.0, 0, 1.5),  # pollo/tacchino petto
    "carne bianca": (110, 23.0, 0, 1.5),
    "hamburger": (140, 20.0, 0, 7.0),  # hamburger di sola carne magra
    "bresaola": (151, 33.0, 0, 2.0),
    "fesa": (110, 22.0, 1, 2.0),  # fesa di tacchino
    "crudo sgrassato": (195, 28.0, 0, 9.0),  # prosciutto crudo sgrassato
    "speck sgrassato": (153, 29.0, 0, 4.0),
    "affettato magro": (140, 28.0, 0.5, 3.0),  # media affettati magri
    # Proteins - Fish
    "pesce magro": (85, 18.0, 0, 1.0),  # merluzzo/sogliola/orata
    "pesce azzurro": (185, 20.0, 0, 12.0),  # salmone/sgombro
    "gamberetti": (71, 14.0, 1, 0.6),
    "gamberi": (71, 14.0, 1, 0.6),
    "seppie": (72, 16.0, 0.7, 0.7),
    "calamari": (81, 15.6, 0.8, 1.4),
    "polipo": (82, 15.5, 2.2, 0.9),
    "tonno al naturale": (103, 23.5, 0, 0.8),
    # Proteins - Dairy & Eggs
    "albumi": (52, 11.0, 0.7, 0.2),
    "uova": (155, 13.0, 1.1, 11.0),  # intere
    "tuorlo": (322, 16.0, 3.6, 27.0),  # singolo tuorlo ~18g
    "yogurt senza zuccheri": (57, 10.0, 3.6, 0.7),  # tipo Total FAGE 0%
    "yogurt": (57, 10.0, 3.6, 0.7),
    "ricotta vaccina": (146, 11.0, 3.0, 10.0),
    "mozzarella light": (160, 20.0, 1.0, 9.0),
    # Carbs - Grains
    "pasta": (353, 12.5, 72.0, 1.5),  # secca
    "riso": (340, 7.0, 79.0, 0.6),  # bianco secco
    "riso basmati": (345, 8.0, 78.0, 0.6),
    "avena": (389, 16.9, 66.3, 6.9),  # fiocchi avena
    "fiocchi avena": (389, 16.9, 66.3, 6.9),
    "fette biscottate": (408, 11.0, 72.0, 8.5),  # tipo Misura senza zucchero
    "gallette": (387, 8.0, 81.0, 3.0),  # gallette di riso
    "wasa": (320, 11.0, 60.0, 2.0),
    # Carbs - Fruit
    "banana": (89, 1.1, 23.0, 0.3),  # ~120g una banana media
    "frutta fresca": (47, 0.5, 11.0, 0.2),  # media frutta
    "marmellata senza zuccheri": (130, 0.4, 30.0, 0.1),
    # Fats
    "olio evo": (884, 0, 0, 100.0),  # 1 cucchiaio = ~10g
    "frutta secca": (607, 15.0, 20.0, 51.0),  # mix noci/mandorle
    "avocado": (160, 2.0, 8.5, 14.7),  # mezzo = ~75g
    # Supplements
    "whey": (400, 80.0, 8.0, 5.0),  # per 100g polvere
    "creatina": (0, 0, 0, 0),  # no calorie
    # Legumes
    "legumi": (104, 7.0, 15.0, 1.5),  # in scatola, 125g
    # Milk
    "latte vegetale": (30, 0.5, 3.0, 1.5),  # soia/avena non dolcificato
    "latte scremato": (34, 3.4, 5.0, 0.1),
}


# ── Portion size patterns from PDFs ──────────────────────────────────────────
# These patterns match typical lines in the nutritional programs

# Regex to capture: quantity(g) + food item
PORTION_PATTERN = re.compile(r"(\d+)\s*g\s+(.+?)(?:\s*\(|$|\s+–|\s+\+)", re.IGNORECASE)

# Specific portion defaults (when no grams specified)
DEFAULT_PORTIONS = {
    "fette biscottate": 40,  # ~4 fette = ~40g
    "gallette": 20,  # 2 gallette = ~20g
    "banana": 120,  # 1 banana media
    "tuorlo": 18,  # 1 tuorlo
    "uova": 60,  # 1 uovo intero
    "avocado_half": 75,  # mezzo avocado
}

# Oil: 1 cucchiaio = ~10g, 1.5 cucchiai = ~15g
OIL_PATTERN = re.compile(r"([\d.,]+)\s*cucchia[io]\s+olio", re.IGNORECASE)


def match_food(text):
    """Match text to a food in the database. Returns (food_key, confidence)."""
    low = text.lower().strip()

    # Direct match
    for key in FOOD_DB:
        if key in low:
            return key, 1.0

    # Partial matches
    aliases = {
        "pollo": "carne bianca magra",
        "tacchino": "carne bianca magra",
        "coniglio": "carne bianca magra",
        "vitello": "carne rossa magra",
        "manzo": "carne rossa magra",
        "cavallo": "carne rossa magra",
        "merluzzo": "pesce magro",
        "sogliola": "pesce magro",
        "orata": "pesce magro",
        "cernia": "pesce magro",
        "spigola": "pesce magro",
        "tonno": "tonno al naturale",
        "salmone": "pesce azzurro",
        "sgombro": "pesce azzurro",
        "trota": "pesce azzurro",
        "proteine": "whey",
        "protein": "whey",
    }
    for alias, key in aliases.items():
        if alias in low:
            return key, 0.8

    return None, 0


def parse_meal_plan(text_lines):
    """
    Parse the base meal plan from PDF text lines (excluding NOTA SECONDI).
    Returns dict of meal_name -> list of food items with grams.

    Key design decisions:
    - Stop parsing when we hit "NOTA SECONDI" or "GIORNO" (the weekly protein table)
    - Track "Oppure" alternatives: only keep the FIRST breakfast option (most common choice)
    - Pranzo: only extract carb sources (pasta/riso) and oil, NOT protein (that comes from weekly_proteins)
    - Spuntino 2: has two variants (training day vs rest day), store both
    """
    current_meal = None
    in_alternative = False  # track "Oppure" sections
    stop_parsing = False

    # Ordered meal markers — checked from top
    meal_markers = [
        ("col.", "colazione"),
        ("colaz", "colazione"),
        ("pancake", "colazione"),
        ("oppure porridge", "colazione_alt2"),
        ("oppure", "colazione_alt"),
        ("sp. 1", "spuntino_1"),
        ("sp.1", "spuntino_1"),
        ("spuntino 1", "spuntino_1"),
        ("pranzo", "pranzo"),
        ("sp. 2 gg all", "spuntino_2_training"),
        ("sp. 2", "spuntino_2_training"),
        ("sp.2", "spuntino_2_training"),
        ("altri gg", "spuntino_2_rest"),
        ("cena", "cena"),
        ("post-all", "post_workout"),
    ]

    items_by_meal = defaultdict(list)

    for line in text_lines:
        low = line.lower().strip()
        if not low:
            continue

        # Stop at the weekly protein table
        if any(stop in low for stop in ["nota secondi", "giorno pranzo cena"]):
            stop_parsing = True
        if stop_parsing:
            # Still pick up food notes below the table
            if any(
                kw in low
                for kw in [
                    "carne rossa magra:",
                    "carne bianca magra:",
                    "pesce magro:",
                    "pesce azzurro:",
                    "formaggi:",
                    "considerare",
                ]
            ):
                continue
            break

        # Skip day-specific lines (LUNEDI, MARTEDI etc. in the secondi table)
        if re.match(r"^(luned|marted|mercoled|gioved|venerd|sabato|domenica)", low):
            continue

        # Detect meal change
        for marker, meal_name in meal_markers:
            if low.startswith(marker) or (marker in low and len(low) < 80):
                current_meal = meal_name
                break

        if not current_meal:
            continue

        # Skip alternative breakfast options — we only compute one
        if current_meal.startswith("colazione_alt"):
            continue

        # For pranzo: only extract carb sources and oil, skip "Secondo (vedi Nota)"
        if current_meal == "pranzo":
            if "secondo" in low or "vedi nota" in low:
                continue
            # Only capture carb items (pasta, riso) and oil
            portions = PORTION_PATTERN.findall(line)
            for grams_str, food_text in portions:
                grams = float(grams_str)
                food_key, confidence = match_food(food_text)
                if food_key and food_key in ("pasta", "riso", "riso basmati", "legumi"):
                    items_by_meal["pranzo"].append(
                        {
                            "food": food_key,
                            "grams": grams,
                            "raw_text": f"{grams_str}g {food_text.strip()}",
                            "confidence": confidence,
                        }
                    )
            # Oil
            oil_match = OIL_PATTERN.search(line)
            if oil_match:
                cucchiai = float(oil_match.group(1).replace(",", "."))
                items_by_meal["pranzo"].append(
                    {
                        "food": "olio evo",
                        "grams": cucchiai * 10,
                        "raw_text": f"{cucchiai} cucchiai olio evo",
                        "confidence": 1.0,
                    }
                )
            continue

        # For cena: only oil (protein comes from weekly_proteins)
        if current_meal == "cena":
            oil_match = OIL_PATTERN.search(line)
            if oil_match:
                cucchiai = float(oil_match.group(1).replace(",", "."))
                items_by_meal["cena"].append(
                    {
                        "food": "olio evo",
                        "grams": cucchiai * 10,
                        "raw_text": f"{cucchiai} cucchiai olio evo",
                        "confidence": 1.0,
                    }
                )
            continue

        # General extraction for other meals (colazione, snacks, post-workout)
        portions = PORTION_PATTERN.findall(line)
        for grams_str, food_text in portions:
            grams = float(grams_str)
            food_key, confidence = match_food(food_text)
            if food_key and confidence > 0:
                items_by_meal[current_meal].append(
                    {
                        "food": food_key,
                        "grams": grams,
                        "raw_text": f"{grams_str}g {food_text.strip()}",
                        "confidence": confidence,
                    }
                )

        # Oil
        if current_meal not in ("pranzo", "cena"):
            oil_match = OIL_PATTERN.search(line)
            if oil_match:
                cucchiai = float(oil_match.group(1).replace(",", "."))
                items_by_meal[current_meal].append(
                    {
                        "food": "olio evo",
                        "grams": cucchiai * 10,
                        "raw_text": f"{cucchiai} cucchiai olio evo",
                        "confidence": 1.0,
                    }
                )

        # Detect specific items without grams
        if "fette bisc" in low:
            num_match = re.search(r"(\d+)\s*fette", low)
            count = int(num_match.group(1)) if num_match else 4
            items_by_meal[current_meal].append(
                {
                    "food": "fette biscottate",
                    "grams": count * 10,
                    "raw_text": f"{count} fette biscottate",
                    "confidence": 0.9,
                }
            )

        if "marmellata" in low:
            items_by_meal[current_meal].append(
                {
                    "food": "marmellata senza zuccheri",
                    "grams": 15,
                    "raw_text": "un velo marmellata",
                    "confidence": 0.7,
                }
            )

        if "banana" in low and current_meal == "post_workout":
            items_by_meal[current_meal].append(
                {
                    "food": "banana",
                    "grams": 120,
                    "raw_text": "1 banana matura",
                    "confidence": 0.9,
                }
            )

        if "gallette" in low:
            m = re.search(r"(\d+)\s*gallette", low)
            count = int(m.group(1)) if m else 2
            items_by_meal[current_meal].append(
                {
                    "food": "gallette",
                    "grams": count * 10,
                    "raw_text": f"{count} gallette",
                    "confidence": 0.9,
                }
            )

    return dict(items_by_meal)


def parse_weekly_proteins(text_lines):
    """
    Parse the 'NOTA SECONDI' table to get daily protein sources and portions.
    Returns dict of day -> {pranzo: (food, grams), cena: (food, grams)}
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

        # Match day lines: LUNEDI 200 g Carne rossa magra 250 g Pesce magro
        day_match = re.match(
            r"(luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica)\s+(.+)",
            low,
        )
        if day_match:
            day = day_match.group(1)
            rest = day_match.group(2)

            # Find all portions in the line
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
                pranzo = ("albumi", 200)  # albumi a sazietà ≈ 200g + 1 tuorlo

            if "insalata" in rest and "gamberetti" in rest:
                cena = ("gamberetti", 300)

            if "libera" in rest:
                cena = ("carne bianca", 250)  # estimate for "libera"

            weekly[day] = {"pranzo": pranzo, "cena": cena}

    return weekly


def calculate_meal_macros(meal_items):
    """Calculate total macros for a list of food items."""
    total = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "items": []}

    for item in meal_items:
        food = item["food"]
        grams = item["grams"]

        if food in FOOD_DB:
            kcal_100, prot_100, carb_100, fat_100 = FOOD_DB[food]
            factor = grams / 100.0

            item_macros = {
                "food": food,
                "grams": grams,
                "kcal": round(kcal_100 * factor, 1),
                "protein": round(prot_100 * factor, 1),
                "carbs": round(carb_100 * factor, 1),
                "fat": round(fat_100 * factor, 1),
                "raw_text": item.get("raw_text", ""),
            }

            total["kcal"] += item_macros["kcal"]
            total["protein"] += item_macros["protein"]
            total["carbs"] += item_macros["carbs"]
            total["fat"] += item_macros["fat"]
            total["items"].append(item_macros)

    # Round totals
    for k in ["kcal", "protein", "carbs", "fat"]:
        total[k] = round(total[k], 1)

    return total


def estimate_daily_macros(meal_plan, weekly_proteins, has_training=True):
    """
    Estimate daily macros by combining the base meal plan with weekly protein rotation.

    The meal plan structure from the PDFs is:
    - Colazione (breakfast): fixed options (pancake or yogurt or porridge)
    - Spuntino 1: whey + frutta secca (fixed)
    - Pranzo: carb source (pasta/riso on LU-ME-VE only) + protein (from weekly rotation) + oil + verdure
    - Spuntino 2: differs between training days (whey+frutta) and rest days (gallette+affettato)
    - Cena: protein (from weekly rotation) + oil + verdure (no carbs)
    - Post-workout: whey + banana (only training days)

    Returns a dict with training_day, rest_day, weekly_average, and per-meal breakdown.
    """
    meal_breakdown = {}

    # Calculate macros for each parsed meal
    for meal_name, items in meal_plan.items():
        if meal_name.startswith("colazione_alt"):
            continue  # skip alternatives
        meal_macros = calculate_meal_macros(items)
        meal_breakdown[meal_name] = meal_macros

    # ── Fixed meals (same every day) ──
    colazione = meal_breakdown.get(
        "colazione", {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )
    spuntino1 = meal_breakdown.get(
        "spuntino_1", {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )

    # ── Pranzo base (carbs + oil, WITHOUT protein) ──
    pranzo_base = meal_breakdown.get(
        "pranzo", {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )
    # Note: pranzo has pasta/riso only on LU-ME-VE (3 days out of 7)
    # On other days, pranzo has only protein + oil + verdure (no carb source)
    # Detect if there are multiple carb entries (pasta + riso basmati)
    pranzo_items = meal_plan.get("pranzo", [])
    carb_items = [
        i for i in pranzo_items if i["food"] in ("pasta", "riso", "riso basmati")
    ]
    oil_items = [i for i in pranzo_items if i["food"] == "olio evo"]

    # Calculate pranzo carbs for training days (when pasta/riso is available)
    pranzo_carb_macros = (
        calculate_meal_macros(carb_items)
        if carb_items
        else {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )
    pranzo_oil_macros = (
        calculate_meal_macros(oil_items)
        if oil_items
        else {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )

    # ── Cena base (oil only, protein from rotation) ──
    cena_base = meal_breakdown.get(
        "cena", {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )

    # ── Snack variants ──
    sp2_training = meal_breakdown.get(
        "spuntino_2_training", {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )
    sp2_rest = meal_breakdown.get(
        "spuntino_2_rest", sp2_training
    )  # fallback to training version

    # ── Post-workout (training days only) ──
    post_workout = meal_breakdown.get(
        "post_workout", {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
    )

    # ── Average daily protein from weekly rotation ──
    days_protein_data = []
    if weekly_proteins:
        for day, proteins in weekly_proteins.items():
            day_prot = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
            for meal_type in ["pranzo", "cena"]:
                if proteins.get(meal_type):
                    food, grams = proteins[meal_type]
                    if food in FOOD_DB:
                        kcal_100, prot_100, carb_100, fat_100 = FOOD_DB[food]
                        factor = grams / 100.0
                        day_prot["kcal"] += kcal_100 * factor
                        day_prot["protein"] += prot_100 * factor
                        day_prot["carbs"] += carb_100 * factor
                        day_prot["fat"] += fat_100 * factor
            days_protein_data.append(day_prot)

    if days_protein_data:
        avg_protein = {
            k: round(sum(d[k] for d in days_protein_data) / len(days_protein_data), 1)
            for k in ["kcal", "protein", "carbs", "fat"]
        }
    else:
        avg_protein = {"kcal": 0, "protein": 0, "carbs": 0, "fat": 0}

    # ── Verdure estimate (both pranzo and cena include "verdure libere") ──
    # ~200g mixed vegetables per meal = ~50 kcal, ~3g carbs, ~2g protein per serving
    verdure_per_meal = {"kcal": 50, "protein": 2, "carbs": 8, "fat": 0.5}
    verdure_daily = {k: v * 2 for k, v in verdure_per_meal.items()}  # 2 meals

    def sum_macros(*sources):
        return {
            k: round(sum(s.get(k, 0) for s in sources), 1)
            for k in ["kcal", "protein", "carbs", "fat"]
        }

    # ── TRAINING DAY ──
    # colazione + sp1 + pranzo(carbs+oil+protein+verdure) + sp2_training + cena(oil+protein+verdure) + post-workout
    # Pranzo carbs: average of pasta(100g) appearing 3/7 days and riso basmati(120g) appearing 1/7 days
    # Simplification: use the average carb entry since we're already averaging proteins
    # Actually: on training days (LU-ME-VE), there IS pasta/riso. On other days, there isn't.
    # Training days = 4, but carbs only on LU-ME-VE = 3 of those 4 days → use average
    training_day = sum_macros(
        colazione,
        spuntino1,
        pranzo_oil_macros,
        pranzo_carb_macros,
        avg_protein,
        verdure_daily,
        sp2_training,
        cena_base,
        post_workout,
    )

    # ── REST DAY ──
    # colazione + sp1 + pranzo(oil+protein+verdure, NO carbs) + sp2_rest + cena(oil+protein+verdure)
    rest_day = sum_macros(
        colazione,
        spuntino1,
        pranzo_oil_macros,
        avg_protein,
        verdure_daily,
        sp2_rest,
        cena_base,
    )

    # ── WEEKLY AVERAGE ── (4 training + 3 rest days)
    weekly_avg = {}
    for k in ["kcal", "protein", "carbs", "fat"]:
        weekly_avg[k] = round((training_day[k] * 4 + rest_day[k] * 3) / 7, 1)

    # ── Per-meal summary for display ──
    per_meal = {
        "colazione": {
            k: colazione.get(k, 0) for k in ["kcal", "protein", "carbs", "fat"]
        },
        "spuntino_1": {
            k: spuntino1.get(k, 0) for k in ["kcal", "protein", "carbs", "fat"]
        },
        "pranzo_training": sum_macros(
            pranzo_oil_macros,
            pranzo_carb_macros,
            {
                "kcal": avg_protein["kcal"] / 2,
                "protein": avg_protein["protein"] / 2,
                "carbs": avg_protein["carbs"] / 2,
                "fat": avg_protein["fat"] / 2,
            },
            verdure_per_meal,
        ),
        "pranzo_rest": sum_macros(
            pranzo_oil_macros,
            {
                "kcal": avg_protein["kcal"] / 2,
                "protein": avg_protein["protein"] / 2,
                "carbs": avg_protein["carbs"] / 2,
                "fat": avg_protein["fat"] / 2,
            },
            verdure_per_meal,
        ),
        "spuntino_2_training": {
            k: sp2_training.get(k, 0) for k in ["kcal", "protein", "carbs", "fat"]
        },
        "spuntino_2_rest": {
            k: sp2_rest.get(k, 0) for k in ["kcal", "protein", "carbs", "fat"]
        },
        "cena": sum_macros(
            cena_base,
            {
                "kcal": avg_protein["kcal"] / 2,
                "protein": avg_protein["protein"] / 2,
                "carbs": avg_protein["carbs"] / 2,
                "fat": avg_protein["fat"] / 2,
            },
            verdure_per_meal,
        ),
        "post_workout": {
            k: post_workout.get(k, 0) for k in ["kcal", "protein", "carbs", "fat"]
        },
    }

    return {
        "training_day": training_day,
        "rest_day": rest_day,
        "weekly_average": weekly_avg,
        "meal_breakdown": per_meal,
        "protein_per_kg": None,  # filled in later if weight available
    }


def extract_macros_from_pdf(pdf_path):
    """Extract macro data from a single nutrition PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_lines = []
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    all_lines.extend(t.split("\n"))

        meal_plan = parse_meal_plan(all_lines)
        weekly_proteins = parse_weekly_proteins(all_lines)

        if not meal_plan and not weekly_proteins:
            return None

        macros = estimate_daily_macros(meal_plan, weekly_proteins)

        # Extract weight for protein/kg calculation
        for line in all_lines:
            m = re.search(r"Peso tot\.\s*\(kg\)\s*([\d.,]+)", line)
            if m:
                weight = float(m.group(1).replace(",", "."))
                if macros["weekly_average"]["protein"] and weight > 0:
                    macros["protein_per_kg"] = round(
                        macros["weekly_average"]["protein"] / weight, 2
                    )
                break

        return macros

    except Exception as e:
        print(f"Error extracting macros from {pdf_path}: {e}", file=sys.stderr)
        return None


def process_all_programs(base_dir, program_range=None):
    """Process all program directories and extract macro data."""
    results = {}

    dirs = []
    for d in os.listdir(base_dir):
        m = re.match(r"#(\d+)_programm", d)
        if m:
            num = int(m.group(1))
            if program_range and (num < program_range[0] or num > program_range[1]):
                continue
            dirs.append((num, os.path.join(base_dir, d)))

    dirs.sort(key=lambda x: x[0])

    for num, dirpath in dirs:
        files = os.listdir(dirpath)
        nutrition_pdfs = [
            f for f in files if f.endswith(".pdf") and "all" not in f.lower()
        ]
        if not nutrition_pdfs:
            nutrition_pdfs = [f for f in files if f.endswith(".pdf")]

        for pdf_name in nutrition_pdfs[:1]:
            filepath = os.path.join(dirpath, pdf_name)
            print(f"  Extracting macros from #{num}...", file=sys.stderr)
            macros = extract_macros_from_pdf(filepath)
            if macros:
                results[num] = macros

    return results


def enrich_programs_data(programs_json_path, base_dir):
    """
    Add macro data to an existing programs_data.json file.
    Returns the enriched data structure.
    """
    with open(programs_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    macro_data = process_all_programs(base_dir)

    for prog in data["programs"]:
        num = prog["program_num"]
        if num in macro_data:
            prog["macros"] = macro_data[num]
            # Add protein/kg if weight available
            if prog.get("weight") and macro_data[num]["weekly_average"]["protein"]:
                prog["macros"]["protein_per_kg"] = round(
                    macro_data[num]["weekly_average"]["protein"] / prog["weight"], 2
                )

    # Add macro summary
    macro_timeline = []
    for prog in data["programs"]:
        if "macros" in prog:
            macro_timeline.append(
                {
                    "program_num": prog["program_num"],
                    "date": prog.get("date"),
                    "weight": prog.get("weight"),
                    "phase": prog.get("phase_label", ""),
                    "daily_kcal_avg": prog["macros"]["weekly_average"]["kcal"],
                    "protein_g": prog["macros"]["weekly_average"]["protein"],
                    "carbs_g": prog["macros"]["weekly_average"]["carbs"],
                    "fat_g": prog["macros"]["weekly_average"]["fat"],
                    "protein_per_kg": prog["macros"].get("protein_per_kg"),
                }
            )

    data["macro_timeline"] = macro_timeline

    return data


def main():
    parser = argparse.ArgumentParser(
        description="Calculate macros from nutritional programs"
    )
    parser.add_argument("--programs-json", help="Existing programs_data.json to enrich")
    parser.add_argument("--pdf-dir", help="Base directory with #XX_programmi folders")
    parser.add_argument("--output", "-o", required=True, help="Output JSON file")
    parser.add_argument(
        "--range", nargs=2, type=int, default=None, help="Program range"
    )
    args = parser.parse_args()

    if args.programs_json and args.pdf_dir:
        # Enrich existing data
        data = enrich_programs_data(args.programs_json, args.pdf_dir)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Enriched data saved to {args.output}", file=sys.stderr)

    elif args.pdf_dir:
        # Standalone extraction
        results = process_all_programs(args.pdf_dir, args.range)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Macro data saved to {args.output}", file=sys.stderr)

    else:
        print(
            "Provide --programs-json + --pdf-dir, or --pdf-dir alone", file=sys.stderr
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
