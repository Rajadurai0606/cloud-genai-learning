# Day 37 — Kubernetes CPU, memory, requests, limits and QoS

I used Docker Desktop Kubernetes and my existing FastAPI Employee API image, `employee-api:v16`, with three replicas and one application container per Pod. This was local, with no GCP charges. I inspected the node, diagnosed the missing metrics pipeline, deployed container resource settings, and reconciled the before-and-after resource totals. The companion Excel workbook indexes my 15 original screenshots by S001–S015.

## T001 — CPU and memory fundamentals

I initially asked how a Pod could “own” CPU and memory when the node owns the computing resources. The node provides the CPU and RAM, and the operating system shares them among containers. A Pod is the context in which one or more containers run, and each container can declare resource requirements. On my laptop, Visual Studio, Chrome and Docker Desktop need time on the same available processors and space in memory. Similarly, multiple Station Managers on a node draw on common resources. A CPU quantity describes processing capacity and does not pin the container to one physical core.

| CPU | Calculation in CPU units | Share of one CPU |
|---|---|---|
| `100m` | 100 ÷ 1,000 = 0.1 | 10% |
| `250m` | 250 ÷ 1,000 = 0.25 | 25% |
| `500m` | 500 ÷ 1,000 = 0.5 | 50% |
| `1000m` | 1,000 ÷ 1,000 = 1 | 100% |
| `2000m` | 2,000 ÷ 1,000 = 2 | 200% |

The `m` in a CPU quantity means milli, like 1,000 millimetres to a metre. The `Mi` in memory is binary. 1 MiB = 1,024 KiB = 1,048,576 bytes, while 1 MB = 1,000,000 bytes. 1 GiB = 1,024 MiB = 1,073,741,824 bytes. So 128 MiB = 128 × 1,048,576 = 134,217,728 bytes (about 134.22 MB), and 256 MiB = 268,435,456 bytes (about 268.44 MB). I use `128Mi`, rather than my shorthand `128m`, in memory YAML.

### My baseline inspection

In PowerShell with `kubectl` pointed at my running Docker Desktop Kubernetes cluster I used:

```powershell
kubectl get nodes
kubectl get pods
kubectl describe node docker-desktop
```

`get nodes` showed `docker-desktop` as Ready (control plane, v1.36.1). `get pods` showed three Employee API Pods at `1/1 Running`, each with one historical restart. `describe node` showed Ready and no memory, disk or PID pressure at inspection. Capacity is the total reported by this Kubernetes node. Allocatable is the amount offered for Pod scheduling after node reservations. These Docker Desktop figures describe the Kubernetes environment rather than the full physical laptop.

| Resource | Capacity | Allocatable |
|---|---:|---:|
| CPU | 8 CPU | 8 CPU |
| Memory | 8,081,048 Ki | 7,978,648 Ki |
| Pods | 110 | 110 |

Capacity = 8,081,048 ÷ 1,048,576 ≈ 7.71 GiB. Allocatable = 7,978,648 ÷ 1,048,576 ≈ 7.61 GiB. Difference = 102,400 Ki ÷ 1,024 = 100 MiB. The eight allocatable CPUs are shared with the scheduled workloads. **Evidence S001–S004.**

## T002 — Requests and node resource accounting

My CPU request of `100m` asks the scheduler to account for 0.1 CPU when placing each Employee API container. At runtime, CPU requests also help determine the container's relative share under contention. It can use less when idle and more when it has work and CPU is available, subject to its limit. My memory request of `128Mi` accounts for 128 MiB in placement and provides an important reference point for memory-pressure eviction. The scheduler checks incoming requests against allocatable resources and existing requests.

### My Employee API teaching example

These figures are illustrative CPU demands, expressed as a percentage of one CPU. The request is 100m and the limit is 500m.

| Work on the API | Demand | What I expect |
|---|---:|---|
| Idle | 20m (2%) | Uses less than request |
| Simple GET | 50m (5%) | Uses less than request |
| Moderate processing | 200m (20%) | Can run above request if CPU is available |
| Heavy processing | 500m (50%) | At the configured limit |
| CPU-intensive operation | 800m (80%) | Demand exceeds limit and can be throttled |

