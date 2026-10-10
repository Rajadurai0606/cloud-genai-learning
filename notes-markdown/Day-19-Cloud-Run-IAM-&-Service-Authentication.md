# Day 19: Cloud Run IAM & Service Authentication

Learning date: 10 October 2026. Project: `cloud-genai-learning`. Region: `europe-west2`. Service: `employee-api`.

## The two access paths in this example

We built an Employee API on Cloud Run. It is private, so a person cannot simply open its URL and expect access. The application also needs an API key stored in Secret Manager. These are **two separate access decisions**:

1. **Can this user call the Employee API?** Cloud Run checks the caller's token and invoke permission.
2. **Can this application read its secret?** Secret Manager checks the application's runtime identity and secret access permission.

The first decision concerns the person outside the application. The second concerns the application doing its work. Passing one does not automatically pass the other.

| Remember this question                            | Access path 1: user calls the API                        | Access path 2: application accesses the secret                                                                            |
| ------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Who is asking?                                    | Your Google account, signed in to Cloud Shell / `gcloud` | The application's runtime service account, `employee-api-sa`                                                              |
| What is being requested?                          | An HTTP response from `employee-api`                     | The payload of a version of `EMPLOYEE_API_KEY`                                                                            |
| Who checks access?                                | Cloud Run's authentication and IAM layer                 | Secret Manager and IAM                                                                                                    |
| Which resource has the relevant permission grant? | The receiving Cloud Run service                          | The particular Secret Manager secret                                                                                      |
| What permission is needed?                        | `run.routes.invoke`                                      | `secretmanager.versions.access`                                                                                           |
| What role normally supplies it?                   | Cloud Run Invoker, `roles/run.invoker`                   | Secret Manager Secret Accessor, `roles/secretmanager.secretAccessor`                                                      |
| Which credential is involved?                     | An ID token sent as `Authorization: Bearer ...`          | Google-managed credentials for the runtime service account; a Google API access token when calling the Secret Manager API |
| Plain-language memory                             | **I may enter the API building.**                        | **The robot working inside may open its assigned safe.**                                                                  |

### Visual map: two routes, two permission checks

```mermaid
flowchart LR
    U[Your Google account] -->|HTTP request with bearer ID token| G[Cloud Run: token and invoke checks]
    G -->|Accepted request| A[employee-api application]
    A -. runs as .-> R[employee-api-sa runtime identity]
    R -->|Managed credentials and secret access permission| S[Secret Manager: EMPLOYEE_API_KEY]
```

Read this as an identity map. It does not say that the app fetches the secret on every HTTP request. Cloud Run can supply a configured secret to the container, or application code can fetch it. A secret may be obtained during startup, before the user's request. Our screenshots do not identify which retrieval pattern or secret version was used.

## The human, the robot, the keys and the rooms

Imagine a company building with a human user and an application robot. Both have identities, but one identity belongs to a person and the other is used by software.

```text
                     Google Cloud building
                              |
               +--------------+--------------+
               |                             |
          Human user                   Application robot
               |                             |
         Google account                 Service account
               |                             |
    rajaduraikr@gmail.com              employee-api-sa@
                            cloud-genai-learning.iam.gserviceaccount.com
```

### 1. Service account: who is the robot?

You use your Google account when working in the console or calling the API from Cloud Shell. The `employee-api` application runs automatically and uses a **service account** as its runtime identity.

The application and its service account are related, but they are different things: `employee-api` is the running software; `employee-api-sa` is the identity it is configured to use. Creating the account gives the robot an ID card. Selecting it in Cloud Run tells the application which ID card to use.

### 2. IAM role: what set of keys does the robot have?

An IAM role is a **collection of permissions**. In the analogy, it is a **bundle of keys granted to an identity for a resource scope**. It is not a room containing all the building's keys.

For example, **Secret Manager Secret Accessor** includes permission to access secret payloads. Granting that role to `employee-api-sa` on `EMPLOYEE_API_KEY` gives the robot the appropriate key bundle for that secret. A principal can receive different roles for different work, and the resource scope of each grant matters.

### 3. Permission: what can an individual key open?

A permission is an individual allowed action. For our robot, `secretmanager.versions.access` is the action that permits reading a secret-version payload. For a caller entering the API, `run.routes.invoke` is the action that permits invoking the Cloud Run service.

### 4. Resource: which room is the robot trying to enter?

A resource is the thing being accessed. In the discussion, it is the **particular room** the robot wants to enter. The room can contain a safe holding the secret value. Our actual resource is the `EMPLOYEE_API_KEY` secret, not every secret in the project.

| Concept              | Building analogy from the discussion                                    | Actual project example                                               |
| -------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Human Google account | Human employee / visitor's identity                                     | `rajaduraikr@gmail.com`                                              |
| Service account      | Robot employee's ID card                                                | `employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com`       |
| IAM role             | Bundle of keys granted to the robot within a scope                      | Secret Manager Secret Accessor, `roles/secretmanager.secretAccessor` |
| Permission           | Individual key / allowed action                                         | `secretmanager.versions.access`                                      |
| Resource             | Particular room the robot wants to enter                                | `EMPLOYEE_API_KEY` secret                                            |
| IAM binding          | Record that this identity receives this bundle of keys on this resource | Grant Secret Accessor to `employee-api-sa` on `EMPLOYEE_API_KEY`     |

