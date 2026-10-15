# Day 21 — My Cloud Run Monitoring and Observability Notes

Service: `employee-api` · Project: `cloud-genai-learning` · Region: `europe-west2`  
Learning sessions: 13–15 October 2026

## My quick recall card

```text
Request Count → employee-api filter → response codes starting with 5
→ last 5 minutes → Rate (requests/sec) → Sum across series
→ above 0.01/s → sustained for a 5-minute retest → incident → email
```

**My policy was named `employee-api - 5xx Error Rate Alert`, but it monitored filtered 5xx request COUNT converted to a RATE. It did not calculate the percentage of requests that failed.** The name alone does not define the calculation.

| Setting | My memory question |
|---|---|
| Rolling window | Which recent data do I use? |
| Rolling window function | What calculation do I apply to that data? |
| Across time series | How do I combine separate streams? |
| Threshold | What calculated value is unacceptable? |
| Retest window | How long must that calculated violation persist? |
| Missing data | What happens when there is no measurement? |

The companion workbook contains my original console, test, incident and email screenshots in learning order. **Learning record** is the screenshot index, with sheet names and row numbers. The five explanation screenshots supplied later are supplementary learning examples, not evidence of saved console settings.

## 1. My learning journey, in order

| Session | My activity and outcome |
|---|---|
| 13 October | Reviewed latency and HTTP errors, including actual p50/p95/p99 values. Opened Monitoring and Alerting, started a policy and found Request Count. Paused before completing filters and saving the policy. |
| 14 October | Applied the service and 5xx filters. Used a five-minute Rate window. Corrected Across time series from 99th percentile to Sum. Configured the threshold, five-minute retest, email notifications and policy name. Reviewed and created the enabled policy. |
| 14 October | Added `/test-500`, checked it locally, selected the deployed image tagged `v15`, and completed the Cloud Run update. Called the deployed endpoint with authentication, checked HTTP 500 logs and ran the repeated test. Initially the overview still showed no firing alert. |
| 14 October, email times | Received a threshold email at 9:44 PM and a missing-data email at 10:15 PM. The threshold notification reported approximately `0.02667/s` against `0.01/s`. |
| 15 October | Reviewed the open incident and logs. Investigated missing-data alerting. Changed missing-data treatment to non-violating, saved and rechecked the 5xx filter. |
| End of exercise | Turned the policy off from the Policies list and confirmed it was disabled. Decided to remove `/test-500` during the next application deployment. That cleanup was deferred. |

Those email display times are local email times. The screenshots also show UTC incident start times: 8:44 PM UTC for the threshold email and 9:15 PM UTC for the missing-data email. I must compare timestamps in the same timezone.

## 2. Monitoring, observability, metrics and logs

Monitoring tells me how my service is behaving. Observability helps me understand why, by connecting measurements with request logs and application events.

| Concept | My question | My example |
|---|---|---|
| Metric | How much, how often, or how slow? | 5xx requests/sec; p95 latency; instance count |
| Log | What happened in a particular request? | `/test-500` returned HTTP 500; the response detail identifies the intentional test |
| Alert policy | Which rule should be watched? | Above 0.01 matching requests/sec for five minutes |
| Incident | Has an evaluated rule produced a problem record? | An open alert with timing, chart, labels and related logs |
| Notification channel | Where should the message go? | My email channel |

My MES analogy: the dashboard shows station cycle time and NG counts; the event log identifies the order, station and failure. The alarm rule is the policy, the alarm occurrence is the incident, and email delivers the notification.

Earlier work provided context: CPU around 30%, maximum instances 2, concurrency 1, and parallel requests causing another instance. **Concurrency 1 limits simultaneous requests per instance; it does not make Python single-threaded.** Day 21 extended this into latency, errors and alerting. I did not configure distributed tracing in this exercise.

## 3. Latency: average, p50, p95 and p99

Latency is how long a request takes. Units matter: `1 second = 1,000 milliseconds`; `0.01 s = 10 ms`.

### Average can hide the tail

My example times were `100, 120, 150, 200, 2,000 ms`.

