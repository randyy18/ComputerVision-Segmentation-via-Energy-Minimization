# GrabCut Interactive Web Demo

Timed bounding-box challenge powered by classical graph-cut segmentation.

## What it does

1. Upload image + ground-truth mask pairs (matched by filename stem).
2. Draw bounding boxes under a countdown — **N images = N seconds**.
3. After time runs out, the backend runs **iterative graph-cut** segmentation on every boxed image.
4. View per-image IoU / Dice scores, download masks, and climb the **session leaderboard**.

## Scoring

Leaderboard rank uses a **composite score**:

**score = mean IoU × images scored × completion bonus**

- `images scored` — how many bounding boxes you drew before time ran out
- `completion bonus` — `0.5 + 0.5 × (scored / total)` (small boost for finishing more of the set)

Example: 10 images at 80% mean IoU with all 10 boxed → score ≈ **8.0**.  
Five images at 90% IoU → score ≈ **3.38**. Doing more images can beat a slightly higher average on fewer.

## Prerequisites

- Python 3.10+
- Node.js 18+
- Dependencies from the main project (`grabcut_classical/` — PyMaxflow, OpenCV, etc.)

## Run locally

Open **two terminals** from the repo root.

### Terminal 1 — Backend (port 8000)

```bash
cd demo/backend
pip install -r requirements.txt
python run.py
```

### Terminal 2 — Frontend (port 5173)

```bash
cd demo/frontend
npm install
npm run dev
```

Open **http://localhost:5173** in your browser.

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Quick test with bundled dataset

Use images from `data/grabcut/`:

- **Images:** `data/grabcut/images/*.jpg`
- **Ground truth:** `data/grabcut/gt/*.png`

Upload both folders on the play screen. Start with 5–10 images to keep processing time short.

## Project layout

```
demo/
├── backend/          # FastAPI — segmentation + API
├── frontend/         # Vue 3 + Vite UI
├── storage/          # Runtime session uploads (gitignored)
└── README.md
```

## API overview

| Endpoint | Description |
|----------|-------------|
| `POST /api/sessions` | Upload pairs, create game session |
| `PUT /api/sessions/{id}/bboxes/{idx}` | Save bbox for image |
| `POST /api/sessions/{id}/finish` | Run batch segmentation |
| `GET /api/sessions/{id}/results` | Metrics + mask URLs |
| `GET /api/leaderboard/datasets` | List all dataset tags / boards |
| `GET /api/leaderboard?dataset_id=…` | Rankings for one dataset |

Leaderboard data is **per dataset** (same image + GT files → same board). Scores are saved under `storage/leaderboards/` and survive server restarts. Upload a different set of files to start a new leaderboard.

## Windows notes

Use PowerShell or WSL. If the project path has spaces, quote it:

```powershell
cd "C:\Users\...\Z_GrabCut\demo\backend"
python run.py
```

## WSL notes

If the repo is on `/mnt/c/...`, run both servers inside WSL. Batch segmentation is headless and works without a display.
