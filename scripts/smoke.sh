#!/usr/bin/env bash
set -euo pipefail
python ai_tuner_toolkit_dyno_v1_2.py --selftest
python selftest.py