For MES, 100 Station Managers at 100m each would request 10,000m = 10 CPUs in total. Actual usage can go up with processing or down when stations are idle. With a simplified four-CPU node, eight Station Managers at 500m each consume the entire 4,000m request budget before accounting for system reservations or existing workloads. This is why capacity planning matters at 100–200 instances. Station Manager and PDT were production contexts for the lesson, while the actual deployment exercise used Employee API.

### Why 850m became 1150m

Employee API was the only application I deployed. The `kube-system` Pods were already scheduled and had their own requests. CoreDNS resolves cluster names. etcd stores cluster state. The API server serves API requests. The controller manager reconciles desired state, and the scheduler chooses nodes for Pods.

| Existing component | CPU request | Memory request | Memory limit |
|---|---:|---:|---:|
| CoreDNS × 2 | 2 × 100m | 2 × 70Mi | 2 × 170Mi |
| etcd | 100m | 100Mi | 0 in table |
| kube-apiserver | 250m | 0 in table | 0 in table |
| kube-controller-manager | 200m | 0 in table | 0 in table |
| kube-scheduler | 100m | 0 in table | 0 in table |
| kube-proxy, storage-provisioner, vpnkit-controller | 0 in table | 0 in table | 0 in table |
| **Baseline total** | **850m** | **240Mi** | **340Mi** |

100 + 100 + 100 + 250 + 200 + 100 = 850m. That is 85% of **one** CPU, or 850 ÷ 8,000 × 100 = 10.625% of my node's allocatable CPU (displayed as 10%). It is accounted capacity. A CPU limits total of zero at baseline indicates zero configured CPU limits in the reported sum, and those workloads can still run. Likewise, 70 + 70 + 100 = 240Mi of requested memory.

| Resource | Per API Pod | Added for 3 Pods | Baseline | Expected and observed after rollout |
|---|---:|---:|---:|---:|
| CPU requests | 100m | 3 × 100m = 300m | 850m | 850 + 300 = **1150m** |
| CPU limits | 500m | 3 × 500m = 1500m | 0 | 0 + 1500 = **1500m** |
| Memory requests | 128Mi | 3 × 128Mi = 384Mi | 240Mi | 240 + 384 = **624Mi** |
| Memory limits | 256Mi | 3 × 256Mi = 768Mi | 340Mi | 340 + 768 = **1108Mi** |

The exact post-rollout shares are `1150 ÷ 8000 = 14.375%` for CPU requests and `1500 ÷ 8000 = 18.75%` for CPU limits. The node display shows whole percentages (14% and 18%). Relative to 7,978,648 Ki allocatable memory, `624 × 1024 ÷ 7,978,648 × 100 ≈ 8.01%` and `1108 × 1024 ÷ 7,978,648 × 100 ≈ 14.22%`. My original comparison mixed allocation scopes. `kubectl describe deployment employee-api` shows the API's Pod template. `kubectl describe node docker-desktop` accounts for all the Pods on that node. **Evidence S003–S004 and S013–S015.**

## T003 — Limits and denominators

My CPU limit of 500m caps the container's CPU time over recurring enforcement periods. My memory limit of 256Mi sets an enforceable memory budget. A container can use memory above 128Mi when available, subject to its limit and node conditions. CPU limits across Pods are individual ceilings. Node totals can exceed 100% of allocatable when the cluster permits overcommit, since placement uses requests. At my current settings:

| Question I asked | Calculation | Interpretation |
|---|---|---|
| Is 500m half a CPU? | 500 ÷ 1000 = 0.5 | 50% of one CPU |
| Is 500m 6.25%? | 500 ÷ 8000 = 0.0625 | 6.25% of my eight-CPU node |
| What about three replicas? | 3 × 500 = 1500m = 1.5 CPU | 1500 ÷ 8000 = 18.75% of node capacity |
| What CPU does the API request? | 3 × 100 = 300m = 0.3 CPU | 300 ÷ 8000 = 3.75% of the node request budget |
| Is the remaining 6500m free? | 8000 − 1500 = 6500m | This is a subtraction against the three limits. Other workloads share the node, and actual free CPU varies. |

**Evidence S008, S011 and S015.** [Kubernetes resource management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)

