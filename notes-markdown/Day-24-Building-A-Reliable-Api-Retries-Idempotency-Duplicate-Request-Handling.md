# Day 24 — My reliable API learning notes

**Learning date: 24 October 2026.** My focus was retries, idempotency, duplicate requests and concurrency in a local FastAPI MES example.

I read these notes alongside `Day_24_Screenshots.xlsx`. Screenshot IDs such as **S12** are stable references into its Index sheet. The final screenshot register below gives the exact sheet and image row for every original screenshot.

## 01. The problem I wanted to solve

My real application scenario is **MES Station Service → API → SQL database**. A station submits an order completion. SQL may commit successfully, but the HTTP response may never reach the station. The station cannot conclude that the operation failed simply because it timed out.

If I retry with a fresh transaction ID, the API may interpret that as a new business operation and repeat the SQL update, order history insertion or production event. I must retain the **same TransactionId for every attempt at the same logical operation**. A genuinely new operation gets a new ID.

For example, the station sends:

```json
{
  "order_id": "ORDER100",
  "transaction_id": "TX561",
  "status": "Completed"
}
```

The first TX561 should perform the operation. A retry of TX561 with the same data should return its recorded result. TX562 represents a different operation. **Idempotency means repeated attempts do not produce additional business effects.** It does not mean that every network attempt succeeds or that POST becomes safe automatically. I have to implement the behavior.

This follows the Day 23 lesson that a timeout can leave the server processing. I did not repeat the earlier timeout or graceful-shutdown experiments or deploy to GCP. I reused my existing learning project, kept the MES router separate from employee CRUD, and worked locally. The original plan estimated 60–90 minutes and emphasized hands-on work; that was a plan, not a measured session duration.

Throughout my notes I distinguish:

- **Observed:** visible original screenshot or result I actually reported.
- **Implemented:** code I uploaded or behavior demonstrated by the local tests.
- **Teaching example:** explanatory timelines, SQL, timings or jitter values, not measured evidence.
- **Proposed:** a command, comment or future design without proof it was executed or saved.
- **Deferred:** work I explicitly chose to leave for later.

## 02. Creating and connecting my first MES endpoint

My local project root was:

```text
C:\Raja\Learning\python\new learning\01-python-fastapi
```

I created `app/routers/mes_orders.py`. The early structure used FastAPI's `APIRouter` and Pydantic's `BaseModel`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/mes/orders", tags=["MES Orders"])

class OrderCompletionRequest(BaseModel):
    order_id: str
    transaction_id: str
    status: str

@router.post("/complete")
async def complete_order(request: OrderCompletionRequest):
    return {
        "order_id": request.order_id,
        "transaction_id": request.transaction_id,
        "status": request.status,
        "message": "Order completion request received"
    }
```

| Field or statement | My chosen value | Meaning and practical effect |
|---|---|---|
| Router prefix | `/mes/orders` | Common path for this router's endpoints. |
| Router tag | `MES Orders` | Groups the endpoint in Swagger. It does not supply idempotency. |
| POST suffix | `/complete` | Combined with the prefix, exposes `POST /mes/orders/complete`. |
| `order_id: str` | `ORDER100` initially | Identifies the order. `ORDER101` later tests a conflicting payload. |
| `transaction_id: str` | `TX561` initially | Identifies one logical operation, retained across retries. |
| `status: str` | `Completed` | Requested status, compared when checking a repeated key. The model shown uses a string, not a restricted enum. |
| Request annotation | `OrderCompletionRequest` | Tells FastAPI/Pydantic how to parse and validate the JSON. |

I registered the router in `app/main.py`, alongside the existing imports and registrations:

```python
from app.routers import mes_orders
app.include_router(mes_orders.router)
```

In a PowerShell terminal at the project root, using my existing virtual environment and application setup, I started the server:

```powershell
py -m app.main
```

I opened `http://localhost:8000/docs`, found **MES Orders**, selected **Try it out**, supplied the JSON and executed it. The request went to `http://localhost:8000/mes/orders/complete`.

**Observed:** S01 shows HTTP 200 and `Order completion request received`. I executed the same request again and received another 200 with the same acknowledgement, shown in S02. At this stage the handler remembered nothing. Repeating a JSON acknowledgement was harmless, but replacing it with real SQL updates, history inserts or event publishing could have repeated the business operation.

The SQL and event functions discussed here were **examples only**:

```python
# Teaching example only — these operations were not implemented.
update_order_in_sql(request.order_id)
insert_order_history(request.order_id)
publish_order_completed_event(request.order_id)
```

## 03. My first idempotency store and sequential tests

I added a module-level dictionary after the router declaration:

```python
processed_transactions = {}
```

The dictionary maps a transaction ID to the recorded response. The basic decision is:

| Incoming request | Decision | Response |
|---|---|---|
| TX561 is absent | Process, build result and store it | 200 |
| TX561 exists and `order_id` and `status` match | Return the previous result | 200 |
| TX561 exists but either compared field differs | Reject reuse of the key for different data | 409 |
| A new key such as TX562 arrives | Treat it as a new logical operation | 200 |

The essential code, before adding locks, was:

```python
from fastapi import HTTPException

transaction_id = request.transaction_id
if transaction_id in processed_transactions:
    previous = processed_transactions[transaction_id]
    if previous["order_id"] != request.order_id or \
       previous["status"] != request.status:
        raise HTTPException(
            status_code=409,
            detail="Transaction ID already used for a different request"
        )
    return previous

response = {
    "order_id": request.order_id,
    "transaction_id": transaction_id,
    "status": request.status,
    "message": "Order completed successfully"
}
processed_transactions[transaction_id] = response
return response
```

