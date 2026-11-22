"""
CSV & link-file reference logging, counting, and deduplication.
"""

import os
import re
import csv
import json
from datetime import datetime


CSV_HEADER = [
    "Class",
    "Language",
    "Video_ID",
    "Source_URL",
    "Date_Accessed",
    "License",
    "Keyword",
    "Title",
    "Channel",
    "Duration",
]

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi")
URL_ID_RE = re.compile(
    r"(?:[?&]v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{6,})"
)


def extract_video_id(url_or_id):
    """Extract YouTube video ID from a URL, or return a safe ID fallback."""
    if not url_or_id:
        return ""
    s = str(url_or_id).strip()
    m = URL_ID_RE.search(s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    cleaned = re.sub(r"[^A-Za-z0-9_-]", "_", s.split("://")[-1])
    return cleaned[-32:] if cleaned else ""


def normalize_url(url, video_id=""):
    """Ensure a valid full video URL."""
    u = (url or "").strip()
    if u.startswith("http://") or u.startswith("https://"):
        return u
    vid = video_id or extract_video_id(u)
    if vid:
        return f"https://www.youtube.com/watch?v={vid}"
    return u


def get_csv_path(config):
    """Return path to source_references.csv."""
    return os.path.join(config["output_dir"], "source_references.csv")


def get_decisions_path(config):
    """Return path to review_decisions.json."""
    return os.path.join(config["output_dir"], "review_decisions.json")


def get_links_path(config, class_name, language=None):
    """Return path to links.txt for a given class and language."""
    lang = language or config["language"]
    return os.path.join(config["output_dir"], class_name, lang, "links.txt")


def get_decision_key(class_name, language, video_id):
    """Canonical key in review_decisions.json for a video link."""
    return f"{class_name}/{language}/{video_id}"


def load_decisions(config):
    """Load review_decisions.json safely."""
    path = get_decisions_path(config)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def get_decision_status(decisions, class_name, language, video_id, url=""):
    """Look up decision ('accepted', 'rejected', or 'pending') supporting new and legacy keys."""
    key = get_decision_key(class_name, language, video_id)
    if key in decisions:
        return decisions[key]
    if url and url in decisions:
        return decisions[url]
    if video_id:
        suffix = f"_{video_id}".lower()
        for k, val in decisions.items():
            k_norm = k.replace("\\", "/")
            if k_norm.startswith(f"{class_name}/{language}/"):
                base = os.path.splitext(os.path.basename(k_norm))[0].lower()
                if base == video_id.lower() or base.endswith(suffix):
                    return val
    return "pending"


def _ensure_csv_header(csv_path):
    """Ensure source_references.csv exists and has the current header columns."""
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADER)
        return

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        first_row = next(reader, None)

    if first_row and "Language" not in first_row:
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            dict_reader = csv.DictReader(f)
            old_rows = list(dict_reader)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
            writer.writeheader()
            for r in old_rows:
                url = r.get("Source_URL", "")
                vid = r.get("Video_ID") or extract_video_id(url)
                writer.writerow(
                    {
                        "Class": r.get("Class", ""),
                        "Language": r.get("Language") or "en",
                        "Video_ID": vid,
                        "Source_URL": normalize_url(url, vid),
                        "Date_Accessed": r.get("Date_Accessed", ""),
                        "License": r.get("License", "YouTube Standard"),
                        "Keyword": r.get("Keyword", ""),
                        "Title": r.get("Title", "Unknown"),
                        "Channel": r.get("Channel", "Unknown"),
                        "Duration": r.get("Duration", ""),
                    }
                )


