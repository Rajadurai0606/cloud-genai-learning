# Day 26 — My GitHub Actions CI and keyless Google Cloud publishing notes

Learning completed across 25–26 October 2026.

My initial plan estimated 60–90 minutes with about 80% practical work. That was a planning estimate, not a measured completion time; I continued the lesson across two days as the authentication questions expanded.

## 1. What I completed

I automated my existing `employee-api` FastAPI project. A push to `main` now starts GitHub Actions, checks out my code, configures Python, installs dependencies, runs pytest, builds a Docker image, prepares Google authentication through OIDC and Workload Identity Federation, verifies that temporary credentials can be obtained, configures Docker authentication, tags the image with the Git commit SHA and pushes it to Artifact Registry.

My final result is **CI with authenticated image publishing**. I did not add automated Cloud Run deployment. I deliberately finished this learning milestone before moving to deployment, revisions, verification and rollback in Day 27. The original broader plan included Cloud Run, but my actual completed scope stops at Artifact Registry.

I reused my existing application, tests, Dockerfile, GitHub repository, Google Cloud project, London Artifact Registry repository and existing Cloud Run service. In my MES work, a CI/CD team handles much of this process. This exercise helps me understand what that team automates: checking source code, testing, packaging, authenticating and delivering a version to the runtime platform.

I use these evidence labels in these notes and the workbook:

- **Teaching example:** explains an idea. It is not an operation I actually performed.
- **Entered/proposed:** a form or YAML was prepared, but this alone does not prove it was saved or run.
- **Saved:** the resource or policy was created or updated.
- **Observed:** a screenshot or run log demonstrates the result.
- **Deferred/unknown:** work left for later or information the evidence does not establish.

The companion workbook contains **85 original screenshot attachments**, embedded as images rather than external links. Screenshot IDs `S001`–`S085` connect these notes to its Index and workflow sheets. The screenshot register at the end gives exact sheet and row locations.

## 2. Repository and workflow structure

### My starting questions: is GitHub providing an OS, a server or application hosting?

CI means Continuous Integration: automatically checking integrated code through tests and builds. CD can mean Continuous Delivery or Continuous Deployment. In my learning sequence it referred to the later delivery/deployment stage: publishing a tested artifact and eventually deploying it to Cloud Run. Day 26 completed artifact publishing, while automated runtime deployment remained separate.

I initially compared `ci.yml` with a Dockerfile: both look like instructions for downloading tools, downloading code, installing dependencies and running commands. The useful distinction is their purpose.

| Item | What I understand now |
|---|---|
| Dockerfile | Instructions for building a container image |
| GitHub Actions YAML | Instructions for running automation, including which machine and steps to use |
| Workflow | The whole automation definition, here `Employee API CI` |
| Trigger | An event that starts it, here a push to `main`, with manual execution also enabled |
| Job | A collection of steps running on a runner, here the job ID `test` |
| Runner | The machine executing the job, here a temporary GitHub-hosted Ubuntu VM |
| Step | A reusable action or a shell command within the job |

`runs-on: ubuntu-latest` asks GitHub to provision a runner from a prepared Ubuntu VM image. It does not mean I manually download an Ubuntu ISO and install an operating system on each run. GitHub manages that execution environment.

My tests execute on that runner. Tests can load FastAPI and send simulated HTTP requests with `TestClient`; this does not necessarily start Uvicorn as a public server. The runner is an automation environment that is released after the job. Cloud Run is the platform that hosts my deployed API and handles application requests, starting or scaling instances according to its configuration and traffic.

The eventual division of responsibility is: GitHub tests and builds my image, authenticates, publishes it and can later ask Cloud Run to deploy it. Google Cloud hosts the deployed application. GitHub Actions is not my production API host.

### I verified my existing Git setup before creating another repository

In the local VS Code PowerShell terminal I used:

```powershell
git remote -v
git branch --show-current
git rev-parse --show-toplevel
```

`git remote -v` shows the configured remote names and fetch/push destinations. My remote is `origin`, connected to `Rajadurai0606/cloud-genai-learning`. `git branch --show-current` showed `main`. `git rev-parse --show-toplevel` identified the real Git repository root. These commands inspect configuration; they do not push or change application code. See **S001–S002**.

My paths were:

```text
Git repository root:
C:\Raja\Learning\python\new learning

FastAPI project:
C:\Raja\Learning\python\new learning\01-python-fastapi
```

This distinction changed where the workflow belonged:

```text
new learning/
├── .github/
│   └── workflows/
│       └── ci.yml
└── 01-python-fastapi/
    ├── app/
    ├── tests/
    ├── Dockerfile
    ├── requirements.txt
    ├── README.md
    └── test_mes_retry.py
```

GitHub discovers workflow files in **the repository root's** `.github/workflows/`. My FastAPI folder is not the Git root. An initial folder-layout example assumed the application folder was the root; after checking the actual root, I corrected that assumption. I also accidentally created a nested `.github` folder and later created another duplicate while adding diagnostics. These were real errors, not alternative valid workflow locations.

### Why I need defaults.run.working-directory

```yaml
defaults:
  run:
    working-directory: 01-python-fastapi
```

This job-level setting makes shell commands written under `run:` execute from my FastAPI folder. Without it, `pip install -r requirements.txt` searches for `new learning/requirements.txt`. With it, the command finds `new learning/01-python-fastapi/requirements.txt`.

It is similar to selecting the correct folder in PowerShell before running a command. It does **not** relocate `.github/workflows/ci.yml`, change where checkout downloads the repository, or make every `uses:` action run inside the application directory. It applies to `run:` shell steps. This distinction later explained my actual CI failure. See **S003–S004, S013–S017**.

### How I read the YAML

| Field or syntax | Meaning and practical effect in my workflow |
|---|---|
| `name: Employee API CI` | Friendly name displayed in Actions |
| `on:` | Events that can trigger this workflow |
| `push:` / `branches: [main]` | Run for pushes to `main` |
| `workflow_dispatch:` | Allow a manual start through GitHub |
| `jobs:` | Container for job definitions |
| `test:` | My job's identifier, not a command to run pytest by itself |
| `runs-on: ubuntu-latest` | Request a GitHub-hosted Ubuntu runner |
| `defaults.run.working-directory` | Set the folder for shell commands |
| `steps:` | Ordered operations inside this job |
| `- name:` | A readable label for a step in logs |
| `uses:` | Execute a reusable action |
| `with:` | Supply inputs to an action |
| `actions/checkout@v4` | Bring this repository's source snapshot onto the runner |
| `actions/setup-python@v5` | Configure the requested Python version |
| `python-version: '3.12'` | Use Python 3.12 for these checks |
| `run:` | Execute shell commands on the runner |
| `run: \|` | A literal multiline YAML string executed as a shell script |

Indentation expresses nesting. Job permissions and defaults belong under the job; individual steps align under `steps:`. The form `runs-on:` followed by an indented `ubuntu-latest` value was valid in my screenshots; the compact form is simply easier to read.

`python -m pip install --upgrade pip` upgrades pip for the selected Python. `pip install -r requirements.txt` reads the dependency list from that file. `python -m pytest -v` invokes pytest through Python and requests verbose test output. The `-v` pytest option is different from Git's `--short` option.

## 3. Git commands and staging

My workflow changes only become available to GitHub after I save, stage, commit and push them. A locally visible editor tab is not proof that the intended YAML has been saved or that GitHub received it.

```text
Create/edit YAML → save → stage → commit → push main → workflow runs
```

### My question: what does --short mean?

`git status` describes the working tree and staging area in detail. `git status --short` presents the same underlying status compactly. Its two status positions distinguish the index/staging area from the working tree.

| Short status | Meaning I use for recall |
|---|---|
| `??` | Untracked file or directory |
| `A ` | New file staged for addition |
| ` M` | Working copy modified but that modification not staged |
| `M ` | Modification staged |
| ` D` | Deleted in the working copy, deletion not staged |
| `D ` | Deletion staged |

My actual sequence showed `?? .github/`, then after staging the workflow, `A  .github/workflows/ci.yml`. Later `?? 01-python-fastapi/.github/` revealed a duplicate nested folder. See **S005–S007, S014–S015**.

