#!/usr/bin/env python3
"""
Narrative Factory CLI - AI-powered storytelling engine

Usage:
    python factory.py --help
    python factory.py generate "Chapter seed text"
    python factory.py status
    python factory.py review <job_id>
    python factory.py approve <job_id>
"""

import typer
from src.cli.commands import app

if __name__ == "__main__":
    app()