# Day 23 — Cloud Run Resilience: Timeouts, Retries and Graceful Shutdown

## 1. My learning outcome and evidence

I learned how to bound HTTP waiting, make retries safe, and understand orderly application shutdown without confusing any of those with a guarantee that a business transaction completed. My practical work used my existing FastAPI `employee-api` service. I verified a Cloud Run timeout, restored the service configuration, and tested FastAPI lifecycle handling locally with and without an active request.

My main learning objectives are complete. Final removal of demonstration code and deployment of a cleaned image remain deferred: I do not have evidence that those actions were completed.

These notes use my original Day 23 messages and explanations, from the initial topic proposal through the final documentation request, and 25 recovered original screenshots. The accompanying **Day-23-Cloud-Run-Resilience.xlsx** embeds those images. References such as **S09** identify its numbered image sheets; each image starts at **B9**. The Index gives the caption, workflow stage and corresponding notes section.

I distinguish four kinds of information:

| Label | How I interpret it |
|---|---|
| Observed | Visible in my original screenshot or terminal output |
| Original discussion | Explanation, question, instruction or decision recovered from the original messages; not proof of a deployment |
| Teaching example | Illustrative values or code used to explain a concept |
| Proposed / deferred | Suggested action without evidence that I completed it |

The continuation handover was also recovered. It is secondary context, not a replacement for the original discussion. Earlier retrieval limitations have been resolved for the Day 23 text and the 25 relevant workflow images. Exact Docker build/push commands and a final cleanup commit or deployment are not evidenced, so I do not reconstruct them as historical facts. This is a record of the session, not a live audit of my current cloud service.

## 2. Why I changed the Day 23 topic

The first proposal repeated scaling and concurrency. I recognised that I had covered these on Day 16 and asked for clarification. We changed the topic to resilience.

My answer to the initial question was correct: changing concurrency from 1 to 10 means **one instance may accept up to ten simultaneous requests**. It does not instruct Cloud Run to create ten instances. Concurrency is overlapping work; parallelism means work actually executing at the same time. They are related but are not interchangeable settings.

The initial PLC analogy had Station A, B and C all sending requests. With two available instances and concurrency 1, A can occupy instance 1 and B instance 2. C waits for capacity or may eventually fail if it cannot be served. Autoscaling takes time. This is an explanation, not a Day 23 load-test result.

The recalled Day 16 work included minimum/maximum instances, autoscaling, two containers from one image, a 10-second delay and overlapping requests, instance IDs `a3241268` and `6ea40b99`, and the fact that an in-memory `employees` list is not shared across instances. Those are prior-day context, not new Day 23 measurements.

## 3. Request timeout: what ends and what may continue

A request timeout bounds how long the HTTP response can take. In my Cloud Run experiment, crossing that boundary produced **HTTP 504 Gateway Timeout**. It did not prove that Python stopped, that the container restarted, or that SQL rolled back.

The first teaching example was `GET /employees/101`, normally taking 100 milliseconds but potentially taking 45 seconds because of a slow query. A hypothetical 30-second timeout makes the caller receive a timeout before the 45-second operation would finish. The container is not automatically restarted simply because this request timed out.

I answered that application execution may continue after the caller receives 504. My original wording sounded certain that it *will* continue. My corrected understanding is **may continue**: CPU availability, cancellation, errors and instance termination can affect what happens afterward. In request-based billing I must not rely on post-response work as a durable worker.

### My MES DML question

I asked what happens when my MES Station Service console application calls MES API, SQL DML is still running, and the Station Service catches a failure and retries because the operation is important.

The important point is that the caller has an **unknown business outcome**. No successful response arrived, but the original DML may still commit. Retrying as a new operation can duplicate a production result.

This was our teaching timeline, not a measured trace:

| Elapsed time | Possible event |
|---:|---|
| 0 s | Station Service sends request A |
| 5 s | MES API starts database work |
| 30 s | Caller timeout or Cloud Run 504, depending on which limit applies |
| 31 s | Station Service sends request B as a retry |
| 40 s | Original request A may commit |
| 45 s | B may perform the same business DML again without protection |

