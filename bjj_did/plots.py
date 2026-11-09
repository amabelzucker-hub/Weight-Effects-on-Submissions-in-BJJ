"""Event-study charts, one PNG per outcome."""
import re


def plot_events(ev, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colors = {"up": "#4C78A8", "down": "#D9762B"}
    for y, s in ev.groupby("outcome"):
        fig, ax = plt.subplots(figsize=(6, 3.6), dpi=150)
        ax.axhline(0, color="#888", lw=0.8)
        ax.axvline(-0.5, color="#bbb", lw=0.8, ls="--")
        for dr, sd in s.groupby("direction"):
            off = -0.06 if dr == "up" else 0.06
            # placebo points (hollow) and after-move points (filled) are drawn as separate
            # lines: the reference year between them has no point of its own
            for part, face, label in [(sd[sd.e < 0], "white", None), (sd[sd.e >= 0], colors[dr], f"moved {dr}")]:
                if part.empty:
                    continue
                ax.errorbar(part.e + off, part.att, yerr=[part.att - part.lo, part.hi - part.att], fmt="o-",
                            color=colors[dr], mfc=face, capsize=0, lw=1.5, elinewidth=1, alpha=.9, label=label)
        ax.legend(frameon=False, fontsize=8)
        ax.text(0.01, 0.02, "hollow = placebo checks (before the move)", transform=ax.transAxes,
                fontsize=7, color="#777")
        ax.set_xlabel("Years relative to changing class")
        ax.set_ylabel("ATT (share of matches)")
        ax.set_title(y, fontsize=10)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out / f"event_{re.sub(r'[^a-z0-9]+', '_', y.lower()).strip('_')}.png")
        plt.close(fig)
