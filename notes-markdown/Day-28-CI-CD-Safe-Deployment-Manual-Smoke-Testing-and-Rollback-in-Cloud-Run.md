# Day 28 — My safe deployment, smoke testing and rollback notes

**Learning date: 31 October 2026**  
**Companion workbook: Day-28-Screenshots.xlsx**

## 1. What I completed

I changed my Employee API deployment so that GitHub Actions could deploy a new Cloud Run revision without immediately sending normal users to it. I tested the new revision through its `candidate` URL with an authenticated request, manually promoted it, then practised returning all normal traffic to the previous working revision.

My final verified routing was `employee-api-00026-djg` at **100%** and `employee-api-00030-pen` at **0%**, with the `candidate` tag still attached to `00030-pen`. This was a completed manual safe-deployment exercise. Automated candidate smoke testing and controlled promotion in GitHub Actions were **not implemented**.

I need to keep five kinds of information separate throughout these notes:

| Label | What it means in my record |
|---|---|
| Observed | Shown in my original screenshots or confirmed during the exercise |
| Saved configuration | A change I applied and then verified through its result |
| Proposed | An idea or next step that was discussed but not necessarily applied |
| Teaching example | A hypothetical scenario used to understand behaviour |
| Inherited setting | A value already present in the revision, not a new Day 28 choice |

My learning progression was Day 26: tests, Docker build and Artifact Registry publishing; Day 27: automated Cloud Run deployment; Day 28: deploy, smoke-test, then promote or roll back. A green deployment is useful, but it does not by itself prove that the deployed API responds correctly to an authorised caller.

The original time budget was approximately 60 minutes: 10 minutes understanding deployment versus release, 15 configuring 0% traffic, 15 smoke testing, 15 releasing and practising rollback, and 5 reviewing/committing. These were planned durations, not a measured record of how long I actually spent.

## 2. My starting state

I opened Google Cloud Console → Cloud Run → `employee-api` → **Revision History** before changing traffic. The initial plan referred to the last verified Day 27 revision, `00025-2kp`, at 100%. My new screenshot corrected that assumption: `00026-djg` had appeared and was already serving 100%. I therefore used `00026-djg` as the working revision for this exercise.

| Field | My actual starting value | Meaning |
|---|---|---|
| Project | `cloud-genai-learning` | The Google Cloud project containing the service and registry resources |
| Region | `europe-west2` | The region of my Cloud Run service and image repository |
| Service | `employee-api` | The stable service containing multiple revisions |
| Current working revision | `employee-api-00026-djg`, 100% | The revision receiving normal requests at the start |
| Previous Day 27 revision | `employee-api-00025-2kp`, 0% | An older deployment retained in revision history |
| Authentication | Required | Knowing a service or tag URL does not grant permission to invoke it |
| Runtime identity previously recorded | `employee-api-sa` | The application's service identity, distinct from the deployment identity |
| Deployment identity visible | `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com` | The identity that deployed the revision using `gcloud` |

The deployment identity performs deployment work. The runtime identity is used by the running application for its own access to resources. My Google account used for the later smoke test was another identity again. I should not treat these as interchangeable merely because all are involved in one workflow.

Screenshot **S01** records the actual starting state. The older assumption about `00025-2kp` is historical context, not the rollback target I ultimately chose.

### Runtime settings visible in my screenshots

These values were inherited/observed. I did not retune them during Day 28, and the discussion did not establish a new Day 28 reason for choosing each value.

| Visible field | Observed value | My beginner interpretation and practical effect |
|---|---|---|
| Billing | Request-based | Billing mode associated with handling requests; changing traffic was not a billing-mode change |
| Startup CPU boost | Enabled | Extra startup CPU can help a container start; it does not determine traffic allocation |
| Concurrency | 1 | At most one concurrent request per instance under this setting; it does not mean the service has only one instance |
| Request timeout | 300 seconds | A request has a configured response-time limit of five minutes; this is not a guaranteed transaction lifetime |
| Execution environment | Default | The default execution environment was selected |
| Revision max instances | 3 | The revision can scale across multiple instances up to this setting; instance-local transaction state is therefore unsafe as a shared record |
| Autoscaling factors | Default autoscaling factors | No custom factors were shown or changed |
| Image | Artifact Registry image link | The container image deployed to the revision; the console truncates the full link, while the workflow/log provides its path |
| Port | 8080 | The container's request listening port |
| Build / Source | No build information / no source information available | These console metadata fields were empty; GitHub still supplied build/deployment evidence separately |
| Command and args | Container entrypoint | Startup used the image's entrypoint rather than a displayed override |
| CPU limit | 1 | One configured CPU unit; not a count of revisions |
| Memory limit | 512 MiB | Memory available to each container instance under this configuration |
| Sandbox launcher Preview | Disabled | Visible on the starting revision; not changed during the exercise |
| Environment variables | Section labelled `(3)` | Three variables were indicated, but their names and values were below the captured area. I cannot infer them from this image |