The related responsibility timeline used 10 seconds as an intermediate point while Cloud Run was still waiting and MES API was doing DML. At 30 seconds Cloud Run returned 504; at 31 seconds a retry could arrive; at 40 seconds the original could commit. These examples explain a race, not guaranteed post-timeout execution.

| Component | My responsibility model |
|---|---|
| MES Station Service | Assign an operation ID, choose safe retries, retain unresolved work and reconcile |
| Cloud Run | Route requests, run/scale instances, enforce the request boundary and configured health checks |
| MES API | Validate requests and keys, coordinate idempotency, execute business logic, return saved outcomes |
| SQL database | Enforce uniqueness and transaction consistency |

Cloud Run does not understand `OrderId`, `TransactionId` or my DML semantics. It does not provide exactly-once business execution.

### Why not just wait longer?

I asked why a timeout helps if processing may continue, and whether waiting would be better for important DML. My example of an operation running infinitely was a useful case, but there are more reasons to bound waiting.

Our MES example normally took 2 seconds. A blocked query might take 10 minutes. Setting a 30-minute request timeout leaves the Station Service waiting, ties up HTTP resources and can make other requests queue, especially at concurrency 1. A timeout gives the caller a point at which it can report an uncertain result, investigate or recover.

Other examples were an external supplier API that never responds, an unresponsive network connection, an infinite loop and abnormal latency. Ending the HTTP wait does not necessarily release every resource still used by application work. I need application timeouts/cancellation, safe retries and monitoring as well.

For a normal operation taking 2 seconds and occasionally 5 seconds, a 30-second timeout was a teaching suggestion. **It was not my saved Cloud Run configuration.** For an operation legitimately taking minutes, we discussed a durable asynchronous workflow:

1. Station Service submits `/complete-order` with its TransactionId.
2. MES API durably records or queues the request and returns **202 Accepted**.
3. An independently managed worker processes it.
4. Station Service polls status or receives a completion event: Processing, Completed or Failed.

202 means accepted, not completed. An untracked thread started inside a request handler does not provide the durability of this design. This was architecture discussion; I did not implement a queue or worker in Day 23.

## 4. Idempotency: my API logic and SQL must cooperate

Idempotency means repeated requests for the **same logical operation** do not create extra business effects. Our example was calling `CompleteOrder(OrderId = 1001)` twice while completing the order only once.

The caller can use a GUID or an operation identifier. Examples included `STATION01-ORDER1001-COMPLETE` and `TX-1001`. These strings illustrated identity; they were not new production identifiers configured on Cloud Run. The caller must reuse the same key for every retry of that operation. A new operation gets a new key.

I initially thought idempotency meant SQL rejects a duplicate GUID. I asked whether Cloud Run protects anything here and whether we write logic based on the key. The answer was that a database constraint is essential coordination, but the API still needs the decision logic and response handling.

### Why a unique constraint alone is incomplete

This was the SQL teaching example:

```sql
CREATE TABLE ProductionResult (
    Id INT PRIMARY KEY,
    TransactionId UNIQUEIDENTIFIER UNIQUE,
    OrderId INT,
    Result VARCHAR(10)
);

-- Illustrative insert; '...' is a placeholder, not an executable GUID.
INSERT INTO ProductionResult VALUES (1, '...', 1001, 'PASS');
```

A second insert with the same TransactionId is rejected. If my API turns that constraint exception into a generic 500, the Station Service may keep retrying an operation that already succeeded. The API should understand a duplicate operation and return the appropriate stored outcome.

| Incoming request | Intended API behaviour |
|---|---|
| First `TX-1001` | Atomically reserve the key, execute business work, commit and retain the outcome |
| Same key after completion | Return the previous successful business response without repeating DML |
| Same key while processing | Return a defined processing state or coordinate with the original work |
| Same key, different payload | Reject conflicting key reuse, for example with 409 |
| New `TX-1002` | Treat as a new logical operation, subject to business validation |

I need to retain request information or a fingerprint to distinguish a real retry from different data using the same key.

The conceptual C# explanation was:

