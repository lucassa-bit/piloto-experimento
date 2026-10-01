"""Statistical helpers — exploratory / future-ready; not confirmatory for the pilot."""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from analysis import config


def clustered_bootstrap_ci(
    values: np.ndarray,
    clusters: np.ndarray,
    *,
    statistic: Callable[[np.ndarray], float] | None = None,
    n_boot: int = 2000,
    seed: int = config.ANALYSIS_SEED,
    alpha: float = 0.05,
    min_clusters_for_ci: int = 10,
) -> dict[str, Any]:
    """
    Clustered bootstrap CI (exploratory).

    With few clusters (e.g. n_user_stories=4 in the pilot), a CI is often
    methodologically inadequate — this function refuses a precise-looking interval
    unless cluster count ≥ min_clusters_for_ci, while remaining ready for larger studies.
    """
    statistic = statistic or (lambda x: float(np.mean(x)))
    values = np.asarray(values)
    clusters = np.asarray(clusters)
    unique = np.unique(clusters)
    n_clusters = len(unique)
    point = statistic(values)

    result: dict[str, Any] = {
        "estimate": point,
        "n_clusters": n_clusters,
        "n_boot": n_boot,
        "seed": seed,
        "alpha": alpha,
        "ci_low": None,
        "ci_high": None,
        "status": "ok",
        "note": "EXPLORATÓRIO — não interpretar como precisão confirmatória no piloto.",
    }

    if n_clusters < min_clusters_for_ci:
        result["status"] = "skipped_insufficient_clusters"
        result["note"] = (
            f"Bootstrap clusterizado não reportado: n_clusters={n_clusters} "
            f"< min_clusters_for_ci={min_clusters_for_ci}. "
            "Função pronta para o estudo principal com mais User Stories / gaps."
        )
        return result

    rng = np.random.default_rng(seed)
    boot_stats = np.empty(n_boot, dtype=float)
    cluster_to_idx = {c: np.where(clusters == c)[0] for c in unique}

    for b in range(n_boot):
        sampled = rng.choice(unique, size=n_clusters, replace=True)
        idx = np.concatenate([cluster_to_idx[c] for c in sampled])
        boot_stats[b] = statistic(values[idx])

    low = float(np.quantile(boot_stats, alpha / 2))
    high = float(np.quantile(boot_stats, 1 - alpha / 2))
    result["ci_low"] = low
    result["ci_high"] = high
    return result


def exploratory_inferential_models_disabled() -> dict[str, str]:
    """Document options for the main study; do not auto-run confirmatory tests."""
    return {
        "section": "Exploratory inferential models — disabled for pilot",
        "disabled": (
            "Friedman, Wilcoxon, ANOVA, Kruskal-Wallis, and pairwise batteries "
            "are NOT executed automatically in this pilot."
        ),
        "rationale": (
            "Pilot is methodological validation with n=4 User Stories; "
            "confirmatory inference would be inappropriate."
        ),
        "future_options": (
            "For the main study: pre-register contrasts; use mixed models or "
            "cluster-robust inference; control multiplicity; avoid treating Gap×Run "
            "rows as independent."
        ),
    }


def fit_mixed_logit_recognized_future(
    matrix: pd.DataFrame,
    *,
    enabled: bool = False,
) -> dict[str, Any]:
    """
    Placeholder for a future logistic mixed-effects model.

    Conceptual model:
      logit(P(recognized)) = β0 + β1 gap_state + β2 condition + β3 category + ...
                            + random intercept(UserStory)
                            + random intercept(Gap nested in UserStory)

    NOT used as a primary pilot result.
    """
    if not enabled:
        return {
            "status": "experimental/future",
            "enabled": False,
            "message": (
                "Mixed-effects logistic model infrastructure reserved for the main study. "
                "Not fitted in the pilot."
            ),
            "outcome": "recognized ∈ {0,1}",
            "fixed_effects_candidates": [
                "gap_state",
                "condition",
                "gap_category",
                "importance",
            ],
            "random_effects_candidates": [
                "user_story_id",
                "gap_id nested within user_story_id",
            ],
            "n_rows_available": len(matrix),
        }

    # Experimental path only when explicitly enabled (main study).
    try:
        import statsmodels.formula.api as smf  # type: ignore
    except ImportError as exc:
        return {"status": "error", "message": f"statsmodels required: {exc}"}

    df = matrix.copy()
    df["recognized"] = df["recognized"].astype(int)
    # statsmodels MixedLM is for linear; binomial GLMM often needs other packages.
    # Keep explicit experimental note rather than a misleading fit.
    return {
        "status": "experimental/future",
        "enabled": True,
        "message": (
            "Fitting a proper binomial GLMM is deferred to a dedicated main-study "
            "module (e.g. statsmodels BinomialBayesMixedGLM or pymer4/R lme4). "
            f"statsmodels available: {getattr(smf, '__name__', 'ok')}"
        ),
        "n_rows": len(df),
    }