The keys are a teaching analogy for permissions. They are **not downloaded service-account private keys**. Our application uses Cloud Run managed credentials; granting an IAM role does not require creating a JSON key file.

### The MES application example discussed earlier

Suppose an MES application needs to read a secret from Google Cloud Secret Manager. Ask two separate questions:

1. **Service account: who is the MES application when it accesses Google Cloud?** Its attached workload service account supplies that identity.
2. **IAM role: what is that identity allowed to do?** A role grant supplies the permissions, within the resource scope where it applies.

| Concept         | Meaning                                                              | Apply it to our Employee API                                        |
| --------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Application     | Software doing the work                                              | `employee-api` running in Cloud Run                                 |
| Service account | Identity used by that workload                                       | `employee-api-sa`                                                   |
| IAM role        | Collection of permissions granted to a principal on a resource scope | Secret Manager Secret Accessor granted on `EMPLOYEE_API_KEY`        |
| Permission      | Specific allowed action                                              | Read a secret-version payload using `secretmanager.versions.access` |

The same reasoning applies to the MES example and to `employee-api`. A service account answers **who the software is**. A role grant answers **what it may do within the grant's scope**.

### Connect the robot story to what we configured

| Our action                                                | Meaning in the story                                              | Why it was needed                                                            |
| --------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Create `employee-api-sa`                                  | Create the robot's ID card.                                       | Give this application a dedicated runtime identity.                          |
| Skip project-wide roles during creation                   | Do not give the robot a master key bundle for the whole building. | Keep the intended access narrow.                                             |
| Open the `EMPLOYEE_API_KEY` permissions page              | Go to the particular room's access list.                          | Put the grant on the secret resource.                                        |
| Grant Secret Manager Secret Accessor to `employee-api-sa` | Give that robot the key bundle for this room.                     | Authorize secret payload access on this secret.                              |
| Select `employee-api-sa` in Cloud Run                     | Tell the application worker to use this robot ID card.            | Make the runtime use the identity that received the grant.                   |
| Deploy the changed configuration                          | Start a revision with the chosen identity.                        | Apply the runtime identity change.                                           |
| Call the private API with your user ID token              | The human presents their own pass at the API entrance.            | Authenticate the incoming caller independently of the robot's secret access. |

## The three-gate story from the discussion

The supplied chat excerpt used these three questions. Keep them together when recalling the successful API request:

```text
Human caller requests the employee-api URL
                 |
                 v
Gate 1: Who are you?
Google authenticated your account; the token represents that identity.
                 |
                 v
Gate 2: Is your pass valid for this building?
Cloud Run must accept the presented identity token for this recipient.
                 |
                 v
Gate 3: Do you have permission to enter?
IAM must authorize the represented caller to invoke employee-api.
                 |
                 v
Application handler executes
Captured response: HTTP/2 200
```

| Gate wording from the discussion                   | Authentication / authorization connection                                      | What to remember technically                                                                                                                               |
| -------------------------------------------------- | ------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Gate 1 — Who are you?**                          | Authentication establishes the caller's identity.                              | The active Google account obtains the developer-test ID token. The receiving service must trust the presented identity proof.                              |
| **Gate 2 — Is your pass valid for this building?** | Token acceptance establishes that the presented credential is acceptable here. | Token validation includes trusted issuer, signature and expiry. In the normal service-to-service pattern, `aud` identifies the intended receiving service. |
| **Gate 3 — Do you have permission to enter?**      | Authorization checks the requested action against IAM.                         | The represented caller needs effective `run.routes.invoke` permission on the service.                                                                      |

Token validity and identity verification overlap in implementation; the platform need not perform them as three separate steps in this exact order. The gate story separates the questions for learning. Our captured Google-account developer token uses Cloud Run's supported testing pattern, so do not assume its `aud` matches a normal service-to-service token.

In the chat excerpt, the last step was labelled **“FastAPI — Request executed: 200 OK.”** The original terminal screenshot shows the wire response **`HTTP/2 200`** and the Employee API JSON. “200 OK” is the familiar success label; HTTP/2 does not need to include that reason phrase.

**The robot's secret access is a separate door.** Passing the user's three API gates does not grant the runtime robot permission to read `EMPLOYEE_API_KEY`. Secret Manager authenticates the workload identity and checks its own applicable IAM grant when secret access occurs.

## Authentication and authorization: what each one checks

**Authentication asks: “Who is making this request, and can I trust the credentials presented?”**

**Authorization asks: “Is this identity allowed to perform this action on this resource?”**

A verified identity does not automatically have permission. IAM roles and their permissions supply the authorization rules. In our example, these two ideas apply to both the incoming user request and the application's access to Secret Manager.

### Path 1: your Google account calls the private Employee API

You send a request to the Cloud Run URL with an ID token in the `Authorization: Bearer ...` header. Cloud Run verifies the accepted token to establish the caller's identity. Under the normal service-to-service pattern, the token's audience must also match the intended receiving service.

Cloud Run then uses the represented caller's effective IAM access to determine whether that identity has `run.routes.invoke` on `employee-api`. Cloud Run Invoker is the usual narrowly scoped role that supplies this permission. Our screenshots demonstrate a successful call, but do not show a separate Invoker grant being created.