## T004 — CPU throttling, CPU time and OOMKilled

I asked whether CPU time meant 500m. CPU time is the length of time my program actually runs on processors. 500m is a rate, roughly 0.5 CPU-seconds per second averaged over the quota periods. As a teaching approximation, over one second 1000m, 500m and 250m correspond to 1, 0.5 and 0.25 CPU-seconds. If a CPU-bound operation needs one full CPU-second, it might take about two seconds of wall time with a 500m limit. Real latency also depends on concurrency, I/O and contention. When a 1000m demand runs against this 500m limit, Linux can pause runnable work until the CPU quota replenishes. My application can continue, with slower responses or longer queues.

Memory is different in practice. If my process asks for more memory than its cgroup can provide and reclaim is insufficient, the kernel can kill a process. Kubernetes can report the resulting container termination as `OOMKilled`. The kubelet may restart the container according to Pod restart policy. The termination reason and restart are separate events. Exit code 137 means SIGKILL and can also arise after another forced kill, including a liveness-related shutdown that exceeds the grace period. I would check the termination reason and Events.

| Teaching timeline | Start | Step 1 | Step 2 | Step 3 | Step 4 |
|---|---:|---:|---:|---:|---:|
| Memory use or demand (MiB) | 80 | 140 | 210 | 250 | 280 |
| Limit (MiB) | 256 | 256 | 256 | 256 | 256 |

At the last step, 280 − 256 = 24 MiB more is wanted. This models an allocation that may fail or cause an OOM kill, rather than steady observed usage above the limit. For MES Station Manager, MQTT bursts can produce slow processing or a growing queue under CPU throttling. A queue that grows in memory may cause an OOM interruption. Acknowledgements, retries and recovery matter if work was in flight. Applied to an HMI, slow processing can appear as delayed updates, and a restart can interrupt updates until recovery. The HMI interpretation here is a recall aid, with no measured HMI result.

I deferred the isolated CPU experiment. The proposal was a temporary test workload with a 500m limit and deliberate CPU-bound demand, observing Linux cgroup throttling counters without Metrics Server, then removing the test workload. The lesson had enough evidence without stressing the laptop. I did not run an OOM experiment. **S008 and S011 show the configured limits only.**

## T005 — Deployment YAML, validation and rollout

In `01-python-fastapi/k8s/deployment.yaml` I added the following block to the existing Employee API container under `spec.template.spec.containers`, alongside the image fields and at the same indentation as the container's `envFrom`. These were the proposed learning values first and the applied values after rollout. The numbers let me see the difference between baseline requests and higher enforced limits. Production sizing was outside this exercise.

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

The same existing container uses `employee-api:v16` and `imagePullPolicy: IfNotPresent`. The Deployment output also shows its existing probes, ConfigMap and Secret reference. These are context for locating the changed block. The Day 37 operation applied the resource settings.

| Step | Command or action in PowerShell | Expected and observed result | Evidence |
|---|---|---|---|
| Edit the file | Open `01-python-fastapi/k8s/deployment.yaml` | Resource block appears under the app container | S008 |
| Validate | `kubectl apply --dry-run=server -f .\k8s\deployment.yaml` | Server accepted manifest and reported `configured (server dry run)`. The dry run does not persist it. | S009 |
| Apply | `kubectl apply -f .\k8s\deployment.yaml` | `deployment.apps/employee-api configured` | S010 |
| Wait | `kubectl rollout status deployment/employee-api` | Waited through updated replicas and old Pod termination, then reported success | S010 |
| Check Pods | `kubectl get pods` | Three new Pods `1/1 Running` with zero restarts. Old Pods still showed `Terminating` during the transition. | S010 |
| Inspect Deployment | `kubectl describe deployment employee-api` | Three desired, updated, total and available, zero unavailable. RollingUpdate, correct resource fields, new ReplicaSet and scaling Events. | S011–S012 |
| Check node totals | `kubectl describe node docker-desktop` | Observed all four expected totals from T002 | S013–S015 |

