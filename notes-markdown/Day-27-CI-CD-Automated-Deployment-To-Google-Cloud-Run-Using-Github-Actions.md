# Day 27 — CI/CD: Automated Cloud Run Deployment with GitHub Actions

## 1. My goal and what I completed

I extended my existing employee-api pipeline so that a GitHub push now tests my Python application, builds its Docker image, authenticates to Google Cloud through Workload Identity Federation (WIF), pushes the image to Artifact Registry, and deploys that same image to my existing Cloud Run service.

My learning session took place on 28 October 2026. These notes were prepared on 29 October 2026. I reviewed the original Day 27 material from “yes lets start” through the final verification and documentation requests. My companion workbook contains 26 recovered original screenshots, with their contents preserved and indexed in workflow order. Screenshot IDs such as **S14** refer to the workbook's Index and Screenshots sheets.

I distinguish the following evidence states throughout my notes:

- **Observed:** visible in my original screenshots or an explicit result I provided.
- **Saved:** a completed change supported by a saved policy or later successful deployment.
- **Teaching example:** an explanation or command illustrating a possibility, not a result I obtained.
- **Proposed/deferred:** a suggested check or improvement that I did not complete.

| Item | My observed result |
|---|---|
| Project | `cloud-genai-learning` |
| Cloud Run service | `employee-api` |
| Region | `europe-west2` — London |
| Deployment identity | `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com` |
| Runtime identity | `employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com` |
| Commit | `7ae978d856d4a35799170e2eeb00439b3368cbc0` (short form `7ae978d`) |
| GitHub Actions run | Employee API CI, run **#9** |
| New revision | `employee-api-00025-2kp` |
| Traffic | **100% to the latest revision** |
| Deployment duration | **25 seconds** |
| Successful job duration | **1 minute 37 seconds** |
| Final security | Require authentication, IAM enabled, `employee-api-sa` selected |

The screenshots establish deployment and configuration success. I did not record a separate HTTP request/response test or a rollback exercise on Day 27. I should not describe either as completed.

## 2. My starting point: inspect before changing

Day 26 had already established my CI and image-publishing stages. Day 27 added deployment. I kept the same existing service and checked its image, resources, environment, secret reference, authentication and service identity first. This helped me avoid accidentally targeting another service or replacing unrelated settings.

**S01–S04** show the initial container-image selector, Security tab, service-account list and Permissions tab. **S10** shows the existing container configuration. Selecting an image from Artifact Registry is only part of preparing a Cloud Run revision; storing an image in the registry does not start the application.

My planned sequence was: inspect → grant narrowly scoped deployment permissions → add the deployment step → review YAML → commit and push → inspect Actions → verify the actual revision and traffic → verify preserved configuration and security. Rollback was mentioned as an objective if required, but it was not needed or performed.

## 3. Three identities, and what actually runs my application

| Identity/component | My understanding |
|---|---|
| `github-deploy-sa` — Robot A | The deployment identity used by GitHub Actions to publish and deploy |
| `employee-api-sa` — Robot B | The identity associated with my running employee-api revision, used for authorised Google Cloud access |
| `order-api-sa` | An identity for a different application/service-to-service exercise; not involved in this deployment |
| Cloud Run | The infrastructure that starts and manages my container and executes my application |
| Docker image | My application code and dependencies packaged for execution |
| Cloud Run revision | An immutable deployed configuration containing the image reference and settings such as port, memory, variables, secret references and service identity |

### My question: “Why did we create employee-api-sa? Is it to run employee-api?”

I initially used “run” too loosely. My corrected understanding is that **Cloud Run executes Python; the service account supplies identity and authorisation**. Creating a service account alone does not grant it access to resources.

I can check my selected identity at **Cloud Run → Services → employee-api → Security → Service Account**. For a particular revision I can inspect its YAML and locate `serviceAccountName`. The teaching fragment was:

```yaml
spec:
  serviceAccountName: employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com
```

This is a field illustration, not a complete deployable service manifest; nesting depends on the resource representation.

### My question: “If there is no secret or Google API dependency, is employee-api-sa unnecessary?”