Paths depend on my terminal folder. From inside `01-python-fastapi`, the root workflow is `../.github/workflows/ci.yml`. From the Git repository root it is `.github/workflows/ci.yml`. `../` means the parent folder; it does not indicate another GitHub repository.

### Commands and messages I used

From the repository root, my first workflow was staged and committed with:

```powershell
git status --short
git add .github/workflows/ci.yml
git status --short
git commit -m "Day 26 - Added GitHub Actions CI workflow for pytest"
git push origin main
```

When my terminal was inside the FastAPI subfolder, the equivalent initial staging command was:

```powershell
git add ../.github/workflows/ci.yml
```

`git add` stages selected content. `git commit -m` creates a commit with a message. `git push origin main` sends commits on `main` to the configured remote. I staged the workflow specifically rather than blindly staging all my learning or application files.

For each later workflow change, I saved the file and repeated `git add .github/workflows/ci.yml`, `git commit -m "..."`, and `git push origin main`. These were the actual commit messages in the learning sequence:

```text
Day 26 - Add CI working directory diagnostics
Day 26 - Fix CI working directory
Day 26 - Add Docker image build to CI pipeline
Day 26 - Add GCP authentication using Workload Identity Federation
Day 26 - Verify GCP authentication using gcloud
Day 26 - Push Docker image to Artifact Registry
```

Before Run 6, the white dot beside `ci.yml` in VS Code indicated unsaved changes. I needed `Ctrl+S` before staging; Git commits file contents saved on disk, not an unsaved editor buffer. See **S073–S074**.

## 4. CI debugging

### A working trigger and a failed job are different findings

My first push successfully triggered `Employee API CI`. Run 1 used commit `b9da2a9`, ran on `main`, lasted about 10 seconds and failed with exit code 1. This proved the workflow was discovered and its trigger worked. It did not prove the application tests failed.

Exit code 0 normally means success; a nonzero code indicates failure. Exit code 1 alone is not a diagnosis. I opened the failed `test` job, expanded the failed step and read the actual log. See **S007–S010**.

The log showed:

```text
Successfully installed pip-26.2.2
ERROR: Could not open requirements file:
[Errno 2] No such file or directory: 'requirements.txt'
```

Checkout and Python 3.12 setup passed. The pip upgrade passed because it did not need my local requirements file. Reading requirements failed, so pytest was not executed. I must not describe this as a pytest failure.

The run also displayed Node.js 20 deprecation notices for the action versions and an `ubuntu-latest` migration notice. These were separate warnings. They did not establish the cause of this missing-file error. Action-version review remained deferred after the working pipeline was established.

### I tested the missing-file hypothesis before changing dependencies

A runner sees the committed repository snapshot, not every file on my Windows laptop. One reasonable hypothesis was that requirements existed locally but had not been committed or pushed. I checked the GitHub Code view and ran locally:

```powershell
git ls-files 01-python-fastapi/requirements.txt
```

It printed:

```text
01-python-fastapi/requirements.txt
```

The file existed in GitHub as well. That ruled out the untracked/unpushed-file explanation. I did not need to recreate `requirements.txt` or change application code. See **S011–S012**.

### My diagnostic shell script

I temporarily placed this step before dependency installation:

```yaml
- name: Debug working directory
  run: |
    echo "Current directory:"
    pwd
    echo "Files:"
    ls -la
    echo "Requirements file:"
    ls -l requirements.txt
```

These are Linux commands because the runner is Ubuntu, even though I edit and push from Windows.

| Command | Question it answers | Explanation |
|---|---|---|
| `echo "Current directory:"` | Which information follows? | Print a label, like Python `print(...)` or C# `Console.WriteLine(...)` |
| `pwd` | Where is this shell running? | Print working directory; comparable to PowerShell `Get-Location` |
| `ls` | What is in this folder? | List entries; comparable to PowerShell `Get-ChildItem` |
| `ls -la` | What is here, including hidden entries and details? | `-l` gives long listing details; `-a` includes dot-prefixed hidden entries |
| `ls -l requirements.txt` | Can this shell see the exact required file? | Show that file's details or fail with a missing-file message |

The `|` preserves a multiline script in YAML. It is not a pipe between these commands. A single command could simply use `run: pwd`. A failing `ls -l requirements.txt` is useful evidence during diagnosis.

Early illustrative listings and sizes were examples. My final actual diagnostic output was:

```text
/home/runner/work/cloud-genai-learning/cloud-genai-learning/01-python-fastapi
```

It showed `app/`, `tests/`, `Dockerfile`, `README.md`, `requirements.txt` and `test_mes_retry.py`. The requirements file was **2,902 bytes**. This actual output is preserved in **S021**, not replaced with a recreated diagram.

### Two distinct mistakes needed correction

First, my diagnostic edits were in `01-python-fastapi/.github/workflows/ci.yml`, a duplicate that GitHub would not use. Git status showed the nested `.github` as untracked. I copied the diagnostic changes into the root workflow, saved the correct file, removed the unnecessary duplicate after checking its contents and checked status again.

Second, when I inspected the actual workflow committed to GitHub, it was missing:

```yaml
defaults:
  run:
    working-directory: 01-python-fastapi
```

The root workflow was running commands at the repository root while the file was one folder below it. Moving the workflow alone did not fix that execution directory. Restoring this block fixed the dependency lookup. See **S013–S017**.

| Stage | What I established |
|---|---|
| First failure | Workflow discovered; requirements installation fails |
| Check remote and tracked files | requirements exists under the FastAPI subfolder |
| Check local edit location | Duplicate nested workflow was being edited |
| Inspect actual remote YAML | Job-level working directory was missing |
| Restore working directory | Shell commands execute in `01-python-fastapi` |
| Run 3 | Dependencies and pytest pass |
| Cleanup | Remove temporary diagnostics; retain correct defaults |

Run 2's diagnostic change appears as another failed run in the Actions history. The original history screenshot **S018** also establishes commit `1616d3c` and a displayed duration of 8 seconds. Run 3 is the verified successful fix, commit `f5a0f45`, 31 seconds. See **S018–S021**.

My practical debugging habit is to compare the actual committed workflow, the checkout layout and the runner's working directory before changing application code. A screenshot of correct YAML is configuration evidence; a successful run is execution evidence.

## 5. Run history and timings

| Run | Commit | Total duration | What this run actually established |
|---|---|---|---|
| 1 | `b9da2a9` | About 10 s | Trigger worked; dependency installation failed because requirements could not be opened |
| 2 | `1616d3c` | 8 s | Diagnostic revision failed in the visible history |
| 3 | `f5a0f45` | 31 s | Correct working directory; installation and pytest pass |
| 4 | `a018e13` | 1 min 9 s | Tests and Docker image build pass |
| 5 | `af47e66` | 1 min 1 s | Authentication action creates/cleans credentials configuration successfully |
| 6 | `9cdeb2b` | 1 min 10 s | Actual temporary Google access-token request succeeds |
| 7 | `5f0cfc1` | 1 min 28 s | Docker authentication, tag and actual registry push succeed |

The source screenshots establish step times for Run 3: checkout 2 s, Python setup 1 s, debug 0 s, dependencies 13 s, pytest 8 s. Run 4 showed checkout 2 s, Python setup 0 s, dependencies 15 s, pytest 9 s and Docker build 37 s. Run 7's push took 7 s. A displayed 0 s is a displayed duration, not proof that an operation consumed absolutely no time. The successful pytest step does not establish an individual test count where that count is not visible.

### Derived arithmetic for checking my units

These are calculations from the displayed timings, not a separate performance experiment or a prior retry/backoff exercise.

```text
Run 4 total = (1 min × 60 s/min) + 9 s = 69 s
Run 5 total = (1 min × 60 s/min) + 1 s = 61 s
Run 6 total = (1 min × 60 s/min) + 10 s = 70 s
Run 7 total = (1 min × 60 s/min) + 28 s = 88 s

Run 3 listed step subtotal = 2 + 1 + 0 + 13 + 8 = 24 s
Displayed total less listed steps = 31 - 24 = 7 s

Run 4 listed step subtotal = 2 + 0 + 15 + 9 + 37 = 63 s
Displayed total less listed steps = 69 - 63 = 6 s
```