```csharp
public async Task<CompleteOrderResponse> CompleteOrderAsync(
    CompleteOrderRequest request)
{
    // Conceptual example, not complete production code.
    var existing = await repository
        .GetByTransactionIdAsync(request.TransactionId);

    if (existing != null)
    {
        if (existing.RequestDataDoesNotMatch(request))
            throw new ConflictException();

        if (existing.IsCompleted)
            return existing.SavedResponse;

        return new CompleteOrderResponse { Status = "Processing" };
    }

    // Must reserve atomically, perform DML and save the result safely.
    return await ProcessAndSaveResultAsync(request);
}
```

That initial lookup is **not concurrency-safe by itself**. Instance A and instance B can both read “not found.” A database-enforced unique key and atomic handling must decide which request owns the operation. The loser handles the duplicate safely. The idempotency record and SQL business changes need transaction protection so a crash between steps does not leave contradictory results. I did not implement this repository or transaction design in my FastAPI exercise.

### How this differs from my SemaphoreSlim gate

My per-step `SemaphoreSlim` gate prevents concurrent `PLC_READY=true` callbacks entering the same in-process step. It protects one running process. It does not coordinate another Cloud Run instance or survive a restart. Durable idempotency protects the logical operation across HTTP retries, instances and restarts.

For critical production work, the Station Service may also need a durable pending-operation record. A final failed retry must not make the operation disappear, and a restart must not cause it to get a fresh identity accidentally.

If SQL work also publishes RabbitMQ events, a SQL transaction alone cannot make both systems atomic. We identified the **transactional outbox** as a future concept for preventing missing or duplicate external effects. No outbox was implemented in Day 23.

## 5. Retries and HTTP status codes

My proposed `catch (Exception)` and retry approach was too broad. Invalid input, missing permission and temporary service failure require different responses. Even a 500 can leave DML outcome uncertain, so a status code alone does not establish that repeating a write is safe.

The original C# retry illustration generated the GUID outside the loop:

```csharp
var transactionId = Guid.NewGuid().ToString();

for (int attempt = 1; attempt <= 3; attempt++)
{
    try
    {
        await CallMesApiAsync(transactionId);
        break;
    }
    catch (HttpRequestException) when (attempt < 3)
    {
        await Task.Delay(TimeSpan.FromSeconds(attempt * 2));
    }
}
```

This is teaching code. It does not fully implement status selection, timeouts, cancellation, durable failure handling or reconciliation. The third failure escapes the filtered catch. HTTP error responses also require deliberate handling in the real HTTP client; they are not universally caught merely by receiving a non-success status.

For this illustration, waits are `1 × 2 = 2 seconds` after attempt 1 and `2 × 2 = 4 seconds` after attempt 2. Total scheduled delay is `2 + 4 = 6 seconds`, excluding API execution time. Three attempts means the initial call plus at most two retries. This is a bounded linear delay example, not an implemented exponential-backoff policy. Where applicable, a real policy respects `Retry-After` and has explicit final-failure handling.

I said I did not know every HTTP code. I can recall the families first:

| Family | Meaning | Example |
|---|---|---|
| 1xx | Informational processing response | Request-processing information |
| 2xx | Success | 200 |
| 3xx | Redirection | 301 Moved Permanently |
| 4xx | Request, identity, permission or rate problem | 400 |
| 5xx | Server or gateway problem | 500 |

| Code | Meaning | My MES / Cloud Run example and response |
|---:|---|---|
| 200 | OK | Order retrieval succeeds; my timeout endpoint also returned 200 |
| 201 | Created | New production record created |
| 202 | Accepted | Durable long operation accepted; completion still pending |
| 204 | No Content | Update succeeds without a response body |
| 400 | Bad Request | Invalid Station Service input; repeating unchanged input usually cannot fix it |
| 401 | Unauthorized | Authentication missing or invalid |
| 403 | Forbidden | Identity lacks required access; credentials alone are not permission |
| 404 | Not Found | Order or route does not exist |
| 409 | Conflict | Same idempotency key used for different data |
| 429 | Too Many Requests | Enforced request/rate limit; retry only according to policy |
| 500 | Internal Server Error | Application failure, such as an unhandled SQL exception |
| 502 | Bad Gateway | Gateway receives an invalid upstream response |
| 503 | Service Unavailable | Service temporarily cannot handle the request |
| 504 | Gateway Timeout | Gateway did not receive a response within its deadline |

