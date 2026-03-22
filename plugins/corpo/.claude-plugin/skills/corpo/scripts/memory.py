#!/usr/bin/env python3
"""
Global Memory Manager for Nutritional Program Analyzer.
Maintains a persistent state file in the programs root directory that tracks:
- Next steps / action items (e.g., blood tests to do, appointments)
- Notes from the nutritionist (Musolino)
- Historical decisions and their outcomes
- Reminders and follow-ups

The memory file is a JSON file stored at <programs_root>/nutrizionista_memory.json.
It persists between sessions and is updated whenever new information is available.

Usage:
  # Read current memory
  python3 memory.py <programs_root> --read

  # Add a next step
  python3 memory.py <programs_root> --add-step "Fare analisi emocromo" --category "analisi" --priority "alta" --source "Musolino"

  # Mark a step as completed
  python3 memory.py <programs_root> --complete-step <step_id>

  # Add a note
  python3 memory.py <programs_root> --add-note "Musolino consiglia analisi entro febbraio"

  # Export summary
  python3 memory.py <programs_root> --summary
"""

import argparse
import json
import os
import sys
from datetime import datetime

MEMORY_FILENAME = "nutrizionista_memory.json"


def get_memory_path(programs_root):
    """Get the path to the memory file in the programs root directory."""
    return os.path.join(programs_root, MEMORY_FILENAME)


def load_memory(programs_root):
    """Load the memory file, creating a default one if it doesn't exist."""
    path = get_memory_path(programs_root)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # Create default memory structure
    return create_default_memory()


def create_default_memory():
    """Create the default memory structure."""
    return {
        "version": 1,
        "created": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "current_program": None,
        "next_steps": [],
        "completed_steps": [],
        "notes": [],
        "nutritionist_recommendations": [],
        "bloodwork_history": [],
        "decisions_log": [],
        "shopping_preferences": {
            "locations": ["bennet_ponte_tresa", "migros_lugano"],
            "people": 2,
            "preferences": {
                "pesce_magro": "tonno fresco abbattuto",
                "pesce_azzurro": "salmone fresco abbattuto",
                "whey_brand": "+Watt (solo Vincenzo)",
                "affettati_mix": "fesa tacchino 5x + bresaola 2x",
            },
            "last_generated": None,
            "notion_db_id": None,
        },
    }


def save_memory(programs_root, memory):
    """Save the memory file."""
    path = get_memory_path(programs_root)
    memory["last_updated"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)
    return path


def generate_step_id(memory):
    """Generate a unique step ID."""
    all_steps = memory.get("next_steps", []) + memory.get("completed_steps", [])
    if not all_steps:
        return 1
    return max(s.get("id", 0) for s in all_steps) + 1


def add_next_step(
    memory,
    description,
    category="generale",
    priority="media",
    source=None,
    due_date=None,
    details=None,
):
    """Add a next step / action item."""
    step = {
        "id": generate_step_id(memory),
        "description": description,
        "category": category,  # analisi, supplementi, alimentazione, allenamento, visita, generale
        "priority": priority,  # alta, media, bassa
        "status": "pending",
        "created": datetime.now().isoformat(),
        "due_date": due_date,
        "source": source,  # e.g., "Musolino", "AI analysis", "self"
        "details": details,  # additional context
    }
    memory["next_steps"].append(step)
    return step


def complete_step(memory, step_id, outcome=None):
    """Mark a step as completed and move it to completed_steps."""
    for i, step in enumerate(memory["next_steps"]):
        if step["id"] == step_id:
            step["status"] = "completed"
            step["completed_date"] = datetime.now().isoformat()
            step["outcome"] = outcome
            memory["completed_steps"].append(step)
            memory["next_steps"].pop(i)
            return step
    return None


def add_note(memory, text, source=None, related_program=None):
    """Add a general note."""
    note = {
        "id": len(memory.get("notes", [])) + 1,
        "text": text,
        "date": datetime.now().isoformat(),
        "source": source,
        "related_program": related_program,
    }
    memory["notes"].append(note)
    return note


def add_nutritionist_recommendation(
    memory,
    recommendation,
    nutritionist="Musolino",
    related_program=None,
    action_items=None,
):
    """Add a recommendation from the nutritionist."""
    rec = {
        "id": len(memory.get("nutritionist_recommendations", [])) + 1,
        "recommendation": recommendation,
        "nutritionist": nutritionist,
        "date": datetime.now().isoformat(),
        "related_program": related_program,
        "action_items": action_items or [],
        "followed": False,
    }
    memory["nutritionist_recommendations"].append(rec)
    return rec


def add_bloodwork_entry(memory, tests_done, results=None, date=None, notes=None):
    """Record bloodwork that was done."""
    entry = {
        "id": len(memory.get("bloodwork_history", [])) + 1,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "tests_done": tests_done,
        "results": results or {},
        "notes": notes,
    }
    memory["bloodwork_history"].append(entry)
    return entry


