from dotenv import load_dotenv

load_dotenv()
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
"""Terminal entry point.

Reads ``dataset/claims.csv``, runs each row through the agent pipeline, and
writes structured predictions to ``output.csv``. See AGENTS.md §6 for the
evaluable-submission contract.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import agent
import output
