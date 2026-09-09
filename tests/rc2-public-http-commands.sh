#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
mkdir "$TMP/bin"
ln -s "$ROOT/tests/rc2-mock-curl" "$TMP/bin/curl"

COMMAND=$(node --input-type=module - <<'JS'
import crypto from 'node:crypto';
import {buildMirrorCommand, MIRROR_ROOT} from './releases/2.1.0-rc.2/assets/distribution.mjs';
const body = 'valid-body';
process.stdout.write(buildMirrorCommand({
  path: 'artifacts/test.bin', bytes: body.length,
  sha256: crypto.createHash('sha256').update(body).digest('hex'),
  urls: [`${MIRROR_ROOT}test.bin`],
}));
JS
)

run_command() {
  case_dir=$1; mode=$2; payload=$3
  mkdir "$TMP/$case_dir"
  (cd "$TMP/$case_dir" && PATH="$TMP/bin:$PATH" MOCK_MODE="$mode" MOCK_PAYLOAD="$payload" bash -c "$COMMAND")
}

run_command success success valid-body
test -f "$TMP/success/test.bin"
test ! -e "$TMP/success/test.bin.partial"

if run_command hash-error success '<html>bad!'; then
  exit 1
fi
test ! -e "$TMP/hash-error/test.bin"
test -f "$TMP/hash-error/test.bin.partial"

if run_command wrapper success '<html>bad!'; then
  exit 1
fi
test ! -e "$TMP/wrapper/test.bin"
test -f "$TMP/wrapper/test.bin.partial"

if run_command download-error failure valid-body; then
  exit 1
fi
test ! -e "$TMP/download-error/test.bin"
test -f "$TMP/download-error/test.bin.partial"

mkdir "$TMP/existing"
printf '%s' owner-bytes > "$TMP/existing/test.bin"
if (cd "$TMP/existing" && PATH="$TMP/bin:$PATH" MOCK_PAYLOAD=valid-body bash -c "$COMMAND"); then
  exit 1
fi
test "$(<"$TMP/existing/test.bin")" = owner-bytes

mkdir "$TMP/partial"
printf '%s' old-partial > "$TMP/partial/test.bin.partial"
if (cd "$TMP/partial" && PATH="$TMP/bin:$PATH" MOCK_PAYLOAD=valid-body bash -c "$COMMAND"); then
  exit 1
fi
test "$(<"$TMP/partial/test.bin.partial")" = old-partial

mkdir "$TMP/symlink"
printf '%s' owner-bytes > "$TMP/target"
ln -s "$TMP/target" "$TMP/symlink/test.bin"
if (cd "$TMP/symlink" && PATH="$TMP/bin:$PATH" MOCK_PAYLOAD=valid-body bash -c "$COMMAND"); then
  exit 1
fi
test -L "$TMP/symlink/test.bin"

mkdir "$TMP/dangling-symlink"
ln -s "$TMP/missing-target" "$TMP/dangling-symlink/test.bin"
if (cd "$TMP/dangling-symlink" && PATH="$TMP/bin:$PATH" MOCK_PAYLOAD=valid-body bash -c "$COMMAND"); then
  exit 1
fi
test -L "$TMP/dangling-symlink/test.bin"

mkdir "$TMP/partial-symlink"
printf '%s' owner-bytes > "$TMP/target-partial"
ln -s "$TMP/target-partial" "$TMP/partial-symlink/test.bin.partial"
if (cd "$TMP/partial-symlink" && PATH="$TMP/bin:$PATH" MOCK_PAYLOAD=valid-body bash -c "$COMMAND"); then
  exit 1
fi
test -L "$TMP/partial-symlink/test.bin.partial"

printf '%s\n' 'RC2 generated HTTP command tests: PASS'
