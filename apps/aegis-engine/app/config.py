"""Configuration and data models for declarative SLO definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field


class AvailabilitySLOConfig(BaseModel):
    """Specification for API Availability SLO."""
    enabled: bool = True
    target_percent: float = Field(default=99.0, ge=0.0, le=100.0)
    warning_threshold_percent: float = Field(default=99.5, ge=0.0, le=100.0)
    sli_query: str


class LatencySLOConfig(BaseModel):
    """Specification for API Latency SLO."""
    enabled: bool = True
    p95_target_ms: float = Field(default=200.0, gt=0.0)
    p99_target_ms: float = Field(default=500.0, gt=0.0)
    p95_sli_query: str
    p99_sli_query: str


class ErrorRateSLOConfig(BaseModel):
    """Specification for API Error Rate SLO."""
    enabled: bool = True
    target_percent: float = Field(default=1.0, ge=0.0, le=100.0)
    sli_query: str


class SLOsConfig(BaseModel):
    """Collection of SLO targets for an API."""
    availability: Optional[AvailabilitySLOConfig] = None
    latency: Optional[LatencySLOConfig] = None
    error_rate: Optional[ErrorRateSLOConfig] = None


class ErrorBudgetConfig(BaseModel):
    """Thresholds for error budget burn rates."""
    burn_rate_warning_threshold: float = Field(default=2.0, gt=0.0)
    burn_rate_critical_threshold: float = Field(default=5.0, gt=0.0)


class ServiceSLOConfig(BaseModel):
    """Root configuration object representing an API's reliability contract."""
    api_name: str
    service_label: str
    namespace: str = "demo"
    evaluation_window: str = "5m"
    slos: SLOsConfig
    error_budget: ErrorBudgetConfig = Field(default_factory=ErrorBudgetConfig)

    @classmethod
    def from_yaml_file(cls, file_path: str | Path) -> ServiceSLOConfig:
        """Loads and parses a YAML SLO specification."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"SLO configuration file not found: {path.resolve()}")
        
        with open(path, "r", encoding="utf-8") as f:
            raw_data = yaml.safe_load(f)
            
        return cls.model_validate(raw_data)