**Observed:** S03 shows the first request after this change returning 200 and the new message `Order completed successfully`. S04 shows the identical request returning the same JSON. That result was expected, but it did **not** prove the duplicate branch executed. Both branches return the same HTTP status and content.

I therefore added `import logging` and separate messages:

```python
logging.info(f"Processing new transaction: {transaction_id}")
logging.info(f"Duplicate transaction detected: {transaction_id}")
```

After restarting, I sent TX561 twice **without restarting between those two requests**. Restarting resets the memory and would make the repeated key look new again. S05–S08 show the fresh and repeated responses alongside logs that distinguish one new operation from one duplicate.

I also tested ORDER101 using the already recorded TX561. S09 shows the conflicting request; S10 shows **409 Conflict** with:

```json
{"detail": "Transaction ID already used for a different request"}
```

S11 combines the relevant server logs. It contains a `Duplicate transaction detected` message before the 409 because the early logging placement reported that the **key existed** before comparing the payload. That message did not mean the conflicting request was accepted. In my final uploaded source, the valid-duplicate message occurs after the conflict comparison.

Swagger's default response documentation still displayed a 200 response schema below the actual 409 in S10. I use the actual server-response section and logs to identify the result. The word “Undocumented” beside 409 does not turn it into a successful response.

### My stateful/stateless clarification

I recalled that Container A's in-memory transaction data is unavailable to Container B. A retry routed to B could be treated as new. Restarting A also loses its dictionary.

My initial shorthand was “in-memory is stateful; Redis is stateless.” The more precise understanding is that an application is stateless **when it does not depend on instance-local state between requests**. Redis itself stores state. Moving state to shared SQL or Redis can allow instances to access the same records, but it does not automatically make concurrent updates safe. I still need atomic coordination.

## 04. Deliberately exposing a race condition

My sequential implementation had a **check-then-act** gap: it checked whether a key existed, performed work, then stored the result. Two requests could both decide that TX562 was missing before either stored it.

One nuance mattered: the early async endpoint had no `await` between the check and store. Normal execution in one event loop might therefore not expose this race. I added a deliberate asynchronous delay to model a slow MES database operation:

```python
import asyncio

# After the complete duplicate-check block, before creating the new response:
await asyncio.sleep(3)
```

**Correction:** I first placed the sleep inside the duplicate branch. S12 preserves that intermediate version. That would delay a request only when the key was already present. It would not create the intended gap for a fresh request. I moved it outside the duplicate-check block, immediately before creating and storing the new response. S13 shows the correction.

My SQL DML analogy helped: request 1 has checked the key but is still doing slow work; request 2 arrives while that work is unfinished, sees no stored result and starts the same operation.

| Illustrative time | Request A | Request B |
|---|---|---|
| 0 s | Checks TX562: absent | — |
| 0.1 s | Awaiting simulated work | Checks TX562: absent |
| Around 3 s | Stores TX562 | Still finishing its own work |
| Shortly later | — | Stores TX562 again |

These values explain ordering; I did not instrument exact arrival times.

### My dictionary exception misunderstanding

I expected the second assignment of the same dictionary key to throw an exception like a SQL unique constraint. It does not. A normal Python assignment **overwrites** the existing value:

```python
processed_transactions["TX561"] = "Request 1 completed"
processed_transactions["TX561"] = "Request 2 completed"
print(processed_transactions["TX561"])
# Request 2 completed
```

The real danger is that both handlers may already have executed their side effects before the final overwrite. In an MES system this could mean duplicate order history, duplicate RabbitMQ production events, or duplicate processing. A suitably constrained database might reject a duplicate row, but the Python dictionary has no equivalent automatic rejection.

## 05. Reproducing the race and fixing the PowerShell request

I used one terminal to run FastAPI and a second terminal to launch two background jobs. I restarted the server first to clear the in-memory store. Both requests used ORDER100, TX562 and Completed.

The first command used `curl.exe -s -X POST`, a JSON content-type header and `-d $json` inside `Start-Job`. **Observed:** the client reported `json_invalid`, a JSON decode error and “Expecting property name enclosed in double quotes.” The server returned two **422 Unprocessable Entity** results (S14–S15).

The explanation was PowerShell-to-curl argument quoting: the JSON could reach the API without required property-name quotation marks. A malformed shape such as `{order_id:ORDER100,...}` was an explanatory example, not a captured raw request body. The parse error occurred before `complete_order()` ran, so this failed attempt supplied no evidence about the race or lock.

I replaced curl with the PowerShell-native request command:

```powershell
$body = @{
    order_id = "ORDER100"
    transaction_id = "TX562"
    status = "Completed"
} | ConvertTo-Json

$jobs = 1..2 | ForEach-Object {
    Start-Job -ScriptBlock {
        param($json)
        Invoke-RestMethod `
            -Uri "http://localhost:8000/mes/orders/complete" `
            -Method Post `
            -ContentType "application/json" `
            -Body $json
    } -ArgumentList $body
}

$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
```

`ConvertTo-Json` creates the body. `-ArgumentList` passes it to each separate job, where `param($json)` receives it. `Wait-Job` waits for completion, `Receive-Job` collects output, and `Remove-Job` removes these finished job records.

**Observed:** S16 shows two responses with separate RunspaceIds. That proves two jobs received responses; it does not alone prove the server processed twice. S17 supplies that evidence: the server logged **Processing new transaction: TX562 twice**, with two POST 200 responses. I had reproduced the race.

## 06. A global lock, an unexpected run and the verified fix

I introduced one shared module-level lock:

```python
transaction_lock = asyncio.Lock()
```

The critical section must include the **whole decision and operation**:

```python
async with transaction_lock:
    # Check whether the key exists.
    # Compare an existing request and return/reject as appropriate.
    # Await the simulated new-operation work.
    # Construct the response and store it.
    # Log and return.
```