The differences account for time outside the selected displayed steps, such as other job stages and timing boundaries. I did not measure a specific cause for each second. I should not force displayed step times to equal the workflow total or claim a speed improvement from runs that do different work. The workbook's Runs sheet calculates the conversions and subtotals from numeric inputs.

## 6. Docker build

After Run 3 passed, I removed the temporary debug step and added:

```yaml
- name: Build Docker image
  run: docker build -t employee-api:ci .
```

| Part | Meaning |
|---|---|
| `docker build` | Build an image using the Dockerfile |
| `-t` | Assign an image name and tag |
| `employee-api` | Local image name |
| `ci` | Local tag for this CI build |
| `.` | Current directory is the build context |

Because my shell working directory is `01-python-fastapi`, the context contains my application and Dockerfile. The build step follows pytest. With normal step success conditions, a failed pytest prevents the following Docker build from running. I do not want to package code that has failed its required automated checks.

My Dockerfile teaching example used `FROM python:3.12-slim`, `COPY requirements.txt .`, `RUN pip install -r requirements.txt` and `COPY . .` to explain image construction. The final observed build log showed `COPY . .`, exporting layers, naming and unpacking, and `DONE`. Files excluded by `.dockerignore` are outside the copied context. The destination of `COPY . .` depends on the Dockerfile's current working directory.

The log's local name `docker.io/library/employee-api:ci` did **not** prove a Docker Hub upload. Naming an image is different from pushing it. The image existed in the runner's Docker environment and would not automatically persist for another run after that temporary environment was released.

Run 4 proved GitHub could build my application without depending on Docker Desktop on my laptop. It did not publish to Artifact Registry or deploy Cloud Run. See **S022–S029**.

## 7. OIDC, WIF, signatures and my analogies

### Why building an image does not give GitHub access to Google Cloud

GitHub and Google Cloud are separate systems. Google must establish who is requesting access and whether that identity can perform the requested operation. A teaching push address ending in `employee-api:v4` illustrated the problem; it was not the final Day 26 publishing command.

One approach would store a long-lived service-account JSON key in GitHub Secrets. I chose WIF instead so my workflow can prove its external identity and obtain short-lived Google credentials without storing a permanent service-account private key.

| Concept | My personal understanding |
|---|---|
| Authentication | Establish which workload is making the request |
| Authorisation | Decide what that identity may do |
| OIDC: OpenID Connect | Standard used for GitHub's signed proof of workload identity |
| WIF: Workload Identity Federation | Google's configured trust arrangement for accepting external workload identities and exchanging credentials |
| STS: Security Token Service | Google service that executes verification and token exchange using provider configuration |
| Service account | Google robot identity I may be authorised to impersonate |
| IAM | Policies controlling impersonation and resource operations |

Direct WIF access is possible for supported resources. My actual implementation uses **service-account impersonation**, which adds the separate permission and credential stage described below.

### My Company A / Company B visitor-pass example

I imagined a visitor entering an office, receiving a pass at reception, being checked at a gate and being checked again at a building. The clarification was to make these **two companies**.

Company A is GitHub. Its OIDC service issues a signed visitor pass to the GitHub Actions runner. Company B is Google Cloud. Google checks the external pass and, if the configured rules pass, issues temporary Google credentials. Warehouse security then checks whether the authorised identity may deliver a Docker image to Artifact Registry.

The runner represents an automated workload, not me as a human standing at reception. An illustrative pass contains issuer, repository, branch/reference, intended audience and short expiry. This is a teaching representation of claims, not an actual token I copied out of the workflow.

### My question: what stops someone copying the repository and branch onto a fake token?

GitHub digitally signs tokens with its **private cryptographic key**. Google retrieves GitHub's corresponding **public verification key** and uses it to verify the signature and detect alteration. A fake token with convincing text still fails without a valid signature.

My easiest memory aid is:

- Private key: Company A's **secret stamping machine**, kept inside Company A.
- Signed token: the **visitor pass bearing Company A's stamp**.
- Public key: the **actual public stamp-verification tool** that Company B can obtain.

I was confused when an earlier explanation said Google never receives “the key.” The correct statement is that Google never receives GitHub's **private** key. Google does receive the **public** key. That public key is real cryptographic material used for verification, not just a manual telling Google what to do. Possessing it does not allow Google or another party to sign valid GitHub tokens.

### How does Google know it retrieved GitHub's real public key?

As administrator I configured the trusted issuer:

```text
https://token.actions.githubusercontent.com
```

Google uses OIDC discovery and the issuer's JWKS, a JSON Web Key Set, to find and retrieve public verification keys. The connection is HTTPS, not unprotected HTTP. TLS certificate verification helps establish that the keys come from the configured issuer's legitimate endpoint.

```text
Trusted HTTPS certificate authorities
  → GitHub's official HTTPS endpoint
  → published public verification keys
  → validation of the signed token
```

Google does not blindly use a key handed over by a stranger presenting a pass. It follows the configured trusted issuer. It also checks issuer, expiry, audience and my configured claim conditions. I did not manually upload the private key, select a custom cryptographic algorithm or write code that verifies the signature.

### Two separate routes cleared up my “token in a room” confusion

I initially imagined GitHub keeping a token in a room that Google visits. The actual routes are:

```text
Signed-token route:
Runner requests token → GitHub OIDC issues and returns it → runner presents it to Google STS

Public-key route:
Google verification infrastructure → trusted GitHub HTTPS discovery/JWKS endpoint → public keys
```

Google does not retrieve my individual workflow token from the public-key endpoint. GitHub's OIDC service does not directly deliver the token to Google. The runner carries it through the authentication process.

### Pool, Provider and STS: my department and library examples

My first analogy was an External Contractor Registration Department. I wondered whether visitors physically enter details in a register or whether the pool routes Company A to a provider. The corrected understanding is that the pool is a **namespace and management boundary**, containing provider configurations. It is not a token database, a visitor log or a traffic router. The workflow explicitly identifies its provider.

My library example was easier to recall:

| My analogy | Actual component | Important limit of the analogy |
|---|---|---|
| Library | Workload Identity Pool `github-pool` | Organises external identities and providers, not stored visitor tokens |
| GitHub or GitLab section | Imaginary grouping of verification books | Real pools do not require separate “section” objects |
| Book | Provider `github-provider` | Configuration describing issuer, mappings and conditions |
| Librarian reading and applying the book | Google STS | Actual verifier and exchanger; it is a Google service, not a process hosted inside my pool |
| Robot | `github-deploy-sa` | Identity used after authorised impersonation |
| Warehouse security | IAM/resource checks | Determines permitted operations |
| Warehouse | Artifact Registry repository | Stores my published Docker artifacts |

The Provider is the instruction book; it does not itself act as a server converting tokens. **STS performs the actual verification and exchange.** GitHub supplies signed proof and public keys. I configure which issuers and workloads Google should accept. Google enforces that policy.

### Teaching scenarios that separate authenticity, trust and permission

| Scenario | Signature / trust result | Can it publish? |
|---|---|---|
| Forged or modified token claiming to be GitHub | Signature fails | No |
| Genuine GitHub token from another repository | Signature can pass; my repository condition fails | No |
| My repository on a feature branch | Genuine token; `main` reference condition fails | No |
| My repository on `main`, but no impersonation binding | Provider may accept identity; robot use is not authorised | No through my chosen impersonation setup |
| Accepted identity and impersonation, but only read access to registry | Authentication works; upload permission absent | No |
| My intended workload with required impersonation and Writer access | All required checks pass | Publishing is allowed, as later demonstrated by Run 7 |

These scenarios explain the boundaries. They are not claims that I ran each negative test against my Google project.

## 8. WIF configuration

### My pool and provider setup sequence

I opened IAM & Admin → Workload Identity Pools in project `cloud-genai-learning`, selected **Get started**, then completed the wizard's stages: create an identity pool, add a provider and configure provider attributes. See **S030–S045**.