I do not need to create a **custom** account merely to execute a simple Python application. Cloud Run still associates a service identity with the service; if I do not choose a custom identity, the default Compute Engine service account is normally used. In my project that identity was `972261256506-compute@developer.gserviceaccount.com`, and the screenshots showed project-level Editor access.

The distinction is therefore “no custom identity needed just for Python execution,” not “no identity exists.” Keeping my dedicated, restricted account remains useful even if a particular secret is later removed.

My teaching example was:

```python
@app.get("/hello")
def hello():
    return {"message": "Hello from Cloud Run"}
```

This example does not access protected Google resources. It was not a Day 27 application change or an observed endpoint test.

### My actual secret-access chain

```text
Cloud Run employee-api
  → runtime identity employee-api-sa
  → Secret Manager Secret Accessor on EMPLOYEE_API_KEY
  → secret version 1 resolved into environment variable API_KEY
```

Being in the same project does not automatically authorise service-to-resource access. My secret still needs an IAM grant. For a secret exposed as an environment variable, Cloud Run resolves the secret using the runtime identity's permissions; my application does not have to fetch it itself with a client library. If that identity cannot read the configured secret, instance startup can fail.

A different teaching scenario was an application making Google API calls directly. A Google client library can obtain temporary credentials from the Cloud Run metadata service under the runtime identity. I do not need to put a service-account private key inside the Docker image for that pattern.

## 4. The two directions of service-account IAM

My questions were: “What can the robot access?” and “Who can access the robot?” These are different investigations because a service account is both a **principal** and a **resource**.

| My question | Direction | Where I look | What it can establish |
|---|---|---|---|
| What can employee-api-sa access? | Outgoing | Project IAM and each resource's Permissions; Policy Analyzer | Roles granted to that identity within the inspected scope |
| Who can access employee-api-sa? | Incoming | IAM & Admin → Service Accounts → employee-api-sa → Principals with access | Other principals' grants on the service-account resource |

**S05–S06** show incoming access by principal and by role. My Google account had inherited Owner and the default Compute Engine account had inherited Editor. Those are other principals' roles on/above this resource; they are not roles assigned to employee-api-sa itself.

### My confusion: “Seems we haven't configured anything?”

I was looking at incoming access while trying to discover outgoing permissions. A screen without a direct deployer grant did not prove my runtime account had no secret access.

**S07** shows project IAM with the default Compute Engine Editor and my Owner account. No direct project-level role for employee-api-sa was visible. **S08–S09** then locate `EMPLOYEE_API_KEY` and show employee-api-sa's direct Secret Manager Secret Accessor grant.

My careful conclusion is: **I verified access to this secret and no direct project grant was visible. I did not prove the absence of all other grants anywhere.** Parent folder/organisation inheritance, other resource policies and effective restrictions require a broader review.

For a broader allow-policy investigation, the proposed Policy Analyzer custom query used scope `cloud-genai-learning`, principal `employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com`, and initially the role Secret Manager Secret Accessor. A role filter narrows the answer; it cannot discover unrelated roles. Leaving role/resource selectors broad, if the interface allows, is a wider query. Allow-policy findings can still be constrained by deny policies or other effective restrictions. No completed Analyzer result was recorded.

### My factory/key analogy

I create the robot, avoid giving it a master key to the entire factory/project, and give it a key to one room: `EMPLOYEE_API_KEY`. Incoming IAM asks who may manage/use that robot. Outgoing IAM asks which rooms the robot may enter. These two lists should not be confused.

## 5. Attaching an identity versus impersonating it

I asked whether my Google account and the default Compute Engine account could log in and impersonate employee-api-sa. Their visible Owner/Editor grants did not establish the specific token-generation permission. I needed to distinguish:

| Role / key permission | What it controls | My Day 27 status |
|---|---|---|
| Service Account User — `iam.serviceAccounts.actAs` | Attaching a service account as a supported resource's runtime identity | Granted to github-deploy-sa on employee-api-sa |
| Service Account Token Creator — `iam.serviceAccounts.getAccessToken` | Generating temporary access tokens as a service account | Explained; not granted to my Google or default Compute Engine account in this exercise |

