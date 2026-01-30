#! /bin/bash
set -e

bough graph --workspace tests/fixtures/sample-workspace --repo tests/fixtures/sample-workspace
bough analyze --workspace tests/fixtures/sample-workspace --repo tests/fixtures/sample-workspace
