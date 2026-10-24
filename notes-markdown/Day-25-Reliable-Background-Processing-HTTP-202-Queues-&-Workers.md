# Day 25 — Reliable Background Processing: HTTP 202, Queues and Workers

## 1. My correction to the Day 23 and Day 24 record

I challenged the earlier label suggesting retries had been implemented on Day 23. The corrected distinction is:

| Day | What I actually implemented or tested, as clarified during Day 25 |
|---|---|
| 23 | Cloud Run request timeout changed from 300 s to 15 s. A 25 s operation produced HTTP 504. Timeout was restored to 300 s. |
| 23 | FastAPI lifespan/shutdown tested locally, including stopping Uvicorn during a request. Cloud Run SIGTERM/SIGKILL behavior discussed. |
| 23 | Retries and idempotency discussed conceptually using MES examples. The client retry mechanism was not implemented that day. |
| 24 | In-memory transaction tracking, duplicate detection, HTTP 409 handling, global locking and per-TransactionId locking implemented. |
| 24 | Client retry script used a 1 s timeout against a 3 s API operation. ReadTimeout, exponential backoff and a successful retry with the same TransactionId were observed. |

These are prior-day results explicitly recalled and corrected during Day 25, not new Day 25 experiments. The timing comparisons explain the behavior: 25 s > 15 s causes the configured request deadline to be exceeded; 3 s > 1 s means the client stops waiting before the server's simulated work finishes. A timeout does not establish that SQL did not commit.

Cloud Run's SIGTERM gives my application an opportunity to clean up. My shutdown code must close the resources it owns. Merely receiving the signal does not automatically clean up every application connection. SIGKILL is a later forced termination possibility. This is distinct from persisting and recovering a particular background job.

## 2. HTTP success and business success are different layers

For a synchronous MES update, the sequence can be: Station Service calls API, API performs SQL update, SQL completes, API returns HTTP 200 under that endpoint's success contract.

For an asynchronous operation, the sequence is: Station Service submits TX568, API accepts it, API returns HTTP 202, a worker later performs the operation, and the application records Completed or Failed.

| Response or state | What I can conclude |
|---|---|
| POST returns 202 Accepted | The submission was accepted under the API contract. Processing can still be pending. |
| GET returns 200 with `status: Processing` | The lookup succeeded and my application currently reports work in progress. |
| GET returns 200 with `status: Completed` | The lookup succeeded and my application reports that its simulated operation finished. |
| GET returns 200 with `status: Failed` | The lookup succeeded; the background business operation failed. |
| GET returns 404, `Job not found` | This process does not have that job in its dictionary. It is not proof that an external business operation never happened. |

My HMI or Station Service must not advance an order merely because POST returned 202. It needs the final business outcome through status polling or a completion event. Likewise, a green HTTP 200 on a status lookup does not mean the order operation succeeded. S17 shows exactly this: HTTP 200 and business status Failed.

One opening architecture illustration used “durably queues” before returning 202. That described the production design. My local BackgroundTasks demonstration only registered work in the application process. HTTP 202 by itself provides no durability guarantee.

## 3. What I built locally

I reused my existing `01-python-fastapi` project. I created `app/routers/mes_jobs.py` beside the existing employee, health, land and mes_orders routers. I kept the Day 24 `mes_orders.py` and its registration.

In `app/main.py`, I added:

```python
from app.routers import mes_jobs

app.include_router(mes_jobs.router)
```

The router uses prefix `/mes/jobs` and Swagger tag `MES Jobs`. `JobRequest`, a Pydantic `BaseModel`, has two string fields: `order_id` identifies the order; `transaction_id` identifies this submitted operation. The learning store is `jobs = {}`, a Python dictionary keyed by TransactionId.

### My submission endpoint

The following combines the submission logic explained in the exercise with the returned message visible in the screenshots. It is the learning implementation, not a production queue:

```python
import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/mes/jobs", tags=["MES Jobs"])
jobs = {}  # Learning-only: process-local and lost on restart.

class JobRequest(BaseModel):
    order_id: str
    transaction_id: str

@router.post("/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(request: JobRequest, background_tasks: BackgroundTasks):
    jobs[request.transaction_id] = {
        "order_id": request.order_id,
        "status": "Pending"
    }
    background_tasks.add_task(process_job, request.transaction_id)
    return {
        "transaction_id": request.transaction_id,
        "status": "Accepted",
        "message": "Job accepted for processing"
    }
```

The first worker version was:

```python
async def process_job(transaction_id: str):
    jobs[transaction_id]["status"] = "Processing"
    logging.info(f"Processing job: {transaction_id}")
    await asyncio.sleep(10)
    jobs[transaction_id]["status"] = "Completed"
    logging.info(f"Job completed: {transaction_id}")
```

