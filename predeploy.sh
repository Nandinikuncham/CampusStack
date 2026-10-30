#!/usr/bin/env bash
set -euo pipefail

python backend/manage.py migrate --noinput