I can convert the visible timeout: `300 seconds ÷ 60 seconds/minute = 5 minutes`. This conversion explains the setting; it was not a timed test. Concurrency 1 and max instances 3 describe different limits. They do not guarantee that a later Echo request reaches the same instance as its Trigger.

## 3. My deployment configuration

I edited the existing file in VS Code:

```text
C:\Raja\Learning\python\new learning\.github\workflows\ci.yml
```

I changed only the existing **Deploy to Cloud Run** step. I first saved the edit and reviewed the YAML indentation before triggering a deployment. Screenshot **S02**, especially lines 68–75, shows the reviewed configuration:

```yaml
- name: Deploy to Cloud Run
  uses: google-github-actions/deploy-cloudrun@v3
  with:
    service: employee-api
    region: europe-west2
    image: europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
    no_traffic: true
    tag: candidate
```

| Field | Chosen value | Why I used it and what it affects |
|---|---|---|
| `name` | `Deploy to Cloud Run` | A readable step label in Actions logs |
| `uses` | `google-github-actions/deploy-cloudrun@v3` | The deployment action already used in my workflow |
| `with` | Input mapping | Groups the deployment action's settings; indentation determines YAML structure |
| `service` | `employee-api` | Deploys to my existing service rather than creating a separately named test service |
| `region` | `europe-west2` | Targets the region where my service exists |
| `image` | Registry path ending in `${{ github.sha }}` | Uses the image associated with the workflow commit; build, tag, push and deployment must refer to the same image |
| `no_traffic` | `true` | Keeps normal service traffic on the existing working revision when deploying the new revision |
| `tag` | `candidate` | Gives the new revision a named direct URL for testing |

The registry path has distinct parts: `europe-west2-docker.pkg.dev` is the registry hostname, `cloud-genai-learning` is the project, the first `employee-api` is the repository and the second is the image name. The colon introduces the Docker image tag. `${{ github.sha }}` is a GitHub Actions expression, not something I type literally as a PowerShell variable.

I must distinguish a **Docker image tag**, such as the commit SHA, from a **Cloud Run revision tag**, such as `candidate`. The image tag identifies an image in the registry. The revision tag supplies a named request route to a Cloud Run revision. They are different settings on different objects.

`no_traffic: true` and `tag: candidate` do separate jobs. The first withholds normal traffic; the second supplies an entry point for a deliberate test request. Neither makes a private service public. The new revision still needs an authorised caller.

My Day 27 deployment step did not contain these two new inputs and sent normal traffic to the new deployment. On Day 28, I separated **deploying** the version from **releasing** it to users.

## 4. My commit and pipeline

After the configuration review, I used my existing VS Code PowerShell terminal in the repository root. Git, the existing repository/remote, permission to push and the already configured GitHub workflow were prerequisites.

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 28 - Deploy candidate revision without traffic"
git push origin main
```

`git add` stages the workflow change. `git commit` records it locally. `git push origin main` publishes the commit to the remote main branch, which triggers the workflow. The commands above were the exercise instructions; **S03** specifically shows the successful push output. It does not show the preceding add/commit terminal output.

The push went to `https://github.com/Rajadurai0606/cloud-genai-learning.git` and advanced main from `f17ddf4` to **`421373c`**. Employee API CI run **#11** first appeared in progress (**S04**) and then succeeded (**S05–S06**). I should not mistake the earlier yellow status for a failed run.

The run summary showed total duration **1m 46s** and the `test` job **1m 43s**. In seconds these are `60 + 46 = 106 s` and `60 + 43 = 103 s`; their difference is `106 − 103 = 3 s`. These displayed durations describe different scopes and do not establish the exact source of the three-second difference.

