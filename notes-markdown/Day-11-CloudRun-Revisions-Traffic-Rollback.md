# Day 11 - Cloud Run revisions traffic and rollback
Date: 28-Sep-2026

## Concepts in this file
- build versus tag versus push
- service versus revision
- v1 and v2
- traffic percentages
- rollback
- restore
- reference commands

## ORIGINAL LEARNING NOTES

## Day 11 - Cloud Run Revisions, Traffic Management and Rollback

## Objective

Deploy v2 of the FastAPI app, practise rollback to v1, then restore v2.
Understand how images, revisions and traffic fit together.

## Source coverage

The retrieved Day-11 conversation contains the final rollback/restoration
messages and five original screenshots. Earlier build/deployment messages
and exact Day-11 command lines were not returned. The complete Docker commands
below are repeatable reference commands based on the established names, not
a verified transcript of the commands typed that day.
The format follows the available Day-10-Notes-Append.txt. The repo's actual
01-python-fastapi/Notes.txt was not available for comparison.

What I completed (recorded Day 11 experiment)

- Project: cloud-genai-learning
- Region: europe-west2
- Cloud Run service: employee-api
- Local v2 image name recorded in the chat summary: employee-api:v2
- New revision: employee-api-00002-pxz
- Previous revision: employee-api-00001-w6s
- Rolled traffic back to v1 and verified the old response.
- Restored traffic to v2 and verified the new response.
- Final traffic: v2 100%, v1 0%.

## Public URL

https://employee-api-972261256506.europe-west2.run.app

## Application responses

v1:
"hello Raja"

v2:
{"message":"Employee API","version":"2.0"}

## Workflow recorded in the chat summary

```text
Change code -> test locally with Python -> build employee-api:v2
-> test Docker container locally -> tag image -> push image
-> Artifact Registry -> deploy a Cloud Run revision -> route traffic
```

The local code/test, build, container test, tag/push, image-selection and
deployment-diff screenshots were not available in the retrieved conversation.
The exact source edit, local test command, build/run options, full v2 registry
tag and image digest therefore still need the earlier messages as evidence.

## Docker commands - build, tag and push v2

These reference commands use the recorded local name employee-api:v2 and the
image path established in Day 10, with the v2 tag. The earlier Day-11 transcript
is needed to confirm that these are exactly the command lines used that day.

Before starting
- Have Docker Desktop running.
- Open the terminal in 01-python-fastapi, where the Dockerfile is located.
- Use the existing cloud-genai-learning project and employee-api repository.
- Docker must be authenticated to the registry. If needed, run:

```powershell
gcloud auth configure-docker europe-west2-docker.pkg.dev
```

## 1. Build the image

```powershell
docker build -t employee-api:v2 .
```

Easy explanation:
- docker build = build an image using the Dockerfile.
- -t employee-api:v2 = give the image the name employee-api and tag v2.
- The final dot means use this folder as the build context (the files Docker
can use for the build).
- The result is a local image. It has not been uploaded to GCP yet.

## 2. Give that same image its registry destination name

```powershell
docker tag employee-api:v2 europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:v2
```

Easy explanation:
- The first name is the image we already built on the laptop.
- The second name is another name pointing to that SAME image.
- Docker tag does not copy the image or build another image.
- Think of it as putting a second address label on the same package.
- The longer name tells Docker where to push the image when we run push.
- Nothing is uploaded by this tag command.

## Reading the longer name:

europe-west2-docker.pkg.dev / cloud-genai-learning / employee-api / employee-api : v2
Registry host                GCP project            Repository     Image name     Tag

The two employee-api parts have different jobs: the first is the repository
(the storage location), and the second is the image name inside it.

## 3. Push the image to Artifact Registry

```powershell
docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:v2
```

Easy explanation:
- Push uses the full destination name we added in step 2.
- It uploads the image content needed by that registry.
- Docker may say a layer already exists if it does not need to upload it again.
- Wait for successful completion and the image digest in the output.
- The image is now available in Artifact Registry for Cloud Run to deploy.
- Push does not automatically deploy a new Cloud Run revision. Deployment is
the next, separate step.

## Quick reminder

Build = create the local image.
Tag   = add another name/address pointing to the same local image.
Push  = upload the image to the registry using that address.

## Alternative: build with the full destination name from the start

```powershell
docker build -t europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:v2 .
docker push europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:v2
```

Here, the build command already gives the image its full registry name, so a
separate docker tag command is unnecessary. This is an alternative workflow,
not an additional step after the three commands above or a claim that we used
this shortcut on Day 11.

## Other commands established in available material

The following complete reference commands already appear in the available
Day-10 notes. They are useful for revisiting this service, but are NOT a record
of commands executed on Day 11. Nothing was executed against GCP to prepare
these learning artifacts.

Check configured project
```powershell
gcloud config get-value project
```

Configure Docker authentication for the registry host (if needed)
```powershell
gcloud auth configure-docker europe-west2-docker.pkg.dev
```

