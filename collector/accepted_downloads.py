"""Download the videos in an accepted catalog snapshot."""

import subprocess
import sys

from . import search


def download(config, videos, output_dir):
    urls = dict.fromkeys(search.watch_url(video["video_id"]) for video in videos)
    if not urls:
        print("No accepted videos to download.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
        "--no-overwrites", "--paths", str(output_dir),
        "--download-archive", str(output_dir / ".download-archive.txt"),
        "--batch-file", "-",
    ]
    if config["cookies_file"]:
        command += ["--cookies", config["cookies_file"]]
    if config["enable_remote_components"]:
        command += ["--remote-components", "ejs:github"]

    print(f"Checking {len(urls)} unique accepted videos for download to {output_dir}", flush=True)
    try:
        subprocess.run(command, input="\n".join(urls) + "\n", encoding="utf-8", check=True)
    except OSError as exc:
        raise RuntimeError(f"Could not start yt-dlp: {exc}") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"yt-dlp exited with code {exc.returncode}. Rerun the same command to retry."
        ) from exc
