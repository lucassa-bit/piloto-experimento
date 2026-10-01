"""Publication-oriented figures for the pilot analysis."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis import config


def _save(fig: plt.Figure, stem: str, figures_dir: Path) -> list[Path]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for ext in ("png", "pdf"):
        path = figures_dir / f"{stem}.{ext}"
        fig.savefig(path, dpi=config.FIGURE_DPI, bbox_inches="tight")
        paths.append(path)
    plt.close(fig)
    return paths


def plot_questions_by_condition(
    questions: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    counts = questions.groupby("condition").size().reindex(
        sorted(questions["condition"].unique())
    )
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(counts.index.astype(str), counts.values, color="#4C72B0")
    ax.set_xlabel("Condição")
    ax.set_ylabel("Número de perguntas")
    ax.set_title("Perguntas por condição (piloto)")
    return _save(fig, "questions-by-condition", figures_dir)


def plot_gap_recall_by_condition(
    recall_table: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    df = recall_table.copy()
    fig, ax = plt.subplots(figsize=(7, 4))
    x = df["condition"].astype(str)
    y = df["gap_recall"].astype(float)
    # N/A → omit from bar height but annotate
    heights = [v if pd.notna(v) else 0.0 for v in y]
    bars = ax.bar(x, heights, color="#55A868")
    for bar, val in zip(bars, y):
        label = "N/A" if pd.isna(val) else f"{val:.2f}"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.set_ylim(0, 1.15)
    ax.set_xlabel("Condição")
    ax.set_ylabel("Gap Recall (OPEN, run-level)")
    ax.set_title("Gap Recall de gaps OPEN por condição")
    return _save(fig, "gap-recall-by-condition", figures_dir)


def plot_requery_by_condition(
    requery_table: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    df = requery_table.copy()
    fig, ax = plt.subplots(figsize=(7, 4))
    x = df["condition"].astype(str)
    y = df["requery_rate"]
    heights = [float(v) if pd.notna(v) else 0.0 for v in y]
    bars = ax.bar(x, heights, color="#C44E52")
    for bar, val in zip(bars, y):
        label = "N/A" if pd.isna(val) else f"{float(val):.2f}"
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            label,
            ha="center",
            va="bottom",
            fontsize=8,
        )
    ax.set_ylim(0, 1.15)
    ax.set_xlabel("Condição")
    ax.set_ylabel("Requery Rate (ANSWERED)")
    ax.set_title("Taxa de reconsulta de gaps ANSWERED por condição")
    return _save(fig, "requery-rate-by-condition", figures_dir)


def plot_occurrence_heatmap(
    occurrence: pd.DataFrame,
    figures_dir: Path,
    *,
    user_story_id: str | None = None,
) -> list[Path]:
    df = occurrence.copy()
    if user_story_id is not None:
        df = df[df["user_story_id"] == user_story_id]
        stem = f"occurrence-heatmap-{user_story_id}"
        title = f"OccurrenceRate — {user_story_id}"
    else:
        stem = "occurrence-heatmap-all"
        title = "OccurrenceRate — todas as User Stories"

    if df.empty:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "Sem dados", ha="center")
        ax.axis("off")
        return _save(fig, stem, figures_dir)

    pivot = df.pivot_table(
        index="gap_id",
        columns="condition",
        values="occurrence_rate",
        aggfunc="mean",
    )
    # stable column order if present
    preferred = [c for c in ["C0", "CL", "CO", "CD", "CS", "CT"] if c in pivot.columns]
    other = [c for c in pivot.columns if c not in preferred]
    pivot = pivot[preferred + other]

    fig, ax = plt.subplots(figsize=(8, max(4, 0.35 * len(pivot))))
    im = ax.imshow(pivot.values, aspect="auto", vmin=0, vmax=1, cmap="Blues")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("Condição")
    ax.set_ylabel("gap_id")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="OccurrenceRate")
    return _save(fig, stem, figures_dir)


def plot_repetition_stability(
    stability: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    order = [
        "nunca reconhecido",
        "reconhecimento raro",
        "reconhecimento frequente",
        "reconhecimento consistente",
    ]
    counts = stability["stability_label"].value_counts()
    counts = counts.reindex([o for o in order if o in counts.index]).fillna(0)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(counts.index.astype(str), counts.values, color="#8172B3")
    ax.set_ylabel("Contagem (gap × condição)")
    ax.set_title("Distribuição descritiva de estabilidade entre repetições")
    ax.tick_params(axis="x", rotation=20)
    return _save(fig, "repetition-stability", figures_dir)


def plot_none_rate_by_condition(
    final_map: pd.DataFrame,
    figures_dir: Path,
) -> list[Path]:
    df = final_map.copy()
    df["is_none"] = df["final_gap_ids"].astype(str).str.strip() == config.SPECIAL_NONE
    rates = df.groupby("condition")["is_none"].mean()
    rates = rates.reindex(sorted(rates.index))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(rates.index.astype(str), rates.values, color="#CCB974")
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("Condição")
    ax.set_ylabel("NONE rate")
    ax.set_title("Proporção de perguntas mapeadas para NONE por condição")
    return _save(fig, "none-rate-by-condition", figures_dir)
