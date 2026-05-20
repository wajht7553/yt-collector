# YouTube Video Collection Toolkit

A config-driven CLI for collecting, organizing, and reviewing YouTube videos for dataset building. Edit `project.yaml` and run the CLI.

## Setup

1. Create a virtual environment:

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

3. Install FFmpeg (required for video/audio merging) and ensure it is on PATH.

Runtime dependencies:
- FFmpeg must be installed and available on PATH for merges.
- A browser-supported cookies export is needed if YouTube requires sign-in. Visit [Cookies Setup Guide](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).
- A JavaScript runtime (Deno or Node.js) may be required for yt-dlp JS challenges.

## Configuration

Copy `project.example.yaml` to `project.yaml` and edit it to define your dataset and download behavior:

```yaml
project:
  name: "My Dataset"
  target_per_class: 200
  resolution: 720
  max_duration_seconds: 3600
  browser: chrome
  cookies_file: ""  # optional cookies.txt to avoid closing your browser
  enable_remote_components: true
  sleep_interval: [10, 20]
  output_dir: "./data"

classes:
  My_Class:
    description: "What this class represents"
    keywords:
      category_1:
        - "search keyword 1"
        - "search keyword 2"
```

Keywords can be grouped by category or listed flat.

## Usage

```bash
python collect.py init
python collect.py download --class MyClass
python collect.py download --all
python collect.py status
python collect.py review
python collect.py dedup
python collect.py clean
```

Optional flags:

```bash
python collect.py download --class MyClass --keyword "q"
python collect.py download --class MyClass --url "..."
python collect.py download --class MyClass --max-per-keyword 15
python collect.py download --class MyClass --no-cookies
python collect.py download --class MyClass --browser edge
```

## Review Tool

The review UI runs at `http://localhost:8765`:

- Click-to-play, so videos only stream on demand
- Pagination (20 per page)
- Keyboard shortcuts: `A` accept, `R` reject, `U` undo, `↑↓` navigate, `Space` play
- Filters by class and review status
