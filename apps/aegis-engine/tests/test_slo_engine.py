"""Unit tests for the Aegis SRE SLO & Error Budget Calculation Engine."""

import pytest
from unittest.mock import MagicMock

from app.config import ServiceSLOConfig, SLOsConfig, AvailabilitySLOConfig, LatencySLOConfig, ErrorRateSLOConfig, ErrorBudgetConfig
from app.prometheus_client import PrometheusClient
from app.slo_engine import SLOEngine, ComplianceStatus


@pytest.fixture
def sample_slo_config() -> ServiceSLOConfig:
    return ServiceSLOConfig(
        api_name="payment-api",
        service_label="payment-api",
        namespace="demo",
        evaluation_window="5m",
        slos=SLOsConfig(
            availability=AvailabilitySLOConfig(
                enabled=True,
                target_percent=99.0,
                warning_threshold_percent=99.5,
                sli_query="dummy_query",
            ),
            latency=LatencySLOConfig(
                enabled=True,
                p95_target_ms=200.0,
                p99_target_ms=500.0,
                p95_sli_query="dummy_query",
                p99_sli_query="dummy_query",
            ),
            error_rate=ErrorRateSLOConfig(
                enabled=True,
                target_percent=1.0,
                sli_query="dummy_query",
            ),
        ),
        error_budget=ErrorBudgetConfig(
            burn_rate_warning_threshold=2.0,
            burn_rate_critical_threshold=5.0,
        ),
    )


def test_slo_perfect_health(sample_slo_config):
    """Test when system is 100% healthy: 0 errors, low latency, full error budget."""
    mock_prom = MagicMock(spec=PrometheusClient)

    def mock_query(query: str):
        if "availability" in query or "status!~" in query or "dummy_query" in query:
            # Let's handle different queries based on context or return mock values
            pass
        return None

    # Availability = 100.0%, Latency = 45.0ms, Error Rate = 0.0%
    mock_prom.query.side_effect = [100.0, 45.0, 0.0]

    engine = SLOEngine(prom_client=mock_prom)
    report = engine.evaluate(sample_slo_config)

    assert report.overall_status == ComplianceStatus.HEALTHY
    assert report.sli_results["availability"].is_compliant is True
    assert report.sli_results["availability"].actual_value == 100.0
    assert report.sli_results["latency_p95"].is_compliant is True
    assert report.sli_results["latency_p95"].actual_value == 45.0
    assert report.sli_results["error_rate"].is_compliant is True
    assert report.sli_results["error_rate"].actual_value == 0.0

    # Error budget calculations
    eb = report.error_budget
    assert eb is not None
    assert eb.total_budget_percent == 1.0  # 100 - 99.0
    assert eb.consumed_budget_percent == 0.0
    assert eb.remaining_budget_percent == 100.0
    assert eb.burn_rate == 0.0
    assert eb.status == ComplianceStatus.HEALTHY


def test_slo_degraded_partial_budget_burn(sample_slo_config):
    """Test when system error rate is 0.5%: still compliant with 99.0% SLO, but 50% budget burned."""
    mock_prom = MagicMock(spec=PrometheusClient)
    # Availability = 99.5%, Latency = 120.0ms, Error Rate = 0.5%
    mock_prom.query.side_effect = [99.5, 120.0, 0.5]

    engine = SLOEngine(prom_client=mock_prom)
    report = engine.evaluate(sample_slo_config)

    assert report.overall_status == ComplianceStatus.HEALTHY
    assert report.sli_results["availability"].is_compliant is True
    assert report.sli_results["error_rate"].is_compliant is True

    # Error budget
    eb = report.error_budget
    assert eb is not None
    assert eb.consumed_budget_percent == 0.5
    assert eb.remaining_budget_percent == 50.0  # (1.0 - 0.5)/1.0 * 100 = 50%
    assert eb.burn_rate == 0.5  # 0.5 / 1.0 = 0.5x


def test_slo_violation_injected_error_rate(sample_slo_config):
    """Test when system error rate is 30.0%: SLO violated, 0% budget remaining, 30x burn rate."""
    mock_prom = MagicMock(spec=PrometheusClient)
    # Availability = 70.0%, Latency = 350.0ms (exceeds 200ms), Error Rate = 30.0%
    mock_prom.query.side_effect = [70.0, 350.0, 30.0]

    engine = SLOEngine(prom_client=mock_prom)
    report = engine.evaluate(sample_slo_config)

    assert report.overall_status == ComplianceStatus.VIOLATED
    assert report.sli_results["availability"].is_compliant is False
    assert report.sli_results["availability"].status == ComplianceStatus.VIOLATED
    assert report.sli_results["latency_p95"].is_compliant is False
    assert report.sli_results["error_rate"].is_compliant is False

    eb = report.error_budget
    assert eb is not None
    assert eb.consumed_budget_percent == 30.0
    assert eb.remaining_budget_percent == 0.0
    assert eb.burn_rate == 30.0  # 30.0 / 1.0 = 30.0x
    assert eb.status == ComplianceStatus.VIOLATED


def test_slo_no_data(sample_slo_config):
    """Test when Prometheus returns no data (e.g. no traffic sent yet)."""
    mock_prom = MagicMock(spec=PrometheusClient)
    mock_prom.query.return_value = None

    engine = SLOEngine(prom_client=mock_prom)
    report = engine.evaluate(sample_slo_config)

    assert report.overall_status == ComplianceStatus.NO_DATA
    assert report.sli_results["availability"].status == ComplianceStatus.NO_DATA
    assert report.sli_results["availability"].actual_value is None
