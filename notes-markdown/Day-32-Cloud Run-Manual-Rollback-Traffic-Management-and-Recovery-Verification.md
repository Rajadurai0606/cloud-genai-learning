# Day 32 — Cloud Run: Manual Rollback, Traffic Management and Recovery Verification

**Status: INCOMPLETE / SOURCE COVERAGE UNVERIFIED.** The recovered Day 32 material is documented, and all 17 discovered chat-linked originals plus one additional Library original are embedded and checked. An exhaustive original-turn inventory could not be recovered, so full discussion completeness is not certified. See the companion audit for the exact retrieval limit.

## My objective and the scope I actually completed
<a id="objective"></a>

I wanted to understand what to do when an application release goes wrong after deployment. I practised moving Cloud Run service traffic to an existing older revision, checking the application, restoring my original revision, and checking it again. I used my existing learning service rather than building a new application.

The original proposed title mentioned **automated rollback**. My production-root-cause question changed the emphasis. I completed a **manual traffic rollback and restoration**. I did not implement an automatic error-rate rollback workflow, create a new Docker image, deploy a new revision, or demonstrate recovery from a real SQL Server outage. The final title above reflects the work actually completed.

My practical sequence was:

1. Understand rollback and distinguish it from preventing promotion.
2. Inspect the current revision and an older possible target.
3. Understand all three Manage traffic modes.
4. Select the older revision, review the proposed change, then save.
5. Observe migration in progress and migration completed.
6. Open Test service and Cloud Shell for an authenticated request.
7. Discover that `/health/ready` did not exist, inspect my application registration, and use `/health` successfully.
8. Restore my original revision and perform a final authenticated health check.

The original screenshots are in the companion workbook. Their stable chat-sequence IDs are S001–S017. L001 identifies an additional original recovered from Library with unverified message linkage; it is placed at its capture-time position in the Cloud Shell group. I can use the Overview Index to jump to each image, or open the original image links in the screenshot register at the end of these notes. The companion manifest and audit hold source references and verification details separately from my learning explanation.

## My starting service and prerequisites
<a id="starting-state"></a>

I reused the following learning environment. These are historical observations from the exercise, not a check of the service's live state today.

| Item | Value |
|---|---|
| Google Cloud project | `cloud-genai-learning` |
| Cloud Run service | `employee-api` |
| Region | `europe-west2` |
| Main service URL | `https://employee-api-972261256506.europe-west2.run.app` |
| Original serving revision | `employee-api-00050-ram` |
| Original traffic | `00050-ram`: 100%; `00048-del`: 0% |
| Older possible rollback target | `employee-api-00048-del` |
| Deployment identity visible in revision details | `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com`, using gcloud |
| Health response's service label | `new-learning-api` |

The Cloud Run service name and the JSON response's service label are different identifiers. I should not substitute one for the other when reproducing the evidence.

I needed access to the project in Google Cloud Console, permission to view the service and change its traffic, and a signed-in identity able to invoke this authenticated service. Cloud Shell provided a terminal and the gcloud identity-token command. I also inspected my local FastAPI `main.py` in Visual Studio Code while diagnosing the URL. The screenshots do not establish the exact IAM role grants, so I do not invent a role list here.

S001 shows my original revision selected and serving 100%. S002 shows the older revision selected while the original still serves 100%. Selecting a table row only changes which details I am viewing; it does not move traffic.

## What rollback means
<a id="rollback-meaning"></a>

I understand a Cloud Run revision as an immutable snapshot of a service deployment configuration. I can retain multiple revisions, but choose which revisions receive service traffic. For the rollback mechanism practised here, I change the routing allocation to an existing revision. I do not edit the old revision, replace one revision's contents with another, or rebuild the old image just to send it traffic.

The initial teaching example used **Revision A, Employee API version 3.0**, as previously working, and **Revision B, version 4.0**, as the new release. These version labels were an illustration, not the actual revision names of my exercise.

| Teaching state | Revision A, stable | Revision B, new |
|---|---:|---:|
| After new release promotion | 0% | 100% |
| After a justified rollback | 100% | 0% |

Rollback can reduce the time users spend on a faulty application release while I investigate a proper fix. It only helps when the earlier revision is a suitable recovery target. An earlier creation time or a green status indicator alone is insufficient evidence of suitability.

