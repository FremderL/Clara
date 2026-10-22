from __future__ import annotations

import re
from pathlib import Path

from viernes_app.core.simulation_engine import SimulationChart


def render_chart(chart: SimulationChart, output_dir: Path, slug: str) -> SimulationChart:
    """Renderiza una grafica PNG si matplotlib esta disponible."""

    if not chart.labels or not chart.values:
        return chart
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", slug).strip("-") or "grafica"
    target = output_dir / f"{safe_slug}.png"
    try:
        import matplotlib

        matplotlib.use("Agg")
        from matplotlib import pyplot as plt

        fig, ax = plt.subplots(figsize=(7, 4), dpi=120)
        if chart.chart_type == "line":
            ax.plot(chart.labels, chart.values, marker="o", color="#2563eb")
        else:
            ax.bar(chart.labels, chart.values, color="#2563eb")
        ax.set_title(chart.title)
        if chart.y_label:
            ax.set_ylabel(chart.y_label)
        ax.grid(axis="y", alpha=0.25)
        fig.autofmt_xdate(rotation=30, ha="right")
        fig.tight_layout()
        fig.savefig(target)
        plt.close(fig)
        return SimulationChart(
            title=chart.title,
            chart_type=chart.chart_type,
            labels=list(chart.labels),
            values=list(chart.values),
            y_label=chart.y_label,
            path=str(target),
        )
    except Exception:
        return chart