```text
Average = (100 + 120 + 150 + 200 + 2000) / 5 = 514 ms
```

Four requests completed within 200 ms, but one took two seconds. The average alone does not explain that distribution well.

| Percentile | How I read it |
|---|---|
| p50 | Approximately 50% of measured requests were this fast or faster; the middle |
| p95 | Approximately 95% were this fast or faster; helps expose the slow tail |
| p99 | Approximately 99% were this fast or faster; further into the slow tail |

These are distribution cutoffs. p95 does not mean 95% took exactly that long, were slower, or failed. p99 is not necessarily the maximum. Monitoring derives percentiles from distribution data; tiny teaching examples do not reproduce its exact interpolation.

### Actual values I inspected

| Chart point | p50 | p95 | p99 | My interpretation |
|---|---:|---:|---:|---|
| 6 October 2026, 7:00 PM | 0.01 s / 10 ms | 10.42 s / 10,420 ms | 10.49 s / 10,490 ms | Typical requests were fast, but part of the tail was very slow |
| 11 October 2026, 11:48:53 AM | 5 ms | 9.5 ms | 9.9 ms | All three displayed cutoffs were below 10 ms |

These belong to the selected chart point and aggregation, not automatically every request across the whole displayed date range. The original charts are embedded in **Latency and metrics**.

My confusion: “If 50% finished in 0.01 s, how can 95% be at 10.42 s?” **The fastest 50% are included inside the fastest 95%.** The p95 statement includes fast requests too.

An illustrative sorted group of 100 requests could have requests 1–50 around 0.01 s, 51–90 around 0.02 s, 91–95 around 10.42 s, 96–99 up to 10.49 s, and the final request slower. This is a memory example, not my actual measured distribution.

My analogies:

- Age: “95% are aged 25 or younger” includes babies, teenagers and 25-year-olds. It does not say everyone is 25.
- Exam marks: p50 of 60 and p95 of 95 describe two cutoffs; they do not mean 95% scored exactly 95.
- Height: p95 of 180 cm means about 95% are at or below 180 cm, not taller.
- MES cycle time: typical orders can be fast while a small group waits a long time. Tail percentiles expose that experience.

The earlier deliberate delay/parallel test was a possible explanation for the high tail. I should verify the cause with matching logs. The chart alone does not prove a cold start, database delay or a particular code path.

## 4. HTTP response classes: what am I counting?

| Class | Meaning in my exercise |
|---|---|
| 2xx | Successful response, such as 200 or 201 |
| 4xx | Request/access/input problem, such as 404 or 403; context matters |
| 5xx | Server failure response, such as 500, 502, 503 or 504 |

A 404 can be the correct response to an unknown employee/order ID. Repeated unexpected 404s in HMI/MES can still indicate a bad URL, missing order or integration issue. A 500 indicates a server failure response. My temporary route intentionally generated it.

Quiz: 100 requests = 90 HTTP 200 + 5 HTTP 404 + 5 HTTP 500. All HTTP error responses are 10%, but **5xx server errors are 5%**. My policy keeps the five HTTP 500 responses and excludes the 404s.

## 5. Request COUNT, request RATE and error PERCENTAGE

I must write the unit and denominator. These quantities answer different questions.

| Quantity | Calculation | Unit | Question |
|---|---|---|---|
| Request count | Number of matching requests | requests | How many? |
| Total request rate | All requests / seconds | requests/sec | How much overall traffic per second? |
| 5xx request rate | 5xx requests / seconds | matching requests/sec | How frequently do errors occur? |
| 5xx error fraction | 5xx requests / all requests | dimensionless | What share failed? |
| 5xx error percentage | Fraction × 100 | % | What percentage failed? |

### My employee-api example: 100 requests in five minutes

100 total requests = 90 successful + 10 HTTP 500. Five minutes = 300 seconds.

```text
Total request rate = 100 / 300 = 0.33333 requests/sec
5xx request rate   =  10 / 300 = 0.03333 matching requests/sec
5xx error fraction =  10 / 100 = 0.10
5xx percentage    =  0.10 × 100 = 10%
```