The discussion also noted that a traffic change need not be instantaneous. Requests already in progress can continue during a transition. I therefore wait for the routing operation and check the application afterward, rather than treating the click on Save as proof of recovery.

## Preventing promotion, rolling back, and recovering a dependency
<a id="prevention-vs-recovery"></a>

My previous deployment approach, recalled as prerequisite context from Day 29, was:

```text
Deploy candidate revision with 0% service traffic
    -> Run smoke test against the candidate
    -> Verify candidate
    -> Explicitly promote to 100%
```

This is a faithful reconstruction of the flow discussed in Day 32, not an original screenshot or a newly executed workflow.

If a candidate fails its smoke test before promotion, the pipeline can stop while the existing production revision keeps its traffic. That is **preventing a failed candidate from being promoted**. If I already promoted the candidate and then discover a release defect, moving traffic back is an actual **rollback after promotion**.

| Situation | What I should understand |
|---|---|
| Candidate fails at 0% before promotion | Stop the release; existing production continues serving |
| New revision causes failures after promotion | Consider routing traffic back to a verified compatible earlier revision |
| Intermittent errors after a release | Investigate logs, metrics and dependencies before choosing an action |
| SQL Server is unavailable for every revision | Restore the dependency or its connectivity; changing application revisions does not repair it |

Cloud Run supports traffic rollback operations. The lesson explicitly rejected the assumption that it automatically reverses every unhealthy application release. Application-error detection, the decision to roll back, and the automation that changes routing need appropriate implementation or configuration. The discussion did not implement such automation or specify an error threshold, monitoring policy, observation window, or rollback YAML. I should not recall those as completed Day 32 work.

## My SQL Server question and the root-cause decision
<a id="root-cause"></a>

I challenged a simplistic automatic rollback rule. My question was: if SQL Server goes offline coincidentally while I deploy a new revision, the application will log database errors. If the CI pipeline automatically reverts to the older revision, won't it fail for the same reason? I proposed investigating the production complaint first and only using Revision History → Manage traffic to send 100% to a stable revision when the evidence indicates the latest deployment caused the problem.

That reasoning was confirmed. **Errors appearing after a deployment show timing, not necessarily causation.** An error-rate increase is a symptom. I still need to identify the likely cause.

### Scenario A: my new release introduced an incorrect SQL query

This was a teaching incident, not an outage executed in the learning project. Revision A works and serves 100%. I deploy B and promote it. MES operators report failed transactions. Investigation finds that B introduced an incorrect SQL query and A used the correct query. Routing to A can help because the application change is the identified cause, assuming A remains compatible with the database and other dependencies.

### Scenario B: SQL Server went offline during deployment

This was also a teaching scenario. A was working. I deploy B at approximately the same time SQL Server becomes unavailable. B reports connection errors and production reports failures. If I immediately route back to A, A still cannot reach the unavailable server. The traffic change does not restore SQL Server. The appropriate recovery addresses database availability or connectivity.

| Question | Defective query in new release | SQL Server outage |
|---|---|---|
| Root cause | Application release defect | External dependency unavailable |
| Would the old revision help? | Potentially, if compatible | No, if it requires the same unavailable database |
| Relevant recovery action | Roll back application traffic | Restore database/connectivity |
| Is the alert alone enough to decide? | No | No |

### The incident process I want to remember

```text
Production operators report transaction failures
    -> Inspect logs, metrics, timing, dependencies and recent changes
    -> Identify likely root cause
        -> Release defect: assess old revision and compatibility
            -> If suitable, move traffic and verify recovery
        -> Dependency outage: recover dependency/connectivity
    -> Check health, real transactions, errors and operator feedback
```

This is a textual reconstruction of the process discussed. In a real MES incident, I would check that transactions are processing and obtain production-operator feedback, in addition to a technical health response. Those broader production checks were explained, not performed in my learning service.

I must also consider schema compatibility. If B changes the database schema so that A cannot operate against it, routing back to A might create another problem. A traffic rollback does not automatically reverse database migrations. My decision needs to consider code, configuration, dependencies, and data/schema compatibility together.

The resulting scope decision was to practise manual rollback and recovery verification, understand where automation might help, and avoid building a complex automatic mechanism just to finish this objective.

## Inspecting the two real revisions
<a id="revision-inspection"></a>

