# Python, FastAPI, Docker, GCP & CI/CD — Revision Quiz Notes (Rounds 1–4)

**Learning covered:** Days 1–28  |  **Total questions:** 60  |  **Prepared:** 4 November 2026

## How I use these notes

This is my personal revision record. Each question includes **what I selected**, the **correct answer**, and a short **explanation of why**. Where I answered incorrectly, I also kept the explanation of my incorrect choice to help me remember the difference. Multi-select answers show each choice separated by semicolons.

**Important evidence limit:** Individual selected answers for **Round 3** could not be recovered from the saved quiz state. I have included every Round 3 question and its correct explanation, but explicitly marked my choice as *not recoverable* rather than guessing. The previously reported Round 3 score was 13/15; it does not reveal which individual questions I missed. Rounds 1, 2 and 4 use saved selections.

## Results and review priorities

| Round | Score | Questions | Saved selected answers |
|---|---:|---:|---|
| 1 — Foundation and CI/CD | 14/15 | 15 | Yes |
| 2 — Practical revision | 12/15 | 15 | Yes |
| 3 — Advanced scenarios | 13/15 (previously reported) | 15 | Not available individually |
| 4 — Production troubleshooting | 12/15 | 15 | Yes |

**Areas to review:** Round 1 multi-select completeness; Round 2 FastAPI 422 vs 401, `0.0.0.0` vs `127.0.0.1`, and `.dockerignore`; Round 3 exponential-backoff and cross-instance concurrency concepts (reported difficulty); Round 4 exponential backoff arithmetic, per-process vs cross-instance semaphores, and immutable revision targeting.

## Round 1 — Foundations, IAM and deployment

### Q1. In our FastAPI employee-api project, what is Pydantic mainly responsible for?

**My selection:** Validating and parsing request data

**Correct answer:** Validating and parsing request data

**Result:** ✅ Correct

**Explanation:** Pydantic models validate incoming fields and convert supported values to the expected Python types.

### Q2. We change only requirements.txt and rebuild a Docker image. What is the likely effect on Docker layer caching?

**My selection:** The dependency installation layer may rebuild

**Correct answer:** The dependency installation layer may rebuild

**Result:** ✅ Correct

**Explanation:** Changing requirements.txt invalidates a layer that uses that file for dependency installation, while earlier unaffected layers can remain cached.

### Q3. A Cloud Run service configured with concurrency 1 can process requests on multiple instances when autoscaling permits it.

**My selection:** True

**Correct answer:** True

**Result:** ✅ Correct

**Explanation:** Concurrency 1 limits simultaneous requests per instance, not the total number of instances. Cloud Run can scale out.

### Q4. Why did we give employee-api-sa Secret Manager Secret Accessor on the specific EMPLOYEE_API_KEY secret rather than across the project?

**My selection:** To limit the runtime identity's secret access

**Correct answer:** To limit the runtime identity's secret access

**Result:** ✅ Correct

**Explanation:** A resource-scoped grant gives the runtime identity access only to the specified secret rather than all project secrets.

### Q5. During Day 26, what was the purpose of GitHub's OIDC token in our Workload Identity Federation setup?

**My selection:** To provide signed claims about the GitHub workflow identity

**Correct answer:** To provide signed claims about the GitHub workflow identity

**Result:** ✅ Correct

**Explanation:** Google validates the GitHub-issued signed token and federation conditions before permitting the configured external identity.

### Q6. Which role did github-deploy-sa need on employee-api-sa so it could attach that identity when deploying Cloud Run revisions?

**My selection:** Service Account User

**Correct answer:** Service Account User

**Result:** ✅ Correct

**Explanation:** Service Account User includes iam.serviceAccounts.actAs, which permits the deployer to attach the chosen runtime identity.

### Q7. Which statements correctly describe our Day 27 GitHub Actions deployment? Select all that apply.

**My selection:** The workflow uses WIF to authenticate to Google Cloud

**Correct answer:** Python tests run before the image deployment; The pushed image is tagged using github.sha; The workflow uses WIF to authenticate to Google Cloud

**Result:** ❌ Incorrect

