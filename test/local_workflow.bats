#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
  export STUB_BIN="$BATS_TEST_TMPDIR/bin"
  export HOMEBREW_ROOT="$BATS_TEST_TMPDIR/homebrew"
  export NEWFIRE_HOMEBREW_PREFIXES="$HOMEBREW_ROOT"
  export COMMAND_LOG="$BATS_TEST_TMPDIR/commands.log"

  mkdir -p "$STUB_BIN"
  export PATH="$STUB_BIN:/usr/bin:/bin"

  write_ruby_stub "$STUB_BIN" "3.2.9"
  write_bundle_stub
  write_bats_stub
  write_git_stub
}

write_ruby_stub() {
  local bin_dir="$1"
  local ruby_version="$2"

  mkdir -p "$bin_dir"
  cat > "$bin_dir/ruby" <<SCRIPT
#!/usr/bin/env bash
set -euo pipefail

if [[ "\${1:-}" == "-e" ]]; then
  printf '%s' "$ruby_version"
else
  printf 'ruby %s\n' "$ruby_version"
fi
SCRIPT
  chmod +x "$bin_dir/ruby"
}

write_bundle_stub() {
  cat > "$STUB_BIN/bundle" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

printf 'bundle %s\n' "$*" >> "$COMMAND_LOG"

if [[ "${1:-}" == "exec" && "${2:-}" == "jekyll" && "${3:-}" == "serve" ]]; then
  printf 'stub serve\n'
fi
SCRIPT
  chmod +x "$STUB_BIN/bundle"
}

write_git_stub() {
  cat > "$STUB_BIN/git" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

printf 'git %s\n' "$*" >> "$COMMAND_LOG"
SCRIPT
  chmod +x "$STUB_BIN/git"
}

write_bats_stub() {
  cat > "$STUB_BIN/bats" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

printf 'bats %s\n' "$*" >> "$COMMAND_LOG"
SCRIPT
  chmod +x "$STUB_BIN/bats"
}

@test "repo pins Ruby 3.2" {
  run tr -d '[:space:]' < "$REPO_ROOT/.ruby-version"

  [ "$status" -eq 0 ]
  [[ "$output" == "3.2" ]]
}

@test "test-and-preview check-only runs all local checks without serving" {
  run "$REPO_ROOT/script/test-and-preview" --check-only

  [ "$status" -eq 0 ]
  [[ "$(cat "$COMMAND_LOG")" == $'bundle install\nbats test\nbundle exec jekyll build\ngit diff --check' ]]
  [[ "$output" != *"Preview URL:"* ]]
}

@test "test-and-preview starts local preview after checks pass" {
  run "$REPO_ROOT/script/test-and-preview" --host 0.0.0.0 --port 4100

  [ "$status" -eq 0 ]
  [[ "$(cat "$COMMAND_LOG")" == *$'git diff --check\nbundle exec jekyll serve --livereload --host 0.0.0.0 --port 4100' ]]
  [[ "$output" == *"Preview URL: http://0.0.0.0:4100/"* ]]
}

@test "test-and-preview supports skipping bundle install" {
  run "$REPO_ROOT/script/test-and-preview" --check-only --skip-install

  [ "$status" -eq 0 ]
  [[ "$(cat "$COMMAND_LOG")" == $'bats test\nbundle exec jekyll build\ngit diff --check' ]]
}

@test "with-ruby runs commands through the repo Ruby setup" {
  run "$REPO_ROOT/script/with-ruby" ruby -e "print RUBY_VERSION"

  [ "$status" -eq 0 ]
  [[ "$output" == "3.2.9" ]]
}

@test "test-and-preview documents the local workflow" {
  run "$REPO_ROOT/script/test-and-preview" --help

  [ "$status" -eq 0 ]
  [[ "$output" == *"bundle install"* ]]
  [[ "$output" == *"bats test"* ]]
  [[ "$output" == *"bundle exec jekyll build"* ]]
  [[ "$output" == *"bundle exec jekyll serve"* ]]
}
