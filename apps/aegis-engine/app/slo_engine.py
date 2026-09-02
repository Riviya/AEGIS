"""Core SRE Evaluation Engine for SLIs, SLOs, Error Budgets, and Burn Rates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from .config import ServiceSLOConfig
from .prometheus_client import PrometheusClient


class ComplianceStatus(str, Enum):
    HEALTHY = "HEALTHY"
    AT_RISK = "AT_RISK"
    VIOLATED = "VIOLATED"
    NO_DATA = "NO_DATA"


@dataclass
class SLIEvaluationResult:
    """Individual SLI metric evaluation against an SLO target."""
    name: str
    target: float
    actual_value: Optional[float]
    unit: str
    is_compliant: bool
    status: ComplianceStatus
    details: str = ""


@dataclass
class ErrorBudgetReport:
    """Comprehensive Error Budget and Burn Rate calculations."""
    slo_target_percent: float
    total_budget_percent: float          # e.g., 1.0% for a 99.0% SLO
    consumed_budget_percent: float       # Actual error rate in window
    remaining_budget_percent: float      # % of the allowable budget left (0% - 100%)
    burn_rate: float                     # Burn rate multiplier (1.0 = normal consumption)
    status: ComplianceStatus
    time_to_exhaustion: Optional[str] = None  # Estimated time before budget hits 0 at current burn


@dataclass
class ServiceSLOReport:
    """Full reliability assessment for an API at a given evaluation timestamp."""
    api_name: str
    namespace: str
    window: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    overall_status: ComplianceStatus = ComplianceStatus.HEALTHY
    sli_results: Dict[str, SLIEvaluationResult] = field(default_factory=dict)
    error_budget: Optional[ErrorBudgetReport] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converts the report to a clean dictionary structure for JSON output."""
        return {
            "api_name": self.api_name,
            "namespace": self.namespace,
            "evaluation_window": self.window,
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "slis": {
                name: {
                    "target": res.target,
                    "actual": res.actual_value,
                    "unit": res.unit,
                    "is_compliant": res.is_compliant,
                    "status": res.status.value,
                    "details": res.details,
                }
                for name, res in self.sli_results.items()
            },
            "error_budget": {
                "slo_target_percent": self.error_budget.slo_target_percent,
                "total_budget_percent": self.error_budget.total_budget_percent,
                "consumed_budget_percent": self.error_budget.consumed_budget_percent,
                "remaining_budget_percent": self.error_budget.remaining_budget_percent,
                "burn_rate": round(self.error_budget.burn_rate, 2),
                "status": self.error_budget.status.value,
                "time_to_exhaustion": self.error_budget.time_to_exhaustion,
            } if self.error_budget else None,
        }