**Explanation:** The workflow runs tests before deployment, tags the image with the commit SHA, and uses Workload Identity Federation for Google authentication. Cloud Run Developer does not grant blanket Secret Manager access.

**Why my selection was incomplete/incorrect:** The WIF choice was correct, but this was a select-all question. The testing order and github.sha image tag were also correct.

### Q8. Our Docker image is tagged with a Git commit SHA, but Cloud Run displays a sha256 digest. What does the digest primarily identify?

**My selection:** The exact referenced image content

**Correct answer:** The exact referenced image content

**Result:** ✅ Correct

**Explanation:** A SHA256 digest is a content-based identifier for the referenced image manifest or related OCI artifact.

### Q9. Our Day 28 candidate revision employee-api-00030-pen received 0% normal traffic. How could we test it directly without promoting it?

**My selection:** By using the candidate tagged URL with valid authentication

**Correct answer:** By using the candidate tagged URL with valid authentication

**Result:** ✅ Correct

**Explanation:** A revision tag gives a direct URL to the candidate despite 0% normal traffic; the service still requires valid authentication.

### Q10. If Cloud Run successfully creates a new revision, the API is automatically verified as functioning correctly for real application requests.

**My selection:** False

**Correct answer:** False

**Result:** ✅ Correct

**Explanation:** Successful deployment does not prove all endpoints or transaction flows work. An actual smoke test is additional evidence.

### Q11. When opening our private Cloud Run candidate URL in a browser produced HTTP 403, but a Cloud Shell request with an identity token returned HTTP 200, what did that demonstrate?

**My selection:** The revision required an authorised request

**Correct answer:** The revision required an authorised request

**Result:** ✅ Correct

**Explanation:** The authenticated call was accepted; the unauthenticated browser result was about access, not proof the application endpoint was broken.

### Q12. A MES Station Trigger reaches revision A and its later Echo reaches revision B. What is the principal risk when transaction state is stored only in revision A's memory?

**My selection:** Revision B may not find the transaction state

**Correct answer:** Revision B may not find the transaction state

**Result:** ✅ Correct

**Explanation:** Different Cloud Run instances or revisions do not automatically share in-memory transaction dictionaries.

### Q13. During our rollback exercise, why did selecting “Send all traffic to the latest revision” fail to restore employee-api-00026-djg?

**My selection:** Latest referred to the newer 00030-pen revision

**Correct answer:** Latest referred to the newer 00030-pen revision

**Result:** ✅ Correct

**Explanation:** Selecting an older row does not redefine “latest”; rollback required explicitly choosing “Send all traffic to one revision”.

### Q14. If two concurrent requests both read an in-memory transaction state before either updates it, what can an asyncio.Lock or SemaphoreSlim-style gate help prevent within one process?

**My selection:** An unsafe overlap in the protected state update

**Correct answer:** An unsafe overlap in the protected state update

**Result:** ✅ Correct

**Explanation:** A correctly placed gate serialises the critical section within the process. It is not a distributed lock.

### Q15. Why is a durable job record important if a FastAPI background task or Cloud Run instance crashes after accepting a request?

**My selection:** It lets a worker recover or reconcile unfinished work

**Correct answer:** It lets a worker recover or reconcile unfinished work

**Result:** ✅ Correct

**Explanation:** A committed job record survives process loss and supports recovery, retries and reconciliation.

---

## Round 2 — FastAPI, containers, WIF and resilient processing

### Q1. Our FastAPI /employees POST endpoint expects a Pydantic model with a required name field. A client sends JSON without name. What normally happens?

**My selection:** FastAPI returns HTTP 401 due to the missing field

**Correct answer:** FastAPI returns HTTP 422 before entering the endpoint

**Result:** ❌ Incorrect

**Explanation:** A missing required Pydantic field causes FastAPI request validation to fail before endpoint execution; 422 is the normal validation response.

**Why my selection was incomplete/incorrect:** 401 relates to authentication. A required body field missing is a validation problem, not an authentication error.

### Q2. Our Cloud Run container is configured for port 8080. Which application startup behaviour allows Cloud Run to forward HTTP requests into it?

