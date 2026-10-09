"""Vercel serverless entry point — expoe o Flask app como WSGI."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
