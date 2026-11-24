# FPS overlay and quantitative performance sessions

The existing Mac engine already supports Apple's Metal performance HUD (`DM_METAL_HUD`), per-frame timing (`DM_NVN_TSV`, with `DM_NVN_TSV_CALLS=0` to avoid call-count instrumentation), and long-frame diagnostics. LumaNX exposes the existing controls; no game/shader rebuild is needed.

## Controls

Under **Manage game → Performance diagnostics (all games)**:

- **Performance HUD** shows the engine's existing Apple overlay: FPS, frame/GPU timing and memory. It applies on the next game launch.
- **Record performance session** captures engine timings for that launch. Recording and the HUD are independent, opt-in global launcher preferences.
- **Run label** distinguishes runs, e.g. “Local compressed — route A” or “Local uncompressed — route A”. Labels do not change storage settings.
- **Timing panel…** opens a floating, mouse-operated panel that cannot become key/main or activate the launcher. Select Gameplay, Loading or Transition, then use Start/Stop. Mark hitch adds a subjective event timestamp alongside the measured data. The panel keeps its state when closed/reopened during the same launch.
- **Performance reports…** opens the game's reports folder.

Finish by quitting the game normally. Cancellation also attempts to finalize a partial capture. Reports are stored separately under `library/benchmarks/<game ID>/<UTC timestamp>-<ID>/`, so source/build-cache cleanup does not remove them. A forced process kill can leave raw data without a finalized report; markers reject stale worker identities.

Each session has `report.html` for reading, `summary.json` for comparisons, `frames.csv` for plotting, raw `engine-timing.tsv`, `markers.jsonl`, a session-only copy of the engine log, and metadata identifying the launcher/engine/game version, compression state, asset path, OS and hardware. Reports stay local; there is no upload or telemetry service. They can contain local paths in metadata/logs; review them before sharing.

## What the numbers mean

Displayed frame timing uses the engine's actual on-screen presentation intervals. CPU present-call timing is kept separate and is only a clearly labeled fallback when display timings are unavailable. Reports include mean interval/FPS derived from it, p50/p95/p99/max frame times, intervals above 33.33/50/100/250 ms, discarded presentations, and GPU timing. GPU/present rows arrive eight frames late; analysis reassembles them with a bounded buffer.

Percentile frame times are not the same as an average-of-the-slowest-1%-frames FPS statistic. Absolute threshold counts are not a universal diagnosis: 30 fps normally means about 33.33 ms, and a menu/loading screen can have low motion or maintain high FPS while the player waits.

Loading and transition durations are **manual stopwatch measurements**, not automatic recognition of a game's loading screens. They include reaction time. Marker timestamps use the system monotonic clock; aligning them with engine frame timestamps uses process launch as an approximate origin. The first recorded presentation is not proof the title screen/world is ready. Recognized pipeline-prewarm durations are recorded separately from the engine log.

## Repeatable comparison

1. Keep the engine/game build, save location, route, display, resolution, frame cap and HUD/recording settings fixed.
2. Label the condition. Warm up once, then record the same 2–5 minute gameplay route at least three times per condition, alternating the order where practical.
3. Mark the same loading/transition boundaries. Use Gameplay sections for gameplay frame-time comparisons; overall statistics also include startup, menus and loads.
4. Keep the game visible and focused. Do not include focus loss, covered/minimized windows, unrelated heavy work or shader/pipeline first-run work as storage-only effects.
5. Compare median loading/transition durations, p95/p99 frame times, long-interval counts and discarded presentations. Keep raw CSVs for investigating outliers.

Caches are deliberately left intact. Restarting a game does not establish a cold filesystem cache. Do not delete shader/build caches just to simulate cold asset reads. HUD and recording have some overhead, so comparisons need identical instrumentation.

Current capture is most complete for the NVN backend. Other backends can use the Metal HUD but may not produce this NVN timing stream; reports show unavailable data rather than invent FPS. Recording generates disk data (potentially hundreds of MB per hour); leave it off for ordinary play and remove old reports through Finder when no longer needed.

NAS gameplay support is a separate change. These tools establish the local baseline now and can measure NAS conditions once that storage path is implemented. Filesystem tracing already exists in nxnative (`DM_FSLOG`) but is not enabled by this lightweight recording mode; it records accesses, not complete per-read latency or decompression attribution. Deeper attribution can use Instruments or future reader-specific counters.
