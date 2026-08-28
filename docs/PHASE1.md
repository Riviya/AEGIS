# Phase 1 — Foundation

**What we are building:** a sample `payment-api`, a local Kubernetes cluster (kind), WSO2 API Manager in front of that API, and GitHub Actions that test and build the image.

**Why:** Aegis cannot observe or remediate APIs that do not exist. WSO2 must be a real gateway (auth + publish), not a label in the report.

**Out of scope:** Prometheus, Grafana, Argo CD, Identity Server, Aegis engine.

**Success gate:** [PHASE_GATES.md](PHASE_GATES.md) Phase 1.

---

## Concepts (read before commands)


| Term                              | Meaning                                                                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Container image**               | Filesystem + your app. Built from the `Dockerfile`. Kubernetes runs images, not Python files on disk.                           |
| **kind**                          | Kubernetes **in Docker**. One (or more) Docker containers act as cluster nodes. Good for a laptop.                              |
| **Pod**                           | Smallest deployable unit. Here: one container per Deployment.                                                                   |
| **Deployment**                    | Declares “keep N copies of this Pod running.”                                                                                   |
| **Service**                       | Stable DNS name and port in the cluster. `payment-api.demo.svc.cluster.local` is how WSO2 finds the backend.                    |
| **Namespace**                     | Name prefix. `demo` vs `wso2` so objects do not collide.                                                                        |
| **NodePort + extraPortMappings**  | kind forwards `localhost:9443` on Windows into the node, then to the WSO2 Service.                                              |
| **WSO2 API Manager (all-in-one)** | One process: Publisher (define APIs), DevPortal (apps + keys), Gateway (the proxy clients call), resident Key Manager (tokens). |
| **imagePullPolicy: Never**        | kind does not see images on your laptop unless you `kind load docker-image`. Never = do not try Docker Hub for `payment-api`.   |


---



## 0. Prerequisites

Give Docker Desktop about **8–10 GB** RAM (Settings → Resources).

**What each tool does**

- **Docker Desktop** — runs containers and kind’s node.
- **kubectl** — talks to the Kubernetes API (create pods, read logs).
- **kind** — creates the cluster.
- **Helm** — not required to apply these YAML files; installed so later charts (optional) are available.
- **Git / GitHub** — source control and CI.

From the repo root in PowerShell:

```powershell
# What it does: runs the checker script.
# Why: fail fast if Docker is not running (kind cannot start).
# Expect: PASS lines, or FAIL Docker daemon if Desktop is stopped.
powershell -File .\scripts\check-prereqs.ps1
```

If Docker fails: start **Docker Desktop**, wait until the whale icon is idle, run the script again.

Install kind if missing:

```powershell
# What it does: installs the kind CLI via WinGet.
# Why: we use kind instead of a cloud cluster.
# Expect: "Successfully installed" (you already have it if check-prereqs prints PASS kind).
winget install Kubernetes.kind --accept-package-agreements --accept-source-agreements
```

Open a **new** terminal after installing kind so `PATH` updates.

---



## 1. Run unit tests on the laptop (optional but useful)

Needs Python 3.12+ on PATH.

```powershell
cd apps\payment-api

# What it does: creates an isolated Python environment.
# Why: does not pollute global Python.
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# What it does: installs FastAPI, uvicorn, pytest.
pip install -r requirements.txt

# What it does: runs tests in tests/.
# Expect: passed tests for /health and /payments.
pytest -q
```

If `python` is not found, skip this step; GitHub Actions still runs pytest.

---



## 2. Create the kind cluster

From the **repository root**:

```powershell
# What it does: starts a single-node Kubernetes cluster named "aegis".
# Why: local Kubernetes without Minikube’s extra VM (on Docker Desktop, kind uses a container).
# Expect: "cluster created". First run downloads a node image (several hundred MB).
kind create cluster --config infra\kind\cluster.yaml
```

If the name `aegis` already exists:

```powershell
# What it does: lists clusters.
kind get clusters
```

Point kubectl at this cluster (kind usually does this automatically):

```powershell
# What it does: shows the current Kubernetes context.
# Expect: kind-aegis
kubectl config current-context
```

```powershell
# What it does: confirms the API server answers.
# Expect: a Ready control-plane node.
kubectl get nodes
```

