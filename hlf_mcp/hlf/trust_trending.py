"""
Trust Trending — time-series trust metrics, trend detection, and alert thresholds.

Monitors trust scores over time using snapshots taken at regular intervals
(or on-demand) and provides statistical trend analysis, linear regression
forecasting, period-over-period comparison, and alert threshold evaluation.

Key design principles:
  - Time-series first: all analysis is based on ordered snapshots.
  - Statistical rigour: linear regression with R² confidence, standard
    deviation anomaly detection, and slope-based trend classification.
  - Operator alerts: configurable thresholds trigger WARNING or CRITICAL
    alerts for trust degradation, violation spikes, and debt growth.
  - Dashboard-ready: export_dashboard_data() provides all metrics
    needed for a real-time trust monitoring dashboard.

Integration points:
  - hlf_mcp.hlf.trust_surface.TrustSurface        → violation counts
  - hlf_mcp.hlf.trust_debt.TrustDebtQuantifier    → debt_total in snapshots
  - hlf_mcp.hlf.audit_trail.AuditTrail            → audit_completeness
  - hlf_mcp.hlf.review_proof.ReviewProof          → completeness metrics
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════════════════════════


class TrendDirection(Enum):
    """Direction of a detected trend."""
    IMPROVING = "improving"
    DEGRADING = "degrading"
    STABLE = "stable"
    VOLATILE = "volatile"


class AlertLevel(Enum):
    """Severity of a trending alert."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class TrustSnapshot:
    """A single point-in-time capture of trust metrics.

    Attributes:
        timestamp: ISO-8601 timestamp when the snapshot was taken.
        overall_trust: Aggregate trust score (0.0–1.0).
        component_scores: Per-component trust scores keyed by component name.
        violation_count: Number of active trust surface violations.
        debt_total: Current total trust debt from TrustDebtQuantifier.
        audit_completeness: Fraction of audit trail checks complete (0.0–1.0).
    """

    timestamp: str
    overall_trust: float
    component_scores: dict[str, float] = field(default_factory=dict)
    violation_count: int = 0
    debt_total: float = 0.0
    audit_completeness: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the trust snapshot."""
        return {
            "timestamp": self.timestamp,
            "overall_trust": self.overall_trust,
            "component_scores": dict(self.component_scores),
            "violation_count": self.violation_count,
            "debt_total": self.debt_total,
            "audit_completeness": self.audit_completeness,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrustSnapshot:
        """Deserialize from a dict."""
        component_scores_raw = data.get("component_scores", {})
        if isinstance(component_scores_raw, dict):
            component_scores = {str(k): float(v) for k, v in component_scores_raw.items()}
        else:
            component_scores = {}
        return cls(
            timestamp=str(data.get("timestamp", "")),
            overall_trust=float(data.get("overall_trust", 0.0)),
            component_scores=component_scores,
            violation_count=int(data.get("violation_count", 0)),
            debt_total=float(data.get("debt_total", 0.0)),
            audit_completeness=float(data.get("audit_completeness", 0.0)),
        )


@dataclass(slots=True)
class TrendReport:
    """The result of a trend analysis on a single metric.

    Attributes:
        direction: The detected trend direction.
        confidence: R² value from linear regression (0.0–1.0).
        slope: Slope of the linear regression line.
        recent_snapshots: The snapshots used in the analysis.
        anomalies: List of anomaly dicts (points > 2σ from mean).
    """

    direction: TrendDirection
    confidence: float
    slope: float
    recent_snapshots: list[TrustSnapshot] = field(default_factory=list)
    anomalies: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class TrendAlert:
    """An alert triggered by crossing a threshold.

    Attributes:
        level: Alert severity level.
        message: Human-readable alert message.
        metric: The metric that triggered the alert.
        current_value: The current value of the metric.
        threshold: The threshold that was crossed.
        triggered_at: ISO-8601 timestamp when the alert fired.
    """

    level: AlertLevel
    message: str
    metric: str
    current_value: float
    threshold: float
    triggered_at: str = ""

    def __post_init__(self) -> None:
        if not self.triggered_at:
            self.triggered_at = _iso_now()


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _iso_now() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _linear_regression(
    x_values: list[float],
    y_values: list[float],
) -> tuple[float, float, float]:
    """Compute simple linear regression: y = slope * x + intercept.

    Also computes R² (coefficient of determination) as a measure of
    goodness of fit.

    Args:
        x_values: Independent variable values.
        y_values: Dependent variable values.

    Returns:
        Tuple of (slope, intercept, r_squared).
        Returns (0.0, mean(y), 0.0) if fewer than 2 data points.
    """
    n = len(x_values)
    if n < 2:
        mean_y = sum(y_values) / n if n > 0 else 0.0
        return (0.0, mean_y, 0.0)

    mean_x = sum(x_values) / n
    mean_y = sum(y_values) / n

    # Covariance and variance
    cov = sum((x_values[i] - mean_x) * (y_values[i] - mean_y) for i in range(n))
    var_x = sum((x_values[i] - mean_x) ** 2 for i in range(n))

    if var_x == 0:
        return (0.0, mean_y, 0.0)

    slope = cov / var_x
    intercept = mean_y - slope * mean_x

    # R²
    ss_res = sum((y_values[i] - (slope * x_values[i] + intercept)) ** 2 for i in range(n))
    ss_tot = sum((y_values[i] - mean_y) ** 2 for i in range(n))

    r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return (slope, intercept, max(0.0, r_squared))


def _get_metric_values(
    snapshots: list[TrustSnapshot],
    metric: str,
) -> list[float]:
    """Extract a list of metric values from ordered snapshots.

    Args:
        snapshots: Ordered list of snapshots.
        metric: One of "overall_trust", "violation_count", "debt_total",
            "audit_completeness", or a component name from component_scores.

    Returns:
        List of float values in snapshot order.
    """
    values: list[float] = []
    base_metrics = {
        "overall_trust": lambda s: s.overall_trust,
        "violation_count": lambda s: float(s.violation_count),
        "debt_total": lambda s: s.debt_total,
        "audit_completeness": lambda s: s.audit_completeness,
    }

    if metric in base_metrics:
        for s in snapshots:
            values.append(base_metrics[metric](s))
    else:
        # Component-level metric
        for s in snapshots:
            values.append(float(s.component_scores.get(metric, 0.0)))

    return values


def _mean_and_std(values: list[float]) -> tuple[float, float]:
    """Compute mean and population standard deviation."""
    if not values:
        return (0.0, 0.0)
    mean = sum(values) / len(values)
    if len(values) < 2:
        return (mean, 0.0)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return (mean, math.sqrt(variance))


# ═══════════════════════════════════════════════════════════════════════════════
# TrustTrending — main time-series analysis engine
# ═══════════════════════════════════════════════════════════════════════════════


class TrustTrending:
    """Time-series trust monitoring with trend detection and alerting.

    Maintains an internal snapshot store and provides statistical
    analysis of trust metrics over time.

    Usage::

        trending = TrustTrending(name="prod-trending", window_size=30)
        trending.add_snapshot(snap)
        report = trending.analyze_trend(metric="overall_trust")
        alerts = trending.check_alerts()
        dashboard = trending.export_dashboard_data()
    """

    def __init__(
        self,
        name: str = "trust-trending",
        window_size: int = 30,
        alert_thresholds: dict[str, float] | None = None,
    ) -> None:
        """Initialise the trending engine.

        Args:
            name: Human-readable label for this trending instance.
            window_size: Default number of recent snapshots for trend analysis.
            alert_thresholds: Optional custom thresholds.  Defaults are:
                trust_degradation: 0.1  (slope < -threshold triggers CRITICAL)
                violation_spike: 5      (current > avg + threshold triggers WARNING)
                debt_growth: 0.2        (growth rate > threshold triggers WARNING)
        """
        self.name = name
        self.window_size = window_size
        self._snapshots: list[TrustSnapshot] = []

        if alert_thresholds is None:
            self.alert_thresholds: dict[str, float] = {
                "trust_degradation": 0.1,
                "violation_spike": 5.0,
                "debt_growth": 0.2,
            }
        else:
            self.alert_thresholds = alert_thresholds

    # ── Snapshot management ─────────────────────────────────────────────────

    def add_snapshot(self, snapshot: TrustSnapshot) -> None:
        """Add a trust snapshot to the internal time-series store.

        Snapshots are kept in insertion order.  Callers should ensure
        chronological ordering.

        Args:
            snapshot: The TrustSnapshot to record.
        """
        self._snapshots.append(snapshot)

    def recent_snapshots(self, lookback: int | None = None) -> list[TrustSnapshot]:
        """Return the most recent N snapshots.

        Args:
            lookback: Number of snapshots to return.  Defaults to window_size.

        Returns:
            Ordered list of recent snapshots.
        """
        n = lookback if lookback is not None else self.window_size
        if n <= 0:
            return []
        return self._snapshots[-n:]

    # ── Trend analysis ─────────────────────────────────────────────────────

    def analyze_trend(
        self,
        metric: str = "overall_trust",
        lookback: int | None = None,
    ) -> TrendReport:
        """Analyze the trend of a metric using linear regression.

        Computes slope, R² confidence, and detects anomalies (values
        more than 2 standard deviations from the regression line).

        Args:
            metric: Which metric to analyze ("overall_trust",
                "violation_count", "debt_total", "audit_completeness",
                or a component name).
            lookback: Number of recent snapshots to use.  Defaults to
                window_size.

        Returns:
            A TrendReport with direction, confidence, and anomaly details.
        """
        snaps = self.recent_snapshots(lookback)
        if len(snaps) < 2:
            return TrendReport(
                direction=TrendDirection.STABLE,
                confidence=0.0,
                slope=0.0,
                recent_snapshots=snaps,
            )

        values = _get_metric_values(snaps, metric)
        x_values = list(range(len(values)))

        slope, intercept, r_squared = _linear_regression(x_values, values)

        # Determine direction
        direction = self._classify_direction(slope, r_squared, values)

        # Detect anomalies (residuals > 2σ)
        predictions = [slope * x + intercept for x in x_values]
        residuals = [values[i] - predictions[i] for i in range(len(values))]
        _, std_residuals = _mean_and_std(residuals)
        std_residuals = max(std_residuals, 0.001)  # avoid division by zero

        anomalies: list[dict[str, Any]] = []
        for i, res in enumerate(residuals):
            if abs(res) > 2.0 * std_residuals:
                anomalies.append({
                    "index": i,
                    "timestamp": snaps[i].timestamp,
                    "value": values[i],
                    "expected": round(predictions[i], 4),
                    "deviation": round(res, 4),
                    "sigma": round(res / std_residuals, 2),
                })

        return TrendReport(
            direction=direction,
            confidence=r_squared,
            slope=slope,
            recent_snapshots=snaps,
            anomalies=anomalies,
        )

    def _classify_direction(
        self,
        slope: float,
        r_squared: float,
        values: list[float],
    ) -> TrendDirection:
        """Classify trend direction from slope and confidence."""
        # If R² is very low, the data is volatile / no clear trend
        if r_squared < 0.3:
            # Check raw variance to distinguish stable vs volatile
            _, std = _mean_and_std(values)
            mean_val = sum(values) / len(values) if values else 0.0
            if mean_val > 0 and std / mean_val > 0.15:
                return TrendDirection.VOLATILE
            return TrendDirection.STABLE

        threshold = 0.001
        if abs(slope) < threshold:
            return TrendDirection.STABLE
        if slope > 0:
            return TrendDirection.IMPROVING
        return TrendDirection.DEGRADING

    # ── Alert evaluation ───────────────────────────────────────────────────

    def check_alerts(self) -> list[TrendAlert]:
        """Evaluate all alert thresholds against recent data.

        Checks:
          - Trust degradation: if slope < -threshold → CRITICAL.
          - Violation spike: if current count > avg + threshold → WARNING.
          - Debt growth: if growth rate > threshold → WARNING.

        Returns:
            List of TrendAlert objects for any thresholds that fired.
        """
        alerts: list[TrendAlert] = []

        if len(self._snapshots) < 2:
            return alerts

        # ── Trust degradation ───────────────────────────────────────────
        trust_trend = self.analyze_trend(metric="overall_trust")
        degradation_threshold = self.alert_thresholds.get("trust_degradation", 0.1)
        if trust_trend.slope < -degradation_threshold:
            alerts.append(TrendAlert(
                level=AlertLevel.CRITICAL,
                message=(
                    f"Trust degradation detected: slope={trust_trend.slope:.4f} "
                    f"(threshold: {-degradation_threshold:.4f}). "
                    f"Confidence: {trust_trend.confidence:.1%}. "
                    f"Direction: {trust_trend.direction.value}."
                ),
                metric="overall_trust",
                current_value=trust_trend.slope,
                threshold=-degradation_threshold,
            ))

        # ── Violation spike ─────────────────────────────────────────────
        violation_trend = self.analyze_trend(metric="violation_count")
        spike_threshold = self.alert_thresholds.get("violation_spike", 5.0)
        if violation_trend.recent_snapshots:
            current_violations = float(violation_trend.recent_snapshots[-1].violation_count)
            violation_values = _get_metric_values(violation_trend.recent_snapshots, "violation_count")
            avg_violations, _ = _mean_and_std(violation_values)
            if current_violations > avg_violations + spike_threshold:
                alerts.append(TrendAlert(
                    level=AlertLevel.WARNING,
                    message=(
                        f"Violation spike detected: current={current_violations:.0f}, "
                        f"average={avg_violations:.1f}, "
                        f"threshold={spike_threshold:.0f} above average."
                    ),
                    metric="violation_count",
                    current_value=current_violations,
                    threshold=avg_violations + spike_threshold,
                ))

        # ── Debt growth ─────────────────────────────────────────────────
        debt_trend = self.analyze_trend(metric="debt_total")
        debt_growth_threshold = self.alert_thresholds.get("debt_growth", 0.2)
        if debt_trend.recent_snapshots:
            debt_values = _get_metric_values(debt_trend.recent_snapshots, "debt_total")
            if len(debt_values) >= 2:
                first_debt = debt_values[0]
                last_debt = debt_values[-1]
                if first_debt > 0:
                    growth_rate = (last_debt - first_debt) / first_debt
                else:
                    growth_rate = 1.0 if last_debt > 0 else 0.0
                if growth_rate > debt_growth_threshold:
                    alerts.append(TrendAlert(
                        level=AlertLevel.WARNING,
                        message=(
                            f"Debt growth rate {growth_rate:.1%} exceeds "
                            f"threshold {debt_growth_threshold:.1%}. "
                            f"Debt grew from {first_debt:.2f} to {last_debt:.2f}."
                        ),
                        metric="debt_total",
                        current_value=growth_rate,
                        threshold=debt_growth_threshold,
                    ))

        return alerts

    # ── Forecasting ────────────────────────────────────────────────────────

    def forecast(
        self,
        metric: str = "overall_trust",
        horizon: int = 7,
    ) -> list[dict[str, Any]]:
        """Project a metric forward using linear extrapolation with
        confidence bands.

        Args:
            metric: The metric to forecast.
            horizon: Number of intervals to project forward.

        Returns:
            List of dicts, each with:
                timestamp: str — projected timestamp.
                predicted: float — extrapolated value.
                lower_bound: float — predicted - 2 * std_error.
                upper_bound: float — predicted + 2 * std_error.
        """
        snaps = self.recent_snapshots()
        if len(snaps) < 2:
            return []

        values = _get_metric_values(snaps, metric)
        x_values = list(range(len(values)))
        slope, intercept, _ = _linear_regression(x_values, values)

        # Estimate standard error of the regression
        predictions = [slope * x + intercept for x in x_values]
        residuals = [values[i] - predictions[i] for i in range(len(values))]
        n = len(residuals)
        if n > 2:
            std_error = math.sqrt(sum(r * r for r in residuals) / (n - 2))
        else:
            std_error = 0.0

        # Compute average interval between snapshots
        last_ts = snaps[-1].timestamp
        forecast_results: list[dict[str, Any]] = []

        try:
            dt_last = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            dt_last = datetime.now(timezone.utc)

        # Estimate average interval from last few snapshots
        avg_interval_hours = 24.0  # default: 1 day
        if len(snaps) >= 3:
            try:
                dt_first = datetime.fromisoformat(snaps[0].timestamp.replace("Z", "+00:00"))
                total_hours = (dt_last - dt_first).total_seconds() / 3600.0
                avg_interval_hours = total_hours / max(len(snaps) - 1, 1)
            except (ValueError, TypeError):
                pass

        for i in range(1, horizon + 1):
            future_x = len(values) + i - 1
            predicted = slope * future_x + intercept
            future_dt = dt_last + timedelta(hours=avg_interval_hours * i)
            # Confidence band widening with horizon distance
            band_width = 2.0 * std_error * math.sqrt(1.0 + i / max(len(snaps), 1))

            forecast_results.append({
                "timestamp": future_dt.isoformat(),
                "predicted": round(predicted, 4),
                "lower_bound": round(max(predicted - band_width, 0.0), 4),
                "upper_bound": round(min(predicted + band_width, 1.0), 4),
            })

        return forecast_results

    # ── Period comparison ──────────────────────────────────────────────────

    def compare_periods(
        self,
        period_a_start: str,
        period_a_end: str,
        period_b_start: str,
        period_b_end: str,
    ) -> dict[str, Any]:
        """Compare two time periods across all tracked metrics.

        Args:
            period_a_start: ISO-8601 start of first period.
            period_a_end: ISO-8601 end of first period.
            period_b_start: ISO-8601 start of second period.
            period_b_end: ISO-8601 end of second period.

        Returns:
            Dict mapping metric name to:
                change_pct: float — percentage change between periods.
                direction: str — "improving", "degrading", "stable".
                significant: bool — whether the change exceeds 5%.
        """
        a_snaps = self._filter_by_period(period_a_start, period_a_end)
        b_snaps = self._filter_by_period(period_b_start, period_b_end)

        metrics_to_compare = [
            "overall_trust",
            "violation_count",
            "debt_total",
            "audit_completeness",
        ]
        result: dict[str, dict[str, Any]] = {}

        for metric in metrics_to_compare:
            a_vals = _get_metric_values(a_snaps, metric) if a_snaps else []
            b_vals = _get_metric_values(b_snaps, metric) if b_snaps else []

            a_avg = sum(a_vals) / len(a_vals) if a_vals else 0.0
            b_avg = sum(b_vals) / len(b_vals) if b_vals else 0.0

            if a_avg > 0:
                change_pct = ((b_avg - a_avg) / a_avg) * 100.0
            else:
                change_pct = 100.0 if b_avg > 0 else 0.0

            if abs(change_pct) < 1.0:
                direction = "stable"
            else:
                # For trust/audit, positive change is improving
                # For violations/debt, negative change is improving
                if metric in ("overall_trust", "audit_completeness"):
                    direction = "improving" if change_pct > 0 else "degrading"
                else:
                    direction = "improving" if change_pct < 0 else "degrading"

            result[metric] = {
                "change_pct": round(change_pct, 2),
                "direction": direction,
                "significant": abs(change_pct) >= 5.0,
                "period_a_avg": round(a_avg, 4),
                "period_b_avg": round(b_avg, 4),
            }

        return result

    def _filter_by_period(
        self,
        start: str,
        end: str,
    ) -> list[TrustSnapshot]:
        """Return snapshots whose timestamps fall within [start, end]."""
        try:
            dt_start = datetime.fromisoformat(start.replace("Z", "+00:00"))
            dt_end = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return []

        result: list[TrustSnapshot] = []
        for snap in self._snapshots:
            try:
                dt_snap = datetime.fromisoformat(snap.timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if dt_start <= dt_snap <= dt_end:
                result.append(snap)

        return result

    # ── Dashboard export ───────────────────────────────────────────────────

    def export_dashboard_data(self) -> dict[str, Any]:
        """Export all data needed for a trust monitoring dashboard.

        Returns:
            A dict with keys:
                current: dict — current metric values.
                trends: dict — trend report per core metric.
                alerts: list[dict] — current active alerts.
                forecast: list[dict] — 7-day forecast for overall_trust.
                snapshot_count: int — total snapshots recorded.
                name: str — trending engine name.
        """
        core_metrics = [
            "overall_trust",
            "violation_count",
            "debt_total",
            "audit_completeness",
        ]
        trends: dict[str, Any] = {}
        for metric in core_metrics:
            report = self.analyze_trend(metric=metric)
            trends[metric] = {
                "direction": report.direction.value,
                "confidence": round(report.confidence, 4),
                "slope": round(report.slope, 4),
                "anomaly_count": len(report.anomalies),
            }

        latest = self._snapshots[-1] if self._snapshots else None
        current = {
            "overall_trust": latest.overall_trust if latest else 0.0,
            "violation_count": latest.violation_count if latest else 0,
            "debt_total": latest.debt_total if latest else 0.0,
            "audit_completeness": latest.audit_completeness if latest else 0.0,
            "component_scores": dict(latest.component_scores) if latest else {},
        }

        alerts = self.check_alerts()
        forecast_data = self.forecast(metric="overall_trust", horizon=7)

        return {
            "name": self.name,
            "snapshot_count": len(self._snapshots),
            "current": current,
            "trends": trends,
            "alerts": [
                {
                    "level": a.level.value,
                    "message": a.message,
                    "metric": a.metric,
                    "triggered_at": a.triggered_at,
                }
                for a in alerts
            ],
            "forecast": forecast_data,
        }
