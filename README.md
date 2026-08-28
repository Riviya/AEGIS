# Aegis — Autonomous API Reliability & SRE Platform

University project: an SRE control plane for APIs on **WSO2 API Manager** and **Kubernetes**.

**Current stage: Phase 1 — Foundation.** Observability, SLO engine, and Aegis itself are not in this repository yet.

## What Phase 1 proves

A developer can commit `payment-api`, GitHub Actions can test and build its image, and locally you can run the API on **kind** behind **WSO2 API Manager**.

```text
GitHub  →  GitHub Actions (test + docker build)
Laptop  →  kind (Kubernetes in Docker)
              ├── demo/payment-api
              └── wso2/wso2am (all-in-one)
Client  →  WSO2 Gateway  →  payment-api
```

## Repository layout

| Path | Why it exists |
| --- | --- |
| [apps/payment-api](apps/payment-api) | Sample backend Aegis will later protect |
| [infra/kind](infra/kind) | Single-node cluster + host port mappings |
| [infra/k8s/demo](infra/k8s/demo) | Kubernetes objects for the API |
| [infra/k8s/wso2](infra/k8s/wso2) | Kubernetes objects for API Manager |
| [docs/PHASE1.md](docs/PHASE1.md) | Copy-paste commands, explanations, troubleshooting |
| [docs/PHASE_GATES.md](docs/PHASE_GATES.md) | How to know a phase is done before starting the next |
| [scripts/check-prereqs.ps1](scripts/check-prereqs.ps1) | Windows tool check |
| [.github/workflows/payment-api.yml](.github/workflows/payment-api.yml) | CI: pytest + docker build |

## Start here

1. Install and start **Docker Desktop** (WSL2). Give it about **8–10 GB** RAM.
2. Confirm tools: `kubectl`, `kind`, `Helm`, `Git` (see [docs/PHASE1.md](docs/PHASE1.md)).
3. Follow **[docs/PHASE1.md](docs/PHASE1.md)** in order. Do not skip to Phase 2.

## Phase freeze line (thesis)

A defensible MVP is **Phase 6 (automated rollback) + Phase 10 (chaos evaluation)**. Phases 7–9 help; Phase 11 is optional.