Protecting only the dictionary assignment would leave the initial decision unprotected. Request B must acquire the lock and recheck the store **after A has finished**, rather than relying on a pre-wait check. `async with` releases the lock when execution leaves the block, including a return or exception.

S18 shows the first portion of the implementation. Because it ended before the whole method, I checked the remainder too. S19 shows response creation, dictionary insertion and return inside the same indentation scope.

My next run still logged TX562 as new twice (S20–S21). I said the lock was not working as expected. The useful response was to diagnose the **running code and shared objects**, rather than conclude that `asyncio.Lock` was broken.

Immediately before acquiring the lock I added:

```python
logging.info(
    f"TX={transaction_id}, LockId={id(transaction_lock)}, "
    f"StoreId={id(processed_transactions)}"
)
```

`id()` identifies an object during its lifetime. Matching IDs within the same process help establish that two requests refer to the same lock and dictionary. These values are not durable business identifiers, and comparing numbers across different processes would not establish shared memory.

After saving/restarting and rerunning, S22–S23 show the correct behavior:

| TX562 retest observation | Actual evidence |
|---|---|
| Shared lock | `2727037231344` for both requests |
| Shared store | `2727038554496` for both requests |
| New processing | One log entry |
| Duplicate processing path | One duplicate-detected log |
| Client responses | Both 200 |

I said I might not have saved the earlier edit properly. That is a **plausible explanation**, not a proven root cause. The firm conclusion is that the later running version behaved correctly.

### Why I then replaced the global lock

One global lock serializes unrelated transactions. If TX562 and TX563 each require 3 seconds and arrive together, their illustrative serialized work time is:

```text
3 s + 3 s = 6 s
```

With independent locks, their ideal overlapping work time is approximately:

```text
max(3 s, 3 s) = 3 s
```

These are teaching calculations excluding network, startup and scheduling overhead. They are not measured benchmark results.

## 07. Per-TransactionId locks, my questions and the uploaded code

I replaced the single global lock with a separate registry, keeping the result store:

```python
transaction_locks: dict[str, asyncio.Lock] = {}
processed_transactions = {}

lock = transaction_locks.setdefault(transaction_id, asyncio.Lock())
async with lock:
    # Same protected decision/process/store sequence.
```

`processed_transactions` holds completed results. `transaction_locks` holds synchronization objects. Requests with the same key share one lock; different keys get separate locks. Both dictionaries belong to this Python process.

### My question: why create a lock when TX561 already exists?

I understood that `setdefault()` returns the existing lock for an existing key. The missing detail was **argument evaluation**: Python evaluates `asyncio.Lock()` before it calls `setdefault()`.

For the first TX561, Lock A is created, stored and returned. For the next TX561, a temporary Lock B is created while evaluating the argument. Because the key already exists, `setdefault()` returns Lock A, leaving B unused. Both requests still coordinate on A. The extra temporary object is acceptable for this small exercise.

The teaching example was:

```python
def create_value():
    print("Creating a new value")
    return "New"

data = {"TX561": "Existing"}
result = data.setdefault("TX561", create_value())
print(result)
```

Expected output:

```text
Creating a new value
Existing
```

### My question: what does “no await in the lookup” mean?

In my current single-threaded asyncio setup, a normal synchronous lookup-and-insertion statement runs without giving another asyncio task a suspension point inside that statement. By contrast, `await asyncio.sleep(3)` can suspend request A and let request B run.

| Order | Request A | Request B |
|---|---|---|
| 1 | Gets/stores Lock A for TX561 | Awaiting event-loop time |
| 2 | Acquires Lock A | — |
| 3 | Reaches asynchronous sleep | Gets a chance to run |
| 4 | Holds lock while awaiting work | Finds the same Lock A and waits |
| 5 | Stores result and releases | Acquires A, rechecks, returns previous result |

This explanation is about cooperative tasks on the same event loop. It is not a claim that `asyncio.Lock` is thread-safe or that `setdefault()` provides distributed coordination. Two containers have separate registries and separate locks.

I still did not feel confident about the event loop internals. I explicitly deferred a deeper study of **async, await, task scheduling, event loops and comparison with C# asynchronous programming** until after the planned learning tasks. That subject remains deferred.

### How I connected this to my MES work

| My existing MES/C# experience | Relationship to this exercise |
|---|---|
| `ConcurrentDictionary<string, SemaphoreSlim>` in Sequin UniversalStep | Registry of gates associated with an operation or step. |
| Per-step `SemaphoreSlim(1,1)` | Comparable purpose to one asyncio lock per transaction key within a process. |
| Duplicate `PLC_READY` | Similar need to avoid processing the same operation concurrently. |
| `OnExecuteFinalized` cleanup | Reminder that synchronization state needs a deliberate lifecycle. |
| Echo/RX race, `_pendingRX` payload | My MES code can retain a message that arrived before the correct state. |
| `IsCurrentOrder=true` validation | Revalidate relevant state before acting, particularly after waiting. |
| Cleanup when the 30-second expiry condition is met | Existing MES correlation, not a timeout or cleanup setting implemented in this Python API. |

An important difference is that my HTTP request waits for a lock; I did **not** implement a separate deferred payload store equivalent to `_pendingRX`. Coordination, ordering, revalidation and careful cleanup are the common principles.

### Lock cleanup was deliberately left simple

A million distinct keys could leave a million lock entries. I must not simply delete a lock as soon as its first request finishes: another request may already be waiting on that object. A later request could then create a different lock for the same key, splitting coordination. I retained the registry for this learning exercise rather than implement a lifecycle scheme.

### My uploaded final `mes_orders.py`

