# Day 29 — My automated smoke testing and safe Cloud Run promotion

I started this learning day by extending my Day 28 manual deployment process. I then spent time understanding identities, permissions, tokens and the actual communication between GitHub and Google before returning to the practical pipeline. These notes include that whole sequence, including the material revisited on 6 November and the later practical completion.

My objective was: **deploy a candidate with 0% normal traffic, authenticate to it, test its response, verify its revision identity and promote that named revision only when the checks pass.** I also deliberately tested the failure path and restored the successful configuration afterward.

The companion workbook contains these detailed explanations on `Learning Notes`, followed by 51 original screenshot sheets, `S01`–`S51`. The `Index` sheet connects each screenshot to its Markdown section and the corresponding explanation row in the workbook. Original image contents and dimensions are preserved. Browser-exported filenames are retained in the index; these filenames do not imply capture dates.

**How I read the evidence:** “Observed” identifies something visible in my original screenshots. “Implemented” identifies code or a setting reviewed and subsequently exercised successfully. “Teaching example” identifies an illustrative value or hypothetical failure, not a live result. “Proposed” identifies future improvements. I keep those distinctions because a useful example must not become a false record of what I deployed.

<a id="start"></a>
## 1. My starting point and exercise plan

My title was **CI/CD: Automated Smoke Testing and Safe Promotion to Google Cloud Run using GitHub Actions**. On Day 28 I had deployed a candidate at 0%, manually obtained an identity token, manually smoke-tested it, promoted it and practised rollback. Day 29 automated the testing and promotion inside my existing `.github/workflows/ci.yml`.

My exercise plan had six responsibilities: check invocation permissions, capture the deployment revision, generate an ID token, validate the HTTP response, automate promotion and simulate failure. Python tests, Docker image building, Artifact Registry pushing and the initial no-traffic deployment already existed. I was adding application verification and traffic control to that baseline.

```text
Local code/workflow change -> Git commit -> Push to main
  -> Python tests -> Docker build
  -> Authenticate through WIF -> Push image to Artifact Registry
  -> Deploy candidate at 0% normal traffic
  -> Capture revision -> Generate Google ID token
  -> Call candidate URL -> Check HTTP status and JSON
  -> Verify candidate tag still matches captured revision
  -> Promote captured revision to 100%

Any ordinary validation failure -> fail the step -> skip later promotion
```

I specifically wanted the exact tested revision to be promoted. `LATEST` can change when another deployment occurs, so it is unsuitable as a substitute for the revision I intended to release. I also kept the service private rather than making it public to simplify testing.

“Safe” in my exercise means guarded by these checks. It does not mean every external race, business regression or operational approval requirement has been eliminated. Those limitations are documented later.

<a id="roles"></a>
## 2. My two robots and the IAM checks I must keep separate

My first question was why I had added **Cloud Run Developer** and **Service Account User**. I understood the answer using two identities:

- **Robot A: `github-deploy-sa`** is my deployment engineer. GitHub Actions uses this identity to push, deploy and later smoke-test.
- **Robot B: `employee-api-sa`** is my application's runtime identity. It has permission to access the `EMPLOYEE_API_KEY` secret.

Cloud Run runs my Python container. Robot B supplies the identity and permissions under which it runs; the service account is not itself a machine executing Python.

| Role | Principal receiving permission | Resource on which it applies | Question it answers |
| --- | --- | --- | --- |
| Artifact Registry Writer | `github-deploy-sa` | Target Artifact Registry repository | Can I store/push the built image? |
| Cloud Run Developer | `github-deploy-sa` | Cloud Run service `employee-api` | Can I update this service and deploy a revision? |
| Service Account User | `github-deploy-sa` | Service account `employee-api-sa` | Can I attach this runtime identity? |
| Cloud Run Invoker | `github-deploy-sa` | Cloud Run service `employee-api` | Can I call the private HTTP application? |
| Secret Manager Secret Accessor | `employee-api-sa` | Secret `EMPLOYEE_API_KEY` | Can my runtime identity access this secret? |
| Workload Identity User | My permitted GitHub federated principal | Service account `github-deploy-sa` | Can this external identity obtain credentials for Robot A? |

The first three deployment grants and Secret Accessor were prior configuration revisited during this lesson. Invoker was the new Day 29 service permission. The Workload Identity User binding came from my earlier WIF setup and was inspected again during token troubleshooting.

### My deployment flowchart

```text
GitHub Actions, operating as github-deploy-sa (Robot A)
                       |
              Request new deployment
                       |
          +------------+-------------+
          |                          |
 Cloud Run Developer          Service Account User
 Can update employee-api?     Can attach employee-api-sa?
          |                          |
          +------------+-------------+
                       |
            Cloud Run creates revision
                       |
      Container runs with employee-api-sa (Robot B)
                       |
      Secret Manager checks Robot B's permission
                       |
              Access EMPLOYEE_API_KEY
```

My original explanation screenshot is preserved as **S01**. It is a teaching flowchart, not a screenshot of an IAM save operation.

### What happens if either role is missing?

**Scenario A — Cloud Run Developer is missing.** Robot A may successfully authenticate through WIF and still fail deployment. Authentication establishes the identity; it does not grant service-update authority. I would investigate permission to update `employee-api` rather than assume WIF failed.

**Scenario B — Service Account User is missing.** Robot A may be allowed to update the service but be rejected when it tries to attach `employee-api-sa`. The relevant permission is `iam.serviceAccounts.actAs`. This failure concerns assigning a runtime identity.

**Scenario C — Both are present.** Robot A can perform those two parts of deployment, assuming the image, repository permissions, runtime secret access and other requirements are also correct. These two grants alone are not proof that every deployment prerequisite is satisfied.

### Why Cloud Run Invoker is a different check

Updating the service and calling its running URL are separate operations. Day 29 adds a request to the candidate's `/` endpoint. For a private service, my caller needs invocation permission and an appropriate ID token. Neither Writer nor Developer nor `actAs` automatically replaces that invocation check.

My memory aid is: **Writer stores; Developer deploys; Service Account User assigns; Invoker calls.** I explicitly requested that the flowchart, these three failure scenarios and the invocation distinction be retained in my documentation.

<a id="runtime"></a>
## 3. My six questions about runtime identity, image upload and public access

### 3.1 What if I do not attach employee-api-sa?

I initially thought deployment might fail because `github-deploy-sa` did not have permission to run the application. The correction was that Cloud Run has a runtime service identity even if I do not explicitly select my custom account. For a new service, the default can be the Compute Engine default service account.

```text
Deploy without custom runtime identity (teaching scenario)
  -> Cloud Run uses its default runtime identity
  -> Runtime tries to resolve/access EMPLOYEE_API_KEY
       -> permission present: secret access can succeed
       -> permission absent: secret resolution/startup can fail
```

This is not an experiment I performed during Day 29. My actual project deliberately used `employee-api-sa` with access to that particular secret. Also, omitting the service-account flag on a later deployment of an existing service does not necessarily reset its identity. The previously configured runtime identity can remain until explicitly changed.

### 3.2 Does Robot A impersonate Robot B at runtime?

I asked whether `github-deploy-sa` impersonated `employee-api-sa` to run Python. The corrected wording is: **Robot A configures Robot B as the runtime identity; Cloud Run runs the container using that configured identity.** Robot A does not remain the running application's identity.

My MES/Windows service analogy makes this clear. A deployment engineer installs a Windows service and configures its logon account as `MES_Service_User`. Windows Service Control Manager starts it under that account. The deployment engineer does not have to stay logged in, and the engineer is not the service process's runtime identity.

`Service Account User` and `iam.serviceAccounts.actAs` authorize attaching the identity. They do not by themselves grant permission to mint short-lived credentials for it. The WIF impersonation described later is a different relationship: the external GitHub identity obtains credentials for `github-deploy-sa`.

### 3.3 Is Artifact Registry Writer just for placing the image in the repository?