class SLOEngine:
    """Evaluates API telemetry against declarative SLO definitions."""

    def __init__(self, prom_client: PrometheusClient):
        self.prom_client = prom_client

    def evaluate(self, config: ServiceSLOConfig, custom_window: Optional[str] = None) -> ServiceSLOReport:
        """Runs a complete SLO and error budget evaluation cycle for a service.

        Args:
            config: The parsed declarative SLO configuration.
            custom_window: Overrides the default evaluation window (e.g., '1m', '5m', '1h').

        Returns:
            A populated ServiceSLOReport containing all SLIs, compliance, and error budgets.
        """
        window = custom_window or config.evaluation_window
        report = ServiceSLOReport(
            api_name=config.api_name,
            namespace=config.namespace,
            window=window,
        )

        overall_violation = False
        overall_warning = False
        has_data = False

        # 1. Evaluate Availability SLO
        if config.slos.availability and config.slos.availability.enabled:
            avail_cfg = config.slos.availability
            query = avail_cfg.sli_query.replace("{window}", window)
            actual_avail = self.prom_client.query(query)

            if actual_avail is not None:
                has_data = True
                is_compliant = actual_avail >= avail_cfg.target_percent
                if not is_compliant:
                    status = ComplianceStatus.VIOLATED
                    overall_violation = True
                elif actual_avail < avail_cfg.warning_threshold_percent:
                    status = ComplianceStatus.AT_RISK
                    overall_warning = True
                else:
                    status = ComplianceStatus.HEALTHY

                report.sli_results["availability"] = SLIEvaluationResult(
                    name="Availability",
                    target=avail_cfg.target_percent,
                    actual_value=round(actual_avail, 2),
                    unit="%",
                    is_compliant=is_compliant,
                    status=status,
                    details=f"Target >= {avail_cfg.target_percent}%",
                )
            else:
                report.sli_results["availability"] = SLIEvaluationResult(
                    name="Availability",
                    target=avail_cfg.target_percent,
                    actual_value=None,
                    unit="%",
                    is_compliant=True,
                    status=ComplianceStatus.NO_DATA,
                    details="No traffic received in window",
                )

        # 2. Evaluate Latency SLO (p95 & p99)
        if config.slos.latency and config.slos.latency.enabled:
            lat_cfg = config.slos.latency
            p95_query = lat_cfg.p95_sli_query.replace("{window}", window)
            p95_val = self.prom_client.query(p95_query)

            if p95_val is not None:
                has_data = True
                is_compliant = p95_val <= lat_cfg.p95_target_ms
                if not is_compliant:
                    status = ComplianceStatus.VIOLATED
                    overall_violation = True
                else:
                    status = ComplianceStatus.HEALTHY

                report.sli_results["latency_p95"] = SLIEvaluationResult(
                    name="Latency (p95)",
                    target=lat_cfg.p95_target_ms,
                    actual_value=round(p95_val, 2),
                    unit="ms",
                    is_compliant=is_compliant,
                    status=status,
                    details=f"Target <= {lat_cfg.p95_target_ms} ms",
                )
            else:
                report.sli_results["latency_p95"] = SLIEvaluationResult(
                    name="Latency (p95)",
                    target=lat_cfg.p95_target_ms,
                    actual_value=None,
                    unit="ms",
                    is_compliant=True,
                    status=ComplianceStatus.NO_DATA,
                    details="No latency samples in window",
                )

        # 3. Evaluate Error Rate SLO
        if config.slos.error_rate and config.slos.error_rate.enabled:
            err_cfg = config.slos.error_rate
            err_query = err_cfg.sli_query.replace("{window}", window)
            actual_err = self.prom_client.query(err_query)

            if actual_err is not None:
                has_data = True
                is_compliant = actual_err <= err_cfg.target_percent
                if not is_compliant:
                    status = ComplianceStatus.VIOLATED
                    overall_violation = True
                else:
                    status = ComplianceStatus.HEALTHY

                report.sli_results["error_rate"] = SLIEvaluationResult(
                    name="Error Rate (5xx)",
                    target=err_cfg.target_percent,
                    actual_value=round(actual_err, 2),
                    unit="%",
                    is_compliant=is_compliant,
                    status=status,
                    details=f"Target <= {err_cfg.target_percent}%",
                )
            else:
                report.sli_results["error_rate"] = SLIEvaluationResult(
                    name="Error Rate (5xx)",
                    target=err_cfg.target_percent,
                    actual_value=None,
                    unit="%",
                    is_compliant=True,
                    status=ComplianceStatus.NO_DATA,
                    details="No traffic received in window",
                )

        # 4. Calculate Error Budget & Burn Rate
        target_avail = (
            config.slos.availability.target_percent
            if config.slos.availability and config.slos.availability.enabled
            else 99.0
        )
        total_budget = 100.0 - target_avail  # e.g. 1.0%

        # Determine actual error rate (consumed unreliability)
        err_res = report.sli_results.get("error_rate")
        consumed_budget = err_res.actual_value if err_res and err_res.actual_value is not None else 0.0

        # Remaining budget calculation:
        # If total allowable error is 1.0% and error rate is 0.2%, remaining budget = (1.0 - 0.2)/1.0 = 80%
        # If error rate is 1.5%, remaining budget = 0%
        if total_budget > 0:
            remaining_pct = max(0.0, ((total_budget - consumed_budget) / total_budget) * 100.0)
            burn_rate = consumed_budget / total_budget
        else:
            remaining_pct = 100.0
            burn_rate = 0.0

        # Burn rate status classification
        if burn_rate >= config.error_budget.burn_rate_critical_threshold or remaining_pct == 0.0:
            eb_status = ComplianceStatus.VIOLATED
            overall_violation = True
        elif burn_rate >= config.error_budget.burn_rate_warning_threshold or remaining_pct < 50.0:
            eb_status = ComplianceStatus.AT_RISK
            overall_warning = True
        else:
            eb_status = ComplianceStatus.HEALTHY

        # Estimate time to exhaustion if burning
        time_to_exhaustion = None
        if burn_rate > 1.0 and remaining_pct > 0:
            # Assuming a standard 1-hour active window for burn calculation
            minutes_left = (remaining_pct / 100.0) * (60.0 / burn_rate)
            time_to_exhaustion = f"~{int(minutes_left)} min at current burn rate"
        elif remaining_pct == 0:
            time_to_exhaustion = "0 min (Budget Fully Exhausted)"

        report.error_budget = ErrorBudgetReport(
            slo_target_percent=target_avail,
            total_budget_percent=round(total_budget, 2),
            consumed_budget_percent=round(consumed_budget, 2),
            remaining_budget_percent=round(remaining_pct, 1),
            burn_rate=round(burn_rate, 2),
            status=eb_status,
            time_to_exhaustion=time_to_exhaustion,
        )

        # Set final overall status
        if not has_data:
            report.overall_status = ComplianceStatus.NO_DATA
        elif overall_violation:
            report.overall_status = ComplianceStatus.VIOLATED
        elif overall_warning:
            report.overall_status = ComplianceStatus.AT_RISK
        else:
            report.overall_status = ComplianceStatus.HEALTHY

        return report