`Pending` means the request has been registered but the function has not started. `Processing` means the background function is executing. `Completed` means the simulated operation finished. `Accepted` is the submission response label; the stored state initially uses Pending. I should not assume those two labels are identical storage states.

### My status endpoint

I added this below the submission endpoint. `HTTPException` could be included in the existing import instead of being a second import later in the file.

```python
@router.get("/{transaction_id}")
async def get_job_status(transaction_id: str):
    if transaction_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "transaction_id": transaction_id,
        "order_id": jobs[transaction_id]["order_id"],
        "status": jobs[transaction_id]["status"]
    }
```

It reads current dictionary state. It does not execute the job. The 404 branch was included in the code; no Day 25 screenshot demonstrates an unknown-ID test. S04 shows the registered GET route, and S07–S08 show a real lookup.

### Settings and fields I actually used

| Field or choice | Value | Purpose and practical effect |
|---|---|---|
| Router prefix | `/mes/jobs` | Combined with `/submit` and `/{transaction_id}` to form the two public paths. |
| Swagger tag | `MES Jobs` | Groups the endpoints in the documentation. |
| POST status | `status.HTTP_202_ACCEPTED` / 202 | Reports acceptance before the simulated work finishes. |
| Request Content-Type | `application/json` | Swagger and PowerShell send a JSON request body. |
| Request fields | `order_id`, `transaction_id`, both strings | Associate an order with a specific submitted operation. |
| Store | Python `jobs` dictionary | Makes status visible to this process, without persistence or cross-container sharing. |
| Simulation delay | `await asyncio.sleep(10)` | Provides a 10 s window to observe Processing. It does not perform SQL. |
| Status path parameter | Original TransactionId | Lets the caller ask about the same operation. |
| Missing job | HTTP 404 / `Job not found` | Explicitly handles absence in this process's learning store. |
| Failure trigger added later | TransactionId `TX572` | Deliberately raises the simulated database exception. |

## 4. My BackgroundTasks questions and the explanation that resolved them

### Is adding a function enough to execute it?

I asked why adding `process_job` into a `BackgroundTasks` object would run it. FastAPI supplies that object because my parameter is declared as `background_tasks: BackgroundTasks`. I do not create it myself.

```python
background_tasks.add_task(process_job, "TX568")
```

This registers a **function reference** and its argument. It does not immediately perform the work. FastAPI/Starlette invokes it after sending the response.

These expressions mean different things:

| Expression | Effect |
|---|---|
| `await process_job("TX568")` | Waits for the function in the endpoint, delaying the response by approximately the simulated 10 s. |
| `background_tasks.add_task(process_job, "TX568")` | Registers the function and argument for post-response execution. |
| `background_tasks.add_task(process_job("TX568"))` | Incorrect registration: calling the async function creates a coroutine object rather than supplying the callable and its argument separately. It does not mean the async function body has already run to completion. |

### Where is the task “attached” if I only return JSON?

I asked whether returning my dictionary should simply send that JSON, and where any task could be attached. The attachment is an **internal property on the server's response object**. It is not an extra field in the JSON body.

Conceptual illustration only; this was not extra code I needed to write:

```python
response = JSONResponse(
    content={
        "transaction_id": "TX568",
        "status": "Accepted",
        "message": "Job accepted for processing"
    },
    status_code=202,
    background=background_tasks
)
```

FastAPI creates a response around the returned dictionary and internally associates the registered tasks. The explanation of Starlette's handling was this simplified pseudocode, not exact library source:

```python
async def send_response():
    await send_http_status_and_headers()
    await send_json_body()
    if background_tasks is not None:
        await background_tasks()
```

The client receives normal status, headers and JSON. It does not receive a Python function, coroutine or task object. Starlette already knows the background work through the response's internal `background` reference; it does not discover it by inspecting my JSON.

The server can still await the async background callable inside its response-handling lifecycle after sending the body. That server-side await does not make the client keep waiting for the business operation before receiving the response.

The sequence I now remember is:

1. Station Service sends ORDER100 / TX568.
2. My endpoint inserts Pending into `jobs` and registers `process_job`.
3. FastAPI associates the work with its response object.
4. Starlette sends HTTP 202 and the JSON.
5. Starlette runs `process_job("TX568")` in the same application process.
6. The dictionary changes to Processing and then Completed.

This is similar in purpose to arranging server-side work after an ASP.NET Core response. It is not a separate .NET Worker Service, durable IHostedService architecture, broker or container. `await asyncio.sleep(10)` suspends the coroutine during a timer wait, letting the event loop handle other work. It does not create a new worker process. Deeper event-loop comparison with C# was deliberately left for another session.

