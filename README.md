# TrafficFlow — simple traffic presentation dashboard

Upload a video. Analysis starts automatically using your trained model.

The dashboard shows:
- Estimated unique vehicles counted throughout the video.
- Number of vehicle categories captured.
- Counts for two-wheelers, auto-rickshaws, cars, and buses/trucks.
- Low, moderate, or high estimated traffic load.
- Suggested green-light duration in seconds.
- Detection boxes and a downloadable CSV report.

## Open it

Double-click **Start-TrafficFlow.command** and open **http://127.0.0.1:8765/**. Leave the launcher running. There is no key entry or lane-drawing step. The model defaults to `~/Downloads/best (1).pt` and a deployment copy is included at `backend/models/best.pt`. Keep this repository private.

On another computer, use Python 3.12:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
MODEL_PATH="/path/to/best.pt" .venv/bin/python backend/app.py
```

## Presentation flow

1. Open the dashboard and wait for “Your model is ready.”
2. Click **Upload traffic video** and choose an H.264 MP4 or another browser-supported video.
3. Watch the results update automatically. Pause/resume if needed.
4. When finished, read the totals and download the report.

The original video is uploaded to the analysis server and stored temporarily during analysis (on this computer when running locally, or on Render when hosted). Every decoded frame is processed in order, with no pre-inference browser resizing or JPEG compression. The temporary file is removed when analysis completes or a new video replaces it. Uploading another video resets the results. Slower hardware may take longer than the video duration. Maximum upload size is 100 MB. Abandoned sessions are cleaned up after 5 minutes of inactivity, checked every 30 seconds.

## Meaning of the estimates

Counts use the Ultralytics default tracker IDs (TrackTrack in version 8.4.175). Each ID is counted once and assigned the first observed vehicle class, so category totals add up to the overall count. Tracker ID switches can overcount. This model counts auto-rickshaws separately and groups buses and trucks together. Non-road-vehicle categories are excluded from counts, density and green-time estimates.

Traffic density is a visible-vehicle load estimate, averaged over the most recent 10 seconds of video: zero = no traffic; up to 5 vehicles = low; over 5 to 15 = moderate; over 15 = high. This is not physical density or road occupancy. The first 10 seconds use the available frames.

Suggested green time is `ceil(3 × average visible vehicles)`, bounded to 10–60 seconds, or zero when no vehicles are present in the rolling window. It is a demonstration heuristic, not a validated signal plan. It does not measure waiting times, stopped queues, pedestrians, competing approaches, or clearance intervals. No real signal is controlled.

At completion, vehicle totals cover the whole video; density and green time describe the final 10 seconds. Expand **How these estimates work** on the dashboard for this explanation.

## Local service

The server defaults to loopback locally; the Docker image binds to `0.0.0.0:$PORT`. Opening the local dashboard establishes an HttpOnly, SameSite session cookie automatically. External browser origins are rejected unless configured in `ITMS_ORIGINS`. One video is analyzed at a time. Visitors receive separate signed cookies; another visitor receives a busy response instead of replacing an active analysis. Only load your own trusted model checkpoints.

The Docker image serves both the dashboard and Python/PyTorch API. A public deployment is pending GitHub connection and hosting-cost approval; no online deployment has been verified.

## Checks

`node tests/insights.test.cjs` verifies the density and timing calculations. Integration testing used the actual best.pt file and a short sample clip.

## Kaggle-matched pipeline

Ultralytics is pinned to 8.4.175, matching the notebook. The service calls `model.track(source=video_path, conf=0.30, iou=0.45, stream=True, vid_stride=1, imgsz=640)` with the package default tracker (TrackTrack in this version). Unlike the notebook, display frames are streamed to the dashboard rather than saving an annotated video (`save=False`). JPEG is used only for displaying frames after detection. Inference runs on CPU on this Mac, rather than CUDA GPU 0 on Kaggle; runtime and small numerical differences can remain. Exact model weights and source footage must match to compare results.

## Render deployment

Planned service: `trafficflow-itms`, Docker runtime, Singapore region, private GitHub repository, My Workspace. Use a single instance and a single Python process; session state is held in memory. Proposed compute: 1 CPU / 2 GB RAM ($25/month compute, plus any applicable usage charges), subject to owner approval. No database or persistent disk required.

The Dockerfile includes the selected `best (1).pt` weights under `backend/models/best.pt`, outside the public static directory. Render supplies `PORT` and `RENDER_EXTERNAL_URL`; the latter enables HTTPS-only cookies and the public same-origin checks. Health endpoint: `/healthz`. Do not publish the model or source repository publicly. The image uses CPU-only PyTorch and Ultralytics 8.4.175. Processing speed depends on the server and source resolution.

The Docker daemon was unavailable locally, so container build and remote validation remain to be completed on Render. Local HTTPS TestClient checks passed with the actual model and 30-frame clip: cookie authentication, cross-origin rejection, visitor isolation, busy responses, frame completion, temporary-file cleanup, invalid-upload recovery, and denial of model download. Run `python tests/test_hosting.py /path/to/30-frame-test.mp4` in an environment with httpx installed to repeat.