| Question                                         | Concept                           | Our Employee API example                                                                                                                                                  | Visitor / building example                                      |
| ------------------------------------------------ | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| Who are you, and are these accepted credentials? | Authentication                    | Cloud Run verifies the ID token representing your Google account.                                                                                                         | The guard verifies your badge and identifies you.               |
| Is the token intended for this recipient?        | Token acceptance / audience check | A normal audience-bound token targets the receiving Employee API service. Our captured developer test uses Cloud Run's special support for Google-account testing tokens. | The guard checks that this badge is intended for this building. |
| May you invoke this API?                         | Authorization                     | IAM must allow the caller `run.routes.invoke` on `employee-api`.                                                                                                          | The guard checks the building's access list for your identity.  |

**Concrete example:** Google verifies that a visitor is Alice. That authenticates Alice. If Alice has no applicable invoke permission on Employee API, IAM does not authorize her to call it. Giving Alice a fresh token does not create that permission. Conversely, an IAM grant to Alice does not let a request with missing or invalid credentials establish that it came from Alice.

The HTTP header is named **`Authorization`**, but its bearer token is a credential used during authentication. The header's name does not mean the token itself grants an IAM role. Keep the header name separate from the concept of authorization.

### How the three gates relate to these concepts

| Gate                            | What is checked?                                                             | Relationship to authentication / authorization                                |
| ------------------------------- | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| 1. Identity and token validity  | Trusted issuer, signature, caller identity and expiry                        | Establishes an authenticated identity from accepted credentials.              |
| 2. Audience / service recipient | Whether a normal audience-bound token is intended for this receiving service | Part of accepting the token for this recipient. It does not grant IAM access. |
| 3. IAM invoke                   | Whether the represented caller has `run.routes.invoke` on this service       | Authorizes the requested action on the resource.                              |

The gates describe the checks you should understand, not a guaranteed internal processing order. Authentication and token acceptance are necessary, and authorization is a separate requirement.

### Path 2: the application accesses Secret Manager

The Employee API runs with the attached identity `employee-api-sa`. When the workload calls the Secret Manager API, Google-managed credentials authenticate that service account. Secret Manager evaluates IAM access for that identity to decide whether it may read the requested secret-version payload.

| Question                                    | Concept        | Our Secret Manager example                                                                                        | Robot / safe example                                         |
| ------------------------------------------- | -------------- | ----------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| Which workload identity is calling?         | Authentication | Managed credentials identify `employee-api-sa` when accessing the Google API.                                     | The safe's security system verifies the robot's badge.       |
| May that identity read this secret payload? | Authorization  | The grant of `roles/secretmanager.secretAccessor` on `EMPLOYEE_API_KEY` supplies `secretmanager.versions.access`. | The safe's access list permits this robot to open this safe. |

**Concrete example:** creating `employee-api-sa` gives the robot an identity. Attaching it to Cloud Run selects that identity for the running application. Granting Secret Manager Secret Accessor on `EMPLOYEE_API_KEY` gives that identity permission to read the secret payload. These actions do different jobs: create the identity, choose who the workload runs as, and authorize access to the resource.

A robot with valid managed credentials can still be denied access to a secret for which it has no applicable permission. Likewise, granting access to `employee-api-sa` does not help a revision that still runs as the old default compute account. The identity actually used for access must have the required permission.

### Compare both paths in one table

| Access path                  | Authentication: establish the identity                                         | Authorization: check the permission                               |
| ---------------------------- | ------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Your request → Cloud Run     | Accepted ID token represents your Google account.                              | That account needs effective invoke permission on `employee-api`. |
| Application → Secret Manager | Managed credentials represent the attached runtime account, `employee-api-sa`. | That account needs secret payload access on `EMPLOYEE_API_KEY`.   |

**Recall:** authentication establishes **who** is asking. Authorization determines **what that identity may do, and on which resource**. Your ability to call the API and the application's ability to read its secret are independent permissions.

## Worked example 1: you request the private URL

Imagine `employee-api` is an office building. **You are the visitor.** Cloud Run is the security guard at the entrance.

The URL is the building's address:

```text
https://employee-api-972261256506.europe-west2.run.app/
```

Knowing an address does not give you permission to enter. A deployed, healthy service can still reject a request without suitable credentials and access.

### Follow the request through the three gates

| Stage                                 | What happens in the example                                                                                                                      | Building example                                                                      |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| Prepare the request                   | You use the active Google account in `gcloud` to obtain an ID token and attach it to the HTTP request.                                           | You present a badge rather than arriving with only the address.                       |
| Gate 1: identity and token validity   | Cloud Run verifies that the presented token is accepted, including its signature, issuer and expiry. The token identifies the caller.            | Is the badge genuine and still valid? Who holds it?                                   |
| Gate 2: intended recipient / audience | For a normal service-to-service ID token, `aud` must identify this receiving service URL or a configured custom audience.                        | Was the badge issued for this building? A badge for another building is insufficient. |
| Gate 3: IAM invoke permission         | The caller represented by the token must have `run.routes.invoke` on the receiving service through effective IAM access.                         | Is this visitor allowed to enter this building?                                       |
| Application handles the request       | Once Cloud Run accepts the request, it can reach the Employee API container. The app can still perform its own checks and return its own errors. | The guard lets you in; the staff now handle your request.                             |

**Important detail for our actual screenshot:** we used a Google-account developer token from `gcloud auth print-identity-token`. Cloud Run specially supports this manual testing pattern. Do not assume that this token has the same audience claim as a normal service-to-service token. The audience rule above describes the normal audience-bound pattern. The gates are a teaching model, not a promise about the platform's internal checking order.