Screenshot **S07** shows the successful sequence: set up job, checkout, set up Python, install dependencies, run pytest, build Docker image, authenticate to Google Cloud, set up the Cloud CLI, verify authentication, configure Docker authentication, tag image, push image, deploy to Cloud Run, post-action cleanup and complete job. The job is called `test`, but it includes more than unit testing. I have success evidence for the stages, not an original screenshot giving the number of pytest tests or their individual output.

The YAML screenshot also shows the existing image tag/push commands:

```bash
docker tag employee-api:ci europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
```

These run on the Actions runner after the image has been built and registry authentication configured. The first adds the registry-qualified name to the local image; the second uploads it. They were existing pipeline stages visible in the screenshot, not separate commands I newly executed in Cloud Shell.

### What the deployment log proves

Screenshot **S08** shows successful authentication followed by the action-generated command. For readability I have line-wrapped it below; the original log is embedded unchanged in Excel.

```bash
gcloud run deploy employee-api \
  --image europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:421373ce50e4b91284a38030092b9792b05f3193 \
  --tag candidate \
  --no-traffic \
  --update-labels ^,^managed-by=github-actions,commit-sha=421373ce50e4b91284a38030092b9792b05f3193 \
  --format json \
  --region europe-west2
```

The action translated my YAML inputs into `--tag candidate` and `--no-traffic`. `--image` names the pushed image, `--region` identifies the deployment location, `--format json` selects machine-readable output and the management/commit labels record provenance. The `^,^` prefix is the delimiter syntax visible in the generated labels argument. This was an observed **runner-generated command**, not a manual deployment I repeated.

The result (**S09**) was `00030-pen` at 0% with `candidate`, while `00026-djg` stayed at 100%. Both **Updating service** and **Routing traffic** reported Completed. This was the evidence that deployment had not replaced the working normal route.

### Warnings and notices I retained

The successful run had one warning and one notice (**S06**). The warning said Node.js 20 was deprecated and that `actions/checkout@v4` and `actions/setup-python@v5`, which target Node.js 20, were being forced to run on Node.js 24. The notice concerned the `ubuntu-latest` label migrating to Ubuntu 26 beginning 19 October 2026. These were runner/action maintenance messages, not an observed Employee API failure. I did not fix or upgrade those actions as part of this exercise, and I should not claim the warnings were resolved.

## 5. Revisions, tags and 0% access

### My question: what does candidate mean, and why are we creating revisions only now?

I initially confused the new tag with the revision itself. Cloud Run had already been creating revisions in earlier deployments. A revision is a deployed application version with its image and revision configuration. Names such as `employee-api-00025-2kp`, `employee-api-00026-djg` and `employee-api-00030-pen` identify different revisions. A deployment that changes revision configuration creates a new revision.

`candidate` is a user-defined **revision tag**. It is not a special Google keyword and does not create the revision. I could have chosen another suitable name such as `testing`, `staging` or `preview`. In my exercise, the tag means I want to test this new version before routing normal users to it.

The MES station analogy helped me: deploying is like installing the new software, smoke testing checks startup/basic communication, promoting allows production requests to use it, and rollback redirects requests to the earlier working version. The analogy has a limit: my candidate was not a separate physical server or an isolated testing environment. Both revisions belonged to the **same Cloud Run service**. A tag also does not create a separate database or isolate side effects.

### My question: can I directly test an untagged revision at 0%?

My teaching example imagined a new revision **`00031-raja`** with no tag. I manually moved normal traffic back to a hypothetical previous revision `00030-pen` at 100%, leaving `00031-raja` at 0%.

| Teaching-example revision | Normal traffic | Tag | What I can reach |
|---|---:|---|---|
| Hypothetical previous `00030-pen` | 100% | None | Normal service URL routes here |
| Hypothetical new `00031-raja` | 0% | None | No dedicated tagged Cloud Run HTTP URL for this revision |
| Same `00031-raja`, after adding tag | 0% | `candidate` | Tagged URL can directly test it, subject to authentication |