The official [FastAPI BackgroundTasks guide](https://fastapi.tiangolo.com/tutorial/background-tasks/) confirms the injection and callable-plus-arguments mechanism. It is a supplementary reference; the original exercise and questions are the basis of these notes.

## 5. My experiments, commands and observed results

### Prerequisites and where I ran the commands

I used the existing local FastAPI project and its configured Python environment. The screenshots show an active virtual environment. I ran the server from the project root in one PowerShell terminal:

```powershell
py -m app.main
```

Swagger was at `http://localhost:8000/docs`. The API was served on port 8000. I used Swagger for the first requests, then a second PowerShell terminal to issue POST and GET calls while leaving the server running. These were local tests, not calls to Cloud Run. Exact dependency versions and a new package-install command were not specified during this exercise.

### Test ledger

| Test | Order | Actual evidence | Screenshots |
|---|---|---|---|
| TX568 | ORDER100 | POST 202 Accepted; terminal logs Processing and Job completed. | S01–S03 |
| TX569 | ORDER101 | Route visible; POST 202; processing/completion logs; GET 200 with Completed. Intermediate Processing was not captured. | S04–S08 |
| TX570 | ORDER102 | POST accepted; manual GET arrived after completion and returned Completed. The attempted intermediate capture was too late. | S09–S12 |
| TX571 | ORDER103 | One block captured Accepted, immediate Processing and Completed after an 11 s wait. | S13 |
| TX572 | ORDER104 | POST 202; GET 200 with Failed after deliberate simulated exception. The four screenshots do not show the worker's failure log. | S14–S17 |

### First test: TX568

I entered this in Swagger's POST request body:

```json
{"order_id": "ORDER100", "transaction_id": "TX568"}
```

S02 shows the actual 202 response with TransactionId, Accepted and “Job accepted for processing.” S03 shows:

```text
POST /mes/jobs/submit HTTP/1.1 202 Accepted
Processing job: TX568
Job completed: TX568
```

This supports post-response background execution in the local experiment. No precise response-latency measurement was captured, so I do not record an invented millisecond value. The 10 s delay was the configured simulation, not a real SQL operation.

### Status lookup: TX569

After adding GET, I submitted ORDER101 / TX569 and checked `/mes/jobs/TX569`. The result was:

```json
{"transaction_id": "TX569", "order_id": "ORDER101", "status": "Completed"}
```

The earlier POST response said Accepted. The later GET said Completed because the dictionary had changed while the worker ran. The screenshots did not catch Processing; that was a timing issue, not evidence of a code fault.

### First intermediate-state attempt: TX570

The proposed PowerShell block was:

```powershell
$body = @{
    order_id = "ORDER102"
    transaction_id = "TX570"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://localhost:8000/mes/jobs/submit" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

Invoke-RestMethod `
    -Uri "http://localhost:8000/mes/jobs/TX570" `
    -Method Get
```

`ConvertTo-Json` serializes the PowerShell hashtable into the body. `Invoke-RestMethod` sends the request and displays the returned data. The backtick continues a command onto the next line. `-ContentType` identifies the POST body format.

Expected: an immediate GET during the 10 s delay would normally show Processing; Pending could also be valid if the task had not started. Observed: I issued the calls manually, and GET arrived after the job finished. The logs show POST 202, Processing, Job completed, then GET 200. S11 shows Completed. Repeating the GET after completion cannot recover a past intermediate state.

### Corrected observation method: TX571

I ran the whole block together in the second terminal, using a fresh ID:

```powershell
$body = @{
    order_id = "ORDER103"
    transaction_id = "TX571"
} | ConvertTo-Json

# Submit the job.
Invoke-RestMethod `
    -Uri "http://localhost:8000/mes/jobs/submit" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

# Immediately read its state.
Invoke-RestMethod `
    -Uri "http://localhost:8000/mes/jobs/TX571" `
    -Method Get

Start-Sleep -Seconds 11

# Read the final state.
Invoke-RestMethod `
    -Uri "http://localhost:8000/mes/jobs/TX571" `
    -Method Get
```

S13 captures all three results: Accepted, Processing and Completed. No Python code change was needed for this correction. The issue was when I observed the state.

| Relative stage | Expected timing, not a measured trace | What I observed for TX571 |
|---|---|---|
| Submit | Near the start | Accepted |
| Immediate GET | Within the worker's 10 s wait | Processing |
| Wait | `Start-Sleep -Seconds 11` | Gives the simulated worker time to finish |
| Final GET | After that wait | Completed |

The timing calculation is 11 s − 10 s = 1 s of nominal margin, assuming the worker starts promptly. It explains why the final lookup should occur after the simulation. It is not a guaranteed scheduling or latency bound.

## 6. Deliberate failure: TX572

I replaced only the worker function to add a controlled failure:

```python
async def process_job(transaction_id: str):
    jobs[transaction_id]["status"] = "Processing"
    logging.info(f"Processing job: {transaction_id}")

    try:
        # Simulate MES processing.
        await asyncio.sleep(10)

        # Learning-only technical failure for this transaction.
        if transaction_id == "TX572":
            raise Exception("Simulated MES database failure")

        jobs[transaction_id]["status"] = "Completed"
        logging.info(f"Job completed: {transaction_id}")

    except Exception as ex:
        jobs[transaction_id]["status"] = "Failed"
        jobs[transaction_id]["error"] = str(ex)
        logging.error(f"Job failed: {transaction_id}, Error: {ex}")
```

Without the handler, an ordinary exception could leave the dictionary at Processing forever. In this demonstration the handler records Failed and an error string. I left the GET response unchanged: it exposes the status, not the stored error detail. Exposing errors was mentioned as a possible later step, not implemented here.

I submitted:

```json
{"order_id": "ORDER104", "transaction_id": "TX572"}
```

The POST returned 202. A later GET returned HTTP 200 with:

```json
{"transaction_id": "TX572", "order_id": "ORDER104", "status": "Failed"}
```

S14–S17 demonstrate the submission and failed final state. The expected error log was `Job failed: TX572, Error: Simulated MES database failure`, but that log is not visible in this screenshot group. I must not claim that a real SQL outage was induced: the exception was deliberately raised by Python.

The demonstrated flow was Accepted, then worker processing, then Failed. Unlike TX571, the screenshots do not directly capture a GET returning Processing for TX572. Production code would distinguish retryable technical failures from permanent business failures. This generic catch is a learning exercise.

## 7. Why catching an exception is not durable processing

I considered hypothetical TX573: FastAPI returns 202, starts the background work, then the process crashes or the container is forcibly terminated. My `except Exception` may never run. The operation may never reach a recorded final status. Restarting the process also loses `jobs` entirely.

The dictionary is local to one process. Another container cannot read it. The submission endpoint also has no duplicate guard: submitting the same TransactionId again overwrites its dictionary entry and can schedule another task. The locks and idempotency learned on Day 24 were not automatically inherited by this new router.

HTTP 202 does not instruct Cloud Run to restart that specific BackgroundTasks function. FastAPI does not restore the dictionary on restart. The correct answer to that understanding check was that work may be lost without an external durable mechanism; no selected quiz answer was recorded as evidence.

| Capability | FastAPI BackgroundTasks | RabbitMQ | Google Cloud Tasks |
|---|---|---|---|
| Separate service | No | Broker | Managed GCP queue |
| Delivery to worker | In-process function invocation | Consumer receives message | HTTP request to target |
| Survives API process failure | Not guaranteed | Depends on durable queue/message/acknowledgement design | Successfully enqueued tasks survive the API process, within service limits |
| Retry | No built-in reliable delivery retry | Consumer/broker retry design required | Configurable delivery retries |
| Acknowledgement | No external broker ACK | Consumer ACK/NACK | Worker HTTP 2xx |
| Worker distribution | Application processes only | Separate consumers possible | Target service instances |
| Duplicate risk | Duplicate submission | Duplicate delivery possible | Duplicate delivery possible |
| Fit discussed | Small noncritical local work | Messaging/event-driven architecture | Controlled deferred HTTP work |

## 8. Production queue and worker design

My familiar pattern is Station Service → RabbitMQ → PDT consumer → business processing → ACK/NACK. Cloud Tasks applies a related delivery pattern through HTTP:

```text
Station Service submits ORDER100 / TX573
    → FastAPI submission endpoint creates a task successfully
    → FastAPI returns 202 to Station Service
    → Cloud Tasks retains and dispatches work
    → Cloud Run worker handles POST /internal/process-job
    → SQL stores business result and durable job/idempotency state
    → Worker acknowledges delivery to Cloud Tasks
```

Illustrative worker request, not an implemented endpoint:

```http
POST /internal/process-job
Content-Type: application/json
```

```json
{"transaction_id": "TX573", "order_id": "ORDER100"}
```

There are **two separate HTTP interactions**. The submission API's 202 acknowledges acceptance to Station Service. The worker's 200/other 2xx acknowledges its handling of the delivery to Cloud Tasks. A worker must not return success merely because it registered another in-process background task. Otherwise the queue can remove the task while the real business work remains unfinished and vulnerable to process failure.

A worker failure, illustrated with HTTP 500 or 503 for unavailable SQL, can leave the delivery eligible for retry. Cloud Tasks delivers at least once; reliable delivery is not exactly-once business execution. If SQL commits TX573 but the HTTP 200 acknowledgement is lost, Cloud Tasks may deliver TX573 again. The worker should check durable TransactionId state and return the previous successful result without repeating the business update. It should not generate a new ID for a retry.

My existing `employee-api` service was described as using request-based billing. CPU allocation is tied to request processing in that mode, making work after a returned response unsuitable as the basis for reliable completion. A Cloud Tasks worker keeps its HTTP request active while processing. This was the architectural reason for the queue approach; billing mode and GCP resources were not changed on Day 25.

## 9. Cloud Tasks retry fields and the correction to the four-attempt example

I asked: “Max attempt vs max-retry: what's the difference?” The precise fields are `maxAttempts` and `maxRetryDuration`. Snake-case names appeared in the explanation; the REST representation uses camelCase. No queue settings below were actually saved.

| REST field (earlier snake-case label) | Meaning | Value discussed | Interaction and practical effect |
|---|---|---|---|
| `maxAttempts` (`max_attempts`) | Total delivery attempts including the first | 4, teaching example | Four total attempts would mean three retries in a count-only illustration. It must be interpreted with retry duration and retention. |
| `maxRetryDuration` (`max_retry_duration`) | Retry time measured from the first attempt | 60 s, teaching example; 0 also explained | With a positive duration, both duration and attempt conditions must be satisfied before policy exhaustion. Zero means no duration limit, subject to retention. |
| `minBackoff` (`min_backoff`) | Starting retry-delay setting | 5 s, teaching example | Supplies the initial delay in the illustrative doubling calculation. |
| `maxBackoff` (`max_backoff`) | Maximum retry interval | No value chosen | Caps increasing intervals. Without its value I cannot claim the full example is an executable queue policy. |
| `maxDoublings` (`max_doublings`) | Controls exponential interval growth | No value chosen | Affects how long doubling continues. The example assumes enough doublings for its first intervals. |
| `maxDispatchesPerSecond` (`max_dispatches_per_second`) | Queue dispatch rate | No value chosen | Limits aggregate delivery traffic, including retries, helping protect the target. |
| `maxConcurrentDispatches` (`max_concurrent_dispatches`) | Concurrent outstanding deliveries | No value chosen | Limits in-flight tasks and pressure on worker/SQL capacity. |

The early four-row TX574 example said attempts 1–3 fail and retry, then attempt 4 fails with no more attempts under that simplified policy. The later clarification matters: **four attempts alone is not a complete Cloud Tasks policy**, especially with a positive retry-duration setting. I retain the corrected understanding rather than treating the simplified row as a saved or verified configuration.

### Worked timing example

Inputs: minimum backoff 5 s, illustrative doubling, immediate attempt completion, no cap affecting these first intervals. For retry number `n`, the teaching formula is:

```text
delay(n) = 5 s × 2^(n − 1)
```

| Delivery attempt | Delay since previous attempt | Cumulative time from first attempt | Outcome in the teaching scenario |
|---|---:|---|
| 1 | None | 0 s | HTTP 500, SQL unavailable |
| 2 | 5 × 2^0 = 5 s | 0 + 5 = 5 s | HTTP 500 |
| 3 | 5 × 2^1 = 10 s | 5 + 10 = 15 s | HTTP 500 |
| 4 | 5 × 2^2 = 20 s | 15 + 20 = 35 s | HTTP 500 |

At 35 s the count condition of four attempts is met, but 60 − 35 = **25 s** remains before the positive duration threshold. Further attempts can therefore be eligible. “60 s+” in the explanation marks when the duration condition can be satisfied; it is not an observed dispatch, a fifth-attempt timestamp, or a guarantee of an action exactly at 60 s. Actual scheduling, execution durations, backoff caps/doublings and throttling affect behavior. No real retry timeline was measured.

A retry-duration window is different from one HTTP request's timeout or dispatch deadline. It is also different from the service's maximum task retention. `maxRetryDuration = 0` does not mean zero retries. I have not invented a retention value or dispatch deadline for the exercise.

Supplementary verification: Google's [RetryConfig reference](https://docs.cloud.google.com/tasks/docs/reference/rest/v2/RetryConfig) confirms the count/duration interaction and zero-duration meaning. Its [queue reference](https://docs.cloud.google.com/tasks/docs/reference/rest/v2/projects.locations.queues) distinguishes queue rate limits from a task's retry policy. These references support the clarified interpretation, not a claim that I configured a queue.

## 10. Delivery exhaustion is not a final business outcome

TX574 / ORDER105 was a teaching scenario: a task is accepted, but every worker call fails because SQL is unavailable. The queue can eventually stop retrying and delete its task. That does not automatically update `MesJobTransactions` to Failed, delete the business record, or prove no SQL commit happened.

| Queue event | Possible application state |
|---|---|
| Waiting for delivery | Pending |
| Worker active | Processing |
| Retryable delivery failure | Pending or Retrying |
| Worker 2xx after successful processing | Completed under the worker's contract |
| Retry policy exhausted | Still unresolved unless my application explicitly handles recovery |

Cloud Tasks is not my permanent MES transaction history. A production design needs a persistent business record, illustrated as:

```text
TransactionId: TX574
OrderId: ORDER105
Status: Retrying
AttemptCount: 3
LastError: SQL connection unavailable
```

Those values are illustrative, not data created in my local project. If the queue is the only surviving reference, deletion can remove the information needed to recover the request.

### How the Station Service finds the eventual result

I implemented the simple polling shape: periodically call `GET /mes/jobs/TX574` in a production version. An alternative is a completion/failure event published after the worker records the result, fitting my RabbitMQ-driven MES experience.

There is a consistency gap if SQL commits and the worker crashes before publishing the event. The transactional outbox pattern was identified as relevant to coordinating durable business state and later publication. We did not implement it. There is also a gap between job registration and queue creation that a real design must handle; naming a queue does not make those two actions atomic.

## 11. Reconciliation and when BAU is needed

I asked whether someone from BAU must manually process TX574 after the queue gives up, or whether reconciliation handles it automatically.

Reconciliation means comparing expected transaction state with reliable evidence of actual business state, then resolving a mismatch or incomplete outcome. It is more than repeatedly sending the same request. It asks whether TX574 already committed, remains pending, has a permanent business rejection, or conflicts with another operation.

A reconciliation worker is an ordinary application or scheduled process. Examples discussed were a .NET Worker Service, SQL Server Agent job, scheduled Cloud Run Job or another scheduled application. Running every five minutes was a teaching example, not a configured schedule.

Conceptual C# sketch from the explanation, not a complete implemented service:

```csharp
public async Task ReconcileAsync()
{
    var pendingTransactions = GetPendingTransactions();
    foreach (var transaction in pendingTransactions)
    {
        // Check actual business status.
        // Retry safely or escalate for manual handling.
    }
}
```

The sketch uses placeholder retrieval and recovery logic. It illustrates responsibility rather than providing a runnable production implementation.

| Reliable evidence found | Reconciliation action discussed |
|---|---|
| TX574 committed, tracking status not updated | Correct the status to Completed without repeating SQL DML. |
| TX574 never committed and SQL is healthy | Requeue/retry safely with the original TransactionId, if business rules allow. |
| SQL still unavailable | Leave unresolved, monitor and try later under policy. |
| ORDER105 already processed by another transaction or with incompatible data | Detect conflict and escalate for investigation. |
| Invalid or unrecoverable business data | BAU/manual handling. |
| No persistent evidence that the transaction ever existed | Reconciliation cannot reconstruct the lost request. |

Simply finding or not finding a row is not always sufficient if state is delayed or updated independently. Recovery must use reliable evidence and preserve the earlier rule that a timeout does not mean no commit. Recovery workers also need idempotency, concurrency protection and bounded retries: two recovery workers must not both process TX574 at once.

In the temporary-outage example, SQL recovered after 10 minutes. If reconciliation establishes that TX574 never committed, safe automated replay may remove the need for BAU. In the conflicting-order example, automatic replay could make matters worse. MES operations can have physical consequences: before replaying an order or station action, I must check that production has not already moved forward.

The analogy to my PDT architecture helped: Redis transaction state, RabbitMQ, Echo/RX coordination and expiry cleanup already separate state and message handling. An RX can be deferred because `_pendingRX` retains information about it. If the payload is discarded and no source can reproduce it, a later cleanup/reconciliation job cannot recover that exact message by magic. This analogy does not establish that an in-memory pending collection itself survives restart.

## 12. What “durable database” actually meant

I initially understood durable database as a separate backup server that the API could switch to when primary SQL was down. Then I pointed out that I already knew committed SQL data survives ordinary restarts, so what was special about “durable job record created”?

The unfamiliar part was terminology. My normal SQL Server database can already provide persistent storage. “Durable job record” meant inserting and committing TX574 into a persistent table instead of keeping it only in a Python dictionary. It did not mean creating a special second database.

| Concept | Meaning and purpose |
|---|---|
| Durability | Committed information survives ordinary process failures/restarts under the storage system's guarantees. |
| Backup | A recoverable copy used to restore after corruption, deletion or disaster. A normal backup file does not directly serve live API traffic. |
| High availability | Redundancy and failover reduce service downtime, for example promotion of a healthy standby. |
| Reconciliation | Uses persistent evidence to establish and resolve unfinished business outcomes. |

SQL Server's normal fully durable transaction behavior uses transaction-log persistence and recovery. Durability does not promise zero downtime, automatic failover, protection from every storage disaster, uninterrupted regional access, or zero loss under every disaster scenario. Backups, replication and recovery architecture address additional failure modes.

In an application crash, SQL can still hold TX574 even though the Python dictionary is lost. In a SQL connectivity outage, committed rows may still exist but be temporarily inaccessible. In a configured HA deployment, a healthy standby can restore access after failover; existing connections may need re-establishment. Cloud SQL cross-zone standby behavior was an example, not an HA setup performed during Day 25.

### Illustrative persistent tracking table

This SQL was a proposed schema only:

```sql
CREATE TABLE MesJobTransactions
(
    Id INT IDENTITY(1,1) PRIMARY KEY,
    TransactionId VARCHAR(50) NOT NULL UNIQUE,
    OrderId VARCHAR(50) NOT NULL,
    Status VARCHAR(30) NOT NULL,
    AttemptCount INT NOT NULL DEFAULT 0,
    LastError NVARCHAR(500) NULL,
    UpdatedAt DATETIME2 NOT NULL
);
```

`Id` is a generated row identifier. `TransactionId` uniquely identifies an operation, helping protect against duplicate records. `OrderId` links the business order. `Status` records progress; `AttemptCount` records attempts; nullable `LastError` retains diagnostic context; `UpdatedAt` supports identifying stale states. This sketch does not implement the full atomic business-update/idempotency/recovery workflow.

The later insert illustration was:

```sql
INSERT INTO MesJobTransactions (TransactionId, OrderId, Status)
VALUES ('TX574', 'ORDER105', 'Pending');
```

It demonstrated persistent storage conceptually. It is not directly runnable against the exact CREATE TABLE above without supplying `UpdatedAt` or adding an appropriate default, because that column is NOT NULL with no default. The two teaching snippets were not executed. I preserve this distinction rather than silently presenting them as a tested migration.

One SQL database could contain both Orders and MesJobTransactions, allowing related business and tracking updates to be committed together. Two tables still depend on the same database's availability. Persisting Pending also does not guarantee execution: SQL commit can succeed and FastAPI can crash before scheduling the task. Recovery logic is still needed to find that retained Pending record.

## 13. My SQL-outage challenge and the final persistence understanding

I asked: “If SQL is already down, the transaction table cannot store TX574. How can a reconciliation worker detect it?” That exposed the limit of the earlier recovery illustration.

### SQL was available at acceptance, then failed

TX574 is committed as Pending. Later processing cannot access SQL. Once SQL returns, reconciliation can find the existing row, check the real business outcome and retry or correct status. It did not repair SQL; it recovered work after the dependency became accessible.

### SQL was already down when the request arrived

If the insert never succeeded and no queue or other store retained the payload, no server-side record exists to discover later. Reconciliation cannot solve that missing initial handoff. Two approaches were discussed:

1. **Reject acceptance and let the caller retain the request.** Return a suitable failure such as 503. Station Service retries the same TransactionId later. If that pending request must survive a Station Service restart, it needs persistent caller-side storage as well.
2. **Accept only after an independent durable queue has stored the request.** Successfully create the Cloud Tasks task, then return 202. Workers can receive retryable SQL failures and try again under queue policy. If SQL stays down beyond queue retry/retention limits and nothing else retains the transaction, this still leaves a recovery gap. Durable tracking, monitoring and an independent recovery source need deliberate design.

If **both SQL and the queue are unavailable**, the API has no confirmed server-side place to retain a new request. It should report inability to accept it, leaving responsibility with a caller that can retain and retry. The question I now ask at acceptance is: **which reliable component has actually taken responsibility for this transaction?**

| Where TX574 was retained | Recovery possibility |
|---|---|
| Committed in SQL before the outage | Reconciliation can recover after SQL is accessible, if recovery logic exists. |
| Stored in independent Cloud Tasks | Delivery can retry within its limits; lasting recovery needs retained evidence. |
| Never saved anywhere | No later worker can reconstruct it reliably. |
| Persistently retained by Station Service after rejection | Caller can retry initial submission with the same ID. |

### My Redis example

I finally restated the idea as: persist server-side, perhaps in Redis, then retry when SQL becomes available. The clarification was:

```text
Persist TX574 as Pending
    → Worker attempts SQL
    → SQL unavailable: retain Pending/Retrying
    → SQL recovers
    → Retry using original TX574
    → Verify business result
    → Mark Completed
```

Redis can play a role only with appropriate persistence and availability design. It is not automatically a guaranteed durable store. No Redis persistence/HA settings were chosen or applied. A durable queue or transactional database was discussed as an alternative for critical MES transactions.

Retry does not necessarily mean sending the same HTTP request again. A worker that owns direct SQL access can retry the SQL operation. If the architecture calls an HTTP MES API, it can replay that request using the original TransactionId. Idempotency and outcome verification remain necessary either way.

The separate responsibilities are: persistence retains the evidence and payload; retry attempts work again; reconciliation checks what actually happened; BAU handles cases automation cannot safely resolve.

## 14. My final state and deferred work

Day 25 learning was completed with a local submission endpoint, GET status endpoint, asynchronous 10 s simulation and failure-state recording. TX568–TX571 supported the success path, with TX571 directly capturing the intermediate state. TX572 supported the deliberately failed path.

I kept `mes_jobs.py` as a learning reference with its process-local/in-memory limitation. The final worker design still contains the TX572 failure trigger described above; no later removal was recorded. I should label that trigger as demonstration-only when reusing the file. No cleanup or deployment is claimed here.

Cloud Tasks creation, Redis implementation, persistent SQL job tracking, queue/worker deployment, reconciliation scheduling, HA/backup setup, transactional outbox and production idempotency were intentionally deferred. They were architecture learning, not completed local features. Error-detail exposure from GET was also deferred.

A commit was suggested as an administrative next step, with the message:

```text
Day 25 - Implemented FastAPI background job processing and status tracking
```

No commit command or successful commit output was shown, so I do not mark it as done. Documentation was the other remaining administrative activity. Python event-loop internals and the C# comparison remain a later learning topic.

## 15. My quick recall guide

| If I forget… | I remind myself… |
|---|---|
| What 202 proves | Acceptance, not final order success. S01–S02 and S14–S15. |
| How the task is attached | Internal server response property; JSON remains ordinary response data. Section 4. |
| Why add_task takes no function-call parentheses | I pass a callable and separate arguments for later execution. |
| Why I missed Processing | I queried too late. TX570 shows the issue; TX571's single block fixes observation timing. S09–S13. |
| Whether HTTP 200 means the job succeeded | It can mean only the status lookup succeeded. S17 says Failed. |
| Whether try/except survives termination | No. The process may disappear before its handler runs. |
| What a queue guarantees | Delivery under its contract and limits; I still design business idempotency and durable outcome state. |
| Count versus retry duration | Attempts include the first; positive duration interacts with count. Four rows are not a complete queue policy. |
| Why reconciliation exists with retries | Delivery ACK and actual business outcome are different questions. |
| What durable means here | Commit the transaction record to persistent storage so it survives the API process. |
| Whether durability makes SQL available | No. Availability/failover and persistence are different properties. |
| What if SQL never stored the job | Recover from another retained source or caller. No record anywhere means nothing to reconcile. |
| Whether to repeat HTTP | Depends on the architecture. Preserve TransactionId and verify outcome. |

## 16. Screenshot navigation and verification record

| IDs | Workbook sheet | What I use them to recall |
|---|---|---|
| S01–S03 | `01 Submit` | TX568 request, accepted response, background logs. |
| S04–S08 | `02 Status` | Registered routes, TX569 accepted response, logs, GET parameter and Completed result. |
| S09–S12 | `03 Timing` | TX570 logs and manual status check that reached Completed too late to capture Processing. |
| S13 | `04 Lifecycle` | TX571 Accepted → Processing → Completed in a single PowerShell block. |
| S14–S17 | `05 Failure` | TX572 accepted request followed by HTTP 200 status lookup reporting Failed. |

The workbook's Index lists exact image rows and filenames. The image groups contain 3 + 5 + 4 + 1 + 4 = **17 originals**. Some screenshots are narrow crops supplied originally; the workbook preserves their whole available contents and proportions. They are not reconstructed screenshots of a rerun.

The full Day 25 material was reviewed in the original browser page from the explicit start through the documentation request, including all five original attachment groups. The bounded chat-retrieval tool initially omitted older turns and answer text; that limitation was overcome through the original page. No screenshot evidence remains missing from the 17-image Day 25 workflow. Implementation source-editor screenshots, a real SQL-outage experiment, a background failure-log capture, measured response latency, Cloud Tasks console configuration and an executed Git commit were not present as Day 25 evidence; these notes do not invent them.

The deliverables were checked against the internal topic checklist. Verification includes screenshot/transaction captions, embedded image count and byte hashes, image proportions and layout, timing arithmetic, explicit distinction between observed results and teaching examples, and cross-references between this document and the workbook. Library upload status is reported with the final delivery links.