The captured command was:

```bash
curl -i \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://employee-api-972261256506.europe-west2.run.app/
```

| Part of the command                | Meaning                                                                                               |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `curl`                             | Sends the HTTP request.                                                                               |
| `-i`                               | Includes response headers, letting us see `HTTP/2 200`.                                               |
| `gcloud auth print-identity-token` | Obtains an ID token for the active `gcloud` identity in this manual test.                             |
| `$(...)`                           | Bash runs the command inside and inserts its output here.                                             |
| `-H "Authorization: Bearer ..."`   | Sends the token in an HTTP header. “Bearer” means possession of this token is used as the credential. |
| The `https://...run.app/` URL      | Identifies the receiving API service.                                                                 |

The token does **not** create an IAM grant. It proves an identity; IAM decides what that identity may do. Being signed in to the Google Cloud console also does not automatically add this bearer header to an ordinary browser address-bar request.

## Understand the token words: Bearer, ID token and audience

### What does `Authorization: Bearer TOKEN` mean?

`Authorization` is the name of an HTTP request header. It carries credentials to the receiving server. `Bearer` is the authentication scheme: **the request presents a token, and possession of that token is used as the credential**.

```text
Authorization: Bearer TOKEN
               │      │
               │      └─ The actual token goes here.
               └──────── The authentication scheme.
```

`TOKEN` above is an explanatory label. In our curl command, Bash replaces `$(gcloud auth print-identity-token)` with the actual token before sending the request.

Bearer does not mean “administrator,” “service account,” or “permission granted.” It also does not tell you which kind of token follows it. Both an **ID token** and an **access token** can be sent using the Bearer scheme, depending on the receiving service. Our private Cloud Run request uses an **ID token**. Calls to the Secret Manager Google API normally use an **access token**.

In the building example, Bearer means “I am presenting this badge as my credential.” The guard still checks whether the badge is valid and whether its holder has access. Treat a real bearer token as a credential: someone who obtains it may be able to use it until it expires, subject to the receiving service's checks. Send it over HTTPS and avoid putting it in shared notes or screenshots.

### What is an identity token / ID token?

An ID token is a signed statement about an identity. In this Cloud Run pattern, Google issues the token and the receiving service verifies it. It contains **claims**, which are named pieces of information such as the issuer, identity, intended recipient and expiry.

These tokens normally use JWT format: three encoded parts separated by dots, representing a header, a payload of claims, and a signature. Reading the payload is not the same as verifying it. The signature lets the receiver detect an altered or untrusted token.

| Word / claim          | Meaning                                                                              | Building memory aid                                               |
| --------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| ID token              | Signed proof of the caller's identity, used in this Cloud Run authentication pattern | The visitor's signed identity badge                               |
| Claim                 | A named statement inside the token                                                   | A field printed on the badge                                      |
| `iss` — issuer        | Who issued the token; the receiver must accept that issuer                           | Which trusted badge office issued it?                             |
| `sub` — subject       | The identity the token represents, expressed as an identifier                        | Whose badge is this?                                              |
| `email`, when present | An email associated with the represented identity                                    | A readable name on the badge; not every token includes this field |
| `aud` — audience      | The intended recipient of the token                                                  | Which building should accept this badge?                          |
| `iat` — issued at     | When the token was issued                                                            | When was the badge printed?                                       |
| `exp` — expiration    | When the token expires                                                               | Until when is the badge valid?                                    |
| Signature             | Protects the token's integrity and allows issuer verification                        | The badge office's verifiable seal                                |

An ID token does not contain a grant of the Cloud Run Invoker role. **The token establishes who is calling. The applicable IAM policy determines whether that caller may invoke the service.**

### What exactly is audience / `aud`?

“Audience” means **the service intended to receive and accept this token**. `aud` is the claim name used for that information.

For a normal service-to-service call to our Employee API, the audience would be the receiving Cloud Run service's base URL:

```text
https://employee-api-972261256506.europe-west2.run.app
```

The audience is not the caller's email, the runtime service account's email, the project ID, or the name of the secret. A configured custom audience can also be accepted by Cloud Run; our screenshot shows no custom audiences configured.

| Item                             | Example                                                        | What it identifies                             |
| -------------------------------- | -------------------------------------------------------------- | ---------------------------------------------- |
| Caller identity                  | Your Google account, or a calling service's service account    | Who sends the request                          |
| Request URL                      | `https://employee-api-972261256506.europe-west2.run.app/`      | Where the HTTP request goes                    |
| Normal token audience            | `https://employee-api-972261256506.europe-west2.run.app`       | Which service the token is intended for        |
| Runtime identity of the receiver | `employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com` | Who the receiving application runs as          |
| Secret resource                  | `EMPLOYEE_API_KEY`                                             | What that application needs permission to read |

The request URL and audience are closely related, but they have different jobs. If the application later has an endpoint such as `/employees`, the request can go to that endpoint while the normal Cloud Run audience remains the **base service URL**, without `/employees` or query parameters.

**Robot example:** suppose a Payroll robot obtains a normal ID token intended for the Payroll service. Sending that token to Employee API does not make Employee API its intended recipient. The Employee API audience check should reject it even if the token is genuine and unexpired. Likewise, a token intended for Employee API can pass the audience check but still fail IAM if the caller has no invoke permission.