My understanding was correct. Writer permits uploading the built image to the permitted repository, with Docker authentication also configured. It does not automatically permit deploying that image or assigning any service account.

This was my teaching example, not a recorded Day 29 image tag:

```bash
docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:abc123
```

The actual workflow used the Git commit SHA in its image reference. I distinguish the repository containing the image from the Cloud Run service running it.

### 3.4 How does a private invocation work?

```text
GitHub Actions establishes WIF identity for github-deploy-sa
  -> Obtain Google-signed ID token
  -> Send Authorization: Bearer ID_TOKEN to candidate URL
  -> Cloud Run validates token, audience and caller
  -> Cloud Run checks invocation permission
  -> Request reaches FastAPI -> check status and response JSON
```

The token and the IAM grant are complementary. A valid token identifies the caller; Invoker authorizes that caller on this service. Invoker does not itself generate the token.

### 3.5 Does Google block unauthenticated callers even when the service is public?

This was a misconception I corrected. Cloud Run supports public HTTP access when configured for it. Public access can be configured through disabling the Invoker IAM check or granting invocation to `allUsers`. A caller then does not need an individual Invoker grant or Google ID token for that platform invocation check, provided ingress allows access.

Private service invocation requires suitable identity and authorization. Rejection is commonly seen as 401 or 403, depending on the failure. Public platform access can still coexist with application-level authentication, API keys or rate limiting. “Public” does not mean every business operation must be unrestricted.

The sample below was illustrative and was not run against a newly public service:

```bash
curl https://YOUR-CLOUD-RUN-SERVICE-URL/health
```

| My question | Private service | Public service |
| --- | --- | --- |
| Can an internet caller invoke without a Google ID token? | Not through my IAM-protected endpoint | Yes, if ingress permits |
| Does GitHub Actions need an ID token for this invocation? | Yes | Not for an unauthenticated platform endpoint |
| Does each caller need its own Invoker grant? | A suitable grant/equivalent authority is required | No individual caller grant |
| Can application authentication still exist? | Yes | Yes |
| Which did I retain? | My actual configuration | Teaching alternative only |

### 3.6 How I remember the complete permission sequence

Robot A can upload an image, deploy it, attach the runtime identity and invoke it only through the relevant grants. Robot B separately accesses its secret. I explicitly asked to keep **all six explanations**, their comparison tables and the assignment-versus-impersonation distinction.

<a id="iam-setup"></a>
## 4. My actual Cloud Run Invoker configuration

The initial service view showed `employee-api`, region `europe-west2`, **Require authentication**, and **Ingress: All**. These are not contradictory settings. Ingress determines which network sources may reach the service; authentication determines whether a reachable caller is authorized. Allowing ingress from all does not turn off IAM authentication.

My existing Invoker was `order-api-sa@cloud-genai-learning.iam.gserviceaccount.com`. `github-deploy-sa` was not listed in the expanded Invoker role. I kept the existing caller permission and added my workflow caller.

My historical console sequence was:

1. Open Cloud Run Services and select `employee-api`.
2. Open **Permissions**, expand **Cloud Run Invoker**, and inspect existing principals.
3. Select **Add principal**.
4. Set **New principals** to `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com`.
5. Select role **Cloud Run Invoker**.
6. Save and inspect the resulting policy.

S02 shows authentication/ingress. S03 shows the initial one-member Invoker list. S04 is the populated grant form **before Save**, so that image alone is not save confirmation. S05 shows both `github-deploy-sa` and `order-api-sa` under **Cloud Run Invoker (2)** and the **Policy updated** message. It also warns that changes can take a few minutes to become active.

The resource was `employee-api`, not the entire project. I chose that scope to grant the required permission on the required service. I did not make the API public. This documentation work did not apply any new cloud permissions.

<a id="wif"></a>
## 5. My existing WIF authentication versus the verification step

I initially described WIF as converting GitHub's token into Google-understandable credentials, and I thought the next command independently verified that signed GitHub token. The precise understanding is that Google validates the external identity under configured trust rules and issues credentials. This is more than a format conversion.

My existing authentication step was:

```yaml
- name: Authenticate to Google Cloud
  id: auth
  uses: google-github-actions/auth@v3
  with:
    project_id: cloud-genai-learning
    workload_identity_provider: projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider
    service_account: github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com
```

| Field | My value | Why it matters |
| --- | --- | --- |
| `name` | Authenticate to Google Cloud | Human-readable job log label |
| `id` | `auth` | Step identifier available to workflow expressions |
| `uses` | `google-github-actions/auth@v3` | Action configuring Google authentication |
| `project_id` | `cloud-genai-learning` | My Google Cloud project identifier |
| `workload_identity_provider` | Full resource path shown above | Chooses my pool/provider trust configuration; not the STS network address |
| `service_account` | Full `github-deploy-sa` email | Chooses the service account the federated GitHub identity is authorized to impersonate |

The image S06 also shows `google-github-actions/setup-gcloud@v3` before the CLI verification. The authentication action configures credentials; Google tools and their libraries use that configuration to obtain tokens when needed. Therefore, configuration success alone does not prove every later exchange or resource permission will succeed.

### Existing job and deployment settings visible in my screenshots

S24 also preserves `permissions: contents: read` and `id-token: write`, runner `ubuntu-latest`, and `defaults.run.working-directory: 01-python-fastapi`. `contents: read` supports repository reading/checkout. `id-token: write` permits requesting GitHub's OIDC token; it does not itself grant Google resource permissions. Shell `run` commands use the FastAPI project folder on the runner. My local Git commands, in contrast, were run from the repository root. This distinction prevents confusing a relative runner path with my Windows repository path.

S06 shows these existing image operations:

```yaml
- name: Configure Docker authentication
  run: gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet

- name: Tag Docker image for Artifact Registry
  run: |
    docker tag employee-api:ci europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}

- name: Push Docker image to Artifact Registry
  run: |
    docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}

- name: Deploy to Cloud Run
  uses: google-github-actions/deploy-cloudrun@v3
  with:
    service: employee-api
    region: europe-west2
    image: europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
    no_traffic: true
    tag: candidate
```

The Docker configuration selects the regional registry host and `--quiet` avoids an interactive prompt. Tagging gives my locally built `employee-api:ci` image the registry destination and current Git commit SHA tag; pushing stores it there. Deployment uses that same reference, the named service/region, the no-normal-traffic setting and the candidate tag. These existing steps were retained while I added testing. They require a built local image, working Google/Docker authentication and the scoped permissions already discussed. The full earlier build/install setup is not reconstructed from off-screen lines.

My separate check was:

```yaml
- name: Verify Google Cloud authentication
  run: |
    gcloud auth print-access-token > /dev/null
    echo "Google Cloud authentication verified"
```

### The five explanations I explicitly wanted to retain

**1 — Different jobs.** `auth@v3` prepares credential configuration. `gcloud auth print-access-token` actually requests an OAuth access token using that configuration and confirms retrieval works. It does not independently revalidate the GitHub JWT as a separate manual validation procedure.

**2 — What happens behind the scenes.** The command causes the credential machinery to use the external identity, STS and service-account permissions as required to obtain temporary Google credentials. My MES security-desk analogy was: the action supplies instructions about which security desk and identity to use; the command actually visits security and obtains the pass.

```text
auth@v3 -> credential instructions for github-deploy-sa
  -> gcloud requests token
  -> WIF / STS / IAM credential checks
  -> retrieval succeeds -> verification message
```

**3 — `/dev/null`.** `>` redirects the command's standard output, and `/dev/null` discards it on the Linux runner. I want to test retrieval without printing a sensitive token into logs. This is a Bash/Linux runner command, although my local commit commands run in Windows PowerShell.

**4 — Optional diagnostic step.** The pipeline can work without this explicit verification because a later authorized operation can request credentials when needed. I added the check earlier to distinguish authentication failure from Artifact Registry authorization failure. A successful token request does not mean Robot A can push into every repository or deploy every service.

