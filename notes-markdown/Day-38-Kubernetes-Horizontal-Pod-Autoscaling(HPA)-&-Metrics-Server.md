# Day 38 — Kubernetes Horizontal Pod Autoscaling (HPA) & Metrics Server

**My learning project:** `01-python-fastapi` / Employee API, running on Docker Desktop Kubernetes (context `docker-desktop`, Kubernetes v1.36.1).  
**Learning dates:** 23–25 November 2026.  
**Outcome:** I installed and repaired Metrics Server, configured CPU-based HPA, generated real CPU load, verified **3 → 6 → 3** replicas, and understood the CPU-percentage and HPA conditions in detail.

> **How to read these notes.** “Observed” refers to actual output/screenshots. “Teaching example” means illustrative values rather than recorded measurements. “Proposed” means a configuration discussed but not applied. Screenshot references S001–S039 point to the separate Day 38 Excel workbook; screenshots are not pasted into this Markdown.

## Day 38 topic / screenshot map

| ID | What I learned | Excel evidence |
|---|---|---|
| T001 | HPA basics; starting cluster/Deployment/metrics checks | S001 |
| T002 | CPU request vs usage vs HPA target; calculations and replica formula | S012, S021–S022; worked calculations in these notes |
| T003 | Metrics Server installation, TLS error, corrected Deployment, verification | S002–S014 |
| T004 | API version/kind, `scaleTargetRef`, min/max replicas, creating HPA | S015–S022 |
| T005 | Finding `/cpu-test`, Service, port-forward, HTTP request, load and scale-up | S023–S036 |
| T006 | Scale-down stabilisation and HPA conditions/events | S035–S039 |
| T007 | MES/Station Manager vs stateless HTTP autoscaling | Concept and architecture notes below |
| T008 | Final decisions, verification and commit guidance | Final checklist below |

## T001 — What HPA is, and why I needed Metrics Server

A **HorizontalPodAutoscaler** automatically changes the **number of Pod replicas** of a scalable workload, such as a Deployment, based on measured demand. “Horizontal” means **more or fewer Pods**; it is not the same as giving an existing Pod a bigger CPU limit. My Employee API Deployment initially had three Pods. I configured an HPA to manage between three and six Pods using average CPU utilisation, targeting 50% of their CPU **requests**.

The important chain is:

```text
Employee API uses CPU
       ↓
Kubelet exposes usage measurements on the Node
       ↓
Metrics Server gathers Node/Pod resource metrics
       ↓
Kubernetes Metrics API (metrics.k8s.io)
       ↓
HPA controller compares actual average utilisation with target
       ↓
HPA updates Employee API Deployment's desired replica count
       ↓
Deployment controller creates/terminates Pods
```

**Service vs HPA:** The Service exposes and routes to eligible backend Pods; HPA controls the replica count. **HPA vs Metrics Server:** Metrics Server measures usage, but **does not itself scale Pods**. HPA uses those measurements to decide scaling. **Request vs limit:** The CPU `request` is the denominator of CPU utilisation; the CPU `limit` restricts the container's available CPU processing capacity. They are not interchangeable.

### My verified starting state — 23 November (S001)

In Windows PowerShell, I ran:

```powershell
kubectl config current-context
kubectl get deployments
kubectl get pods
kubectl top pods
```

Observed: context `docker-desktop`; `employee-api` Deployment READY/UP-TO-DATE/AVAILABLE **3/3**; three Pods Running/Ready; `kubectl top pods` returned **`error: Metrics API not available`**. The Pods showed a restart count of 1 each at that point, but I did not determine a restart cause. That does not establish an Employee API or HPA fault.

## T002 — CPU utilisation, percentages, averages and replica calculations

### My central formula (include verbatim)

\[
\boxed{\text{CPU Utilisation (\%)} = \frac{\text{Actual CPU Usage}}{\text{CPU Request}} \times 100}
\]

**I must use the CPU request, not the CPU limit, in the denominator.** Units must match: `70m ÷ 100m` works because `m` cancels. `100m` is 0.1 CPU, not 100 CPU cores. A percentage such as 50% means `50 ÷ 100 = 0.5`; **I do not multiply 100m directly by 50**.

My actual Employee API configuration, saved on Day 37 and reused in Day 38:

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

My proposed HPA setting was `averageUtilization: 50`, meaning **50% of CPU requested**, not “50m” as a unit specified in YAML. The **equivalent target usage** for one Pod requesting 100m is:

\[
100m \times \frac{50}{100} = 50m.
\]

