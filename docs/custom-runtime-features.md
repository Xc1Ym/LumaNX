# Task controls and compiled runtime archives

Build, export, conversion, archive and restore tasks can be paused and resumed from the task list. A paused task retains its execution slot. Cancellation resumes its process tree before normal termination; a guardian releases and cancels a paused worker if the app exits unexpectedly. Pausing is for the current app session, not a persistent checkpoint across reboot.

Task activity shows the last measured progress change separately from the last log output and worker heartbeat. Shader preparation reads the engine's progress feed, including cache checks, compilation, image packaging and finalization. Older engines retain loose-library progress counting.

## Compile and play requirements

A verified compiled game remains playable after managed source packages or build caches are removed. Source requirements are reported separately for rebuilding. New source content or an engine change can still mark a game as having an update to prepare; launching uses the last successful compiled release.

Registered games with additional DLC shader packages use the engine's shader-only derived profile callback when available, preserving the registered module fixes. A reused split checkpoint restores that profile too.

## Archive to NAS

Choose **Manage game → Archive to NAS…**, select a destination outside the local library, and confirm. The worker creates a runtime-only shader image, compresses the compiled runtime to a ZIP64 archive, then reads back and hashes every file. Only after verification and recording the archive in the local catalog does it remove that active local compiled release. Other releases, saves, input mappings and user caches remain local.

**Restore for play** verifies the catalog-pinned archive manifest and every restored file before activating the local release. The NAS copy is retained. Restore needs neither managed source packages nor a build cache and does not compile shaders. Archives are storage copies; gameplay uses the restored local runtime, not streaming from the ZIP over SMB.

Failures and cancellation before local removal leave the local runtime intact. Do not edit the archive or its sidecar manifest. A lost local catalog is not automatically reconstructed from archive folders. Keep the library catalog and saves backed up.

Runtime packaging uses nxnative's shader subset API to retain runtime metallibs/reflection/tables while excluding generated Metal source and compilation CAS databases. Actual archive size depends on the game assets' compressibility.

Validation covers synthetic round trips, corruption, cancellation, save preservation, process suspension and UI request plumbing. Full real-game NAS round-trip acceptance is separate.