def log_decision(memory, decision, reasoning, related_program=None):
    """Log a decision made (e.g., starting/stopping a supplement, changing diet)."""
    entry = {
        "id": len(memory.get("decisions_log", [])) + 1,
        "date": datetime.now().isoformat(),
        "decision": decision,
        "reasoning": reasoning,
        "related_program": related_program,
    }
    memory["decisions_log"].append(entry)
    return entry


def get_shopping_preferences(memory):
    """Get shopping preferences, initializing defaults if missing."""
    if "shopping_preferences" not in memory:
        memory["shopping_preferences"] = {
            "locations": ["bennet_ponte_tresa", "migros_lugano"],
            "people": 2,
            "preferences": {},
            "last_generated": None,
            "notion_db_id": None,
        }
    return memory["shopping_preferences"]


def set_shopping_preference(memory, key, value):
    """Set a shopping preference value."""
    prefs = get_shopping_preferences(memory)
    if key in ("locations", "people", "notion_db_id", "last_generated"):
        if key == "people":
            value = int(value)
        elif key == "locations":
            value = [v.strip() for v in value.split(",")]
        prefs[key] = value
    else:
        prefs.setdefault("preferences", {})[key] = value
    return prefs


def update_shopping_last_generated(memory):
    """Mark when the shopping list was last generated."""
    prefs = get_shopping_preferences(memory)
    prefs["last_generated"] = datetime.now().isoformat()


def format_shopping_preferences(memory):
    """Format shopping preferences as human-readable text."""
    prefs = get_shopping_preferences(memory)
    lines = []
    lines.append("--- PREFERENZE SPESA ---")
    lines.append(f"  Persone: {prefs.get('people', 1)}")
    lines.append(f"  Negozi: {', '.join(prefs.get('locations', []))}")
    custom = prefs.get("preferences", {})
    if custom:
        lines.append("  Preferenze specifiche:")
        for k, v in custom.items():
            lines.append(f"    {k}: {v}")
    last = prefs.get("last_generated")
    if last:
        lines.append(f"  Ultima lista generata: {last[:10]}")
    return "\n".join(lines)


def update_current_program(memory, program_num, program_data=None):
    """Update the current program reference in memory."""
    memory["current_program"] = {
        "program_num": program_num,
        "updated": datetime.now().isoformat(),
        "summary": program_data,
    }


def get_pending_steps(memory, category=None, priority=None):
    """Get pending next steps, optionally filtered."""
    steps = memory.get("next_steps", [])
    if category:
        steps = [s for s in steps if s.get("category") == category]
    if priority:
        steps = [s for s in steps if s.get("priority") == priority]
    return steps