**My selection:** Listen only on 127.0.0.1:8080

**Correct answer:** Listen on 0.0.0.0 using the configured PORT

**Result:** ❌ Incorrect

**Explanation:** Cloud Run forwards incoming requests to the container on its configured port; binding to 0.0.0.0 makes the server reachable on the container network interface.

**Why my selection was incomplete/incorrect:** Binding only to loopback (127.0.0.1) may prevent Cloud Run from reaching the application.

### Q3. We want a smaller, cleaner Docker build context for our FastAPI project. Which files or directories should generally be excluded from the build context? Select all that apply.

**My selection:** The application source directory app

**Correct answer:** The local .venv directory; The local .pytest_cache directory; The .env file containing local secrets

**Result:** ❌ Incorrect

**Explanation:** Local virtual environments, pytest caches and secret-containing .env files should generally be excluded with .dockerignore. Application source must remain in the build context.

**Why my selection was incomplete/incorrect:** Excluding the app source means the Docker build cannot package the application itself. This question required selecting three exclusions.

### Q4. A service account needs to call our private Cloud Run employee-api over HTTPS. Which role is most directly intended to authorise invocation?

**My selection:** Cloud Run Invoker

**Correct answer:** Cloud Run Invoker

**Result:** ✅ Correct

**Explanation:** Cloud Run Invoker authorises the run.routes.invoke operation used to call a private Cloud Run service.

### Q5. Our GitHub Actions workflow has permissions: id-token: write. What does this allow the workflow to request?

**My selection:** A short-lived OIDC identity token issued by GitHub

**Correct answer:** A short-lived OIDC identity token issued by GitHub

**Result:** ✅ Correct

**Explanation:** GitHub may issue a signed, short-lived OIDC identity token; Google IAM still decides whether it grants any Google resource permissions.

### Q6. A Workload Identity Federation provider can restrict accepted GitHub OIDC tokens by repository and branch claims.

**My selection:** True

**Correct answer:** True

**Result:** ✅ Correct

**Explanation:** WIF provider attribute mapping and conditions can filter assertion.repository, assertion.ref and related claims.

### Q7. Our GitHub WIF provider permits only pushes from the main branch. A valid GitHub OIDC token comes from another branch. What should happen?

**My selection:** The provider rejects the identity because the branch condition fails

**Correct answer:** The provider rejects the identity because the branch condition fails

**Result:** ✅ Correct

**Explanation:** The token may be correctly signed yet fail the configured branch condition; a verified identity is not automatically an allowed identity.

### Q8. For a GitHub Actions job authenticated as github-deploy-sa, which permissions match the operations listed? Select all that apply.

**My selection:** Artifact Registry Writer on the repository to push images; Cloud Run Developer on the service to deploy a revision; Service Account User on employee-api-sa to attach it

**Correct answer:** Artifact Registry Writer on the repository to push images; Cloud Run Developer on the service to deploy a revision; Service Account User on employee-api-sa to attach it

**Result:** ✅ Correct

**Explanation:** Push permission, service-update permission and actAs permission apply to different protected resources. Blanket access to all project secrets is not needed.

### Q9. A Cloud Run request is processing when its instance receives a shutdown signal. Which approach is appropriate for graceful shutdown?

**My selection:** Handle SIGTERM and attempt to finish or clean up promptly

**Correct answer:** Handle SIGTERM and attempt to finish or clean up promptly

**Result:** ✅ Correct

**Explanation:** Respond to SIGTERM and do appropriate cleanup during the platform grace period; forced termination may follow.

### Q10. Our API retries a temporarily failed downstream call using exponential backoff with jitter. Why add jitter?

**My selection:** To reduce many clients retrying at exactly the same time

**Correct answer:** To reduce many clients retrying at exactly the same time

**Result:** ✅ Correct

**Explanation:** Randomised delay spreads retries and reduces synchronised request bursts against a recovering dependency.

### Q11. If an HTTP POST request times out, retrying it automatically guarantees that the business operation was never performed twice.

**My selection:** False

**Correct answer:** False

