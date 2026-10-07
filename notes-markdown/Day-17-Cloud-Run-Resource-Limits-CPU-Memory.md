# Day 17 – Cloud Run Resource Limits: CPU & Memory

## Practical setup

| Setting           |   Value | Meaning                                            |
| ----------------- | ------: | -------------------------------------------------- |
| CPU               |  1 vCPU | Processing allocation for each instance            |
| Memory            | 512 MiB | Memory limit for each instance                     |
| Maximum instances |       2 | Configured autoscaling ceiling for this experiment |
| Concurrency       |       1 | One incoming request at a time per instance        |

These are the experiment's settings, not universal Cloud Run defaults. Two instances each have their own 1 vCPU and 512 MiB. They do not share one 512 MiB pool.

## CPU and memory behave differently

**CPU at 100%:** the allocated CPU is fully busy. Reaching 100% does not itself terminate the instance. Under sustained demand, capacity pressure can increase response times and waiting. Autoscaling can add instances when the configuration allows it.

**Memory above 512 MiB:** exceeding the configured memory limit causes Cloud Run to terminate the instance. This is an out-of-memory (OOM) condition, and requests being processed can fail. A CPU calculation loop does not necessarily need much memory.

## Day 16 compared with Day 17

| Experiment | Work performed                                                 | What it taught                                                         |
| ---------- | -------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Day 16     | `time.sleep(10)` keeps the request open while its thread waits | Concurrency and scaling can matter even with little CPU work           |
| Day 17     | 50,000,000 iterations calculating and accumulating `i * i`     | Real CPU work, resource utilization, and scaling under parallel demand |

The sleep was not part of the Day 17 `/cpu-test` route. The workload initially used 10 million iterations, then increased to 50 million so its CPU activity was easier to observe.

Illustrative workload matching the learning experiment:

```python
total = 0
for i in range(50_000_000):
    total += i * i
```

## Observed results

| Observation                                  |                     Approximate value |
| -------------------------------------------- | ------------------------------------: |
| Local 10M test                               |                                1.13 s |
| Local 50M test                               |                                4.31 s |
| Cloud Run 50M test, first call               |                                6.30 s |
| Cloud Run 50M test, second call              |                                6.54 s |
| CPU utilization highlighted on graph         |                                   30% |
| Memory utilization highlighted on graph      |                                   15% |
| Container instance count under parallel load |                             Reached 2 |
| Max concurrent requests graph                | Increased, with plotted values near 2 |

The measured Cloud Run durations were approximately 6.3–6.5 seconds. These are client-side elapsed times from `Measure-Command`, including the HTTP request. They are not isolated CPU execution times or a controlled laptop-versus-cloud benchmark. Hardware, CPU allocation, network overhead, and possible startup or waiting can affect timing; the screenshots do not isolate the cause of the difference.

15% of 512 MiB is `512 × 0.15 = 76.8 MiB`, or roughly 77 MiB. This is an estimate from a rounded utilization reading, not an exact memory measurement.

## Read the metrics simply

- **CPU utilization:** how much of the allocated processing capacity is being used. The displayed 30% is a sampled/aggregated reading. A short, busy calculation can have a higher instantaneous peak.
- **Memory utilization:** the fraction of the memory allocation in use. About 15% means modest memory use at the observed point.
- **Container instance count:** how many instances exist in the plotted state. Check the active/idle legend. Reaching 2 is direct evidence that the service scaled out during the parallel test.
- **Max concurrent requests:** requests overlapping in the chart's measurement scope. The graph is a metric, while concurrency=1 is a per-instance configuration. A plotted value near 2 alone does not prove that one instance served two requests; check metric scope, revision, and aggregation before comparing them.
- **Time axis and colored lines:** horizontal position shows time, vertical position shows the metric value. Read the units and legend. 50th/95th/99th percentile labels describe a distribution, not the CPU setting or the instance limit. A wide time window compresses a short test into a narrow spike; missing data does not necessarily mean zero.

## Parallel requests and scaling

Three requests were started almost together. With concurrency=1, a busy instance has no free request slot. Cloud Run can start a second instance to handle additional demand. With both instances busy, remaining requests may wait for serving capacity, then be routed to an available instance. If capacity stays unavailable, requests can fail rather than wait indefinitely.

Cloud Run considers CPU and request-concurrency signals. **The 30% CPU reading did not determine an exact instance count of 2.** The configured maximum bounds scaling, while incoming demand drives it. Memory utilization is not an autoscaling signal.

For this experiment, maximum instances=2 explains the intended ceiling. It is not an absolute guarantee that transient instance counts can never exceed 2: Cloud Run documents exceptions during events such as deployments and traffic surges, and service-level versus revision-level settings affect scope.

## How Does Cloud Run Decide If More Instances Are Needed?

Cloud Run mainly considers how busy the existing instances are. Two important factors are:

- **Request concurrency** – how many requests an instance is handling at the same time.
- **CPU utilization** – how busy the CPU is processing the workload.

### Example

Configuration:

- CPU = 1 vCPU
- Concurrency = 1
- Max instances = 2

Request 1 arrives:

Request 1 → Instance 1 → Concurrency = 1

While Request 1 is still being processed, Request 2 arrives.

Instance 1 is already handling its configured concurrency. Cloud Run sees additional demand and can start **Instance 2**.

Request 3 may then have to wait for available capacity because the service is already at its configured **Max instances = 2**.

CPU utilization can also influence autoscaling when the application is doing CPU-intensive work.

**Important:** CPU reaching a particular value such as 30% does **not** mean Cloud Run automatically creates another instance at that value. There is no simple "30% CPU = scale" rule.

### Simple Flow

Incoming Requests  
→ Cloud Run checks workload  
→ Considers concurrency and CPU utilization  
→ Keeps existing instances or scales out  
→ Scaling cannot exceed `Max instances`

## Deployment connection

The conversation records deploying Docker image v10. Artifact Registry stores the image, a Cloud Run revision records the deployed image and configuration, and instances run that revision to serve requests. Successful deployment and a successful `/cpu-test` response demonstrate delivery and execution. Utilization and instance-count graphs demonstrate runtime behavior.

## Key takeaways

1. CPU and memory are allocated per instance.
2. CPU saturation generally means capacity pressure, not an immediate CPU-triggered crash.
3. Exceeding the memory limit can terminate the instance and fail requests.
4. Waiting requests and CPU-heavy requests can both occupy request slots, but their CPU metrics differ.
5. Parallel demand reached two instances in this experiment.
6. Read metric units, time windows, legends, and aggregation before drawing conclusions.

## Sources and evidence

The companion workbook embeds selected screenshot captures from the original conversation, with concise captions. Observed values are approximate and specific to this learning exercise.

- [Learning conversation](https://chatgpt.com/c/6aa66e73-10d4-83ed-b1d2-0f0f2ca78540)
- [Autoscaling](https://docs.cloud.google.com/run/docs/about-instance-autoscaling)
- [Memory limits](https://docs.cloud.google.com/run/docs/configuring/services/memory-limits)
- [Concurrency](https://docs.cloud.google.com/run/docs/about-concurrency)
- [Maximum instances](https://docs.cloud.google.com/run/docs/configuring/max-instances-limits)
