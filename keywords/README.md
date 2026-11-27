# Keyword Files

Use UTF-8 YAML files named `keywords_<language>.yaml`, where the suffix is a two-letter code such as `en`, `es`, or `ko`. Each file maps class names to the search phrases used to find videos in that language. For setup and the first collection run, see the [main quick start](../README.md#quick-start).

```yaml
Class_Name:
  - "first search phrase"
  - "second search phrase"

Another_Class:
  - "another search phrase"
```

Copy the template to a language-specific filename and edit the class names and phrases. Keep class names consistent across files when they refer to the same category. Use spaces for YAML indentation and quotes around phrases. Match the class name exactly in CLI commands, with quotes if it contains spaces. [Keyword template](keywords_--.yaml)

For example, `keywords_ko.yaml` might contain these phrases.

```yaml
Origami:
  - "종이배 접는 법"

Drawing:
  - "연필로 정육면체 그리는 법"
```

Set `keywords_file` under `project:` to `"./keywords/keywords_ko.yaml"`. When you collect, this file gives the new entries the `ko` label. Open them with `python collect.py review --language ko`. [Collect in another language](../README.md#collect-in-another-language)