def format_summary(memory):
    """Format a human-readable summary of the current memory state."""
    lines = []
    lines.append("=" * 60)
    lines.append("STATO ATTUALE — MEMORIA NUTRIZIONISTA")
    lines.append(f"Ultimo aggiornamento: {memory.get('last_updated', '?')}")
    lines.append("=" * 60)

    # Current program
    cp = memory.get("current_program")
    if cp:
        lines.append(f"\nProgramma corrente: #{cp.get('program_num', '?')}")

    # Pending steps by priority
    pending = memory.get("next_steps", [])
    if pending:
        lines.append(f"\n--- PROSSIMI PASSI ({len(pending)} in sospeso) ---")

        # Sort by priority
        priority_order = {"alta": 0, "media": 1, "bassa": 2}
        pending_sorted = sorted(
            pending, key=lambda s: priority_order.get(s.get("priority", "media"), 1)
        )

        for step in pending_sorted:
            priority_icon = {"alta": "🔴", "media": "🟡", "bassa": "🟢"}.get(
                step.get("priority", "media"), "⚪"
            )
            source_str = f" [da {step['source']}]" if step.get("source") else ""
            due_str = f" — scadenza: {step['due_date']}" if step.get("due_date") else ""
            details_str = (
                f"\n    Dettagli: {step['details']}" if step.get("details") else ""
            )
            lines.append(
                f"  {priority_icon} [{step['id']}] {step['description']} ({step['category']}){source_str}{due_str}{details_str}"
            )

    # Recent notes
    notes = memory.get("notes", [])
    if notes:
        lines.append(f"\n--- NOTE RECENTI ---")
        for note in notes[-5:]:  # last 5
            source_str = f" [{note['source']}]" if note.get("source") else ""
            note_text = note.get("text") or note.get("content", "(no text)")
            lines.append(f"  • {note_text}{source_str} ({note['date'][:10]})")

    # Nutritionist recommendations
    recs = memory.get("nutritionist_recommendations", [])
    if recs:
        lines.append(f"\n--- RACCOMANDAZIONI NUTRIZIONISTA ---")
        for rec in recs[-3:]:  # last 3
            status = "✅" if rec.get("followed") else "⏳"
            lines.append(
                f"  {status} {rec['recommendation']} [{rec['nutritionist']}] ({rec['date'][:10]})"
            )

    # Bloodwork history
    blood = memory.get("bloodwork_history", [])
    if blood:
        lines.append(f"\n--- STORICO ANALISI ---")
        for b in blood[-3:]:
            if "tests_done" in b:
                tests_str = ", ".join(b["tests_done"][:5]) + (
                    "..." if len(b["tests_done"]) > 5 else ""
                )
            elif "results" in b and isinstance(b["results"], dict):
                tests_str = ", ".join(b["results"].keys())
            elif "key_findings" in b:
                tests_str = f"{len(b['key_findings'])} findings"
            else:
                tests_str = "(no details)"
            lab_str = f" [{b.get('lab', '')}]" if b.get("lab") else ""
            lines.append(f"  • {b['date']}{lab_str}: {tests_str}")

    # Recently completed steps
    completed = memory.get("completed_steps", [])
    if completed:
        lines.append(f"\n--- COMPLETATI DI RECENTE ({len(completed)} totali) ---")
        for step in completed[-3:]:
            outcome_str = f" → {step['outcome']}" if step.get("outcome") else ""
            lines.append(
                f"  ✅ {step['description']}{outcome_str} ({step.get('completed_date', '?')[:10]})"
            )

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Manage nutritional program memory")
    parser.add_argument("programs_root", help="Root directory of nutritional programs")
    parser.add_argument("--read", action="store_true", help="Read current memory")
    parser.add_argument(
        "--summary", action="store_true", help="Print formatted summary"
    )
    parser.add_argument("--add-step", help="Add a next step")
    parser.add_argument("--category", default="generale", help="Step category")
    parser.add_argument(
        "--priority", default="media", help="Step priority (alta/media/bassa)"
    )
    parser.add_argument("--source", help="Who recommended this step")
    parser.add_argument("--due-date", help="Due date for the step")
    parser.add_argument("--details", help="Additional details")
    parser.add_argument(
        "--complete-step", type=int, help="Mark a step as completed by ID"
    )
    parser.add_argument("--outcome", help="Outcome of completed step")
    parser.add_argument("--add-note", help="Add a note")
    parser.add_argument(
        "--init", action="store_true", help="Initialize/reset memory file"
    )
    parser.add_argument(
        "--set-shopping-pref",
        nargs=2,
        metavar=("KEY", "VALUE"),
        help="Set a shopping preference (e.g., people 2, locations bennet_ponte_tresa,migros_lugano)",
    )
    parser.add_argument(
        "--show-shopping-prefs",
        action="store_true",
        help="Show current shopping preferences",
    )
    parser.add_argument(
        "--log-price",
        nargs=3,
        metavar=("LOCATION", "FOOD", "PRICE"),
        help="Log a price from a receipt",
    )
    parser.add_argument("--log-price-source", default="scontrino", help="Price source")
    parser.add_argument("--log-price-note", help="Note for logged price")
    args = parser.parse_args()

    if args.init:
        memory = create_default_memory()
        path = save_memory(args.programs_root, memory)
        print(f"Memory initialized at {path}", file=sys.stderr)
        return

    memory = load_memory(args.programs_root)

    if args.add_step:
        step = add_next_step(
            memory,
            args.add_step,
            category=args.category,
            priority=args.priority,
            source=args.source,
            due_date=args.due_date,
            details=args.details,
        )
        save_memory(args.programs_root, memory)
        print(f"Added step #{step['id']}: {step['description']}", file=sys.stderr)

    elif args.complete_step:
        step = complete_step(memory, args.complete_step, outcome=args.outcome)
        if step:
            save_memory(args.programs_root, memory)
            print(
                f"Completed step #{step['id']}: {step['description']}", file=sys.stderr
            )
        else:
            print(f"Step #{args.complete_step} not found", file=sys.stderr)

    elif args.add_note:
        note = add_note(memory, args.add_note, source=args.source)
        save_memory(args.programs_root, memory)
        print(f"Added note #{note['id']}", file=sys.stderr)

    elif args.set_shopping_pref:
        key, value = args.set_shopping_pref
        prefs = set_shopping_preference(memory, key, value)
        save_memory(args.programs_root, memory)
        print(f"Set shopping preference {key} = {value}", file=sys.stderr)

    elif args.show_shopping_prefs:
        print(format_shopping_preferences(memory))

    elif args.log_price:
        location, food, price_str = args.log_price
        price = float(price_str)
        # Import and use generate_shopping_list's price functions
        script_dir = os.path.dirname(os.path.abspath(__file__))
        price_db_path = os.path.join(script_dir, "price_db.json")
        if os.path.exists(price_db_path):
            sys.path.insert(0, script_dir)
            from generate_shopping_list import load_price_db, log_receipt_price, save_price_db

            price_db = load_price_db(price_db_path)
            log_receipt_price(price_db, location, food, price, args.log_price_note)
            save_price_db(price_db_path, price_db)
            print(
                f"Logged price: {food} at {location} = {price} ({args.log_price_source})",
                file=sys.stderr,
            )
        else:
            print(f"Price database not found: {price_db_path}", file=sys.stderr)

    elif args.summary:
        print(format_summary(memory))

    elif args.read:
        print(json.dumps(memory, ensure_ascii=False, indent=2))

    else:
        # Default: print summary
        print(format_summary(memory))


if __name__ == "__main__":
    main()
