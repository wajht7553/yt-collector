# YouTube Video Collection Toolkit

A config-driven CLI tool for collecting, organizing, and reviewing YouTube videos for dataset building. No code changes needed — just edit `project.yaml` and run.

## Quick Start

```bash
# 1. Edit project.yaml with your classes and keywords
# 2. Initialize the project
python collect.py init

# 3. Download videos for a class
python collect.py download --class MyClass --no-cookies

# 4. Download all classes
python collect.py download --all --no-cookies

# 5. Check progress
python collect.py status

# 6. Review collected videos in browser
python collect.py review

# 7. Clean up duplicates
python collect.py dedup
```

## Requirements

- Python 3.10+
- yt-dlp (`pip install yt-dlp`)
- PyYAML (`pip install pyyaml`)
- FFmpeg (for video/audio merging)

## Configuration

Edit `project.yaml` to define your dataset:

```yaml
project:
  name: "My Dataset"
  target_per_class: 200
  resolution: 720
  max_duration_seconds: 3600
  browser: chrome
  cookies_file: ""
  enable_remote_components: true

classes:
  My_Class:
    description: "What this class represents"
    keywords:
      category_1:
        - "search keyword 1"
        - "search keyword 2"
      category_2:
        - "search keyword 3"
```

Keywords can be grouped by category (for organization) or listed flat — both work.

## Commands

| Command | Description |
|---|---|
| `python collect.py init` | Create folder structure from config |
| `python collect.py download --class X` | Download all keywords for a class |
| `python collect.py download --all` | Download all classes |
| `python collect.py download --class X --keyword "q"` | Search a specific keyword |
| `python collect.py download --class X --url "..."` | Download a specific video |
| `python collect.py status` | Show collection progress |
| `python collect.py review` | Launch video review UI in browser |
| `python collect.py dedup` | Remove duplicate references |
| `python collect.py clean` | Move rejected videos to `_rejected/` |

## Download Options

| Flag | Description |
|---|---|
| `--no-cookies` | Skip browser cookie authentication |
| `--browser edge` | Use Edge instead of Chrome for cookies |
| `--max-per-keyword 15` | Download up to 15 videos per keyword |

You can also set browser and cookie behavior in `project.yaml`:

```yaml
project:
  browser: chrome
  cookies_file: ""  # optional cookies.txt to avoid closing your browser
```

When `cookies_file` is set, the downloader uses it instead of live browser cookies.

## Folder Structure

After `collect.py init`, the toolkit creates:

```
data/
├── Class_1/
│   └── Videos/
├── Class_2/
│   └── Videos/
├── source_references.csv
└── review_decisions.json
```

## Review Tool

The built-in review tool (`collect.py review`) opens a web UI at `http://localhost:8765`:

- **Click-to-play**: Videos only load when you click (saves bandwidth)
- **Pagination**: 20 videos per page, page-based navigation
- **Keyboard shortcuts**: `A` accept, `R` reject, `U` undo, `↑↓` navigate, `Space` play
- **Filters**: Filter by class and review status
- **Persistent**: Decisions saved to `review_decisions.json`