| Field | My chosen value | Meaning, reason and effect |
|---|---|---|
| Pool name | `github-pool` | Human-readable name for my external GitHub identity boundary |
| Pool ID | `github-pool` | Resource identifier used in provider paths and IAM references; cannot be changed after creation |
| Pool description | `External GitHub Actions identities for CI/CD` | Records why I created it |
| Enabled pool | Enabled | Allows use of the configuration; does not grant access to resources |
| Provider type | OpenID Connect (OIDC) | Matches the tokens GitHub Actions issues; dropdown also offered AWS, SAML and X509 |
| Provider name and ID | `github-provider` | Identifies my specific GitHub verification configuration |
| Issuer URL | `https://token.actions.githubusercontent.com` | Trusted GitHub issuer used for discovery and token validation |
| JWK file (JSON) | Empty | Google discovers GitHub's public keys instead of using a manually uploaded file |
| Audiences | Default audience | Token must target this provider; I did not configure the alternative allowed-audiences list |

The form already displayed the future provider resource with my project number and pool. A populated form was not creation evidence. **S045** showed “Successfully created the pool and added the provider,” with both resources enabled. “No data is available for the selected time frame” was expected because no workload had used the new trust configuration yet.

### Attribute mapping translates claims into Google's identity attributes

`assertion` means the incoming token's claims. The mapped attributes let Google refer to that information in the external identity namespace and IAM bindings.

| Google attribute | GitHub token expression | Purpose |
|---|---|---|
| `google.subject` | `assertion.sub` | Required subject identity |
| `attribute.repository` | `assertion.repository` | Readable owner/repository name |
| `attribute.ref` | `assertion.ref` | Git reference such as `refs/heads/main` |
| `attribute.repository_id` | `assertion.repository_id` | Stable numeric repository identifier used by my principal set |

A teaching subject example was `repo:Rajadurai0606/cloud-genai-learning:ref:refs/heads/main`. I did not treat that explanatory string as a captured token.

The first attributes screenshot had an empty required OIDC subject field and visible validation. I entered `assertion.sub`, then added repository and ref. Later I added repository ID. The incomplete form and intermediate three-mapping state remain in the workbook so I can see the configuration evolve. See **S035–S040**.

### My initial condition and the numeric-ID improvement

My first condition checked readable repository and branch:

```text
assertion.repository == 'Rajadurai0606/cloud-genai-learning' &&
assertion.ref == 'refs/heads/main'
```

This is CEL, Common Expression Language. `&&` means every clause must be true. A valid GitHub signature alone would not restrict the shared GitHub issuer to my repository.

I strengthened the condition with the immutable repository ID. Names can change or be reused. A stable ID is like checking a permanent project identification number alongside its readable name.

I initially opened the wrong JSON endpoint:

```text
https://api.github.com/users/Rajadurai0606
```

It showed **128257476**, my GitHub account/user ID. The correct repository endpoint was:

```text
https://api.github.com/repos/Rajadurai0606/cloud-genai-learning
```

Its **top-level `id` is 1368433185**. I must not substitute `owner.id`, the user endpoint's ID or `node_id`. The illustrative number `123456789` was only an example. See the wrong lookup in **S041** and correction in **S042**.

My final saved provider condition was:

```text
assertion.repository_id == '1368433185' &&
assertion.repository == 'Rajadurai0606/cloud-genai-learning' &&
assertion.ref == 'refs/heads/main'
```

I retained all four mappings. **S043–S044** show different scroll positions within the small condition box, so together they show all clauses. Numeric owner-ID hardening was discussed as a possible broader approach; I did not add an owner-ID clause to this saved configuration.

My question was: “Where did I configure the authentic GitHub signature check? I only entered three attribute conditions.” Signature validation is handled through OIDC type, issuer configuration and key discovery. The CEL box contains my additional workload restrictions. They are separate checks working together.

## 9. OIDC provider explanations

### 1. Each configuration field explained using our analogy

| My field | My Company A / Company B analogy | What actually happens |
|---|---|---|
| Provider type: OIDC | Company B expects an electronically signed visitor pass, rather than another kind of identity document | Google applies OIDC token validation |
| Issuer URL | Company B knows Company A's official security-office address | Google identifies GitHub's trusted issuer and discovers public verification keys |
| JWK file: empty | I do not hand over a verification tool because Company B can obtain it from Company A's official office | Google retrieves the actual public cryptographic keys through discovery/JWKS |
| Default audience | The pass must say it is intended for Company B's designated entrance | Google checks that the token's intended recipient matches the provider configuration |

I keep “verification book” and “public key” distinct. The Provider book is configuration. The public key is the actual mathematical verification tool.

### 2. Let's follow a visitor arriving at Company B

1. **Provider type:** security expects the OIDC digitally signed pass format.
2. **Issuer:** security knows the official identity office is `https://token.actions.githubusercontent.com`.
3. **JWK discovery:** Google obtains the public stamp-verification tool over trusted HTTPS and verifies the pass's signature. It never receives GitHub's private stamping machine.
4. **Audience:** security checks that this pass targets the intended Google entrance, rather than a different system. Expiry and other required token validation also apply.
5. **Attribute conditions:** security checks my actual repository ID, repository name and `main` reference.
6. **Separate IAM checks:** an accepted visitor must still be permitted to use the deployment robot, and that robot must have the necessary warehouse permission.

The first five points describe validating and accepting the external proof. The sixth connects that accepted identity to my chosen resource-access path.

### 3. Audience — one example worth remembering

Suppose Company A issues two genuine passes:

| Pass | Issuer/signature | Intended recipient | Result at my Google entrance |
|---|---|---|---|
| A | Genuine GitHub signature | My configured WIF Provider | Audience matches; continue other checks |
| B | Genuine GitHub signature | An unrelated system | Audience fails; reject |

Both passes can have valid signatures. Authenticity is not enough: the intended recipient matters. In my setup, the default audience corresponds to the provider resource. The displayed provider address includes:

