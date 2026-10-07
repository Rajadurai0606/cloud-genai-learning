# Day 18 — Cloud Run Structured Logging & Troubleshooting

Date: 7 October 2026  
Source: [New_Learning_1](chatgpt-conversation://6aa66e73-10d4-83ed-b1d2-0f0f2ca78540)

## What we achieved

The final **v14** test showed exactly **one INFO, one WARNING and one ERROR** for each landing-endpoint call, with the correct Cloud Logging severity. The CPU-test start and completion messages also appeared once each. Separate HTTP access and platform lifecycle logs still exist; those are different messages.

## Starting problem: DEFAULT severity

The application already called `logger.info()`, `logger.warning()` and `logger.error()`. Locally, the terminal displayed their level names. In the initial Cloud Run experiment (v11), the application messages appeared with **DEFAULT** severity.

Python knew each message's level, but its plain-text output did not supply structured GCP severity metadata. A word such as `ERROR` inside text is not the same as a recognized `severity` field in a structured log.

## What changed during the experiments

| Stage | What we did or observed | What we learned |
| --- | --- | --- |
| Local | Printed INFO, WARNING and ERROR in the terminal. | The application logging calls were already present. |
| v11 | Cloud Run showed DEFAULT severity for the plain-text application messages. | Cloud Logging needed structured severity metadata. |
| Preparation | Installed `google-cloud-logging`. | The package supplies Google's Python logging integration and `StructuredLogHandler`. |
| v12 | Tried `google.cloud.logging.Client().setup_logging()`. Severity became correct, but messages appeared twice. | Correct severity and duplicate prevention are separate things to check. |
| v13 | Kept `basicConfig()` in the local-only branch. Cloud logs still duplicated INFO/WARNING/ERROR and CPU-test messages. | Removing local `basicConfig()` from the Cloud Run path did not fully solve duplicates. |
| v14 | Replaced root handlers with one explicit `StructuredLogHandler`. | Correct severity and single application-message output were verified. |

The earlier explanation blaming `basicConfig()` alone was incomplete. Multiple active handlers or logging paths were suspected; the exact internal duplicate path was not proven. The explicit root-handler configuration resolved the observed duplication.

## Package and Cloud Run detection

The package installed today was:

```text
google-cloud-logging
```

`K_SERVICE` is a **service-name environment variable provided by Cloud Run**. Here, `os.getenv("K_SERVICE")` selects the Cloud Run logging branch when that variable has a value. It is not a secret or something we needed to manually add for this test. Locally, when it is absent, the code uses the local branch.

## First attempt

```python
import google.cloud.logging

if os.getenv("K_SERVICE"):
    logging_client = google.cloud.logging.Client()
    logging_client.setup_logging()
else:
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(name)s - %(message)s"
    )
```

This integration gave the application messages the correct severity, but the v13 screenshot confirmed that even after separating the local branch, the Cloud Run messages still appeared twice.

## Final main.py logging configuration

```python
import logging
import os

from google.cloud.logging_v2.handlers import StructuredLogHandler

if os.getenv("K_SERVICE"):
    # Cloud Run: structured container logs.
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(StructuredLogHandler())
else:
    # Local: readable console logs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(name)s - %(message)s"
    )
```

The final branch replaces `Client().setup_logging()`. The `import google.cloud.logging` and client setup calls are no longer needed for this configuration. The `google-cloud-logging` package remains needed for the structured handler import.

### Each line explained simply

| Line | Meaning |
| --- | --- |
| `logging.getLogger()` | Get the root logger: the central logger used by normal upward propagation. No name means the root logger. |
| `root_logger.handlers.clear()` | Remove handlers currently attached to the root logger so they do not also write the same message. This clears root handlers, not every named logger's handlers. |
| `root_logger.setLevel(logging.INFO)` | Set the root logger's threshold to INFO. Loggers inheriting this level allow INFO, WARNING, ERROR and CRITICAL, while DEBUG is filtered. A named logger with its own explicit level can behave differently. |
| `root_logger.addHandler(StructuredLogHandler())` | Attach one Google handler that formats messages as structured JSON with fields such as severity for Cloud Run's container-log collection. |

### Logger versus handler

A **logger** is what the application calls to create a log message and label its level. A **handler** decides how and where to write that record.

```python
logger = logging.getLogger(__name__)
logger.info("This is an INFO log")
logger.warning("This is a WARNING log")
logger.error("This is an ERROR log")
```

Normally, these named application loggers propagate records to the root logger. The structured handler emits JSON to the container's output stream, Cloud Run collects it, and Cloud Logging recognizes the severity. The application logging calls themselves did not need to change.

`logging.basicConfig()` in the local branch sets up readable console output, including the level, logger name and message.

## Final v14 verification

The final screenshot showed:

- One `This is an INFO log`, marked INFO.
- One `This is a WARNING log`, marked WARNING.
- One `This is an ERROR log`, marked ERROR.
- One `CPU test started` and one `CPU test completed` for the CPU-test request.

The screenshot contains more than one landing request. Each request has its own single set of messages; this is different from the v13 duplicate pairs for the same request.

## Why “Application shutdown complete” appeared

The sequence `Waiting for application shutdown`, `Application shutdown complete` and `Finished server process [1]` means the **Uvicorn process gracefully stopped**.

With minimum instances set to zero, Cloud Run may scale down when there is no traffic. Revision replacement after deploying v14 is another plausible reason for a shutdown. The lines alone do not prove the cause, and they do not mean Cloud Run necessarily stopped immediately after a request finished. A shutdown message is not automatically an application error.

## Screenshots in the Excel recap

The workbook embeds the accessible v13 duplicate-log screenshot, the final main.py configuration screenshot, and the final v14 logs showing correct severity and single CPU-test messages. Earlier local, v11 and v12 screenshots were not returned by the available conversation retrieval, so those stages are recapped in text. Repetitive deployment screenshots were omitted.

## Suggested Git commit message

```text
Configure structured Cloud Run logging and resolve duplicate application logs
```