I opened Google Cloud Console → Cloud Run → `employee-api` → Revision History. Before changing traffic, I inspected the current revision, then clicked `employee-api-00048-del` and reviewed its visible container settings. The comparison in the discussion was:

| Configuration | `00050-ram` | `00048-del` | Meaning for my exercise |
|---|---:|---:|---|
| Traffic before change | 100% | 0% | Which revision receives main-service requests |
| Concurrency | 1 | 1 | Configured concurrent requests per instance |
| Request timeout | 300 seconds | 300 seconds | Configured request time limit |
| Revision maximum instances | 3 | 3 | Configured maximum instance count for the revision |
| Memory limit | 512 MiB | 512 MiB | Memory allocated per instance |
| Container port | 8080 | 8080 | Port the application container is expected to serve |

The original screenshots additionally show request-based billing, startup CPU boost enabled, execution environment Default, default autoscaling factors, CPU limit 1, and Sandbox launcher disabled. These were existing visible settings. I did not change them during Day 32 or record a new rationale for selecting them. The image URL is visually truncated in the source; I must not invent its complete tag or digest. The details say no build information and no source information available, with command and arguments using the container entrypoint. The Environment variables heading shows a count of 3, but their complete names and values are outside the captured view.

Matching visible settings do not establish matching code, a successful transaction history, or overall application stability. We explicitly had **not independently established `00048-del` as a known-good production revision**. This was a controlled demonstration on my learning-only service. The inspection was useful for understanding the target, but I should not rewrite the history as a production incident with a proven stable fallback.

See S001–S002 on **01 Revisions**.

## Understanding all three traffic modes
<a id="traffic-modes"></a>

I opened **Manage traffic** without saving a change. S003 shows the available modes and the current selection. The revision dropdown still contained `employee-api-00050-ram`.

| Mode | Meaning | Why I might choose it |
|---|---|---|
| Send all traffic to the latest revision | 100% follows the latest revision | When I deliberately want routing to track the newest revision |
| Send all traffic to one revision | 100% goes to the specifically selected revision | Pin production routing or perform a manual rollback |
| Split traffic across multiple revisions | Allocate percentages to several revisions | Gradual releases, canary testing, or comparison testing |

The discussion used a hypothetical new Revision C to distinguish following the latest revision from pinning one revision. I need to understand the routing intention as well as the deployment workflow. Our existing workflow intentionally deployed candidates with 0% traffic and promoted them explicitly, so we retained deliberate control instead of changing to the latest-revision mode. This does not mean a later explicit deployment command could never change routing; it means the selected traffic target in this exercise was a named revision.

The canary example was **90% stable / 10% canary**. It illustrated allowing a small portion of requests to reach a candidate before full promotion. I did not save that split. The percentages sum to 100%; no request-volume calculation or measured canary result was part of the exercise.

I kept **Send all traffic to one revision** and selected `employee-api-00048-del`. S004 records this proposed configuration. At that point, I had not yet clicked Save, so the underlying revision list still showed `00050-ram` receiving 100%. The selected dropdown and the currently serving table can legitimately differ before saving.

See S003–S004 on **02 Traffic Modes**.

## Applying my no-code manual rollback
<a id="manual-rollback"></a>

After reviewing the selected target, I clicked Save for the learning exercise. I returned to Revision History and watched the routing operation.

S005 is the **intermediate** screenshot: Updating service was Completed while Routing traffic was Active. The table still showed the original allocation while migration was underway. That screenshot is evidence of progress, not the final allocation.

S006 is the **completed** screenshot: Updating service and Routing traffic both read Completed. `employee-api-00048-del` received 100%, and `employee-api-00050-ram` received 0%. I had changed service routing without rebuilding the image, redeploying the application, or creating a new revision.

| Stage | `employee-api-00050-ram` | `employee-api-00048-del` |
|---|---:|---:|
| Original | 100% | 0% |
| Selected target, before Save | Still 100% | Still 0% |
| Completed rollback | 0% | 100% |

This proved the routing operation succeeded. It did not, on its own, prove every application function worked. I next tested the application before restoring traffic. In a real incident I would also check transactions, logs and user/operator feedback.

See S005–S006 on **03 Rollback and Restore**.

## Test service and why I did not use the generated POST as a health check
<a id="test-service"></a>

I clicked **Test** at the top of the service details. S007 captures the Test button and completed migration. S008 shows the Test service panel, its sample payload, optional query-parameter and header controls, generated CLI command, and **Test in Cloud Shell** button.