**5 — It does not prove ID-token generation.** `print-access-token` tests OAuth access-token retrieval. My private HTTP smoke test uses a Google ID token. I must configure and exercise that token generation separately.

<a id="impersonation"></a>
## 6. Who impersonates whom, and why I need different tokens

My question was: nowhere in the YAML says “impersonate,” so which account is doing it? The `service_account` setting is the relevant instruction. The external GitHub workflow identity is accepted through WIF and authorized to obtain credentials for **github-deploy-sa**. The action and authentication libraries handle that process, so my YAML does not require a separate handwritten impersonation command.

```text
GitHub workflow external identity
  -> GitHub-signed OIDC JWT
  -> Google WIF/STS accepts identity under trust rules
  -> Workload Identity User on github-deploy-sa permits credential request
  -> workflow operates as github-deploy-sa (Robot A)

Separate relationship:
Robot A has actAs on employee-api-sa
  -> may configure Robot B as Cloud Run runtime identity
  -> Cloud Run runs container with Robot B's permissions
```

The first is credential impersonation through WIF. The second is runtime identity assignment. Neither means Robot A and Robot B are interchangeable.

### My three-token table

| Stage/token | Issuer or source | Intended receiver/purpose | Where I use it |
| --- | --- | --- | --- |
| GitHub OIDC token | GitHub signs the JWT | Prove workflow identity to Google's federation service | WIF/STS exchange |
| Google OAuth access token | Google credential flow | Authorized Google Cloud management/API operations | Push/deploy/manage using Google tooling and resource IAM |
| Google-signed ID token | Google token-generation flow | Identify authenticated caller to the intended private Cloud Run service | `Authorization: Bearer` on candidate HTTP request |

I can reuse the same WIF configuration and `github-deploy-sa` identity while obtaining different token types for different receivers. Already being authenticated for Google management operations does not make an access token interchangeable with the ID token expected by my IAM-protected application endpoint.

My two MES checkpoints were **server administration** and **calling the running MES REST API**. Updating a Windows service requires administration authority. Calling a protected REST endpoint presents an identity token intended for that application. The same engineer can do both, but the receivers and permission checks differ.

The audience on the ID token is a security claim identifying the intended service. It is not an instruction to execute a URL. This distinction later explains why I use the main service URL as token audience while sending the request to the candidate-tag URL.

<a id="discovery"></a>
## 7. How GitHub and Google actually communicate

The stamping-machine analogy explained signature verification, but I still could not picture how two separate systems communicate. My missing pieces were the public discovery endpoints and the runner's outbound HTTPS request.

### Connection A — Google discovers GitHub's verification keys

I configured the issuer:

```text
https://token.actions.githubusercontent.com
```

Google understands the OpenID Connect discovery convention. From that issuer it can read:

```text
https://token.actions.githubusercontent.com/.well-known/openid-configuration
```

The discovery JSON contains `jwks_uri`, which points to:

```text
https://token.actions.githubusercontent.com/.well-known/jwks
```

```text
My configured issuer
  -> standard /.well-known/openid-configuration
  -> read jwks_uri
  -> retrieve public keys from GitHub over HTTPS
  -> select appropriate key and verify GitHub JWT signature
```

I had asked how Google could find `jwks_uri` when I had configured only the issuer. The answer is the standard discovery mechanism. I did not manually paste a public key or JWKS URL into this lesson's GCP configuration.

GitHub hosts public keys at its own endpoint. It does not upload its private key into my project. Google retrieves, and may cache/refresh, public verification keys. A public key verifies a signature; it cannot be used as GitHub's private signing key.

### My actual browser experiment and its 404

I thought the supplied URLs might be samples. They were real GitHub endpoints. My screenshots show:

| Screenshot | What I opened | Observed result | What it means |
| --- | --- | --- | --- |
| S07 | Bare issuer root | `404 page not found` | The issuer need not be a human-readable webpage; this did not disprove OIDC availability |
| S08 | Discovery endpoint | JSON containing issuer and `jwks_uri` | This is the directory Google can consult |
| S09 | JWKS endpoint | JSON with a `keys` collection | Public verification-key material is available |

In the key JSON, `kid` identifies a signing key, `kty` describes its type, and `n` and `e` are RSA public-key components. The screenshot includes fields such as `alg: RS256` and `use: sig`. I did not need to study RSA mathematics to complete the pipeline, and the JSON does not expose GitHub's private signing key.

### Connection B — The runner delivers the signed token to STS

```text
GitHub Actions runner
  | asks GitHub's token service for an OIDC JWT
  v
GitHub token service signs JWT with private key
  | returns signed JWT to runner
  v
Runner/authentication libraries
  | HTTPS POST to https://sts.googleapis.com/v1/token
  | includes signed external JWT and provider audience
  v
Google STS + WIF provider
  | validate issuer, signature, audience, expiry and conditions
  | return federated credential
  v
Runner obtains credentials for github-deploy-sa if IAM permits
```

The runner is the bridge. GitHub's token issuer does not have to directly push my JWT into Google. The authentication tooling already knows Google's standard STS endpoint. My provider resource path chooses the trust configuration and helps construct the exchange audience; it is not an STS server address.

WIF is the **trust agreement**, HTTPS is the **communication channel**, and the runner is the **courier**. There is no need for a permanent socket, private tunnel or shared signing secret between GitHub and Google for this exchange.

### Signature verification is not sufficient authorization

My discussed trust values were pool `github-pool`, provider `github-provider`, repository `Rajadurai0606/cloud-genai-learning`, repository ID `1368433185`, and branch `main`. GitHub signs tokens for many repositories. A valid GitHub signature alone must not authorize every repository to use my deployment account.

This JSON was a **teaching example of claims**, not a token decoded from my run:

```json
{
  "iss": "https://token.actions.githubusercontent.com",
  "repository": "Rajadurai0606/cloud-genai-learning",
  "repository_id": "1368433185",
  "ref": "refs/heads/main",
  "aud": "//iam.googleapis.com/projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
}
```

Google checks signature, issuer, intended audience, expiration and the configured repository/branch conditions. Then IAM separately controls whether the accepted federated principal may obtain credentials for `github-deploy-sa`. “GitHub issued it” and “this workflow is allowed here” are different questions.

### My complete stamping-machine/MES analogy

| Real mechanism | My analogy |
| --- | --- |
| GitHub | Trusted external company issuing employee cards |
| GitHub private key | Secret stamping-creator machine |
| Public verification key | Public stamp-verification template |
| OIDC discovery document | Directory showing where verification templates are kept |
| GitHub runner | Courier carrying the signed visitor pass |
| WIF provider | MES gate configured to recognize that company |
| Provider repository/branch conditions | Approved department/person rules |
| STS | Visitor desk issuing a temporary internal credential |
| Workload Identity User | Permission for the accepted visitor to act as my deployment engineer |
| github-deploy-sa | Deployment engineer's Google identity |

When I explained it back on the later continuation, I said GitHub “signs a digital key.” The correction is that GitHub **signs the OIDC token/JWT with its private key**. Also, the provider path identifies the trust configuration rather than the network endpoint. I now connect both the analogy and the actual HTTPS flow.

<a id="learning"></a>
## 8. My detour into earlier notes, learning pace and scope

During this Day 29 exploration I supplied my Day 26 Markdown and asked that the revisited authentication explanations be added with flowcharts, short examples, impersonation distinctions and the three-token comparison. The historical response handed that separate update to Work. The commit message I requested was:

```text
Day 26 - Updated WIF, OIDC authentication and token flow explanations
```

Those concepts belong in my Day 29 notes too because I explored them after beginning this learning day. I do not treat a historical handoff message as proof that this documentation task has modified the separate Day 26 attachment. My screenshot run lists show that earlier documentation commit as Run #14, commit `1190a3a`; it is context, not one of Runs #15–20.