```text
https://iam.googleapis.com/projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

The authentication action knows the provider resource and can request the appropriate audience. I did not need to create a custom allowed-audiences list or manually specify another STS endpoint. These two passes are a teaching example, not captured tokens.

### 4. How is this different from Attribute Conditions?

| Question | Configuration answering it |
|---|---|
| Is the token from the expected issuer, authentic, valid and intended for this entrance? | OIDC provider settings and token validation |
| Even if genuine, is this the approved repository and branch? | Provider attribute conditions |
| Which external identities receive this account-level role? | Attribute-specific principal set in an IAM binding |
| May that identity operate `github-deploy-sa`? | Workload Identity User on that service account |
| May the robot upload/manage artifacts in this warehouse? | Artifact Registry Writer on `employee-api` |

I remember the sequence as **pass format → issuer → public verification tool → intended entrance → approved workload → authorised robot → permitted warehouse operation**. Neither pool creation nor a genuine GitHub pass automatically grants registry access.

## 10. Service accounts and IAM

### I kept runtime and deployment robots separate

My existing accounts included the default compute service account, `employee-api-sa` for my Cloud Run application's runtime and `order-api-sa` used by the order application to call private services. I did not reuse those as the deployment identity. See **S046–S050**.

| Identity | Used by | Responsibility |
|---|---|---|
| `employee-api-sa` | Running application | Access permitted application resources, such as its allowed Secret Manager secret |
| `order-api-sa` | Order application | Existing service-to-service responsibility |
| `github-deploy-sa` | GitHub workflow | Publish images; future deployment permission is a separate later decision |

This separates application privileges from pipeline privileges. A runtime identity does not automatically need to deploy services, and a publishing identity does not automatically need every application secret.

I created `github-deploy-sa` with the ID `github-deploy-sa` and description **Service account for GitHub Actions CI/CD deployment**, in project `cloud-genai-learning`. I left optional project roles empty, left service-account users/admins empty in the creation wizard, finished the wizard and verified the account was enabled with **no user-managed keys**.

Creating the robot did not give it warehouse keys or allow GitHub to operate it. Those were two separate IAM grants.

### Grant A: who may use my deployment robot?

In the service account I distinguished **Permissions** from **Principals with access**. The first concerns permissions held by the robot over resources. The second concerns identities allowed to use or administer the robot. I opened Principals with access → Grant access on the specific `github-deploy-sa` resource.

Existing inherited entries included the default compute account with Editor and my human account with Owner. I did not change them during this exercise. The broad default-compute Editor grant was noted for a separate later review.

The grant form initially selected **Service Account Admin**. That was too broad and not my intended role. I changed it before saving. See **S051–S055**.

| Field | Actually saved |
|---|---|
| Protected resource | `github-deploy-sa` service account |
| Principal | The repository-ID principal set in section 11 |
| Role | Workload Identity User, `roles/iam.workloadIdentityUser` |
| Additional IAM condition | Empty |

The existing Provider condition already restricted repository and branch. The IAM principal set identifies which recognised external identities receive the impersonation role. Without the binding, Google could recognise a genuine accepted workload but still deny use of this service account.

### Grant B: what may the robot do at the warehouse?

I opened Artifact Registry, verified `employee-api` was the existing **Standard Docker** repository in **europe-west2**, returned to the repository list, selected its checkbox, opened the information/Permissions panel and selected Add principal. Selecting the repository for IAM is different from opening the image list. See **S056–S063**.

| Field | Actually saved | Why |
|---|---|---|
| Resource | `employee-api` repository only | Limit scope to this warehouse |
| Principal | `github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com` | Give the deployment robot resource access |
| Role | Artifact Registry Writer, `roles/artifactregistry.writer` | Permit required publishing operations |
| Additional IAM condition | Empty | No extra condition was entered here |

Writer is broader than a permission to upload one image: it includes reading and artifact-management operations covered by that role. Limiting the binding to this repository still matters. I did not grant project-wide Writer, Editor or Owner to the new deployment account.

The policy-updated notification said changes may take a few minutes to become active. A collapsed `Artifact Registry Writer (1)` role confirmed a saved role group but did not show who received it. I expanded the role and verified the exact deployment-account email. That final inspection was **S063**.

I paused after the initial policy save because the session was long, then resumed Day 26 by confirming the Writer principal before editing authentication YAML. I did not recreate completed resources.

### My service-account email question

```text
github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com
```

| Part | Meaning | My analogy |
|---|---|---|
| `github-deploy-sa` | Service account ID | Robot's name/ID |
| `@` | Separates identity from its domain | Boundary between robot name and organisation |
| `cloud-genai-learning` | Project ID where the account was created | Company B department |
| `iam.gserviceaccount.com` | Google's service-account identity domain | Official robot identity system |

The general form is `SERVICE_ACCOUNT_ID@PROJECT_ID.iam.gserviceaccount.com`. My runtime identity `employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com` follows the same structure. These are IAM identities, not ordinary personal email inboxes.

| Binding | Principal | Role | Resource | Question answered |
|---|---|---|---|---|
| Impersonation | External repository principal set | Workload Identity User | Deployment service account | Who may operate the robot? |
| Resource access | Deployment account email | Artifact Registry Writer | Selected repository | What may the robot do there? |

## 11. Principal identifiers

### What does the principal address actually do?

I entered this under New principals on the deployment service account:

```text
principalSet://iam.googleapis.com/projects/972261256506/locations/global/workloadIdentityPools/github-pool/attribute.repository_id/1368433185
```

It identifies the **set of external identities** whose mapped `repository_id` equals my repository's ID within that pool. Saving it with a role and resource creates the permission binding. The string alone does not create an identity, issue a token or grant warehouse access.

| Component | Meaning |
|---|---|
| `principalSet://` | A set of principals sharing an attribute/group, rather than one individual subject |
| `iam.googleapis.com` | IAM principal namespace; not a website I need to browse |
| `projects/972261256506` | Numeric project number of the project containing the pool |
| `locations/global` | Location of the WIF pool resource |
| `workloadIdentityPools/github-pool` | Exact pool identity namespace |
| `attribute.repository_id` | Custom mapped Google attribute |
| `1368433185` | Approved GitHub repository ID |

`principal://` identifies one particular federated subject; `principalSet://` can identify many workflow executions matching my repository attribute. I do not create a new IAM binding for every run.

### How would I construct it independently?

```text
principalSet://iam.googleapis.com/projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/attribute.ATTRIBUTE_NAME/ATTRIBUTE_VALUE
```

I obtain the project number from Google Cloud Project Settings or the generated provider resource path, the pool ID from pool details, the attribute name from my mapping and its expected value from the GitHub repository JSON.

| Value | Mine |
|---|---|
| Project ID | `cloud-genai-learning` |
| Project number | `972261256506` |
| Pool ID | `github-pool` |
| Attribute name | `repository_id` |
| Attribute value | `1368433185` |

Project ID and project number are not interchangeable. The principal identifier uses the numeric **project number**. My question “Where can I see `projects/972261256506`?” was answered by Project Settings and the default-audience provider address already shown by the console.

The provider name does not appear in this principal-set path. It refers to the pool's mapped identity attribute:

```text
Incoming assertion.repository_id = "1368433185"
  → attribute.repository_id = "1368433185"
  → matching principalSet receives Workload Identity User
```

If I later add another provider to the same pool, its mappings must not unintentionally produce identities that qualify for this binding. The address does not inherently distinguish providers. My Day 26 setup contained the configured GitHub provider.

I need both the Provider condition and the principal-set binding: the condition restricts which external passes Google accepts, while the binding decides which accepted identities may impersonate this particular account. See **S039–S044, S054–S055**.

## 12. GitHub OIDC requests

### Which repository does contents: read refer to?

I thought `on.push.branches: [main]` might identify the repository. It specifies **when** the workflow runs. The workflow's location inside `Rajadurai0606/cloud-genai-learning/.github/workflows/ci.yml` establishes the repository context.

`contents: read` grants the job's GitHub token permission to read repository contents for the normal current-repository checkout. `actions/checkout@v4` performs the download. It does not grant access to every private repository.

My office equivalent is: department = repository, push = event telling me to begin, permission = ability to read departmental documents, checkout = actually collecting them.

### Why is id-token: write named “write” when I am asking for a pass?

```yaml
permissions:
  contents: read
  id-token: write
```

I repeatedly associated “write” with sending a token to Google or modifying Google resources. Here it is GitHub's permission name for requesting issuance/retrieval of a **new identity token**. It is permission to ask Company A reception to create a visitor pass, not permission for reception to deliver it to Company B.

| GitHub permission | What it allows |
|---|---|
| `contents: read` | Read repository contents |
| `contents: write` | Modify repository contents, subject to other restrictions |
| `id-token: write` | Request a new GitHub-issued OIDC token |
| `id-token: read` | Not a supported way to request the OIDC token |

`id-token: write` does not by itself modify my repository, write GCP resources or grant Artifact Registry Writer. That last permission is configured in Google IAM. See **S064–S065**.

### Who requests, issues, returns and presents the signed token?

| Step | Actor | Destination or action |
|---|---|---|
| 1 | Authentication action executing on the runner | Requests an OIDC token from GitHub, enabled by job permission |
| 2 | GitHub OIDC service | Creates/signs token and returns it to the runner |
| 3 | Runner's authentication/credential process | Presents the signed token to Google STS |
| 4 | Google verification infrastructure | Retrieves trusted public keys separately through GitHub HTTPS discovery/JWKS |
| 5 | Google STS | Validates token using Provider settings and returns a federated credential if accepted |
| 6 | Google IAM Credentials service | Checks authorised impersonation and issues temporary service-account credentials |

My mistaken model was “GitHub OIDC sends directly to Google, then the Provider converts the token.” The corrected model is: **OIDC issues to the runner; the runner presents; the Provider is configuration; STS exchanges.**

### How does the runner know my Google project and account?

These values are in my actual YAML:

```yaml
- name: Authenticate to Google Cloud
  id: auth
  uses: google-github-actions/auth@v3
  with:
    project_id: cloud-genai-learning
    workload_identity_provider: projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider
    service_account: github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com
```

