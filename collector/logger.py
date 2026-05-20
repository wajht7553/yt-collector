"""
CSV reference logging and deduplication.
"""

import csv
import json
import os
from datetime import datetime


def get_csv_path(config):
    """Return path to source_references.csv."""
    return os.path.join(config["output_dir"], "source_references.csv")


def get_decisions_path(config):
    """Return path to review_decisions.json."""
    return os.path.join(config["output_dir"], "review_decisions.json")


CSV_HEADER = [
    "Class", "Source_URL", "Source_Type", "Media_Type",
    "Num_Videos", "Date_Accessed", "License", "Notes",
]


def log_entries(config, class_name, entries, keyword):
    """Log video metadata entries to the CSV."""
    csv_path = get_csv_path(config)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for entry in entries:
            url = entry.get("webpage_url") or entry.get("url", "")
            title = entry.get("title", "Unknown")
            channel = entry.get("channel", entry.get("uploader", "Unknown"))
            license_info = entry.get("license", "YouTube Standard")
            duration = entry.get("duration", 0)

            writer.writerow([
                class_name,
                url,
                "YouTube",
                "Video",
                1,
                datetime.now().strftime("%Y-%m-%d"),
                license_info,
                f"keyword={keyword} | title={title} | channel={channel} | duration={duration}s",
            ])


def log_simple(config, class_name, source, num_videos, notes=""):
    """Fallback logging when metadata is unavailable."""
    csv_path = get_csv_path(config)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            class_name, source, "YouTube", "Video",
            num_videos, datetime.now().strftime("%Y-%m-%d"),
            "YouTube Standard", notes,
        ])


def count_videos(config, class_name):
    """Count video files on disk for a class."""
    class_dir = os.path.join(config["output_dir"], class_name, "Videos")
    count = 0
    if os.path.exists(class_dir):
        for root, dirs, files in os.walk(class_dir):
            dirs[:] = [d for d in dirs if d != "_rejected"]
            count += len([f for f in files if f.lower().endswith((".mp4", ".mkv", ".webm"))])
    return count


def deduplicate(config):
    """Remove duplicate and fallback rows from the CSV. Returns stats."""
    csv_path = get_csv_path(config)
    if not os.path.exists(csv_path):
        return {"before": 0, "after": 0, "removed": 0}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    before = len(rows)

    # Remove fallback rows
    cleaned = [r for r in rows if not r["Source_URL"].startswith("YouTube search:")]

    # Deduplicate by URL
    seen = set()
    deduped = []
    for r in cleaned:
        url = r["Source_URL"]
        if url not in seen:
            seen.add(url)
            deduped.append(r)

    # Write back
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deduped)

    return {"before": before, "after": len(deduped), "removed": before - len(deduped)}


def get_progress(config):
    """Get download progress for all classes."""
    target = config["target_per_class"]
    progress = {}
    for cls_name in config["classes"]:
        count = count_videos(config, cls_name)
        progress[cls_name] = {
            "count": count,
            "target": target,
            "pct": min(100, round(count / target * 100)) if target > 0 else 0,
        }
    return progress


def print_progress(config):
    """Print a formatted progress bar for all classes."""
    progress = get_progress(config)
    target = config["target_per_class"]
    bar_width = 40

    print(f"\n{'='*60}")
    print(f"  {config['name']} - Collection Progress")
    print(f"{'='*60}")

    for cls_name, data in progress.items():
        filled = int(bar_width * data["count"] / target) if target > 0 else 0
        bar = "#" * filled + "-" * (bar_width - filled)
        print(f"  {cls_name:20s}: {data['count']:4d}/{target}  [{bar}] {data['pct']}%")

    print()
