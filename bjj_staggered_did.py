"""
Run the full analysis.

    python3 bjj_staggered_did.py data.csv [results_folder]

The code lives in the bjj_did package; the settings are in bjj_did/config.py.
Needs numpy, pandas and matplotlib.
"""
import sys

from bjj_did import main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "results")
