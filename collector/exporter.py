"""Export accepted videos or video links (and matching metadata) to an external dataset folder."""

import os
import csv
import shutil

from . import logger

VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".avi")
YOUTUBE_ID_LENGTH = 11


def _video_id_from_filename(filename):
    """Extract the trailing yt-dlp video ID from a --restrict-filenames basename."""
    base = os.path.splitext(filename)[0]
    if len(base) > YOUTUBE_ID_LENGTH and base[-(YOUTUBE_ID_LENGTH + 1)] == "_":
        return base[-YOUTUBE_ID_LENGTH:]
    return None


def _find_accepted_videos(output_dir):
    """Yield (class_name, language, full_path, filename) for every video under an _accepted/ folder."""
    if not os.path.exists(output_dir):
        return
    for cls_name in sorted(os.listdir(output_dir)):
        cls_path = os.path.join(output_dir, cls_name)
        if not os.path.isdir(cls_path):
            continue
        for root, dirs, files in os.walk(cls_path):
            if os.path.basename(root) != "_accepted":
                continue
            language = os.path.relpath(root, cls_path).split(os.sep)[0]
            if language == "Videos":
                continue
            for f in sorted(files):
                if f.lower().endswith(VIDEO_EXTS):
                    yield cls_name, language, os.path.join(root, f), f


def export_dataset(config, dest_dir):
    """Export accepted videos (or accepted video links in link-only mode) and filtered metadata."""
    output_dir = config["output_dir"]
    os.makedirs(dest_dir, exist_ok=True)

    file_items = list(_find_accepted_videos(output_dir))

    # If physical accepted video files exist and we are not in links_only mode, copy files
    if file_items and not config.get("links_only"):
        all_keys = set()
        per_class = {}
        skipped_existing = 0

        for cls_name, language, full_path, fname in file_items:
            dest_class_dir = os.path.join(dest_dir, cls_name, language)
            os.makedirs(dest_class_dir, exist_ok=True)
            dest_path = os.path.join(dest_class_dir, fname)

            vid = _video_id_from_filename(fname)
            if vid:
                all_keys.add((cls_name, vid))

            if os.path.exists(dest_path):
                skipped_existing += 1
            else:
                shutil.copy2(full_path, dest_path)
                per_class[cls_name] = per_class.get(cls_name, 0) + 1

        records = logger.load_all_entries(config)
        matched = [
            r for r in records if (r["Class"], r["Video_ID"]) in all_keys
        ]
        dest_csv_path = os.path.join(dest_dir, "source_references.csv")
        with open(dest_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=logger.CSV_HEADER, extrasaction="ignore"
            )
            writer.writeheader()
            writer.writerows(matched)

        return {
            "copied": sum(per_class.values()),
            "skipped_existing": skipped_existing,
            "per_class": per_class,
            "metadata_rows": len(matched),
        }

    # Link-only mode export: write accepted_links.txt per class/language, master all_accepted_links.txt, and CSV
    records = logger.load_all_entries(config)
    decisions = logger.load_decisions(config)

    accepted_records = []
    per_class = {}
    per_class_lang_urls = {}
    per_class_urls = {}
    all_urls = []

    for r in records:
        cls_name = r["Class"]
        lang = r["Language"]
        vid = r["Video_ID"]
        url = r["Source_URL"]
        status = logger.get_decision_status(decisions, cls_name, lang, vid, url)
        if status != "accepted":
            continue

        accepted_records.append(r)
        per_class[cls_name] = per_class.get(cls_name, 0) + 1

        lang_list = per_class_lang_urls.setdefault((cls_name, lang), [])
        if url not in lang_list:
            lang_list.append(url)

        cls_list = per_class_urls.setdefault(cls_name, [])
        if url not in cls_list:
            cls_list.append(url)

        if url not in all_urls:
            all_urls.append(url)

    for (cls_name, lang), urls in per_class_lang_urls.items():
        target_dir = os.path.join(dest_dir, cls_name, lang)
        os.makedirs(target_dir, exist_ok=True)
        with open(
            os.path.join(target_dir, "accepted_links.txt"), "w", encoding="utf-8"
        ) as f:
            for u in urls:
                f.write(u + "\n")

    for cls_name, urls in per_class_urls.items():
        target_dir = os.path.join(dest_dir, cls_name)
        os.makedirs(target_dir, exist_ok=True)
        with open(
            os.path.join(target_dir, "accepted_links.txt"), "w", encoding="utf-8"
        ) as f:
            for u in urls:
                f.write(u + "\n")

    with open(
        os.path.join(dest_dir, "all_accepted_links.txt"), "w", encoding="utf-8"
    ) as f:
        for u in all_urls:
            f.write(u + "\n")

    dest_csv_path = os.path.join(dest_dir, "source_references.csv")
    with open(dest_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=logger.CSV_HEADER, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(accepted_records)

    return {
        "copied": len(accepted_records),
        "skipped_existing": 0,
        "per_class": per_class,
        "metadata_rows": len(accepted_records),
    }