The generated request was a generic sample:

```bash
curl -X POST "https://employee-api-972261256506.europe-west2.run.app" \
  -H "Authorization: bearer $(gcloud auth print-identity-token)" \
  -H "Content-Type: application/json" \
  -d '{"name": "Developer"}'
```

This preserves the command's meaning from the panel/discussion; the panel displayed the JSON over several lines. `-X POST` explicitly selects POST, the Authorization header supplies an identity token, Content-Type describes the JSON payload, and `-d` supplies the sample data. The payload was generated by the console, not evidence that my API had a matching root POST route.

We chose a read-only GET health request instead of assuming the generated POST was an appropriate test. I did not establish a successful POST response, employee creation, or data modification in Day 32. I also did not add query parameters or additional headers through those optional panel controls.

The original assistant heading mistakenly called this “GitHub Cloud Run Test Service.” The actual panel is in Google Cloud Console; it is not a GitHub Actions run.

## Cloud Shell setup and the continuation prompt
<a id="cloud-shell"></a>

I clicked **Test in Cloud Shell**. L001 is an additional original Library screenshot from 19:18:32 showing Cloud Shell provisioning and an unarchive notice. It was not in the recovered conversation attachment inventory, so its precise message linkage remains unverified. I retained it as a Library supplement, separate from the 17 proved chat-sequence images. S009 shows Cloud Shell connecting and provisioning, with a notice that its disk might need unarchiving after a period without use. S010 shows a connected session whose project is `cloud-genai-learning`.

The generated POST text was present in the terminal, including a shell continuation prompt `>`. That prompt meant the terminal was still accepting the command entry shown in the screenshot. It was not an HTTP response or proof of successful execution.

The instruction was to press **Ctrl+C** to cancel the current command entry and return to the normal prompt, then enter the GET check. The later screenshot shows the intended curl request, but there is no separate screenshot of the Ctrl+C keystroke itself. I therefore record cancellation as the instructed step, with the subsequent terminal state supporting that I proceeded to the new request, rather than pretending every keystroke was individually captured.

Cloud Shell's welcome text also displayed the generic project-switch help command `gcloud config set project [PROJECT_ID]`. It was welcome guidance, not a command I demonstrated running. My session already reported the correct project.

See S007–S010 on **04 Test and Cloud Shell**.

## My incorrect health URL, diagnosis, and correction
<a id="health-correction"></a>

The original advice incorrectly assumed I had implemented `/health/ready` earlier. That was an unverified assumption, and the later evidence disproved it for the deployed application being tested.

### First request: proposed and then executed with the wrong path

In Cloud Shell I used:

```bash
curl -i \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://employee-api-972261256506.europe-west2.run.app/health/ready"
```

S011 shows the command entered before a response. S012 shows the response:

```http
HTTP/2 404
content-type: application/json
content-length: 22

{"detail":"Not Found"}
```

The source response's Date header was **Thu, 12 Nov 2026 19:20:38 GMT**. This was an observed failure for that route, not a successful readiness check. The original expectation had been 200, but I must preserve the actual 404 and the correction.

### What I checked in my application

I pointed out: “we don't have health/ready, i checked it and hit the right url.” S013 shows my local `main.py`, including:

```python
app = FastAPI(
    title="New Learning API",
    lifespan=lifespan
)

app.include_router(land.router, prefix="")
app.include_router(health.router, prefix="/health")
app.include_router(employee.router, prefix="/employees", tags=["employees"])
app.include_router(mes_orders.router)
app.include_router(mes_jobs.router)
```

These are inspected existing registrations, not code changes made for rollback. The `/health` prefix is important, but the full route still depends on the paths inside `health.router`. The screenshot does not display that router's implementation, so I should not claim the prefix alone proves every endpoint or database check it provides. The successful deployed HTTP request is the direct evidence for `/health` responding.

The same source screenshot contains older lifespan logging and a partial `/test-timeout` definition from Day 23. They are surrounding existing code, not Day 32 edits or a timeout exercise performed here. I did not need to change this code, rebuild Docker, or redeploy to correct the request URL.

### Corrected request and observed result

I changed the URL to the endpoint my application actually exposed:

```bash
curl -i \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  "https://employee-api-972261256506.europe-west2.run.app/health"
```

S014 shows:

```http
HTTP/2 200
content-type: application/json
content-length: 49

{"status":"healthy","service":"new-learning-api"}
```

Its Date header was **Thu, 12 Nov 2026 19:23:27 GMT**. At this stage, the completed service traffic allocation was 100% to `employee-api-00048-del`. Together, the routing evidence and request to the main service URL support the rollback-target health validation. The response body itself does not print a revision identifier; I correlate it with the routing state rather than claiming the body directly identifies the revision.

### What the command means

| Part | What I need to remember |
|---|---|
| `curl` | Sends the HTTP request |
| `-i` | Includes response status and headers so I can see the result |
| `-H` | Adds a request header |
| `Authorization: Bearer ...` | Carries the Google identity token for the authenticated service |
| `$(gcloud auth print-identity-token)` | Shell command substitution obtains the token for the signed-in identity |
| Quoted service URL plus `/health` | Sends the request to the actual health path |
| Backslash at line end | Continues the command onto the next line in this shell |

Without a POST/data option, this curl request uses GET. I did not paste a literal identity token into my notes. Token generation is shown, not a stored credential.

The earlier discussion said that a 401 or 403 should lead me to investigate authentication or permissions. Those statuses were possible troubleshooting branches, not observed responses here. The observed wrong-path result was 404. I should diagnose the actual status rather than label every non-200 response an unhealthy revision.

Most importantly, `/health` returning 200 proves that **this endpoint responded successfully**. Without inspecting its implementation and testing the required dependencies, I cannot conclude that SQL connectivity or every MES transaction is healthy. The health response is useful but bounded evidence.

See S011–S014 on **05 Health Correction**. S012 is corrected by S013–S014; it remains in the workbook to preserve the troubleshooting history.

## Restoring my original revision and validating again
<a id="restore-and-validate"></a>

After the older revision responded successfully, I restored my initial allocation:

1. Close or minimise Cloud Shell as needed.
2. Open Revision History → Manage traffic.
3. Keep **Send all traffic to one revision**.
4. Select `employee-api-00050-ram`.
5. Click Save and wait for completion.

S015 shows the original revision selected in the dropdown while the table still has the older revision at 100%. This is the restoration proposal before completion. S016 shows the completed restoration: `00050-ram` at 100%, `00048-del` at 0%, and both Updating service and Routing traffic Completed.

I then ran the same corrected authenticated `/health` command again in the existing Cloud Shell session. S017 shows **HTTP/2 200** and the same JSON health response. Its Date header is **Thu, 12 Nov 2026 19:28:09 GMT**. The assistant had described the expected result as “200 OK”; the actual curl screenshot reports HTTP/2 status 200, so I retain that exact observed protocol/status format.

| Validation point | Serving allocation established by routing evidence | Health result |
|---|---|---|
| Completed rollback | `00048-del` 100%; `00050-ram` 0% | `/health` HTTP/2 200 |
| Completed restoration | `00050-ram` 100%; `00048-del` 0% | `/health` HTTP/2 200 |

My final observed state matched the starting traffic allocation. No automatic rollback implementation was required to finish the practical objective. No new cleanup action was established as completed or required in the Day 32 conclusion. Broader production transaction testing and an actual SQL outage were outside this exercise.

See S015–S017 on **03 Rollback and Restore**, after the rollback screenshots.

## My questions, decisions, and corrections in one place
<a id="questions-and-decisions"></a>

| Question or uncertainty | Resolution and status |
|---|---|
| Should errors alone cause automatic rollback? | No. I first identify whether the release caused them; the SQL outage example explains why. Conceptual decision. |
| Is the earlier revision automatically stable? | No. Similar visible settings and an earlier creation time are insufficient. This was a controlled demonstration. |
| Does viewing an older revision change traffic? | No. Viewing details and selecting a dropdown target precede saving. Observed in S002/S004. |
| Which traffic mode did I use? | A single named revision at 100%, retained for rollback and restoration. No canary split saved. |
| Did the routing success prove incident recovery? | It proved routing completion. Application testing followed; full MES recovery was a production example. |
| Should I execute the console-generated POST? | We chose a read-only GET health check. No successful POST/data creation was demonstrated. |
| Why was `/health/ready` failing? | The route did not exist in this tested application. I inspected code and corrected the URL. |
| Did I fix code to make `/health` work? | No. I fixed the request path, then observed 200. |
| Does health 200 prove database availability? | Not from this evidence. The endpoint implementation and required operations need separate validation. |
| Did I leave the older revision serving? | No. I restored `employee-api-00050-ram` to 100% and validated again. |
| Why change the day's title? | The completed work was manual rollback, traffic management and recovery verification. Automation remained conceptual/deferred. |