The relative file path assumes the PowerShell working directory is `01-python-fastapi`. The cluster and Deployment already existed. Server dry run uses API server validation and admission before I apply. The Pod template change triggers a ReplicaSet rollout, so seeing old Pods terminate alongside new ready Pods fits RollingUpdate. The Deployment display showed 25% max unavailable and 25% max surge (existing strategy fields). For three replicas, those percentages round down to zero unavailable and up to one surge Pod respectively. During rollout my snapshot can temporarily contain both generations. I use the later snapshot for steady-state resource comparison.

## T006 — Metrics Server, Metrics API and troubleshooting

I first confused `kubectl` with kubelet and assumed an API server that knows about Pods must already have every kind of resource data. `kubectl` is the client I run in PowerShell. Kubelet is the agent on each node. It manages local Pods, reports status and exposes node/container resource measurements. Commands such as `get pods` use the ordinary Kubernetes API. `describe node` reports declared configuration and status, and its allocated-resources table sums requests and limits.

```text
Object query:  kubectl get pods → Kubernetes API server → Pod objects and status
Metrics flow:  containers / runtime → kubelet on each node → Metrics Server scrapes
Metrics query: kubectl top → Kubernetes API server / aggregation
                           → metrics.k8s.io API backed by Metrics Server
```

My MES analogy was a client asking a REST API for station production counts. The REST endpoint is the entry point and the collection service supplies the measurements. Metrics Server is the collector and serving component, and Metrics API is the interface. `kubectl top` uses recent CPU and memory data, and the resource metrics pipeline can also feed autoscaling. That data is separate from the manifest and node accounting. A full historical monitoring system was outside this exercise. [Kubernetes resource metrics pipeline](https://kubernetes.io/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/)

| I ran | Observed | Interpretation |
|---|---|---|
| `kubectl top nodes` and `kubectl top pods` | `error: Metrics API not available` for both | Live resource metrics were unavailable. |
| `kubectl get deployment metrics-server -n kube-system` | Deployment `metrics-server` NotFound | The usual Metrics Server Deployment was absent in that namespace. |
| `kubectl get apiservice v1beta1.metrics.k8s.io` | APIService NotFound | The usual aggregation registration was absent. |

If an APIService exists but shows `Available=False`, I would investigate its backing service, endpoints and collector health. If it shows `Available=True` and top still fails, I would examine permissions, metrics freshness and the actual response. I deferred installation and enablement to Day 38. The API server, scheduler and kubelet could already accept and enforce resource configuration, so I continued the rollout. **Evidence S005–S007.**

## T007 — QoS, node-pressure eviction and Pod Priority

QoS means Quality of Service. For the container-level configuration in this lab, Kubernetes derives a Pod's class from CPU and memory settings across its containers:

| Class | Rule for this lab | Example |
|---|---|---|
| BestEffort | No container has CPU or memory requests or limits | An unconfigured background helper, assuming admission adds none |
| Burstable | At least one container specifies a CPU or memory request or limit, and the Pod fails the Guaranteed test | Employee API: 100m/128Mi requests and 500m/256Mi limits. A Station Manager with requests below limits also fits this pattern. |
| Guaranteed | Each container has CPU and memory requests and limits, with each request equal to its corresponding limit | Teaching variant: both CPU request and limit 500m, both memory request and limit 256Mi. This was never applied. |

For the BestEffort teaching variant, omit the CPU and memory resource declarations. For the Guaranteed variant, use:

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "256Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

In the real lab the expected `Burstable` class is inferred from the deployed manifest. The following optional check was discussed and deferred:

```powershell
kubectl get pods -l app=employee-api -o custom-columns='NAME:.metadata.name,QOS:.status.qosClass'
```

### What would happen during memory pressure?

I initially tried to equate the three QoS names to eviction priority. The kubelet ranks candidates by whether their usage exceeds requests, then by Pod Priority, then by usage relative to requests. In this memory example the final comparison uses memory above request in absolute units. BestEffort Pods with any usage are above their zero request. A Burstable Pod can be above or below request. A Guaranteed Pod at its request ranks after above-request Pods in this example. A Guaranteed Pod can still be evicted under severe pressure. Eviction terminates the Pod, and a Deployment may create a replacement. Memory-limit enforcement can kill a container even if the node as a whole has free memory.

| Pod | QoS | Memory request | Memory limit | Usage | Usage minus request |
|---|---|---:|---:|---:|---:|
| A | BestEffort | 0Mi | None | 1Mi | +1Mi |
| B | Burstable | 128Mi | 200Mi | 199Mi | +71Mi |
| C | Guaranteed | 256Mi | 256Mi | 256Mi | 0Mi |

Assume memory pressure, these are the relevant candidates, and all have priority 0. B has 1Mi of headroom to its limit (200 − 199) and is 71Mi over request (199 − 128). A and B are in the above-request group. With equal priority B ranks ahead of A for eviction because 71Mi > 1Mi. C is at request. At exactly 200Mi, B would be 72Mi above request (200 − 128). Sustaining 300Mi is plausible if B's limit were 500Mi, and would put it 172Mi above request (300 − 128). With the original 200Mi limit, 300Mi is a **demand** 100Mi beyond the limit (300 − 200). It can trigger OOM enforcement rather than serve as a steady 300Mi eviction sample. [Kubernetes node-pressure eviction](https://kubernetes.io/docs/concepts/scheduling-eviction/node-pressure-eviction/)

### Who decides priority?

An administrator or deployment author selects importance through a named `PriorityClass`. With no explicit class and no cluster-wide default, a Pod's priority is 0. Higher numbers mean higher priority. My example ranks 1001 above 1000 above 0. They need no consecutive numbering and the importance choice is independent of QoS. When Pods are in the same above-request group, lower-priority Pods are generally considered before higher-priority ones. A critical Station Manager might use a higher class than an ordinary application. I discussed this teaching manifest and did not create or apply it:

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: station-manager-high
value: 1001
globalDefault: false
```

`PriorityClass` is cluster-scoped. `value` defines ordering, and `globalDefault: false` means this class will not become the default for unspecified Pods. To select it, set `priorityClassName: station-manager-high` under a Pod's `spec`, or under `spec.template.spec` in a workload template. **S008/S011 support the actual Employee API QoS inference.**

## Quick recall

- **Placement:** capacity → allocatable → existing requests + incoming request.
- **CPU:** divide millicpu by 1000 for CPU units, by 8000 for my node share.
- **Memory:** `Mi` is binary. A request accounts for placement and informs eviction. A limit creates a container memory budget.
- **Observed or configured?** `describe node` shows the accounted amounts. `top` needs a working metrics pipeline to show recent use.
- **Diagnose the outcome:** slow CPU-bound work can mean throttling. `OOMKilled` points to a memory kill. `Evicted` calls for node pressure and Pod event investigation.
- **QoS and priority:** resource declarations derive the class. PriorityClass sets numeric importance. Memory eviction compares above-request status, priority and above-request usage.

## Coverage audit and my final state

| Topic | Checked against the original discussion | Original evidence |
|---|---|---|
| T001 | Node vs Pod ownership, unit questions, physical and logical CPU, compute vs memory conversions, capacity vs allocatable, node/Pod checks | S001–S004 |
| T002 | Requests vs live usage, five API cases, Station Manager sizing, component-by-component system totals, 850m misconception, observed reconciliation | S004, S013–S015 |
| T003 | Four resource values, three-replica arithmetic, one-CPU vs eight-CPU denominator, remaining CPU caveat | S008, S011, S015 |
| T004 | Throttling, CPU time approximation, memory progression, 137 caveat, MQTT analogy and deferred experiments | Configured limits in S008/S011. Behaviour examples were conceptual. |
| T005 | Manifest location, validation vs persistence, successful rolling update, replicas, Events and follow-up inspection | S008–S015 |
| T006 | `kubectl` vs kubelet, metrics collection and query paths, MES analogy, errors, diagnosis and Day 38 deferral | S005–S007 |
| T007 | QoS classes and YAML comparisons, optional command, memory scenarios, ordering, default and explicit priorities, PriorityClass YAML | S008/S011 for resource configuration. The QoS command and eviction examples were not run. |

I finished with three available Employee API replicas using the applied resource block, and the node totals matched the expected values. I left Metrics Server installation for Day 38. The optional QoS query, controlled CPU test and OOM test were not run, so no test workload needed cleanup. Git review/commit was discussed as a follow-up, with no completed Day 37 commit recorded.
