# Day 22 — My Cloud Run health checks and application reliability notes

## 1. What I learned and what I actually changed

I used my existing FastAPI `employee-api` in project `cloud-genai-learning`, region `europe-west2`. Day 21 taught me to detect problems through request metrics, latency, server errors and alerts. Day 22 added application health checks: how to establish successful startup and detect a running container that has become unresponsive.

My `/health` implementation and HTTP startup probe already existed. I inspected and reused them. I added an HTTP liveness probe, deployed a new revision using the existing image, and verified successful startup and liveness events in logs. I did not need to change Python code, rebuild Docker or push a new image for this configuration change.

I keep these evidence categories separate:

| Category | What belongs here |
|---|---|
| Existing implementation | FastAPI health router, `/health`, HTTP startup probe |
| Entered but not yet deployed | Liveness form and `Containers *` screenshot |
| Review before deployment | Current/new configuration comparison, with immediate traffic serving selected |
| Observed deployment | Updating service, creating revision and routing traffic all completed |
| Observed runtime | Startup and liveness success events and repeated HTTP 200 health responses |
| Teaching examples | HTTP 500 probe failures, deadlocks, slow employee requests, RabbitMQ/database outages and Kubernetes Pods |
| Proposed future work | Separate live/ready endpoints and reducing routine health access logs |

