"""
CLI entry point.

Usage:
    python main.py "<plain language lead-gen request>"
    python main.py "<request>" --mode fixed
    python main.py "<request>" --mode agent   (default)
"""
import sys
import os
import json

# Fix Windows console encoding for Unicode output
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.pipeline import run_pipeline, save_results


def main():
    if len(sys.argv) < 2:
        print('Usage: python main.py "<request>" [--mode agent|fixed]')
        sys.exit(1)

    user_request = sys.argv[1]
    mode = "agent"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            mode = sys.argv[idx + 1]

    print(f"\nQuery: {user_request}")
    print(f"Mode:  {mode}\n")

    results = run_pipeline(
        user_request,
        mode=mode,
        progress_callback=lambda msg: print(f"  > {msg}"),
    )

    leads = results.get("leads", [])
    actual = results.get("mode", "unknown")
    print(f"\nFound {len(leads)} leads (pipeline: {actual}):\n")

    for i, lead in enumerate(leads, 1):
        print(f"  {i}. {lead['company']} -- Score: {lead['lead_score']}/100, Confidence: {lead['confidence']}")
        if lead.get("why_relevant"):
            print(f"     {lead['why_relevant']}")
        if lead.get("sources"):
            for s in lead["sources"]:
                tag = "[verified]" if s["verified"] else "[unverified]"
                print(f"     {tag} [{s['type']}] {s['url']}")
        print()

    os.makedirs("data", exist_ok=True)
    out_path = "data/results.json"
    save_results(results, out_path)
    print(f"Results saved to {out_path}")


if __name__ == "__main__":
    main()