def _append_links_file(config, class_name, language, urls):
    """Append new URLs to <output_dir>/<class_name>/<language>/links.txt without duplicates."""
    links_path = get_links_path(config, class_name, language)
    os.makedirs(os.path.dirname(links_path), exist_ok=True)
    existing = set()
    if os.path.exists(links_path):
        with open(links_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    existing.add(line)

    new_urls = [u for u in urls if u and u not in existing]
    if new_urls:
        with open(links_path, "a", encoding="utf-8") as f:
            for u in new_urls:
                f.write(u + "\n")
                existing.add(u)


def log_entries(config, class_name, entries, keyword, language=None):
    """Log video metadata entries to source_references.csv and (in link-only mode) per-class links.txt."""
    lang = language or config.get("language", "en")
    csv_path = get_csv_path(config)
    _ensure_csv_header(csv_path)

    urls_to_save = []
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for entry in entries:
            vid = entry.get("id") or extract_video_id(
                entry.get("webpage_url") or entry.get("url", "")
            )
            url = normalize_url(
                entry.get("webpage_url") or entry.get("url", ""), vid
            )
            title = entry.get("title") or vid or "Unknown"
            channel = (
                entry.get("channel")
                or entry.get("uploader")
                or entry.get("uploader_id")
                or "Unknown"
            )
            license_info = entry.get("license") or "YouTube Standard"
            duration = entry.get("duration")
            duration_str = (
                str(int(round(float(duration))))
                if duration is not None and str(duration) != ""
                else ""
            )

            writer.writerow(
                [
                    class_name,
                    lang,
                    vid,
                    url,
                    datetime.now().strftime("%Y-%m-%d"),
                    license_info,
                    keyword,
                    title,
                    channel,
                    duration_str,
                ]
            )
            urls_to_save.append(url)

    if config.get("links_only") or os.path.exists(get_links_path(config, class_name, lang)):
        _append_links_file(config, class_name, lang, urls_to_save)


def load_all_entries(config):
    """Load all collected link records from source_references.csv and any links.txt files."""
    csv_path = get_csv_path(config)
    records = []
    seen_keys = set()

    if os.path.exists(csv_path):
        _ensure_csv_header(csv_path)
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cls_name = (row.get("Class") or "").strip()
                lang = (row.get("Language") or config.get("language", "en")).strip()
                raw_url = (row.get("Source_URL") or "").strip()
                if not cls_name or not raw_url or raw_url.startswith("YouTube search:"):
                    continue
                vid = (row.get("Video_ID") or "").strip() or extract_video_id(raw_url)
                url = normalize_url(raw_url, vid)
                dedup_k = (cls_name, lang, vid or url)
                if dedup_k in seen_keys:
                    continue
                seen_keys.add(dedup_k)
                records.append(
                    {
                        "Class": cls_name,
                        "Language": lang,
                        "Video_ID": vid,
                        "Source_URL": url,
                        "Date_Accessed": row.get("Date_Accessed", ""),
                        "License": row.get("License", "YouTube Standard"),
                        "Keyword": row.get("Keyword", ""),
                        "Title": row.get("Title") or vid or url,
                        "Channel": row.get("Channel") or "Unknown",
                        "Duration": row.get("Duration", ""),
                    }
                )

    out_dir = config.get("output_dir", "./data")
    if os.path.exists(out_dir):
        for cls_name in sorted(os.listdir(out_dir)):
            cls_path = os.path.join(out_dir, cls_name)
            if not os.path.isdir(cls_path):
                continue
            for lang in sorted(os.listdir(cls_path)):
                lang_path = os.path.join(cls_path, lang)
                if not os.path.isdir(lang_path):
                    continue
                links_file = os.path.join(lang_path, "links.txt")
                if not os.path.exists(links_file):
                    continue
                with open(links_file, "r", encoding="utf-8") as f:
                    for line in f:
                        raw_url = line.strip()
                        if not raw_url or raw_url.startswith("#"):
                            continue
                        vid = extract_video_id(raw_url)
                        url = normalize_url(raw_url, vid)
                        dedup_k = (cls_name, lang, vid or url)
                        if dedup_k in seen_keys:
                            continue
                        seen_keys.add(dedup_k)
                        records.append(
                            {
                                "Class": cls_name,
                                "Language": lang,
                                "Video_ID": vid,
                                "Source_URL": url,
                                "Date_Accessed": "",
                                "License": "YouTube Standard",
                                "Keyword": "manual",
                                "Title": vid or url,
                                "Channel": "Unknown",
                                "Duration": "",
                            }
                        )

    return records


def _count_disk_videos(config, class_name, language=None):
    """Count physical video files on disk (excluding _rejected/)."""
    class_dir = os.path.join(config["output_dir"], class_name)
    count = 0
    video_dir = (
        os.path.join(class_dir, language, "Videos")
        if language
        else os.path.join(class_dir, "Videos")
    )
    if os.path.exists(video_dir):
        for root, dirs, files in os.walk(video_dir):
            dirs[:] = [d for d in dirs if d != "_rejected"]
            count += len([f for f in files if f.lower().endswith(VIDEO_EXTS)])
    return count


def count_videos(config, class_name, language=None):
    """Count collected videos or links for a class, optionally filtered by language."""
    disk_count = _count_disk_videos(config, class_name, language)
    if disk_count > 0 and not config.get("links_only"):
        return disk_count

    records = load_all_entries(config)
    decisions = load_decisions(config)
    count = 0
    for r in records:
        if r["Class"] != class_name:
            continue
        if language and r["Language"] != language:
            continue
        status = get_decision_status(
            decisions, r["Class"], r["Language"], r["Video_ID"], r["Source_URL"]
        )
        if status != "rejected":
            count += 1
    return count


def get_language_folders(config, class_name):
    """Return a sorted list of languages present for a class (from folders or CSV)."""
    languages = set()
    class_dir = os.path.join(config["output_dir"], class_name)
    if os.path.exists(class_dir):
        for item in sorted(os.listdir(class_dir)):
            item_path = os.path.join(class_dir, item)
            if os.path.isdir(item_path) and item not in {
                "Videos",
                "_rejected",
                "_accepted",
            }:
                if (
                    os.path.exists(os.path.join(item_path, "Videos"))
                    or os.path.exists(os.path.join(item_path, "links.txt"))
                ):
                    languages.add(item)

    for r in load_all_entries(config):
        if r["Class"] == class_name and r["Language"]:
            languages.add(r["Language"])

    return sorted(languages)


def deduplicate(config):
    """Remove duplicate rows from source_references.csv and per-folder links.txt files."""
    csv_path = get_csv_path(config)
    if not os.path.exists(csv_path):
        return {"before": 0, "after": 0, "removed": 0}

    _ensure_csv_header(csv_path)
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    before = len(rows)
    cleaned = [
        r for r in rows if not (r.get("Source_URL") or "").startswith("YouTube search:")
    ]

    seen = set()
    deduped = []
    per_folder_urls = {}

    for r in cleaned:
        cls_name = r.get("Class", "")
        lang = r.get("Language") or config.get("language", "en")
        url = r.get("Source_URL", "")
        vid = r.get("Video_ID") or extract_video_id(url)
        norm_u = normalize_url(url, vid)
        r["Video_ID"] = vid
        r["Source_URL"] = norm_u
        r["Language"] = lang

        key = (cls_name, vid or norm_u)
        if key not in seen:
            seen.add(key)
            deduped.append(r)
            per_folder_urls.setdefault((cls_name, lang), []).append(norm_u)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(deduped)

    for (cls_name, lang), urls in per_folder_urls.items():
        links_path = get_links_path(config, cls_name, lang)
        if os.path.exists(links_path) or config.get("links_only"):
            os.makedirs(os.path.dirname(links_path), exist_ok=True)
            unique_urls = list(dict.fromkeys(urls))
            with open(links_path, "w", encoding="utf-8") as f:
                for u in unique_urls:
                    f.write(u + "\n")

    return {"before": before, "after": len(deduped), "removed": before - len(deduped)}


def get_progress(config):
    """Get collection progress for all classes and languages."""
    default_target = config["target_per_class"]
    class_targets = config.get("class_targets", {})
    progress = {}
    out = config.get("output_dir", "./data")
    decisions = load_decisions(config)
    records = load_all_entries(config)

    all_classes = list(config.get("classes", {}).keys())
    if os.path.exists(out):
        for name in sorted(os.listdir(out)):
            if os.path.isdir(os.path.join(out, name)) and name not in all_classes:
                all_classes.append(name)
    for r in records:
        if r["Class"] not in all_classes:
            all_classes.append(r["Class"])

    for name in all_classes:
        target = int(class_targets.get(name, default_target))
        languages = get_language_folders(config, name)
        if not languages:
            languages = [config.get("language", "en")]
        progress[name] = {}
        for lang in languages:
            lang_records = [
                r for r in records if r["Class"] == name and r["Language"] == lang
            ]
            if lang_records or config.get("links_only"):
                accepted = 0
                rejected = 0
                pending = 0
                for r in lang_records:
                    st = get_decision_status(
                        decisions,
                        r["Class"],
                        r["Language"],
                        r["Video_ID"],
                        r["Source_URL"],
                    )
                    if st == "accepted":
                        accepted += 1
                    elif st == "rejected":
                        rejected += 1
                    else:
                        pending += 1
                active_count = accepted + pending
                progress[name][lang] = {
                    "count": active_count,
                    "accepted": accepted,
                    "pending": pending,
                    "rejected": rejected,
                    "target": target,
                    "pct": min(100, round(active_count / target * 100))
                    if target > 0
                    else 0,
                }
            else:
                count = _count_disk_videos(config, name, language=lang)
                progress[name][lang] = {
                    "count": count,
                    "target": target,
                    "pct": min(100, round(count / target * 100)) if target > 0 else 0,
                }

    return progress


def print_progress(config):
    """Print a formatted progress bar for all classes and languages."""
    progress = get_progress(config)
    bar_width = 30

    print(f"\n{'='*80}")
    print(f"  {config['name']} - Collection Progress")
    print(f"{'='*80}")

    total_collected = 0
    total_target = 0

    for cls_name, data in progress.items():
        cls_target = int(
            config.get("class_targets", {}).get(cls_name, config["target_per_class"])
        )
        total_target += cls_target
        print(f"\n  {cls_name} (Target: {cls_target}):")
        for lang, lang_data in sorted(data.items()):
            count = lang_data["count"]
            target = lang_data["target"]
            total_collected += count
            pct = lang_data["pct"]
            filled = (
                min(bar_width, int(bar_width * count / target)) if target > 0 else 0
            )
            bar = "#" * filled + "-" * (bar_width - filled)
            if "accepted" in lang_data:
                acc = lang_data["accepted"]
                pend = lang_data["pending"]
                rej = lang_data["rejected"]
                print(
                    f"    {lang:4s}: {count:4d}/{target:3d}  [{bar}] {pct:3d}%  "
                    f"(Accepted: {acc}, Pending: {pend}, Rejected: {rej})"
                )
            else:
                print(f"    {lang:4s}: {count:4d}/{target:3d}  [{bar}] {pct:3d}%")

    print(f"\n  TOTAL: {total_collected}/{total_target}")
    print()
