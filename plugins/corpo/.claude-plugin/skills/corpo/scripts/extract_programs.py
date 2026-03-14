#!/usr/bin/env python3
"""
Nutritional Program Extractor
Extracts body composition, supplement, nutrition, and training data from program PDFs.
Usage: python3 extract_programs.py <base_directory> [--output <output.json>] [--range START END]
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


# ── Compound classification ──────────────────────────────────────────────────
COMPOUND_DB = {
    # SARMs
    "rad 140": {"name": "RAD 140 (Testolone)", "category": "SARM", "risk": "high",
                "effects": ["HPTA suppression", "hepatotoxicity", "HDL reduction"],
                "notes": "One of the most potent SARMs, significant testosterone suppression"},
    "rad140": {"name": "RAD 140 (Testolone)", "category": "SARM", "risk": "high",
               "effects": ["HPTA suppression", "hepatotoxicity", "HDL reduction"], "notes": ""},
    "mk2866": {"name": "MK-2866 (Ostarine)", "category": "SARM", "risk": "high",
               "effects": ["HPTA suppression", "HDL reduction"],
               "notes": "Milder SARM but still suppressive"},
    "mk-2866": {"name": "MK-2866 (Ostarine)", "category": "SARM", "risk": "high",
                "effects": ["HPTA suppression", "HDL reduction"], "notes": ""},
    "ostarine": {"name": "MK-2866 (Ostarine)", "category": "SARM", "risk": "high",
                 "effects": ["HPTA suppression", "HDL reduction"], "notes": ""},
    "lgd-4033": {"name": "LGD-4033 (Ligandrol)", "category": "SARM", "risk": "high",
                 "effects": ["HPTA suppression", "HDL reduction", "water retention"], "notes": ""},

    # GH Secretagogues
    "mk-677": {"name": "MK-677 (Ibutamoren)", "category": "GH_secretagogue", "risk": "medium-high",
               "effects": ["insulin resistance", "water retention", "increased appetite", "elevated GH/IGF-1"],
               "notes": "Non-suppressive to HPTA, but long-term GH elevation carries risks"},
    "mk677": {"name": "MK-677 (Ibutamoren)", "category": "GH_secretagogue", "risk": "medium-high",
              "effects": ["insulin resistance", "water retention", "increased appetite"], "notes": ""},
    "lx-gh pro": {"name": "LX-GH PRO (Core Labs)", "category": "GH_booster", "risk": "medium-high",
                  "effects": ["GH elevation", "possible liver stress"], "notes": ""},

    # PPAR-delta
    "gw501516": {"name": "GW501516 (Cardarine)", "category": "PPAR_delta_agonist", "risk": "high",
                 "effects": ["potential carcinogenicity (animal studies)", "improved endurance"],
                 "notes": "Abandoned by GSK due to tumor development in rats/mice"},
    "cardarine": {"name": "GW501516 (Cardarine)", "category": "PPAR_delta_agonist", "risk": "high",
                  "effects": ["potential carcinogenicity"], "notes": ""},

    # Pro-Hormones
    "dmz": {"name": "DMZ (Dymethazine)", "category": "pro_hormone", "risk": "very_high",
            "effects": ["severe hepatotoxicity (17α-alkylated)", "complete HPTA suppression",
                        "HDL destruction", "blood pressure increase"],
            "notes": "True steroid, one of the most hepatotoxic oral compounds"},
    "g-mass": {"name": "G-Mass (Animal Factory)", "category": "pro_hormone", "risk": "high",
               "effects": ["hepatotoxicity", "HPTA suppression", "lipid alteration"], "notes": ""},
    "veno test": {"name": "Veno Test (Core Labs)", "category": "testosterone_booster", "risk": "medium",
                  "effects": ["possible mild HPTA modulation"], "notes": ""},

    # PCT
    "test restore": {"name": "Test Restore AM (Revange)", "category": "PCT", "risk": "low-medium",
                     "effects": ["estrogen modulation"], "notes": "Post-cycle therapy"},
    "pct pro": {"name": "PCT PRO (Core Labs)", "category": "PCT", "risk": "medium",
                "effects": ["HPTA recovery support", "estrogen modulation"],
                "notes": "If used long after last cycle, may indicate incomplete recovery"},
    "alpha male": {"name": "Alpha Male (Revange)", "category": "PCT", "risk": "medium",
                   "effects": ["anti-estrogenic", "testosterone support"], "notes": ""},
    "turkester": {"name": "Turkesterone 650 (Hi-Tech)", "category": "ecdysteroid", "risk": "low",
                  "effects": ["mild anabolic support"], "notes": "Plant-based, generally safe"},

    # Liver support
    "liver": {"name": "Liver (Revange)", "category": "liver_support", "risk": "low",
              "effects": ["hepatoprotective"], "notes": "Protective, should be used during hepatotoxic cycles"},

    # Thermogenics / Fat burners
    "ripper": {"name": "Ripper (Skull Labs)", "category": "thermogenic", "risk": "medium",
               "effects": ["stimulant stress", "cardiovascular load", "appetite suppression"],
               "notes": "High stimulant content"},
    "laser melt": {"name": "Laser Melt (Toxic Pharma)", "category": "thermogenic", "risk": "medium",
                   "effects": ["stimulant stress", "pre-workout energy"], "notes": ""},
    "animal cuts": {"name": "Animal Cuts (Universal)", "category": "thermogenic", "risk": "medium",
                    "effects": ["stimulant load", "thermogenesis"], "notes": ""},
    "yohimbine": {"name": "Yohimbine HCL", "category": "fat_burner", "risk": "medium",
                  "effects": ["alpha-2 antagonist", "cardiovascular stress", "anxiety", "blood pressure increase"],
                  "notes": "Potent fat burner, significant side effects in sensitive individuals"},

    # Base supplements
    "creatina": {"name": "Creatina Monoidrato", "category": "base", "risk": "very_low",
                 "effects": ["strength", "muscle volume", "neuroprotection"], "notes": "Extensively studied, safe"},
    "glutammina": {"name": "Glutammina", "category": "base", "risk": "very_low",
                   "effects": ["recovery", "immune support", "gut health"], "notes": ""},
    "acetilcarnitina": {"name": "Acetil-L-Carnitina", "category": "base", "risk": "very_low",
                        "effects": ["fat oxidation", "cognitive support"], "notes": ""},
    "bcaa": {"name": "BCAA", "category": "base", "risk": "very_low",
             "effects": ["muscle recovery"], "notes": ""},
    "omega": {"name": "Omega 3", "category": "base", "risk": "very_low",
              "effects": ["anti-inflammatory", "cardiovascular support", "lipid improvement"], "notes": ""},
    "acido lipoico": {"name": "Acido Alfa-Lipoico", "category": "base", "risk": "very_low",
                      "effects": ["antioxidant", "insulin sensitivity"], "notes": ""},
    "cla": {"name": "CLA", "category": "base", "risk": "very_low",
            "effects": ["body composition support"], "notes": ""},
    "vsl3": {"name": "VSL#3", "category": "probiotic", "risk": "very_low",
             "effects": ["gut health", "immune support"], "notes": ""},
    "magnesio": {"name": "Magnesio Potassio", "category": "base", "risk": "very_low",
                 "effects": ["electrolyte balance", "recovery"], "notes": ""},
}

# Keywords for supplement line detection
SUPP_KEYWORDS = [
    'rad 140', 'rad140', 'mk-677', 'mk677', 'mk2866', 'mk-2866', 'gw501516',
    'ostarine', 'cardarine', 'lgd', 'sarm',
    'creatina', 'glutammina', 'bcaa', 'omega', 'vitamina', 'multivit',
    'carnitin', 'acetilcarnitin', 'acido lipoico', 'cla',
    'ripper', 'skull lab', 'laser melt', 'toxic pharma',
    'test restore', 'turkester', 'pct pro',
    'liver', 'revange', 'core lab', 'veno test', 'lx-gh',
    'animal factory', 'animal cuts', 'g-mass', 'alpha male',
    'dmz', 'yohimbine', 'yohimb',
    'swiss', 'yamamoto', 'flexotor',
    'euphoriq', 'muscletech', 'c4', 'cellucor',
    'black focus', 'acid melt', 'hazard',
    'magnesio potassio', 'swisse', 'vsl3', 'vsl',
    'mister hyde', 'pro supps',
]

# Keywords indicating a supplement/protocol line (not food)
SUPP_CONTEXT_KEYWORDS = [
    'pre-all', 'post-all', 'pre-col', 'pre-sonno', 'pre-pranzo', 'pre-cena',
    'colaz.', 'a colaz', 'a pranzo', 'a cena',
    'cps', 'caps', 'mg', 'misurino', 'bustine', 'bustina', 'compresse',
    'settiman', 'stripping',
]


def classify_compound(line):
    """Identify compounds in a supplement line and return classifications."""
    low = line.lower()
    found = []
    for key, info in COMPOUND_DB.items():
        if key in low:
            if info not in found:
                found.append(info)
    return found


def detect_phase(program_data, prev_weight=None):
    """Detect training phase based on program characteristics."""
    supps = program_data.get("supplements_raw", [])
    weight = program_data.get("weight")
    carb_info = program_data.get("carb_details", "")
    has_cardio = program_data.get("has_cardio", False)

    supp_text = " ".join(supps).lower()

    has_sarm = any(k in supp_text for k in ['rad 140', 'rad140', 'mk2866', 'ostarine', 'lgd'])
    has_ph = any(k in supp_text for k in ['dmz', 'g-mass'])
    has_gh = any(k in supp_text for k in ['mk-677', 'mk677', 'lx-gh'])
    has_pct = any(k in supp_text for k in ['pct pro', 'test restore', 'alpha male', 'turkester'])
    has_thermo = any(k in supp_text for k in ['ripper', 'animal cuts', 'yohimbine', 'yohimb', 'laser melt'])
    has_liver = 'liver' in supp_text
    has_fat_burner = any(k in supp_text for k in ['carnitin', 'cla', 'acido lipoico'])

    weight_change = None
    if weight and prev_weight:
        weight_change = weight - prev_weight

    # Phase detection logic
    if has_sarm and has_thermo:
        return "cutting_assisted"
    if has_sarm or has_ph:
        if weight_change and weight_change > 2:
            return "bulk_assisted"
        elif has_thermo or has_fat_burner:
            return "cutting_assisted"
        else:
            return "recomp_assisted"
    if has_pct and not has_sarm and not has_ph:
        return "pct_recovery"
    if has_thermo or has_fat_burner:
        if weight_change and weight_change < -1:
            return "cutting_natural"
        return "cutting_natural"
    if has_liver and not has_sarm and not has_ph:
        return "recovery"
    if weight_change and weight_change > 2:
        return "bulking_natural"
    if weight_change and weight_change < -1:
        return "cutting_natural"
    return "maintenance"


PHASE_LABELS = {
    "cutting_assisted": "Cutting (assistito PED)",
    "cutting_natural": "Cutting (naturale)",
    "bulk_assisted": "Bulk (assistito PED)",
    "bulking_natural": "Bulk (naturale)",
    "recomp_assisted": "Ricomposizione (assistita PED)",
    "pct_recovery": "PCT / Recupero ormonale",
    "recovery": "Recupero",
    "maintenance": "Mantenimento",
}


def extract_program_data(dirpath, program_num):
    """Extract all data from a program directory."""
    result = {
        "program_num": program_num,
        "date": None,
        "date_iso": None,
        "weight": None,
        "body_fat_pct": None,
        "fat_mass": None,
        "lean_mass": None,
        "bmi": None,
        "waist": None,
        "objective": None,
        "valid_until": None,
        "supplements_raw": [],
        "supplements_classified": [],
        "nutrition_plan": {},
        "training_summary": {},
        "has_cardio": False,
        "cardio_detail": "",
        "notes": [],
    }

    files = os.listdir(dirpath)
    pdfs = [f for f in files if f.endswith('.pdf')]
    docxs = [f for f in files if f.endswith('.docx')]

    # Separate nutrition vs training PDFs
    nutrition_pdfs = [f for f in pdfs if 'all' not in f.lower() or f.lower().count('all') == 0]
    training_pdfs = [f for f in pdfs if 'all.' in f.lower() or '(all' in f.lower()]

    # If no clear separation, try all PDFs
    if not nutrition_pdfs:
        nutrition_pdfs = pdfs

    # ── Extract from nutrition PDF ─────────────────────────────────────────
    for pdf_name in nutrition_pdfs:
        filepath = os.path.join(dirpath, pdf_name)
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + "\n"

                lines = full_text.split('\n')

                for line in lines:
                    # Date
                    m = re.search(r'DATA\s+(\d{1,2}/\d{1,2}/\d{4})', line)
                    if m and not result["date"]:
                        result["date"] = m.group(1)
                        try:
                            result["date_iso"] = datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
                        except:
                            pass

                    # Weight
                    m = re.search(r'Peso tot\.\s*\(kg\)\s*([\d.,]+)', line)
                    if m:
                        result["weight"] = float(m.group(1).replace(',', '.'))

                    # Body fat
                    # Look for the current measurement - usually on the body comp page
                    m = re.search(r'Peso massa grassa\s*\(kg\)\s*([\d.,]+)', line)
                    if m:
                        result["fat_mass"] = float(m.group(1).replace(',', '.'))

                    m = re.search(r'Peso massa magra\s*\(kg\)\s*([\d.,]+)', line)
                    if m:
                        result["lean_mass"] = float(m.group(1).replace(',', '.'))

                    m = re.search(r'BMI\s+([\d.,]+)', line)
                    if m and not result["bmi"]:
                        try:
                            val = float(m.group(1).replace(',', '.'))
                            if 15 < val < 45:  # sanity check
                                result["bmi"] = val
                        except:
                            pass

                    # Waist
                    m = re.search(r'Vita\s+(\d{2,3})$', line.strip())
                    if m:
                        result["waist"] = int(m.group(1))

                    # Objective
                    m = re.search(r'[Oo]biettivo[:\s]*([\d.,]+)\s*kg', line)
                    if m:
                        result["objective"] = float(m.group(1).replace(',', '.'))

                    m = re.search(r'Prossimo obiettivo[:\s]*([\d.,]+)\s*kg', line)
                    if m:
                        result["objective"] = float(m.group(1).replace(',', '.'))

                    # Valid until
                    m = re.search(r'Fino al\s+(.+?)$', line.strip())
                    if m:
                        result["valid_until"] = m.group(1).strip()

                    # Supplements
                    low = line.lower().strip()
                    is_supp_line = False

                    # Check if line contains known compound names
                    for kw in SUPP_KEYWORDS:
                        if kw in low:
                            # Exclude pure food lines
                            if not any(food in low for food in ['pancake', 'porridge', 'secondo', 'nota secondi',
                                                                  'carne rossa', 'carne bianca', 'pesce magro',
                                                                  'pesce azzurro', 'formaggio', 'ricotta',
                                                                  'seppie', 'gamberi', 'calamari', 'polipo']):
                                is_supp_line = True
                                break

                    # Also check context keywords for supplement protocol lines
                    if not is_supp_line:
                        for ck in SUPP_CONTEXT_KEYWORDS:
                            if ck in low and any(sk in low for sk in SUPP_KEYWORDS):
                                is_supp_line = True
                                break

                    if is_supp_line:
                        clean_line = line.strip()
                        # Skip nutritional plan structure lines
                        if not re.match(r'^(Col\.|Sp\.\s*\d|Pranzo|Cena|GIORNO|LUNEDI|MARTEDI|MERCOLEDI|GIOVEDI|VENERDI|SABATO|DOMENICA)', clean_line):
                            result["supplements_raw"].append(clean_line)
                        elif 'post-all' in low or 'pre-all' in low or 'pre-col' in low:
                            result["supplements_raw"].append(clean_line)

                    # Cardio
                    if any(k in low for k in ['cardio', 'tappeto', 'nuoto', 'glidex', 'camminat']):
                        result["has_cardio"] = True
                        result["cardio_detail"] = line.strip()

                    # Carb info
                    if re.search(r'pasta|riso|avena|fiocchi', low):
                        m_carb = re.search(r'(\d+)\s*g\s*(pasta|riso|avena|fiocchi)', low)
                        if m_carb:
                            if "carb_details" not in result:
                                result["carb_details"] = ""
                            result["carb_details"] += f"{m_carb.group(1)}g {m_carb.group(2)}; "

                # Classify supplements
                seen_names = set()
                for supp_line in result["supplements_raw"]:
                    classifications = classify_compound(supp_line)
                    for c in classifications:
                        if c["name"] not in seen_names:
                            seen_names.add(c["name"])
                            result["supplements_classified"].append({
                                "name": c["name"],
                                "category": c["category"],
                                "risk": c["risk"],
                                "effects": c["effects"],
                                "protocol": supp_line,
                            })

        except Exception as e:
            result["notes"].append(f"Error reading {pdf_name}: {str(e)}")

    # ── Extract from training PDF ──────────────────────────────────────────
    for pdf_name in training_pdfs:
        filepath = os.path.join(dirpath, pdf_name)
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + "\n"

                # Count training days
                days = re.findall(r'^([A-D])\s*$', full_text, re.MULTILINE)
                result["training_summary"]["split_days"] = len(set(days)) if days else None

                # Cardio from training PDF
                low = full_text.lower()
                if any(k in low for k in ['cardio', 'tappeto', 'nuoto', 'glidex']):
                    result["has_cardio"] = True
                    for line in full_text.split('\n'):
                        if any(k in line.lower() for k in ['cardio', 'tappeto', 'nuoto', 'glidex']):
                            result["cardio_detail"] = line.strip()

                # Detect intensity techniques
                techniques = []
                if 'stripping' in low:
                    techniques.append("stripping")
                if 'neg.' in low or 'negativ' in low:
                    techniques.append("negative")
                if 'superserie' in low or 'In rosso' in full_text:
                    techniques.append("superserie")
                if 'parziali' in low:
                    techniques.append("parziali")
                if 'pausa e stretch' in low:
                    techniques.append("rest-pause + stretch")
                result["training_summary"]["intensity_techniques"] = techniques

        except Exception as e:
            result["notes"].append(f"Error reading training {pdf_name}: {str(e)}")

    # Deduplicate supplement lines
    result["supplements_raw"] = list(dict.fromkeys(result["supplements_raw"]))

    return result


def extract_body_comp_history(dirpath):
    """Extract the full historical body composition table from the most recent program."""
    history = []
    files = os.listdir(dirpath)
    pdfs = [f for f in files if f.endswith('.pdf') and 'all' not in f.lower()]
    if not pdfs:
        pdfs = [f for f in files if f.endswith('.pdf')]

    for pdf_name in pdfs:
        filepath = os.path.join(dirpath, pdf_name)
        try:
            with pdfplumber.open(filepath) as pdf:
                full_text = ""
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        full_text += t + "\n"

                lines = full_text.split('\n')
                i = 0
                while i < len(lines):
                    # Look for date rows (7 dates)
                    date_match = re.findall(r'\d{2}/\d{2}/\d{4}', lines[i])
                    if len(date_match) >= 3:
                        dates = date_match
                        # Next lines should be Peso, % grasso, FM, FFM, Vita
                        data_block = {}
                        for j in range(i + 1, min(i + 6, len(lines))):
                            line = lines[j]
                            if line.startswith('Peso ') or line.startswith('Peso\t'):
                                vals = re.findall(r'[\d.]+', line)
                                data_block['peso'] = vals
                            elif '% grasso' in line or '%grasso' in line:
                                vals = re.findall(r'[\d.]+', line)
                                data_block['grasso'] = vals
                            elif line.startswith('FM ') or line.startswith('FM\t'):
                                vals = re.findall(r'[\d.]+', line)
                                data_block['fm'] = vals
                            elif line.startswith('FFM ') or line.startswith('FFM\t'):
                                vals = re.findall(r'[\d.]+', line)
                                data_block['ffm'] = vals
                            elif line.startswith('Vita ') or line.startswith('Vita\t'):
                                vals = re.findall(r'\d+', line)
                                data_block['vita'] = vals

                        for idx, date in enumerate(dates):
                            entry = {"date": date}
                            try:
                                entry["date_iso"] = datetime.strptime(date, "%d/%m/%Y").strftime("%Y-%m-%d")
                            except:
                                pass
                            if 'peso' in data_block and idx < len(data_block['peso']):
                                entry['weight'] = float(data_block['peso'][idx])
                            if 'grasso' in data_block and idx < len(data_block['grasso']):
                                entry['body_fat_pct'] = float(data_block['grasso'][idx])
                            if 'fm' in data_block and idx < len(data_block['fm']):
                                entry['fat_mass'] = float(data_block['fm'][idx])
                            if 'ffm' in data_block and idx < len(data_block['ffm']):
                                entry['lean_mass'] = float(data_block['ffm'][idx])
                            if 'vita' in data_block and idx < len(data_block['vita']):
                                entry['waist'] = int(data_block['vita'][idx])
                            history.append(entry)
                        i += 6
                    else:
                        i += 1
        except:
            pass

    # Deduplicate by date
    seen = set()
    unique = []
    for h in history:
        if h['date'] not in seen:
            seen.add(h['date'])
            unique.append(h)

    # Sort by date
    unique.sort(key=lambda x: x.get('date_iso', ''))
    return unique


def compute_risk_summary(all_programs):
    """Compute overall health risk summary from all programs."""
    risk = {
        "liver": {"level": "low", "score": 0, "compounds": [], "notes": []},
        "hpta": {"level": "low", "score": 0, "compounds": [], "notes": []},
        "cardiovascular": {"level": "low", "score": 0, "compounds": [], "notes": []},
        "kidney": {"level": "low", "score": 0, "compounds": [], "notes": []},
        "cancer": {"level": "low", "score": 0, "compounds": [], "notes": []},
    }

    sarm_cycles = 0
    ph_cycles = 0
    last_ped_date = None
    last_pct_date = None
    liver_support_present = {}  # program_num -> bool

    for prog in all_programs:
        has_liver_support = False
        has_ped = False

        for supp in prog.get("supplements_classified", []):
            cat = supp["category"]
            name = supp["name"]

            if cat == "SARM":
                risk["hpta"]["score"] += 3
                risk["liver"]["score"] += 2
                risk["cardiovascular"]["score"] += 2
                sarm_cycles += 1
                has_ped = True
                if name not in risk["hpta"]["compounds"]:
                    risk["hpta"]["compounds"].append(name)
                if name not in risk["cardiovascular"]["compounds"]:
                    risk["cardiovascular"]["compounds"].append(name)

            elif cat == "pro_hormone":
                risk["liver"]["score"] += 4
                risk["hpta"]["score"] += 4
                risk["cardiovascular"]["score"] += 3
                risk["kidney"]["score"] += 1
                ph_cycles += 1
                has_ped = True
                if name not in risk["liver"]["compounds"]:
                    risk["liver"]["compounds"].append(name)
                if name not in risk["hpta"]["compounds"]:
                    risk["hpta"]["compounds"].append(name)

            elif cat == "PPAR_delta_agonist":
                risk["cancer"]["score"] += 5
                if name not in risk["cancer"]["compounds"]:
                    risk["cancer"]["compounds"].append(name)

            elif cat == "GH_secretagogue" or cat == "GH_booster":
                risk["cardiovascular"]["score"] += 1
                has_ped = True

            elif cat == "thermogenic" or cat == "fat_burner":
                risk["cardiovascular"]["score"] += 1
                if "yohimbine" in name.lower():
                    risk["cardiovascular"]["score"] += 1
                    if name not in risk["cardiovascular"]["compounds"]:
                        risk["cardiovascular"]["compounds"].append(name)

            elif cat == "liver_support":
                has_liver_support = True

            elif cat == "PCT":
                if prog.get("date_iso"):
                    last_pct_date = prog["date_iso"]

        if has_ped and prog.get("date_iso"):
            last_ped_date = prog["date_iso"]

        liver_support_present[prog["program_num"]] = has_liver_support

    # Assess risk levels
    for key in risk:
        score = risk[key]["score"]
        if score >= 8:
            risk[key]["level"] = "very_high"
        elif score >= 5:
            risk[key]["level"] = "high"
        elif score >= 3:
            risk[key]["level"] = "medium"
        elif score >= 1:
            risk[key]["level"] = "low-medium"

    # Add specific notes
    if last_ped_date and last_pct_date:
        if last_pct_date > last_ped_date:
            risk["hpta"]["notes"].append(
                f"PCT ({last_pct_date}) used after last PED cycle ({last_ped_date}) — may indicate ongoing recovery issues")

    risk["summary"] = {
        "total_sarm_cycles": sarm_cycles,
        "total_ph_cycles": ph_cycles,
        "last_ped_date": last_ped_date,
        "last_pct_date": last_pct_date,
    }

    return risk


def main():
    parser = argparse.ArgumentParser(description="Extract nutritional program data from PDFs")
    parser.add_argument("base_dir", help="Base directory containing #XX_programmi folders")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file path")
    parser.add_argument("--range", nargs=2, type=int, default=None, help="Program range (start end)")
    parser.add_argument("--history", action="store_true", help="Also extract full body comp history from latest program")
    args = parser.parse_args()

    base_dir = args.base_dir

    # Find all program directories
    dirs = []
    for d in os.listdir(base_dir):
        m = re.match(r'#(\d+)_programm', d)
        if m:
            num = int(m.group(1))
            if args.range:
                if num < args.range[0] or num > args.range[1]:
                    continue
            dirs.append((num, os.path.join(base_dir, d)))

    dirs.sort(key=lambda x: x[0])

    print(f"Found {len(dirs)} program directories", file=sys.stderr)

    all_programs = []
    prev_weight = None

    for num, dirpath in dirs:
        print(f"  Processing #{num}...", file=sys.stderr)
        prog = extract_program_data(dirpath, num)

        # Detect phase
        prog["phase"] = detect_phase(prog, prev_weight)
        prog["phase_label"] = PHASE_LABELS.get(prog["phase"], prog["phase"])

        if prog["weight"]:
            if prev_weight:
                prog["weight_change"] = round(prog["weight"] - prev_weight, 1)
            prev_weight = prog["weight"]

        all_programs.append(prog)

    # Compute risk summary
    risk_summary = compute_risk_summary(all_programs)

    # Extract full body composition history if requested
    body_comp_history = []
    if args.history and dirs:
        latest_dir = dirs[-1][1]
        body_comp_history = extract_body_comp_history(latest_dir)
        print(f"  Extracted {len(body_comp_history)} historical data points", file=sys.stderr)

    output = {
        "extraction_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_programs": len(all_programs),
        "date_range": {
            "first": all_programs[0]["date"] if all_programs else None,
            "last": all_programs[-1]["date"] if all_programs else None,
        },
        "programs": all_programs,
        "risk_summary": risk_summary,
        "body_comp_history": body_comp_history,
    }

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"Output saved to {args.output}", file=sys.stderr)
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
