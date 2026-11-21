# LumaNX 0.4.4

## Changes

- **Bundled nxnative update.** The engine advances from `33c734f` to `9b03dee`. The upstream changes include graphics and pipeline-cache updates, audio and video fixes, and improvements to NUP metadata, shader extraction and registered game profiles. Prepare games again after updating to refresh their runtime and shader artifacts. [Compare upstream commits](https://github.com/seedds/nxnative/compare/33c734f61963c6af738e1b79d99fab0930ea3bf3...9b03dee5d617138c6b98890abf8f1d68c0785511).
- **Controller motion.** The upstream Mac engine adds passive Bluetooth DualShock 4 motion alongside Switch Pro Controller motion. LumaNX's native regression test uses the engine's pairing path and checks that it clears motion on focus loss and disconnect.

## Installation and validation

Download **LumaNX-0.4.4-arm64.dmg** and verify the SHA-256 shown on the GitHub release. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real gameplay sessions and iOS devices remain pending acceptance. NUP and directory imports rely on the registered game profiles and do not generate temporary ones. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **更新内置 nxnative。** 引擎从 `33c734f` 更新至 `9b03dee`。上游更新包含图形与流水线缓存改进、音视频修复，以及 NUP 元数据、着色器提取和已登记游戏配置的更新。升级后请重新准备游戏，以更新运行时和着色器产物。 [查看上游提交对比](https://github.com/seedds/nxnative/compare/33c734f61963c6af738e1b79d99fab0930ea3bf3...9b03dee5d617138c6b98890abf8f1d68c0785511)。
- **手柄体感。** Mac 端上游引擎在 Switch Pro 手柄之外新增蓝牙 DualShock 4 的被动体感读取。璃游的原生回归测试现通过引擎的实际配对路径，验证失焦和断开时是否清除体感状态。

下载 **LumaNX-0.4.4-arm64.dmg**，按 GitHub Release 页面给出的 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：完整游戏流程与 iOS 设备仍待验收；NUP 与目录导入仅使用已登记配置，不自动生成临时配置。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