**Result:** ✅ Correct

**Explanation:** The first request may have committed successfully before its response was lost; retries need idempotency or deduplication to avoid duplicate effects.

### Q12. A FastAPI endpoint starts a long-running business job that must survive instance crashes. Which design is most appropriate?

**My selection:** Persist job state and enqueue durable work for processing

**Correct answer:** Persist job state and enqueue durable work for processing

**Result:** ✅ Correct

**Explanation:** A committed job record and durable queue or task mechanism support recovery and retry after an instance disappears.

### Q13. Our API receives two requests with the same transaction ID because a client retries after a timeout. Which safeguards can help prevent duplicate business effects? Select all that apply.

**My selection:** A database unique constraint on the transaction ID; A persistent idempotency record checked atomically; A transactional operation that returns the existing result for a repeated ID

**Correct answer:** A database unique constraint on the transaction ID; A persistent idempotency record checked atomically; A transactional operation that returns the existing result for a repeated ID

**Result:** ✅ Correct

**Explanation:** Cross-instance correctness needs shared, atomic deduplication. A single asyncio.Lock inside one process cannot coordinate all instances.

### Q14. We want to add automatic smoke testing after deploying a Cloud Run candidate at 0% traffic. Which sequence best protects normal traffic?

**My selection:** Deploy with no traffic, authenticate, test the tagged URL, then promote only on success

**Correct answer:** Deploy with no traffic, authenticate, test the tagged URL, then promote only on success

**Result:** ✅ Correct

**Explanation:** The old revision continues serving normal traffic while the candidate is verified; promotion only follows a successful authenticated test.

### Q15. During a Cloud Run rollout, p95 request latency rises while average latency changes little. What does p95 tell us?

**My selection:** Approximately 95% of measured requests completed at or below that latency

**Correct answer:** Approximately 95% of measured requests completed at or below that latency

**Result:** ✅ Correct

**Explanation:** p95 is the latency threshold at or below which roughly 95% of the measured request durations fall.

---

## Round 3 — Advanced operational scenarios

### Q1. A FastAPI async def endpoint calls time.sleep(5) while processing an HTTP request. Other requests handled by that same event loop become slow. What is the main cause?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** The blocking sleep stops the event loop thread

**Explanation:** time.sleep blocks the executing event-loop thread, preventing other coroutines from making progress. Use an awaitable delay for an async wait.

### Q2. Our employee-api stores employees in a module-level Python dictionary. One test creates an employee, and a later test unexpectedly finds it already present. What is the best immediate testing improvement?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Reset or replace the in-memory store for each test

**Explanation:** Independent tests should begin with predictable state. Resetting or injecting a new store avoids test-order contamination.

### Q3. Our Dockerfile copies all application source before running pip install -r requirements.txt. We frequently edit only Python source files. Which change would improve caching of dependencies?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Copy requirements.txt, install dependencies, then copy application source

**Explanation:** Dependency installation can remain cached when only source files change if dependencies are copied and installed first.

### Q4. A Cloud Run service has concurrency 1 and maximum instances 2. Five CPU-heavy requests arrive together and remain active. Assuming both instances are available, how many requests can be executing concurrently through those instances?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Two

**Explanation:** 2 instances × 1 request per instance = 2 simultaneous slots. Remaining requests may queue or fail under limits.

### Q5. Our Cloud Run service shows increasing p95 latency, but the HTTP 5xx rate remains low. Which investigations are appropriate? Select all that apply.

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Check instance count and concurrency during the slow period; Inspect request-duration metrics and slow application operations; Check downstream dependency latency and timeouts

**Explanation:** Investigate capacity, processing time and downstream dependencies. A low error rate alone does not prove satisfactory latency.

### Q6. Robot A has Cloud Run Developer on employee-api, and Service Account User on employee-api-sa. It tries to update another service, order-api, with the same deploy identity. What should we expect from these grants alone?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** The update is not authorised without additional permissions on order-api

**Explanation:** A service-level Cloud Run Developer grant for employee-api does not extend to order-api; actAs is not service-update permission.