### Why did our manual command not specify `--audiences`?

Our captured request used:

```bash
gcloud auth print-identity-token
```

This obtains a token using the active Google-account credentials for a **developer test**. Cloud Run supports this testing pattern specially. Do not assume it creates a normal service-specific `aud` claim, and do not use that exception to conclude that audience never matters.

For a normal service-account token, target the receiving service's audience. The optional impersonation example later in this guide shows `--audiences=...`. It requires permission to impersonate that account, and the represented account must also have invoke permission. For workloads, authentication libraries can obtain an ID token for the intended audience using the workload's managed identity.

### ID token versus access token versus API key

| Credential                           | What it is for in our learning                                                                            | Who uses it?                                              | Recall                                                  |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ------------------------------------------------------- |
| ID token                             | Authenticate an HTTP caller to private Cloud Run; IAM still decides invoke access                         | The person testing the API, or another service calling it | “This is who I am, speaking to this recipient.”         |
| Google OAuth access token            | Authenticate a request to a Google API such as Secret Manager; IAM still decides resource access          | The runtime workload using its service identity           | “These are my credentials for calling this Google API.” |
| API key stored in `EMPLOYEE_API_KEY` | Application configuration containing a key; its downstream purpose is not demonstrated by the screenshots | The Employee API application                              | “This is the stored key my application needs.”          |

The secret's API key is not the ID token used to enter private Cloud Run. A successful incoming bearer-token check does not retrieve that secret automatically. Secret retrieval belongs to the application's separate runtime access path.

### Connect the vocabulary back to the gates

| Recall question                           | Token / IAM concept                                          | Can this alone allow the request?                                                           |
| ----------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------- |
| Have I presented credentials?             | `Authorization: Bearer ...` header                           | No. The contents still need checking.                                                       |
| Who am I, and is the proof valid?         | Accepted issuer, signature, identity and expiry              | No. Recipient and authorization still matter.                                               |
| Who is this token for?                    | `aud`, under the normal audience-bound pattern               | No. Correct audience does not grant a role.                                                 |
| May this identity call this service?      | Effective IAM permission `run.routes.invoke`                 | The request still needs accepted authentication and must satisfy other applicable controls. |
| May the running application read its key? | Runtime service identity and `secretmanager.versions.access` | This is a separate resource-access decision, not an incoming Cloud Run gate.                |

## Worked example 2: the application robot needs its secret

Inside the office, the Employee API needs an API key to do its work. The key is stored in a locked safe called `EMPLOYEE_API_KEY` in Secret Manager.

**The application is the worker robot.** Its badge name is:

```text
employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com
```

The service account is the robot's Google Cloud identity. The application code still runs in the container; the service account tells Google Cloud **which identity that workload uses** when accessing resources.

### Build the robot's access one step at a time

| Step                                | Google Cloud action                                                            | Robot example                                                  | Why it matters                                                    |
| ----------------------------------- | ------------------------------------------------------------------------------ | -------------------------------------------------------------- | ----------------------------------------------------------------- |
| 1. Create its identity              | Create `employee-api-sa`.                                                      | Give the robot a named badge.                                  | An identity can exist before it is granted resource access.       |
| 2. Skip project-wide roles          | Leave the creation wizard's project-access role selection empty.               | Do not hand it a master pass to the whole campus.              | We only need access to one secret.                                |
| 3. Grant the specific resource role | On `EMPLOYEE_API_KEY`, grant `employee-api-sa` Secret Manager Secret Accessor. | Let this robot open this safe.                                 | This supplies secret payload access on the chosen secret.         |
| 4. Attach the identity to Cloud Run | Set the service's runtime account to `employee-api-sa`.                        | Assign this robot badge to the worker in our office.           | A grant to an unused account does not help the running app.       |
| 5. Deploy the configuration         | Create a revision with the new runtime identity and route traffic to it.       | Start the worker using the new badge.                          | Requests must reach the revision with the intended configuration. |
| 6. Retest                           | Call the private API using your user token.                                    | The visitor enters, and the worker can use its configured key. | Our screenshot reports `api_key_configured=true`.                 |

When the workload accesses Secret Manager, the relevant identity is **`employee-api-sa`**, not your personal Google account. Cloud Run manages credentials for its attached service identity. If code calls Secret Manager through a Google client library, it can use Application Default Credentials instead of a downloaded service-account key.

Your incoming user ID token is not automatically forwarded to Secret Manager to borrow your personal permissions. The Secret Manager API uses Google API authentication, normally an OAuth access token for the workload identity. Cloud Run ID tokens and Google API access tokens serve different purposes.

### A concrete permission statement

Read the secret grant as one sentence:

> On the resource `EMPLOYEE_API_KEY`, grant the principal `employee-api-sa` the role `Secret Manager Secret Accessor`, which includes permission to access secret-version payloads.

| IAM component                         | Example                                                   | Memory aid                                           |
| ------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------- |
| Principal: **who**                    | `employee-api-sa`                                         | Which robot?                                         |
| Role: **bundle of permissions**       | `roles/secretmanager.secretAccessor`                      | Which access pass?                                   |
| Permission: **allowed action**        | `secretmanager.versions.access`                           | What may it do? Read a secret payload.               |
| Resource: **where the grant applies** | `EMPLOYEE_API_KEY`                                        | Which safe?                                          |
| IAM policy binding                    | That principal is a member of that role on that resource. | Record this robot's pass on this safe's access list. |

