#!/usr/bin/env python3
"""RS3 JARVIS — root launcher.

Usage::

    python run_jarvis.py                       # uses config.yaml in this directory
    python run_jarvis.py --config my.yaml      # custom config
    python run_jarvis.py --log-level DEBUG     # verbose logging

First time?  Run the setup wizard first::

    python scripts/setup_rs3.py
"""

import sys
from pathlib import Path

# Ensure the package is importable when run from the project root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from openjarvis.rs3.main import main  # noqa: E402

if __name__ == "__main__":
    main()