**If the output is different:** `Unable to connect` → Docker is down or the cluster failed. `kind delete cluster --name aegis` then create again.

---



## 3. Build payment-api and load it into kind

kind nodes do **not** automatically see images you built on Windows.

```powershell
# What it does: builds image payment-api:0.1.0 from the Dockerfile.
# Why: Kubernetes will run this image.
# Expect: "naming to docker.io/library/payment-api:0.1.0" (or similar) at the end.
docker build -t payment-api:0.1.0 apps\payment-api
```

```powershell
# What it does: copies that image into the kind node.
# Why: imagePullPolicy is Never; without this, the Pod stays ImagePullBackOff or ErrImageNeverPull.
kind load docker-image payment-api:0.1.0 --name aegis
```

---



## 4. Deploy payment-api

```powershell
# What it does: creates namespace demo.
kubectl apply -f infra\k8s\demo\namespace.yaml

# What it does: creates Deployment + Service.
kubectl apply -f infra\k8s\demo\payment-api.yaml
```

```powershell
# What it does: waits until the Pod is Ready.
# Expect: condition met (up to 60s).
kubectl -n demo rollout status deployment/payment-api --timeout=60s
```

```powershell
# What it does: lists pods.
# Expect: 1/1 Ready.
kubectl -n demo get pods -o wide
```

Debug from Windows (kind maps nodePort 30080 → localhost 18080):

```powershell
# What it does: calls the API, bypassing WSO2.
# Why: proves the backend is healthy before fighting the gateway.
# Expect: JSON with status ok.
curl.exe http://localhost:18080/health
```

```powershell
curl.exe http://localhost:18080/payments
```

PowerShell’s `curl` is `Invoke-WebRequest`. Use `curl.exe` as above.

**If pending / ImagePullBackOff:** you skipped `kind load`. **If 404 on localhost:18080:** cluster extraPortMappings not applied — recreate cluster from `infra/kind/cluster.yaml`.

---



## 5. Deploy WSO2 API Manager (all-in-one)

This image is **large** (multiple GB). Pull once:

```powershell
# What it does: downloads wso2/wso2am:4.5.0.
# Why: APIM all-in-one includes gateway + publisher + key manager.
# Expect: several minutes. If disk is full, Docker will error — free space and retry.
docker pull wso2/wso2am:4.5.0
```

```powershell
kind load docker-image wso2/wso2am:4.5.0 --name aegis
```

Loading a multi-GB image into kind can take several minutes.

Credentials Secret (gitignored `secret.yaml`):

```powershell
# What it does: copies the example Secret.
# Why: we do not commit a custom password file; the example documents the default lab user.
Copy-Item infra\k8s\wso2\secret.yaml.example infra\k8s\wso2\secret.yaml
```

```powershell
kubectl apply -f infra\k8s\wso2\namespace.yaml
kubectl apply -f infra\k8s\wso2\secret.yaml
kubectl apply -f infra\k8s\wso2\apim.yaml
```

```powershell
# What it does: watch the Pod. STATUS goes Running; READY becomes 1/1 after Carbon binds 9443.
# Expect: 3–8 minutes. startupProbe allows ~10 minutes.
kubectl -n wso2 get pods -w
```

Press Ctrl+C to stop watching when `1/1`.

```powershell
kubectl -n wso2 rollout status deployment/wso2am --timeout=600s
```

**If OOMKilled:** raise Docker Desktop memory, or lower `JAVA_OPTS` `-Xmx` in `apim.yaml` to `1536m` and re-apply.

**If CrashLoopBackOff immediately:** `kubectl -n wso2 logs deploy/wso2am --tail=80` and read the Java error before changing YAML.

Consoles (browser; certificate is self-signed — Advanced → continue):