### Q7. A GitHub Actions job receives a valid GitHub OIDC token, but Google refuses to let it impersonate github-deploy-sa. The WIF provider accepts the token. Which permission should we investigate next?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Workload Identity User on github-deploy-sa for the federated principal

**Explanation:** After provider acceptance, the external principal must have the appropriate service-account impersonation binding, typically roles/iam.workloadIdentityUser.

### Q8. In our GitHub Actions pipeline, a docker push failure normally prevents a later Cloud Run deployment step from running when the steps use the default success condition.

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** True

**Explanation:** A failed step causes later steps with the default success condition to be skipped.

### Q9. Our GitHub Actions tests pass, but the Docker build fails with COPY failed: file not found. The repository stores the Dockerfile under 01-python-fastapi/, while the build command runs from the repository root using docker build . What should we investigate first?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Whether Docker's build context and Dockerfile path match the project layout

**Explanation:** COPY source paths are relative to the Docker build context. Check build context, Dockerfile location and .dockerignore.

### Q10. Three consecutive retries use exponential backoff with an initial delay of 500 ms and a multiplier of 2, without jitter or a maximum delay. What is the total waiting time before those three retries?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** 3,500 ms

**Explanation:** The waits are 500 ms + 1,000 ms + 2,000 ms = 3,500 ms = 3.5 seconds, excluding request processing time.

### Q11. Our FastAPI application uses a Python dictionary with an asyncio.Lock to reserve a transaction ID. We deploy it to Cloud Run with multiple instances. Which statements are correct? Select all that apply.

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** The lock coordinates coroutines sharing that lock in one process; An atomic shared database reservation can coordinate across instances; A process restart can erase dictionary-based transaction state

**Explanation:** Process-local locks and dictionaries do not coordinate separate Cloud Run instances. Shared atomic operations coordinate globally; memory is lost on restart.

### Q12. A client sends a transaction request, receives a timeout, and retries. The API stores the transaction successfully but crashes before sending the first response. Which design best lets the second request return the original outcome safely?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Use the same idempotency key and persist the outcome atomically

**Explanation:** Stable idempotency keys with durable results let retries recognise an already committed logical operation.

### Q13. Changing Cloud Run's traffic allocation between already deployed revisions necessarily builds a new Docker image and creates another application revision.

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** False

**Explanation:** Cloud Run traffic changes can route requests among existing revisions without rebuilding the image or creating a new revision.

### Q14. Our candidate revision passes a GET / smoke test, but a newly modified POST endpoint has a regression. What is the most accurate conclusion?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** The basic tested path works, but additional checks are required

**Explanation:** A smoke test proves only the tested path. Separate regression or integration tests are needed for changed endpoints.

### Q15. Our Cloud Run revision cannot start because an environment variable references a Secret Manager version that the runtime service account cannot access. What should we investigate first?

**My selection:** Not recoverable from saved quiz result (Round 3 individual selections were not available)

**Correct answer:** Whether employee-api-sa can access the referenced secret version

**Explanation:** Confirm the secret version exists and is usable, and that the runtime identity has the necessary access to resolve it.

---

## Round 4 — Production troubleshooting and safe promotion

### Q1. Our API retries a failed downstream request four times. Backoff starts at 200 ms and triples after each retry, with no jitter or cap. What is the total waiting time before all four retries?

**My selection:** 10,800 ms

**Correct answer:** 8,000 ms

**Result:** ❌ Incorrect

**Explanation:** Four waits: 200 + 600 + 1,800 + 5,400 = 8,000 ms = 8 seconds, not counting request time.

**Why my selection was incomplete/incorrect:** 10,800 ms exceeds the four-term geometric sum; only four pre-retry waits are counted.

### Q2. Our retry policy uses base delay 400 ms, multiplier 2 and maximum delay 1,000 ms. What are the first four capped retry delays, without jitter?

**My selection:** 400, 800, 1,000, 1,000 ms

**Correct answer:** 400, 800, 1,000, 1,000 ms

**Result:** ✅ Correct

**Explanation:** Uncapped: 400, 800, 1,600, 3,200 ms. Cap each delay to 1,000 ms, giving 400, 800, 1,000, 1,000 ms.

