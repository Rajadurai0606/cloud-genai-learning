# Day 37 — Kubernetes CPU, memory, requests, limits and QoS

I ran my Employee API locally in Docker Desktop Kubernetes, with no GCP charges. I used the existing FastAPI image, `employee-api:v16`, and ran three copies of the app. Each copy ran in its own Pod with one app container. I checked what CPU and memory the node could offer, set requests and limits for the app, and checked what changed. I also found out why I couldn’t see recent usage with `kubectl top`. My 15 screenshots are numbered S001–S015 in the Excel workbook.

## T001 — CPU and memory fundamentals

### Where does my Pod get CPU and memory?

The **node** is the machine that runs my Pods. It provides the CPU that does the work and the memory that holds the data while the work is running. A Pod holds one or more containers. Each container can ask Kubernetes for CPU and memory, and the operating system shares those resources among them.

I can picture Chrome, Visual Studio and Docker Desktop running together on my laptop. They all use time on the same processors and space in the same RAM. Station Managers on one Kubernetes node share resources in the same way. When I ask for half a CPU, that describes how much processing power I need. The operating system can schedule the work across available cores.

### How do I read `100m` and `128Mi`?

For CPU, `m` means one thousandth. Just as 1,000 millimetres make one metre, `1000m` makes one CPU. I divide by 1,000 to turn a CPU value written with `m` into CPU units.

| CPU | Calculation in CPU units | Share of one CPU |
|---|---|---|
| `100m` | 100 ÷ 1,000 = 0.1 | 10% |
| `250m` | 250 ÷ 1,000 = 0.25 | 25% |
| `500m` | 500 ÷ 1,000 = 0.5 | 50% |
| `1000m` | 1,000 ÷ 1,000 = 1 | 100% |
| `2000m` | 2,000 ÷ 1,000 = 2 | 200% |

For memory, `Mi` means mebibytes (MiB). I write `128Mi` in my YAML for 128 MiB of RAM. These units count in steps of 1,024:

- 1 MiB = 1,024 KiB = 1,048,576 bytes. For comparison, 1 MB = 1,000,000 bytes.
- 1 GiB = 1,024 MiB = 1,073,741,824 bytes.
- 128 MiB = 128 × 1,048,576 = 134,217,728 bytes (about 134.22 MB).
- 256 MiB = 256 × 1,048,576 = 268,435,456 bytes (about 268.44 MB).

### My baseline inspection

In PowerShell with `kubectl` pointed at my running Docker Desktop Kubernetes cluster I used:

```powershell
kubectl get nodes
kubectl get pods
kubectl describe node docker-desktop
```

`get nodes` showed that my `docker-desktop` node was Ready (control plane, v1.36.1). `get pods` showed three Employee API Pods. Each had one ready container and one earlier restart. `describe node` showed that the node was Ready and had enough memory, disk space and process IDs at that moment.

**Capacity** is the total the node reports. **Allocatable** is what Kubernetes can plan to give to Pods after setting aside resources for the node itself. The figures below are for my Docker Desktop Kubernetes node.

| Resource | Capacity | Allocatable |
|---|---:|---:|
| CPU | 8 CPU | 8 CPU |
| Memory | 8,081,048 Ki | 7,978,648 Ki |
| Pods | 110 | 110 |

I divide by 1,048,576 to convert KiB to GiB. Capacity is 8,081,048 ÷ 1,048,576 ≈ 7.71 GiB. Allocatable memory is 7,978,648 ÷ 1,048,576 ≈ 7.61 GiB. The difference is 102,400 KiB, or 102,400 ÷ 1,024 = 100 MiB set aside. The Pods share the eight allocatable CPUs. **See S001–S004.**

## T002 — Requests and node resource accounting

### What does a request do?

The **scheduler** is the part of Kubernetes that chooses a node for a new Pod. It checks how much the node offers, adds up the requests it has already accepted, and checks whether the new Pod’s requests fit.

My Employee API asks for `100m` of CPU and `128Mi` of memory per Pod. Kubernetes counts those amounts when it places each Pod. Once the app is running, it may use less when idle and more when busy, up to its limits. If several containers compete for CPU, their CPU requests help decide how much each gets. The memory request also matters if the node runs short of memory and Kubernetes has to decide which Pods to stop (T007).

### My Employee API teaching example

I used these made-up numbers to see what my app might do. Each percentage is a share of one CPU. The request is `100m` and the limit is `500m`.