For a rate I divide by **time**. For a percentage I divide by **all requests**. The 5xx filter only selects the numerator; it does not create the denominator.

### Same error frequency, different reliability

| Five-minute scenario | Total requests | HTTP 500 | 5xx rate | 5xx percentage |
|---|---:|---:|---:|---:|
| A | 100 | 10 | 10/300 = 0.03333/s | 10/100 = 10% |
| B | 1,000 | 10 | 10/300 = 0.03333/s | 10/1,000 = 1% |

Both have the same error frequency. A affects a larger proportion of requests. My MES analogy is **NG parts per second** versus **NG parts divided by total inspected parts**.

Other calculations I discussed:

| Example | 5xx rate | 5xx percentage |
|---|---:|---:|
| 1,000 requests, 20 HTTP 500 | Needs a time period to calculate /s | 20/1,000 × 100 = 2% |
| 600 requests, 30 errors, five minutes | 30/300 = 0.1/s | 30/600 × 100 = 5% |
| 200 requests, 20 errors, five minutes | 20/300 = 0.06667/s | 20/200 = 0.1 fraction = 10% |

My answer of roughly 0.06 for the last rate was rounded too far; `0.06667/s` is clearer. Fraction `0.1` means 10%, not 0.1%.

My original discussion included a percentage goal such as 5%. The implemented exercise used a simpler **5xx requests/sec threshold**. A true percentage alert needs 5xx and total requests over the same service, period and aggregation scope, followed by a ratio calculation. That denominator/formula was not configured here.

## 6. Policy creation: metric and filters

My path: **Monitoring → Alerting → Create policy → Builder → Select a metric**.

1. With **Active** enabled I initially saw no results. It can hide metrics without recent activity; turning it off allowed me to continue.
2. I inspected Request latency while finding the right item, then selected **Cloud Run Revision → Request_count → Request Count**.
3. Metric identifier: `run.googleapis.com/request_count`.
4. Filter: `service_name = employee-api`.
5. Filter: `response_code` → **starts with** → **5**.

This selects the 5xx class, including codes such as 500, 502, 503 and 504, rather than only literal 500. Seeing observed dropdown values such as 200/403 did not mean only those codes were supported.

The metric description excludes some requests that do not reach the container. I should not assume this metric records every possible access/platform failure. An authentication 403 and the application's intentional 500 are different checks.

Workbook: **Policy setup** preserves the builder, Active-filter issue, metric selection and both filters.

## 7. Rolling window: which recent data?

My **Rolling window was five minutes**. At each evaluation the calculation uses recent data spanning that window.

| Example evaluation time | Period used |
|---|---|
| 10:05 | 10:00–10:05 |
| 10:06 | 10:01–10:06 |
| 10:07 | 10:02–10:07 |