### Q3. Two Cloud Run instances receive the same MES transaction ID simultaneously. Which approaches can coordinate the reservation across both instances? Select all that apply.

**My selection:** A conditional database update within an appropriate transaction; An atomic Redis SET NX operation using the transaction ID; A database insert protected by a unique transaction-ID constraint

**Correct answer:** A conditional database update within an appropriate transaction; An atomic Redis SET NX operation using the transaction ID; A database insert protected by a unique transaction-ID constraint

**Result:** ✅ Correct

**Explanation:** Redis SET NX, database uniqueness and conditional transactional writes can coordinate across instances. Independent semaphores cannot.

### Q4. A process-wide SemaphoreSlim can coordinate two independent Cloud Run container instances without a shared external store.

**My selection:** True

**Correct answer:** False

**Result:** ❌ Incorrect

**Explanation:** SemaphoreSlim coordinates callers sharing the same semaphore object inside a process; different Cloud Run instances have separate memory.

**Why my selection was incomplete/incorrect:** An in-process semaphore cannot provide distributed coordination without a shared mechanism.

### Q5. A worker reserves TX900 using a Redis key with a 30-second TTL. Processing lasts 45 seconds, and another worker acquires the key after expiration. What is the key design problem?

**My selection:** The reservation can expire before the original work finishes

**Correct answer:** The reservation can expire before the original work finishes

**Result:** ✅ Correct

**Explanation:** At 30 s the lease expires while the first worker still runs until 45 s, permitting duplicate claims. Consider renewal, fencing and idempotency.

### Q6. Our FastAPI endpoint awaits a downstream HTTP API for 8 seconds. We want requests to stop waiting after 3 seconds and return a controlled error. What should we configure?

**My selection:** Configure a three-second timeout on the outbound HTTP client call

**Correct answer:** Configure a three-second timeout on the outbound HTTP client call

**Result:** ✅ Correct

**Explanation:** The outbound HTTP client controls its wait for the downstream response. Handle the timeout in the application.

### Q7. We need to diagnose intermittent HTTP 503 responses during an employee-api deployment. Which evidence would be useful? Select all that apply.

**My selection:** Revision startup and container error logs; Cloud Run request logs filtered to the affected time period; Cloud Run instance count and scaling metrics

**Correct answer:** Revision startup and container error logs; Cloud Run request logs filtered to the affected time period; Cloud Run instance count and scaling metrics

**Result:** ✅ Correct

**Explanation:** Correlate request 503s with startup errors, crashes and scaling capacity. A commit message alone cannot establish the runtime cause.

### Q8. Our GitHub Actions workflow uses WIF and can authenticate to Google Cloud, but Docker push returns PERMISSION_DENIED for Artifact Registry. What is the most targeted next check?

**My selection:** Check github-deploy-sa's writer permission on the target Artifact Registry repository

**Correct answer:** Check github-deploy-sa's writer permission on the target Artifact Registry repository

**Result:** ✅ Correct

**Explanation:** Authentication is separate from repository authorisation; check Artifact Registry Writer on the target repository for the deployment identity.

### Q9. A GitHub Actions job can authenticate successfully through WIF but still receive an IAM permission error when deploying to Cloud Run.

**My selection:** True

**Correct answer:** True

**Result:** ✅ Correct

**Explanation:** Federation establishes identity, while Cloud Run updating and actAs require their own IAM grants.

### Q10. A Cloud Run request has a 60-second timeout. A client disconnects after 10 seconds, but application work continues and commits at 25 seconds. What does this illustrate?

**My selection:** An absent client response does not prove server-side work was cancelled

**Correct answer:** An absent client response does not prove server-side work was cancelled

**Result:** ✅ Correct

**Explanation:** A disconnected client may not receive a response even while server-side processing continues and commits. Retried requests need idempotency.

### Q11. We plan to automate Cloud Run candidate promotion after a smoke test. Which safeguards should the workflow include? Select all that apply.

**My selection:** Fail the workflow when the smoke test returns an unexpected status or body; Verify the candidate's exact revision before promotion; Use an authorised identity to call the private candidate URL