The original uploaded file was retrieved and read directly. Its full content appears in Appendix A. It has module-level dictionaries, per-key lock lookup, diagnostic IDs, payload conflict checking, a three-second delay, and storage before releasing the lock.

The review identified an extra leading space before the comment at original line 34. Aligning that comment was recommended, but it is cosmetic and does not change execution. Appendix A preserves the original uploaded content rather than claiming that recommendation was saved.

### My actual per-key tests

| Test | Original screenshots | Actual observation |
|---|---|---|
| Same TX563, same payload | S24–S25 | Two 200 responses, one new-operation log and one duplicate log. Both use LockId `2883151202928`, StoreId `2883117720064`. |
| Different TX564 and TX565 | S26–S27 | Both process as new and return 200. LockIds are `1355265068544` and `1355293775568`; StoreId is `1355259978560` for both. |

For TX563 I reused the two-job command from section 05 with `transaction_id = "TX563"`. I restarted first to begin with an empty store. For TX564/TX565, both keys were new, so another restart was unnecessary. The different-key command was:

```powershell
$jobs = @("TX564", "TX565") | ForEach-Object {
    $tx = $_
    Start-Job -ScriptBlock {
        param($transactionId)
        $body = @{
            order_id = "ORDER100"
            transaction_id = $transactionId
            status = "Completed"
        } | ConvertTo-Json
        Invoke-RestMethod `
            -Uri "http://localhost:8000/mes/orders/complete" `
            -Method Post `
            -ContentType "application/json" `
            -Body $body
    } -ArgumentList $tx
}
$watch = [System.Diagnostics.Stopwatch]::StartNew()
$jobs | Wait-Job | Receive-Job
$watch.Stop()
Write-Host "Elapsed time: $($watch.Elapsed.TotalSeconds) seconds"
$jobs | Remove-Job
```

The stopwatch starts **after** the jobs have been started. Its reading would reflect the remaining job scheduling, processing and collection, not an isolated API duration. My shared screenshots did not capture an elapsed-time value. The evidence supports independent lock paths and successful results; I must not claim that I measured exactly three seconds or a precise speed-up.

## 08. Concurrent conflicting payloads and blocked PowerShell jobs

I then sent two simultaneous requests using **TX566**, one for ORDER100 and one for ORDER101. Whichever acquired the shared transaction lock first could become the recorded operation. The other had to compare its payload with that result and receive 409.

The first test used `Invoke-WebRequest`, read its status/content, and attempted to read an exception status in `catch`. **Observed:** `Wait-Job` failed with `BlockedJobsDeadlockWithWaitJob`, stating that jobs were blocked waiting for user interaction (S28).

An interactive prompt was a possible explanation. It was not proven, and the job error did not establish a FastAPI failure. I returned to the `Invoke-RestMethod` approach that had worked earlier. The corrected instructions restarted FastAPI to clear TX566 and then used:

```powershell
$jobs = @("ORDER100", "ORDER101") | ForEach-Object {
    $order = $_
    Start-Job -ScriptBlock {
        param($orderId)
        $body = @{
            order_id = $orderId
            transaction_id = "TX566"
            status = "Completed"
        } | ConvertTo-Json
        try {
            $result = Invoke-RestMethod `
                -Uri "http://localhost:8000/mes/orders/complete" `
                -Method Post `
                -ContentType "application/json" `
                -Body $body `
                -ErrorAction Stop
            [PSCustomObject]@{ OrderId = $orderId; Result = "200 OK" }
        }
        catch {
            [PSCustomObject]@{
                OrderId = $orderId
                Result = "409 Conflict"
                Error = $_.ErrorDetails.Message
            }
        }
    } -ArgumentList $order
}
$jobs | Wait-Job | Receive-Job
$jobs | Remove-Job
```

The simplified catch labels **any caught error** as “409 Conflict.” That is not a general status-detection implementation. I verified the actual HTTP status in the server access log rather than treating the printed label as proof.

**Observed:** S29–S30 show ORDER100 winning with 200 and ORDER101 returning 409, with the exact conflict detail used earlier. Both requests share LockId `2139305803904`. The server logs confirm one success and one conflict. ORDER100 winning was this run's result, not a guaranteed ordering rule.

For leftover test jobs, the suggested inspection was:

```powershell
Get-Job | Select-Object Id, State
# If a known test job is still blocked, replace <id> with that test job's ID:
Remove-Job -Id <id> -Force
```

That targeted cleanup was advice, not evidence that I removed every blocked job. I should inspect the jobs before removing only the relevant test jobs.

## 09. Why this is still not production idempotency

A lock only coordinates users of the **same shared lock object**. Cloud Run A can have TX567 → Lock A and Dictionary A, while Cloud Run B has TX567 → Lock B and Dictionary B. Both can process the same key. Multiple worker processes have the same fundamental separation. A restart also loses results.

I already understood SQL unique constraints and did not want to repeat an unnecessary practical. My proposed table idea was clarified with this teaching example:

```sql
CREATE TABLE Orders
(
    Id INT IDENTITY(1,1) PRIMARY KEY,
    TransactionId VARCHAR(50) UNIQUE
);
```

Two inserts using TX561 cannot both create independent rows with that same unique key. The discussion mentioned SQL Server errors 2627 or 2601 as typical duplicate/unique-key errors. This was conceptual SQL discussion; I did not install SQL, execute the table creation or capture those errors in this exercise.

My other description was “check TX561, then insert if absent.” This works sequentially when request B checks after A commits. The concurrent case is different:

| Illustrative time | Request A | Request B |
|---|---|---|
| 0 ms | Checks TX561: absent | — |
| 1 ms | — | Checks TX561: absent |
| 2 ms | Attempts INSERT | — |
| 3 ms | — | Attempts INSERT |
| Later | One succeeds | The competing insert is rejected by uniqueness enforcement |

The database's atomic uniqueness enforcement is the final protection; a preliminary check is not sufficient. **Atomic reservation** means only one requester can successfully claim the key in shared storage. The competing requester examines the existing record rather than independently performing the business operation.

Uniqueness alone still does not supply a complete API contract. If SQL committed but the response was lost, simply exposing a duplicate-insert error is not the same as returning the original successful result. A production design may record the key, request identity, processing state and previous response, and handle in-progress or interrupted work. Those records and the business operation need appropriate transaction coordination.

Shared SQL/Redis idempotency, durable reservation and reconciliation remained **concepts only**. I intentionally skipped another SQL practical, Redis setup and GCP deployment.

## 10. My external retry client and timeout experiment

I asked where `test_mes_retry.py` should go. It belongs at the **project root alongside `requirements.txt`**, outside `app/routers`, because it acts as an external station service calling the API over HTTP:

```text
01-python-fastapi/
  app/
    main.py
    routers/mes_orders.py
  test_mes_retry.py
  requirements.txt
  Dockerfile
