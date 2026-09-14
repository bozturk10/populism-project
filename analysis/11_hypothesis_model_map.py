"""Create a compact, manuscript-ready map of the H1-H2 model sequence."""

from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "figures" / "hypotheses_model_map.png"


def add_row(
    ax: plt.Axes,
    *,
    y: float,
    label: str,
    model: str,
    formula: str,
    formula_size: float = 13.0,
) -> None:
    """Add one row to the compact model table."""
    ax.text(
        0.055,
        y,
        label,
        color="#1D232A",
        fontsize=15.5,
        fontweight="bold",
        va="center",
        transform=ax.transAxes,
    )
    ax.text(
        0.145,
        y,
        model,
        color="#1D232A",
        fontsize=14.0,
        fontweight="bold",
        va="center",
        ha="center",
        transform=ax.transAxes,
    )
    ax.text(
        0.22,
        y,
        formula,
        color="#22272E",
        fontsize=formula_size,
        family="monospace",
        va="center",
        transform=ax.transAxes,
    )


def add_definition(
    ax: plt.Axes,
    *,
    x: float,
    y: float,
    variable: str,
    description: str,
) -> None:
    """Add one variable-definition entry below the model table."""
    ax.text(
        x,
        y,
        variable,
        color="#1D232A",
        fontsize=10.7,
        family="monospace",
        fontweight="bold",
        va="top",
        transform=ax.transAxes,
    )
    ax.text(
        x,
        y - 0.045,
        description,
        color="#363B41",
        fontsize=9.5,
        va="top",
        transform=ax.transAxes,
    )


def main() -> None:
    """Render the figure to the project outputs directory."""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        }
    )

    fig, ax = plt.subplots(figsize=(13.2, 5.2), dpi=220)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.axis("off")

    for y in (0.96, 0.82, 0.68, 0.54):
        ax.plot(
            [0.025, 0.975],
            [y, y],
            color="#AEB4BA",
            linewidth=1.0,
            transform=ax.transAxes,
        )
    ax.plot(
        [0.105, 0.105],
        [0.54, 0.96],
        color="#D0D4D8",
        linewidth=0.8,
        transform=ax.transAxes,
    )
    ax.plot(
        [0.185, 0.185],
        [0.54, 0.96],
        color="#D0D4D8",
        linewidth=0.8,
        transform=ax.transAxes,
    )

    for x, label, alignment in (
        (0.055, "Hypothesis", "center"),
        (0.145, "Model", "center"),
        (0.22, "Specification", "left"),
    ):
        ax.text(
            x,
            0.93,
            label,
            fontsize=9.5,
            fontweight="bold",
            ha=alignment,
            transform=ax.transAxes,
        )

    add_row(
        ax,
        y=0.87,
        label="H1",
        model="M1",
        formula="voted_populist ~ distrust_index_three + controls",
    )
    add_row(
        ax,
        y=0.73,
        label="H2a",
        model="M2",
        formula="voted_populist ~ distrust_index_three + viepol + controls",
    )
    add_row(
        ax,
        y=0.59,
        label="H2b",
        model="M3",
        formula=(
            "voted_populist ~ distrust_index_three + viepol + wpestop + votedir "
            "+ controls"
        ),
        formula_size=11.4,
    )

    ax.text(
        0.055,
        0.485,
        "Controls",
        color="#1D232A",
        fontsize=13.0,
        fontweight="bold",
        va="center",
        transform=ax.transAxes,
    )
    ax.text(
        0.22,
        0.485,
        "age_decades_50 + C(gndr) + C(eisced_model) + C(cntry)",
        color="#22272E",
        fontsize=11.5,
        family="monospace",
        va="center",
        transform=ax.transAxes,
    )
    ax.text(
        0.22,
        0.440,
        (
            "age_decades_50: age in decades centred at 50 · gndr: gender · "
            "eisced_model: education · cntry: country fixed effects"
        ),
        color="#363B41",
        fontsize=9.2,
        va="center",
        transform=ax.transAxes,
    )
    ax.plot(
        [0.025, 0.975],
        [0.39, 0.39],
        color="#AEB4BA",
        linewidth=1.0,
        transform=ax.transAxes,
    )
    ax.text(
        0.025,
        0.355,
        "Variable definitions",
        color="#1D232A",
        fontsize=11.5,
        fontweight="bold",
        va="top",
        transform=ax.transAxes,
    )
    add_definition(
        ax,
        x=0.055,
        y=0.305,
        variable="voted_populist",
        description=(
            "Binary outcome: 1 = populist-party vote; "
            "0 = non-populist-party vote."
        ),
    )
    add_definition(
        ax,
        x=0.055,
        y=0.205,
        variable="distrust_index_three",
        description=(
            "Mean of 10 − trstprl, 10 − trstplt, and 10 − trstprt; "
            "higher values mean greater distrust.\n"
            "trstprl = parliament · trstplt = politicians · trstprt = political parties"
        ),
    )
    add_definition(
        ax,
        x=0.52,
        y=0.305,
        variable="viepol",
        description="People-over-elite representational priority (0–10).",
    )
    add_definition(
        ax,
        x=0.52,
        y=0.205,
        variable="wpestop",
        description="Unrestricted popular-sovereignty orientation (0–10).",
    )
    add_definition(
        ax,
        x=0.52,
        y=0.105,
        variable="votedir",
        description="Direct-democracy orientation through referendums (0–10).",
    )
    fig.savefig(OUTPUT, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