`uses` selects Google's reusable authentication action. `project_id` selects my project context. `workload_identity_provider` names the exact trust configuration. `service_account` identifies the robot I want to impersonate. `id: auth` gives the step an identifier. The action knows the standard authentication endpoints; I did not supply a separate STS URL.

These resource identifiers are instructions for obtaining credentials, not usernames/passwords, private keys or permanent access tokens. It is like instructing the employee: go to Company B through the `github-provider` arrangement and request `github-deploy-sa`.

## 13. Configuration and temporary credentials

### Why a green auth step was not my final authentication proof

Run 5, commit `af47e66`, passed in 61 seconds after adding job permissions and the authentication action. Its logs showed creation of a file like:

```text
/home/runner/work/cloud-genai-learning/cloud-genai-learning/gha-creds-....json
```

Cleanup later removed the exported credentials file. The variable filename is shown as an example pattern, not a filename I need to reuse. The log inputs showed `create_credentials_file: true`, `export_environment_variables: true` and `cleanup_credentials: true`. See **S066–S072**.

This was an **external-account credentials configuration file**, not a downloaded service-account private key. It prepared later tools to obtain credentials. A green action alone did not necessarily prove that STS had exchanged credentials, that service-account impersonation completed or that a repository operation was authorised.

### My question: where does gcloud find the configured credentials?

I wondered whether `gcloud auth print-access-token` was like a human opening a CLI and logging into a project. In a manual local workflow, `gcloud auth login` can open a browser for a human sign-in. My automated workflow uses the configuration already prepared by `auth@v3`.

| Exported environment variable | Meaning in this workflow |
|---|---|
| `CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE` | Points the gcloud CLI to the generated credentials configuration |
| `GOOGLE_APPLICATION_CREDENTIALS` | Makes that credentials configuration discoverable to Google client libraries |
| `GOOGLE_GHA_CREDS_PATH` | Exported path to the generated GitHub Action credentials file |

These variables store paths/configuration references, not a printed token placed into each variable. I did not repeat the provider and account inputs on every later command. I also must not assume every unrelated tool reads these variables directly.

### Requesting credentials is different from issuing them

I asked why `gcloud` was described as requesting credentials when STS was described as issuing them. Those are the two sides of one process. The employee asks security for access; security checks the pass and issues access if authorised.

| Credential | Issuer | Purpose |
|---|---|---|
| GitHub OIDC token | GitHub OIDC service | Signed proof of the workflow identity |
| Federated Google credential | Google STS | Represents the accepted external identity |
| Service-account access token | Google IAM Credentials service | Allows permitted API calls as `github-deploy-sa` |

There are two Google credential stages because I chose service-account impersonation. `gcloud` initiates a request and receives/uses the result; it does not mint Google's access tokens itself.

### My actual validation step

```yaml
- name: Set up Google Cloud CLI
  uses: google-github-actions/setup-gcloud@v3

- name: Verify Google Cloud authentication
  run: |
    gcloud auth print-access-token > /dev/null
    echo "Google Cloud authentication verified"
```

`setup-gcloud@v3` makes the CLI available. `print-access-token` uses the existing configuration to request temporary credentials. `> /dev/null` redirects the printed sensitive token to Linux's discard destination. It hides output; it does not skip verification or prevent the request.

The second command prints an ordinary success message. GitHub's normal bash error handling causes a failing preceding command to fail the step; explicit `set -e` was discussed as a way to make such error handling clear. I did not add `set -e` as a separately evidenced saved line in this historical YAML.

Run 6, commit `9cdeb2b`, passed in 70 seconds. Its expanded logs showed the command, the environment paths and **Google Cloud authentication verified**. This is stronger evidence than merely creating the file. It still did not test an actual registry operation. See **S073–S076**.

### My recurring confusion: which operation creates reusable configuration?

| Step | Creates or updates configuration? | Actual role |
|---|---|---|
| `google-github-actions/auth@v3` | Yes | Create WIF external-account configuration and export paths |
| `gcloud auth print-access-token` | No new reusable auth configuration | Use the configuration to request a real temporary token |
| `gcloud auth configure-docker` | Yes, Docker configuration | Tell Docker which helper to use for this registry |
| `docker push` | No new configuration required | Obtain/use credentials through the helper and upload |

My instruction document is reusable configuration. My temporary pass is an actual credential. I redirected the test token output and did not manually save it for Docker. Google tooling may reuse an unexpired cached token or request another one, but the print command is not the creator of the reusable configuration and does not guarantee a token was saved for subsequent Docker commands.

## 14. Docker authentication, tag and push

### Why Docker needs an extra configuration step

I understood that the auth action created a file and exported paths for later steps. My next question was whether Docker would therefore simply use that file. Docker is a separate tool: with my chosen approach it consults **its own** configuration, rather than directly parsing the WIF file or automatically reading `GOOGLE_APPLICATION_CREDENTIALS`.

```yaml
- name: Configure Docker authentication
  run: gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet
```

This registers Google's helper for the London registry host, normally in `~/.docker/config.json`. `--quiet` avoids an interactive confirmation during unattended CI. It does not upload an image or grant any new IAM role. See **S077**.

The conceptual Docker configuration is:

```json
{
  "credHelpers": {
    "europe-west2-docker.pkg.dev": "gcloud"
  }
}
```

This JSON illustrates the effect of the command. I did not capture Docker's actual file contents as a separate screenshot. It maps a registry host to the helper name, not directly to `gha-creds-*.json`.

### My question: docker push just uploads, so why invoke a helper?

Artifact Registry is a protected warehouse. Before accepting delivery, it needs credentials identifying the uploader and IAM permission authorising the operation. During registry interaction, Docker can receive an authentication challenge and use its configured helper to supply credentials.

| Tool | Where authentication comes from |
|---|---|
| gcloud | Configuration discovered through the exported credential override |
| Google Python client libraries | Commonly the path in `GOOGLE_APPLICATION_CREDENTIALS` |
| Docker CLI | Registry-specific settings in Docker's `config.json` |
| Docker's gcloud helper | Existing gcloud/WIF identity, used to obtain valid temporary credentials |

The driver analogy helped: Docker is the delivery driver, the image is the package, the helper is the security assistant who can obtain a pass and Artifact Registry is the warehouse. `configure-docker` tells the driver which assistant to ask when visiting this warehouse. `docker push` tells the driver to deliver the package. The driver then uses those instructions automatically.

### My question: where is the explicit helper invocation in the push command?

I correctly noticed that no additional helper command was written in YAML. The invocation is internal to Docker's normal credential process:

```text
docker push identifies europe-west2-docker.pkg.dev
  → Docker reads credHelpers for that host
  → Docker invokes docker-credential-gcloud automatically
  → helper uses configured Google identity to supply a valid access token
  → registry authenticates the request and checks Writer permission
  → authorised layers/manifest are uploaded
```

I do not manually invoke the helper or insert the token into the `docker push` command. The helper can use an existing valid cached token or obtain one using STS/IAM Credentials as necessary. Those are logical dependencies, not a claim that every push always repeats every exchange from scratch.

### My full image address

```text
europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:<tag>
```

| Part | Meaning |
|---|---|
| `europe-west2-docker.pkg.dev` | London Docker registry endpoint |
| `cloud-genai-learning` | Google project ID |
| First `employee-api` | Artifact Registry repository |
| Second `employee-api` | Docker image name inside that repository |
| Text after `:` | Image version tag |

Repository and image happen to have the same name but are different objects. An early example used `:ci`; my final publishing workflow uses the full Git commit SHA.

### My question: what is github.sha, and does it create a new SHA?

`github.sha` is the commit identifier associated with the run. For this push-to-main workflow it identifies the commit that triggered the run. `github` is GitHub Actions' context; `sha` is a value in it; `${{ ... }}` evaluates an expression and inserts its value.

`git commit` creates a commit and its ID. `git push` sends it to GitHub. The workflow starts, reads `${{ github.sha }}` and uses that existing value as the image tag. The expression does not create another commit or a new SHA.

A full SHA in my examples has 40 hexadecimal characters; short forms such as `af47e66` and `9cdeb2b` are display abbreviations. Examples like `abc123def456...` and `a1b2c3d` were illustrative, not real final image tags. I do not need to find and type the new SHA manually.

