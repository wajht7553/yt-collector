"""Export a snapshot of accepted YouTube links and their metadata."""

import csv
from pathlib import Path
from tempfile import NamedTemporaryFile

from . import catalog, search


CSV_HEADER = (
    "Class", "Language", "Video_ID", "Source_URL", "Date_Accessed",
    "License", "Keyword", "Title", "Channel", "Duration",
)


def export_dataset(db, destination):
    videos = catalog.list_videos(db, status="accepted")
    return write_accepted_csv(videos, destination), len(videos)


def write_accepted_csv(videos, destination):
    path = Path(destination) / "accepted_links.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = NamedTemporaryFile(
        mode="w", newline="", encoding="utf-8", dir=path.parent, delete=False
    )
    temp_path = Path(temp.name)
    try:
        with temp:
            writer = csv.writer(temp)
            writer.writerow(CSV_HEADER)
            for video in videos:
                for keyword in video["keywords"] or [""]:
                    writer.writerow((
                        video["class_name"], video["language"], video["video_id"],
                        search.watch_url(video["video_id"]), video["date_accessed"],
                        video["license"], keyword, video["title"], video["channel"],
                        video["duration"],
                    ))
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path