I paused because I was mentally tired and wanted to understand issuer discovery properly. Later I asked whether to finish that evening. The planning estimate was 15–20 minutes for ID generation, 15–20 for smoke testing, 10–15 for promotion and 15–20 for failure handling. Adding the lower bounds gives 15 + 15 + 10 + 15 = **55 minutes**; upper bounds give 20 + 20 + 15 + 20 = **75 minutes**. These were planning estimates, not measured completion times. “Verify rollback safety” in that estimate did not become a demonstrated post-promotion automatic rollback.

I also asked whether I was progressing too slowly. The feedback was subjective, including an 8/10 assessment, not a certification. My previously reported quiz scores were 14/15, 12/15, 13/15 and 12/15. The calculation was `(14 + 12 + 13 + 12) / 60 × 100 = 51/60 × 100 = 85%`. Quiz retention and independent implementation ability are related but different.

The suggested 60-minute session was **35 minutes hands-on + 15 minutes explanation + 10 minutes notes/recall = 60 minutes**. I asked for a clear pause when a deeper topic was not needed yet. My agreed learning approach became:

- Understand now what I need to implement, troubleshoot and secure the application.
- Record useful deeper questions and revisit them when relevant.
- Implement, observe, troubleshoot and connect the result to the explanation.

A genuine architecture or security issue still deserves attention. I do not need cryptographic mathematics before using WIF correctly. My next independent practice should involve proposing small workflow changes, not memorizing a long YAML file.

<a id="token-permission"></a>
## 9. My token-generation permission investigation and correction

When I resumed, Invoker was already configured. The next check was the **Principals with access** panel on `github-deploy-sa`. S10 shows a GitHub federated principal ending in repository ID `1368433185` with **Workload Identity User**. It also shows other inherited/account entries; they are not the reason I concluded another broad grant was needed.

The initial explanation raised Service Account Token Creator or the narrower Service Account OpenID Connect Identity Token Creator as permissions to investigate. I challenged this: neither was shown as added, so would token generation fail?

The corrected conclusion was that my existing **`roles/iam.workloadIdentityUser` includes both `iam.serviceAccounts.getAccessToken` and `iam.serviceAccounts.getOpenIdToken`**. My authorized GitHub federated principal already had that role on `github-deploy-sa`. Therefore I did not automatically need another Token Creator grant for this WIF path.

| Permission/role | What I learned | Actual decision |
| --- | --- | --- |
| `iam.serviceAccounts.getAccessToken` | Obtain an OAuth access token for the service account | Covered by existing Workload Identity User |
| `iam.serviceAccounts.getOpenIdToken` | Obtain a Google-signed ID token | Also covered by that existing role |
| Service Account Token Creator | Broader credential-generation role | Not newly granted for this exercise |
| Service Account OpenID Connect Identity Token Creator | Narrow role for ID-token generation when needed | Not newly granted for this exercise |
| Cloud Run Invoker | Invoke the private service | Separate service grant, already added |

I must be precise about the role's subject: the GitHub federated principal has permission **on** the deployment service account to request credentials for that account. This is not the same as saying Robot A automatically gives itself every credential-generation role.

My approach was to test the existing configuration, inspect any exact permission error and grant only what was actually missing. Run #15 succeeded without an additional Token Creator role. No long-lived service-account JSON key was created as part of this change. A temporary credentials file mentioned in an action log is not evidence that I manually created a long-lived private-key file.

<a id="token-settings"></a>
## 10. My ID-token YAML and all four requested explanations

Initially I placed this immediately after **Deploy to Cloud Run**. Later revision capture was inserted between deployment and this step.

```yaml
- name: Generate Cloud Run ID token
  id: cloud-run-token
  uses: google-github-actions/auth@v3
  with:
    project_id: cloud-genai-learning
    workload_identity_provider: projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider
    service_account: github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com
    token_format: id_token
    id_token_audience: https://employee-api-972261256506.europe-west2.run.app
    id_token_include_email: true
```

**1 — `token_format: id_token`.** This requests a Google-signed ID token, not merely credential setup and not an OAuth access token. I need it because my running Cloud Run application requires authenticated invocation.

**2 — `id_token_audience`.** The chosen value is my main service URL, `https://employee-api-972261256506.europe-west2.run.app`. Google places this intended-service value in the token's `aud` claim. My HTTP request will target a tagged candidate URL, but the audience ordinarily identifies the main service unless a custom audience is configured. No custom audience was introduced here.

**3 — `id_token_include_email: true`.** This requests the service account's email identity in the generated ID token. The explanation illustrated claims such as `email: github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com` and `email_verified: true`. That JSON was illustrative, not a token printed from my run. Cloud Run validates the caller and its authorization.

**4 — Complete flow.** Request the right token type, set the intended recipient, include the service account email, present the token when calling the candidate, and let Cloud Run validate the request and Invoker authority.

```text
token_format -> What type of pass do I request?
audience -> Which application is this pass intended for?
include_email -> Include the caller's service-account email
HTTP Authorization header -> Present that pass at the gate
```

I explicitly asked to preserve all four points and clarified that we had not yet called the candidate. That was correct, with one refinement: a successful action run actually obtains a token; it is not merely collecting parameters. At that stage the `curl` request and promotion did not yet exist.

My MES analogy was **obtain an authorized access pass first, present it at the application gate next**. Issuing the pass does not itself send a business request. S11 shows the YAML review and an unsaved-change dot, so I had to save before committing.

<a id="run15"></a>
## 11. Run #15 — ID-token generation succeeded

My local commands, from repository root `C:\Raja\Learning\python\new learning`, were:

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 29 - Add Cloud Run ID token generation"
git push origin main
```

Git stages the changed workflow, commits the staged change and pushes `main` to `origin`. The prerequisites are the intended saved edit, the correct repository and configured Git access. A Python `(.venv)` prompt appears in the terminal, but Git does not require that virtual environment.

Observed result: **Run #15**, commit **`17e7b03`**, **Success**, total **1m 42s**. The **Generate Cloud Run ID token** step passed. S12 shows commit/push; S13 the in-progress run; S14 the successful list; S15 the success summary; S16 the token-step log. The job duration shown in S15/S16 is 1m 39s, distinct from total run duration.

This verified token generation through my existing WIF setup. It did not yet prove authenticated HTTP invocation because I had not added that request. Deployment still used `no_traffic: true` and `tag: candidate`. The action log mentions a generated credentials file but does not print my token value.

Node.js action-runtime and Ubuntu runner notices appeared separately. They were maintenance notices, not evidence that the token step failed.

<a id="smoke"></a>
## 12. My authenticated smoke test, line by line

I then added this after ID-token generation:

```yaml
- name: Smoke test candidate revision
  env:
    ID_TOKEN: ${{ steps.cloud-run-token.outputs.id_token }}
  run: |
    CANDIDATE_URL=$(gcloud run services describe employee-api \
      --region europe-west2 --format=json | \
      python -c 'import json,sys; d=json.load(sys.stdin); print(next(t["url"] for t in d["status"]["traffic"] if t.get("tag")=="candidate"))')

    echo "Calling candidate revision..."

    HTTP_CODE=$(curl --silent --show-error \
      --output response.json \
      --write-out "%{http_code}" \
      -H "Authorization: Bearer $ID_TOKEN" \
      "$CANDIDATE_URL/")

    echo "HTTP status: $HTTP_CODE"
    test "$HTTP_CODE" = "200"

    python -c 'import json; d=json.load(open("response.json")); assert d["message"] == "Employee API"; assert d["version"] == "3.0"; assert d["api_key_configured"] is True'

    echo "Candidate smoke test passed"
