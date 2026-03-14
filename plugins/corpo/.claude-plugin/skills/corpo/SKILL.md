---
name: corpo
description: >
  Analyze nutritional and training program PDFs to extract body composition data (weight, fat mass, lean mass, BMI),
  supplement/compound history, and training plans. Use this skill whenever the user asks about their nutrition programs,
  supplement history, weight trends, body composition analysis, training program comparisons, health risk assessment
  from supplement use, or wants predictions and recommendations based on their program history. Trigger on mentions of:
  programmi, programma, nutrizionista, integratori, supplementi, peso, massa grassa, massa magra, composizione corporea,
  cutting, bulking, SARM, PCT, pro-ormone, ciclo, allenamento, dieta, piano alimentare, calorie, kcal, macros,
  proteine, carboidrati, grassi, macronutrienti, deficit calorico, surplus, or any reference to numbered
  programs (#XX). Also trigger when the user uploads or references PDF files containing nutritional/training data,
  or asks for health risk analysis related to performance-enhancing compounds.
---

# Nutritional Program Analyzer

This skill extracts and analyzes data from a structured set of nutritional/training program PDFs organized in numbered directories (e.g., `#53_programmi/`). Each directory typically contains a nutrition PDF and a training PDF (marked "all." for "allenamento").

## Prerequisites

This skill requires the following Python packages (install via pip if not already present):

```bash
pip install pdfplumber python-docx
```

## What This Skill Does

1. **Data Extraction** — Parses all program PDFs to extract:
   - Program date, body weight, body fat %, lean mass, fat mass, BMI
   - Waist circumference and other measurements
   - Supplement/compound protocols with dosages and timing
   - Nutritional plan structure (meals, macros, portions)
   - **Daily kcal and macronutrient estimates** (protein, carbs, fats) from the diet plan
   - Training plan details (exercises, sets, reps, rest, cardio)
   - Program objectives

2. **Timeline Analysis** — Builds a chronological view of:
   - Weight and body composition trends over time
   - Supplement cycling patterns (SARMs, pro-hormones, PCT, thermogenics, base supplements)
   - Cutting vs bulking phases identification
   - Rate of weight change per phase

3. **Health Risk Assessment** — Evaluates potential health concerns based on:
   - Types of compounds used and their known risk profiles
   - Duration and frequency of cycles
   - Presence/absence of liver support and PCT
   - Cumulative load on liver, HPTA axis, cardiovascular system, kidneys

4. **Calorie & Macro Tracking** — Calculates daily nutritional intake from each program's diet plan:
   - Parses meal plans (colazione, spuntini, pranzo, cena, post-workout) with portion sizes in grams
   - Uses a built-in Italian food database (~40 foods covering meats, fish, grains, dairy, supplements)
   - Calculates per-meal and daily totals for kcal, protein (g), carbs (g), fat (g)
   - Differentiates between **training days** (with carbs at lunch + post-workout shake) and **rest days** (no carbs, different snack)
   - Computes **weekly average** (4 training + 3 rest days)
   - Tracks **protein per kg bodyweight** across programs
   - Handles the weekly protein rotation table ("NOTA SECONDI") by averaging across 7 days
   - Provides a macro timeline showing how caloric intake changed across all programs

5. **Current Status Summary** — Always include when analyzing data:
   - Current program number, date, weight, objective
   - Active supplements with risk classification
   - Current training split and cardio protocol
   - How current phase compares to historical patterns
   - Whether liver support or PCT is missing vs what was used in similar past cycles

6. **Post-Program Recommendations** — After analyzing the current program, always provide a "what to do next" section:
   - Based on the current program's compounds, predict what PCT/recovery protocol will be needed
   - Reference historical post-cycle patterns (e.g., after RAD 140 #53, the user did Test Restore + Turkesterone in #54)
   - Estimate a realistic weight target for the end of the current program based on historical rate of change
   - Suggest the next phase (cutting/maintenance/recovery) with specific supplement and nutrition recommendations
   - Flag if the user should get bloodwork done before starting the next phase
   - If PED compounds are being used, always recommend a minimum recovery window before any new cycle, based on the "time on = time off" principle
   - Prioritize natural approaches that historically gave the best results (the #39→#44 cutting phase achieved 7.3% body fat with zero PED)

7. **Persistent Memory & Next Steps** — Maintains a `nutrizionista_memory.json` file in the programs root directory:
   - Tracks **next steps** (blood tests to do, supplements to add, appointments) with priority and source
   - Stores **nutritionist recommendations** (e.g., Musolino's advice) with action items
   - Records **bloodwork history** when results come in
   - Logs **decisions** (starting/stopping supplements, changing diet) with reasoning
   - Persists between sessions — always read memory at the start and update it at the end
   - Categories: analisi, supplementi, alimentazione, allenamento, visita, generale
   - Each step has: id, description, category, priority (alta/media/bassa), source, due_date, details

8. **General Recommendations** — Provides evidence-based suggestions for:
   - Supplement protocols based on historical patterns that worked
   - Nutritional adjustments for cutting/bulking goals
   - Medical tests to monitor based on compound history
   - Safer alternatives based on what achieved the best results historically

## How to Use

**Important:** In all commands below, replace `<skill-dir>` with the absolute path to this skill's directory (the folder containing this SKILL.md file). For Goose, this is typically:
- `~/.config/goose/skills/nutrizionista-analyzer/` (global install)
- `./.goose/skills/nutrizionista-analyzer/` (project-level install)

### Step 1: Extract Data

Run the extraction script on the program directory:

```bash
python3 <skill-dir>/scripts/extract_programs.py <programs-base-directory> --output <output-json-path>
```

This produces a structured JSON file with all extracted data. The script handles both PDF and DOCX files, and automatically identifies nutrition vs training PDFs.

### Step 2: Enrich with Macro/Calorie Data

Run the macro calculator to add daily kcal and macronutrient estimates to the extracted data:

```bash
python3 <skill-dir>/scripts/calc_macros.py --programs-json <output-json-path> --pdf-dir <programs-base-directory> --output <enriched-json-path>
```

This parses the diet plans from each PDF and calculates:
- Training day vs rest day macros (kcal, protein, carbs, fats)
- Weekly average intake
- Protein per kg bodyweight
- Per-meal breakdown (colazione, spuntini, pranzo, cena, post-workout)
- A macro_timeline array for easy charting

The calculator uses a built-in Italian food database and handles the weekly protein rotation table ("NOTA SECONDI") that appears in most programs.

### Step 3: Analyze the Data

Once you have the enriched JSON, you can:

- **View full timeline**: Read the JSON and present chronological weight + macro data
- **Compare periods**: Filter by date range or program numbers
- **Identify phases**: The script tags each program with detected phase (cutting/bulking/maintenance)
- **Risk analysis**: Cross-reference compound history with known risk profiles
- **Caloric analysis**: Compare kcal intake across cutting vs bulking phases, track protein/kg trends

### Step 4: Generate Reports

Run the report generator to create an HTML report with Chart.js charts:

```bash
python3 <skill-dir>/scripts/generate_report.py --programs-json <enriched-json-path> --output <report-html-path>
```

Or answer specific user questions about their history directly from the enriched JSON.

### Step 5: Read & Update Memory

Always start by reading the persistent memory file to understand the current state:

```bash
python3 <skill-dir>/scripts/memory.py <programs-base-directory> --summary
```

After any analysis or when the user provides new information, update the memory:

```bash
# Add a next step
python3 <skill-dir>/scripts/memory.py <programs-base-directory> --add-step "Description" --category "analisi" --priority "alta" --source "Musolino"

# Mark a step as completed
python3 <skill-dir>/scripts/memory.py <programs-base-directory> --complete-step <step_id> --outcome "Risultati nella norma"

# Add a note
python3 <skill-dir>/scripts/memory.py <programs-base-directory> --add-note "Note text" --source "Musolino"
```

The memory file (`nutrizionista_memory.json`) is stored in the programs root directory and persists between sessions. It tracks:
- Pending next steps (blood tests, supplement changes, appointments)
- Nutritionist recommendations with action items
- Bloodwork history and results
- Decision log with reasoning

**Important**: When the user mentions new information from their nutritionist (e.g., "Musolino mi ha detto di fare X"), always add it to the memory as a next step or recommendation. When the user reports completing a step (e.g., "ho fatto le analisi"), mark it as completed and record the outcome.

You can also use the memory module programmatically in Python:

```python
from memory import load_memory, save_memory, add_next_step, complete_step, add_note
memory = load_memory("<programs-root>")
# ... modify memory ...
save_memory("<programs-root>", memory)
```

### Step 6: Current Status & Post-Program Plan

After extraction, always analyze the **latest program** (highest number) to provide:

1. **Current status snapshot** — summarize what the user is currently doing: compounds, training, nutrition, phase, and how it compares to similar past programs
2. **End-of-program prediction** — based on the current phase and historical rate of change, estimate where weight and body composition will be when the current program ends (use the `valid_until` field)
3. **Post-program action plan** — what specific steps to take after the current program finishes:

**If current program includes PED compounds (SARMs, PH):**
- Recommend specific PCT protocol based on what worked after similar past cycles
- Recommend liver support duration
- Specify minimum recovery window (at least equal to cycle length)
- List bloodwork to get 4-6 weeks post-cycle
- Suggest transition nutrition plan (maintain protein, gradually adjust carbs)

**If current program is natural/PCT:**
- Assess if recovery is complete (check if PCT products are still being used long after last cycle)
- Recommend next cutting or maintenance phase
- Suggest supplements from the "safe" category that historically correlated with best results

**Historical pattern reference for post-cycle recommendations:**
- After RAD 140 (#53 → #54): Test Restore AM + Turkesterone + MK-677 + Laser Melt
- After DMZ (#58 → #59): Veno Test + Ripper + Liver
- After DMZ (#60 → #61-62): Liver only, then Animal Cuts for cutting
- After latest cycle, always compare with these patterns and suggest the best approach

## Compound Classification Reference

When analyzing supplements, classify them into these categories:

| Category | Examples | Risk Level |
|----------|----------|------------|
| SARM | RAD 140, MK-2866 (Ostarine), LGD-4033 | High |
| GH Secretagogue | MK-677 (Ibutamoren) | Medium-High |
| PPAR-delta agonist | GW501516 (Cardarine) | High (cancer risk in animal studies) |
| Pro-Hormone | DMZ, G-Mass, LX-GH PRO, Veno Test | High (especially 17α-alkylated) |
| PCT | Test Restore AM, PCT PRO, Alpha Male, Turkesterone | Low-Medium |
| Liver Support | Liver (Revange), TUDCA, NAC | Low (protective) |
| Thermogenic | Ripper (Skull Labs), Laser Melt, Animal Cuts | Medium |
| Fat Burner | Yohimbine HCL, CLA, Acetilcarnitina, Acido Lipoico | Low-Medium |
| Base | Creatina, Glutammina, BCAA, Whey, Omega 3, Probiotici | Very Low |
| Pre-Workout | EuphoriQ, C4, Flexotor, Black Focus, Acid Melt | Low-Medium |

## Key Health Monitoring Areas

Based on compound use, always recommend monitoring:

1. **Liver** (ALT, AST, GGT, bilirubina) — especially after 17α-alkylated compounds (DMZ)
2. **Hormonal axis** (Testosterone, LH, FSH, Estradiol, SHBG) — after any SARM or PH cycle
3. **Lipids** (HDL, LDL, Triglycerides, hs-CRP) — SARMs and PH dramatically lower HDL
4. **Kidney** (Creatinine, BUN, eGFR) — general monitoring
5. **Cardiovascular** (Blood pressure, ECG) — especially with stimulant use (Yohimbine + Ripper)
6. **Blood count** (CBC) — erythrocytosis risk from androgens

## Phase Detection Logic

Identify training phases based on these patterns from historical data:

- **Cutting**: Weight decreasing, reduced carbs (pasta 80g or less, avena reduced), no carbs at dinner, increased cardio, thermogenics/fat burners present
- **Bulking**: Weight increasing, higher carbs, presence of anabolic compounds (SARMs, PH), mass gainers
- **PCT/Recovery**: Post-cycle therapy products, liver support, weight may fluctuate
- **Maintenance**: Stable weight, base supplements only, moderate carbs

## Important Notes

- Always include a medical disclaimer — this analysis is informational, not medical advice
- Flag when PCT is used long after the last cycle (may indicate incomplete HPTA recovery)
- Compare lean mass across time to assess whether compounds actually added contractile tissue vs water/fat
- When making cutting recommendations, prioritize approaches that historically yielded the best body composition (lowest % fat with preserved lean mass)
