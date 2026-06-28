# Leonard

A Jekyll site for Leonard the Emotional Support Fry.

## Documentation

- [Leonard image and sticker guidelines](docs/leonard-image-guidelines.md)
  are the source of truth for generating, editing, and evaluating Leonard
  sticker art and website-only image assets.

## Day One Field Notes

Use the repo skill at `.codex/skills/dayone-field-notes/` to import Day One
export ZIP files into Field Notes without manual copy/paste. Start with a
dry-run, then apply only after the target post and banner decision look right:

```bash
python3 .codex/skills/dayone-field-notes/scripts/import_dayone_field_note.py ~/Downloads/export.zip --repo .
python3 .codex/skills/dayone-field-notes/scripts/import_dayone_field_note.py ~/Downloads/export.zip --repo . --apply
```

## Develop

This site expects Ruby 3.2.

```bash
script/check-ruby
script/test-and-preview
```

Open `http://127.0.0.1:4000/` for the local preview.

Run the same checks GitHub Pages runs without starting a server:

```bash
script/test-and-preview --check-only
```

The local workflow requires Ruby 3.2, Bundler, and BATS. On macOS, install
missing tools with:

```bash
brew install ruby@3.2 bats-core
gem install bundler
```