This is why we created the account with no project-wide role and then granted access **on the secret**. “No project-wide role” does not mean “no permissions anywhere.” The identity can receive a narrow resource-level grant. That grant alone does not authorize reading a different secret unless another applicable grant permits it.

Attaching the account and granting secret access are both necessary parts of this design. The app also needs a valid secret reference or code that retrieves the secret. **IAM grants access; it does not itself place an API key into an environment variable.**

## Four scenarios that keep the two paths separate

| Example                             | User may invoke `employee-api`?  | Runtime identity may read the secret?                   | What to expect / investigate                                                                                                                                                          |
| ----------------------------------- | -------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A. Our intended working setup       | Yes, with an accepted token      | Yes, with the correct identity and secret configuration | The captured test returned `HTTP/2 200` and `api_key_configured=true`.                                                                                                                |
| B. Visitor has no invoke permission | No, even if their token is valid | Yes                                                     | Cloud Run rejects the caller. Giving the robot more secret permissions will not fix the visitor's access.                                                                             |
| C. Robot has no secret permission   | Yes                              | No                                                      | The container may fail to start if it needs a secret at startup, or the app may fail a secret read later. Giving the visitor more invoke permissions will not fix the robot's access. |
| D. Both lack access                 | No                               | No                                                      | Fix caller authentication / invoke access and runtime secret access separately. One fix does not resolve both.                                                                        |

These are conceptual examples, not additional tests captured in the screenshots. Even when both IAM paths allow access, application code, secret configuration and network settings can still affect the result.

### The shortest useful recall

**User → Cloud Run:** “Who are you, is your token accepted for this recipient, and may you invoke this service?”

**Application → Secret Manager:** “Which runtime identity are you using, and may that identity read this secret?”

**Deployment connects the application to its robot badge. IAM connects that badge to the resources it may access.**

## Captured outcome

The original screenshot shows the private API responding to an authenticated Cloud Shell request with `HTTP/2 200` and:

```json
{
  "message": "Employee API",
  "version": "3.0",
  "environment": "staging",
  "api_key_configured": true
}
```

The runtime identity changed from `972261256506-compute@developer.gserviceaccount.com` to `employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com`. Deployment status shows service update, revision creation and traffic routing completed. The exact revision identifier is not visible. This is captured evidence, not a fresh deployment or live test performed while writing these notes.

## Key difference

| Question         | Caller Google account                                                                             | Runtime service account                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Who is it?       | The person signed in to gcloud. The evidence shows rajaduraikr@gmail.com in IAM.                  | employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com                                                   |
| What does it do? | Sends the HTTP request to private employee-api.                                                   | Identifies the running employee-api revision when accessing Google Cloud resources.                            |
| Required access  | run.routes.invoke on employee-api, usually through roles/run.invoker or an existing broader role. | secretmanager.versions.access on EMPLOYEE_API_KEY through roles/secretmanager.secretAccessor.                  |
| Credential       | Bearer ID token from gcloud auth print-identity-token for this manual test.                       | Cloud Run managed credentials through its attached service identity. No downloaded service-account key needed. |
| Permission scope | Receiving Cloud Run service.                                                                      | Individual EMPLOYEE_API_KEY secret; no project-wide role in the intended setup.                                |
| Key difference   | Permission to enter the API.                                                                      | Permission for the API to read its secret.                                                                     |

## Three gates

| Gate                            | Check                                                                                                      | Recall                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| 1. Identity and token validity  | Google-signed ID token proves the caller. Check issuer, signature and expiry.                              | Who are you, and is your badge valid?    |
| 2. Audience / service recipient | Normal service-to-service ID token has aud set to the receiving service URL or configured custom audience. | Was this badge issued for this building? |
| 3. IAM invoke                   | The token identity needs run.routes.invoke on employee-api. A valid token alone does not grant access.     | Are you allowed through this door?       |

These gates are a recall model, not a guaranteed error-checking sequence. An identity token authenticates a caller; IAM authorizes an action. For service-to-service calls, the audience normally identifies the receiving Cloud Run service URL (without an endpoint path), or a configured custom audience. The screenshot uses `gcloud auth print-identity-token` with user credentials for a manual developer test. Cloud Run specially supports those developer tokens; do not mistake that example for the normal production audience-bound token pattern.

Private here means IAM-authenticated access. Network ingress is a separate setting. A browser address-bar request does not automatically send the required bearer token.

## IAM and the robot / building analogy

| Term               | Day 19 example                                           | Robot / building analogy                                            |
| ------------------ | -------------------------------------------------------- | ------------------------------------------------------------------- |
| Principal          | employee-api-sa (runtime) or the Google account (caller) | Robot or person holding a badge.                                    |
| Permission         | secretmanager.versions.access or run.routes.invoke       | One allowed action: open the safe or enter the building.            |
| Role               | Secret Manager Secret Accessor or Cloud Run Invoker      | A bundle of allowed actions printed on an access pass.              |
| Resource           | EMPLOYEE_API_KEY secret or employee-api service          | The specific safe or building.                                      |
| IAM binding        | Grant a role to a principal on a resource                | Give this robot a pass for this safe.                               |
| Project-wide grant | Would apply more broadly, including inherited access     | A master pass for many rooms. Avoid it when one safe is sufficient. |