A SQL exception does not automatically map to 500: my API's exception handling decides the mapping. Likewise, a client-side timeout is not an HTTP status code. It means the caller stopped waiting and might have received no HTTP response at all. In my actual Cloud Run test, I received an explicit 504 response.

My practical rule is to classify the error, reuse the operation key, bound/delay retries and reconcile an unknown result. I should not assume all 5xx responses mean “no database change happened.”

## 6. My actual configuration and the Console correction

I could not find the suggested **Edit & deploy new revision** button. My screenshots showed the newer tabbed service interface. I found **Request timeout under Scaling** instead. That UI correction matters when repeating the exercise. S01 shows the initial Containers page; S02 shows the original Scaling configuration.

| Field | Observed value | Meaning and practical effect |
|---|---|---|
| Project | `cloud-genai-learning` | Selects my learning cloud resources |
| Region | `europe-west2` | Service region and Artifact Registry hostname prefix |
| Service | `employee-api` | The existing service used for this exercise |
| URL | `https://employee-api-972261256506.europe-west2.run.app` | Base address; `/test-timeout` is the temporary route |
| Authentication | Private service; authenticated curl used | Identity token and invoker permission are needed |
| Scaling mode | Auto scaling | Cloud Run adjusts instance count according to demand |
| Minimum instances | 0 | Allows scale-to-zero; warm capacity is not guaranteed |
| Maximum instances | 2 | Configured scaling limit; not an instruction to keep two running |
| Maximum concurrent requests per instance | 1 | One routed concurrent request per instance; separate from instance count |
| Billing | Request-based | CPU limited outside request processing, relevant to unreliable post-response work |
| Original timeout | 300 seconds | Existing value, equivalent to five minutes |
| Experiment timeout | 15 seconds | Deliberately shorter than the 25-second simulated operation |
| Restored timeout | 300 seconds | Final evidenced service setting after the experiment |

I did not change minimum/maximum instances, concurrency or billing in Day 23. Their original selection rationale belongs to earlier lessons. Here I preserved them to isolate the timeout experiment.

The initial Containers screenshot also records existing settings, not new Day 23 changes:

| Field | Value visible in S01 | Why it matters |
|---|---|---|
| Container image | Artifact Registry image with digest beginning `e0b1bb6` | Initial image; full digest is truncated in the field |
| Container name | `employee-api-1` | Identifies the configured container |
| Container port | 8080 | Cloud Run routes traffic to this port; application must listen on its supplied port |
| Container command / arguments | Blank | Uses the image's configured entry point without these overrides |
| Memory / CPU | 512 MiB / 1 vCPU | Existing per-instance resources, unchanged in this exercise |
| `APP_VERSION` | `3.0` | Existing application configuration value |
| `APP_ENV` | `staging` | Existing environment label |
| Secret mapping | `API_KEY` → `EMPLOYEE_API_KEY`, version 1 | Secret reference; screenshot does not disclose the secret value |
| Ephemeral disk | Unchecked | No new option enabled in that visible control |

The Scaling page also showed Manual scaling unselected, Instance-based billing unselected, and **Customize autoscaling factors** collapsed. I do not infer hidden advanced settings, probe values or volumes from those controls. The UI displayed a maximum timeout of 3600 seconds; that was a limit shown by the interface, not my chosen value.

The hypothetical 30-second timeout was never my observed saved setting. With my restored 300-second setting, a 40-second operation does not time out merely because 30 seconds elapsed, assuming no shorter timeout elsewhere.

## 7. My timeout exercise, in actual workflow order

### Replace the old temporary test route

I confirmed that the Day 21 `/test-500` endpoint still existed. S03 preserves the pre-change code: it deliberately raised an HTTPException with status 500 for monitoring. I replaced that temporary route instead of accumulating test routes.

I added `import asyncio` among my imports and used this Day 23 code in `app/main.py`:

```python
import asyncio

# Day 23 - Temporary endpoint to test Cloud Run request timeout.
# Remove after testing.
@app.get("/test-timeout")
async def test_timeout():
    await asyncio.sleep(25)
    return {
        "status": "completed",
        "message": "Request completed after 25 seconds"
    }
```

`asyncio.sleep(25)` yields while waiting, so it simulates a slow operation without blocking the event loop like `time.sleep(25)` inside this async function. It performs no actual SQL DML. A returned message claiming 25 seconds is not itself a stopwatch measurement.

The proposed local launch command was `uvicorn app.main:app --reload`, run from the project directory with dependencies available. Then I opened `http://localhost:8000/test-timeout`. S04 shows the successful JSON. This local test does not pass through Cloud Run and therefore does not test Cloud Run's 300-second timeout.

### Build, select and deploy the changed application

I asked whether to deploy first. A proposed sequence was to build/push a new image, deploy at 300 seconds, establish a cloud baseline, then change timeout to 15 seconds. **The actual screenshots show a combined deployment of the new image and 15-second timeout.** I should remember the actual sequence rather than turn that proposal into an observation.

S05 shows Artifact Registry selection of **v16**, with digest prefix `6a2f17f349`. The repository shown was `europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api`. S06 shows the pending 15-second setting. S07 reviews both timeout and image changes, including **300 → 15 seconds** and Serve this revision immediately checked. S08 shows update, revision creation and traffic routing completed.

The discussion says the changed Docker image was built and pushed, and the selected image is evidenced. The exact build and push command strings are not present in the recovered Day 23 material. I do not invent tags, command flags or a full digest. Changing a service timeout alone would not upload my changed local Python code.

### Authenticate and test Cloud Run

I pointed out that the service was private and needed curl with a token. I ran these commands in PowerShell where Google Cloud CLI was configured:

```powershell
$token = gcloud auth print-identity-token

curl.exe -i -H "Authorization: Bearer $token" `
  "https://employee-api-972261256506.europe-west2.run.app/test-timeout"