Without the tag, normal requests do not reach `00031-raja` at 0%, and I do not have the ordinary dedicated revision-tag URL to select it directly. I can add a tag later without rebuilding the Docker image or creating a new application revision just to assign the tag. The tag supplies routing; permission is still checked separately.

I must not mix that example with the actual Day 28 state. **`00031-raja` was hypothetical. My actual working revision was `00026-djg`, and my actual candidate was `00030-pen`.**

I can picture the normal URL as the plant's main entrance and the tag URL as an engineering test entrance. The main entrance follows the service's traffic allocation. The test entrance selects the tagged revision, even at 0% normal traffic.

| Address or token field | My value / role |
|---|---|
| Normal service URL | `https://employee-api-972261256506.europe-west2.run.app` |
| Candidate request URL | `https://candidate---employee-api-26u42lscua-nw.a.run.app/` |
| Revision tag | `candidate`, attached to `00030-pen` |
| ID-token audience for later service-account automation | Normally the accepted main Cloud Run service URL, even when the HTTP request targets a tag URL; the request destination and audience must not be blindly treated as identical |

The URLs have different hostname formats. I should use the actual URL provided by Cloud Run rather than inventing a hostname from the revision name. Audience is the service identity the ID token is intended for, whereas the request URL controls where the HTTP call is sent. The manual Google-account test below used the developer identity-token command; a future service-account implementation needs its audience configured deliberately.

## 6. My authenticated smoke test

I found `00030-pen` in Revision History and clicked the blue `candidate` link (**S10**). Normal traffic was still 100% on `00026-djg`. Opening the candidate URL in an ordinary browser returned **403 Forbidden** (**S11**): the client did not have permission to get `/`.

A healthy deployment and an authorised request are separate checks. A browser being signed into Google Cloud Console does not mean that opening an API URL automatically supplies an accepted bearer token. I did not solve this by making the private service public or changing its IAM permissions.

I opened the terminal icon in Google Cloud Console to use **Cloud Shell**. My active Google account needed permission to invoke the service (`run.routes.invoke`). Cloud Shell had the `gcloud` CLI and `curl` available. I ran:

```bash
TOKEN=$(gcloud auth print-identity-token)

curl -i \
  -H "Authorization: Bearer $TOKEN" \
  "https://candidate---employee-api-26u42lscua-nw.a.run.app/"
```

The first command obtains a temporary identity token for the active account and stores it in a shell variable. `-H` adds the Authorization header. `Bearer $TOKEN` supplies the identity token to Cloud Run. `-i` includes the HTTP response status and headers so that I can inspect them alongside the body. The tagged hostname selects the candidate revision even though its normal traffic percentage is 0%. I do not need to publish the token in my notes.

I used `/` as the initial route. If the application had no root GET route, a known valid GET endpoint would be needed. That fallback was discussed; the actual root test succeeded, so no alternative route was needed.

| Status discussed | My interpretation |
|---|---|
| 200 | The authenticated request succeeded and the endpoint returned a successful response |
| 403 | Invocation permission or accepted authentication is missing; investigate identity/token/permission before blaming application logic |
| 404 | The requested application route might not exist; this status alone is not a complete authentication diagnosis |
| 500 | Server-side processing failed; inspect the application and its logs |

Screenshot **S12** shows **HTTP/2 200**, `content-type: application/json`, and the response:

```json
{
  "message": "Employee API",
  "version": "3.0",
  "environment": "staging",
  "api_key_configured": true
}
```

This confirmed that I could invoke the candidate while the working revision continued handling normal traffic. The response header recorded 31 October 2026 at **09:28:03 GMT**, and content-length was 92. The API key flag showed that the application detected its configuration. It did **not** independently prove that every Secret Manager operation, every endpoint or a complete MES transaction would work.

My smoke test was a small, quick confidence check, not an exhaustive integration or production-load test. The exact JSON fields were more useful than checking only that a deployment command returned success.

## 7. My MES canary decision

After the smoke test, the proposed next step was a **90% / 10% canary**: `00026-djg` at 90% and `00030-pen` at 10%. A canary introduces a small share of normal requests to a new version before a wider release. It can be useful for an independent, stateless API request.

I questioned whether that would mix a real production MES transaction: **Station Trigger goes to `00026-djg`, then Station Echo goes to `00030-pen`. Wouldn't 100% on one version be safer?**