| Work on the API | Demand | What I expect |
|---|---:|---|
| Idle | 20m (2%) | Uses less than request |
| Simple GET | 50m (5%) | Uses less than request |
| Moderate processing | 200m (20%) | Can run above request if CPU is available |
| Heavy processing | 500m (50%) | At the configured limit |
| CPU-intensive operation | 800m (80%) | Demand exceeds limit and can be throttled |

For MES, 100 Station Managers at `100m` each would request 100 × 100m = 10,000m, or 10 CPUs in total. Their actual use can rise when they process messages and fall when stations are idle. On a node with four CPUs to offer, eight Station Managers at `500m` each would ask for 8 × 500m = 4,000m. That fills the node’s request budget if the whole budget is available to them. At 100–200 instances I need to check what space is already taken by system and app Pods. Station Manager and PDT were production examples. I used Employee API for my hands-on deployment.

### Why 850m became 1150m

Before I changed Employee API, the node already showed `850m` of CPU requests. Those requests came from the Pods in `kube-system` that help run Kubernetes. CoreDNS looks up names inside the cluster. etcd stores the cluster’s records. The API server handles commands, the controller manager keeps things running as configured, and the scheduler chooses nodes for Pods.

| Existing component | CPU request | Memory request | Memory limit |
|---|---:|---:|---:|
| CoreDNS × 2 | 2 × 100m | 2 × 70Mi | 2 × 170Mi |
| etcd | 100m | 100Mi | 0 in table |
| kube-apiserver | 250m | 0 in table | 0 in table |
| kube-controller-manager | 200m | 0 in table | 0 in table |
| kube-scheduler | 100m | 0 in table | 0 in table |
| kube-proxy, storage-provisioner, vpnkit-controller | 0 in table | 0 in table | 0 in table |
| **Baseline total** | **850m** | **240Mi** | **340Mi** |

I added the system Pods’ CPU requests: 100 + 100 + 100 + 250 + 200 + 100 = 850m. That is 85% of **one** CPU. My node offers eight CPUs, so the same request takes up 850 ÷ 8,000 × 100 = 10.625% of the node’s CPU budget (shown as 10%). The table shows what Kubernetes is planning for. A zero in the CPU limits total means no CPU limits were counted, so those Pods can still use CPU. The memory requests add up the same way: 70 + 70 + 100 = 240Mi.

| Resource | Per API Pod | Added for 3 Pods | Baseline | Expected and observed after rollout |
|---|---:|---:|---:|---:|
| CPU requests | 100m | 3 × 100m = 300m | 850m | 850 + 300 = **1150m** |
| CPU limits | 500m | 3 × 500m = 1500m | 0 | 0 + 1500 = **1500m** |
| Memory requests | 128Mi | 3 × 128Mi = 384Mi | 240Mi | 240 + 384 = **624Mi** |
| Memory limits | 256Mi | 3 × 256Mi = 768Mi | 340Mi | 340 + 768 = **1108Mi** |

After the update, I checked the percentages against what my node offers:

- CPU requests: 1,150 ÷ 8,000 × 100 = 14.375%, shown as 14%.
- CPU limits: 1,500 ÷ 8,000 × 100 = 18.75%, shown as 18%.
- Memory requests: 624 × 1,024 ÷ 7,978,648 × 100 ≈ 8.01%. I multiply by 1,024 to turn MiB into KiB before dividing.
- Memory limits: 1,108 × 1,024 ÷ 7,978,648 × 100 ≈ 14.22%.

I was comparing two different views. `kubectl describe deployment employee-api` shows the settings for each new Employee API Pod. `kubectl describe node docker-desktop` adds up the settings from all Pods on that node, including system Pods. That’s how my app’s `300m` of requests became part of the node’s `1150m` total. **See S003–S004 and S013–S015.**

## T003 — Limits and CPU percentages

My app can use more than its `128Mi` memory request when the node has room. The `256Mi` limit is the container’s memory cap. For CPU, the `500m` limit controls how much CPU time the container can get, as I explain in T004. Each Pod’s app container has its own limits. Kubernetes can sometimes place Pods whose limits add up to more than the node offers, because it checks requests when deciding where to run them.

When I read a CPU percentage, I ask what it is a percentage **of**. My app’s `500m` can be 50% of one CPU and 6.25% of my eight-CPU node at the same time.