The API runs as a robot, `employee-api-sa`. It gets permission to open the `EMPLOYEE_API_KEY` safe. A person calling the API needs permission to enter the `employee-api` building. Those permissions are evaluated against different principals and resources. A resource-level grant can work without a project-wide grant.

## Step-by-step console procedure

### 1. Create employee-api-sa

Select project cloud-genai-learning. Open IAM & Admin > Service Accounts > Create service account. Enter employee-api-sa as the name / ID, then Create and continue.

Check: Resulting email: employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com. Creation screen is not among the recovered screenshots.

### 2. Skip project-wide roles

Leave Grant this service account access to project empty. Continue. Leave optional user access empty and choose Done.

Check: The intended account starts with no project-wide role. Secret permissions screenshots alone cannot prove that no other inherited grant exists.

### 3. Grant access on EMPLOYEE_API_KEY

Open Secret Manager > EMPLOYEE_API_KEY > Permissions > Grant access. Add the employee-api-sa email. Choose Secret Manager Secret Accessor. Save.

Check: Grant on this secret only. Evidence 03 shows the grant dialog; Evidence 04 shows the resulting principal and role.

### 4. Switch Cloud Run runtime identity

Open Cloud Run > Services > employee-api in europe-west2 > Security. Keep Require authentication and IAM selected. Select employee-api-sa under Service Account.

Check: Evidence 05 shows the private IAM setting and new runtime identity. In alternate console layouts use Edit & deploy new revision > Security.

### 5. Review and deploy

Choose View diff & redeploy. Review the current default compute account and the new employee-api-sa account. Choose Serve this revision immediately only if the new revision should receive all traffic, then Deploy changes.

Check: Evidence 06 shows the service-account diff and 100% traffic choice. This configuration change creates a revision without requiring a new container build.

### 6. Confirm the new revision

Wait until Updating service, Creating revision and Routing traffic are Completed. Open Revision History to confirm the latest revision and its traffic allocation.

Check: Evidence 07 confirms those three completion states. The screenshot does not show the revision ID.

### 7. Check caller invoke access

For an explicitly scoped caller grant, open the employee-api IAM / permissions panel. Add the caller Google account and Cloud Run Invoker, then Save. Inspect existing access first.

Check: The captured caller is also shown as a project Owner on the secret page. A successful call proves effective invoke access, not that a separate Invoker binding was created.

### 8. Invoke with a bearer identity token

Open Cloud Shell with the intended Google account. Confirm the active gcloud account, then invoke the URL with Authorization: Bearer and a freshly generated ID token.

Check: Evidence 08 shows HTTP/2 200 and api_key_configured=true. A normal browser address-bar request does not attach this bearer token automatically.

The deployer needs Cloud Run update access and `iam.serviceAccounts.actAs` on the runtime service account (typically through Service Account User). The attached runtime identity uses Cloud Run managed credentials to access Google APIs. It does not need a downloaded JSON key. Preserve the existing secret reference / application configuration: a permission grant alone does not inject a secret into a container. The supplied images do not identify the secret version or exact environment mapping.

## Commands

Run in Cloud Shell using Bash. These commands use the actual captured project, service, region and principal. Account creation and IAM changes are repeatable learning procedures; only the curl invocation is visibly captured.

### Set project

```bash
gcloud config set project cloud-genai-learning
```

All examples use the captured project and europe-west2 region.

### Check caller

```bash
gcloud auth list --filter=status:ACTIVE --format='value(account)'
```

The active gcloud identity supplies the manual-test token.

### Create runtime identity

```bash
gcloud iam service-accounts create employee-api-sa --project=cloud-genai-learning --display-name=employee-api-sa
```

Run only if it does not already exist. Creating an account does not itself grant project roles.

### Grant secret access

```bash
gcloud secrets add-iam-policy-binding EMPLOYEE_API_KEY --project=cloud-genai-learning --member='serviceAccount:employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com' --role='roles/secretmanager.secretAccessor'
```

Secret-level policy binding. Do not replace this with a project IAM grant.

### Switch runtime identity

```bash
gcloud run services update employee-api --project=cloud-genai-learning --region=europe-west2 --service-account=employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com
```

Creates a new revision. Deployer needs permission to update the service and iam.serviceAccounts.actAs on this account.

### Grant caller invoke if needed

```bash
gcloud run services add-iam-policy-binding employee-api --project=cloud-genai-learning --region=europe-west2 --member='user:rajaduraikr@gmail.com' --role='roles/run.invoker'
```

Explicit service-level caller grant. The screenshots do not show this command was run.

### Captured manual test

```bash
curl -i -H "Authorization: Bearer $(gcloud auth print-identity-token)" https://employee-api-972261256506.europe-west2.run.app/
```

This matches the successful screenshot. Developer tokens from gcloud have special Cloud Run support and are not the production audience-bound pattern.

### Inspect secret scope

```bash
gcloud secrets get-iam-policy EMPLOYEE_API_KEY --project=cloud-genai-learning
```

Look for the employee-api-sa binding to roles/secretmanager.secretAccessor.

### Inspect direct project grants

```bash
gcloud projects get-iam-policy cloud-genai-learning --flatten='bindings[].members' --filter='bindings.members:employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com' --format='table(bindings.role)'
```

Empty output addresses direct project policy only; also consider folder / organization inheritance and group memberships.

### Inspect runtime and revision