Service Account User does not by itself provide access-token generation through `--impersonate-service-account`. It also does not directly grant the deployment identity Secret Manager access. However, I should treat permission to deploy code under an authorised identity as consequential: deployed code can exercise that runtime identity's permissions.

### Commands I discussed, but did not record executing

The following were **teaching/proposed checks**, not successful results. For local PowerShell I need Google Cloud CLI installed and an appropriately authorised signed-in account:

```powershell
gcloud auth login
gcloud auth print-access-token --impersonate-service-account=employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com
```

The second command requests a temporary token. Success requires `iam.serviceAccounts.getAccessToken`; lack of permission can produce `PERMISSION_DENIED`. It prints the token, so it was not the preferred evidence to share.

A secret-access illustration combined caller impersonation rights and the target account's secret permission:

```powershell
gcloud secrets versions access 1 `
  --secret=EMPLOYEE_API_KEY `
  --project=cloud-genai-learning `
  --impersonate-service-account=employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com
```

I was explicitly told not to run that illustration because it would display the secret. No secret value is needed in my learning record.

For Cloud Shell (Bash), the proposed test suppressed token output:

```bash
gcloud auth list
gcloud auth print-access-token \
  --impersonate-service-account=employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com \
  > /dev/null && echo "Impersonation successful"
