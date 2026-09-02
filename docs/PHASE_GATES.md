# Phase gates

Aegis is built **one phase at a time**. Do not start phase N+1 until phase N’s **success gate** is true. After you finish a later phase, **re-check the previous gate** so the new layer did not break the old one.

How to work on every phase:

1. Explain the concept.
2. Show how it fits the architecture.
3. List prerequisites (previous gate must pass).
4. Implement the smallest slice.
5. Test with the commands in that phase’s doc.
6. Troubleshoot from logs/events, not random config edits.
7. Write a short lab note (what you ran, screenshot or log excerpt, result).
8. Record what you will measure later for the report.

---

## Phase 1 — Foundation (current)

**Prerequisite:** Docker engine running; `kubectl`, `kind`, Git installed.

**Success gate (all must be true):**

- `kubectl -n demo get pods` shows `payment-api` Ready.
- `curl http://localhost:18080/health` returns `{"status":"ok",...}` (direct debug port).
- WSO2 Publisher opens at `https://localhost:9443/publisher` (accept the self-signed cert).
- The Payments API is **published** and callable **through the gateway** (`localhost:8243` or `8280`) with a valid token or API key.
- GitHub Actions workflow **payment-api** has a green run that executed pytest and `docker build`.

**Do not add yet:** Prometheus, Grafana, Loki, OpenTelemetry, Argo CD, Identity Server, Aegis services.

**Re-check later:** After Phase 2, the API must still answer through the gateway.

---

## Phase 2 — Observability (current)

**Prerequisite:** Phase 1 gate.

**Success gate:** Grafana shows request rate, error rate, latency, and pod CPU/memory from **real** traffic, not fake panels.

**Re-check:** Phase 1 gateway call still works.

---

## Phase 3 — SLI / SLO / error budget (current)

**Prerequisite:** Phase 2 (Prometheus has the SLI metrics).

**Success gate:** For a YAML SLO (availability / p95 / error rate), Aegis (or the first job) prints compliance and remaining error budget. A forced error-rate increase shows a violation.

**Re-check:** Grafana still has data.

---

## Phase 4 — Incident detection

**Prerequisite:** Phase 3 numbers exist.

**Success gate:** Injecting high error rate creates a structured incident (id, API, severity, evidence) without you writing it by hand.

**Re-check:** SLO calculation still runs.

---

## Phase 5 — Canary / safe delivery

**Prerequisite:** Phase 4 (you can see v2 behaving badly).

**Success gate:** A bad v2 does not receive 100% of traffic; metrics distinguish v1 vs v2.

**Re-check:** Incidents still fire on a bad canary.

---

## Phase 6 — Automated rollback

**Prerequisite:** Phase 4 (and Phase 5 if you use canaries). Policy exists; rollback is not hard-coded to one demo.

**Success gate:** Faulty deployment is rolled back by Aegis; a verification check shows error rate recovered. You did not run `kubectl rollout undo` yourself.

**Re-check:** Gateway still serves the healthy revision.

---

## Phase 7 — Remediation engine

**Prerequisite:** Phase 6 rollback works as one action type.

**Success gate:** Policy YAML selects restart **or** scale **or** rollback; the chosen action is executed and logged.

**Re-check:** Rollback path from Phase 6 still works.

---

## Phase 8 — Safety controller

**Prerequisite:** At least one automated action (Phase 6 or 7).

**Success gate:** Observe / recommend / auto-remediate modes work; cooldown or blast-radius rules block a repeat or out-of-scope action.

**Re-check:** A permitted rollback still executes.

---

## Phase 9 — RCA (rule-based)

**Prerequisite:** Metrics + logs (Phase 2) and incidents (Phase 4).

**Success gate:** For each **scripted** failure (crash, saturation, bad deploy, backend down), Aegis names the expected cause and lists evidence.

**Re-check:** Detection still creates incidents.

---

## Phase 10 — Chaos and evaluation

**Prerequisite:** Closed loop through rollback (Phase 6) at minimum.

**Success gate:** A results table exists: detection time, remediation time, MTTR, manual steps, SLO impact — **with Aegis vs without**.

**Re-check:** Experiments did not leave the cluster permanently broken (Phase 1 gate still passes).

---

## Phase 11 — Optional

**Prerequisite:** Phases 1–10 stable enough to explain in a viva.

**Success gate:** Each extra feature (AI advisory RCA, multi-cluster, predictive) has a demo **and** a one-paragraph explanation of limits.

Suggested dissertation freeze: **Phase 6 + Phase 10**. Add 7–9 if time remains.