```

Prerequisites were an authenticated gcloud identity and permission to invoke this service. `-i` includes HTTP response headers. `-H` supplies the bearer-token header. The PowerShell backtick continues the command onto the next line; it must be at the line end. I used `curl.exe` explicitly. No token value needs to be preserved in my notes.

S09 shows **HTTP/1.1 504 Gateway Timeout**, with body `upstream request timeout`. A proposed output had used HTTP/2 504; my observed protocol was HTTP/1.1. The meaningful comparison is the status, not forcing the protocol version to match an example.

I then opened Cloud Run → employee-api → Observability → Logs. S10 records `GET /test-timeout`, status **504**, **15.001 s**, **72 B** and client **curl 8.21.0**. Nearby `/health` entries show 200, but that does not establish that my timed-out business request finished.

The response Date header is 18:22:44 GMT on 20 October 2026. The request log timestamp is 19:22:29.897 BST, with a duration of 15.001 seconds. BST is one hour ahead of UTC: the log's request start around 18:22:29.897 UTC plus 15.001 seconds gives around 18:22:44.898 UTC. The screenshot headers are not evidence of conflicting tests.

### What I proved and what remained unknown

| Point | Evidence-based conclusion |
|---|---|
| Timeout was enforced | Yes: 504 and duration close to 15 seconds |
| Authentication reached the request | Authenticated request produced the timeout response |
| Python completed after the 504 | Not proved: no endpoint completion log after sleep |
| SQL committed / rolled back | Not tested: endpoint was a sleep simulation |
| Container restarted because of timeout | Not demonstrated |

We decided another deployment merely to add a completion log was unnecessary for this lesson. Cancellation and stronger continuation verification were left for future exploration.

### Restore and retest

I returned to Scaling, restored 300 seconds, reviewed the diff and deployed. S11 shows the pending restored value; S12 explicitly shows **15 → 300 seconds**. S13 confirms update service, creation of revision and traffic routing completed. S14 shows the authenticated request returning **HTTP/1.1 200 OK** and the expected completed JSON. I retained v16 for this restoration. This establishes both outcomes for the same 25-second endpoint, without claiming an earlier separate cloud baseline deployment.

## 8. My calculations and timing interpretation

| Calculation | Inputs and working | Result and interpretation |
|---|---|---|
| Original timeout in minutes | 300 s ÷ 60 s/min | 5 min |
| Simulated work beyond temporary limit | 25 s − 15 s | 10 s nominal excess; not proof of actual post-timeout CPU execution |
| Log duration difference | 15.001 s − 15.000 s = 0.001 s; × 1000 ms/s | 1 ms above configured boundary; near-boundary observation, not a latency guarantee |
| Restored nominal margin | 300 s − 25 s | 275 s of arithmetic headroom; ignores startup, scheduling and other overhead |
| Local active-request example | 25 s total − about 5 s before Ctrl+C | About 20 s remaining; 5 s was an instruction, not measured in the screenshots |
| Compare with Cloud Run termination window | About 20 s remaining − 10 s window | About 10 s short in that hypothetical case |
| Long transaction teaching example | 40 s of work − 10 s shutdown window | 30 s short if all 40 s remain when termination begins |

My cloud experiment timeline was request start, timeout near 15 seconds and hypothetical application sleep completion at 25 seconds. That final event was unverified in the 504 test. After restoration, the client received completed JSON; the exact elapsed time was not measured with a timing command.

## 9. Graceful shutdown and the MES transaction example

I chose Option B: attempt to finish or safely interrupt work, release resources and exit within the available deadline. A production service should not assume an arbitrary long transaction can always finish after a stop request.

The MES example was Order 1001 being completed while a container was being scaled down or replaced. Safe outcomes include a committed transaction, a safely rolled-back transaction, or an unresolved outcome that the caller reconciles using the same idempotency key. Graceful shutdown alone cannot tell the caller which outcome occurred.

Cloud Run's container termination discussion used this timeline:

| Relative time | Meaning |
|---|---|
| Termination begins | Container receives SIGTERM |
| Available shutdown window | Server can attempt orderly draining and application cleanup |
| Roughly 10 seconds later if still running | SIGKILL can forcibly terminate it |

SIGTERM is notice to terminate. SIGKILL cannot be caught or delayed by Python cleanup code. The HTTP request timeout and termination window are separate limits: restoring a 300-second request timeout does not grant 300 seconds of shutdown time.

The local Windows Ctrl+C test is an interrupt handled by Uvicorn. It is not a direct test of Linux SIGTERM delivery or Cloud Run's enforced deadline. I did not deliberately terminate a Cloud Run instance in this lesson.

## 10. FastAPI lifespan: implementation and local checks

### My existing application and minimal change

S15 and S16 show the original `app/main.py` before lifespan changes. Existing routers were `land`, `health` and `employee`. Logging used `StructuredLogHandler` when `K_SERVICE` was present and ordinary console logging locally. The initial FastAPI title was `New Learning API`.

We kept that logging and routing structure and added three changes: import `asynccontextmanager`, define lifespan above application creation after logging setup, and register it with FastAPI. S17 and S18 show the actual edits:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Day 23 - Application started")
    yield
    logging.info("Day 23 - Application shutting down")
    logging.info("Day 23 - Application cleanup completed")

app = FastAPI(
    title="New Learning API",
    lifespan=lifespan
)
```

This snippet relies on the existing `FastAPI` and `logging` imports. Code before `yield` runs at startup. The application serves requests during its lifetime. Code after `yield` runs during orderly shutdown. The earlier teaching version used `print("MES API started")` and shutdown/cleanup print messages; the actual implementation used my logging configuration.

`yield` is the lifecycle dividing point. It is not the mechanism that makes Uvicorn wait for an active request. Uvicorn handles the interrupt/termination process and coordinates outstanding work; FastAPI then runs the application lifecycle cleanup. If a platform forcibly kills the process before this point, the messages or real cleanup might never finish.

The handler only logged. The line “Application cleanup completed” proves that a logging statement executed, not that a database pool, MQTT connection or other real resource was released. No such application-owned cleanup was implemented.

### Duplicate startup block: debugging detail

The original screenshots showed two identical `if __name__ == "__main__":` blocks around lines 46 and 50. After lifespan edits they appeared around lines 57–59 and 61–63. The repeated code was:

```python
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
```