Cloud Run traffic splitting operates at the HTTP-request level. It does not automatically understand that Trigger and Echo belong to one manufacturing transaction.

| Teaching sequence for TX100 | Revision / state | Possible consequence |
|---|---|---|
| Station Trigger starts TX100 | Old `00026-djg` stores pending state in its local memory | Only that instance knows the transaction |
| Later Station Echo for TX100 | New `00030-pen` receives the next request | It may not find the pending transaction |
| Both revisions individually appear healthy | Each can answer a basic request | The overall manufacturing transaction can still fail |

This risk also exists at 100% on one revision if Cloud Run uses multiple instances. Instance A's memory is not automatically instance B's memory. Concurrency 1 does not provide a permanent station-to-instance relationship.

My MES/PDT discussion had already considered Redis for pending requests and transaction state. Shared Redis or SQL can allow another instance/version to read TX100, but **shared storage alone is insufficient**. Old and new versions must agree on data format, lifecycle and processing rules. If one version writes a Redis structure the other cannot understand, mixing versions can still break the transaction.

| Application design | What I learned about traffic splitting |
|---|---|
| Stateless REST request, independent of previous requests | Generally suitable for a canary |
| Shared SQL/Redis state with compatible versions | Potentially suitable after validation |
| Trigger state held only in local memory, Echo expected on same instance | Unsafe without additional design |
| Trigger/Echo must stay on the same software version | Needs version-aware routing or another rollout strategy |

Session affinity attempts to keep a client's requests on one instance, but it is best effort. I should not depend on it as a critical transaction-consistency guarantee.

Even a direct 0% → 100% switch can cross an in-progress transaction:

| Teaching time | Event |
|---|---|
| 10:00:00 | Trigger TX100 reaches the old revision |
| 10:00:01 | I switch 100% normal traffic to the new revision |
| 10:00:02 | Echo TX100 reaches the new revision |

The two-second teaching example explains why a real MES rollout may need transaction draining, compatible shared state, or routing that allows existing transactions to finish on their original version. A 100% switch avoids intentionally maintaining a mixed-version percentage, but it does not automatically solve state or cutover boundaries.

For my simple Employee API, the original canary proposal was reasonable as a learning exercise. After considering the MES issue, I chose **manual 100% promotion followed by rollback** instead. I inspected the split option for documentation but did not save a 90/10 split.

### Calculations I can use to recall percentages

These are explanatory calculations, not measured request counts. For a teaching input of **1,000 normal HTTP requests**, `requests × percentage ÷ 100` gives `1,000 × 90 ÷ 100 = 900 requests` to the old revision and `1,000 × 10 ÷ 100 = 100 requests` to the candidate in an expected 90/10 distribution. `900 + 100 = 1,000`, and `90% + 10% = 100%`. Real routing is not a promise that every block of 1,000 has those exact counts, nor that related requests stay together.

For the actual pre-promotion allocation, the same illustrative input gives `1,000 × 100 ÷ 100 = 1,000` old-revision normal requests and `1,000 × 0 ÷ 100 = 0` candidate normal requests. Deliberate tagged test requests are separate from this normal-URL percentage illustration.

Screenshot **S13** shows the action menu. **S14** shows the split dialog with old revision **100%** and candidate **0%**. It is important that I do not label that original image as an applied 90/10 canary.

## 8. My promotion

Promoting means changing routing so that the tested candidate receives normal service requests. I did not rebuild the Docker image or create a new application revision merely to change the traffic percentages.

I opened **Manage traffic**, selected **Send all traffic to the latest revision**, and clicked **Save**. At that moment the latest deployed revision was `00030-pen` (**S15**). The saved result (**S16**) showed `00030-pen` at **100% (to latest)** and `00026-djg` at 0%. Updating service and routing traffic completed. The `candidate` tag remained attached.

| Option in Manage traffic | Meaning for my exercise |
|---|---|
| Send all traffic to the latest revision | Follow the newest revision; it selected `00030-pen` at that time and represents latest-following routing |
| Send all traffic to one revision | Explicitly select a fixed revision to receive 100% |
| Split traffic across multiple revisions | Choose revision dropdowns and percentage fields for a distribution |