For a hypothetical Pod requesting 200m instead, **the same 50% target** would correspond to `200m × (50/100) = 100m`. Thus **50% and 50m are different things**; they just coincide numerically in my 100m request example. `50m` is **not** the CPU limit; the limit remains 500m. The 50% target is a chosen learning setting, not a Kubernetes-mandated default.

### Examples I worked through — preserve both the confusion and correction

| Request | Actual usage | Computation | Actual CPU utilisation | Compared to HPA target of 50% |
|---|---|---|---|---|
| 100m | 70m | `70/100 × 100` | **70%** | Above |
| 200m | 70m | `70/200 × 100` | **35%** | Below |
| 200m | 140m | `140/200 × 100` | **70%** | Above |
| 100m | 3m | `3/100 × 100` | **3%** | Below |
| 100m | 4m | `4/100 × 100` | **4%** | Below |

At first I calculated `70/100 = 0.7` and then tried `100m × 0.7 = 70m`, thinking that was the utilisation percentage. **Correction:** `0.7 × 100 = 70%` is the utilisation percentage; `100m × 0.7 = 70m` merely reconstructs the original CPU usage. Likewise, when I changed request from 100m to 200m but left usage at 70m, utilisation dropped to 35%; it **did not** become 140% or 140m. I decided to revisit percentage mathematics separately, without diverting the Kubernetes lesson.

### Average over Pods — HPA looks at the workload, not just the busiest Pod

**Teaching example 1 — All Pods same request (100m):**

| Pod | Actual usage | Calculation | Utilisation |
|---|---|---|---|
| 1 | 80m | `80/100 ×100` | 80% |
| 2 | 40m | `40/100 ×100` | 40% |
| 3 | 60m | `60/100 ×100` | 60% |

Average `=(80%+40%+60%)/3 = 180%/3 = 60%`. Here percentages can be directly averaged because all requests are equal. It is above the 50% HPA target. If all three were instead using 80m each, average would be 80% (not “only the maximum Pod is 80m”). With usage `80m, 20m, 50m`, average is 50%, despite Pod 1 alone being at 80%.

I also solved a quiz with Pod utilisations **30%, 60%, 30%**: `(**30+60+30**)/3 = 120/3 = 40%`. **Write parentheses**; `30 + 60 + 30 / 3` without parentheses has a different mathematical meaning. This 40% is below 50%, but that alone doesn't guarantee the replica count immediately decreases.

### How HPA calculates desired replicas

Simplified formula (assuming usable, representative metrics):

\[
\boxed{\text{Desired replicas} = \left\lceil\text{Current replicas} \times \frac{\text{Current average CPU utilisation}}{\text{HPA target utilisation}}\right\rceil}
\]

The ceiling signs mean **round up to the next whole Pod**; the number of replicas cannot be fractional. Real HPA also considers tolerance, missing/not-ready Pod metrics, min/max replica boundaries, and stabilisation/rate policies.

| Teaching case | Calculation | Simplified desired replicas | Explanation |
|---|---|---|---|
| 3 Pods; avg 80%; target 50% | `ceil(3 × 80/50) = ceil(4.8)` | **5** | Raise replicas when avg is above target |
| 3 Pods; avg 60%; target 50% | `ceil(3 × 60/50) = ceil(3.6)` | **4** | My 80/40/60 case |
| 3 Pods; avg 40%; target 50% | `ceil(3 × 40/50) = ceil(2.4)` | **3** | Below target but round-up keeps three |
| 4 Pods; avg 80%; target 50%; max 6 | `ceil(4 × 80/50) = 7`, then clamp | **6** | Maximum enforced |
| 4 Pods; avg 20%; target 50%; min 2 | `ceil(4 × 20/50) = 2` | **2** | Potential scale-down, with safeguards |

**Why multiply by 3?** Three is the current **number of Pods**, not a CPU measurement. `80/50` is the ratio between **average current utilisation** and target, not the usage of only one Pod. Scaling does not instantly imply load distributes evenly to every new Pod; the formula is a control-system estimate.

### My own six-Pod calculation — 75m request and 65% target

This was a **teaching scenario**, not applied to Employee API. I chose a 75m CPU request for each of six Pods and `averageUtilization: 65`.

| Pod | CPU request | Utilisation | Usage = `75m × percent / 100` |
|---|---:|---:|---:|
| 1 | 75m | 80% | 60m |
| 2 | 75m | 30% | 22.5m |
| 3 | 75m | 70% | 52.5m |
| 4 | 75m | 30% | 22.5m |
| 5 | 75m | 40% | 30m |
| 6 | 75m | 70% | 52.5m |
| **Total** | **450m** | **320 percentage points (sum, not average)** | **240m** |

