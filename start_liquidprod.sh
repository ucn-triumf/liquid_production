#!/bin/bash
# Set up the virtual environment shared by all scripts in this directory.
#
# On first run, creates a .venv next to this script, installs the PyPI
# dependencies listed in requirements.txt, and installs the MIDAS python client
# (editable) from $MIDASSYS/python. On later runs the existing .venv is simply
# activated (no re-install) before launching the script.

set -euo pipefail

# Resolve the directory this script lives in, so it works from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# The MIDAS python client is not on PyPI; it comes from the MIDAS install.
if [[ -z "${MIDASSYS:-}" ]]; then
    echo "Error: MIDASSYS is not set. Set it to your MIDAS installation and retry." >&2
    exit 1
fi
if [[ ! -f "$MIDASSYS/python/setup.py" ]]; then
    echo "Error: '$MIDASSYS/python/setup.py' not found. Is MIDASSYS correct?" >&2
    exit 1
fi

# Create and populate the venv only if it does not already exist.
if [[ ! -d "$VENV_DIR" ]]; then
    echo "Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"

    # Activate before installing so packages land in the venv.
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"

    # Install dependencies: pip itself, the PyPI packages, then MIDAS (editable).
    pip install --upgrade pip
    pip install -r "$SCRIPT_DIR/requirements.txt"
    pip install -e "$MIDASSYS/python"
else
    # Existing venv: just activate it, no re-install needed.
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
fi

cd "$SCRIPT_DIR"

python3 liquid_prod_rate.py
