# Validate the hand-built Python Callaway & Sant'Anna estimator against the R `did` package
# (Callaway & Sant'Anna's own implementation).
#
# Inputs (made by make_validation_data.py, in this folder):
#   panel_balanced.csv  2017-2020, competitors observed every year  -> should match exactly
#   panel_full.csv      2010-2023 unbalanced panel                  -> should be close
#   python_estimates.csv  the Python estimator's results on the same data and settings
#
# Settings on both sides: never-movers as controls, no covariates, unweighted,
# year-before ("varying") base for placebo periods, movers up and down estimated separately.
#
# Run from Terminal:   Rscript validate_did.R
# Output: did_estimates.csv, comparison.csv, and a summary printed to the screen.

options(warn = 1)
if (!requireNamespace("did", quietly = TRUE)) {
  message("Installing the 'did' package from CRAN (one time only)...")
  install.packages("did", repos = "https://cloud.r-project.org")
}
suppressPackageStartupMessages(library(did))

# folder this script lives in
args <- commandArgs(trailingOnly = FALSE)
file_arg <- sub("^--file=", "", args[grep("^--file=", args)])
here <- if (length(file_arg)) dirname(normalizePath(file_arg)) else getwd()
setwd(here)

set.seed(20261109)
outcomes <- c("sub_win", "sub_loss", "sub_any")
rows <- list()
add <- function(...) rows[[length(rows) + 1]] <<- data.frame(...)

for (ds in c("balanced", "full")) {
  panel <- read.csv(sprintf("panel_%s.csv", ds))
  for (dr in c("up", "down")) {
    sub <- panel[panel$direction %in% c(dr, "never"), ]
    sub$g <- ifelse(sub$direction == dr, sub$cohort, 0)
    for (y in outcomes) {
      res <- tryCatch({
        suppressWarnings(att_gt(
          yname = y, tname = "Year", idname = "id", gname = "g", data = sub,
          panel = TRUE, allow_unbalanced_panel = (ds == "full"),
          control_group = "nevertreated", base_period = "varying",
          est_method = "reg", bstrap = TRUE, biters = 999, cband = FALSE,
          print_details = FALSE))
      }, error = function(e) e)
      if (inherits(res, "error")) {
        message(sprintf("att_gt failed for %s / %s / %s: %s", ds, dr, y, conditionMessage(res)))
        next
      }
      add(dataset = ds, direction = dr, outcome = y, type = "att_gt",
          g = res$group, t = res$t, e = res$t - res$group, estimate = res$att, se = res$se)
      s <- aggte(res, type = "simple", na.rm = TRUE)
      add(dataset = ds, direction = dr, outcome = y, type = "simple",
          g = NA, t = NA, e = NA, estimate = s$overall.att, se = s$overall.se)
      dyn <- aggte(res, type = "dynamic", na.rm = TRUE)
      add(dataset = ds, direction = dr, outcome = y, type = "dynamic",
          g = NA, t = NA, e = dyn$egt, estimate = dyn$att.egt, se = dyn$se.egt)
      cat(sprintf("done: %-8s %-4s %-8s  did simple ATT = %+.4f (se %.4f)\n",
                  ds, dr, y, s$overall.att, s$overall.se))
    }
  }
}

did_est <- do.call(rbind, rows)
write.csv(did_est, "did_estimates.csv", row.names = FALSE)

py <- read.csv("python_estimates.csv")
keys <- c("dataset", "direction", "outcome", "type", "g", "t", "e")
for (k in c("g", "t", "e")) { py[[k]] <- as.integer(py[[k]]); did_est[[k]] <- as.integer(did_est[[k]]) }
py$g[py$type != "att_gt"] <- NA; py$t[py$type != "att_gt"] <- NA
did_est$g[did_est$type != "att_gt"] <- NA; did_est$t[did_est$type != "att_gt"] <- NA
cmp <- merge(py, did_est, by = keys, suffixes = c("_python", "_did"))
cmp <- cmp[!is.na(cmp$estimate_python) & !is.na(cmp$estimate_did), ]
cmp$diff <- cmp$estimate_python - cmp$estimate_did
write.csv(cmp, "comparison.csv", row.names = FALSE)

cat("\n==================== COMPARISON: Python vs R did ====================\n")
for (ds in c("balanced", "full")) {
  for (ty in c("att_gt", "simple", "dynamic")) {
    x <- cmp[cmp$dataset == ds & cmp$type == ty, ]
    if (!nrow(x)) next
    cat(sprintf("%-8s %-8s  %4d estimates compared | largest gap %.6f | mean gap %.6f (share points)\n",
                ds, ty, nrow(x), max(abs(x$diff)), mean(abs(x$diff))))
  }
}
cat("\nOverall (simple) ATT, Python vs did:\n")
s <- cmp[cmp$type == "simple", c("dataset", "direction", "outcome",
                                 "estimate_python", "estimate_did", "se_python", "se_did")]
s[, 4:7] <- round(s[, 4:7], 4)
print(s, row.names = FALSE)
cat("\nExpect: balanced = identical estimates (gaps ~0); full = close but not identical,\n",
    "because did treats the unbalanced panel as repeated cross-sections.\n",
    "Standard errors differ slightly by design (did uses a multiplier bootstrap).\n", sep = "")
