#!/usr/bin/env bats

setup() {
  export REPO_ROOT="$BATS_TEST_DIRNAME/.."
  export STUB_BIN="$BATS_TEST_TMPDIR/bin"
  export HOMEBREW_ROOT="$BATS_TEST_TMPDIR/homebrew"
  export NEWFIRE_HOMEBREW_PREFIXES="$HOMEBREW_ROOT"

  mkdir -p "$STUB_BIN"
  export PATH="$STUB_BIN:/usr/bin:/bin"
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
  local bin_dir="$1"

  mkdir -p "$bin_dir"
  cat > "$bin_dir/bundle" <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
printf 'stub bundle\n'
SCRIPT
  chmod +x "$bin_dir/bundle"
}

write_homebrew_ruby() {
  local prefix="$1"
  local major_minor="$2"
  local ruby_version="$3"
  local ruby_bin="$prefix/opt/ruby@$major_minor/bin"
  local gem_bin="$prefix/lib/ruby/gems/$major_minor.0/bin"

  write_ruby_stub "$ruby_bin" "$ruby_version"
  write_bundle_stub "$gem_bin"
}

@test "repo pins Ruby 3.2" {
  run tr -d '[:space:]' < "$REPO_ROOT/.ruby-version"

  [ "$status" -eq 0 ]
  [[ "$output" == "3.2" ]]
}

@test "ruby-env keeps an already-active matching Ruby" {
  write_ruby_stub "$STUB_BIN" "3.2.9"
  write_bundle_stub "$STUB_BIN"

  run bash -c 'source "$REPO_ROOT/script/ruby-env"; ruby -e "print RUBY_VERSION"; command -v bundle'

  [ "$status" -eq 0 ]
  [[ "$output" == *"3.2.9"* ]]
  [[ "$output" == *"$STUB_BIN/bundle"* ]]
}

@test "ruby-env activates Homebrew Ruby when active Ruby is wrong" {
  write_ruby_stub "$STUB_BIN" "2.6.10"
  write_homebrew_ruby "$HOMEBREW_ROOT" "3.2" "3.2.9"

  run bash -c 'source "$REPO_ROOT/script/ruby-env"; ruby -e "print RUBY_VERSION"; command -v bundle'

  [ "$status" -eq 0 ]
  [[ "$output" == *"3.2.9"* ]]
  [[ "$output" == *"$HOMEBREW_ROOT/lib/ruby/gems/3.2.0/bin/bundle"* ]]
}

@test "ruby-env reports the Homebrew install command when Ruby is unavailable" {
  write_ruby_stub "$STUB_BIN" "2.6.10"

  run bash -c 'source "$REPO_ROOT/script/ruby-env"'

  [ "$status" -eq 69 ]
  [[ "$output" == *"Install with: brew install ruby@3.2"* ]]
}

@test "with-ruby runs commands after Homebrew Ruby activation" {
  write_ruby_stub "$STUB_BIN" "2.6.10"
  write_homebrew_ruby "$HOMEBREW_ROOT" "3.2" "3.2.9"

  run "$REPO_ROOT/script/with-ruby" ruby -e "print RUBY_VERSION"

  [ "$status" -eq 0 ]
  [[ "$output" == "3.2.9" ]]
}
