#!/bin/bash
# Double-click to run the R validation. Output is also saved to validation_log.txt.
cd "$(dirname "$0")"
RS="$(command -v Rscript)"
[ -z "$RS" ] && [ -x /usr/local/bin/Rscript ] && RS=/usr/local/bin/Rscript
[ -z "$RS" ] && [ -x /opt/homebrew/bin/Rscript ] && RS=/opt/homebrew/bin/Rscript
[ -z "$RS" ] && [ -x /Library/Frameworks/R.framework/Resources/bin/Rscript ] && RS=/Library/Frameworks/R.framework/Resources/bin/Rscript
if [ -z "$RS" ]; then echo "Could not find Rscript. Is R installed?" | tee validation_log.txt; exit 1; fi
echo "Using $RS"
"$RS" validate_did.R 2>&1 | tee validation_log.txt
echo; echo "Finished. You can close this window."
