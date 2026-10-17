#!/usr/bin/env bash
# Type check the integration and fail only on mypy errors that are not
# listed in mypy-baseline.txt. Used by CI and the pre-commit hook.
#
# After fixing baselined errors, refresh the baseline with:
#   mypy custom_components/hcu_integration | mypy-baseline sync
set -euo pipefail

cd "$(dirname "$0")/.."

output="$(mktemp)"
trap 'rm -f "$output"' EXIT

set +e
mypy custom_components/hcu_integration >"$output"
status=$?
set -e

# mypy exits 1 when it finds errors and 2 when it crashes.
if [ "$status" -gt 1 ]; then
  cat "$output"
  exit "$status"
fi

mypy-baseline filter <"$output"