**Correct answer:** Fail the workflow when the smoke test returns an unexpected status or body; Verify the candidate's exact revision before promotion; Use an authorised identity to call the private candidate URL

**Result:** ✅ Correct

**Explanation:** Use valid private-service authentication, require expected status/body, and promote only the exact revision tested.

### Q12. Our tested candidate has 0% traffic. Before promotion another deployment creates a newer revision. What is the safest way to avoid promoting the wrong version?

**My selection:** Assume the candidate tag permanently identifies the original revision

**Correct answer:** Use the exact tested revision name when updating traffic

**Result:** ❌ Incorrect

**Explanation:** Pin traffic to the exact revision verified in the smoke test, rather than a moving reference like “latest” or a reassignable tag.

**Why my selection was incomplete/incorrect:** A candidate tag can be moved to another revision, so assuming it permanently identifies the original is unsafe.

### Q13. A smoke test succeeds on one revision, but production users later receive errors on another revision. The service has a 70%/30% traffic split. What should we verify first?

**My selection:** That the production service URL routes requests according to the configured split

**Correct answer:** That the production service URL routes requests according to the configured split

**Result:** ✅ Correct

**Explanation:** The tagged URL tests one revision, while the normal service URL follows the 70/30 split and may send traffic to a different revision.

### Q14. An MES transaction uses shared Redis state. Revision A writes a new field that revision B does not understand, and both revisions receive traffic. What is the safest general rollout principle?

**My selection:** Use compatible schema changes or prevent cross-version transaction processing

**Correct answer:** Use compatible schema changes or prevent cross-version transaction processing

**Result:** ✅ Correct

**Explanation:** Shared storage does not ensure data-format compatibility. Use backward-compatible schemas or version-aware routing.

### Q15. Our Cloud Run revision reports 12 errors among 800 HTTP requests during a monitoring interval. What is the observed error rate?

**My selection:** 1.5%

**Correct answer:** 1.5%

**Result:** ✅ Correct

**Explanation:** Error rate = (12 / 800) × 100 = 1.5%.

## Quick recall — concepts I want to retain

- **FastAPI validation:** missing required Pydantic request fields normally produce HTTP 422; HTTP 401 concerns authentication.
- **Cloud Run network binding:** bind the HTTP server to `0.0.0.0` on the configured `PORT` (8080 in my service), not only `127.0.0.1`.
- **Docker build context:** include application source, exclude local `.venv`, pytest cache and local secret `.env` files.
- **IAM chain:** GitHub WIF authenticates the deployer; Artifact Registry Writer pushes; Cloud Run Developer updates the service; Service Account User permits attaching the runtime service account; the runtime identity has narrowly scoped secret access.
- **Retries:** distinguish attempt count from wait count; for base `b` and multiplier `m`, the first `n` waits total `b × (mⁿ − 1) / (m − 1)` when there is no cap or jitter. Check each wait before adding.
- **Process-local locks:** `asyncio.Lock` and `SemaphoreSlim` protect participants sharing that object within a process. Separate Cloud Run instances require Redis, database transactions or other shared coordination.
- **Distributed leases:** TTL must account for work duration and expiry races; use idempotency and fencing/renewal where needed.
- **Safe rollout:** deploy a candidate with 0% normal traffic; use a tagged URL for authenticated smoke testing; promote only the exact revision that passed; retain an explicit rollback target.
- **MES Trigger/Echo risk:** a split rollout can send linked messages to different revisions. Shared state and version compatibility are essential; a 100% switch can still separate in-flight transactions.
- **Monitoring:** inspect latency distributions, 5xx, logs, startup events, scaling and downstream dependencies together.

## Evidence note

The questions, correct answers and explanations are based on the four quiz sets in my learning record. The saved quiz answer snapshots provide individual selections for Rounds 1, 2 and 4. Round 3 has its original quiz questions and a previously reported aggregate score only; no selection details were inferred. Explanations are concise faithful restatements of the feedback shown in the quizzes, rather than exhaustive copies of every option's feedback.