## Learning direction and documentation decisions
<a id="learning-direction"></a>

Before the practical lesson, I had asked whether spending so long around Cloud Run was keeping me on track for GenAI and interviews. I clarified that I did **not** want to rush or skip essential understanding. Office priorities and tiredness meant one learning day should represent a completed objective, not necessarily one calendar day.

The earlier proposal to start GenAI from Day 34 was revised after I asked to connect the course to Kubernetes, pods, GKE, Anthos and on-premises infrastructure used in my MES environment. The updated provisional sequence was Day 33 Cloud Run versus Kubernetes, Day 34 cluster/node/pod/container basics, Day 35 deployments/services/scaling/networking, Day 36 GKE practical deployment, Day 37 Anthos/hybrid/on-premises MES, Day 38 reliability/monitoring/CI/CD overview, then GenAI from Day 39 onward. This was a flexible roadmap, not completed learning or a fixed deadline. The Day 32 conclusion specifically named Day 33 as Cloud Run versus Kubernetes, beginning from fundamentals.

Interview preparation was to continue alongside technical learning: MES/manufacturing integration, senior C#/.NET and system design, and STAR/behavioural preparation with CV/job applications. A suggested seven-hour weekly allocation was four hours cloud/GenAI, two hours MES/.NET interviews, and one hour STAR/CV/applications. This was a suggestion, not a measured study log. UniversalStep, MQTT handling, concurrency gates and real production incidents were suggested as interview material.

I wanted explanations of what a concept is, why it is needed, the problem it solves, how our implementation works, alternatives, risks and interview relevance. We agreed to avoid adding abstractions just to use a pattern. UniversalStep trigger strategies illustrated where Strategy can fit; Keyence `SemaphoreSlim`, `WaitAsync()` and `Release()` illustrated the need to understand the race condition and the reason for a gate. These were mentoring examples/context, not new Day 32 implementations. Singleton/Scoped/Transient and other .NET subjects could be explored in separate discussions without expanding the main Cloud → Kubernetes → GenAI roadmap.

For documentation, I explained that Excel is for quick visual recall and Markdown is for detailed understanding. Day 30's concept-wise sheets were easier to review than Day 31's one-image-per-sheet format. I requested grouped sheets with multiple related screenshots, a complete source review, a persistent evidence record and a full audit to prevent repeated missing-content revisions. Reorganising Day 31 remained separate work. I did not redo it as part of these notes.

The evidence record delivered with this document was assembled during this documentation task. I should not mistake it for a record captured after every original lesson segment, or assume unattended future capture and cross-chat memory are guaranteed.

## My quick recall and interview guide
<a id="quick-recall"></a>

- **Investigate first:** a release and an error can coincide without the release causing the error.
- **Release defect versus SQL outage:** reverting an incorrect query can help; reverting an application does not bring an offline database back.
- **Before promotion:** stop a failed candidate. **After promotion:** consider a justified compatible rollback.
- **Revision:** an immutable deployment snapshot. **Rollback here:** change traffic, without rebuilding an image.
- **Latest / one / split:** follow the latest revision, pin a named revision, or distribute percentages. I used one named revision.
- **Selection is not saving:** dropdown changes are proposals until applied; an active migration is not completion.
- **My sequence:** `00050-ram` 100% → `00048-del` 100% → `/health` 200 → `00050-ram` 100% → `/health` 200.
- **My mistake and fix:** `/health/ready` returned 404; I checked my app and used `/health`.
- **My health-check location:** authenticated curl in Cloud Shell, using `gcloud auth print-identity-token`.
- **My evidence limit:** health 200 is not proof of every database-backed MES transaction.
- **Production recovery:** routing + application health + transaction checks + logs + operator feedback.
- **Automation:** requires meaningful signals and safeguards; I did not implement it in this exercise.

