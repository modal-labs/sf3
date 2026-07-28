from __future__ import annotations

from pathlib import Path
from typing import Any

from matplotlib.axes import Axes
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure

FIGURE_BACKGROUND = "#181818"
AXES_BACKGROUND = "#222222"
TEXT_PRIMARY = "#d1d1d1"
TEXT_SECONDARY = "#a3a3a3"
BORDER_PRIMARY = "#464646"
BORDER_DIVIDER = "#272727"
BAR_COLORS = (
    "#adeaab",
    "#d9866b",
    "#ffc1f7",
    "#4aa19d",
    "#decb6c",
    "#4fbe5f",
    "#648fe0",
    "#8d324c",
)
HEATMAP_COLORS = (
    "#f87171",
    "#d18e50",
    "#d1c05f",
    "#6ac345",
    "#7fee64",
)
BAD_CELL = "#2f2f2f"
HEATMAP_GRID = "#181818"
HEATMAP_TEXT = "#181818"


def apply_dark_style(figure: Figure, axes: Axes) -> None:
    figure.patch.set_facecolor(FIGURE_BACKGROUND)
    axes.set_facecolor(AXES_BACKGROUND)
    axes.title.set_color(TEXT_PRIMARY)
    axes.xaxis.label.set_color(TEXT_PRIMARY)
    axes.yaxis.label.set_color(TEXT_PRIMARY)
    axes.tick_params(colors=TEXT_SECONDARY, which="both")
    for spine in axes.spines.values():
        spine.set_color(BORDER_PRIMARY)
    axes.title.set_fontsize(13)


def save_figure(figure: Figure, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    figure.savefig(
        temporary,
        format="png",
        dpi=180,
        bbox_inches="tight",
        facecolor=figure.get_facecolor(),
        edgecolor="none",
    )
    temporary.replace(path)


def write_elo_plot(report: dict[str, Any], path: Path) -> None:
    rankings = report["rankings"]
    labels = [row["label"] for row in rankings]
    ratings = [float(row["elo"]) for row in rankings]

    figure = Figure(figsize=(max(7.0, len(rankings) * 1.7), 5.5))
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    apply_dark_style(figure, axes)
    bars = axes.bar(
        range(len(rankings)),
        ratings,
        color=[BAR_COLORS[index % len(BAR_COLORS)] for index in range(len(rankings))],
        edgecolor=BORDER_PRIMARY,
        linewidth=0.8,
    )
    axes.bar_label(
        bars,
        labels=[f"{rating:.1f}" for rating in ratings],
        padding=4,
        color=TEXT_PRIMARY,
    )
    axes.set_xticks(range(len(rankings)), labels=labels, rotation=20, ha="right")
    axes.set_ylim(0, max(ratings) * 1.12)
    axes.set_ylabel("Elo rating")
    axes.set_title("Tournament Elo Rankings")
    axes.grid(axis="y", color=BORDER_DIVIDER, linewidth=0.8)
    axes.set_axisbelow(True)
    figure.tight_layout()
    save_figure(figure, path)


def write_win_rate_plot(report: dict[str, Any], path: Path) -> None:
    rankings = report["rankings"]
    players = [row["player"] for row in rankings]
    labels = [row["label"] for row in rankings]
    win_rates = report["win_rate_matrix"]
    matrix = [
        [
            float("nan")
            if win_rates[player][opponent] is None
            else win_rates[player][opponent]
            for opponent in players
        ]
        for player in players
    ]

    size = max(7.0, len(players) * 1.5)
    figure = Figure(figsize=(size + 1.0, size))
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    apply_dark_style(figure, axes)
    colormap = LinearSegmentedColormap.from_list("modal_win_rate", HEATMAP_COLORS)
    colormap.set_bad(BAD_CELL)
    image = axes.imshow(
        matrix,
        cmap=colormap,
        vmin=0.0,
        vmax=1.0,
        interpolation="nearest",
    )
    colorbar = figure.colorbar(image, ax=axes, fraction=0.046, pad=0.04)
    colorbar.set_label("Win rate", color=TEXT_PRIMARY)
    colorbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])
    colorbar.set_ticklabels(["0%", "25%", "50%", "75%", "100%"])
    colorbar.ax.yaxis.set_tick_params(color=TEXT_SECONDARY, labelcolor=TEXT_SECONDARY)
    colorbar.outline.set_edgecolor(BORDER_PRIMARY)
    colorbar.ax.set_facecolor(AXES_BACKGROUND)

    axes.set_xticks(
        range(len(players)),
        labels=labels,
        rotation=30,
        ha="right",
        rotation_mode="anchor",
    )
    axes.set_yticks(range(len(players)), labels=labels)
    axes.set_xlabel("Opponent")
    axes.set_ylabel("Player")
    axes.set_title("Tournament Match Win Rates")
    boundaries = [index - 0.5 for index in range(len(players) + 1)]
    axes.set_xticks(boundaries, minor=True)
    axes.set_yticks(boundaries, minor=True)
    axes.grid(which="minor", color=HEATMAP_GRID, linewidth=2)
    axes.tick_params(which="minor", bottom=False, left=False)

    for row, player in enumerate(players):
        for column, opponent in enumerate(players):
            value = win_rates[player][opponent]
            label = "N/A" if value is None else f"{value:.0%}"
            color = TEXT_SECONDARY if value is None else HEATMAP_TEXT
            axes.text(column, row, label, ha="center", va="center", color=color)

    figure.tight_layout()
    save_figure(figure, path)


def write_tournament_plots(report: dict[str, Any], output_dir: Path) -> list[Path]:
    paths = [output_dir / "elo.png", output_dir / "win_rate_matrix.png"]
    write_elo_plot(report, paths[0])
    write_win_rate_plot(report, paths[1])
    return paths