The recommendation was to keep one and remove the second. `PORT` allows the cloud-provided port; 8000 is the local fallback. The screenshot of final shutdown then startup again with the same process ID is consistent with sequential duplicate calls: once the first blocking `uvicorn.run` returns, the second can execute. That is an explanation supported by the displayed code, not proof that cleanup was later applied. A same-PID restart is not evidence of Cloud Run autoscaling.

### Start and check the application

These launch commands appeared as instructions:

```powershell
# Earlier local timeout-test suggestion:
uvicorn app.main:app --reload

# Direct Uvicorn launch proposed for lifespan testing:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Actual command visible in my local terminal:
py -m app.main
```

I run them from my project root, with the virtual environment/dependencies available. I choose one launch method, not all three concurrently. `app.main:app` identifies the `app` object in the module; `py -m app.main` runs my module's main block. The latter followed my configured host `0.0.0.0` and local port 8000. My client connects to `localhost:8000`, not to `0.0.0.0` as a destination address.

S19 shows startup, including `Day 23 - Application started`, startup completion and the server listening on port 8000. S20 shows the root response:

```json
{
  "message": "Employee API",
  "version": "local",
  "environment": "local",
  "api_key_configured": false
}
```

The terminal also shows `GET / HTTP/1.1` returning 200. My terminal includes ordinary INFO/WARNING/ERROR demonstration logs from the root route; those severity labels alone do not mean startup failed. The local `api_key_configured: false` value does not prove the Cloud Run secret was removed.

### Normal shutdown without active work

I pressed Ctrl+C once in the server terminal instead of killing the process or closing its window. S21 shows shutdown messages, application cleanup log, shutdown completion, process 8088 finished and the prompt returned. This verifies orderly local lifecycle execution. It does not test real resource release or guarantee any in-flight SQL transaction.

The follow-up understanding question asked whether lifespan guarantees SQL completion after SIGTERM. The correct answer is no; completion depends on time and operation handling. My reply was only “yes” to continuing the exercise, so I do not record it as a specific selection of a multiple-choice answer.

## 11. Local graceful shutdown during an active request

I chose two separate command windows. Window 1 ran `py -m app.main`. After startup, Window 2 ran:

```powershell
curl.exe -i http://localhost:8000/test-timeout
```

The instructions were to wait about five seconds while the request processed, then press Ctrl+C **once in the server window**. I left the HTTP client waiting. A second Ctrl+C could force a different outcome, so the experiment used a single normal stop request.

For learning order, the workbook puts the client request starting at S22, the server draining at S23, the completed client response at S24 and final server shutdown at S25. This order follows the causal workflow, even though the attachment list presented the first two images in the opposite order.

| Stage | Actual screenshot observation |
|---|---|
| S22 | Client sent `/test-timeout` and was still waiting |
| S23 | Server entered shutdown and displayed `Waiting for connections to close. (CTRL+C to force quit)` |
| S24 | Client received HTTP/1.1 200 OK and completed JSON |
| S25 | Request access log shows 200, then lifespan shutdown messages, shutdown completion and process 18912 finished |

S25 also shows a fresh startup sequence with the same process ID after the completed shutdown. The duplicate main block is a plausible explanation, as discussed above. I do not treat this as proof of an external supervisor or a successful code fix.

My local Uvicorn server allowed the pending request to complete before lifespan shutdown ran. This connects to an MES SQL update: a server may drain work successfully if time allows. It does **not** mean Cloud Run will allow the same remaining duration during termination. If about 20 seconds remain and only 10 seconds are available, business completion cannot be guaranteed.

This test and the Cloud Run timeout experiment answer different questions. The timeout experiment checks the gateway's HTTP waiting boundary. The local shutdown experiment checks server draining and lifecycle ordering. Neither implemented production database idempotency, durable queuing or cancellation.

## 12. Final state, decisions and deferred work

