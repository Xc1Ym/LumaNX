# LumaNX 0.2.20

## Changes

- **Updated bundled engine.** Includes nxnative `cd859c38a8f8890ddbb57a23d6f45e23ba9e6651`, with upstream extraction, RomFS and shader preparation updates since 0.2.19. Re-prepare existing games to apply engine changes.
- **Restored daily engine synchronization.** Sync patches now support upstream shared controller mappings and continue to validate unique patch anchors. The imported engine retains LumaNX's native controller button policy.
- **Updated extraction compatibility.** The worker passes the selected application ID to newer upstream extractors, retains support for older signatures, and adapts Application/Patch content selection in the bundled reader.
- **Refreshed documentation.** Bilingual READMEs include current interface previews, daily engine synchronization, weekly release cadence and the supported macOS source build sequence.

## Installation and validation

Download **LumaNX-0.2.20-arm64.dmg** and verify the SHA-256 below. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **更新内置引擎。** 包含 nxnative `cd859c38a8f8890ddbb57a23d6f45e23ba9e6651`，汇总 0.2.19 之后上游的解包、RomFS 与着色器准备更新。已有游戏需要重新准备才能应用引擎变更。
- **恢复每日引擎同步。** 同步补丁兼容上游共享手柄映射，并继续严格校验补丁锚点；导入引擎保留 LumaNX 的原生手柄按键策略。
- **适配新版解包接口。** 工作进程向新版上游解包器传入选定应用 ID，同时兼容旧签名，并适配内置读取器的 Application/Patch 内容筛选。
- **刷新使用与编译文档。** 中英文 README 包含当前界面预览、每日引擎同步、每周发布节奏，以及受支持的 macOS 源码编译顺序。

下载 **LumaNX-0.2.20-arm64.dmg**，按下方 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
