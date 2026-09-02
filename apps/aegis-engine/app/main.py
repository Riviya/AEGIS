"""CLI Entry point for Aegis SRE SLO & Error Budget Engine."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from .config import ServiceSLOConfig
from .prometheus_client import PrometheusClient
from .slo_engine import SLOEngine, ComplianceStatus
from .formatter import print_cli_report, format_json_report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aegis Autonomous SRE Platform — SLO & Error Budget Engine",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--slo-config",
        "-c",
        type=str,
        default="configs/slos/payment-api.yaml",
        help="Path to the declarative SLO YAML specification file.",
    )
    parser.add_argument(
        "--prom-url",
        "-p",
        type=str,
        default=os.getenv("PROMETHEUS_URL", "http://localhost:9090"),
        help="Prometheus HTTP API base URL.",
    )
    parser.add_argument(
        "--window",
        "-w",
        type=str,
        default=None,
        help="Override the evaluation window (e.g., '1m', '5m', '1h').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the evaluation report as raw JSON.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Run continuously in a loop, evaluating every N seconds.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Interval in seconds between evaluation loops when in --watch mode.",
    )
    parser.add_argument(
        "--fail-on-violation",
        action="store_true",
        help="Return exit code 1 if any SLO is violated (useful for CI/CD phase gates).",
    )

    args = parser.parse_args()

    # 1. Load SLO Configuration
    config_path = Path(args.slo_config)
    if not config_path.is_absolute():
        # Try relative to current working directory or relative to project root
        if not config_path.exists():
            # Search upwards
            candidate = Path(__file__).resolve().parent.parent.parent.parent / args.slo_config
            if candidate.exists():
                config_path = candidate

    try:
        slo_config = ServiceSLOConfig.from_yaml_file(config_path)
    except Exception as e:
        print(f"[ERROR] Failed to load SLO configuration from {config_path}: {e}", file=sys.stderr)
        return 2

    # 2. Initialize Prometheus Client & SLO Engine
    prom_client = PrometheusClient(base_url=args.prom_url)
    engine = SLOEngine(prom_client=prom_client)

    # 3. Execution Loop (Single Run or Watch Mode)
    last_status = ComplianceStatus.HEALTHY

    try:
        while True:
            if args.watch and not args.json:
                # Clear terminal screen in watch mode
                os.system("cls" if os.name == "nt" else "clear")

            report = engine.evaluate(slo_config, custom_window=args.window)
            last_status = report.overall_status

            if args.json:
                print(format_json_report(report))
            else:
                print_cli_report(report)

            if not args.watch:
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nAegis SLO monitoring stopped by user.")

    # 4. Exit Code Handling
    if args.fail_on_violation and last_status == ComplianceStatus.VIOLATED:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