```

`gcloud auth list` identifies the active caller. The success text would appear only after a successful token request. Running this in my own Cloud Shell tests my active identity, not the default Compute Engine account. I did not provide a completed result.

### My preference for a Console check, and the decision to move on

I tried **Policy Troubleshooter**, selecting Manual and entering a principal, a service-account resource and `iam.serviceAccounts.getAccessToken`. The proposed full resource name was:

```text
//iam.googleapis.com/projects/-/serviceAccounts/employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com
```

The same check could be repeated for `972261256506-compute@developer.gserviceaccount.com`. Granted would indicate evaluated permission, Denied a failed policy check, and Unknown/conditional a need for more information. Troubleshooter evaluates policy; it is not a live token-generation attempt.

**S11** shows the resource-selection dialog, not an access decision. I decided not to spend more time on this detour. **Both impersonation checks remained unverified.** I learned where to configure access if needed: Service Accounts → employee-api-sa → Principals with access → Grant access, selecting the appropriate role for the intended operation. I did not add Token Creator merely to continue deployment.

## 6. Why I need both deployment roles — my key clarification

I repeatedly asked why Service Account User was needed if Cloud Run runs the application, why Robot B seemed to be deploying, and where Cloud Run Developer fit into the chain. The corrected wording is:

> I ask Cloud Run to deploy my image as a new employee-api revision while retaining employee-api-sa as the application's identity.

Robot B does not deploy, start Python or operate infrastructure. The original “runtime operator” wording made that confusing; my MES Windows-service analogy is more precise.

### The comparison table I wanted to preserve

| Permission | What Google checks |
|---|---|
| Cloud Run Developer | Is Robot A allowed to update the employee-api Cloud Run service and create a new revision? |
| Service Account User | Is Robot A allowed to configure employee-api-sa as the runtime identity? |

Both roles are received by **Robot A**, but granted on **different resources**.

| Part of the chain | Responsibility |
|---|---|
| Request/deploy a new image and revision | Robot A's authorised deployment request; Cloud Run performs the deployment |
| Select/retain employee-api-sa | Robot A's Service Account User permission on that account |
| Execute my application | Cloud Run infrastructure |
| Resolve EMPLOYEE_API_KEY | Cloud Run uses Robot B's identity and its Secret Manager permission |

### My MES / Windows service analogy

Robot A is my MES deployment engineer. Cloud Run is the Windows server hosting and starting the MES application. Robot B is the Windows service identity configured for that application. Cloud Run Developer is permission to install/update the application on that host. Service Account User is permission to configure that particular identity. Secret Manager Secret Accessor is the identity's permission to access protected configuration, analogous to a database or secured resource needed by the MES application.

I initially called `Runtime identity: employee-api-sa` an environment variable. That was corrected: **runtime identity is a separate Cloud Run setting**. `APP_ENV` and `APP_VERSION` are environment variables. `API_KEY` is an environment variable backed by a secret reference.

The separate checks prevent a deployer from automatically selecting any highly privileged identity simply because it can update a Cloud Run service.

| Missing permission — teaching scenario | Expected effect |
|---|---|
| Robot A has Cloud Run Developer but lacks actAs on employee-api-sa | Cannot deploy using that identity; a missing `iam.serviceAccounts.actAs` error is possible |
| Robot A has Service Account User but lacks service update rights | Cannot update employee-api |
| Robot A has both | Can perform this part of deployment, assuming the remaining registry/authentication requirements are met |
| Robot B lacks required secret access | The protected environment-secret reference cannot be resolved successfully |

These were explanations, not failures observed in run #9.

## 7. Service-account addresses and my saved IAM grants

I asked how we decided the domain in `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com`. I did not configure or host that domain. Google generates this service-account email from:

```text
SERVICE_ACCOUNT_ID @ PROJECT_ID . iam.gserviceaccount.com
github-deploy-sa   @ cloud-genai-learning . iam.gserviceaccount.com
```

I chose the account ID and project ID; Google supplies the service-account domain. It is an identity address, not my application's website. In another teaching example, account `mes-deploy-sa` in project `factory-mes-prod` becomes `mes-deploy-sa@factory-mes-prod.iam.gserviceaccount.com`. I can copy the actual Email column from IAM & Admin → Service Accounts instead of typing it from memory. **S03** shows my account inventory.

### Step A — Service Account User on employee-api-sa

I opened IAM & Admin → Service Accounts → employee-api-sa → Principals with access → Grant access. **S12** is the initial access screen, **S13** the form before saving, and **S14** the completed grant with “Policy updated.”

| Field | My chosen value and purpose |
|---|---|
| Resource | `employee-api-sa`; the protected runtime account |
| New principal | `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com`; the deployer receiving access |
| Role | Service Account User (`roles/iam.serviceAccountUser`), including actAs |
| IAM condition | No condition added in the form |
| Scope | Directly on this account, rather than all service accounts at project scope |
| Result | Saved and visible in S14; inherited Owner/Editor entries remain distinguishable |

### Step B — Cloud Run Developer on employee-api

I selected employee-api in the Cloud Run Services list and opened Permissions. I could not find “Grant access” because this interface called the button **Add principal**. **S15** shows that button. It was a UI naming difference, not a missing permission or a failed deployment.

**S16** shows my pre-save form and **S17** the saved result, including Cloud Run Developer (1) and “Policy updated.” The principal is github-deploy-sa, role Cloud Run Developer (`roles/run.developer`), condition none, resource the existing employee-api service, scope this service only.

### My question: “Why not assign the same role under IAM & Admin?”

The significant difference is the resource/scope, not the navigation screen. A project-level Cloud Run Developer grant applies to eligible Cloud Run resources across that project, including future ones. A direct employee-api grant is limited to that service for this particular binding. It does not remove broader access granted elsewhere.

In my teaching project with employee-api, order-api and inventory-api, project scope is like an engineer having access to all production lines. Service scope is like permission for only the employee line. I used service scope for least privilege and did not duplicate the grant at project level.

| Resource | Principal receiving role | Role | Evidence/status |
|---|---|---|---|
| Cloud Run employee-api | github-deploy-sa | Cloud Run Developer | Newly saved; S17 |
| Service account employee-api-sa | github-deploy-sa | Service Account User | Newly saved; S14 |
| Artifact Registry employee-api repository | github-deploy-sa | Artifact Registry Writer | Existing Day 26 configuration; publishing succeeds in run #9 |
| Secret EMPLOYEE_API_KEY | employee-api-sa | Secret Manager Secret Accessor | Existing resource grant verified; S09 |

Writer already provided the repository read access needed for this deployment exercise as well as publishing. I did not add a separate Reader grant. Authentication through WIF is another prerequisite; neither of the two new deployment roles replaces it.

## 8. My workflow change and WIF context

My file was `.github/workflows/ci.yml` in my existing repository. I added the following **exact deployment step** immediately after the Docker push step, matching the indentation under `jobs.test.steps`. **S18** shows lines 64–73.

```yaml
      - name: Push Docker image to Artifact Registry
        run: |
          docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}

      - name: Deploy to Cloud Run
        uses: google-github-actions/deploy-cloudrun@v3
        with:
          service: employee-api
          region: europe-west2
          image: europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
