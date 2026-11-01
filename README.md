<p align="center">
  <img src="Assets/LumaNX.png" width="112" alt="LumaNX icon">
</p>
<h1 align="center">LumaNX · 璃游</h1>
<p align="center">A native Mac workspace for building and packaging Switch games.</p>
<p align="center"><strong>English</strong> · <a href="README.zh-CN.md">简体中文</a></p>
<p align="center">
  <a href="https://github.com/Xc1Ym/LumaNX/releases/latest">Download DMG</a> ·
  <a href="docs/Getting-started.md">User guide</a> ·
  <a href="docs/Development.md">Build from source</a> ·
  <a href="https://github.com/Xc1Ym/LumaNX/issues">Report an issue</a>
</p>

LumaNX is a third-party graphical frontend for **[nxnative](https://github.com/seedds/nxnative)** on Apple Silicon Macs. Import your game files, prepare a Mac runtime, launch from your library, or export an unsigned IPA for iPhone and iPad. nxnative provides native execution and Metal graphics; LumaNX brings the workflow into a SwiftUI interface.

<img src="docs/screenshots/library-en.jpg" width="1000" alt="LumaNX 0.2.19 game library in light appearance">

## From files to a ready library

| Workspace | What you can do |
| --- | --- |
| **Game library** | Add NSP/XCI/NSZ/XCZ files or scan folders; manage base games, updates and DLC. Compressed files are decompressed before import. |
| **Game preparation** | Prepare code, shaders and runtime files with validated caches. Follow stage progress, counters and reference time estimates; cancel or retry tasks. |
| **Mac and mobile** | Launch prepared games on Mac, or generate an unsigned iPhone / iPad IPA from game details. |
| **File conversion** | Convert NSP/XCI, compress or decompress NSZ/XCZ, and merge packages using bundled conversion tools. |
| **Save recovery** | Back up and verify saves, restore a backup, or switch prepared runtime versions with an automatic save backup. |
| **Preferences** | Choose English or Simplified Chinese, light or dark appearance, and game language. Configure input where supported by the engine. |

Switch Pro, Xbox and PlayStation controllers connect through Apple's GameController framework. The native button policy maps Switch A / Xbox A / PlayStation cross to game A. Re-prepare existing games after an engine update to apply runtime changes.

## Get started

**You need an Apple Silicon Mac running macOS 26 or later.** Game preparation requires full Xcode and its Metal components. The packaged app includes nxnative, the metadata reader, shader translator and runtime dependencies.

1. Download the ARM64 DMG from [Releases](https://github.com/Xc1Ym/LumaNX/releases/latest), check its SHA-256 against the release notes, and drag **LumaNX.app** into Applications. Packages currently use ad-hoc signing and are not notarized.
2. Open LumaNX. Use the setup assistant to check your environment and **prepare engine tools**.
3. Choose a game library and import your own `prod.keys`. Add game files, updates and DLC that you are authorized to use.
4. Prepare a game, then choose **Launch game**. For mobile, choose **Generate IPA…** in game details.

IPA export also needs Xcode's **iOS platform** and **XcodeGen** (`brew install xcodegen`). Sign the exported IPA with your installation tool before installing it.

Compatibility varies by game, version and engine. Preparation success does not establish full gameplay compatibility; iOS device compatibility has not been validated. Back up saves before upgrading or experimenting.

## Interface

Captured on **2026-10-30** from a **0.2.19 UI preview build**, in light appearance with an isolated, empty data directory. No games, keys or player data are shown. The setup assistant illustrates components needing attention in this preview.

<details>
<summary>Setup assistant and preferences</summary>

<img src="docs/screenshots/setup-en.jpg" width="1000" alt="LumaNX setup assistant">
<img src="docs/screenshots/settings-en.jpg" width="1000" alt="LumaNX preferences">

</details>

## Documentation

| Guide | Contents |
| --- | --- |
| [Getting started](docs/Getting-started.md) | Setup, IPA export, controllers, language and data management |
| [Environment and repair](docs/Environment.md) | Dependencies and toolchain troubleshooting |
| [Development](docs/Development.md) | Tests, local App / DMG builds and CI |
| [Release notes](docs/RELEASE_NOTES.md) | Changes in English and Chinese |
| [Architecture](docs/架构说明.md) · [Engine interface](docs/引擎修改.md) · [Validation record](docs/验收记录.md) | Implementation and recorded validation scope (Chinese) |

For a failure, open the task log or copy its redacted error summary. Include the app, chip, macOS and Xcode versions, plus reproduction steps, in your [issue](https://github.com/Xc1Ym/LumaNX/issues). Review diagnostics before sharing and exclude games, keys, firmware, saves and private caches.

## Engine updates and releases

nxnative is synchronized from upstream **once a day**, with updates committed to `main` only after CI passes. If an upstream change fails validation, the previous verified snapshot is retained.

**When there are no regular feature updates, LumaNX releases once a week** to include the accumulated nxnative updates. Feature updates follow their own release schedule. Daily engine synchronization and the weekly DMG release are separate: an installed app uses the engine bundled with that build.

To use the latest successfully synchronized nxnative before the next release, build from the current `main` branch using the steps below. Re-prepare games to apply the new engine to their runtimes.

## Build from source

Use an **Apple Silicon Mac running macOS 26 or later**, with a native `arm64` terminal (`uname -m`). Install [Homebrew](https://brew.sh/) and the **[.NET 10 SDK for macOS Arm64](https://dotnet.microsoft.com/en-us/download/dotnet/10.0)**. Open the full Xcode app once, accept its license and finish initial component installation. Adjust `DEVELOPER_DIR` below if Xcode is installed elsewhere.

1. Get the latest verified sources and prepare the toolchain. `dotnet --list-sdks` must show a `10.0.x` SDK, and the Metal command must report an Apple Metal compiler version.

   ```bash
   git clone --branch main https://github.com/Xc1Ym/LumaNX.git
   cd LumaNX
   export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
   xcodebuild -version
   xcodebuild -downloadComponent MetalToolchain
   xcrun --sdk macosx metal --version
   dotnet --list-sdks

   brew install python@3.14 spirv-cross zstd xcodegen actionlint
   mkdir -p work
   "$(brew --prefix python@3.14)/bin/python3.14" -m venv work/python-venv
   work/python-venv/bin/python -m pip install -r requirements-runtime.txt -r requirements-build.txt
   ```

2. Run the launcher checks from the repository root.

   ```bash
   actionlint .github/workflows/*.yml
   work/python-venv/bin/python -B -m unittest discover -s tests -v
   swift test --disable-sandbox --cache-path "$PWD/work/spm-cache" -c release
   ```

3. Build in this order. The scripts download pinned conversion dependencies, collect the portable runtime, compile the metadata reader, then build and sign the app and create the DMG. Internet access is required during dependency collection and the first reader build.

   ```bash
   swift scripts/make_icons.swift
   work/python-venv/bin/python -B scripts/bundle_converter.py
   work/python-venv/bin/python -B scripts/bundle_runtime.py
   work/python-venv/bin/python -B scripts/bundle_engine.py
   work/python-venv/bin/python -B scripts/package.py
   work/python-venv/bin/python -B scripts/source_archive.py
   work/python-venv/bin/python -B scripts/verify_release.py
   ```

The outputs are `release/LumaNX.app`, `release/LumaNX-<version>-arm64.dmg`, the source ZIP and `release/SHA256SUMS`; `<version>` comes from `product.json`. The last command verifies signatures, the DMG, source contents, checksums and runtime relocation. Close any running copy built into this output directory before rebuilding. Packaging uses ad-hoc signing and needs no Apple Developer signing account.

For a later update, run `git pull --ff-only` in this `main` checkout and repeat the checks and build steps. The bundled engine revision is recorded in `Engine/nxnative/manifest.json`. For native-engine and iOS checks, see the [CI workflow](.github/workflows/ci.yml) and [development guide](docs/Development.md); the Metal/iOS fixture check also requires Xcode's iOS platform. Building the launcher and its distribution does not require games or keys.

LumaNX was previously called **LumaDock**. The original icon, application identifier, library and settings remain compatible with existing installations.

## Credits and license

Thanks to **[nxnative](https://github.com/seedds/nxnative)** for execution and graphics, and to **[MacNativeGames](https://github.com/ly05010419/MacNativeGames)** and **[d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)** for upstream contributions. Conversion tools adapt **[SAK-Mac](https://github.com/ggaoph-lab/SAK-Mac)**. See [third-party notices](docs/Third-party-licenses.md) for these components and dependencies including Ryujinx / Spv.Generator, LibHac, SPIRV-Cross, CPython and .NET.

Launcher code and original artwork use the **[MIT License](LICENSE)**. Third-party components retain their own licenses. Games, updates, DLC, firmware, keys, game artwork and player caches are not included. Use only content you are authorized to use. Nintendo and game trademarks belong to their owners; LumaNX is not affiliated with or endorsed by Nintendo or game publishers.