The latest option worked for this promotion because the revision I wanted happened to be latest. For controlled promotion and rollback, explicitly choosing **one revision** makes the intended target clearer. A future deployment can interact with a latest-following route; the workflow's no-traffic behaviour and explicit routing should be checked together rather than assuming that selecting a row pins it.

The split dialog also exposed **Revision 1 / Revision 2**, **Traffic 1 / Traffic 2**, **Add revision**, **Cancel** and **Save**. The revision dropdown names the target; its percentage sets the normal traffic share; the shares must total 100%. Cancel abandons the dialog edit, whereas Save applies the chosen routing. A configuration screenshot before Save is not proof of the saved result.

Changing traffic did not remove the service's authentication requirement. A tag and a percentage are independent: my candidate could have a tag at either 0% or 100%.

## 9. My rollback and correction

I selected `employee-api-00026-djg`, opened its three-dot menu, chose Manage traffic, then mistakenly chose **Send all traffic to the latest revision** and saved. I asked why the selected old revision had not become 100%.

The issue was the meaning of **latest**, not the row selection or an unexplained delay. Latest still meant `00030-pen`, the newest deployment. Selecting the `00026-djg` row did not redefine latest. Screenshot **S17** shows the selected old revision still at 0%, with `00030-pen` still at 100% (to latest).

I corrected the rollback as follows:

1. Open **Manage traffic** again.
2. Choose **Send all traffic to one revision**, the second option.
3. Explicitly select **`employee-api-00026-djg`** in the revision dropdown.
4. Click **Save**.
5. Check both the completion indicators and the resulting percentages in Revision History.

Screenshot **S18** is the corrected configuration before Save. Its background still shows the pre-save percentages, which is expected for that stage. Screenshot **S19** is the confirmation after Save: updating service and routing traffic completed, `00026-djg` is at 100%, and `00030-pen` is at 0% with the `candidate` tag.

| Stage | `00026-djg` normal traffic | `00030-pen` normal traffic | What actually happened |
|---|---:|---:|---|
| Start / candidate deployed | 100% | 0% | Working route preserved |
| Candidate smoke test | 100% | 0% | A tagged authenticated request tested the candidate |
| Canary proposal | 90% proposed | 10% proposed | Considered, not applied |
| Split dialog screenshot | 100% displayed | 0% displayed | Inspected for documentation |
| Promotion saved | 0% | 100% to latest | Candidate received normal traffic |
| Mistaken rollback saved | 0% | 100% to latest | Latest option kept normal traffic on candidate |
| Corrected rollback saved | 100% explicit revision | 0% | Final verified Day 28 state |

Rollback changed only traffic routing. It did not rebuild an image, delete the candidate or create another application revision. The candidate's tag remained, so it was still directly testable with accepted authentication. Routing rollback should not be confused with undoing database writes or other side effects; no data rollback was performed in this exercise.

## 10. Final state and work deliberately left for later

I completed candidate deployment at 0%, revision/tag understanding, private-service authentication, a successful candidate smoke test, manual promotion, MES canary-risk discussion, corrected rollback and final routing verification.

I retained the candidate revision and its tag. No candidate deletion or tag cleanup was performed. I retained the original screenshots and the runner warning/notice for documentation. I did not change authentication to public access.

The future improvement was to add authenticated smoke testing and controlled promotion to GitHub Actions, proposed as a Day 29 exercise. The existing workflow deploys at 0% but does not automatically decide that the candidate is safe or promote it. A future implementation needs the correct invoking identity, permission and token audience, a meaningful expected status/body check, and an explicit promotion decision. These are deferred requirements, not code that I already saved.

I have not silently filled in settings outside my screenshots. Full environment variable values, secret contents, the complete CI file and individual pytest output were not visible in the Day 28 images. My notes preserve what was discussed and what the original evidence actually shows.

## 11. My quick recall guide

