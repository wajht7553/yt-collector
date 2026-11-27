# YouTube Link Collection Toolkit

Find YouTube videos using your own search phrases, review them in a browser, and export the accepted results. Collection saves links and metadata to a local catalog. During review, videos play directly from YouTube. When you want local video files, run `download-accepted` after review.

[Quick start](#quick-start) · [Collect more videos](#collect-more-videos) · [Review your queue](#review-your-queue) · [Export and download](#export-and-download) · [Configuration](#configuration) · [Troubleshooting](#troubleshooting)

## Quick start

### 1. Set up the tool

Download or clone this repository, then open a terminal in the folder containing `collect.py`. You need Python, a browser, and an internet connection for YouTube searches and playback. Use Python 3.11–3.14 with the dependencies in this repository. [Python downloads](https://www.python.org/downloads/)

**Windows PowerShell**

```powershell
python -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
.\env\Scripts\python.exe collect.py --help
```

If you use the Windows `py` launcher, select your installed version in the first line, for example `py -3.14 -m venv env`. The examples call the virtual environment's Python directly, so PowerShell activation is optional.

**macOS or Linux**

```bash
python3 -m venv env
./env/bin/python -m pip install -r requirements.txt
./env/bin/python collect.py --help
```

Install **Deno** for yt-dlp's YouTube JavaScript challenges. Open a new terminal and run `deno --version` to check that it is available. If you plan to download accepted videos, also install **FFmpeg** and check it with `ffmpeg -version`. yt-dlp uses FFmpeg when it needs to merge separate audio and video streams. [Deno installation](https://docs.deno.com/runtime/getting_started/installation/) · [yt-dlp YouTube setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS) · [FFmpeg downloads](https://ffmpeg.org/download.html)

### 2. Create a sample project

To continue an existing project, use its current config and keyword files and skip to [Collect more videos](#collect-more-videos).

For the sample project, create `project.yaml` next to `collect.py` and paste the settings below. [Project configuration template](project.example.yaml)

```yaml
project:
  name: "YouTube Review Demo"
  keywords_file: "./keywords/keywords_en.yaml"
  target_per_class: 2
  max_duration_seconds: 600
  output_dir: "./data"
```

Create `keywords/keywords_en.yaml` and save it as UTF-8. Each top-level name is a category, called a **class** in the tool. The indented lines under it are the YouTube search phrases for that class. [Keyword file guide](keywords/README.md)

```yaml
Origami:
  - "easy origami paper boat tutorial"

Drawing:
  - "how to draw a cube step by step"
```

### 3. Collect links and open the reviewer

**Windows PowerShell**

```powershell
.\env\Scripts\python.exe collect.py init
.\env\Scripts\python.exe collect.py collect --all --max-per-keyword 3 --no-cookies
.\env\Scripts\python.exe collect.py status
.\env\Scripts\python.exe collect.py review --language en
```

**macOS or Linux**

```bash
./env/bin/python collect.py init
./env/bin/python collect.py collect --all --max-per-keyword 3 --no-cookies
./env/bin/python collect.py status
./env/bin/python collect.py review --language en
```

If YouTube returns enough eligible results, you will get up to two links per class. New links start as **Pending**. The last command opens the review page at `http://127.0.0.1:8765`. If the tab does not open automatically, paste the address printed in your terminal into a browser on the same computer. Keep that terminal open while reviewing. Press **Ctrl+C** there when you finish.

Click a video's play button, then choose **Accept** or **Reject**. Try this on at least one video before exporting. See [Review your queue](#review-your-queue) for filters and shortcuts.

The rest of this guide uses `python` in commands. Use it after activating the virtual environment, or substitute `.\env\Scripts\python.exe` on Windows or `./env/bin/python` on macOS and Linux.

## Collect more videos

Pick the command that matches what you want to collect. The examples use the classes from the quick start. Replace them with the exact names from your own keyword file.

| To do this | Run this command |
| --- | --- |
| Search the keywords for every class | `python collect.py collect --all --no-cookies` |
| Search the keywords for one class | `python collect.py collect --class Origami --no-cookies` |
| Try a different search phrase | `python collect.py collect --class Drawing --keyword "pencil shading basics" --max-per-keyword 5 --no-cookies` |
| Add one known YouTube video | `python collect.py collect --class Drawing --url "https://www.youtube.com/watch?v=H7nYSsVFQWo" --no-cookies` |
| Check saved links and review counts | `python collect.py status` |

Bulk collection uses the keyword file selected in `project.yaml`. Within each class and language, it stops when the number of **Pending** plus **Accepted** links reaches `target_per_class`. Rejected links are excluded from that count. A direct URL or one-off keyword search can add links beyond the bulk target. `--max-per-keyword` controls how many YouTube results the tool asks for per search and defaults to 10. Duplicates and duration filtering can result in fewer saved links. Run a new search phrase or raise the search limit if you need more candidates.

The catalog stores one entry per class, language, and YouTube video ID. A repeat match adds any new keyword and keeps the existing review decision. The same video can have separate decisions in different classes or languages.

### Collect in another language

1. Create a file such as `keywords/keywords_ko.yaml`. Use the same class names for categories that carry over, then write the search phrases in Korean or your chosen language.
2. Copy `project.yaml` to `project_ko.yaml`. Change `keywords_file` to `"./keywords/keywords_ko.yaml"` and keep the same `output_dir` to add the results to the same catalog.
3. Run the collection command with the alternate config, then open a review session for that language.

```bash
python collect.py --config project_ko.yaml collect --all --no-cookies
python collect.py review --language ko
```

Each collection run uses one keyword file. The two-letter filename suffix is the **search language label**. When the spoken language matters, check it during review. Use a different `output_dir` when you want a separate project, with its own catalog and review decisions. Put `--config PATH` before the command name whenever you select a different config.

## Review your queue

```bash
python collect.py review
python collect.py review --language en
python collect.py review --language ko --port 8766
```

Use the class and status filters to focus the queue. In an unrestricted session with multiple languages, the page starts with the config's language if it is present in the catalog. Choose **All Languages** to see the full catalog. A session started with `--language` contains only that language.

| Status | What it means |
| --- | --- |
| **Pending** | The video awaits a decision. **Undo** returns a reviewed video here. |
| **Accepted** | The video is included in the next accepted export or download batch. |
| **Rejected** | The video is excluded from the next accepted export or download batch. |

Decisions are saved immediately and are available when you reopen the reviewer. For keyboard review, use **A** to accept, **R** to reject, **U** to undo, **↑ / ↓** to move between cards, and **Space** to open the focused video's player. Click the review page outside the embedded player to use the review shortcuts again.

If the embedded player cannot play a video, try **Open on YouTube** on its card. Some videos allow playback only on YouTube itself, and private or removed videos may be unavailable. [YouTube player errors](https://developers.google.com/youtube/iframe_api_reference#onError)

## Export and download

Run one of these commands after accepting videos.

| To get | Run |
| --- | --- |
| A CSV of accepted links and metadata | `python collect.py export --dest ./exported_data` |
| The CSV and local copies of accepted videos | `python collect.py download-accepted` |
| The CSV and videos in a custom folder | `python collect.py download-accepted --dest "./My Dataset"` |

Both commands read **every accepted entry in the selected catalog**, across classes and languages. A reviewer filter or `review --language` applies only to the review session. Use separate catalogs if you need independent export batches for each language.

With the default download destination, you will see these files.

```text
exported_data/
├── accepted_links.csv
└── videos/
    ├── <video files>
    └── .download-archive.txt
```

- **CSV.** Each export replaces `accepted_links.csv` with a snapshot of current acceptances. It includes class, language, YouTube ID, source URL, access date, license, keyword, title, channel, and duration in seconds when known. A video can appear in several rows when it has multiple keywords or accepted labels.
- **Videos.** The downloader saves one copy for each distinct accepted YouTube ID in the batch. The output format and resolution follow yt-dlp's automatic selection.
- **Archive.** Rerun `download-accepted` with the same destination after accepting more videos or after an interrupted download. yt-dlp skips completed IDs recorded in that destination's `videos/.download-archive.txt`. The media folder accumulates successful downloads across runs. Use a fresh destination to download a new set based on the current decisions.

The accepted CSV is written before media downloads begin. Check the terminal for download errors, especially when a video has become unavailable.

## Configuration

Put the settings below under `project:` in your YAML file. The defaults in this table apply when you omit an optional setting.

| Key | Required or default | What it controls |
| --- | --- | --- |
| `name` | Required | The project name shown in the terminal and reviewer. |
| `keywords_file` | Required | The keyword YAML, such as `./keywords/keywords_en.yaml`. A relative path is resolved from the config file's folder. |
| `target_per_class` | Required | Bulk collection target for each class and language. Use a positive whole number. |
| `description` | Optional text | A short note about the project. |
| `output_dir` | `./data` | Folder for `catalog.sqlite3`. Point configs here to share a catalog. A relative path is resolved from the terminal's current folder. |
| `max_duration_seconds` | `3600` | Skips results with a known duration above this number. Use `0` to disable the duration limit. |
| `sleep_interval` | `[5, 15]` | Minimum and maximum seconds to wait between keyword searches. Use two numbers in brackets. |
| `browser` | `chrome` | Browser to read cookies from during collection when `cookies_file` is empty. Override it for one collection run with e.g. `--browser firefox`. |
| `cookies_file` | Empty | Path to a Netscape-format cookies file. Relative paths are resolved from the terminal's current folder. |
| `enable_remote_components` | `true` | Allows yt-dlp to fetch its YouTube JavaScript solver from GitHub. |

### YouTube sign-in

For a public search, start with `collect --no-cookies` as in the quick start. If the request requires sign-in, run collection with the browser option, such as `python collect.py collect --all --browser firefox`. A configured `cookies_file` takes precedence over browser cookies. `--no-cookies` disables both sources for collection.

`download-accepted` uses `cookies_file` when it is set and otherwise makes an unauthenticated request. Keep exported cookies private because they contain sign-in information. [yt-dlp guide to exporting YouTube cookies](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies)

### Where the tool saves your work

- `<output_dir>/catalog.sqlite3` stores collected links, keywords, metadata, and review decisions. With the sample config, this is `data/catalog.sqlite3`.
- `project.yaml` and your keyword YAML files describe how to collect. Back them up with the SQLite catalog to move or restore a project. Stop the reviewer and finish running commands before copying the catalog.
- The export destination is separate from the catalog. Keep the media folder and its download archive together if you want to resume downloads in a copy of the destination.

## Command reference

Run `python collect.py --help` to list commands or `python collect.py <command> --help` for the options to one command.

| Command | Purpose and options |
| --- | --- |
| `init` | Create the catalog using the selected config. |
| `collect` | Save YouTube links and metadata. Choose `--all` or `--class NAME`. With `--class`, optionally pass `--keyword TEXT` or `--url URL`. Also accepts `--max-per-keyword N`, `--browser NAME`, and `--no-cookies`. |
| `status` | Show pending, accepted, and rejected counts by class and language. |
| `review` | Start the local browser reviewer. Optional `--language CODE` and `--port PORT`. |
| `export` | Write accepted links and metadata to the required `--dest PATH` directory. |
| `download-accepted` | Export the CSV and download accepted videos. Optional `--dest PATH` defaults to `./exported_data`. |
| `download` | Compatibility alias for `collect`. |
| `dedup` and `clean` | Compatibility commands. The catalog handles deduplication and saves decisions immediately. |

## Troubleshooting

| What you see | What to check |
| --- | --- |
| `Config file not found` | Run from the folder containing `collect.py` and `project.yaml`, or use `--config PATH` before the command. |
| `Keywords file not found` or `Unknown class` | Check the path in `keywords_file` and the exact top-level class name in that YAML file. A name with spaces needs quotes in a command. |
| `No module named yaml` or `No module named yt_dlp` | Re-run the dependency install from step 1. Use the same virtual environment's Python to run the tool. |
| YouTube asks you to sign in or cookie loading fails | For public videos, try collection with `--no-cookies`. For requests that require sign-in, check the browser setting or use a fresh cookies file as described under [YouTube sign-in](#youtube-sign-in). |
| yt-dlp reports a JavaScript challenge or a missing runtime | Run `deno --version` in the same terminal and check `enable_remote_components`. If your network cannot reach GitHub release assets, see the local solver installation option. [yt-dlp JavaScript setup](https://github.com/yt-dlp/yt-dlp/wiki/EJS) |
| The reviewer is empty | Run `status` to confirm links exist. Check `output_dir`, the selected language, and class and status filters. |
| The review port is already in use | Stop the earlier session with **Ctrl+C** or start a new one with `python collect.py review --port 8766`. |
| The export has no video rows | Check `status` for accepted entries in the selected catalog, then run the export again. |
| yt-dlp reports FFmpeg is missing | Install FFmpeg, verify `ffmpeg -version` in the same terminal, and retry `download-accepted`. [FFmpeg downloads](https://ffmpeg.org/download.html) |
| yt-dlp says a video is already in the archive but the file is missing | Choose a new `--dest` to download the current accepted set again. |
