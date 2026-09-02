"""Prometheus HTTP API client for querying SLI metrics."""

from __future__ import annotations

import logging
from typing import Any, Optional
import httpx

logger = logging.getLogger("aegis.prometheus")


class PrometheusClient:
    """Client for executing PromQL queries against a Prometheus server."""

    def __init__(self, base_url: str = "http://localhost:9090", timeout_seconds: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    def query(self, promql_query: str) -> Optional[float]:
        """Executes an instant PromQL query and extracts the scalar float value.

        Args:
            promql_query: The PromQL expression to evaluate.

        Returns:
            The single numerical value as a float, or None if no data / query returns empty.
        """
        endpoint = f"{self.base_url}/api/v1/query"
        params = {"query": promql_query}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(endpoint, params=params)
                response.raise_for_status()
                payload = response.json()

            if payload.get("status") != "success":
                logger.warning(f"Prometheus query failed: {payload.get('error')}")
                return None

            data = payload.get("data", {})
            result_type = data.get("resultType")
            result = data.get("result", [])

            if not result:
                # No data matching query in current window
                return None

            if result_type == "vector":
                # Result format: [{"metric": {...}, "value": [timestamp, "value_string"]}]
                value_str = result[0]["value"][1]
                val = float(value_str)
                # Check for NaN / Inf
                if val != val or val == float("inf") or val == float("-inf"):
                    return None
                return val

            if result_type == "scalar":
                # Result format: [timestamp, "value_string"]
                return float(result[1])

            return None

        except httpx.ConnectError:
            logger.error(f"Cannot connect to Prometheus at {self.base_url}. Is port-forwarding running?")
            raise ConnectionError(f"Could not connect to Prometheus at {self.base_url}")
        except Exception as e:
            logger.error(f"Error querying Prometheus with PromQL '{promql_query}': {e}")
            return None

    def test_connection(self) -> bool:
        """Verifies that Prometheus is reachable and healthy."""
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.get(f"{self.base_url}/-/healthy")
                return resp.status_code == 200
        except Exception:
            return False
