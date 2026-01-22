import os

# Prevent host Python environment variables from breaking embedded Python.
for key in ("PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "PYTHONEXECUTABLE"):
    os.environ.pop(key, None)