```

These are Bash commands on the GitHub runner. They require the earlier Google authentication/CLI setup, Python, curl, the successful ID-token output and the permitted private service. S17 preserves the original code review; the end of its long JSON assertion is off-screen, while the complete block above comes from the original written instruction.

### How the step ID supplies the token

I asked why `id: cloud-run-token` appeared earlier and was now referenced in `env`. `steps.cloud-run-token` identifies that earlier step. `outputs.id_token` retrieves its token output. `ID_TOKEN` makes it available to the shell as `$ID_TOKEN`. The step ID supplies authentication data; it does not select a Cloud Run revision.

### How my candidate URL is chosen

I thought `gcloud run services describe` might default to the main URL. The command returns service JSON. The Python expression walks `status.traffic` and selects the entry whose `tag` is `candidate`, then reads that entry's `url`. It explicitly selects the tagged destination.

```json
{
  "status": {
    "traffic": [
      {"revisionName": "employee-api-00026-djg", "percent": 100},
      {"revisionName": "employee-api-00030-pen", "percent": 0,
       "tag": "candidate", "url": "https://candidate---employee-api-example.run.app"}
    ]
  }
}
```

That was a simplified **teaching response**, not the live JSON of Run #16. The normal service URL follows traffic allocation. The tagged URL directly targets the tagged revision even when it has 0% normal traffic. My token's audience remains the intended main service.

### What curl captures

| Code | Purpose and practical effect |
| --- | --- |
| `$(...)` | Captures command output into the shell variable |
| `--silent` | Suppresses normal progress display |
| `--show-error` | Still displays curl errors |
| `--output response.json` | Saves the HTTP body for the JSON assertions |
| `--write-out "%{http_code}"` | Writes the response status into `HTTP_CODE` |
| `-H "Authorization: Bearer $ID_TOKEN"` | Presents the ID token to the private endpoint |
| `"$CANDIDATE_URL/"` | Calls the candidate's root endpoint |
| `test "$HTTP_CODE" = "200"` | Rejects any status other than the expected 200 |
| `python -c ...` | Parses the saved body and tests business/application fields |

The expected values were **message = Employee API**, **version = 3.0**, and **api_key_configured is True**, using the response established earlier. The last check confirms the reported configuration flag, not every secret-dependent business operation. I did not print the ID token.

`--fail-with-body` was mentioned as a possible improvement but was not necessary for this exercise because status was explicitly checked. I do not claim it was added.

At this stage the tag lookup could test whichever revision currently held `candidate`. Another deployment could move the tag. That was the reason for later concurrency, capture and identity checks before promotion.

<a id="run16"></a>
## 13. Run #16 — My first automated authenticated candidate request

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 29 - Add automated Cloud Run candidate smoke test"
git push origin main
```

Observed result: **Run #16**, **`3b63660`**, **Success**, **1m 46s** total. The smoke log showed:

```text
Calling candidate revision...
HTTP status: 200
Candidate smoke test passed
```

This established that token generation, the candidate request and configured response checks worked together. S18–S22 cover the push, in-progress list, success list, summary and expanded smoke log. The summary's job duration is 1m 44s.

S23 then showed **`employee-api-00039-voz` at 0% with `candidate`**, **`employee-api-00038-giw` at 0%**, and **`employee-api-00026-djg` still at 100%**. Successful testing did not mean promotion had occurred. I was told not to manually change traffic while preparing the automated step.

An early checklist placed “promote the exact tested revision” alongside automated tasks, but the surrounding instructions and actual traffic show it was the **next goal**, not already completed in Run #16. My first automatic promotion was Run #18.

<a id="concurrency"></a>
## 14. The concurrency explanation I specifically asked to preserve

Before enabling promotion, I added job-level settings under my existing `test` job:

```yaml
jobs:
  test:
    concurrency:
      group: employee-api-deployment
      cancel-in-progress: false
```

S24 shows this placement. Other job settings and steps remained in place.

| Setting | Chosen value | Why I chose it and its effect |
| --- | --- | --- |
| `concurrency` | Job-level block | Coordinate participating deployment jobs |
| `group` | `employee-api-deployment` | Runs using the same group do not execute simultaneously |
| `cancel-in-progress` | `false` | Do not cancel the currently running deployment just because a newer one starts |

My teaching timeline was: if Run #17 is deploying when Run #18 starts, the second waits pending while the first runs. The explanation also noted GitHub's usual one-running/one-pending behavior: a newer pending job can replace an older pending one. Therefore this setting is not a promise that an arbitrary-length queue of every commit will execute in order.

**This is not Cloud Run request concurrency.** Cloud Run `concurrency: 1` limits requests handled by a container instance. GitHub Actions concurrency controls overlapping workflow jobs. One prevents my participating deployment jobs from changing a candidate tag or traffic simultaneously; the other concerns request processing.

It does not prevent someone deploying from Cloud Console or another independently configured system. I still needed revision checks and retained the external-deployment limitation.

<a id="revision"></a>
## 15. Capturing and remembering my deployed revision

I should not hardcode `employee-api-00039-voz` because the next deployment creates another revision name. I inserted this after **Deploy to Cloud Run**, before **Generate Cloud Run ID token**:

```yaml
- name: Capture deployed candidate revision
  run: |
    REVISION=$(gcloud run services describe employee-api \
      --region europe-west2 \
      --format="value(status.latestCreatedRevisionName)")

    test -n "$REVISION"

    echo "Deployed revision: $REVISION"
    echo "CANDIDATE_REVISION=$REVISION" >> "$GITHUB_ENV"
```

S25 shows the reviewed placement. `gcloud run services describe` reads service status; `status.latestCreatedRevisionName` selects the latest created name; `test -n` rejects an empty value. The first echo helps inspection. The second appends an environment assignment to the GitHub-provided environment file so **later steps** can use `$CANDIDATE_REVISION`.

The capture variable is local within that shell step until explicitly persisted for subsequent steps. `>>` appends to the environment file. The example `CANDIDATE_REVISION=employee-api-00039-voz` explained its shape; the following real run would capture its own newly created revision.

My important limitation is that `latestCreatedRevisionName` is service-wide. An unrelated deployment could change it. The action's service-URL output was not a dedicated revision-name output in the implementation discussion, so I queried Cloud Run. The query and concurrency setting are useful but do not prove the captured revision came exclusively from this run when external actors are allowed.

<a id="gates"></a>
## 16. Verifying the candidate identity and understanding test failures

After the existing smoke-test step I added:

```yaml
- name: Verify candidate revision before promotion
  run: |
    TAGGED_REVISION=$(gcloud run services describe employee-api \
      --region europe-west2 \
      --format=json | \
      python -c 'import json,sys; d=json.load(sys.stdin); print(next(t["revisionName"] for t in d["status"]["traffic"] if t.get("tag")=="candidate"))')

    echo "Captured revision: $CANDIDATE_REVISION"
    echo "Tagged revision: $TAGGED_REVISION"

    test "$CANDIDATE_REVISION" = "$TAGGED_REVISION"

    echo "Candidate revision verified"
```

S26 shows the YAML review. The Python expression looks for the same `candidate` traffic entry, but reads `revisionName` rather than `url`. My capture names the expected revision; this query names the revision currently tagged. Equality checks their agreement at that moment.

My teaching example was capture **`employee-api-00040-abc`** and tag **`employee-api-00040-abc`**: pass. If a separate deployment moves the tag to **`employee-api-00041-xyz`**: mismatch, fail, no normal promotion. These suffixes are examples, not my actual #17 revision.

### My question: does any failed test stop later steps?

I explicitly asked about these commands and an HTTP 404 case:

| Gate | Pass condition | Failure example |
| --- | --- | --- |
| `test -n "$REVISION"` | Nonempty captured name | Empty variable |
| `test "$HTTP_CODE" = "200"` | Exactly the expected status | 404, 403 or 500 |
| JSON assertions | Expected response fields | Wrong version or missing/incorrect field |
| `test "$CANDIDATE_REVISION" = "$TAGGED_REVISION"` | Both names match | Candidate tag moved |

`test` returns exit code **0** for a true condition and **1** for false. My ordinary runner Bash steps use fail-fast behavior (`-e`), and subsequent normal steps use the default success condition. Consequently a failure stops that step and prevents later verification/promotion from running.

