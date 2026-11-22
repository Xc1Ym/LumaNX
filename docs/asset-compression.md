# Optional compressed game assets

Under **Library → Manage game**, **Compress game assets (Zstandard)** is an opt-in setting for each game. It defaults to off and applies to future preparations. Nothing is automatically compressed when the app is updated.

For an older compiled runtime, changing the option records the preference for the next preparation. The existing runtime remains playable. Reimport source packages if they were removed, then prepare once with the updated engine to obtain the new reader.

For a runtime built with reader support, changing the option converts the current base/DLC asset images without compiling shaders. Turning it off restores ordinary uncompressed images. Folder-based assets are not yet converted into images by this operation. The operation requires temporary local space and offers pause/cancel and retry through the task list.

The worker stages a separate runtime, verifies converted bytes and runtime integrity, atomically switches the active release, and only then removes the replaced active release. Other releases, saves, input mappings and gameplay caches are kept. Failure before activation preserves the current runtime and preference. If cleanup after activation fails, the new runtime stays active and leftover release files may still occupy space.

This compresses asset data only; shaders and executables remain separate. Compression happens in independent 256 KiB Zstandard level-3 blocks. Incompressible blocks are stored raw. The native engine decompresses requested blocks into a bounded LRU cache (4 MiB per mounted image), with additional memory for index, scratch and decoder state. Block/index checksums detect corruption. A small per-image index means fully incompressible content may grow slightly.

The decoder uses the already bundled pinned Zstandard 1.5.7 library through an explicit app-owned runtime path. No Homebrew installation is required for players. The engine snapshot records the local reader patch in its inventory manifest. Existing uncompressed runtimes and images continue to work.

This feature operates on local game images. **Archive to NAS** remains a separate ZIP64 storage/restore operation; this update does not add gameplay streaming from a NAS archive. Compressed asset images can be archived/restored by the updated app. iOS export prepares its own ordinary assets and does not enable this Mac storage mode.

For Bananza's measured base and DLC images, Zstandard reduced 10.140 GB to 9.179 GB (961 MB / 9.47%). The total game size also includes runtime shaders and other files. Results vary by content. Native synthetic tests and byte comparisons do not replace real-game compatibility and frame-time testing.