| If I forget… | My recall answer | Original evidence |
|---|---|---|
| Deploy versus release | Deploy creates the version; release changes which version normal users reach | S02, S09, S16 |
| Revision versus candidate | Revision is the deployed version; candidate is my chosen revision tag | S09–S10 |
| 0% means inaccessible? | 0% excludes normal allocation, but a tagged authenticated test can still invoke it | S10–S12 |
| Untagged `00031-raja` | Hypothetical 0% revision has no dedicated tag URL until I assign a tag | Section 5 teaching example |
| Browser 403 | Check accepted authentication and invoke permission; do not immediately blame the API | S11–S12 |
| Successful smoke test | HTTP 200 plus Employee API / 3.0 / staging / API key configured true | S12 |
| Why not 90/10 for MES? | Trigger and Echo can cross instances/versions; compatible shared state and cutover design matter | S14; section 7 |
| Latest versus one revision | Latest follows newest; one revision pins the explicit dropdown target | S15, S17–S18 |
| Final allocation | Old `00026-djg` 100%, candidate `00030-pen` 0% | S19 |
| Is automation complete? | Deployment is automated; smoke test, promotion and rollback were manual | S07–S08; section 10 |

## 12. Screenshot index

The workbook embeds all 19 original screenshots in workflow order. The following index gives the worksheet, caption row, image start row and matching topic. Images retain their original contents and proportions. I can zoom in within Excel when inspecting small log text.

| ID | Caption | Worksheet / caption row | Image starts | Notes section |
|---|---|---|---|---|
| S01 | Starting revision history: 00026-djg at 100% | Deployment!A5 | Deployment!A8 | 2. My starting state |
| S02 | Reviewed ci.yml with no_traffic and candidate tag | Deployment!A44 | Deployment!A47 | 3. My deployment configuration |
| S03 | Push to main: f17ddf4..421373c | Deployment!A80 | Deployment!A83 | 4. My commit and pipeline |
| S04 | Employee API CI run #11 in progress | Deployment!A102 | Deployment!A105 | 4. My commit and pipeline |
| S05 | Run #11 completes successfully | Deployment!A142 | Deployment!A145 | 4. My commit and pipeline |
| S06 | Run summary, duration and non-blocking annotations | Deployment!A182 | Deployment!A185 | 4. My commit and pipeline |
| S07 | Successful pipeline stages | Deployment!A219 | Deployment!A222 | 4. My commit and pipeline |
| S08 | Expanded deployment command confirms tag and no traffic | Deployment!A258 | Deployment!A261 | 4. My commit and pipeline |
| S09 | Candidate 00030-pen deployed at 0% | Deployment!A297 | Deployment!A300 | 5. Revisions, tags and 0% access |
| S10 | Candidate link with normal traffic still on 00026-djg | Testing!A5 | Testing!A8 | 6. My authenticated smoke test |
| S11 | Ordinary browser request receives 403 Forbidden | Testing!A37 | Testing!A40 | 6. My authenticated smoke test |
| S12 | Cloud Shell returns HTTP/2 200 and expected JSON | Testing!A59 | Testing!A62 | 6. My authenticated smoke test |
| S13 | Open Manage traffic from the candidate row | Traffic!A5 | Traffic!A8 | 7. My MES canary decision |
| S14 | Split option inspected for documentation, showing 100% / 0% | Traffic!A42 | Traffic!A45 | 7. My MES canary decision |
| S15 | Latest-revision option selected for promotion | Traffic!A72 | Traffic!A75 | 8. My promotion |
| S16 | Promotion completes: 00030-pen at 100% to latest | Traffic!A102 | Traffic!A105 | 8. My promotion |
| S17 | Unsuccessful rollback: selected old row still has 0% | Traffic!A141 | Traffic!A144 | 9. My rollback and correction |
| S18 | Correct rollback configuration: one revision, 00026-djg | Traffic!A175 | Traffic!A178 | 9. My rollback and correction |
| S19 | Final verified state: 00026-djg 100%, candidate 0% | Traffic!A204 | Traffic!A207 | 9. My rollback and correction |

## 13. Documentation verification record

The Day 28 material was reviewed from the request for the Day 28 task through the completion/documentation request, including the original attachments. The bounded chat reader exposed only the last five turns; the earlier discussion and attachments were recovered through the original app view rather than replaced by its preview or an older prepared document.

Coverage was checked against the concepts, questions, examples, settings, commands, observed errors, corrections, decisions and all 19 workflow screenshots. Additional arithmetic in section 7 is explicitly labelled explanatory. No screenshot was substituted with a recreated mockup. The workbook's embedded media, drawing anchors, captions and cross-references were checked after export.

Library saving is recorded separately at delivery according to the capabilities available. A local saved file is not, by itself, proof of a Library save.