**Accuracy correction, checked on 17 October 2026:** the lesson said Cloud Run services did not expose configurable readiness probes. Current Google documentation does describe Cloud Run readiness probes. I must not retain the earlier statement as a current platform limitation. This does not change my exercise record: I configured startup and liveness, and discussed readiness conceptually. No readiness endpoint or probe was implemented in this exercise. [Google Cloud health-check documentation](https://docs.cloud.google.com/run/docs/configuring/healthchecks)

## 2. My three health questions

A running process does not automatically mean useful work can be completed. In my MES environment, a controller can start, answer a heartbeat and still be unable to process production work because its database is unavailable.

| Check | My question | When it matters | Failure response |
|---|---|---|---|
| Startup | Has my application initialized and started successfully? | Initial startup of each container | Repeated unsuccessful startup checks cause startup failure and container shutdown |
| Liveness | Is my running application still responsive? | After startup, repeatedly | Consecutive failures can cause the unhealthy container to be restarted |
| Readiness | Can my application accept useful requests right now? | During operation as required dependencies change | Stop new routed traffic to an unready instance/Pod until it recovers, without a restart merely for readiness failure |

My MES recall analogy is: startup asks whether the station controller has started; liveness asks whether it still responds; readiness asks whether it can accept production work. These questions are related but have different jobs.

In Kubernetes, the readiness example concerns eligibility for traffic through the relevant Service. It is not a promise that every kind of connection or direct access to the Pod will be blocked. Cloud Run readiness is also now documented: after the configured failure threshold it stops new traffic to an unready instance, and resumes routing when readiness recovers. The startup check should already establish safe initial readiness because traffic can arrive before the first readiness check finishes. This is a current-documentation clarification, not something I tested on Day 22. [Google Cloud health-check documentation](https://docs.cloud.google.com/run/docs/configuring/healthchecks)

## 3. My existing FastAPI health endpoint

**Workbook: Step 01, image at A9.** I inspected `01-python-fastapi/app/routers/health.py` in VS Code. The original screenshot shows:

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("")
def health_check():
    return {
        "status": "healthy",
        "service": "new-learning-api"
    }
```

The router is registered in `main.py` using:

```python
app.include_router(health.router, prefix="/health")
```

The empty route suffix joins the `/health` prefix to expose `GET /health`. Returning a dictionary produces the JSON body and the normal HTTP 200 response. The string `new-learning-api` is the response's service label; it differs from my Cloud Run service name `employee-api` without implying a deployment problem.

This endpoint is a lightweight responsiveness check. It does not query the database, RabbitMQ or another external system. I reused it for both startup and liveness. Its static `healthy` field is not evidence that every business operation or dependency is healthy.

### My local test and correction

**Workbook: Step 02 and Step 03, image at A9 on each sheet.** I first opened `http://localhost:8000/`. The response contained `message: "Employee API"`, `version: "local"`, `environment: "local"` and `api_key_configured: false`. That confirmed the local application responded, but I had tested the root route rather than the dedicated health route. The missing local API key was not a blocker for this test.

I corrected the browser address to `http://localhost:8000/health`. The screenshot then showed:

```json
{"status":"healthy","service":"new-learning-api"}
```

The lesson identified this as a successful local test. The browser screenshot shows the URL and JSON; it does not display a network panel with the numerical status code. HTTP 200 is consistent with the shown handler's normal response and the explanation, while the later cloud logs explicitly show 200.

Prerequisites were the existing FastAPI project and a locally running application on port 8000. The discussion instructed me to start it if needed, but did not provide or record the exact launch command. I do not invent a command or claim a terminal execution. These were browser tests. The cloud container later listened on port 8080, so local port 8000 and cloud port 8080 must not be confused.

## 4. My startup probe was already configured

**Workbook: Step 04, image at A9.** The proposed console route was Google Cloud Console → Cloud Run → Services → `employee-api` → Edit & deploy new revision → Containers → Health checks. The actual screenshot showed an existing HTTP startup probe. I did not add a duplicate. Cloud Run has basic startup checking even without my explicit HTTP endpoint configuration; here I was inspecting an explicit check of `/health`.

| Field | Existing startup value | Meaning and practical effect |
|---|---|---|
| Probe protocol | HTTP | Calls an application endpoint rather than merely testing an open socket |
| Path | `/health` | Must match the route exposed by FastAPI |
| Initial delay | 5 seconds | Allows an initial interval before probe attempts |
| Period | 10 seconds | Spacing between startup attempts while startup is still being checked |
| Timeout | 5 seconds | Maximum wait for an individual response |
| Failure threshold | 3 | Consecutive failed checks allowed before startup fails |

The existing values were retained. They were not newly derived from measured startup requirements that day. The startup screenshot does not expose a port field; the later runtime log confirms the startup check used 8080.

My sequence is: container starts → initial delay → HTTP health attempts → startup succeeds → initial traffic and ongoing liveness monitoring can proceed. HTTP 2xx/3xx responses count as success for this HTTP probe; an HTTP 500 or a timeout is a failure.

**My understanding check:** if FastAPI starts successfully but becomes unresponsive 30 minutes later, will startup detect it? I answered no. Once startup passes, it stops checking for that container startup. It is not a permanent heartbeat. A replacement container has its own startup lifecycle.

## 5. What liveness can and cannot detect

My question was: how does Cloud Run decide an application is stuck? Is it a long process, or a container crash?

Cloud Run uses the configured probe result. It does not automatically understand the progress of every application transaction.

| Scenario from my learning | What the check sees | Meaning |
|---|---|---|
| FastAPI/Uvicorn process crashes and exits | Container terminates | Cloud Run can detect termination and start a replacement when needed; this is different from probing a still-running but stuck process |
| Process runs but `/health` cannot respond | Repeated failed or timed-out probes | Liveness can trigger recovery through restart |
| An API request takes 30 seconds | `/health` still responds | A long request alone does not fail liveness |
| RabbitMQ connection fails | Lightweight `/health` remains responsive | Liveness can still pass; a dependency failure is not automatically an unrecoverable application failure |

### My MQTT and UniversalStep example

Suppose MES receives an MQTT message and starts a UniversalStep transaction. In scenario A, processing takes 30 seconds while the health endpoint answers normally. Liveness passes; duration alone is not a reason to restart.

In scenario B, an application deadlock prevents `/health` from responding. Three consecutive failed liveness checks reach the configured threshold and Cloud Run restarts the unhealthy container.

There is a blind spot: if only the UniversalStep processing thread is deadlocked but the health endpoint still responds, this basic probe can pass. My health check can only judge what it actually observes.

### My employee API example

I was asked whether a 60-second request would cause a restart while `/health` kept returning 200 every 10 seconds. My answer was that liveness only calls the configured health URL.

| Teaching endpoint | Example result | Liveness implication |
|---|---|---|
| `GET /employees/1` | 60 seconds | Slow business request |
| `POST /employees` | HTTP 500 | Business operation failed |
| `GET /health` | HTTP 200 | Probe passes, so these probe checks do not request a restart |

The qualification matters: slow or stuck work can exhaust application resources. If that also prevents `/health` responding within the timeout, liveness can fail indirectly.

I therefore need three separate observations: liveness for responsiveness, latency metrics for slowness and 5xx metrics for server failures. A heartbeat response from an MES station controller does not prove its production operation is succeeding. Day 21's metrics remain useful; Day 22 does not replace them.

## 6. My liveness configuration and why the fields matter

**Workbook: Step 05, image at A9 and field explanations below the image.** I opened Health checks → Add health check and selected Liveness check. I reused `/health`; `/health/live` was an alternative discussed, not a route I created.

| Field | Entered value | Why it fits and how it interacts |
|---|---|---|
| Health check type | Liveness check | Governs restart decisions for a running container |
| Probe type | HTTP | Uses my existing FastAPI endpoint |
| Path | `/health` | Uses the same lightweight route already tested locally |
| Port | 8080 | Matches the cloud container listener; not local port 8000 |
| HTTP headers (optional) | Unchecked | No custom headers were entered in the shown form |
| Initial delay | 5 seconds | Initial wait; liveness is also gated by successful startup |
| Period | 10 seconds | Approximate interval between probe attempts |
| Failure threshold | 3 | Requires consecutive failures, rather than reacting to one transient failure |
| Timeout | 1 second | Suitable for a simple lightweight handler; normal contention could require later tuning to avoid false failures |

The form says timeout must not exceed period; mine satisfies `1 second ≤ 10 seconds`. Its visible helper ranges are initial delay 0–3600 seconds, period 1–3600 and timeout 1–3600. I preserve those as text visible in my original UI screenshot, not as a claim about every current backend limit. The failure-threshold helper says “before marking the container as Unready”; because this is a liveness form, the behavior to remember is restart after the configured consecutive failures, not just Kubernetes-style traffic removal.

The earlier conceptual example used a **5-second liveness timeout**. My actual entered and deployed liveness timeout was **1 second**. My startup timeout remained 5 seconds. This difference is deliberate and must not be lost in my notes.

### My illustrative timelines and timing calculations

The first teaching timeline used period 10 seconds, timeout 5 seconds and threshold 3:

| Time | Teaching event |
|---|---|
| 10:00:00 | Health succeeds |
| 10:00:10 | First failed check |
| 10:00:20 | Second failed check |
| 10:00:30 | Third failed check; threshold reached |

The later timeline used immediate HTTP 500 responses with checks at relative 0, 10 and 20 seconds, followed by restart. These are compatible: one starts from the last successful check and the other from the first failure.

For three attempts at 10-second intervals, the elapsed span from first attempt start to third attempt start is `(3 − 1) × 10 seconds = 20 seconds`. If the first failing probe occurs 10 seconds after the last success, the span from that last success to the third attempt is `3 × 10 seconds = 30 seconds`. A timed-out final attempt also takes its timeout before its result is known. These are explanatory calculations, not a measured restart time or a service guarantee; scheduling, response durations and restart handling affect reality. I did not deliberately make `/health` fail and measure a restart on Day 22.

## 7. From unsaved changes to deployed revision

**Workbook: Step 06 → Step 07 → Step 08, each image at A9.** I clicked Add to put liveness into the pending configuration. Both probes appeared, but `Containers *` showed unsaved changes. Seeing the new settings in that screen did not mean the running revision had changed.

The comparison before deployment showed the existing startup probe on the Current side and retained startup plus new liveness on the New side:

| Setting | Startup retained | Liveness added |
|---|---|---|
| Endpoint | HTTP `/health` | HTTP `/health` |
| Period | 10 seconds | 10 seconds |
| Initial delay | 5 seconds | 5 seconds |
| Timeout | 5 seconds | 1 second |
| Failure threshold | 3 | 3 |

The review screen had **Serve this revision immediately** checked. Its explanation said 100% of traffic would migrate to this revision, overriding existing traffic splits if any. I then deployed the configuration. The completion screenshot showed Updating service, Creating revision and Routing traffic all Completed.

The earlier general instruction said Save/Deploy or its equivalent. My actual review screenshot shows **Deploy changes**. A configuration-only deployment creates a revision using the existing image. It does not rebuild source code, and therefore cannot include unrelated local-only code edits unless a new image is built separately.

## 8. My observed log evidence

**Workbook: Step 09, original image at A9; explanations and calculations below it.** I navigated to Cloud Run → `employee-api` → Observability → Logs, using the latest revision or a recent time range. I looked for startup, probe failures and restart events. My actual screenshot contains success evidence, not a deliberately induced failure.

| Timestamp shown, 17 October 2026 (BST) | Visible event | What I can conclude |
|---|---|---|
| 08:46:50.278 | Starting new instance, `DEPLOYMENT_ROLLOUT` | Deployment caused a new instance to start |
| 08:46:55.555 | Started server process `[1]` | Uvicorn process started |
| 08:46:55.556 | Waiting for application startup; application startup complete | FastAPI initialization completed |
| 08:46:55.558 | Uvicorn running on `http://0.0.0.0:8080` | Cloud listener uses port 8080 |
| 08:47:05.602 | STARTUP HTTP probe succeeded after 2 attempts, container `employee-api-1`, port 8080, `/health` | Startup eventually passed |
| 08:47:05.603 | `GET /health HTTP/1.1` 200 OK | Application access log records success |
| 08:47:05.680 | Revision `employee-api-00022-m5v` Ready condition True | New revision became ready |
| 08:47:06.995 | Service Ready condition True | Service readiness condition changed |
| 08:47:10.605 | Health 200 and LIVENESS HTTP probe succeeded | Running container passed liveness |
| 08:47:20.607 through 08:48:50.624 | Repeated health 200 responses | Continuing health requests at approximately 10-second intervals |

The log explicitly says only the first successful liveness probe per revision is logged. That platform event is different from Uvicorn's repeated application access logs. Before seeing these logs, the explanation warned that absence of individual health request entries would not by itself prove probes were broken. My screenshot then supplied positive evidence for both probe types.

The phrase “after 2 attempts” proves the count reported and eventual success. It does not show the first attempt's exact response, status or cause. The earlier wording suggested the container may not have been ready; I treat that as a possible explanation, not a proven diagnosis. I cannot claim a specific first-attempt error without its record.

For a reproducible observed interval calculation, I take `08:47:20.607 − 08:47:10.605 = 10.002 seconds`. The next is `08:47:30.609 − 08:47:20.607 = 10.002 seconds`. These support “approximately every 10 seconds.” They do not establish the exact initial-delay reference point. The workbook calculates these differences from numeric seconds after midnight.

My answer to the failure question was that three failed attempts cause a restart. The correction is **Cloud Run performs the checks**, not the application retrying itself. A liveness restart concerns the unhealthy instance, not necessarily every instance of the service. A normal endpoint's HTTP 500 alone is not the same as an HTTP 500 from the configured probe endpoint.

## 9. My readiness and shared-database reasoning

The Kubernetes teaching example had `/health/live` returning 200, the database connection failing and `/health/ready` returning 503. I chose option B: keep the application running but stop routing new Service requests to that Pod. Restarting MES would leave the same external database problem in place.

With three MES Pods sharing one database, all three can be live and all three unready. Their containers keep running, but no ready Service endpoints remain, so new requests through that Service may fail until readiness recovers. Readiness prevents routing to known-unready Pods; it does not restore the database or guarantee availability when every backend is unready.

I would investigate database logs, connectivity, credentials, connection exhaustion and resource availability. My initial phrase “database service is stopped” was too specific: a connection failure can also mean a running database is unreachable or rejecting access.

The proposed future routes were `/health/live` for responsiveness and `/health/ready` for business readiness. They were not implemented. I also need to decide which dependencies are essential. An optional external service outage should not automatically make the whole application unready.

## 10. Final state, deferred work and quick recall

The observed final exercise state is a deployed revision with startup retained, liveness added and successful checks in logs. No deliberate liveness failure, measured restart, database outage or Kubernetes deployment was performed in this exercise. The lesson mentioned minimum instances 0, meaning the service can scale to zero; probes do not keep an idle instance permanently running. The Day 22 screenshots do not independently expose that scaling setting, and I did not change it here.

Reducing routine `/health` access-log volume was a production improvement suggestion, not a completed configuration change. Readiness implementation was deferred. The preceding Day 21 material had deferred removing `/test-500` until a later code/image deployment and had disabled, rather than deleted, the temporary alert policy. Day 22's existing-image probe deployment is not evidence that `/test-500` was removed. I retain this as carried-forward cleanup context, not a newly verified cleanup result.

| If I need to recall… | My short answer | Workbook evidence |
|---|---|---|
| Health code and response | Lightweight static FastAPI JSON; no dependency tests | Step 01, A9 |
| Wrong local test | Root response is not the health response | Step 02, A9 |
| Correct local test | Browse `/health` on local port 8000 | Step 03, A9 |
| Startup | Already configured; stops after success | Step 04, A9 |
| Saved liveness timeout | 1 second; the 5-second example was illustrative | Step 05, A9 |
| Pending versus deployed | `Containers *` means pending changes | Step 06, A9 |
| Deployment review | Startup retained, liveness added; immediate 100% traffic selected | Step 07, A9 |
| Deployment success | All three rollout stages completed | Step 08, A9 |
| Runtime verification | Startup and liveness passed; periodic health 200s | Step 09, A9 |
| Slow or failed business request | Does not alone fail the lightweight liveness route | Sections 5–6 |
| Live but not ready | Keep running, withdraw new routed traffic, investigate dependency | Section 9 |

## 11. Documentation verification and evidence boundaries

I reviewed the original Day 22 material from its explicit start through the documentation request, including all nine original screenshots. The first retrieval exposed only five recent turns; browser access recovered earlier messages and original image files. The workbook embeds those nine images in chronological workflow order, preserves their full contents and proportions, and provides an index and explanations. I did not replace originals with recreated diagrams.

No original Day 22 screenshot was missing from the recovered sequence. The source contains no separately demonstrated HMI example beyond the MES/controller analogies recorded above, no exact local start command, no new YAML or CLI deployment command, and no observed fault-injection result. I therefore have not invented any of these. My added calculations are explicitly labelled as explanatory or derived from visible timestamps. The current readiness-support correction is separated from the historical exercise.
