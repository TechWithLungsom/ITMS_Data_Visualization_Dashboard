# Verification — simplified presentation version

- Loaded the supplied YOLOv8s model with four labels: two_wheeler, autorickshaw, car, bus_truck.
- Local dashboard connects automatically with an HttpOnly SameSite cookie; no access-key entry required.
- Browser upload automatically started and completed inference on a 3-second sample clip.
- Confirmed total count, cumulative counts by type, categories captured, rolling visible-load density estimate, and green-time suggestion.
- Repeated frames retained one unique track, and category totals matched the overall count. This verifies integration, not model accuracy on traffic footage.
- Unauthenticated API calls and disallowed browser origins were rejected.
- Density tests cover threshold boundaries, no traffic, green-time minimum/maximum, smoothing and the rolling-window cutoff.
- Browser showed no JavaScript errors.
- Local delivery only; online publication has not been verified.

Run `node tests/insights.test.cjs` for the calculation checks.

## Model switch — 12 October 2026

Default model changed to `~/Desktop/best.pt` (the file directly on Desktop, not Desktop/Model/best.pt). A direct model test on 11 October loaded it and produced inference results. Restarting on 12 October was blocked by macOS Desktop access even after file permission was granted in Codex; the updated service is not running yet. Its labels remain two_wheeler, autorickshaw, car, bus_truck.

## Latest model selection

Switched to `~/Downloads/best (1).pt`. Direct model loading and prediction succeeded. The local service was restarted with this model.

## Current model: yolov8n.pt

Switched to `~/Downloads/yolov8n.pt` and restarted the local service. Health endpoint confirms the model. Road-vehicle classes are bicycle, car, motorcycle, bus and truck. Verified person-class requests are rejected; a test image containing a bus and people produced only the bus detection (0.882 confidence). Repeated-frame unique count stayed at one, and category totals matched the overall count. No auto-rickshaw category is available in this model.

## Latest selection restored

Restored `~/Downloads/best (1).pt`. The running service confirms the selected model and its four vehicle categories; an inference smoke check passed.

## Kaggle pipeline matching

User confirmed Kaggle uses Ultralytics 8.4.175, matching the installed version. Replaced browser sampling/JPEG input with original-video upload and native sequential tracking. Settings match the supplied code: confidence 0.30, IoU 0.45, default tracker (TrackTrack). All frames processed (vid_stride=1), image size 640. Device remains CPU rather than Kaggle CUDA; save=False streams results instead of writing annotated video.

Compared all 30 frames of a local test clip against direct `YOLO(...).track(source=..., conf=0.30, iou=0.45)` under the same installed version and CPU. Detection classes, confidence values and normalized bounding boxes matched. Count totals, session replacement, invalid uploads, and invalid session IDs were verified. This is pipeline equivalence testing on one clip, not validation of accuracy on the user's traffic footage or a GPU comparison.

Browser verification: original-video upload completed all 30 frames, displayed the server-decoded frames and overlays, and produced no JavaScript errors. Unconfirmed tracks are now displayed as a dash rather than implying that no vehicles were detected; vehicle-type counts include categories actually detected.

## Stale-tab repair

Old /api/start and /api/infer calls reproduced HTTP 405 while the new video endpoints worked. Versioned dashboard asset URLs, disabled browser caching, and added explicit stale-tab responses. Restarted the service and verified video upload followed by all 30 frames of the test clip.


## Public hosting preparation — 2026-10-12
- Added Docker package with private model copy, Render port binding, and health endpoint.
- Actual-model TestClient test passed across 30 frames with separate HTTPS visitor cookies and cross-session denial. Busy uploads no longer replace another visitor's video.
- Verified completion and idle file cleanup, invalid uploads, and model path returning 404. Density calculation tests passed.
- Container build not run: local Docker daemon unavailable. Public deployment pending GitHub connection and paid compute approval.
