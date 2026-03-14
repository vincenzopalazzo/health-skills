#!/usr/bin/env python3
"""
Generate an interactive HTML report from extracted program data.
Usage: python3 generate_report.py <programs_data.json> --output <report.html>
"""

import argparse
import json
import sys


def generate_html(data, output_path):
    programs = data['programs']
    risk = data['risk_summary']
    history = data.get('body_comp_history', [])

    macro_timeline = data.get('macro_timeline', [])

    # Build chart data - only programs with weight
    weight_labels = []
    weight_data = []
    weight_colors = []
    for p in programs:
        if p.get('weight') and p.get('date'):
            label = f"#{p['program_num']} ({p['date'][:5]})"
            weight_labels.append(label)
            weight_data.append(p['weight'])
            # Color by phase
            phase = p.get('phase', '')
            if 'assisted' in phase:
                weight_colors.append('#f43f5e')
            elif 'pct' in phase or 'recovery' in phase:
                weight_colors.append('#a78bfa')
            elif 'cutting' in phase:
                weight_colors.append('#22d3ee')
            elif 'bulk' in phase:
                weight_colors.append('#f59e0b')
            else:
                weight_colors.append('#667eea')

    # Body comp data
    bc_labels = []
    bc_fm = []
    bc_ffm = []
    for p in programs:
        if p.get('fat_mass') and p.get('lean_mass') and p.get('fat_mass') < 20 and p.get('lean_mass') > 50:
            bc_labels.append(f"#{p['program_num']} ({p['date'][:5]})")
            bc_fm.append(p['fat_mass'])
            bc_ffm.append(p['lean_mass'])

    # Macro chart data
    macro_labels = []
    macro_kcal = []
    macro_protein = []
    macro_carbs = []
    macro_fat = []
    macro_ppkg = []
    for mt in macro_timeline:
        if mt.get('daily_kcal_avg') and mt['daily_kcal_avg'] > 800:  # filter out incomplete extractions
            label = f"#{mt['program_num']} ({mt.get('date', '?')[:5]})"
            macro_labels.append(label)
            macro_kcal.append(round(mt['daily_kcal_avg']))
            macro_protein.append(round(mt.get('protein_g', 0)))
            macro_carbs.append(round(mt.get('carbs_g', 0)))
            macro_fat.append(round(mt.get('fat_g', 0)))
            macro_ppkg.append(mt.get('protein_per_kg', 0))

    # Current program macro summary for the highlight box
    current_macros = None
    for mt in reversed(macro_timeline):
        if mt.get('daily_kcal_avg') and mt['daily_kcal_avg'] > 800:
            current_macros = mt
            break

    # Timeline items
    timeline_html = ""
    for p in programs:
        if not p.get('date'):
            continue

        supps = p.get('supplements_classified', [])
        if not supps and not p.get('weight'):
            continue

        # Determine danger level
        max_risk = 'safe'
        for s in supps:
            r = s['risk']
            if r in ('very_high', 'high'):
                max_risk = 'danger'
                break
            elif r in ('medium-high', 'medium'):
                if max_risk != 'danger':
                    max_risk = 'warning'

        wc = p.get('weight_change')
        wc_str = f" ({wc:+.1f} kg)" if wc is not None else ""
        weight_str = f"{p['weight']:.1f} kg" if p.get('weight') else "? kg"
        obj_str = f" → obiettivo {p['objective']:.0f} kg" if p.get('objective') else ""

        supp_tags = ""
        for s in supps:
            cat = s['category']
            tag_class = {
                'SARM': 'tag-sarm', 'pro_hormone': 'tag-ph', 'GH_secretagogue': 'tag-ph',
                'GH_booster': 'tag-ph', 'PPAR_delta_agonist': 'tag-sarm',
                'PCT': 'tag-pct', 'ecdysteroid': 'tag-pct',
                'liver_support': 'tag-liver', 'thermogenic': 'tag-thermo',
                'fat_burner': 'tag-thermo', 'base': 'tag-base', 'probiotic': 'tag-base',
                'testosterone_booster': 'tag-ph',
            }.get(cat, 'tag-base')
            supp_tags += f'<span class="supp-tag {tag_class}">{s["name"]}</span>\n'

        if not supp_tags:
            supp_tags = '<span class="supp-tag tag-base">Solo base (Whey)</span>'

        cardio_str = ""
        if p.get('has_cardio'):
            cardio_str = f'<div class="cardio-note">Cardio: {p.get("cardio_detail", "Si")}</div>'

        training_str = ""
        ts = p.get('training_summary', {})
        if ts.get('intensity_techniques'):
            training_str = f'<div class="training-note">Tecniche: {", ".join(ts["intensity_techniques"])}</div>'

        timeline_html += f'''
        <div class="timeline-item {max_risk}">
          <div class="date">#{p['program_num']} — {p['date']} — {weight_str}{wc_str}{obj_str}</div>
          <div class="phase-tag">{p.get('phase_label', '?')}</div>
          <div class="supp-list">{supp_tags}</div>
          {cardio_str}
          {training_str}
        </div>'''

    # Risk cards
    risk_html = ""
    risk_order = ['liver', 'hpta', 'cardiovascular', 'cancer', 'kidney']
    risk_titles = {
        'liver': 'Fegato (Epatotossicità)',
        'hpta': 'Asse Ormonale (HPTA)',
        'cardiovascular': 'Sistema Cardiovascolare',
        'cancer': 'Rischio Cancerogenicità (GW501516)',
        'kidney': 'Reni',
    }
    risk_descriptions = {
        'liver': 'Il DMZ (Dymethazine) è un composto 17α-alchilato con severa epatotossicità. Usato in 2 cicli (#58, #60). RAD 140 aggiunge ulteriore stress epatico. Il Liver (Revange) presente in molti programmi offre protezione parziale, ma non nel #72 attuale.',
        'hpta': 'Cicli ripetuti di SARMs (Ostarine, RAD 140 x2) e pro-ormoni (DMZ x2, G-Mass) dal 2022 al 2026 hanno causato soppressione ripetuta dell\'asse ipotalamo-ipofisi-gonadi. Il PCT PRO usato nel #71 (Nov 2025) e il ritorno al RAD 140 nel #72 (Gen 2026) a soli 2 mesi di distanza indica cicli molto ravvicinati senza recupero completo.',
        'cardiovascular': 'Score molto alto dovuto all\'accumulo di: SARMs (abbattono HDL), pro-ormoni, termogenici stimolanti (Ripper), e ora Yohimbine HCL nel #72. La combinazione RAD 140 + Yohimbine + cardio intenso nel programma attuale è particolarmente stressante per il sistema cardiovascolare.',
        'cancer': 'Il GW501516 (Cardarine) usato nel #49 è stato abbandonato dalla ricerca per sviluppo di tumori in studi animali. Un singolo ciclo breve limita il rischio, ma rimane un fattore da monitorare.',
        'kidney': 'Rischio contenuto. Monitorare creatinina e eGFR come precauzione generale dato l\'uso prolungato di composti.',
    }

    for key in risk_order:
        r = risk[key]
        level = r['level']
        css_class = 'risk-high' if level in ('very_high', 'high') else ('risk-medium' if level in ('medium', 'medium-high', 'low-medium') else 'risk-low')
        compounds = ', '.join(r['compounds']) if r['compounds'] else 'N/A'
        notes = '<br>'.join(r.get('notes', []))

        risk_html += f'''
        <div class="risk-card {css_class}">
          <div class="risk-label">{level.replace('_', ' ').upper()} — {risk_titles[key]}</div>
          <p><strong>Score:</strong> {r["score"]} | <strong>Composti coinvolti:</strong> {compounds}</p>
          <p style="margin-top:8px">{risk_descriptions[key]}</p>
          {"<p style='margin-top:8px;color:#fbbf24'>" + notes + "</p>" if notes else ""}
        </div>'''

    # Summary stats
    summary = risk['summary']
    current = programs[-2] if programs[-1]['program_num'] == 404 else programs[-1]  # skip #404
    # Find actual last program
    for p in reversed(programs):
        if p.get('date') and p['program_num'] != 404:
            current = p
            break

    html = f'''<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Analisi Completa Programmi - Palazzo Vincenzo</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0f1117; color: #e0e0e0; line-height: 1.6; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
  h1 {{ text-align: center; font-size: 2em; margin: 30px 0 10px; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  h2 {{ color: #667eea; margin: 30px 0 15px; font-size: 1.4em; border-bottom: 2px solid #667eea33; padding-bottom: 8px; }}
  .card {{ background: #1a1d2e; border-radius: 12px; padding: 24px; margin: 20px 0; border: 1px solid #2a2d3e; }}
  .chart-container {{ position: relative; height: 400px; margin: 20px 0; }}
  .timeline {{ position: relative; padding-left: 30px; }}
  .timeline::before {{ content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 3px; background: linear-gradient(to bottom, #667eea, #764ba2, #f43f5e); border-radius: 2px; }}
  .timeline-item {{ position: relative; margin-bottom: 14px; padding: 12px 16px; background: #1e2235; border-radius: 8px; border-left: 3px solid #667eea; }}
  .timeline-item.danger {{ border-left-color: #f43f5e; }}
  .timeline-item.warning {{ border-left-color: #f59e0b; }}
  .timeline-item.safe {{ border-left-color: #10b981; }}
  .timeline-item::before {{ content: ''; position: absolute; left: -27px; top: 16px; width: 12px; height: 12px; border-radius: 50%; background: #667eea; border: 2px solid #0f1117; }}
  .timeline-item.danger::before {{ background: #f43f5e; }}
  .timeline-item.warning::before {{ background: #f59e0b; }}
  .timeline-item.safe::before {{ background: #10b981; }}
  .date {{ font-size: 0.9em; color: #e0e0e0; font-weight: 600; }}
  .phase-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75em; background: #2a2d3e; color: #8b8fa3; margin: 4px 0; }}
  .supp-list {{ margin-top: 4px; }}
  .supp-tag {{ display: inline-block; padding: 2px 10px; margin: 3px 4px 3px 0; border-radius: 20px; font-size: 0.8em; font-weight: 500; }}
  .tag-sarm {{ background: #f43f5e22; color: #f87171; border: 1px solid #f43f5e44; }}
  .tag-ph {{ background: #f59e0b22; color: #fbbf24; border: 1px solid #f59e0b44; }}
  .tag-pct {{ background: #8b5cf622; color: #a78bfa; border: 1px solid #8b5cf644; }}
  .tag-liver {{ background: #06b6d422; color: #22d3ee; border: 1px solid #06b6d444; }}
  .tag-thermo {{ background: #f9731622; color: #fb923c; border: 1px solid #f9731644; }}
  .tag-base {{ background: #10b98122; color: #34d399; border: 1px solid #10b98144; }}
  .risk-card {{ padding: 16px; margin: 10px 0; border-radius: 8px; }}
  .risk-high {{ background: #f43f5e15; border: 1px solid #f43f5e33; }}
  .risk-medium {{ background: #f59e0b15; border: 1px solid #f59e0b33; }}
  .risk-low {{ background: #10b98115; border: 1px solid #10b98133; }}
  .risk-label {{ font-weight: 700; text-transform: uppercase; font-size: 0.8em; letter-spacing: 1px; margin-bottom: 6px; }}
  .risk-high .risk-label {{ color: #f87171; }}
  .risk-medium .risk-label {{ color: #fbbf24; }}
  .risk-low .risk-label {{ color: #34d399; }}
  .stat-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }}
  .stat-box {{ background: #1e2235; border-radius: 10px; padding: 18px; text-align: center; }}
  .stat-value {{ font-size: 1.8em; font-weight: 700; background: linear-gradient(135deg, #667eea, #764ba2); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
  .stat-label {{ font-size: 0.85em; color: #8b8fa3; margin-top: 4px; }}
  .cardio-note, .training-note {{ font-size: 0.8em; color: #8b8fa3; margin-top: 4px; font-style: italic; }}
  .disclaimer {{ background: #f59e0b11; border: 1px solid #f59e0b33; border-radius: 8px; padding: 16px; margin: 30px 0; font-size: 0.85em; color: #fbbf24; }}
  table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
  th {{ background: #1e2235; color: #a78bfa; padding: 10px 12px; text-align: left; font-size: 0.85em; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #2a2d3e; font-size: 0.9em; }}
  .legend-row {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; justify-content: center; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 0.8em; }}
  .legend-dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .subtitle {{ text-align: center; color: #8b8fa3; margin-bottom: 30px; }}
  .current-highlight {{ background: #667eea22; border: 1px solid #667eea44; border-radius: 8px; padding: 16px; margin: 15px 0; }}
</style>
</head>
<body>
<div class="container">

<h1>Analisi Completa Programmi Nutrizionali</h1>
<p class="subtitle">Palazzo Vincenzo — {data['total_programs']} programmi analizzati — Generato dallo script di estrazione automatica</p>

<div class="disclaimer">
  <strong>Nota importante:</strong> Questa analisi si basa esclusivamente sui dati estratti dai programmi nutrizionali. Non sono un medico. Le considerazioni sulle problematiche future hanno scopo puramente informativo. Consulta sempre un medico o endocrinologo per valutazioni cliniche.
</div>

<div class="current-highlight">
  <strong>Programma attuale: #{current['program_num']}</strong> — Data: {current.get('date', '?')} — Peso: {current.get('weight', '?')} kg — Obiettivo: {current.get('objective', '?')} kg<br>
  <strong>Integratori in corso:</strong> {', '.join(s['name'] for s in current.get('supplements_classified', [])) or 'Nessuno specifico'}<br>
  <strong>Fase:</strong> {current.get('phase_label', '?')}
  {f'<br><strong>Calorie medie:</strong> {current_macros["daily_kcal_avg"]:.0f} kcal/giorno — Proteine: {current_macros["protein_g"]:.0f}g ({current_macros.get("protein_per_kg", 0):.2f} g/kg) — Carbs: {current_macros["carbs_g"]:.0f}g — Grassi: {current_macros["fat_g"]:.0f}g' if current_macros else ''}
</div>

<div class="stat-grid">
  <div class="stat-box">
    <div class="stat-value">{current.get('weight', '?')}</div>
    <div class="stat-label">Peso attuale (kg)</div>
  </div>
  <div class="stat-box">
    <div class="stat-value">{summary['total_sarm_cycles']}</div>
    <div class="stat-label">Cicli SARM totali</div>
  </div>
  <div class="stat-box">
    <div class="stat-value">{summary['total_ph_cycles']}</div>
    <div class="stat-label">Cicli Pro-Ormone</div>
  </div>
  <div class="stat-box">
    <div class="stat-value">84.0</div>
    <div class="stat-label">Peso max (Mar 2024)</div>
  </div>
  <div class="stat-box">
    <div class="stat-value">67.4</div>
    <div class="stat-label">Peso min (Nov 2021)</div>
  </div>
</div>

<div class="card">
  <h2>Andamento Peso</h2>
  <div class="legend-row">
    <div class="legend-item"><div class="legend-dot" style="background:#f43f5e"></div> PED-assistito</div>
    <div class="legend-item"><div class="legend-dot" style="background:#a78bfa"></div> PCT/Recupero</div>
    <div class="legend-item"><div class="legend-dot" style="background:#22d3ee"></div> Cutting naturale</div>
    <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div> Bulk naturale</div>
    <div class="legend-item"><div class="legend-dot" style="background:#667eea"></div> Mantenimento</div>
  </div>
  <div class="chart-container">
    <canvas id="weightChart"></canvas>
  </div>
</div>

<div class="card">
  <h2>Composizione Corporea</h2>
  <div class="chart-container">
    <canvas id="bodyCompChart"></canvas>
  </div>
</div>

{"" if not macro_labels else f"""<div class="card">
  <h2>Calorie e Macronutrienti nel Tempo</h2>
  <div class="chart-container">
    <canvas id="macroChart"></canvas>
  </div>
  <div class="chart-container" style="height:300px;margin-top:20px">
    <canvas id="proteinKgChart"></canvas>
  </div>
</div>"""}

<div class="card">
  <h2>Timeline Completa Programmi e Integratori</h2>
  <div class="legend-row">
    <div class="legend-item"><div class="legend-dot" style="background:#f87171"></div> SARM/PED</div>
    <div class="legend-item"><div class="legend-dot" style="background:#fbbf24"></div> Pro-Ormone/GH</div>
    <div class="legend-item"><div class="legend-dot" style="background:#a78bfa"></div> PCT</div>
    <div class="legend-item"><div class="legend-dot" style="background:#22d3ee"></div> Supporto Epatico</div>
    <div class="legend-item"><div class="legend-dot" style="background:#fb923c"></div> Termogenico</div>
    <div class="legend-item"><div class="legend-dot" style="background:#34d399"></div> Base</div>
  </div>
  <div class="timeline">
    {timeline_html}
  </div>
</div>

<div class="card">
  <h2>Analisi Rischi per la Salute</h2>
  {risk_html}
</div>

<div class="card">
  <h2>Esami Consigliati</h2>
  <table>
    <thead><tr><th>Esame</th><th>Cosa Valuta</th><th>Urgenza</th></tr></thead>
    <tbody>
      <tr><td>Pannello epatico (ALT, AST, GGT, bilirubina, albumina)</td><td>Danni da DMZ e SARMs</td><td style="color:#f87171">Alta</td></tr>
      <tr><td>Testosterone totale + libero, LH, FSH</td><td>Recupero HPTA</td><td style="color:#f87171">Alta</td></tr>
      <tr><td>Estradiolo, SHBG, Prolattina</td><td>Equilibrio ormonale</td><td style="color:#f87171">Alta</td></tr>
      <tr><td>Profilo lipidico completo</td><td>Impatto cardiovascolare RAD+Yohimbine</td><td style="color:#f87171">Alta</td></tr>
      <tr><td>hs-CRP, Omocisteina</td><td>Infiammazione e rischio CV</td><td style="color:#fbbf24">Media</td></tr>
      <tr><td>Creatinina, BUN, eGFR</td><td>Funzionalità renale</td><td style="color:#fbbf24">Media</td></tr>
      <tr><td>Emocromo completo</td><td>Eritrocitosi da SARMs</td><td style="color:#fbbf24">Media</td></tr>
      <tr><td>Glicemia a digiuno + HbA1c</td><td>Impatto MK-677 su insulina</td><td style="color:#fbbf24">Media</td></tr>
      <tr><td>Ecografia epatica</td><td>Steatosi/danni strutturali</td><td style="color:#fbbf24">Media</td></tr>
      <tr><td>ECG a riposo + sotto sforzo</td><td>Aritmie da stimolanti+PED</td><td style="color:#34d399">Preventiva</td></tr>
      <tr><td>Ecocardiogramma</td><td>Ipertrofia ventricolare</td><td style="color:#34d399">Preventiva</td></tr>
      <tr><td>Spessore intima-media carotideo</td><td>Aterosclerosi precoce</td><td style="color:#34d399">Preventiva</td></tr>
    </tbody>
  </table>
</div>

</div>

<script>
const wCtx = document.getElementById('weightChart').getContext('2d');
new Chart(wCtx, {{
  type: 'line',
  data: {{
    labels: {json.dumps(weight_labels)},
    datasets: [{{
      label: 'Peso (kg)',
      data: {json.dumps(weight_data)},
      borderColor: '#667eea',
      backgroundColor: '#667eea22',
      fill: true,
      tension: 0.3,
      pointRadius: 5,
      pointBackgroundColor: {json.dumps(weight_colors)},
      spanGaps: true
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }},
    scales: {{
      x: {{ ticks: {{ color: '#8b8fa3', maxRotation: 60, font: {{ size: 10 }} }}, grid: {{ color: '#2a2d3e' }} }},
      y: {{ min: 64, max: 88, ticks: {{ color: '#8b8fa3' }}, grid: {{ color: '#2a2d3e' }} }}
    }}
  }}
}});

const bcCtx = document.getElementById('bodyCompChart').getContext('2d');
new Chart(bcCtx, {{
  type: 'bar',
  data: {{
    labels: {json.dumps(bc_labels)},
    datasets: [
      {{ label: 'Massa Magra (kg)', data: {json.dumps(bc_ffm)}, backgroundColor: '#667eea88', borderColor: '#667eea', borderWidth: 1 }},
      {{ label: 'Massa Grassa (kg)', data: {json.dumps(bc_fm)}, backgroundColor: '#f43f5e88', borderColor: '#f43f5e', borderWidth: 1 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ labels: {{ color: '#e0e0e0' }} }} }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: '#8b8fa3', font: {{ size: 10 }} }}, grid: {{ color: '#2a2d3e' }} }},
      y: {{ stacked: true, ticks: {{ color: '#8b8fa3' }}, grid: {{ color: '#2a2d3e' }} }}
    }}
  }}
}});

{"" if not macro_labels else f"""
// Macro chart
const mCtx = document.getElementById('macroChart').getContext('2d');
new Chart(mCtx, {{
  type: 'bar',
  data: {{
    labels: {json.dumps(macro_labels)},
    datasets: [
      {{ label: 'Proteine (g)', data: {json.dumps(macro_protein)}, backgroundColor: '#667eea88', borderColor: '#667eea', borderWidth: 1 }},
      {{ label: 'Carboidrati (g)', data: {json.dumps(macro_carbs)}, backgroundColor: '#f59e0b88', borderColor: '#f59e0b', borderWidth: 1 }},
      {{ label: 'Grassi (g)', data: {json.dumps(macro_fat)}, backgroundColor: '#f43f5e88', borderColor: '#f43f5e', borderWidth: 1 }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color: '#e0e0e0' }} }},
      title: {{ display: true, text: 'Macronutrienti giornalieri medi (g)', color: '#e0e0e0' }}
    }},
    scales: {{
      x: {{ stacked: true, ticks: {{ color: '#8b8fa3', maxRotation: 60, font: {{ size: 9 }} }}, grid: {{ color: '#2a2d3e' }} }},
      y: {{ stacked: true, ticks: {{ color: '#8b8fa3' }}, grid: {{ color: '#2a2d3e' }} }}
    }}
  }}
}});

// Protein per kg chart
const pkCtx = document.getElementById('proteinKgChart').getContext('2d');
new Chart(pkCtx, {{
  type: 'line',
  data: {{
    labels: {json.dumps(macro_labels)},
    datasets: [{{
      label: 'Proteine (g/kg)',
      data: {json.dumps(macro_ppkg)},
      borderColor: '#a78bfa',
      backgroundColor: '#a78bfa22',
      fill: true,
      tension: 0.3,
      pointRadius: 4
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color: '#e0e0e0' }} }},
      title: {{ display: true, text: 'Proteine per kg di peso corporeo', color: '#e0e0e0' }},
      annotation: {{ annotations: {{ target: {{ type: 'line', yMin: 2.0, yMax: 2.0, borderColor: '#34d399', borderWidth: 1, borderDash: [5,5], label: {{ display: true, content: 'Target 2.0 g/kg', position: 'start', color: '#34d399', font: {{ size: 10 }} }} }} }} }}
    }},
    scales: {{
      x: {{ ticks: {{ color: '#8b8fa3', maxRotation: 60, font: {{ size: 9 }} }}, grid: {{ color: '#2a2d3e' }} }},
      y: {{ min: 1.5, max: 3.5, ticks: {{ color: '#8b8fa3' }}, grid: {{ color: '#2a2d3e' }} }}
    }}
  }}
}});
"""}
</script>
</body>
</html>'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Report saved to {output_path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Generate HTML report from extracted program data")
    parser.add_argument("input", help="Input JSON file from extract_programs.py")
    parser.add_argument("--output", "-o", required=True, help="Output HTML file path")
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)

    generate_html(data, args.output)


if __name__ == "__main__":
    main()
