# Leonard

A Jekyll site for Leonard the Emotional Support Fry.

## Documentation

- [Leonard image and sticker guidelines](docs/leonard-image-guidelines.md)
  are the source of truth for generating, editing, and evaluating Leonard
  sticker art and website-only image assets.

## Develop

This site expects Ruby 3.2.

```bash
script/check-ruby
script/test-and-preview
```

Open `http://127.0.0.1:4000/leonard/` for the local preview.

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