```bash
gcloud run services describe employee-api --project=cloud-genai-learning --region=europe-west2 --format='yaml(spec.template.spec.serviceAccountName,status.latestReadyRevisionName,status.traffic,status.url)'
```

Check account, latest ready revision, traffic and URL together.

### Inspect caller access

```bash
gcloud run services get-iam-policy employee-api --project=cloud-genai-learning --region=europe-west2
```

Effective access may include inherited roles. Review public allUsers grants if confirming a private service.

### Audience-bound robot call

```bash
ID_TOKEN=$(gcloud auth print-identity-token --impersonate-service-account=employee-api-sa@cloud-genai-learning.iam.gserviceaccount.com --audiences=https://employee-api-972261256506.europe-west2.run.app --include-email)
curl -i -H "Authorization: Bearer $ID_TOKEN" https://employee-api-972261256506.europe-west2.run.app/
```

Optional learning example, not captured execution. Requires caller impersonation permission and employee-api-sa invoke access on the receiving service. Its existing secret role does not grant invoke. Prefer a separate caller account in a real multi-service design.

## Screenshot evidence

All eight original screenshots are embedded in the companion Excel workbook's Screenshots tab, with an index and captions.

| Image                      | What it shows                                                                                                                                                                                                               |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| image(20261010-110108).png | 01. Locate the secret. Secret Manager lists EMPLOYEE_API_KEY in cloud-genai-learning. Start here to scope access to this specific resource.                                                                                 |
| image(20261010-110129).png | 02. Inspect existing access. Before the new grant, the secret page shows the default compute account and caller Google account. The compute account retains visible Editor and Secret Accessor roles in this evidence.      |
| image(20261010-110320).png | 03. Grant the robot access to one secret. The grant dialog targets EMPLOYEE_API_KEY and employee-api-sa, with Secret Manager Secret Accessor selected.                                                                      |
| image(20261010-110338).png | 04. Verify the saved binding. employee-api-sa appears as Secret Manager Secret Accessor on the secret Permissions page. The old compute account is still listed; the screenshots do not demonstrate its access was removed. |
| image(20261010-114638).png | 05. Keep the service private and switch identity. Require authentication and IAM are selected. The Service Account dropdown now shows employee-api-sa. The page still has pending changes.                                  |
| image(20261010-114720).png | 06. Review and deploy the runtime change. The diff replaces the default compute account with employee-api-sa. Serve this revision immediately is checked, indicating 100% traffic migration.                                |
| image(20261010-114757).png | 07. Confirm deployment completion. Updating service, Creating revision and Routing traffic all show Completed for employee-api in europe-west2.                                                                             |
| image(20261010-115146).png | 08. Verify authenticated HTTP response. The captured curl sends a bearer identity token. Response: HTTP/2 200; message Employee API; version 3.0; environment staging; api_key_configured true.                             |

The original Linux paths supplied in the request were unavailable on this Windows host. The conversation reader recovered matching files into accessible temporary Windows paths. No substitute images or placeholders were used. The service-account creation wizard was not among these images. The before / after permission pages still show the old compute account; they do not establish that its previous access was revoked.

## Recall notes

| Prompt                                                  | Answer                                                                                                                                                                                                                                  |
| ------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Private service is deployed. Why can a plain URL fail?  | Deployment readiness does not grant caller access. The request still needs an accepted ID token and IAM invoke permission.                                                                                                              |
| Does the secret role let me call Cloud Run?             | No. Secret access and service invoke are separate actions on separate resources.                                                                                                                                                        |
| Does my Google account become the API runtime identity? | No. The request caller is separate from the service account attached to the running revision.                                                                                                                                           |
| Why create employee-api-sa with no project-wide role?   | The account is an identity. Grant only the resource access its workload needs, here one secret.                                                                                                                                         |
| What changed at deployment?                             | Runtime account changed from 972261256506-compute@developer.gserviceaccount.com to employee-api-sa. A new revision was created and traffic routed.                                                                                      |
| What does api_key_configured=true prove?                | The app reports an API key is configured. Together with the grant and deployment screenshots it supports the setup working; it does not reveal the key, prove a downstream API call, or identify the secret version.                    |
| What should I check for a failed request?               | Missing / expired token, active caller identity, normal token audience and IAM invoke access. If the request reaches the app but secret configuration fails, inspect runtime account, secret binding, secret version and configuration. |
| What is not documented by these screenshots?            | Service-account creation wizard, absence of all inherited project roles, exact revision ID, secret version / environment mapping and an explicit Invoker grant.                                                                         |

## References

Source learning evidence: New_Learning_1, conversation `6aa66e73-10d4-83ed-b1d2-0f0f2ca78540`, the eight original console / terminal screenshots, and the four conversation excerpts supplied in this chat. The excerpts show the human-versus-robot identity diagram, roles as bundles of keys, permissions as individual actions, the MES example, and the original three-gate wording. The conversation reader returned older assistant prose as unresolved content references, so the guide does not claim to reproduce unseen parts of the full discussion. Technical distinctions were checked against official Google Cloud documentation.

- [Developer authentication](https://docs.cloud.google.com/run/docs/authenticating/developers)
- [Service-to-service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)
- [Runtime service identity](https://docs.cloud.google.com/run/docs/configuring/services/service-identity)
- [Secret IAM scope](https://docs.cloud.google.com/secret-manager/docs/access-control)
- [Cloud Run secret configuration](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
