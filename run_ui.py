import sys
import os
import subprocess

# Ensure the root directory is at the top of sys.path
current_dir = os.path.abspath(os.path.dirname(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Run streamlit
subprocess.run([sys.executable, "-m", "streamlit", "run", "ui/app.py", "--server.port", "8501"])
