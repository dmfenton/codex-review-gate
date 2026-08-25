#!/usr/bin/env bash
set -euo pipefail

actionlint
python3 -m unittest discover -s tests -q