Average utilisation: `(80+30+70+30+40+70)/6 = 320/6 = 53.333…%` (**53.33%, or 53% rounded to nearest whole number, not 54%**). I found a useful shortcut since **all six requests are equal**: `(320/100) × 75m = 3.2 × 75m = 240m` total actual usage. Cross-check: `240m ÷ 450m ×100 = 53.33%`. HPA target equivalent is `75m × 65/100 = 48.75m per Pod`, or `48.75m ×6 = 292.5m` across six Pods. Thus actual 240m is below target-equivalent 292.5m. Simplified replicas `ceil(6 × 53.333…/65) = ceil(4.923…) = 5`, **if permitted by minReplicas and scaling safeguards**. I must not confuse the sum of six percentages (`320%`) with the average (`53.33%`). With unequal per-Pod requests, don't simply average Pod percentages without considering the HPA metric's aggregate interpretation.

## T003 — Metrics Server: from unavailable metrics to a working installation

### What the commands mean

- `kubectl get pods`: readiness/status/restarts and metadata, not live CPU use.
- `kubectl describe pod POD`: configuration, probes, requests/limits, events.
- `kubectl top pods`: measured CPU and memory for Pods **in the current namespace** (my `default` namespace has Employee API).
- `kubectl top pods -n kube-system`: measured usage for Kubernetes's own Pods.
- `kubectl top pods -A`: all namespaces.
- `kubectl top nodes`: measured Node-level CPU and memory.
- `kubectl describe node docker-desktop`: includes configured **allocated requests/limits** (summation), not live resource consumption. `top` and `describe` answer different questions.

My first install command (run in Windows PowerShell):

```powershell
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl get deployment metrics-server -n kube-system
kubectl get pods -n kube-system -l k8s-app=metrics-server
kubectl rollout status deployment/metrics-server -n kube-system --timeout=60s
kubectl logs -n kube-system deployment/metrics-server --tail=50
```

**Observed (S002–S006):** resources including ServiceAccount, ClusterRoles/Bindings, Service, Deployment and APIService `v1beta1.metrics.k8s.io` were created. Initially Deployment `0/1 READY`, `0 AVAILABLE` at age 20s; after ~4 minutes Pod `Running` but `0/1 READY`, restarts 0; rollout timed out. **Running ≠ Ready** (I connected this with Day 36 readiness probes). Logs reported:

```text
Failed to scrape node ... Get "https://192.168.65.3:10250/metrics/resource":
tls: failed to verify certificate: x509: cannot validate certificate
for 192.168.65.3 because it doesn't contain any IP SANs
Failed probe probe="metric-storage-ready" err="no metrics to serve"
```

**Cause:** The kubelet serving TLS certificate did not identify the IP address Metrics Server chose, so HTTPS certificate identity validation failed. No metrics were scraped; Metrics Server readiness failed. Not an Employee API deployment problem.

### Correction made for my local Docker Desktop only

The project provided a local/testing workaround `--kubelet-insecure-tls` to bypass kubelet serving certificate validation. **This weakens TLS authenticity checks and is not suitable as a default production setting**; production should use properly signed and correctly identified kubelet serving certificates. I wanted to preserve the existing five container arguments and append one sixth argument.

I first tried `kubectl edit deployment metrics-server -n kube-system`. My saved reference text showed **tabs/incorrect indentation** and even copied the explanatory comment `# Existing arguments remain here`, so the update was not applied as intended. The rollout returned `exceeded its progress deadline`. A later JSON patch attempted in Windows PowerShell was rejected (`The request is invalid: the server rejected our request due to an error in our request`); its exact server-side parsing cause was **not independently proven**. We discussed a temporary patch-file alternative but **did not observe that alternative being executed successfully**. I prepared a corrected YAML reference file, then successfully edited the live Deployment with proper indentation.

The **actual verified final live container arguments** (S010; also present in uploaded YAML reference) were:

```yaml
# Relevant section of Metrics Server Deployment, not the entire Kubernetes-generated object
apiVersion: apps/v1
kind: Deployment
metadata:
  name: metrics-server
  namespace: kube-system
spec:
  template:
    spec:
      containers:
        - name: metrics-server
          image: registry.k8s.io/metrics-server/metrics-server:v0.9.1
          args:
            - --cert-dir=/tmp
            - --secure-port=10250
            - --kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname
            - --kubelet-use-node-status-port
            - --metric-resolution=15s
            - --kubelet-insecure-tls  # local learning cluster only
          resources:
            requests:
              cpu: 100m
              memory: 200Mi
          livenessProbe:
            httpGet:
              path: /livez
              port: https
              scheme: HTTPS
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /readyz
              port: https
              scheme: HTTPS
            initialDelaySeconds: 20
            periodSeconds: 10
            failureThreshold: 3
```

