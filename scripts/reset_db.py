"""Reset database — drop all tables and re-seed."""
import os
import sys
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "seed_db.py"), "--reset"])