```bash
# Teaching example in the fail-fast runner context
HTTP_CODE="404"
echo "HTTP status: $HTTP_CODE"
test "$HTTP_CODE" = "200"
echo "Candidate smoke test passed"
```

`test "404" = "200"` returns 1. The final success echo is not reached in that context. Revision verification and promotion are skipped. If production is `00026-djg` at 100% and candidate `00039-voz` at 0%, that run does not intentionally change normal traffic, assuming no outside actor changes it.

This is not a universal claim that a false `test` terminates every shell everywhere. `continue-on-error: true`, `if: always()`, explicit error handling and different shell contexts can change behavior. My Python assertions likewise provide a nonzero failure on an unexpected JSON result.

The check is a point-in-time identity comparison. It does not lock the service configuration afterward or eliminate every race between capture, request, verification and promotion.

<a id="run17"></a>
## 17. Run #17 — Actual revision matching succeeded

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 29 - Add candidate revision verification before promotion"
git push origin main
```

Observed result: **Run #17**, **`01a95e3`**, **Success**, **1m 41s**. My actual log named **`employee-api-00040-cil`**:

```text
Deployed revision: employee-api-00040-cil
Captured revision: employee-api-00040-cil
Tagged revision: employee-api-00040-cil
Candidate revision verified
```

S27–S31 preserve the push, in-progress list, success list, summary and verification log. This exercised capture, smoke testing and matching. It still preceded adding the automatic traffic-update step. Matching actual `00040-cil` must not be confused with the hypothetical `00040-abc` example.

<a id="promotion"></a>
## 18. My exact-revision promotion command and approval

After verification I added:

```yaml
- name: Promote verified candidate to production
  run: |
    echo "Promoting revision: $CANDIDATE_REVISION"

    gcloud run services update-traffic employee-api \
      --region europe-west2 \
      --to-revisions="$CANDIDATE_REVISION=100"

    echo "Traffic promotion completed"
```

S32 shows this code review. `update-traffic employee-api` changes routing for that service. `--region europe-west2` chooses its region. `--to-revisions="$CANDIDATE_REVISION=100"` targets the captured name with a 100% allocation. The final echo follows a successful command in the normal fail-fast step.

| Choice | Behavior | Why it mattered to me |
| --- | --- | --- |
| `--to-latest` | Select whatever revision is latest | A later deployment can change that target |
| Named `--to-revisions` | Select the explicitly supplied revision | Keeps the traffic target tied to the captured name |

I remembered the Day 28 mistake: choosing “Send all traffic to latest revision” during rollback did not restore the selected older revision. A selected row does not redefine latest. I wanted an explicit name for promotion too.

This was the first step that would actually switch normal traffic automatically. The review explicitly asked whether the next successful run could change 100% of live `employee-api` traffic, and I said to proceed. `employee-api-00026-djg` was identified as the known working revision for a possible manual rollback. No automatic rollback was added by this YAML.

The successful path is old revision 100% / candidate 0% before, then named candidate 100% / old revision 0% after. A successful `/` test is still not a guarantee that every endpoint or MES business transaction works.

<a id="run18"></a>
## 19. Run #18 — First automatic promotion and console verification

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 29 - Automate safe Cloud Run candidate promotion"
git push origin main
```

Observed result: **Run #18**, **`06819dd`**, **Success**, **1m 52s**. My promotion log showed:

```text
Promoting revision: employee-api-00041-pow
Updating traffic...
Routing traffic................done
Done!
Traffic:
  100% employee-api-00041-pow
Traffic promotion completed
```

S33–S37 show the push through expanded promotion log. S38 independently shows Cloud Run updating/routing completed and the traffic allocation:

| Revision after #18 | Normal traffic |
| --- | --- |
| `employee-api-00041-pow` | 100% |
| `employee-api-00040-cil` | 0% |
| `employee-api-00026-djg` | 0% |

The tag still appeared on the promoted revision. A `candidate` tag is a route name, not a guarantee that the tagged revision always has 0% normal traffic. My known production target had now advanced from 00026-djg to 00041-pow.

<a id="negative"></a>
## 20. My negative-test edit, initial mistake and correction

I wanted to prove that a failed smoke test blocks promotion after the build/deployment succeeds. I changed only the expected response version, leaving the FastAPI application unchanged:

```python
# Correct normal expectation
assert d["version"] == "3.0"

# Temporary deliberately incorrect expectation
assert d["version"] == "99.0"
```

The application still returned 3.0. A 99.0 expectation should produce a Python assertion failure even if HTTP returns 200. This specifically tests the content-validation gate.

### My initial edit was in the wrong language context

S39 shows I had added `assert d["version"] == "99.0"` as a standalone Bash line around line 120. The review caught it before execution. `assert` is Python syntax; Bash would instead report `assert: command not found`. Such a failure would not demonstrate that my JSON comparison was working.

I removed that separate line and changed the version assertion **inside the existing `python -c` command**, around line 124, keeping the other assertions unchanged. S40 shows the corrected location. The line numbers describe those historical screenshots, not a permanent location in every future workflow version.

The predicted Bash error was never the observed Run #19 result. The later real log showed `AssertionError`, which is the failure I intended to exercise.

After removing the extra line, the corrected screenshot S40 places the Python validation on line 122. The earlier review's reference to line 124 belonged to the previous edit. The command's language context matters more than retaining a stale line number.

<a id="run19"></a>
## 21. Run #19 — Intentional failure blocks verification and promotion

The historical instruction first suggested a commit message “Test failed smoke test blocks promotion”; after review the actual sequence used:

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 29 - Verify failed smoke test blocks promotion"
git push origin main
```

Observed result: **Run #19**, **`26563ef`**, **Failure**, **1m 41s** total. S41 is the push, including the commit that had been missing from the first workbook. S42 is in progress, S43 the failed list, S44 the failure summary, and S45 the diagnostic log.

```text
Calling candidate revision...
HTTP status: 200
Traceback (most recent call last):
  File "<string>", line 1, in <module>
AssertionError
Error: Process completed with exit code 1.
```

| Step in the negative test | Actual result |
| --- | --- |
| Build, push and candidate deployment | Passed |
| Revision capture and ID-token generation | Passed |
| Candidate HTTP request | 200 |
| Expected JSON version | Failed intentionally |
| Verify candidate revision before promotion | Skipped |
| Promote verified candidate to production | Skipped |

The red run is evidence of a successful negative test of the gate. HTTP success and content correctness are separate checks. The summary's job duration is 1m 37s, distinct from total 1m 41s. Cleanup/post steps can run after failure; their green statuses do not mean promotion occurred.

Expected traffic behavior was to leave 00041-pow serving normal traffic, provided nobody else changed routing. The skipped-promotion log proves no promotion step ran in #19. It is not itself a console snapshot immediately after #19. The final console view later shows failed candidate **00043-cek** at 0%; I do not invent an intervening traffic observation or explain an absent revision 00042.

The summary also contains a Node.js runtime warning and an Ubuntu runner notice. Those historical notices appeared on successful runs too. They were separate from the intentional Python assertion failure. No action-version or runner-image maintenance fix was demonstrated in this exercise.

<a id="run20"></a>
## 22. Run #20 — Restore the correct expectation and succeed again

I restored `assert d["version"] == "3.0"` inside the existing Python validation. I did not leave the deliberately failing 99.0 expectation behind.

```powershell
git add .github/workflows/ci.yml
git commit -m "Day 29 - Restore smoke test validation after failure test"
git push origin main
```

Observed result: **Run #20**, **`2c1919a`**, **Success**, **1m 57s** total. S46 shows `26563ef..2c1919a main -> main`; S47 the in-progress run; S48 the successful list; S49 the success summary; S50 the capture/promotion log. The job duration is 1m 55s.

```text
Deployed revision: employee-api-00044-say
Promoting revision: employee-api-00044-say
Updating traffic...
Routing traffic........................done
Traffic:
  100% employee-api-00044-say