**This is an explanatory excerpt, not an apply-ready complete Deployment**: the official installed Deployment also has selectors, volumes, permissions, service account, security context, etc. My uploaded `kubectl-edit-deployment-metrics-server(1).yaml` is the full **captured `kubectl edit` reference**, including a stale pre-fix `status` block, `metadata.resourceVersion`, `uid`, `last-applied-configuration` annotation and editor comment lines; I must **not blindly apply that captured whole object** to another cluster. The correct original source for reproducibility is the upstream installation manifest plus the explicitly documented local TLS argument. The verified runtime args came from:

```powershell
kubectl edit deployment metrics-server -n kube-system
kubectl get deployment metrics-server -n kube-system -o jsonpath='{.spec.template.spec.containers[0].args}'
kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s
kubectl get deployment metrics-server -n kube-system
kubectl top pods
```

**Observed (S010–S012):** output `deployment.apps/metrics-server edited`; saved arguments contained `--kubelet-insecure-tls`; rollout **successfully rolled out**; Deployment `1/1 READY`, `1 AVAILABLE`; `kubectl top pods` now worked.

### Measurements I actually saw (not fixed guarantees)

My default-namespace Employee API CPU/memory (S012):

| Pod suffix | CPU usage | Memory usage |
|---|---:|---:|
| `266dg` | 3m | 117Mi |
| `sjwzn` | 4m | 90Mi |
| `w5l7x` | 3m | 54Mi |

These are **actual sampled usage**. A Pod requesting 100m CPU can use only 3m when idle; it is not forced to consume 100m. CPU usage **3m** is approximately `0.003` CPU, or 0.3% of one CPU, while utilisation **relative to the request** is 3%. These are two different percentages.

`kubectl top pods -n kube-system` (S013) returned metrics for CoreDNS, etcd, API Server, controller-manager, scheduler, kube-proxy, storage-provisioner, vpnkit-controller and Metrics Server. Selected actual readings: CoreDNS Pods 6m/13Mi and 5m/84Mi; etcd 72m/300Mi; API Server 89m/303Mi; controller-manager 62m/117Mi; scheduler 28m/70Mi; **Metrics Server itself 9m/20Mi**. This confirmed the system components consume real resources even though Employee API was the only application I deployed.

`kubectl top nodes` (S014) showed Docker Desktop Node `1028m` CPU usage, `12%` CPU, `1381Mi` memory usage, `17%` memory at the time of capture. These percentages refer to the Node's resources, unlike HPA CPU percentages based on application CPU requests. These are snapshots, not reservations or long-term averages.

## T004 — HPA YAML, API resources, kinds, min/max and deployment ownership

### Final saved and applied `k8s/hpa.yaml` (S018–S020)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: employee-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: employee-api

  minReplicas: 3
  maxReplicas: 6

  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