### Tagging and publishing are separate operations

```yaml
- name: Tag Docker image for Artifact Registry
  run: |
    docker tag employee-api:ci europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}

- name: Push Docker image to Artifact Registry
  run: |
    docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
```

`docker tag` adds another local name to the existing image. It does not rebuild or upload it. `employee-api:ci` is the package prepared at the factory; the full registry address is its delivery address; the commit tag is its source-version label. The push destination must match the tag destination exactly. See **S078–S079**.

Commit tags help trace an image back to the source code and select a previous tested version for a future rollback. Tags are labels and can technically be overwritten. An image **digest** is the stronger content identifier for an exact artifact. A Git commit SHA and an image digest identify different things, even though both use hash-like strings.

### Reading my actual push logs

Run 7, commit `5f0cfc1`, completed in 88 seconds, with the push taking 7 seconds. Tests, build, auth setup, credential verification, Docker helper configuration, tag and push all passed. See **S080–S084**.

| Log | Meaning |
|---|---|
| `Waiting` | Layer waits for processing/upload |
| `Layer already exists` | Identical layer is already stored and can be reused |
| `Pushed` | That layer was uploaded successfully |
| `digest: sha256:...` | Content identifier for the resulting image manifest |

I must not treat `Layer already exists` as an error or assume every layer must upload again. The final digest was reported with a prefix beginning `7eda6e9022d89b15...`. It is a Docker artifact digest, not the Git source commit.

## 15. Final state and deferred work

I opened the `employee-api` image's versions/tags in Artifact Registry and verified the published version. **S085** shows:

| Item | Observed final value |
|---|---|
| Project | `cloud-genai-learning` |
| Region | `europe-west2` |
| Repository | `employee-api` |
| Image | `employee-api` |
| Full Git commit tag | `5f0cfc19fcf917026a43c1a6c48361a82ecaa94` |
| Tagged image digest prefix | `7eda6e9022d8` |
| Publishing result | Successful |

The Git tag matches Run 7 and the digest prefix matches the push result. This links source commit, successful publishing run and stored artifact.

The versions view also showed associated entries beginning `b6eaa1359fed` and `a101f32ad4ba`. They may be manifests or OCI-related metadata, but I did not inspect their details sufficiently to identify them. I do not label them definitively as a particular artifact type. Their presence does not undo the verified tagged-image result.

My final sequence is:

```text
Push main → checkout → Python setup → dependencies → pytest
  → Docker build → prepare WIF credentials configuration
  → set up gcloud → request/verify temporary access token
  → register Docker helper → tag with commit SHA
  → push image → verify stored version in Artifact Registry
```

I did not create a long-lived service-account JSON key. I did not add Cloud Run deployment to this YAML, so this workflow did not deploy a new Cloud Run revision. Deployment permission, revision inspection, testing and rollback belong to the next lesson. I also deferred reviewing the inherited broad default-compute Editor role and action-version warnings. The diagnostic step was already removed after fixing CI; I retained its original screenshot and explanation here.

## 16. Quick recall guide

| If I forget… | My recall sentence | Evidence |
|---|---|---|
| Root versus application folder | Workflow lives at Git root; run commands can default to the FastAPI subfolder | S001–S004, S017 |
| Missing requirements error | Check actual committed YAML and runner directory before changing dependencies | S010–S021 |
| VM versus hosted API | GitHub runs temporary automation; Cloud Run serves my API | Section 2 |
| Local Docker naming | Build/tag are local; push transfers to a registry | S023–S029, S078–S084 |
| OIDC versus WIF | GitHub issues identity proof; Google accepts it according to configured trust | Sections 7–9 |
| Public versus private key | Private stamp machine stays at GitHub; Google obtains the actual public verifier over HTTPS | Section 7 |
| Pool versus Provider versus STS | Library, verification book, librarian doing the work | Section 7 |
| Signature versus condition | Genuine pass is not enough; approved repository and branch must match | S036–S044 |
| Repository versus account ID | 1368433185 is repository; 128257476 is my GitHub user | S041–S042 |
| Two IAM grants | Visitor may use robot; robot may write to selected warehouse | S054–S063 |
| id-token: write | Permission to request a new pass from GitHub, not GCP write access | S064 |
| Auth file versus token | Configuration tells tools how to get credentials; access token is the actual temporary credential | S071–S076 |
| Requester versus issuer | gcloud requests; STS and IAM Credentials issue their respective credentials | Section 13 |
| Docker helper | configure-docker registers it; push calls it automatically | S077–S084 |
| Commit SHA versus digest | Source version label versus artifact-content identifier | S078, S084–S085 |
| Day 26 finish line | Image stored and verified; Cloud Run automation is Day 27 | S085 |

### My historical final workflow, assembled from the implemented steps

This is the complete learning configuration reconstructed from the reviewed steps and original YAML screenshots. It preserves the action versions used in Day 26; it is not a claim that I re-ran the workflow while writing these notes.

```yaml
name: Employee API CI

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    permissions:
      contents: read
      id-token: write

    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: 01-python-fastapi

    steps:
      - name: Checkout source code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run pytest
        run: python -m pytest -v

      - name: Build Docker image
        run: docker build -t employee-api:ci .

      - name: Authenticate to Google Cloud
        id: auth
        uses: google-github-actions/auth@v3
        with:
          project_id: cloud-genai-learning
          workload_identity_provider: projects/972261256506/locations/global/workloadIdentityPools/github-pool/providers/github-provider
          service_account: github-deploy-sa@cloud-genai-learning.iam.gserviceaccount.com

      - name: Set up Google Cloud CLI
        uses: google-github-actions/setup-gcloud@v3

      - name: Verify Google Cloud authentication
        run: |
          gcloud auth print-access-token > /dev/null
          echo "Google Cloud authentication verified"

      - name: Configure Docker authentication
        run: gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet

      - name: Tag Docker image for Artifact Registry
        run: |
          docker tag employee-api:ci europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}

      - name: Push Docker image to Artifact Registry
        run: |
          docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:${{ github.sha }}
```

### References I can use to locate my observed results