```

The proposed prerequisite check, in the project's virtual environment, was:

```powershell
python -m pip show requests
```

The script uses `requests` and `time`; the discussion asked me to ensure the package was installed. There is no captured package-version or installation result, so I do not invent one.

| Setting | Value used/discussed | Purpose and interaction |
|---|---|---|
| URL | `http://localhost:8000/mes/orders/complete` | Calls my local MES endpoint. |
| Order/status | ORDER100 / Completed | Same payload on every retry. |
| Transaction key | TX567 | Fresh test key, reused across attempts. |
| Server simulation | 3 s | Deliberately slower than the client's response wait. |
| `timeout` | 1 s | Causes the controlled read-timeout case. A scalar configures connection/read behavior; it is not a strict whole-operation deadline. |
| `max_attempts` | 4 | Initial attempt plus at most three retries. |
| `base_delay` | 1 s | Backoff waits intended to grow 1, 2, 4 s. |
| Jitter | Not implemented in the tested code | Discussed afterward as a production improvement. |

### Which exception did I expect?

I asked what happens when the client waits one second but the server takes three. In this test the connection was made but no response arrived within the read wait, so `requests.exceptions.ReadTimeout` was raised. The actual message included:

```text
HTTPConnectionPool(host='localhost', port=8000):
Read timed out. (read timeout=1)
```

`ConnectTimeout` concerns establishing the connection. `ReadTimeout` concerns waiting for response data after connection. `ReadTimeout` inherits from `RequestException`, so the broader handler caught it:

```python
except requests.exceptions.RequestException as ex:
    print(f"Attempt {attempt} failed: {ex}")
```

A specifically proposed alternative was:

```python
except requests.exceptions.ReadTimeout as ex:
    print(f"Server response not received within timeout: {ex}")
```

The test client also called `response.raise_for_status()` so unsuccessful HTTP status codes could raise an exception, printed successful status/JSON, and broke out of the loop on success. Broadly retrying every `RequestException` was a learning simplification, not the final production retry policy.

### The source-snippet discrepancy I must retain

The original displayed retry-script blocks end after the `attempt == max_attempts` check and omit the delay calculation and sleep. Later explanations refer to `delay = base_delay * (2 ** (attempt - 1))` and `time.sleep(delay)`, and S33 visibly prints a one-second wait. Therefore, the **actual run did include a wait**, but those earlier displayed snippets are incomplete as a full retry/backoff script.

The actual uploaded attachment was `mes_orders.py`; an original `test_mes_retry.py` file was not attached. I can document its visible behavior and taught statements, but I cannot present a reconstructed client as the exact saved file.

### “Nothing happens” and the save correction

In terminal 1 I ran `py -m app.main`. In terminal 2, at the root, I ran:

```powershell
py test_mes_retry.py
```

Initially the prompt returned with no attempt output (S31), while the server showed startup but no incoming request (S32). The diagnostic suggestions were to check whether the file was empty, unsaved, commented out or contained an uncalled function, and optionally add:

```python
print("Day 24 - Retry client started")
```

I then confirmed I had not saved the script. I saved with **Ctrl+S** and reran it. Unlike the earlier lock incident, this unsaved client file was explicitly acknowledged. No change to the server lock was necessary.

### My actual successful retry result

S33 shows:

```text
Attempt 1: Sending TX567
Attempt 1 failed: ... Read timed out. (read timeout=1)
Waiting 1 seconds before retry...
Attempt 2: Sending TX567
Success: HTTP 200
{'order_id': 'ORDER100', 'transaction_id': 'TX567',
 'status': 'Completed', 'message': 'Order completed successfully'}
```

S34 shows both TX567 requests using LockId `1980402430128` and StoreId `1980369150528`, one new-processing log and one duplicate-detection log. The retained startup text says “Day 23 - Application started”; it is an earlier log label, not evidence that this was a different experiment.

The approximate explanation was:

| Illustrative elapsed time | Client | Server |
|---|---|---|
| 0 s | Sends TX567 | Begins the 3-second simulated operation |
| About 1 s | ReadTimeout | Original request can continue |
| 1–2 s | Waits 1 second | Still processing |
| About 2 s | Sends TX567 again | Retry waits on the same per-key lock |
| About 3 s | Receives a successful retry response in this run | First request stores the result; retry reads it |

The retry has approximately `3 s − 2 s = 1 s` left to wait, which is very close to its own one-second read timeout. Scheduling and network overhead could cause another run's second attempt to time out too. **Observed success is valid but not guaranteed by these settings.** I did not capture precise timestamps.

Only the **first retry wait** was observed in this run. The second and third intended backoff waits were not exercised because attempt 2 succeeded.

## 11. Production retry rules, backoff and my jitter clarification