| URL                                                                  | What it is                                    |
| -------------------------------------------------------------------- | --------------------------------------------- |
| [https://localhost:9443/publisher](https://localhost:9443/publisher) | Define and publish APIs                       |
| [https://localhost:9443/devportal](https://localhost:9443/devportal) | Applications, subscribe, generate keys        |
| [https://localhost:9443/carbon](https://localhost:9443/carbon)       | Super-admin console (avoid until you need it) |
| [https://localhost:9443/admin](https://localhost:9443/admin)         | Admin portal                                  |


Default lab login (matches the example Secret): **admin** / **admin**.

---



## 6. Publish payment-api through WSO2 (Publisher UI)

WSO2 is the **only** public entry the project cares about. The backend URL must be the **in-cluster** Service, not localhost.

1. Open [https://localhost:9443/publisher](https://localhost:9443/publisher) and sign in as `admin`.
2. Create API → **REST API** → **Start from Scratch** (or Start with OpenAPI if you prefer).
3. Name: `PaymentAPI`. Context: `/payments`. Version: `1.0.0`.
4. Endpoint: `http://payment-api.demo.svc.cluster.local:8080`
  **Why this URL:** from the APIM pod, Kubernetes DNS resolves `payment-api` in namespace `demo`. `localhost` inside that pod would mean APIM itself, which is wrong.
5. Add resources:
  - `GET /health`
  - `GET /payments`
  - `GET /payments/{paymentId}`
6. **Deploy** (create a revision and deploy to the default gateway).
7. **Publish**.

Developer Portal:

1. Open [https://localhost:9443/devportal](https://localhost:9443/devportal).
2. Subscribe to `PaymentAPI` with the default application (or create `aegis-lab`).
3. Generate keys (OAuth2). Copy the **access token**.

Call through the **HTTPS gateway** (kind maps 8243):

```powershell
# Replace TOKEN with the access token from DevPortal.
# -k: skip verify of WSO2’s self-signed cert (lab only).
# Expect: same JSON as the backend /payments (gateway may prefix the context; if you set context /payments and resource /payments, the path may be /payments/payments — if 404, try GET /payments/health or match the resource paths you configured).
curl.exe -k -H "Authorization: Bearer TOKEN" https://localhost:8243/payments/1.0.0/health
```

WSO2 often exposes: `https://<gw-host>:8243/<context>/<version>/<resource>`.

If health was mapped as `/health` under context `/payment` version `1.0.0`:

```powershell
curl.exe -k -H "Authorization: Bearer TOKEN" https://localhost:8243/payment/1.0.0/health
```

Without a token you should get **401/403**. That is success for “gateway enforces auth.”

**Rate limit (optional, still Phase 1):** in Publisher, add a burst-control or application throttle so WSO2 is clearly doing API management, not only proxying.

---



## 7. GitHub Actions

1. Create a GitHub repository and push this project.
2. Confirm **Actions** is enabled.
3. Push a change under `apps/payment-api/` (or run the workflow manually).

**What the workflow does:** checks out code, installs Python 3.12, runs `pytest`, builds the Docker image. It does **not** deploy to kind (no public cluster).

**Expect:** a green check. **If pytest fails:** run pytest locally and fix tests. **If docker build fails:** read the log; usually a COPY path or missing file.

---



## 8. What to document for the university report

- Diagram: Developer → GitHub → CI; kind with `demo` and `wso2`; Client → Gateway → Service.
- Why WSO2: publish, gateway, OAuth, (optional) rate limit — not a dummy container.
- Screenshot: Publisher showing the API **PUBLISHED**; curl through 8243 with and without a token.
- Resource note: APIM ~2–4 GiB; why all-in-one instead of HA.



## 9. What to measure later (not Phase 1)

Detection time, MTTR, manual steps — those need observability and Aegis. Phase 1 only establishes the **baseline API path**.

---



## Tear down (when you need RAM back)

```powershell
# What it does: deletes the Kubernetes cluster and its containers.
# Why: APIM is heavy; stop it when you are not working.
# Expect: cluster deleted. Images remain in Docker until you docker rmi.
kind delete cluster --name aegis
```

---



## Files in this phase (quick map)


| File                                    | Role                               |
| --------------------------------------- | ---------------------------------- |
| `apps/payment-api/app/main.py`          | HTTP API (`/health`, `/payments`)  |
| `apps/payment-api/Dockerfile`           | How to package the API             |
| `apps/payment-api/tests/test_health.py` | CI tests                           |
| `infra/kind/cluster.yaml`               | kind ports 9443, 8243, 8280, 18080 |
| `infra/k8s/demo/payment-api.yaml`       | Run the API in Kubernetes          |
| `infra/k8s/wso2/apim.yaml`              | Run APIM all-in-one                |
| `infra/k8s/wso2/secret.yaml.example`    | Lab credentials template           |
| `.github/workflows/payment-api.yml`     | Test + image build on GitHub       |


