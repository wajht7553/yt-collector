# YouTube Video Collection Toolkit

A config-driven CLI for collecting, organizing, and reviewing YouTube videos (or video link manifests) for dataset building. Edit `project.yaml` and run the CLI.

## Setup

1. Create a virtual environment, for example:

```bash
python -m venv env
```

2. Activate it and install dependencies:

```bash
# Windows
env\Scripts\activate

# macOS / Linux
source env/bin/activate

pip install -r requirements.txt
```

3. Install FFmpeg (required for video/audio merging when downloading full videos) and ensure it is on PATH.

Runtime dependencies:
- FFmpeg must be installed and available on PATH for video merges.
- A browser-supported cookies export is needed if YouTube requires sign-in. Visit [Cookies Setup Guide](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).
- A JavaScript runtime (Deno or Node.js) may be required for yt-dlp JS challenges.

## Configuration

### Project Config (project.yaml)

Rename `project.example.yaml` to `project.yaml` and edit it to define your dataset and collection behavior:

```yaml
project:
  name: "My Dataset"
  description: "Dataset description"
  keywords_file: "./keywords/keywords_en.yaml"  # Path to language-specific keywords file
  target_per_class: 200
  # Optional per-class target overrides:
  # class_targets:
  #   Class_1: 180
  #   Class_2: 270
  resolution: 720
  min_duration_seconds: 0
  max_duration_seconds: 3600
  links_only: false  # Set to true to save only video links & metadata without downloading video files
  browser: chrome
  cookies_file: ""  # optional cookies.txt to avoid closing your browser
  video_only: false
  enable_remote_components: true
  sleep_interval: [10, 20]
  output_dir: "./data"
  # Optional list of terms to exclude from video titles during search:
  # exclude_title_terms:
  #   - "tutorial"
  #   - "how to"
```

**Note:** Class names are automatically derived from the keywords file. You don't need to define a `classes` section.

### Link-Only Mode (`links_only: true` or `--links-only`)

If you prefer to collect and review YouTube URLs without downloading `.mp4` files upfront:
- Set `links_only: true` in `project.yaml` (or pass `--links-only` to `python collect.py download`).
- Collected URLs are saved per class and language in `data/<Class>/<lang>/links.txt` along with full metadata (`Video_ID`, `Source_URL`, `Title`, `Channel`, `Duration`, `Keyword`) in `data/source_references.csv`.
- The **Review UI** (`python collect.py review`) plays collected video links directly in the browser (via embedded YouTube player or direct `yt-dlp` stream) and syncs your decisions into `accepted_links.txt`, `rejected_links.txt`, and `pending_links.txt` (ready for batch downloading later with `yt-dlp -a accepted_links.txt`).

### Keywords File (keywords/keywords_*.yaml)

Keywords are stored in separate language files under the `keywords/` directory. The `keywords_file` setting in `project.yaml` points to the file to use. Note that each keyword file must be named `keywords_<language>.yaml`, where `<language>` is a two-letter language code (e.g., `en` for English, `es` for Spanish). The default template is `keywords_--.yaml`.

**Structure of keyword files:**
```yaml
Class_1:
  - "search keyword 1"
  - "search keyword 2"
  - "search keyword 3"

Class_2:
  - "search keyword 4"
  - "search keyword 5"
```

### Switching Languages

To use different language keywords:

1. Copy and rename a keywords file (e.g., `keywords_es.yaml` for Spanish)
2. Update the keywords in your language
3. Update `project.yaml`: `keywords_file: "./keywords/keywords_es.yaml"`
4. Run your collector — it automatically loads the new language keywords

See `keywords/keywords_--.yaml` for a starting template when creating new language files.

## Usage

```bash
python collect.py init # Initialize the project and create the output directory
python collect.py download --class MyClass # Download videos (or collect links) for a specific class
python collect.py download --all # Download videos (or collect links) for all classes
python collect.py download --all --links-only # Collect only video links and metadata (no video files)
python collect.py status # Show collection status for all classes across all languages
python collect.py review # Start the review UI
python collect.py dedup # Deduplicate references
python collect.py clean # Organize accepted and rejected videos or link lists
python collect.py export --dest "./exported_data" # Export accepted videos/links to a destination directory
```

If you are using this repo while it is under active development, pull updates periodically:

```bash
git pull
```

Optional flags:

```bash
python collect.py download --class MyClass --keyword "q"
python collect.py download --class MyClass --url "..."
python collect.py download --class MyClass --max-per-keyword 15
python collect.py download --class MyClass --no-cookies
python collect.py download --class MyClass --browser edge
python collect.py download --class MyClass --links-only
python collect.py export --dest "./exported_data"
```

## Review Tool

The review UI runs at `http://localhost:8765`:

- Plays both local downloaded video files and collected YouTube links directly in the card (supports instant **YouTube Embed** playback and **Direct Stream via `yt-dlp`**)
- Shows YouTube thumbnails, duration badges, channel names, search keywords, and a direct `↗ YouTube` link
- Click-to-play, so videos only stream on demand
- Keyboard shortcuts: `A` accept, `R` reject, `U` undo, `↑↓` (or `J`/`K`) navigate, `Space` play
- Filters by class, language, and review status