### Which failures should my station retry?

| Result | My response |
|---|---|
| 200 / 201 | Success; stop retrying. |
| 400 / 422 | Correct invalid request data. |
| 401 / 403 | Investigate authentication or permission; do not blindly repeat. |
| 404 | Usually do not retry; the resource may not exist. |
| 409 | Resolve the business conflict; a fresh attempt does not fix different data under the same key. |
| 429 | Retry when appropriate with backoff and respect `Retry-After`. |
| 500 | Retry selectively when the failure is temporary and the operation is safely idempotent. |
| 502 / 503 | Usually candidates for bounded retries. |
| 504 | Retry cautiously because original processing may have continued. |
| Client ReadTimeout | Outcome may be unknown; retain the key and coordinate safely. |

For data-changing POST operations, a status code alone is not enough to authorize repeating business effects. The operation must be safe to repeat using the same transaction identity. I should bound attempts, cap the delay and consider the total retry deadline as well as per-attempt waits.

### My backoff calculation

With a base delay of 1 second and retry number `r` starting at 1:

```text
delay(r) = base_delay × 2^(r − 1)
```

| Overall attempt | Action | Wait before it | Calculation |
|---|---|---|---|
| 1 | Initial request | 0 s | No retry wait |
| 2 | Retry 1 | 1 s | 1 × 2^0 |
| 3 | Retry 2 | 2 s | 1 × 2^1 |
| 4 | Retry 3 | 4 s | 1 × 2^2 |

Total planned backoff is `1 s + 2 s + 4 s = 7 s`, **excluding all HTTP execution and overhead**. Four attempts does not mean four retries. The discussed client statements calculate the delay after a failed attempt and before the next one:

```python
delay = base_delay * (2 ** (attempt - 1))
time.sleep(delay)
```

There is no reason to sleep after the last allowed attempt. A maximum-delay and total-deadline policy were discussed, but no numeric production values were selected or saved.

### My question: isn't 1, 2, 4 already “backoff with jitter”?

I had combined two ideas. **Exponential backoff** describes how the base delay grows. **Jitter** introduces randomness so many clients do not retry together.

If 100 MES Station Services all fail together and all wait exactly 1 second, then 2 seconds, then 4 seconds, they can repeatedly hit the recovering API in synchronized bursts. This was the **thundering herd** example. Jitter spreads those arrivals across time.

| Retry | Base delay | Station A example | Station B example | Station C example |
|---|---|---|---|---|
| 1 | 1 s | 1.2 s | 0.8 s | 1.1 s |
| 2 | 2 s | 2.3 s | 1.7 s | 2.1 s |
| 3 | 4 s | 4.4 s | 3.8 s | 4.2 s |

These are **teaching values**, not measurements or saved application settings. An earlier example also used 1.2, 2.3 and 4.6 seconds. These illustrate varying waits rather than a prescribed sequence.

The proposed Python strategy applies a random multiplier between 0.8 and 1.2:

```python
# Teaching variation for a synchronous client retry loop.
# Requires import time and an existing attempt value.
import random

base_delay = 1
delay = base_delay * (2 ** (attempt - 1))
jittered_delay = delay * random.uniform(0.8, 1.2)
print(f"Waiting {jittered_delay:.2f} seconds")
time.sleep(jittered_delay)
```

For the third retry, the base is 4 seconds:

```text
Minimum = 4 s × 0.8 = 3.2 s
Maximum = 4 s × 1.2 = 4.8 s
```

The client chooses a random delay in that range. This is one strategy. **Full jitter** can choose between zero and a calculated maximum; production policies may also apply caps and server-provided `Retry-After` values. I did not add or test jitter in my Day 24 client.

The concepts complement each other: backoff reduces repeated pressure, jitter reduces synchronized pressure, and idempotency prevents duplicated business effects.

### What if every attempt fails?

The station's failure to receive a successful response does not prove that SQL failed. The API may have committed while every response was lost.

| Transaction state | Meaning | My station's next action |
|---|---|---|
| Completed | Operation is known to have committed | Use its recorded result. |
| Failed | Known business or technical failure | Handle that specific failure. |
| Unknown / Pending | Final outcome cannot yet be confirmed | Reconcile using the original TransactionId. |

I should not generate a fresh ID and repeat the operation merely because retries are exhausted. A production system can query the original status, safely retry the same key, or use controlled reconciliation. Durable reconciliation was discussed, not implemented.

## 12. My final state, retained code and deferred work

| Area | Final learning status |
|---|---|
| Local FastAPI MES endpoint | Implemented and tested. |
| In-memory saved response and identical retry | Implemented and verified with branch logs. |
| Conflicting payload | Sequential and concurrent HTTP 409 results observed. |
| Race without lock | Reproduced with two new-processing logs. |
| Global lock | Implemented and verified after an initially unexpected run. |
| Per-transaction lock | Final uploaded implementation; same/different-key tests passed. |
| Client timeout and retry | Read timeout observed; first retry wait observed; second attempt succeeded. |
| Jitter | Concept and proposed example only. |
| Durable shared SQL/Redis coordination | Concept only. |
| SQL operations, history, RabbitMQ events | MES analogies; no actual database/event operation in this exercise. |
| Cloud deployment | Not performed or required. |

When temporary-code removal was suggested, I asked to keep it for reference. The final decision was to retain `mes_orders.py`, `test_mes_retry.py`, both dictionaries, `await asyncio.sleep(3)`, and LockId/StoreId diagnostics as learning material. I did not remove them.

The proposed source-file comments were:

```python
# Day 24 - Idempotency and concurrency learning example.
# Uses in-memory transaction storage and per-transaction asyncio locks.
# The 3-second delay simulates slow database processing.
# This is only for local learning, not production use.
# Multiple Cloud Run instances cannot share these locks or transaction data.
```