List uploaded images and tags
```powershell
gcloud artifacts docker images list europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api --include-tags
```

Inspect the Cloud Run service
```powershell
gcloud run services describe employee-api --region=europe-west2 --project=cloud-genai-learning
```

Check the public root response
curl.exe -i https://employee-api-972261256506.europe-west2.run.app/

Read recent service logs
```powershell
gcloud run services logs read employee-api --region=europe-west2 --project=cloud-genai-learning --limit=50
```

## Learned

Docker build
- Builds an image from the application and Dockerfile.
- Code changes on the laptop do not change a previously built image.
- The Day-11 summary identifies the new local image as employee-api:v2.

Docker tag
Docker tag gives an image another reference/name. A registry-qualified image name also identifies the registry/repository destination
that can be used by a later docker push. docker tag itself does not upload the image.

```powershell
docker tag employee-api:v2 europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api/employee-api:v2
```
employee-api:v2 - Source (from docker)
europe-west2-docker.pkg.dev - Registry host
cloud-genai-learning - Project
employee-api - Repository
employee-api : v2 - employee-api - Image, v2 - Tag

```powershell
docker tag creates another reference to the same image. How we name that reference matters, because a registry-qualified reference
```
contains the destination information that docker push will later use.

- Adds another reference/name pointing to the same image; it does not copy it.
- A full registry name also supplies the destination for a later push.
- Tagging does not upload the image and does not deploy the app.
- A separate tag step is unnecessary if build already used the full name.
- A tag is a label. A digest identifies the exact image content.

Docker push and Artifact Registry
- Push uploads the named image to the registry.
- Artifact Registry stores images so Cloud Run can use them.
- Established repository: employee-api, Docker format, europe-west2.
- Registry repository path:
europe-west2-docker.pkg.dev/cloud-genai-learning/employee-api
- Repository name and image name are separate parts of an image reference.
- A successful push alone does not update an existing Cloud Run revision.
- The reference commands above use :v2; yesterday's recorded push used :latest.

Cloud Run service and revisions
- employee-api is the service and keeps the same public URL.
- A revision is an immutable version of the service's container/configuration.
- Deploying v2 created employee-api-00002-pxz; v1 was still present.
- Revision History shows both revisions and the traffic each receives.
- The screenshot shows Updating service, Creating revision and Routing traffic
all completed for the v2 deployment.
- One chat reply says 00002-nxz. The screenshots show 00002-pxz, used here.

Traffic management
- Traffic settings decide which revision handles requests to the service URL.
- A revision can exist with 0% of service traffic.
- In this exercise, one revision received 100% at a time.
- The final screenshot labels v2 traffic as 100% (to latest).

Rollback exercise (Cloud Console actions used)

## 1. Open Cloud Run > employee-api > Revision History.
## 2. Click Manage traffic.
## 3. Choose Send all traffic to one revision.
## 4. Select employee-api-00001-w6s (v1).
## 5. Click Save.
## 6. Open the same public URL.
## 7. Verify the response is "hello Raja".

The selection screenshot is before Save. The next browser screenshot confirms
the old response after the rollback. No rebuild, push or new revision was
needed for this traffic change. The v2 revision was retained.

Restore v2 (recorded follow-up)

## 1. Go back to Manage traffic.
## 2. Choose Send all traffic to one revision.
## 3. Select employee-api-00002-pxz (v2), then Save.
## 4. Verify completed traffic migration and v2 100%, v1 0%.
## 5. Open the same URL and verify:
{"message":"Employee API","version":"2.0"}

The returned chat instructs the single-revision option above. The final
screenshot shows the completed outcome with 100% (to latest) beside v2;
the exact final dialog selection is not captured.

## What rollback taught me

```text
Same service / same URL
       |
  Traffic settings
   /           \
v1              v2
00001-w6s       00002-pxz
```

After deployment: v1 0%,   v2 100%
During rollback:  v1 100%, v2 0% (old response verified)
Final state:      v1 0%,   v2 100%

Changing traffic selects an existing revision. It does not change its code.
Rebuilding an image, pushing an image and routing traffic are separate actions.

## Revision checklist

[ ] Explain the difference between build, tag and push.
[ ] Explain why Artifact Registry is needed.
[ ] Explain the difference between a service and a revision.
[ ] Find both revisions and their traffic percentages.
[ ] Describe how to roll back without rebuilding.
[ ] Verify the response at the same URL after each traffic change.
[ ] Recover the earlier Day-11 screenshots and exact command arguments.

## Documentation

Append this section to 01-python-fastapi/Notes.txt.
Store the workbook at learning-results/Day-11-Cloud-Run-Revision-Rollback.xlsx.
The workbook includes five original screenshots and a complete stage index
that marks missing evidence. Earlier command/screenshot coverage remains
incomplete until the original material is available.

Source conversation
New_Learning_1
chatgpt-conversation://6aa66e73-10d4-83ed-b1d2-0f0f2ca78540

Day 11 outcome: rollback to v1 and restoration to v2 verified in the original
screenshots. No cloud resources were changed while preparing these files.
