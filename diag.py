import sys
import os
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Path: {sys.path}", flush=True)
try:
    import pandas
    print("Pandas imported", flush=True)
except ImportError as e:
    print(f"Pandas Missing: {e}", flush=True)

try:
    import modules.logic
    print("Modules Logic Imported", flush=True)
except ImportError as e:
    print(f"Modules Logic Missing: {e}", flush=True)