```

The top-level `apiVersion: autoscaling/v2` and `kind: HorizontalPodAutoscaler` identify **the object I am creating**. Inside `scaleTargetRef`, `apiVersion: apps/v1`, `kind: Deployment`, `name: employee-api` identify **the existing target that will be scaled**. The second `kind` **does not create another Deployment**. The API version is determined by Kubernetes resource API group/version, not Python or .NET. I checked my cluster using:

```powershell
kubectl api-resources
kubectl explain deployment --api-version=apps/v1
kubectl explain horizontalpodautoscaler --api-version=autoscaling/v2
```

Observed (S015–S017): `deployments` had `apps/v1`; `horizontalpodautoscalers` had `autoscaling/v2`; `kubectl explain deployment` showed Deployment fields, metadata, spec and status. A useful mental model is “**kind at top = what I create; kind within scaleTargetRef = what it controls**.” MES analogy: a management configuration can identify its own type and separately reference the station/controller it manages.

### Every important HPA field

| Field | Actual value | Meaning and practical effect |
|---|---|---|
| `apiVersion` | `autoscaling/v2` | HPA's Kubernetes API version |
| `kind` | `HorizontalPodAutoscaler` | Creates HPA resource |
| `metadata.name` | `employee-api-hpa` | Name of autoscaler |
| `spec.scaleTargetRef.apiVersion` | `apps/v1` | API of existing Deployment |
| `spec.scaleTargetRef.kind` | `Deployment` | Resource to be scaled |
| `spec.scaleTargetRef.name` | `employee-api` | Actual existing target name |
| `minReplicas` | `3` | Cannot scale below 3 |
| `maxReplicas` | `6` | Cannot scale above 6 |
| `metrics[].type` | `Resource` | Use CPU usage resource metric |
| `resource.name` | `cpu` | Target CPU rather than memory |
| `target.type` | `Utilization` | Express target relative to requested CPU |
| `averageUtilization` | `50` | Target average **50%**, equivalent to 50m for 100m CPU request |

### My replica-boundary questions

- **Teaching scenario:** Deployment has `replicas: 3`, HPA `minReplicas: 5`, `maxReplicas: 8`. Once HPA actively controls the Deployment, it should set the desired replicas to at least **5**.
- **Teaching scenario:** Deployment `replicas: 4`, HPA `minReplicas: 2`, `maxReplicas: 6`. It **does not automatically mean exactly 2**; the target and metric determine a number between 2 and 6.
- My corrected question: Deployment has `replicas: 4`, HPA `minReplicas: 1`, **`maxReplicas: 2`**. HPA can reduce the target to **2**, even if load is high, because it must stay at or below the maximum. This requires a valid range (`minReplicas <= maxReplicas`), functional HPA and reconciliation; it's not an instantaneous deletion guarantee.
- `maxReplicas: 6` means **ceiling**, not “create six Pods now.” `minReplicas: 3` means **floor**, not “always keep exactly three.”

I chose to **retain `replicas: 3` in my existing `deployment.yaml` for my own learning**, although it is normally preferable to omit the explicit Deployment `replicas` field for an HPA-managed workload. Reapplying a Deployment manifest with `replicas: 3` can overwrite the live desired replica count temporarily, before HPA reconciles again. **This cleanup was discussed but deliberately deferred; do not document it as completed.**

### Actual creation and initial HPA status

From `01-python-fastapi` in Windows PowerShell:

```powershell
kubectl apply --dry-run=server -f .\k8s\hpa.yaml
kubectl apply -f .\k8s\hpa.yaml
kubectl get hpa
kubectl get deployment employee-api
kubectl describe hpa employee-api-hpa
```

Observed (S018–S022): server dry run reported `created (server dry run)`; actual apply reported `horizontalpodautoscaler.autoscaling/employee-api-hpa created`. At 40 seconds the first `kubectl get hpa` showed `cpu: <unknown>/50%` and `REPLICAS 0` **in HPA status**. This did **not** mean the Deployment had zero Pods. A subsequent check showed HPA `cpu: 4%/50%`, replicas **3**, and Deployment READY/UP-TO-DATE/AVAILABLE `3/3`. `kubectl describe hpa` showed `4% (4m) / 50%`, `ScalingActive=True`, `ValidMetricFound`; 4m represented approximate **per-Pod average** CPU usage relative to 100m requests. A new HPA can take a little time to receive its first usable metrics.

## T005 — The controlled CPU-load experiment, initial result and successful scale-up

### Discovering the existing endpoint (S023–S026)

I wanted a CPU-heavy endpoint rather than generating huge traffic against a normal health check. I inspected existing Python route declarations:

```powershell
Get-ChildItem .\app -Recurse -Filter *.py | Select-String -Pattern '@app.get|@router.get|@app.post|@router.post'
Get-Content .\app\routers\land.py
Select-String -Path .\app\main.py -Pattern 'include_router'
```

There was an existing `@router.get("/cpu-test")` endpoint in `app/routers/land.py`. `main.py` included that router with **`prefix=""`**, so the final route was **`GET /cpu-test`** (not `/land/cpu-test`). I also saw normal Employee API/health/MES route declarations. The CPU-test code actually used was:

```python
@router.get("/cpu-test")
def cpu_test():
    logger.info("CPU test started")
    total = 0
    for i in range(50_000_000):
        total += i * i
    logger.info("CPU test completed")
    return {"message": "CPU test completed", "result": total}
```

`50_000_000` is **50 million**; underscores improve readability. The synchronous loop repeatedly calculates and adds squares, creating CPU-bound work. The endpoint already existed in the deployed image (confirmed by a successful request), so **no new Python code, Docker rebuild or new image was required**. I did not change the 500m per-Pod CPU limit.

### Access through Service and PowerShell (S027–S029)

```powershell
kubectl get svc employee-api-service
kubectl port-forward service/employee-api-service 8000:8000
# In another PowerShell terminal, while port-forward is running:
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