```

This is my recovered workflow tail, not a fabricated copy of every unseen line in the full file.

| Field | Meaning and why I used it |
|---|---|
| `name` | Human-readable step title in Actions |
| `uses: ...@v3` | The Google-provided action used in my actual exercise |
| `service: employee-api` | Updates the existing service, retaining its identity as the deployment target |
| `region: europe-west2` | Targets the London service, matching my existing resources |
| `image` | Fully qualified registry/project/repository/image reference |
| `${{ github.sha }}` | GitHub expression resolved to the commit associated with this run; used consistently for tag, push and deployment |
| Omitted environment/secrets/runtime replacement fields | Intentional: deploy the new image without explicitly replacing those existing settings; I verified them afterward |

The first `employee-api` after the project is the **repository**; the second is the **image name**. They have the same text but different roles. A Docker tag labels the packaged image; it does not create a new Git commit.

### The authentication foundation I reused

WIF was configured earlier and worked in run #9. It lets GitHub's external workload obtain short-lived Google credentials as github-deploy-sa without storing a permanent Google service-account private key in GitHub. In the Company A/Company B analogy, GitHub supplies a signed visitor identity, Google's WIF entrance validates it, and the approved deployment identity receives temporary access.

My existing pipeline used `google-github-actions/auth@v3`, Google Cloud CLI setup, a credential-verification command, Docker credential-helper configuration, image tagging and push. The inherited provider context recovered from the adjacent learning material was:

```yaml
with:
  project_id: cloud-genai-learning
  workload_identity_provider: projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider
  service_account: github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com