| Question I asked | Calculation | Interpretation |
|---|---|---|
| Is 500m half a CPU? | 500 ÷ 1000 = 0.5 | 50% of one CPU |
| Is 500m 6.25%? | 500 ÷ 8000 = 0.0625 | 6.25% of my eight-CPU node |
| What about three replicas? | 3 × 500 = 1500m = 1.5 CPU | 1500 ÷ 8000 = 18.75% of node capacity |
| What CPU does the API request? | 3 × 100 = 300m = 0.3 CPU | 300 ÷ 8000 = 3.75% of the node request budget |
| Is the remaining 6500m free? | 8000 − 1500 = 6500m | This is a subtraction against the three limits. Other workloads share the node, and actual free CPU varies. |

**Evidence S008, S011 and S015.** [Kubernetes resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

## T004 — CPU throttling, CPU time and OOMKilled

### CPU time and throttling

**CPU time** is how long the CPU actually spends doing my app’s work. Time I see on a clock also includes any time the app spends waiting. If my Employee API needs one second of CPU time to finish a calculation, it may take about two seconds on the clock with a `500m` limit.

I can think of `500m` as a CPU budget. Over one second, `1000m` allows about one second of work on one CPU, `500m` allows about half a second, and `250m` allows about a quarter of a second. Linux gives the app that budget in short, repeating intervals. If the app uses up its share for one interval, its CPU work waits until the next one. That wait is **CPU throttling**. My Employee API can keep running, but a request that needs lots of CPU may take longer to finish. The two-second example assumes CPU is the main thing slowing the calculation down.

### Memory limit and OOMKilled

My Employee API has a memory limit of `256Mi`. If it needs more and Linux cannot free enough memory within that limit, Linux can kill the app process. Kubernetes can show `OOMKilled` as the reason the container stopped. OOM stands for *out of memory*. Kubernetes may then restart the container, depending on the Pod’s restart policy.

| Teaching timeline | Start | Step 1 | Step 2 | Step 3 | Step 4 |
|---|---:|---:|---:|---:|---:|
| Memory use or demand (MiB) | 80 | 140 | 210 | 250 | 280 |
| Limit (MiB) | 256 | 256 | 256 | 256 | 256 |

In this example, the app is still within its limit at 250 MiB. At the last step it **asks for** 280 MiB in total, which is 280 − 256 = 24 MiB over its budget. That request can fail or lead to an OOM kill. These numbers are a teaching example.

If I see exit code 137, I’ll check the termination reason and Kubernetes Events. Code 137 means the process was forcibly killed. An out-of-memory kill is one possible cause. A failed liveness check followed by a forced shutdown can also produce that code.

### How I remember it

- **CPU throttling:** My app waits for more CPU time. Work can take longer.
- **OOMKilled:** My app was killed because it ran out of usable memory. A restart may follow.

For my MES Station Manager, a burst of MQTT messages can make processing slow down under CPU throttling. Messages can pile up in a queue and the HMI may show updates late. If that queue grows in memory and the app is OOMKilled, updates may stop until the app recovers. Acknowledgements and retries help me handle messages that were still being processed. The HMI is a teaching example here.

I deferred the CPU experiment. My plan was to give a temporary test app a `500m` limit, make it do heavy CPU work, check Linux’s throttling counters without Metrics Server, then remove the test app. I did not run an OOM experiment either. **S008 and S011 show the configured limits.**

## T005 — Deployment YAML, validation and rollout

### Where I put the settings

I opened `01-python-fastapi/k8s/deployment.yaml`. In that file, the Pod template is the blueprint Kubernetes uses to create each copy of Employee API. I found my app under `spec.template.spec.containers` and added `resources` alongside its image and `envFrom` settings, at the same indentation.

I picked these values for the lab so I could see what happens when the requests are lower than the limits. They are the values I actually applied.

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

I kept the existing image `employee-api:v16` and `imagePullPolicy: IfNotPresent`, which lets Kubernetes use the image if it already has it locally. My Deployment also showed the existing health checks, ConfigMap settings and Secret reference.

### How I checked and applied the change

I ran these commands in PowerShell from `01-python-fastapi`, with Docker Desktop Kubernetes running and Employee API already deployed.

| Step | Command or action in PowerShell | Expected and observed result | Evidence |
|---|---|---|---|
| Edit the file | Open `01-python-fastapi/k8s/deployment.yaml` | Resource block appears under the app container | S008 |
| Validate | `kubectl apply --dry-run=server -f .\k8s\deployment.yaml` | I asked the server to check the file without saving the change. It returned `configured (server dry run)`. | S009 |
| Apply | `kubectl apply -f .\k8s\deployment.yaml` | `deployment.apps/employee-api configured` | S010 |
| Wait | `kubectl rollout status deployment/employee-api` | I watched Kubernetes bring up the new Pods and take down the old ones. The command reported success. | S010 |
| Check Pods | `kubectl get pods` | Three new Pods `1/1 Running` with zero restarts. Old Pods still showed `Terminating` during the transition. | S010 |
| Inspect Deployment | `kubectl describe deployment employee-api` | All three copies were updated and available. I saw the new resource values, the new ReplicaSet and the Events showing how Kubernetes changed the Pod counts. | S011–S012 |
| Check node totals | `kubectl describe node docker-desktop` | Observed all four expected totals from T002 | S013–S015 |

### Why I saw old and new Pods together

Changing the blueprint starts a **rolling update**. Kubernetes uses a new ReplicaSet to manage the new copies and reduces the old set as the new Pods become ready. My strategy showed `25%` max unavailable and `25%` max surge. With three copies, 25% of 3 is 0.75. Kubernetes rounds down for unavailable Pods (zero) and up for extra Pods (one). It can start an extra Pod so the app stays available while the old Pods shut down. I used the later node screenshot to compare resource totals once the old Pods were gone.

## T006 — Metrics Server, Metrics API and troubleshooting

### Why did `get pods` work when `top` failed?

I first mixed up two names. **`kubectl`** is the tool I type commands into in PowerShell. **Kubelet** is a program running on each node. It looks after the Pods there and makes CPU and memory measurements available.

When I run `kubectl get pods`, the API server can tell me about my Pods and whether they’re running. With `kubectl describe node`, I can see the node’s status and add up the requests and limits I’ve set. To answer “how much CPU and memory are my Pods using right now?”, `kubectl top` needs recent measurements from the Metrics API.

```text
Pod status:   kubectl get pods → Kubernetes API server → Pod records
Measurements: containers → kubelet on each node → Metrics Server collects them
Usage query:  kubectl top → Kubernetes API server → Metrics API (metrics.k8s.io)
```

I picture my MES client asking a REST API for station production counts. The client knows where to ask, and another service collects the counts. Here, **Metrics Server** collects usage from each kubelet and supplies the numbers. The **Metrics API** is where those numbers are available through the Kubernetes API server. These recent measurements can also help Kubernetes decide when to add or remove app copies (autoscaling). [Kubernetes resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)

| I ran | Observed | Interpretation |
|---|---|---|
| `kubectl top nodes` and `kubectl top pods` | `error: Metrics API not available` for both | Live resource metrics were unavailable. |
| `kubectl get deployment metrics-server -n kube-system` | Deployment `metrics-server` NotFound | The usual Metrics Server Deployment was absent in that namespace. |
| `kubectl get apiservice v1beta1.metrics.k8s.io` | APIService NotFound | The usual entry that connects the Metrics API to the Kubernetes API server was missing. |

If that API entry exists and says `Available=False`, I would check whether Metrics Server is running and reachable. If it says `Available=True` but `top` still fails, I would read the error, check my permissions and see whether recent measurements are coming in. I left the installation for Day 38. Kubernetes could already place my Pods and enforce their limits, so I continued the Employee API update. **See S005–S007.**

## T007 — QoS, node-pressure eviction and Pod Priority

### How does Kubernetes pick a QoS class?

QoS means **Quality of Service**. In this lab, Kubernetes looks at the CPU and memory requests and limits I set on every container in the Pod. It uses those settings to give the Pod one of three classes.

| Class | Rule for this lab | Example |
|---|---|---|
| BestEffort | All containers have no CPU or memory requests or limits | A background helper with no resource settings, provided the cluster adds no defaults. |
| Burstable | At least one container has a CPU or memory setting, but the whole Pod does not meet the Guaranteed rule | My Employee API asks for 100m and 128Mi, with limits of 500m and 256Mi. A Station Manager with requests below its limits also fits. |
| Guaranteed | Every container has both CPU and memory set, and each request exactly matches its limit | In my example, both CPU values are 500m and both memory values are 256Mi. |

For my BestEffort example, I would leave CPU and memory settings out. For my one-container Guaranteed example, I would use the block below. Both were teaching examples.

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

My deployed Employee API should be `Burstable` based on the applied settings. This optional command would show each Employee API Pod’s name and its actual QoS class. I left the check for later.

```powershell
kubectl get pods -l app=employee-api -o custom-columns='NAME:.metadata.name,QOS:.status.qosClass'
```

### What would happen during memory pressure?

If the whole node runs low on memory, kubelet may stop a Pod to free up space. This is **eviction**. A Deployment can create a replacement Pod. In T004, the container could be OOMKilled because it hit its own limit, even with free memory elsewhere on the node.

I originally thought the QoS name alone told me which Pod kubelet would evict first. I use these three questions to work through the memory example:

1. **Who is using more than they requested?** Kubelet considers those Pods first. Even 1Mi puts a BestEffort Pod above its zero request.
2. **Who has lower Pod Priority?** Within the same group, lower-priority Pods come first.
3. **If priority is tied, who is further above their request?** I compare the extra MiB each Pod is using.

A Burstable Pod can be above or below its request. A Guaranteed Pod using exactly its request comes after the Pods above theirs, but it can still be evicted if pressure is severe.

| Pod | QoS | Memory request | Memory limit | Usage | Usage minus request |
|---|---|---:|---:|---:|---:|
| A | BestEffort | 0Mi | None | 1Mi | +1Mi |
| B | Burstable | 128Mi | 200Mi | 199Mi | +71Mi |
| C | Guaranteed | 256Mi | 256Mi | 256Mi | 0Mi |

Suppose the node is short of memory, these are the three candidates, and all have priority 0. A and B are above their requests. B comes first because it is 199 − 128 = **71Mi above its request**, while A is only 1Mi above. C is using exactly what it requested. B is still 200 − 199 = **1Mi below its limit**. It can be evicted even though it has room under that limit.

- At 200Mi, B would be 200 − 128 = 72Mi over its request.
- If B’s limit were 500Mi and it used 300Mi, it would be 300 − 128 = 172Mi over its request.
- With B’s original 200Mi limit, asking for 300Mi means asking for 300 − 200 = 100Mi more than its limit. That can lead to `OOMKilled`. [Kubernetes node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)

### Who decides priority?

My team can set how important a Pod is by choosing a named `PriorityClass`. A Pod gets priority 0 if I choose no class and the cluster has no default. Higher numbers mean higher priority, so 1001 ranks above 1000, and 1000 ranks above 0. The numbers can have gaps. My team could give a critical Station Manager a higher priority even if it has the same QoS class as a less important app. I used this YAML as a teaching example:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: station-manager-high
value: 1001
globalDefault: false
```

I would create this class for the whole cluster. Its `value` sets the priority number and `globalDefault: false` leaves it as a class I choose explicitly. To give a Pod this priority, I would set `priorityClassName: station-manager-high` under the Pod’s `spec`. In a Deployment I would put it under `spec.template.spec`. **See S008 and S011 for the settings that make my lab Pods likely to be Burstable.**

## Quick recall

- **Where can my Pod run?** Kubernetes checks if its requests fit alongside the other Pods’ requests on the node.
- **How much CPU is 500m?** I divide by 1,000 for a share of one CPU. I divide by 8,000 for a share of my eight-CPU node.
- **What’s my memory budget?** A request helps Kubernetes place my Pod. A limit caps the memory my container can use.
- **What’s my app using right now?** I use `kubectl top` for recent usage when metrics are available. I use `kubectl describe node` to see the requests and limits added together.
- **Why did my app slow down or stop?** Throttling can slow CPU work. `OOMKilled` means a memory kill. For `Evicted`, I check node pressure and Pod Events.
- **Which Pod might be evicted first?** I check who is above request, who has lower priority, and who is further above request when priorities tie.

## Coverage audit and my final state

| Topic | Checked against the original discussion | Original evidence |
|---|---|---|
| T001 | Where CPU and memory come from, what the units mean, and what my node offers Pods | S001–S004 |
| T002 | What requests do, five API examples, Station Manager sizing, and how the system and app requests add up | S004, S013–S015 |
| T003 | My app’s four resource settings, totals for three copies, and shares of one CPU or the whole node | S008, S011, S015 |
| T004 | Why work can slow down or stop, what exit code 137 tells me, and what might happen to MQTT messages | S008 and S011 show the limits. The behaviour examples were for learning. |
| T005 | Where I edited the file, how I checked and applied it, and what happened during the update | S008–S015 |
| T006 | What `kubectl` and kubelet do, how measurements reach `top`, what errors I saw, and what I left for Day 38 | S005–S007 |
| T007 | How Kubernetes picks QoS, which Pods can be evicted first, and how I would set Pod Priority | S008 and S011 show my app’s settings. The QoS command and eviction examples were left as exercises. |

I finished with all three Employee API copies available and using the new settings. The node totals matched my calculations. I left the Metrics Server installation for Day 38. I skipped the optional QoS check and the CPU and OOM tests, so I had no test Pods to clean up. Reviewing and committing the changes in Git was a follow-up. I have no record of a completed Day 37 commit.