And for the client:

```python
# Day 24 - Client timeout and retry experiment.
# The 1-second timeout is intentionally shorter than the API's 3-second delay.
# Reuses the same TransactionId to demonstrate idempotent retries.
# Learning example only, not production retry logic.
```

These were recommendations, with no evidence that the new header comments were saved. The existing uploaded file already contains process-local learning comments. I should explicitly decide before including this learning-only router in a future production deployment of the employee API.

The proposed next commit message was:

```text
Day 24 - Implemented MES API idempotency, per-transaction locking and retry handling
```

No commit execution was shown. I also deferred event-loop/C# async study, lock-registry lifecycle management, durable shared idempotency, transaction reconciliation and production retry refinements. Removing the simulation was not a required cleanup item after I chose to keep it.

## 13. My quick recall guide

| When I need to remember… | My answer | Evidence |
|---|---|---|
| Does a timeout prove the business operation failed? | No; retain its key and confirm the outcome. | S33–S34; sections 10–11 |
| Is two HTTP 200 responses proof of idempotency? | No; inspect branch logs and side effects. | S04, S08, S17 |
| Same key, same payload? | Return recorded result after coordination. | S24–S25 |
| Same key, different payload? | 409 Conflict. | S09–S11, S29–S30 |
| Does assigning a dictionary key twice raise a unique error? | No; ordinary assignment overwrites. | Section 04 |
| What must the lock protect? | Check, process and store as one critical section. | S18–S19 |
| Why one lock per key? | Same-key requests coordinate; unrelated keys can progress independently. | S24–S27 |
| Is setdefault's default argument lazy? | No; it is evaluated even when the key exists. | Section 07 |
| Can local locks protect multiple instances? | No; shared durable atomic coordination is required. | Section 09 |
| What caused the 422 test? | Malformed JSON passed through curl/PowerShell quoting. | S14–S15 |
| What caused “nothing happens”? | I had not saved the client file. | S31–S32 |
| Backoff versus jitter? | Growing base waits versus randomized spread. | Section 11 |
| Four attempts means what? | Initial call plus three retries; planned waits total 7 seconds excluding calls. | Section 11 |
| Exactly three seconds for different keys? | An illustration; I did not capture a stopwatch measurement. | S26–S27 |
| Which file is the actual uploaded evidence? | mes_orders.py, preserved in Appendix A. | Appendix A |

## 14. Coverage and verification record

The entire Day 24 discussion was reviewed from its explicit start through the final documentation request, with the preceding Day 24 task plan used for scope. Earlier Day 23 shutdown material is background, not an additional Day 24 practical.

I have 34 distinct original Day 24 screenshot attachments in the workflow register. All are embedded in the workbook; none is replaced by a recreated screenshot. Failed and intermediate versions remain visible with corrections identified. Repeated retrievals of the same original file were deduplicated by SHA-256. The 69-item coverage checklist is included in the workbook's Coverage sheet, mapping every substantive topic, question, correction, command family, calculation, decision and limitation to these notes.

The uploaded server file is preserved below. The unuploaded client source cannot be certified verbatim; the snippet omission and actual wait output are explicitly recorded in section 10. Exact request arrival times, a measured different-key runtime, proof of the first unsaved-server-edit cause, executed commit, saved proposed comments and completed cleanup were not supplied, so I do not claim them.

The screenshot register and verification details are appended below after checking the saved workbook.

### Earlier command versions retained for debugging recall

The failed curl experiment in section 05 used this job body, with the same `$body` JSON and `Wait-Job`, `Receive-Job`, `Remove-Job` sequence shown there:

```powershell
$jobs = 1..2 | ForEach-Object {
    Start-Job -ScriptBlock {
        param($json)
        curl.exe -s -X POST "http://localhost:8000/mes/orders/complete" `
            -H "Content-Type: application/json" `
            -d $json
    } -ArgumentList $body
}
```

I keep this as the **failed version**, not the recommended command. Its observed 422/json_invalid outcome is preserved in S14–S15. The corrected complete command is in section 05.

The first concurrent-conflict test in section 08 used this request and result handling inside the two-order `Start-Job` loop, before the corrected Invoke-RestMethod version:

```powershell
try {
    $response = Invoke-WebRequest `
        -Uri "http://localhost:8000/mes/orders/complete" `
        -Method Post `
        -ContentType "application/json" `
        -Body $body
    [PSCustomObject]@{
        OrderId = $orderId
        StatusCode = [int]$response.StatusCode
        Response = $response.Content
    }
}
catch {
    [PSCustomObject]@{
        OrderId = $orderId
        StatusCode = [int]$_.Exception.Response.StatusCode
        Response = $_.ErrorDetails.Message
    }
}
```

That experiment produced the blocked-background-job error in S28. I did not establish which interactive prompt caused it.

The originally displayed retry-client script was the following. **It is an incomplete backoff example as displayed**: it contains no sleep block. It is retained here to preserve what was proposed rather than silently repair the source history. The actual successful run and separately discussed backoff statements are documented in sections 10–11.

```python
import time
import requests

url = "http://localhost:8000/mes/orders/complete"
payload = {
    "order_id": "ORDER100",
    "transaction_id": "TX567",
    "status": "Completed"
}
max_attempts = 4
base_delay = 1

for attempt in range(1, max_attempts + 1):
    try:
        print(f"Attempt {attempt}: Sending TX567")
        response = requests.post(url, json=payload, timeout=1)
        response.raise_for_status()
        print(f"Success: HTTP {response.status_code}")
        print(response.json())
        break
    except requests.exceptions.RequestException as ex:
        print(f"Attempt {attempt} failed: {ex}")
        if attempt == max_attempts:
            print("Maximum attempts reached")
            break
```