- [Run 4 — Docker build](https://github.com/Rajadurai0606/cloud-genai-learning/actions/runs/40181554848)
- [Run 6 — actual credential verification](https://github.com/Rajadurai0606/cloud-genai-learning/actions/runs/40387604644)
- [Run 7 — image publishing](https://github.com/Rajadurai0606/cloud-genai-learning/actions/runs/40394371429)
- [Artifact Registry repository](https://console.cloud.google.com/artifacts/docker/cloud-genai-learning/europe-west2/employee-api?project=cloud-genai-learning)
- [Repository JSON used for its numeric ID](https://api.github.com/repos/Rajadurai0606/cloud-genai-learning)

These links locate the historical resources. The embedded screenshots preserve what I observed during the exercise, independently of later changes to those resources.

## Screenshot register

The workbook's Index gives captions, evidence state, notes section and image locations. The following register is generated from the same image manifest as the workbook.

| Screenshot | Caption | Workbook location | Notes section |
|---|---|---|---|
| S001 | GitHub remote and main branch | CI setup!B7 (image B12) | 2. Repository and workflow structure |
| S002 | Locate the Git repository root | CI setup!B32 (image B37) | 2. Repository and workflow structure |
| S003 | Workflow initially inside FastAPI subfolder | CI setup!B46 (image B51) | 2. Repository and workflow structure |
| S004 | Root workflow folder retained | CI setup!B93 (image B98) | 2. Repository and workflow structure |
| S005 | Untracked workflow in Git short status | CI setup!B137 (image B142) | 3. Git commands and staging |
| S006 | Stage only the workflow file | CI setup!B157 (image B162) | 3. Git commands and staging |
| S007 | Commit and push initial CI workflow | CI setup!B177 (image B182) | 3. Git commands and staging |
| S008 | First workflow detected by GitHub | CI setup!B207 (image B212) | 4. CI debugging |
| S009 | Run 1 failure and warnings | CI setup!B256 (image B261) | 4. CI debugging |
| S010 | Expanded requirements file error | CI setup!B313 (image B318) | 4. CI debugging |
| S011 | requirements.txt exists remotely | CI setup!B373 (image B378) | 4. CI debugging |
| S012 | Git tracks the requirements file | CI setup!B426 (image B431) | 4. CI debugging |
| S013 | Temporary diagnostic step added | CI setup!B450 (image B455) | 4. CI debugging |
| S014 | Duplicate nested .github detected | CI setup!B504 (image B509) | 4. CI debugging |
| S015 | Root workflow now modified | CI setup!B525 (image B530) | 4. CI debugging |
| S016 | Committed workflow lacks working directory | CI setup!B546 (image B551) | 4. CI debugging |
| S017 | Working directory restored in remote YAML | CI setup!B606 (image B611) | 4. CI debugging |
| S018 | Run 3 succeeds after the correction | CI results!B7 (image B12) | 4. CI debugging |
| S019 | Run 3 summary | CI results!B63 (image B68) | 5. Run history and timings |
| S020 | Run 3 step results | CI results!B122 (image B127) | 4. CI debugging |
| S021 | Actual working-directory debug output | CI results!B180 (image B185) | 4. CI debugging |
| S022 | Clean workflow retains working directory | CI results!B240 (image B245) | 6. Docker build |
| S023 | Docker build placed after pytest | CI results!B292 (image B297) | 6. Docker build |
| S024 | Commit and push Docker build change | CI results!B340 (image B345) | 6. Docker build |
| S025 | Docker build run in progress | CI results!B368 (image B373) | 6. Docker build |
| S026 | Docker build run passes | CI results!B421 (image B426) | 6. Docker build |
| S027 | Run 4 summary | CI results!B477 (image B482) | 5. Run history and timings |
| S028 | Run 4 successful job steps | CI results!B535 (image B540) | 6. Docker build |
| S029 | Expanded Docker build log | CI results!B590 (image B595) | 6. Docker build |
| S030 | Workload Identity Federation entry page | WIF setup!B7 (image B12) | 8. WIF configuration |
| S031 | Blank identity pool form | WIF setup!B67 (image B72) | 8. WIF configuration |
| S032 | Pool details entered | WIF setup!B127 (image B132) | 8. WIF configuration |
| S033 | Identity provider type choices | WIF setup!B187 (image B192) | 8. WIF configuration |
| S034 | OIDC provider fields and audience options | WIF setup!B248 (image B253) | 8. WIF configuration |
| S035 | Required subject mapping initially empty | WIF setup!B309 (image B314) | 8. WIF configuration |
| S036 | Completed provider identity settings | WIF setup!B370 (image B375) | 9. OIDC provider explanations |
| S037 | Subject mapping entered | WIF setup!B431 (image B436) | 8. WIF configuration |
| S038 | Three mappings and name/branch condition | WIF setup!B492 (image B497) | 8. WIF configuration |
| S039 | Fourth repository ID mapping added | WIF setup!B553 (image B558) | 8. WIF configuration |
| S040 | Readable condition before ID strengthening | WIF setup!B614 (image B619) | 8. WIF configuration |
| S041 | Wrong lookup: GitHub user endpoint | WIF setup!B663 (image B668) | 8. WIF configuration |
| S042 | Correct lookup: GitHub repository endpoint | WIF setup!B708 (image B713) | 8. WIF configuration |
| S043 | Final CEL condition, first visible lines | WIF setup!B770 (image B775) | 8. WIF configuration |
| S044 | Final CEL condition, remaining visible lines | WIF setup!B831 (image B836) | 8. WIF configuration |
| S045 | Pool and provider successfully created | WIF setup!B892 (image B897) | 8. WIF configuration |
| S046 | Existing service accounts reviewed | IAM!B7 (image B12) | 10. Service accounts and IAM |
| S047 | Dedicated deployment account form | IAM!B65 (image B70) | 10. Service accounts and IAM |
| S048 | Service account created without project roles | IAM!B119 (image B124) | 10. Service accounts and IAM |
| S049 | Optional users and admins left empty | IAM!B181 (image B186) | 10. Service accounts and IAM |
| S050 | Deployment account enabled with no keys | IAM!B231 (image B236) | 10. Service accounts and IAM |
| S051 | Permissions versus principals with access | IAM!B290 (image B295) | 10. Service accounts and IAM |
| S052 | Inherited principals before WIF grant | IAM!B346 (image B351) | 10. Service accounts and IAM |
| S053 | Grant form initially selects Service Account Admin | IAM!B406 (image B411) | 10. Service accounts and IAM |
| S054 | Correct principal set and Workload Identity User | IAM!B467 (image B472) | 11. Principal identifiers |
| S055 | Impersonation policy updated | IAM!B528 (image B533) | 10. Service accounts and IAM |
| S056 | Existing Docker repository details | IAM!B590 (image B595) | 10. Service accounts and IAM |
| S057 | Repository list for scoped IAM | IAM!B638 (image B643) | 10. Service accounts and IAM |
| S058 | Select only employee-api repository | IAM!B678 (image B683) | 10. Service accounts and IAM |
| S059 | Repository permissions panel | IAM!B716 (image B721) | 10. Service accounts and IAM |
| S060 | Choose Artifact Registry Writer | IAM!B767 (image B772) | 10. Service accounts and IAM |
| S061 | Writer grant ready to save | IAM!B819 (image B824) | 10. Service accounts and IAM |
| S062 | Repository policy update confirmed | IAM!B871 (image B876) | 10. Service accounts and IAM |
| S063 | Expand Writer to verify exact principal | IAM!B932 (image B937) | 10. Service accounts and IAM |
| S064 | GitHub job permissions added | Google auth!B7 (image B12) | 12. GitHub OIDC requests |
| S065 | Google authentication action added | Google auth!B55 (image B60) | 13. Configuration and temporary credentials |
| S066 | Commit and push WIF workflow | Google auth!B91 (image B96) | 13. Configuration and temporary credentials |
| S067 | Run 5 initially running | Google auth!B123 (image B128) | 13. Configuration and temporary credentials |
| S068 | Run 5 passes | Google auth!B180 (image B185) | 13. Configuration and temporary credentials |
| S069 | Run 5 summary | Google auth!B238 (image B243) | 5. Run history and timings |
| S070 | Run 5 job steps | Google auth!B297 (image B302) | 13. Configuration and temporary credentials |
| S071 | Credentials file creation and cleanup | Google auth!B357 (image B362) | 13. Configuration and temporary credentials |
| S072 | Expanded auth defaults and resource values | Google auth!B417 (image B422) | 13. Configuration and temporary credentials |
| S073 | gcloud verification YAML and unsaved dot | Google auth!B476 (image B481) | 13. Configuration and temporary credentials |
| S074 | Commit and push credential verification | Google auth!B525 (image B530) | 13. Configuration and temporary credentials |
| S075 | Run 6 passes | Google auth!B556 (image B561) | 13. Configuration and temporary credentials |
| S076 | Expanded temporary-token verification | Google auth!B615 (image B620) | 13. Configuration and temporary credentials |
| S077 | Docker credential helper configured in YAML | Image publishing!B7 (image B12) | 14. Docker authentication, tag and push |
| S078 | Commit SHA tagging added | Image publishing!B52 (image B57) | 14. Docker authentication, tag and push |
| S079 | Docker push added after tagging | Image publishing!B97 (image B102) | 14. Docker authentication, tag and push |
| S080 | Commit and push image-publishing workflow | Image publishing!B139 (image B144) | 14. Docker authentication, tag and push |
| S081 | Run 7 passes | Image publishing!B169 (image B174) | 15. Final state and deferred work |
| S082 | All Run 7 job steps pass | Image publishing!B230 (image B235) | 15. Final state and deferred work |
| S083 | Docker push begins uploading layers | Image publishing!B290 (image B295) | 14. Docker authentication, tag and push |
| S084 | Docker push finishes with digest | Image publishing!B318 (image B323) | 14. Docker authentication, tag and push |
| S085 | Verify commit tag in Artifact Registry | Image publishing!B350 (image B355) | 15. Final state and deferred work |