Observed Service `ClusterIP`, IP `10.105.206.127`, port `8000/TCP` (internal service address; don't assume Windows can directly reach ClusterIP). Port forwarding printed `Forwarding from 127.0.0.1:8000 -> 8000` and IPv6 `[::1]`. `/health` returned `status=healthy`, `service=new-learning-api`. The port-forward terminal must remain open and can be stopped by `Ctrl+C`.

**What `Invoke-RestMethod` means:** It is PowerShell's HTTP/REST client (roughly comparable to making a request with C# `HttpClient` or Postman). With no `-Method`, it makes GET. It converts a JSON response into a PowerShell object, which the console displays in columns; the JSON did not literally originate as a table.

### First single test: succeeded but did not scale (S030–S031)

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/cpu-test" -TimeoutSec 120
kubectl top pods
kubectl get hpa
```

Observed response `message=CPU test completed` with a large integer `result` (sum of squares). Immediately **after the request finished**, my sampled `kubectl top pods` showed about `3m` for each Pod and HPA around `4%/50%`, still three replicas. **Correct interpretation:** the calculation ran successfully, but a brief CPU spike can be missed if metrics are checked after completion; Metrics Server and HPA measure periodically. It does **not** prove the endpoint used no CPU.

### Controlled repeated load: actual scale-up (S032–S035)

I kept port forwarding running in one terminal, executed a two-minute repeated test in another terminal, and checked metrics/HPA in a third:

```powershell
$endTime = (Get-Date).AddMinutes(2)
while ((Get-Date) -lt $endTime) {
    try {
        Invoke-RestMethod `
            -Uri "http://localhost:8000/cpu-test" `
            -TimeoutSec 120 | Out-Null
        Write-Host "CPU test request completed"
    }
    catch {
        Write-Host "Request failed: $($_.Exception.Message)"
        break
    }
}
Write-Host "CPU load test finished"
```

This is a **bounded repeated sequential** request loop, not a concurrent load-testing framework. A request already in flight can finish after the two-minute start-window; `Ctrl+C` stops it early. `Out-Null` discards the giant response, keeping the console readable. Repeating CPU-intensive requests maintained demand long enough for metrics/HPA reconciliation.

**Observed during the test:** One original Pod (`...w5l7x`) reached about **355m, 500m, 501m, 502m** in separate `kubectl top` samples, while most other Pods were around **2–3m**. At first HPA still showed stale `4%/50%` and 3 replicas, but a subsequent `kubectl top pods` displayed **six** Employee API Pods (three new replicas visible). The load script displayed multiple `CPU test request completed` lines and then `CPU load test finished`. Values slightly above 500m in sampled metrics do not imply a permanent bypass of the 500m CPU limit; metrics samples and CPU quota enforcement differ in granularity.

**Why only one Pod was busy:** The Service `kubectl port-forward` selected a backend Pod for the connection; it is **not a realistic Kubernetes Service load-balancing test over all Pods**. Traffic repeatedly hit the selected backend, even after HPA created additional replicas. HPA still monitors **aggregate utilisation across the Deployment**, so scale-up can occur despite some replicas being nearly idle. For a production-like distributed load test, use proper in-cluster Service access or an external/load-balancing path rather than assuming port-forward spreads HTTP requests.

**Caution about earlier illustrative values:** Example 300m on one Pod with 3m on others gave `(300+3+3)/3 = 102m average` and approximately `102%` of 100m request. These were **teaching-only values**, not measured samples. The actual measured loaded Pod was near 500m at peak; HPA's exact intermediate percentage at the scale-up decision was **not captured**. We later verified the official HPA scaling event rather than inferring it from a stale earlier percentage.

## T006 — Scale-up/scale-down events, limits, stabilisation and conditions

### Observed scale-up event (S036–S037)

```powershell
kubectl get hpa employee-api-hpa
kubectl describe hpa employee-api-hpa
kubectl get deployment employee-api
```

After test stopped, `kubectl get hpa` showed CPU about **4%/50%**, min 3, max 6, **6 replicas**. Deployment reported `6/6` ready/updated/available. `kubectl describe hpa` had an event:

```text
Normal SuccessfulRescale ... New size: 6;
reason: cpu resource utilization (percentage of request) above target
```

Conditions included `AbleToScale=True / ScaleDownStabilized`, `ScalingActive=True / ValidMetricFound`, and `ScalingLimited=True / TooManyReplicas` at that moment. **TooManyReplicas** meant HPA's calculated request for replicas exceeded `maxReplicas: 6`, so Kubernetes capped it at six; **not an error**. Importantly, the later 4% metric did not mean HPA originally scaled at 4%; those are successive samples at different times.

### Why the workload did not immediately return to three

The CPU load stopped, but the six Pods remained briefly because HPA has a **default 5-minute scale-down stabilisation window** (unless configured otherwise). The controller considers recent recommendations to avoid oscillating between replica counts during short traffic changes. Five minutes is not an exact timer measured from the Event timestamp; HPA reconciliation and recommendation history matter. My observed `AbleToScale=True / ScaleDownStabilized` supported this explanation.

### Observed final scale-down (S038–S039)

Later screenshots showed **HPA 3 replicas**, Deployment `3/3`, low CPU approximately **3–4%**, and a second HPA event:

```text
Normal SuccessfulRescale ... New size: 3; reason: All metrics below target
```

This completes real verification: **3 → 6 → 3**. The final HPA condition snapshot showed:

| Condition | Actual status / reason | What I should remember |
|---|---|---|
| `AbleToScale` | `True / ReadyForNewScale` | HPA is able/ready to manage target scaling; True **doesn't require a scaling change** |
| `ScalingActive` | `True / ValidMetricFound` | CPU metric was usable and HPA could calculate replicas |
| `ScalingLimited` | `True / TooFewReplicas` | A low-CPU calculation wanted fewer than `minReplicas: 3`; HPA correctly enforced the floor |

Example using **observed 3% utilisation** at three Pods: `ceil(3 × 3/50) = ceil(0.18) = 1`, but `minReplicas: 3` clamps the final desired count to **3**. `ScalingLimited=True` can be healthy: it means min/max constrained the computed count. During high CPU, `TooManyReplicas` meant clamped at max 6. `ScalingLimited=False` in an earlier low-load capture meant the desired recommendation was within bounds at that snapshot; these condition values can change as calculations evolve.

### Timeline — evidence, not invented timings

| Stage | What I observed | Source |
|---|---|---|
| Baseline | 3 healthy Employee API Pods, around 3–4% utilisation | S021–S022 |
| One `/cpu-test` call | Request succeeded; later sampled metrics were low; 3 Pods | S030–S031 |
| Repeated 2-min CPU test | Busy backend up to about 500m, other Pods low | S032–S035 |
| Scale-up | 6 Pods; `SuccessfulRescale New size: 6` | S035–S037 |
| Test stopped | Metrics back to ~3–4%; 6 Pods retained briefly | S036–S037 |
| Stabilisation elapsed | `SuccessfulRescale New size: 3`; Deployment `3/3` | S038–S039 |

## T007 — How I would apply this knowledge to MES, PLC, MQTT, RabbitMQ and Station Manager

My Employee API is a stateless-ish HTTP service: independent requests can generally be served by any ready replica, making CPU-based HPA a sensible first exercise. MES Station Manager is different. It may own a specific station, remember an active transaction, consume MQTT/PLC events and send state-changing commands to controllers. **Simply increasing replicas is not automatically safe.**

Example: `STN-100-XX` publishes `PLC_READY=true` through MQTT. If three Station Manager Pods each subscribe independently, one incoming event **might be delivered to multiple instances** depending on MQTT subscription patterns and broker behaviour. Duplicate MES work or conflicting writes are possible **if the application isn't designed for ownership/coordination**. Replication **does not by itself guarantee duplicates**; topic subscriptions, shared subscriptions, broker routing and application idempotency matter.

My questions before applying HPA to MES are: Which instance owns each station? Are consumer subscriptions shared or independent? How are duplicate/delayed events, ordering and retry managed? Is transaction state safely stored externally (e.g. Redis) or only in memory? If a Pod is terminated mid-transaction, can it finish, hand off or recover work? Do readiness, graceful SIGTERM handling and reconciliation prevent inconsistent station outcomes? Are station-processing steps safe to run in parallel?

CPU-based HPA also may not represent work waiting in a queue. **Teaching-only example:** message backlog rises to 2,000 while CPU sits at 35%. A RabbitMQ-backed scalable worker might benefit from queue-length/event-driven scaling (for example KEDA), **after** safe acknowledgement, ownership, retry and idempotency are designed. For an MQTT Station Manager, I must not assume RabbitMQ queue scaling directly applies. A StatefulSet can technically have HPA, but replica scaling is safe only if application identity and station ownership permit it. For station-controlled workloads I prefer predictable replicas until failover/ownership is explicitly designed.

**Interview recall:** “HPA can adjust Pod replicas from measurable demand, but my application's architecture must support multi-replica execution. For PLC/MQTT station workloads, I consider ownership, ordering, transaction state, duplicate prevention and graceful termination before autoscaling.”

## T008 — Final configuration, completed tasks and deliberate decisions

### What I actually completed

- Verified Docker Desktop cluster and three healthy Employee API Pods.
- Installed official Metrics Server, diagnosed `x509 ... doesn't contain any IP SANs`, corrected its args with `--kubelet-insecure-tls` **only for local learning**, and verified `1/1` readiness and working `kubectl top`.
- Examined actual Employee API Pod usage, Kubernetes-system Pod usage and Node-level usage.
- Created and applied `k8s/hpa.yaml`, HPA `employee-api-hpa`, CPU utilisation target **50%**, minimum **3**, maximum **6**, targeting Deployment `employee-api`.
- Understood CPU percentages and replica formula using several examples including my own **75m × 6 Pods** scenario.
- Used existing `/cpu-test` endpoint (`50_000_000` iterations) and PowerShell `Invoke-RestMethod` through `kubectl port-forward`.
- Verified real scale-up **3 → 6** and HPA `SuccessfulRescale` event, then scale-down **6 → 3** with second `SuccessfulRescale` event.
- Explained `AbleToScale`, `ScalingActive`, `ScalingLimited`, `ScaleDownStabilized`, `TooManyReplicas`, `TooFewReplicas`.
- Discussed MES Station Manager/PLC/MQTT risks rather than making a potentially unsafe autoscaling change.

### Items intentionally not completed, or not established by evidence

- I **chose to keep `replicas: 3` in `deployment.yaml`** for understanding. Removing it was proposed but not executed. Future `kubectl apply` of that Deployment may temporarily override HPA's live replica count.
- Metrics Server TLS bypass is a **local-development workaround**, not production hardening. Production certificate correction was not attempted.
- A separate standalone Metrics Server manifest specifically for reproducible Git deployment was discussed but **no final committed manifest or Git commit is evidenced** in the Day 38 material. The uploaded editor YAML is a reference snapshot, not a clean reproducible manifest.
- A controlled standalone Linux CPU throttling-counter exercise was mentioned on Day 37 but **not part of the completed Day 38 results**.
- The exact HPA metric at the instant scale-up was triggered was not captured; the HPA event confirms why it happened.
- The full actual distribution of HTTP load across all six replicas was not tested; `port-forward` sent traffic mainly to one Pod.

### Suggested Git commit once changes are staged

```text
Day 38 - Added CPU-based HPA for Employee API and verified autoscaling
```

I should review staging and avoid committing secrets, local `.env`, cache, or Kubernetes editor snapshots containing generated metadata. At minimum `k8s/hpa.yaml` is the new application file. Whether to version a cleaned Metrics Server install/customisation is a separate decision; don't automatically commit the raw `kubectl edit` dump.

## Quick recall — questions I want to answer months later

| Question | My answer |
|---|---|
| What does HPA do? | Adds/removes Pod replicas of a target Deployment based on measured metrics. |
| What does Metrics Server do? | Collects kubelet metrics and serves resource metrics through Metrics API; does not scale Pods itself. |
| `kubectl get pods` vs `kubectl top pods`? | Status/metadata vs sampled resource consumption. |
| What is CPU utilisation formula? | **Actual CPU Usage ÷ CPU Request × 100**. |
| Does 50% target mean 50m? | Only when CPU request is 100m; 50% is configured, 50m is its calculated equivalent. |
| Is target calculated from CPU limit? | No; from CPU **request**. |
| Why multiply replica formula by 3? | 3 is current replicas; scaling ratio is average utilisation / target utilisation. |
| Why can one Pod show 500m while others show 3m? | Our Service port-forward selected a backend; it did not load-balance across all Pods. |
| Why did one successful CPU-test call not scale? | It finished before later samples; short-lived load may be missed by periodic metrics. |
| What proves scale-up and scale-down? | Observed 3→6→3 Deployment/POD counts and HPA `SuccessfulRescale` events. |
| Why did scale-down wait? | Default approximately five-minute scale-down stabilisation window. |
| What is `TooManyReplicas`? | Computed recommendation above `maxReplicas` was capped. |
| What is `TooFewReplicas`? | Computed recommendation below `minReplicas` was raised to minimum. |
| Why two `kind` fields? | Top identifies HPA being created; inside `scaleTargetRef` identifies its existing Deployment target. |
| Why not blindly HPA Station Manager? | Station ownership, PLC/MQTT event ordering, state and shutdown may not be replica-safe. |

## Evidence and self-audit

The companion workbook **`Day_38_Kubernetes_HPA_Screenshot_Workbook.xlsx`** contains a screenshot index and the **39 original user-shared PNG screenshots from Day 38**, grouped chronologically in four workflow sheets. Original image pixels were not altered for content; their displayed size is scaled proportionally. The workbook includes original filenames and topic IDs in the index. Screenshots from the preceding Day 37 were deliberately excluded. The three Metrics Server YAML/text attachments from Day 38 were reviewed; the **source snapshots** are referenced for provenance but not treated as proof of a final runnable YAML save where their `status` was stale. The source discussion includes **no confirmed Day 38 Git commit**, so no commit outcome is asserted.