An interview answer I can explain in my own words: I first determine whether the release caused the failure. If the problem is a compatible application regression, I can redirect Cloud Run traffic to a verified stable revision without rebuilding the image. If the problem is a shared SQL dependency outage, routing to an older revision will not fix that dependency. After any routing change, I verify actual application behaviour. In my learning exercise, I moved traffic from `employee-api-00050-ram` to `employee-api-00048-del`, corrected a mistaken health path, validated HTTP 200, restored the original revision and validated again.

## Screenshot register
<a id="screenshot-register"></a>

The following register is generated from the manifest. The companion audit contains every destination anchor, original file hash, occurrence reference and verification result.

| ID | Original screenshot | Concept / workbook sheet | Notes |
|---|---|---|---|
| S001 | [Original serving revision at 100%](evidence/images/image(20261112-190129).png) | 01 Revisions | [Section](#starting-state) |
| S002 | [Inspect older revision without moving traffic](evidence/images/image(20261112-190324).png) | 01 Revisions | [Section](#revision-inspection) |
| S003 | [Three routing modes, current named revision](evidence/images/image(20261112-190613).png) | 02 Traffic Modes | [Section](#traffic-modes) |
| S004 | [Older revision selected before Save](evidence/images/image(20261112-191121).png) | 02 Traffic Modes | [Section](#traffic-modes) |
| S005 | [Rollback migration in progress](evidence/images/image(20261112-191225).png) | 03 Rollback and Restore | [Section](#manual-rollback) |
| S006 | [Rollback completed, older revision at 100%](evidence/images/image(20261112-191254).png) | 03 Rollback and Restore | [Section](#manual-rollback) |
| S007 | [Opening Test after completed migration](evidence/images/image(20261112-191512).png) | 04 Test and Cloud Shell | [Section](#test-service) |
| S008 | [Generated sample POST and Test in Cloud Shell](evidence/images/image(20261112-191531).png) | 04 Test and Cloud Shell | [Section](#test-service) |
| L001 | [Additional Library original: earlier Cloud Shell provisioning](evidence/images/image(20261112-191832).png) | 04 Test and Cloud Shell | [Section](#cloud-shell) |
| S009 | [Cloud Shell provisioning and connecting](evidence/images/image(20261112-191855).png) | 04 Test and Cloud Shell | [Section](#cloud-shell) |
| S010 | [Connected shell with generated command entry](evidence/images/image(20261112-191909).png) | 04 Test and Cloud Shell | [Section](#cloud-shell) |
| S011 | [Incorrect health path entered](evidence/images/image(20261112-192030).png) | 05 Health Correction | [Section](#health-correction) |
| S012 | [Wrong route returns HTTP/2 404](evidence/images/image(20261112-192112).png) | 05 Health Correction | [Section](#health-correction) |
| S013 | [Inspect local FastAPI router registration](evidence/images/image(20261112-192238).png) | 05 Health Correction | [Section](#health-correction) |
| S014 | [Correct /health request returns HTTP/2 200](evidence/images/image(20261112-192342).png) | 05 Health Correction | [Section](#health-correction) |
| S015 | [Original revision selected for restoration](evidence/images/image(20261112-192624).png) | 03 Rollback and Restore | [Section](#restore-and-validate) |
| S016 | [Original allocation restored and completed](evidence/images/image(20261112-192703).png) | 03 Rollback and Restore | [Section](#restore-and-validate) |
| S017 | [Final authenticated health validation](evidence/images/image(20261112-192824).png) | 03 Rollback and Restore | [Section](#restore-and-validate) |

## Evidence and verification appendix
<a id="evidence-appendix"></a>

The original learning evidence is conversation `6ad7ba76-2eb0-83eb-9299-379b33722d4d`. The source tool returned only the latest five turns and no older cursor. Earlier original lesson text and attachment inventory were recovered through the app UI. The 17 chat-linked original Day 32 PNGs were copied out of attachment previews before those temporary previews disappeared. An additional original Cloud Shell image was subsequently recovered from Library and retained as L001, producing 18 embedded original assets in the reconciled workbook. Day 30's original workbook was inspected for its grouped-sheet structure.

The full topic mapping, source-retrieval limitations, exact screenshot/media/anchor reconciliation, final artifact hashes and visual checks are in **Day32-evidence-manifest-Reconciled.json** and **Day32-coverage-audit-Reconciled.md**. Completion status is governed by that audit; the existence of these notes alone is not a claim that every verification gate passed. The screenshot folder must remain beside these notes for relative image links to work. The all-files ZIP preserves that arrangement.