```

These values belong to the existing authentication stage, not a new Day 27 provider creation. My new work did not replace the Day 26 WIF restrictions.

For recall, the auth action prepares reusable credential configuration; `gcloud auth print-access-token` tests obtaining a token; Docker needs its own helper configuration to use that Google identity. The existing runner commands included:

```bash
gcloud auth print-access-token > /dev/null
gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet
docker build -t employee-api:ci .
docker tag employee-api:ci europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
```

These illustrate the inherited stages, not a newly reordered complete workflow. Build precedes authentication in the observed run. `--quiet` suppresses interactive confirmation. Docker uses its `config.json` credential helper for this registry; it does not directly parse the WIF file merely because `GOOGLE_APPLICATION_CREDENTIALS` exists. The helper can obtain/reuse valid temporary credentials; a previous token-printing test is not itself Docker login configuration.

## 9. Commit, run #9 and observed timings

After reviewing the YAML placement and image address, I saved the file and ran these commands from my local Git repository root in the VS Code PowerShell terminal:

```powershell
git add .github/workflows/ci.yml
git commit -m "CI/CD - Automate Cloud Run deployment"
git push origin main
```

My terminal in **S19** shows commit `7ae978d`, one file changed with seven insertions, and a successful push to main. The preceding `git status` message “no changes added to commit” was an unstaged-change status, not the final commit result. I then staged, committed and pushed correctly.

**S20** is an intermediate Actions list with run #9 in progress. **S21–S22** are the completed successful job and expanded deployment log. I should not caption the in-progress screen as final success.

Observed sequence:

```text
Checkout → Python setup → dependencies → pytest → Docker build
→ WIF authentication → gcloud setup → credential verification
→ Docker authentication → tag → push → deploy → cleanup
```

| Stage visible in the run | Observed duration |
|---|---:|
| Checkout | 2 s |
| Python setup | 0 s |
| Install dependencies | 16 s |
| pytest | 8 s |
| Docker build | 24 s |
| Authenticate to Google Cloud | 0 s |
| Set up gcloud | 6 s |
| Verify Google authentication | 1 s |
| Configure Docker authentication | 0 s |
| Tag image | 0 s |
| Push image | 8 s |
| Deploy to Cloud Run | 25 s |
| Reported successful job | 1 min 37 s |

The deployment log shows `gcloud run deploy employee-api` with the full commit-tagged image, `--region europe-west2` and `--format json`. The action also adds `managed-by=github-actions` and a `commit-sha` label in its generated command. This is an important screenshot correction: although a later explanation proposed adding a commit label in the future, **the recorded action already supplied one**. I did not separately inspect the label in the Console, so I distinguish “present in generated command” from “visually verified label on revision.”

### Timing interpretation — supplementary calculation from my observed values

This is a recall calculation added to these notes, not a separate calculation I performed during the exercise:

1. Total reported duration: `1 min × 60 s/min + 37 s = 97 s`.
2. Deployment duration: `25 s`.
3. Other time in the reported total: `97 − 25 = 72 s`.
4. Deployment share: `(25 s ÷ 97 s) × 100 = 25.77%`.

The displayed per-step seconds are rounded and do not have to sum exactly to the reported total. I should not interpret the remainder as one specific stage or invent exact start timestamps.

## 10. My post-deployment configuration verification

In Revision History I selected the newest revision. **S23** shows `employee-api-00025-2kp` with 100% (to latest), confirming it was serving traffic rather than merely existing.

| Configuration field | My observed value | Meaning / practical effect |
|---|---|---|
| Image | Artifact Registry image resolved to a digest | Identifies packaged content for this revision |
| Port | 8080 | Port the container receives requests on; must match application listening configuration |
| CPU | 1 | Configured CPU allocation; retained |
| Memory | 512 MiB | Configured memory limit; retained |
| APP_VERSION | `3.0` | My application version environment setting; does not automatically equal the Git SHA |
| APP_ENV | `staging` | Application environment setting; not a Cloud Run traffic tag |
| API_KEY | Secret `EMPLOYEE_API_KEY`, version `1` | Secret-backed environment variable, not the literal secret in YAML |
| Runtime account | employee-api-sa | Retained Google identity; finally rechecked in Security |
| Authentication | Require authentication, IAM enabled | Retained service invocation protection |

S23 additionally displays request timeout 300 seconds, execution environment Default, revision maximum instances 3, CPU/memory, no source/build information, and zero volumes. These are visible retained settings, not new values chosen during Day 27. Their original design rationale was not re-established. A revision maximum of 3 is an instance limit, not a traffic percentage or concurrency value.

**S26**, the final Security screenshot, verifies employee-api-sa, Require authentication and IAM enabled after deployment. It also displays no custom audiences, IAP unchecked, Google-managed encryption, Threat Detection disabled, and Binary Authorization unchecked. These were visible existing options, not new security changes performed in this exercise. I did not enable IAP, KMS encryption, threat detection or Binary Authorization.

An earlier “are we done?” answer correctly left the Security check outstanding. The subsequent S26 closes that specific check; my final state must not keep saying it is unverified.

## 11. My image-identification questions and corrections

### “Not showing the revision tag”

I expected to see `7ae978d` under Revision tags. A **Docker image tag** and a **Cloud Run revision/traffic tag** are different:

| Identifier | Example | What I use it for |
|---|---|---|
| Git commit SHA | `7ae978d...` | Source-code commit |
| Docker image tag | `employee-api:7ae978d...` | A label assigned to the image by my workflow |
| Docker image digest | `sha256:3a2b7e...` | Content-based identifier of an image manifest |
| Cloud Run revision | `employee-api-00025-2kp` | Deployed image plus configuration |
| Cloud Run traffic/revision tag | `staging` — teaching example | A named URL/traffic tag for a revision |

My workflow used the commit SHA as the **image tag**, but it did not assign a Cloud Run traffic tag. I did not need to use the + button in Revision tags. My APP_ENV value `staging` is also independent of such a tag.

### “Where can I see the commit and image tag?”

In GitHub I can open commit history and the commit “CI/CD - Automate Cloud Run deployment,” then expand short `7ae978d` to the full SHA. In GCP I open Artifact Registry → employee-api repository → employee-api image → versions/tags. **S24–S25** show the commit-tagged entry.

The narrow Cloud Run image panel truncated the image reference. I copied it and provided this full deployed reference:

```text
europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api@sha256:3a2b7e257266599f5045252db9a7e43b1ce2432b7878c5856d0458a3a1437097
```

Cloud Run resolves a tag at deployment and records the immutable digest. It does not need to display the original Git SHA in the Revision tags column. The earlier expectation “look for an image tag starting 7ae978d” was refined after seeing the digest-based reference.

### “What is a digest, and why do I need both?”

A digest is a cryptographic fingerprint of the referenced content. In my MES/Keyence C# example, hashing an exact image file helps identify its bytes. Likewise, a Docker digest identifies exact manifest content rather than just its human-readable package label.

Teaching example: I could reuse tag `v1` for image A and image B. The label remains `v1`, while different content produces different digests, such as illustrative `sha256:AAA...` and `sha256:BBB...`. These are placeholders, not real hashes from my project. My commit-based tag helps trace source; the digest is the stronger identifier for exact packaged content. A small content change almost certainly changes the SHA-256 result.

### Multiple digest rows: an important evidence boundary

| Artifact Registry prefix | What was discussed/visible |
|---|---|
| `6a0654f71f8c` | Entry carrying the full `7ae978d...` tag; discussed as an image index/manifest |
| `3a2b7e257266` | Prefix matching my Cloud Run deployed image digest |
| `6bcc4018d4cb` | Another associated artifact; exact type was not independently inspected |

A modern image push can create an index plus platform-specific manifests and associated metadata. Each object has a different digest. I must not assume adjacent rows are the same object or that the extra artifact's exact type is proven by this list alone.

The proposed stronger check was to open `6a0654f71f8c`, inspect its manifest/details and verify it references the `3a2b7e257266...` platform manifest. **No screenshot of that manifest relationship was recorded.** The earlier wording suggesting the listing alone proved the complete relationship was too strong. My final evidence is the successful same-tag deployment command, registry listing, exact deployed digest supplied by me, and revision receiving all traffic; the index-to-child inspection remained a suggested independent check.

### “How did we ensure this was deployed?”

My tag/push/deploy addresses consistently use `${{ github.sha }}`. For run #9, that resolves to my full commit SHA. The evidence chain is:

```text
Git commit 7ae978d...
  → workflow builds and tags that commit's image
  → docker push of the same full image address succeeds
  → deploy action supplies that same address to Cloud Run
  → new revision 00025-2kp references an immutable digest
  → newest revision receives 100% traffic
