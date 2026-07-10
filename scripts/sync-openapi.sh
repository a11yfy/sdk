#!/usr/bin/env bash
# Az OpenAPI spec szinkronja a fő repóból + SDK-regenerálás.
# Használat: ./scripts/sync-openapi.sh [main-repo-út]
set -euo pipefail

MAIN_REPO="${1:-$HOME/projektek/a11yfy}"
SPEC_SRC="$MAIN_REPO/web/static/openapi.json"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

[ -f "$SPEC_SRC" ] || { echo "Nem található: $SPEC_SRC" >&2; exit 1; }

cp "$SPEC_SRC" "$HERE/fern/openapi/openapi.json"
echo "✓ openapi.json szinkronizálva ($SPEC_SRC)"

cd "$HERE"
fern check
fern generate --group local --local
echo "✓ SDK-k újragenerálva (sdks/python, sdks/typescript)"
echo "Futtasd a teszteket: (cd sdks/python && uv run pytest) ; (cd sdks/typescript && npm test)"