The overlapping window moves forward. This is different from a job that runs only once every five minutes. The rolling window and retest window do not set evaluation frequency. [Google's alignment and retest guide](https://docs.cloud.google.com/monitoring/alerts/concepts-indepth#alignment_periods_and_retest_windows) confirms this separation.

My memory aid is a moving CCTV view of the last five minutes: older activity drops out as new activity enters. Errors can stop happening while earlier errors remain in the lookback window for a while.

Three different time settings:

- **Chart range**, such as one hour: how much history I see.
- **Rolling window**, five minutes: data used to calculate a result.
- **Retest window**, five minutes: persistence required before opening an incident.

## 8. Rolling window function: what calculation?

My **Rolling window function was Rate**. For Request Count, it converts matching request data over time into a per-second rate. The memory calculation is `10 / 300 = 0.03333/s`. Monitoring uses sampled metric intervals and alignment; a rounded point is not a raw event export.

The dropdown also included delta, minimum, maximum, mean, count, sum and standard deviation. Suitability depends on metric type. Sum can total suitable count samples; mean gives an average; maximum selects the largest value. **A function named Count can count data points, so it must not automatically be read as HTTP request count.** My source metric is already Request Count.

Workbook: **Window and aggregation** shows the Rate dropdown and five-minute setting.

## 9. Across time series: how do I combine streams?

A time series is one stream with a particular set of labels. Request metrics can be split by revision, response code and other labels. Filtering selects streams, alignment calculates within each stream, and a reducer combines streams.

My screen initially showed **99th percentile** under Across time series. I changed it to **Sum**, with no group-by field selected, to add the matching 5xx rates.

```text
Revision A: 6 errors / 300 s = 0.02/s
Revision B: 9 errors / 300 s = 0.03/s
Across-series Sum: 0.02 + 0.03 = 0.05/s
Equivalent simple total: 15 / 300 = 0.05/s
```

The 99th percentile reducer across request-rate streams is different from p99 **latency**. It was not the right way to add service-wide 5xx volume. Sum still does not produce a percentage. Grouping retains separate results for selected label groups; without reduction, streams remain separate. [Google's aggregation guide](https://docs.cloud.google.com/monitoring/api/v3/aggregation) explains filtering, alignment and reduction.

**Any time series violates** refers to resulting monitored streams. It does not mean “any request fails” or “a percentage of requests failed.” The workbook retains both the earlier 99th-percentile selection and its correction to Sum.

## 10. Threshold: above 0.01 requests/sec

I selected a **Threshold** condition, **Above threshold**, value **0.01**, in `/s`. I did not choose forecast or a separate metric-absence condition.

```text
0.01 matching requests/sec × 60  = 0.6 matching requests/minute
0.01 matching requests/sec × 300 = 3 matching requests per five minutes
```

This is an average-rate equivalent, not three errors per second or evenly spaced errors. I multiply by seconds to convert a rate to a count equivalent.

| Errors in a simple complete 300-second window | Rate | Strictly above 0.01/s? |
|---:|---:|---|
| 2 | 0.00667/s | No: below |
| 3 | 0.01000/s | No: equal |
| 4 | 0.01333/s | Yes |

One above-threshold point is insufficient when a five-minute retest is required. Four errors do not automatically cause an instant alert.

**0.01/s is not 1%.** A dimensionless fraction of 0.01 equals 1%; events per second measure a different quantity.

## 11. Retest window: how long must the calculated violation persist?

Under **Configure alert trigger → Advanced Options**, I set **Retest window = five minutes**. Review alert also showed five minutes. Retest does not retry the API, resend requests or set an email interval. It checks the calculated metric condition. [Google's retest guidance](https://docs.cloud.google.com/monitoring/alerts/concepts-indepth#retest_windows) explains that a non-violating measurement resets the window.

### Example: sustained violation

| Time | Calculated 5xx rate | Result |
|---|---:|---|
| 10:00 | 0.005/s | Below |
| 10:01 | 0.020/s | Above; persistence starts |
| 10:02 | 0.025/s | Above |
| 10:03 | 0.020/s | Above |
| 10:04 | 0.015/s | Above |
| 10:05 | 0.020/s | Above |
| 10:06 | 0.025/s | Five minutes above; incident can open |

These are illustrative evaluation times. Data ingestion, evaluation and delivery can delay visibility. Two five-minute settings do not guarantee a fixed ten-minute wait from the first error.

### Example: reset

| Time | Rate | My conceptual counter |
|---|---:|---|
| 10:00 | 0.020/s | Starts |
| 10:01 | 0.030/s | One minute |
| 10:02 | 0.020/s | Two minutes |
| 10:03 | 0.005/s | Below: reset |
| 10:04 | 0.020/s | Starts again |
| 10:05 | 0.030/s | One minute |
| 10:09 | 0.020/s | Five minutes, if all intervening evaluations stayed above |

The omitted 10:06–10:08 points must also violate. Two separated high points do not prove continuous violation.

MES analogy: “Above 80°C for five minutes.” If the value falls to 75°C after two minutes, I cannot keep those two minutes and add three later. The confirmation period starts again. Threshold is the limit; retest confirms persistence; rolling window separately selects data used for the calculated measurement.

## 12. Email channel, naming, review and save

The dropdown initially had no available email channel. I opened **Manage notification channels → Email → Add new**, entered my address/display name, saved, returned to the policy and selected the channel. Creating a channel and attaching it to a policy are separate steps.

| Field | My recorded value |
|---|---|
| Policy | `employee-api - 5xx Error Rate Alert` |
| Condition | `employee-api - 5xx request rate` |
| Resource / metric | Cloud Run Revision / Request Count |
| Filters | `service_name = employee-api`; `response_code starts with 5` |
| Window / function | Five minutes / Rate |
| Across series | Sum; no grouping field selected |
| Trigger | Any time series violates; above 0.01/s |
| Retest | Five minutes |
| Actual severity | No severity; a suggested Warning was not the saved evidence |
| Email behavior visible later | Notify on alert open only; closure notification unchecked |
| Initial state | Enabled; policy saved confirmation |
| Missing data, later discovered | Treated as violating before correction |
| Missing data, later update | Treated as non-violating; saved |
| Final state | Disabled |

The auto-close field was left at its default; I have not recorded an exact duration. My policy documentation directed me to Cloud Run ERROR/HTTP 500 logs, recent deployments, application exceptions and service health, with project/region/service for navigation. **Trigger and save** preserves the configuration, channel-management screen, name, review and successful save.

## 13. Missing data, zero errors and scale-to-zero

**Missing is not a measurement of zero.** Zero says a measured value is zero. Missing says no value is available; it does not independently prove failure, health or the number of running instances.

| Dropdown choice | My interpretation |
|---|---|
| Missing data empty | Do not explicitly convert missing points to violating/non-violating values; incident handling depends on evaluation and auto-close behavior |
| Missing data treated as values that violate the policy condition | Absence can be treated as a problem by this threshold condition |
| Missing data treated as values that do not violate the policy condition | Absence itself is not counted as a breach of the 5xx threshold |

An earlier recommendation was non-violating treatment. The later review showed the saved policy was actually treating missing data as violating. I received a missing-data email, changed the setting to **non-violating**, saved and checked the 5xx filter. A recommendation is not the same as what was saved.

- Cloud Run can scale to zero when idle, depending on its instance configuration. No activity can be normal for my learning service.
- A 5xx-filtered metric can lack matching data while successful requests are being served.
- No 5xx data therefore does not reliably mean the service is down.
- If production activity is expected, I may need a separate all-request activity, heartbeat or availability check. This exercise did not configure that separate check.

My analogies:

- Thermometer: 90°C and 20°C are readings; a disconnected sensor is unknown, not automatically 0°C.
- Keyence camera: NG means a failed inspection, OK means a successful inspection, and no inspection is a different situation.
- MES: no messages can be expected when production is stopped. When production is running, missing messages may matter. I need production context and a suitable activity signal, not simply absence of NG events.

## 14. My practical HTTP 500 test

I added a temporary FastAPI route in `app/main.py`, after router inclusion and before the main execution block. The code discussed was:

```python
from fastapi import FastAPI, HTTPException

@app.get("/test-500")
def test_server_error():
    raise HTTPException(
        status_code=500,
        detail="Intentional error for Cloud Monitoring testing",
    )
```

The local browser at `localhost:8000/test-500` returned the intentional-error detail. Local calls verify local behavior; they do not contribute to deployed Cloud Run metrics. A handled HTTPException can return 500 without an unhandled-exception traceback.

The deployment screenshots show an image tagged **v15** and a completed Cloud Run update, including revision creation and traffic routing. A suggested example tag is not evidence of the actual deployed tag. I have not invented missing build/push command history.

### Deployed test in Cloud Shell — Bash

The service required authenticated access. I supplied an identity token without making the service public:

```bash
curl -i \
  -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
  https://employee-api-972261256506.europe-west2.run.app/test-500
```

The response screenshot showed the intentional-error JSON. In Cloud Run **Observability → Logs**, I found HTTP 500 request entries; one displayed 9 ms and curl 8.5.0. The request status confirms a matching test more directly than the JSON text alone.

Then I used the discussed Bash loop:

```bash
for i in {1..12}; do
  curl -s -o /dev/null -w "Request $i: HTTP %{http_code}\n" \
    -H "Authorization: Bearer $(gcloud auth print-identity-token)" \
    https://employee-api-972261256506.europe-west2.run.app/test-500
  sleep 30
done
```

The output showed **all 12 requests returned HTTP 500**. The loop spans roughly six minutes including its final sleep, plus token/request overhead. A simple 12/360 average is 0.03333/s; it is not necessarily the exact five-minute aligned chart value. A 404 test would not exercise this 5xx filter.

Initially the overview still showed zero firing alerts, one enabled policy and no chart data. That alone did not prove a broken policy. I needed to allow for metric visibility and retest timing, check filters and inspect logs rather than repeatedly generate errors without checking.

## 15. Incident, 0.02667/s and two different emails

The open incident showed timing, labels, documentation, chart and related request logs. Its tooltip displayed approximately **0.02667/s** with threshold **0.01/s**.

```text
0.02667 / 0.01 ≈ 2.667 times the threshold
0.02667 × 300 ≈ 8 matching requests (five-minute rate equivalent)
```

The count equivalent helps explain the unit; it does not independently prove an exact raw event count because the chart value is rounded and aligned.

| Email display time | Message | My interpretation |
|---|---|---|
| 14 October, 9:44 PM | Request Count above threshold 0.01; value about 0.0266667 | Threshold violation in rate units |
| 14 October, 10:15 PM | Request Count is missing data | A different reason; check saved missing-data treatment |

These do not prove emails repeat every five minutes. **Retest is not an email interval.** The original email bodies and incident tooltip are in **Incidents and emails**.

The incident was open for roughly 16 hours 19 minutes when reviewed the next day. That does not prove the API continuously returned 500 for the whole time; missing-data handling and incident state also matter.

I asked where five minutes was visible on the graph. One spike does not establish retest configuration. The Configure alert trigger and Review alert screens establish the saved five-minute setting.

The incident is the problem record; email is its notification. Acknowledging records that someone is handling it, rather than repairing the application. Closing an incident and disabling a policy serve different purposes. Disabling stops future evaluation of that policy; it does not remove the deployed test route.

## 16. My debugging checklist

1. Verify project, service, revision, chart range and timezone.
2. Check Request Count, service employee-api and response code starting with 5.
3. Confirm five-minute Rate and Sum across series. Read `/s`, not `%`.
4. Expand Advanced Options and verify above 0.01 and five-minute retest. The policy name is insufficient.
5. Check the deployed endpoint returns 500 with authentication. Local calls, 404s and access-denied responses are different evidence.
6. Correlate `/test-500` request logs and application details with chart time.
7. Allow for sampled-data and notification delay; verify the channel is attached.
8. Read the email reason: threshold or missing data? Inspect the saved treatment.
9. Save edits and recheck the confirmation and filters. I did this after the missing-data change.

## 17. Disabling and deferred cleanup

I first looked for a toggle on policy details and could not find it. The working path was **Monitoring → Alerting → Policies → Enabled toggle**. I confirmed turn-off and saw **Policy disabled**, the toggle off, zero firing alerts and zero acknowledged alerts, with one policy still listed.

The final screenshot proves success; the confirmation dialog only proves I reached that step. Both are preserved in **Missing data and cleanup**.

I decided to remove `/test-500` **when the next application is deployed**. Disabling the alert did not remove it. My next cleanup task is to remove the route from the application, build/deploy the next image and verify the intentional-error route is gone. That cleanup was not performed in this exercise.

## 18. My quick self-check

| Question | My answer |
|---|---|
| Is 0.01/s equal to 1%? | No: events/time versus proportion. |
| Does the 5xx filter calculate a percentage? | No: a total-request denominator is still needed. |
| Why two five-minute windows? | One selects data, the other confirms persistence. |
| Does retest call the API again? | No: it evaluates the metric condition. |
| What if the rate falls below? | The sustained-violation retest resets. |
| Does Sum produce a percentage? | No: it adds matching rates across streams. |
| Is p95 the same as 95% errors? | No: it is a response-time cutoff. |
| Does missing 5xx data prove downtime? | No: it can mean no matching failures or no activity. |
| Was this a true error-percentage alert? | No: filtered Request Count was converted to requests/sec. |
| What triggered the threshold notification? | Approximately 0.02667/s against 0.01/s. |
| What remains for the next deployment? | Remove /test-500 and verify the deployed result. |

## My visual reference

Open `Day_21_Screenshot_Workbook.xlsx` beside these notes. **Learning record** lists embedded screenshots and their sheet/row positions. The captions distinguish initial setup, corrections, test evidence and final state. Screenshots retain their original contents; they are not recreated console images. Later explanation attachments are collected separately in **Learning examples**.

### Screenshot-by-screenshot index

| No. | My screenshot | Workbook sheet | Row |
|---:|---|---|---:|
| 1 | My high-tail latency chart | Latency and metrics | 8 |
| 2 | My low-latency chart | Latency and metrics | 27 |
| 3 | Open Monitoring | Policy setup | 8 |
| 4 | Start from Alerting | Policy setup | 36 |
| 5 | Create alerting policy in Builder | Policy setup | 63 |
| 6 | No metric results with Active enabled | Policy setup | 92 |
| 7 | Turn off Active to find Cloud Run | Policy setup | 126 |
| 8 | Select Cloud Run Request Count | Policy setup | 165 |
| 9 | Filter my service | Policy setup | 192 |
| 10 | Keep response codes starting with 5 | Policy setup | 223 |
| 11 | Set five-minute Rate window | Window and aggregation | 8 |
| 12 | Inspect rolling-window functions | Window and aggregation | 40 |
| 13 | Earlier reducer: 99th percentile | Window and aggregation | 73 |
| 14 | Correct reducer to Sum | Window and aggregation | 105 |
| 15 | Configure alert trigger and Advanced Options | Trigger and save | 8 |
| 16 | No available notification channel yet | Trigger and save | 40 |
| 17 | Manage email notification channels | Trigger and save | 72 |
| 18 | Policy documentation, severity and name | Trigger and save | 104 |
| 19 | Review alert before creation | Trigger and save | 142 |
| 20 | Policy created and enabled | Trigger and save | 173 |
| 21 | Check the temporary route locally | HTTP 500 test | 8 |
| 22 | Select the actual deployed image | HTTP 500 test | 23 |
| 23 | Cloud Run update completes | HTTP 500 test | 53 |
| 24 | Authenticated deployed curl response | HTTP 500 test | 74 |
| 25 | Confirm HTTP 500 in request logs | HTTP 500 test | 84 |
| 26 | Repeated test output | HTTP 500 test | 93 |
| 27 | Next-day overview: one firing alert | Incidents and emails | 8 |
| 28 | Inspect the actual incident and rate | Incidents and emails | 37 |
| 29 | Threshold notification email | Incidents and emails | 67 |
| 30 | Missing-data notification email | Incidents and emails | 91 |
| 31 | Debugging instructions inside the email | Incidents and emails | 114 |
| 32 | Review missing-data choices | Missing data and cleanup | 8 |
| 33 | Change treatment to non-violating | Missing data and cleanup | 36 |
| 34 | Save the missing-data correction | Missing data and cleanup | 66 |
| 35 | Recheck the metric filters | Missing data and cleanup | 98 |
| 36 | Saved notification behavior | Missing data and cleanup | 132 |
| 37 | Turn off the policy from the Policies list | Missing data and cleanup | 162 |
| 38 | Confirm final disabled state | Missing data and cleanup | 189 |
| 39 | 100 requests in five minutes | Learning examples | 8 |
| 40 | Same frequency, different percentage | Learning examples | 38 |
| 41 | Sustained calculated violation | Learning examples | 55 |
| 42 | Window, function, threshold and retest | Learning examples | 85 |
| 43 | Retest resets on a normal point | Learning examples | 118 |