```

The hypothetical failure case matters: if push succeeded but deployment failed due to IAM, the new image could exist in Artifact Registry while Cloud Run continued serving the previous successful revision. That is why registry presence alone is not deployment proof. In my actual run the deployment succeeded.

## 12. My troubleshooting, decisions and remaining work

| Question/problem | Clarification or action | Final state |
|---|---|---|
| Account Permissions screen seemed empty | Separate outgoing roles from incoming access | Understood; S05–S09 |
| Runtime robot seemed to execute/deploy Python | Cloud Run executes; identity authorises resource access | Corrected wording retained |
| Runtime identity called an environment variable | Separate revision setting | Corrected |
| Owner/Editor assumed to prove token impersonation | Check getAccessToken specifically | Not verified; detour stopped |
| Policy Troubleshooter resource field confusing | UI resource selection inspected | No completed access result; S11 |
| “Grant access” missing in Cloud Run | Button called Add principal | Proceeded; S15–S17 |
| Why two deployer roles? | Service update and identity attachment are separate checks | Both saved |
| Missing commit under Revision tags | Image tag differs from traffic tag | No extra tag added |
| Cloud Run shows digest | Copy full reference; compare registry evidence | Digest recorded |
| Three registry rows | Index/manifests/metadata can have separate hashes | Exact relationship check proposed, not recorded |
| Was security preserved? | Reopen Security after deployment | Verified; S26 |

I did not record a failed Day 27 deployment. Missing-permission errors were teaching cases. Run #9 passed. I did not broaden project IAM, remove the default account's Editor role, delete old revisions/images, change the secret, rotate credentials, perform rollback or alter runtime security as cleanup. No completed cleanup should be inferred.

Potential follow-up items remain distinct from this completed deployment exercise: broader IAM audit, the two token-impersonation checks if still needed, independent manifest-parent inspection, an HTTP smoke test, and rollback practice. I have no recorded decision to delete any existing resource.

## 13. Quick recall guide

- **Who runs Python?** Cloud Run.
- **Who deploys?** GitHub Actions authenticated as github-deploy-sa.
- **What is employee-api-sa?** My revision's Google Cloud identity.
- **Why Service Account User?** Robot A may attach Robot B; granted on Robot B's resource.
- **Why Cloud Run Developer?** Robot A may update employee-api; granted on that service.
- **Why Secret Accessor?** Robot B may resolve EMPLOYEE_API_KEY.
- **Does actAs equal token impersonation?** No; getAccessToken is a separate permission.
- **Does no project IAM row mean no access?** No; inspect resource grants and inheritance.
- **Does pushing an image deploy it?** No; my added deploy step does that.
- **Is APP_ENV=staging a traffic tag?** No.
- **What identifies source versus bytes?** Git SHA versus image digest; image tag connects my workflow's package label to the commit.
- **My success anchors:** commit `7ae978d`, run #9, revision `00025-2kp`, 100% traffic, S26 final security.

## 14. Screenshot index and coverage verification

The workbook Index gives the exact sheet and row for every embedded original. Images remain at their original proportions and are displayed at a readable width. Original bytes are embedded in the XLSX, not linked externally.

| Screenshots | My note sections | Evidence |
|---|---|---|
| S01–S04 | 2–3, 7 | Initial image selection, security, accounts and Permissions |
| S05–S07 | 4 | Incoming access, inherited roles, project IAM |
| S08–S10 | 3–4, 10 | Secret location, actual secret grant and container settings |
| S11–S14 | 5–7 | Troubleshooter detour, pre-save form, saved Service Account User |
| S15–S17 | 7 | Add principal, Cloud Run Developer form and saved policy |
| S18–S19 | 8–9 | Actual workflow tail and successful commit/push |
| S20–S22 | 9 | In-progress run, successful stages and deployment log |
| S23 | 10–11 | New revision, traffic, resources, environment and secret |
| S24–S25 | 11 | Registry tag and digest entries |
| S26 | 10, 12 | Final Security tab verification |

I checked coverage of my goal, all identity questions, incoming/outgoing IAM, inheritance and scope, least privilege, custom/default identity, secret startup behavior, actAs versus token generation, Console and CLI teaching checks, email construction, MES/key/package/hash analogies, both saved grants, YAML and WIF context, Git commands, timings, revision/traffic/configuration checks, tag/digest/revision distinctions, evidence corrections and deferred work. The workbook Coverage sheet maps these items to note sections and screenshots.

No original full-file YAML attachment was supplied for Day 27; the recovered screenshot shows the tail. I retain that actual excerpt and the observed stage order rather than invent unseen lines. The source does not contain a completed manifest-parent view, token-impersonation result, HTTP response test or rollback result. These are evidence limits, not missing recovered successes.

### Technical reference checks

I used the original learning material as the record of what I did. The following primary references support the central distinctions; they are not evidence of my project's saved state:

- [Cloud Run deployment requirements and tag resolution](https://docs.cloud.google.com/run/docs/deploying)
- [Cloud Run service identity](https://docs.cloud.google.com/run/docs/configuring/services/service-identity)
- [Service-account authentication roles](https://docs.cloud.google.com/iam/docs/service-account-permissions)
- [Google deploy-cloudrun action](https://github.com/google-github-actions/deploy-cloudrun)

My deliverables are the Markdown notes and the Excel screenshot workbook. Library saving is handled separately from the content and workbook validation.