The asynchronous teaching function used to illustrate yielding was:

```python
async def process_order():
    print("Step 1")
    await asyncio.sleep(3)
    print("Step 2")
```

While this function is awaiting the asynchronous sleep, another task can run. This was an explanation for my deferred event-loop topic, not another measured practical.


## Appendix A. Original uploaded mes_orders.py

The following is the retrieved original upload, including its cosmetic comment indentation. It is a local learning implementation, not a durable distributed solution.

```python
from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import HTTPException
import logging
import asyncio

router = APIRouter(
    prefix="/mes/orders",
    tags=["MES Orders"]
)

# Day 24 - One lock for each TransactionId.
# Different transactions can process in parallel.
# Learning-only: locks are shared only within this Python process.
transaction_locks: dict[str, asyncio.Lock] = {}

# Day 24 - Temporary in-memory store to understand idempotency.
# Each transaction ID represents one logical business operation.
# This is local to one Python process, not shared across containers.
processed_transactions = {}

# Request received from MES Station Service
class OrderCompletionRequest(BaseModel):
    order_id: str
    transaction_id: str
    status: str


@router.post("/complete")
async def complete_order(request: OrderCompletionRequest):

    transaction_id = request.transaction_id

     # Requests with the same TransactionId share one lock.
    lock = transaction_locks.setdefault(
        transaction_id,
        asyncio.Lock()
    )

    logging.info(
        f"TX={transaction_id}, LockId={id(lock)}, "
        f"StoreId={id(processed_transactions)}")

    async with lock:

        # Only one request can enter this section at a time.
        if transaction_id in processed_transactions:

            previous = processed_transactions[transaction_id]

            if previous["order_id"] != request.order_id or \
               previous["status"] != request.status:
                raise HTTPException(
                    status_code=409,
                    detail="Transaction ID already used for a different request"
                )

            logging.info(
                f"Duplicate transaction detected: {transaction_id}"
            )

            return previous

        # Simulate a slow MES database operation.
        await asyncio.sleep(3)

        response = {
            "order_id": request.order_id,
            "transaction_id": transaction_id,
            "status": request.status,
            "message": "Order completed successfully"
        }

        processed_transactions[transaction_id] = response

        logging.info(
            f"Processing new transaction: {transaction_id}"
        )

        return response
```

## Appendix B. Original screenshot register

| ID | Workflow caption | Workbook image location | Notes section |
|---|---|---|---|
| S01 | First endpoint acknowledgement | Setup!A8 | 02 |
| S02 | Repeated acknowledgement before idempotency | Setup!A38 | 02 |
| S03 | First response after adding the transaction store | Setup!A69 | 03 |
| S04 | Identical retry returns the same JSON | Setup!A113 | 03 |
| S05 | Fresh TX561 request during logging test | Sequential!A8 | 03 |
| S06 | Server processes the first TX561 request | Sequential!A50 | 03 |
| S07 | Sequential retry response | Sequential!A75 | 03 |
| S08 | Server confirms duplicate detection | Sequential!A109 | 03 |
| S09 | Conflicting payload prepared | Sequential!A137 | 03 |
| S10 | Conflict rejected with HTTP 409 | Sequential!A163 | 03 |
| S11 | Combined sequential test logs | Sequential!A196 | 03 |
| S12 | Incorrect delay placement | Race!A8 | 04 |
| S13 | Delay moved before new-result creation | Race!A35 | 04 |
| S14 | curl JSON quoting failure in PowerShell | Race!A73 | 05 |
| S15 | Server rejects malformed JSON with 422 | Race!A103 | 05 |
| S16 | Parallel PowerShell requests receive responses | Race!A130 | 05 |
| S17 | Race condition reproduced on the server | Race!A182 | 05 |
| S18 | Global lock implementation, first view | Lock!A8 | 06 |
| S19 | Global lock implementation, complete view | Lock!A50 | 06 |
| S20 | First locked test still returns two responses | Lock!A98 | 06 |
| S21 | Unexpected duplicate processing after intended lock edit | Lock!A129 | 06 |
| S22 | Retest client responses after saving and restarting | Lock!A157 | 06 |
| S23 | Global lock verified with object IDs | Lock!A189 | 06 |
| S24 | Same-key test returns two successful responses | Per transaction!A8 | 07 |
| S25 | TX563 shares one lock and processes once | Per transaction!A40 | 07 |
| S26 | Different keys both return success | Per transaction!A68 | 07 |
| S27 | Different keys use distinct locks | Per transaction!A98 | 07 |
| S28 | PowerShell background jobs become blocked | Per transaction!A126 | 08 |
| S29 | Corrected concurrent conflict test | Per transaction!A161 | 08 |
| S30 | Server confirms one success and one conflict | Per transaction!A206 | 08 |
| S31 | Retry client exits without running requests | Retry!A8 | 10 |
| S32 | Server is running but receives no retry request | Retry!A29 | 10 |
| S33 | Observed timeout, one-second backoff, then success | Retry!A52 | 10 |
| S34 | Final server evidence for idempotent retry | Retry!A76 | 10 |

## Appendix C. Saved-file verification

The saved workbook was inspected as an XLSX package: it contains 34 embedded PNG files and 34 drawing anchors. Every embedded image matches an original recovered attachment byte for byte by SHA-256. All nine worksheets were rendered for visual review. The nine saved calculation results were checked independently, including 7 seconds total base backoff, 3.2–4.8 seconds jitter at a 4-second base, and the illustrative 6-second/3-second lock comparison. No Excel error-valued cells were found. All 34 screenshot IDs and locations match the register; the original uploaded server source is included verbatim. Native Microsoft Excel application behavior was not separately exercised.