Traffic promotion completed
```

The captured and promoted names agree in the actual successful run. Smoke testing and revision verification both show success. This completed my positive test → negative test → restoration cycle, rather than ending with a deliberately broken workflow.

<a id="final-state"></a>
## 23. My final state, settings and traffic timeline

S51 is my final Cloud Run screenshot. It shows project `cloud-genai-learning`, service `employee-api`, region `europe-west2`, update completed and routing completed. The selected revision was deployed by `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com` using gcloud.

| Revision in final view | Normal traffic | Tag/context |
| --- | --- | --- |
| `employee-api-00044-say` | 100% | `candidate`; successful restored run |
| `employee-api-00043-cek` | 0% | Failed-smoke-test candidate identified in the learning explanation |
| `employee-api-00041-pow` | 0% | Previous successful production revision |

### My traffic timeline

| Stage | Candidate being discussed | Production/normal traffic evidence |
| --- | --- | --- |
| After #16 | 00039-voz at 0% | 00026-djg at 100%, observed S23 |
| After #17 | 00040-cil verified | Promotion not yet implemented in that run |
| After #18 | 00041-pow promoted | 00041-pow 100%; 00026-djg 0%, observed S38 |
| #19 failed gate | Later identified as 00043-cek | Promotion skipped; unchanged traffic expected absent outside changes |
| After #20 | 00044-say promoted | 00044-say 100%; 00043-cek and 00041-pow 0%, observed S51 |

### Saved settings visible on the selected final revision

| Setting | Displayed value | Meaning/effect I can recall | Evidence limit |
| --- | --- | --- | --- |
| Billing | Request-based | Selected billing mode | No original cost calculation was performed here |
| Startup CPU Boost | Enabled | Startup boost enabled | No measured startup comparison recorded |
| Concurrency | 1 | Request concurrency per instance | Does not serialize deployments or all instances globally |
| Request timeout | 300 seconds | Configured request deadline | No original choice rationale recorded in this Day 29 segment |
| Execution environment | Default | Default selection | No explicit resolved generation shown |
| Revision max instances | 3 | Revision-level instance setting | Not proof of global throughput or all service-level limits |
| Autoscaling factors | Default autoscaling factors | Defaults displayed | Internal values not displayed |
| Container port | 8080 | Port through which the container accepts service requests | Startup command not reproduced in this view |
| CPU limit | 1 | Displayed CPU limit | Memory not visible in this crop |
| Command and args | Container entrypoint | Uses the image's entrypoint | Dockerfile contents not shown here |
| Build and Source metadata | No information available | Metadata absent from this panel | Does not mean no build or source code existed |

The displayed image reference begins `europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/...`; its end is truncated in this console view. Earlier YAML shows the full Git-SHA-tagged reference. I do not invent a digest from the truncated panel.

I avoid presenting the displayed settings as new Day 29 choices when their original selection rationale was not discussed here. In particular, `max instances × request concurrency` is not a measured requests-per-second result. My lesson's key concurrency distinction was deployment-job coordination versus per-instance HTTP processing.

Older revisions remained visible at 0%. Zero traffic does not mean deletion. No revision deletion or deferred cleanup was demonstrated as completed.

The earlier candidate view S23 additionally shows **Memory limit 512MiB** and **Sandbox launcher Disabled**. Those are observed values for the selected 00039-voz candidate, not newly chosen Day29 settings or proof of off-screen fields in the final 00044-say crop. The count “Environment variables (3)” is visible there, but their names and values are below the crop, so I do not invent them.

### My six-run reference table

| Run | Commit | Total duration | Milestone | Screenshots |
| --- | --- | --- | --- | --- |
| #15 | 17e7b03 | 1m 42s | ID token generated | S12–S16 |
| #16 | 3b63660 | 1m 46s | Authenticated smoke test passed | S18–S22 |
| #17 | 01a95e3 | 1m 41s | Exact revision 00040-cil verified | S27–S31 |
| #18 | 06819dd | 1m 52s | Automatic promotion of 00041-pow | S33–S38 |
| #19 | 26563ef | 1m 41s | Intentional JSON failure; promotion skipped | S41–S45 |
| #20 | 2c1919a | 1m 57s | Restored validation; 00044-say promoted | S46–S51 |

<a id="controls"></a>
## 24. My production concerns: CI, CD, branches and approval

At the end I said I did not want GitHub Actions deploying on every commit. Developers may commit incomplete boilerplate with a compilation error. My clarification was to distinguish **CI validation** from **deployment**. Running build/tests on commits or PRs can be useful precisely because they catch invalid work. A failed build must not continue into deployment.

| Activity | Policy discussed | Status |
| --- | --- | --- |
| Compile/build, unit tests, quality/security checks | Usually automatic on commits/PRs | General release-process guidance |
| Docker build | Depends on cost and workflow | Policy choice |
| DEV deployment | Frequent when useful, per team policy | Future design choice |
| QA/SIT deployment | Approved builds plus functional/integration testing | Proposed process |
| Production release | Explicit approval, change window and rollback plan | Required direction for my real production concerns |

I had also assumed DEV, QA, SIT and PROD should each have a branch. The distinction is that branches control code changes, while environments identify where approved artifacts run. They may be related, but separate branches per environment are not a universal requirement.

A proposed practice was to build once, identify an immutable image digest and promote the same tested artifact through environments. That avoids treating separate rebuilds as automatically identical. This was a future improvement, not proof that my current SHA-tagged workflow already promotes by immutable digest.

### Why no_traffic is not production authorization

My operational concern was that plant users and management may associate a production problem with a deployment, even if I explain that the candidate got 0% normal traffic. Confidence, change windows and official approval matter.

`no_traffic: true` prevents the new revision automatically receiving normal service traffic at deployment. It still creates a revision inside the service and can involve configuration, startup, logs and resource activity. It is not a promise that nothing changed in production.

My Day 29 pipeline then **automatically promotes to 100% after the test**. The initial no-traffic setting therefore does not enforce a formal production approval process. I need both technical verification and an authorized release.

The future design discussed was separate CI and CD responsibilities: automatic code validation, then deployment only when the environment's release conditions are satisfied. Manual triggering or approved GitHub Environments were proposed production controls. No such control was verified as added during Day 29. I retain the working learning pipeline and record these controls as future work.

<a id="scope"></a>
## 25. My smoke test versus a complete MES/HMI transaction

My test proves specific behavior: the workflow could authenticate to the private candidate, receive HTTP 200, and satisfy three expected JSON values. It does not establish every CRUD endpoint, database operation, background job, downstream integration or production scenario.

My actual MES analogy was: **a service answering a basic request does not prove the complete Trigger → Echo → Steps → RX transaction**. Each business step and integration can still fail. QA and SIT are needed for wider functional/integration coverage, and production validation has its own requirements.

The root response check and `api_key_configured` flag are useful smoke signals. They are not an end-to-end test of the secret's use in every workflow. A successful promotion means my configured gates passed, not that the entire plant application was exhaustively tested.

I also said I could explain the flow but could not independently write the whole `ci.yml`. The next practice should develop implementation fluency by changing smaller pieces—such as making production approval necessary—while keeping the conceptual understanding I have built.

<a id="deferred"></a>
## 26. What I finished and what I deliberately deferred

**Finished in the exercise:** service-scoped Invoker grant, ID-token generation, authenticated candidate smoke test, deployment-job concurrency, revision capture and matching, named-revision 100% promotion, intentional assertion failure with skipped promotion, and restoration to a successful final run.

**Still deferred:** formal production release approval, broader application/integration tests, coordination with external deployment actors, post-promotion monitoring/rollback, and any old-revision cleanup decision. I do not describe these as already implemented.

My remaining race concern spans several moments: another actor can change the service-wide latest-created revision, move the tag before a request, or modify configuration after verification. My concurrency group covers participating jobs, and exact-name promotion improves target selection, but neither is a global deployment lock.

Blocking an unpromoted candidate is also different from reverting a revision that fails **after** promotion. The negative test demonstrated the former. No automatic post-promotion rollback was exercised. The earlier working revision was identified for manual recovery if needed, but I did not run a new rollback during this Day 29 sequence.

<a id="recall"></a>
## 27. My quick recall questions

| Question I want to answer months later | My answer |
| --- | --- |
| Who deploys, and who runs? | GitHub uses github-deploy-sa; Cloud Run runs the container with employee-api-sa as runtime identity. |
| Does actAs mint tokens? | It authorizes attaching a runtime identity; credential generation is a different capability. |
| Why three token stages? | GitHub proves identity to federation; access token serves Google APIs; ID token serves private application invocation. |
| How does Google find keys with only issuer configured? | OIDC discovery gives jwks_uri; Google retrieves GitHub's public keys over HTTPS. |
| How does the JWT reach Google? | The runner/auth libraries send it to the known STS HTTPS endpoint. |
| Why print-access-token? | Optional diagnostic proving access-token retrieval while discarding its value. |
| Why no new Token Creator role? | Existing Workload Identity User already supplied both token permissions for my federated principal. |
| Is audience my request destination? | Audience identifies the intended service; the request can target its candidate-tag URL. |
| Why compare revisions? | A mutable tag may no longer identify my captured candidate. |
| Why not latest? | Another deployment can change latest; named promotion selects the captured revision. |
| What did #19 prove? | HTTP 200 plus wrong JSON version produces AssertionError; verification/promotion were skipped. |
| Which failed edit was only caught in review? | Python assert placed as a Bash command; I corrected it before the negative run. |
| What was the final revision? | 00044-say, 100% normal traffic, candidate tag; prior 00041-pow and failed00043-cek at0%. |
| Does 0% mean no production change? | No. Revision deployment still happens, and my workflow later auto-promotes. |
| Does a green smoke test prove my whole MES transaction? | No; Trigger/Echo/Steps/RX and integrations need broader validation. |

<a id="coverage"></a>
## 28. My explicitly requested documentation items and where they are

| My explicit request | Preserved here | Original screenshot references |
| --- | --- | --- |
| Flowchart, missing-role scenarios and Day29 Invoker distinction | Sections 2–4 | S01–S05 |
| All six runtime/public-private/roles explanations | Section 3 | S01 and relevant IAM views |
| Who impersonates whom and why access plus ID tokens | Sections 5–7 | S06, S10–S11 |
| GitHub/Google connection and stamping analogy | Section 7 | S07–S09 |
| All five access-token verification explanations | Section 5 | S06, S10 |
| All four token-setting explanations and not-yet-calling clarification | Section 10 | S11–S16 |
| GitHub concurrency explanation | Section 14 | S24 |
| Tests, exit codes, HTTP404 and revision mismatch | Sections 15–17 | S25–S31 |
| Positive promotion, negative test and restoration | Sections 18–23 | S32–S51 |

This edition replaces the earlier partial documentation. The full original Day 29 sequence was reviewed in the browser, including the earlier security detour and 51 screenshot attachments, rather than relying on the five exchanges returned by the chat retrieval tool. Stale claims that those screenshots and explanations were inaccessible have been removed.

The separately uploaded Day26 document was part of a historical update request; these notes include the concepts revisited during Day29 without claiming that a new revised Day26 file was delivered here. Persistent Library saving is not available through the enabled tools. The two final deliverables are saved locally and provided with verified links.

<a id="screenshots"></a>
## 29. My complete screenshot index

The following index is generated from the verified 51-image workbook manifest. Each image begins at `A12` on its sheet. The workbook Index also provides the matching `Learning Notes` row. Intermediate, incorrect, corrected and final screens are retained separately.


| Screenshot / image location | Caption | Markdown section |
| --- | --- | --- |
| S01!A12 | IAM deployment flowchart | [roles](#roles) |
| S02!A12 | Private service authentication and ingress | [iam-setup](#iam-setup) |
| S03!A12 | Existing order-api-sa Invoker permission | [iam-setup](#iam-setup) |
| S04!A12 | New principal and Invoker role before saving | [iam-setup](#iam-setup) |
| S05!A12 | Both service accounts authorised as Invokers | [iam-setup](#iam-setup) |
| S06!A12 | Existing WIF and access-token verification YAML | [wif](#wif) |
| S07!A12 | Bare issuer URL returns 404 | [discovery](#discovery) |
| S08!A12 | OIDC discovery document and jwks_uri | [discovery](#discovery) |
| S09!A12 | GitHub public signing keys JSON | [discovery](#discovery) |
| S10!A12 | Workload Identity User binding on deployment account | [token-permission](#token-permission) |
| S11!A12 | ID-token generation YAML review | [token-settings](#token-settings) |
| S12!A12 | Run 15 commit and push | [run15](#run15) |
| S13!A12 | Run 15 workflow in progress | [run15](#run15) |
| S14!A12 | Run 15 workflow success list | [run15](#run15) |
| S15!A12 | Run 15 success summary | [run15](#run15) |
| S16!A12 | Run 15 token step passed | [run15](#run15) |
| S17!A12 | Authenticated smoke-test YAML | [smoke](#smoke) |
| S18!A12 | Run 16 commit and push | [run16](#run16) |
| S19!A12 | Run 16 workflow in progress | [run16](#run16) |
| S20!A12 | Run 16 workflow success list | [run16](#run16) |
| S21!A12 | Run 16 success summary | [run16](#run16) |
| S22!A12 | Run 16 authenticated HTTP 200 smoke test | [run16](#run16) |
| S23!A12 | Candidate 00039-voz at zero traffic | [revision](#revision) |
| S24!A12 | Job concurrency YAML | [concurrency](#concurrency) |
| S25!A12 | Capture deployed candidate revision YAML | [revision](#revision) |
| S26!A12 | Verify candidate revision YAML | [gates](#gates) |
| S27!A12 | Run 17 commit and push | [run17](#run17) |
| S28!A12 | Run 17 workflow in progress | [run17](#run17) |
| S29!A12 | Run 17 workflow success list | [run17](#run17) |
| S30!A12 | Run 17 success summary | [run17](#run17) |
| S31!A12 | Run 17 exact revision verified | [run17](#run17) |
| S32!A12 | Exact-revision promotion YAML | [promotion](#promotion) |
| S33!A12 | Run 18 commit and push | [run18](#run18) |
| S34!A12 | Run 18 workflow in progress | [run18](#run18) |
| S35!A12 | Run 18 workflow success list | [run18](#run18) |
| S36!A12 | Run 18 success summary | [run18](#run18) |
| S37!A12 | Run 18 promotes 00041-pow to 100 percent | [run18](#run18) |
| S38!A12 | Cloud Run confirms first automatic promotion | [run18](#run18) |
| S39!A12 | Incorrect assertion placed outside Python | [negative](#negative) |
| S40!A12 | Corrected assertion inside Python validation | [negative](#negative) |
| S41!A12 | Run 19 commit and push | [run19](#run19) |
| S42!A12 | Run 19 in progress | [run19](#run19) |
| S43!A12 | Run 19 intentionally failed | [run19](#run19) |
| S44!A12 | Run 19 failure summary | [run19](#run19) |
| S45!A12 | HTTP 200 then AssertionError; promotion skipped | [run19](#run19) |
| S46!A12 | Run 20 restoration push | [run20](#run20) |
| S47!A12 | Run 20 in progress | [run20](#run20) |
| S48!A12 | Run 20 succeeded | [run20](#run20) |
| S49!A12 | Run 20 success summary | [run20](#run20) |
| S50!A12 | Run 20 captured and promoted 00044-say | [run20](#run20) |
| S51!A12 | Final Cloud Run traffic and settings | [final-state](#final-state) |