| Item | Final evidenced state |
|---|---|
| Cloud Run request timeout | Restored to 300 seconds; successful rollout and HTTP 200 evidenced |
| Cloud image used in timeout experiment | v16 selected; restoration did not require another code change |
| Local lifespan demonstration | Implemented and tested |
| Local active-request shutdown | Client completed before server's lifecycle shutdown logs |
| Temporary `/test-timeout` route | Still present in the local test screenshots; removal not evidenced |
| Duplicate main block | Identified; removal recommended but not evidenced |
| Cleaned application build/push/deploy | Deferred; no final clean image or rollout evidenced |
| Real database/MQTT resource cleanup | Not implemented in this lesson |
| Cloud Run forced termination test | Not performed |

My decision was to retain a lifespan handler **only if it will manage actual application resources in the future**. Since this version was logging-only, the final recommendation was to remove that demonstration handler while keeping existing logging. That recommendation is not evidence of an edit.

Deferred cleanup was: remove the temporary route and unused `asyncio` import, remove the logging-only lifespan function/decorator/import/registration if it has no resource purpose, retain one main block, test locally and build/deploy a cleaned image. I do not need to change the restored 300-second timeout again. We decided no additional resilience experiment was necessary to complete the main learning objectives.

## 13. Quick recall and screenshot guide

- **Timeout means no timely response.** It does not mean rollback, cancellation or guaranteed application continuation. Recall S09–S10.
- **Same logical operation, same key.** Generate the GUID outside the retry loop and persist unresolved operations where needed.
- **API behaviour plus SQL coordination.** Replay completed results; handle processing and mismatched payloads; reserve atomically across instances.
- **SemaphoreSlim has process scope.** It does not replace durable idempotency.
- **Actual timeout values:** 300 originally, 15 temporarily, 300 restored. The 30-second examples were teaching only. Recall S02, S07, S12.
- **Code changes need an image deployment.** A timeout configuration update does not upload Python code. Recall S05–S08.
- **Observe both failure and recovery.** 504 near 15 seconds, then 200 after restoration. Recall S09–S14.
- **Uvicorn drains; lifespan manages application lifecycle.** `yield` did not make the pending request finish. Recall S17–S25.
- **Local Ctrl+C differs from Cloud Run SIGTERM/deadline.** A local successful 25-second request is no cloud termination guarantee.
- **Cleanup log is only a log in this exercise.** Final clean code deployment remains unverified.

| Workbook sheets | What I can revisit |
|---|---|
| S01–S02 | Initial Containers and Scaling settings; Console navigation correction |
| S03–S04 | Original error route and local timeout-test JSON |
| S05–S08 | v16 selection, temporary timeout, combined review and completed deployment |
| S09–S10 | Cloud 504 response and 15.001-second request log |
| S11–S14 | Restored timeout, diff, completed rollout and cloud 200 |
| S15–S18 | Existing main.py, duplicate blocks and lifespan implementation |
| S19–S21 | Local startup, root response and normal shutdown |
| S22–S25 | Pending request, drain, client200 and final shutdown/restart |

## 14. Evidence and technical reference record

Original Day 23 text was reviewed across both learning locations using their displayed messages, rather than relying on the cached preview or handover alone. The 25 workflow screenshots were recovered from original attachments. Browser downloads used generated download filenames; that naming does not mean the image contents were recreated. The workbook preserves the image bytes and proportions. A repeated download of the same pre-change screenshot and a duplicate 504 download were excluded from the workflow count.

The handover's claims about v16, configuration and results were checked against the original messages and images. The handover did not transfer files by itself. No generated diagram or explanation screenshot replaces original evidence in the workbook.

For future technical review, these official references corroborate the concepts. They are current reference material, not additional Day 23 experiments:

- [Cloud Run request timeout](https://docs.cloud.google.com/run/docs/configuring/request-timeout): a missed response deadline returns 504; application work may continue.
- [Cloud Run container runtime contract](https://docs.cloud.google.com/run/docs/container-contract): service response and container shutdown requirements, including termination signals.
- [FastAPI lifespan events](https://fastapi.tiangolo.com/advanced/events/): startup/shutdown resource management with lifespan.
- [Uvicorn server behaviour](https://www.uvicorn.org/server-behavior/): graceful shutdown and outstanding work.

No exact Docker build/push history, final cleanup completion or post-504 application completion trace is available in the reviewed material. These are explicit evidence limits, not omitted successful results.
