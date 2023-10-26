#! /bin/sh
find ./src -name package.json -not -path "*/node_modules/*" -exec bash -c "npm --prefix \$(dirname {}) install --no-audit" \;