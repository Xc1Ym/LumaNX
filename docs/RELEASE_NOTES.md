# LumaNX 0.4.5

## Changes

- **Bundled nxnative update.** The engine advances from `9b03dee` to `73150dd`, including wired support for Xbox One controllers handled by the engine's macOS USB driver. Prepare games again after updating to refresh their runtime and shader artifacts. [Compare upstream commits](https://github.com/seedds/nxnative/compare/9b03dee5d617138c6b98890abf8f1d68c0785511...73150dd93e3d3c8039a83c8ad83f5ceca2db0f05).
- **Shader preparation and export.** LumaNX validates shader libraries stored in packed images during game preparation and iOS export. The bundled translator is checked against nxnative's current source fingerprint, which includes the Ryujinx sources.

## Installation and validation

Download **LumaNX-0.4.5-arm64.dmg** and verify the SHA-256 shown on the GitHub release. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real gameplay sessions and iOS devices remain pending acceptance. NUP and directory imports rely on the registered game profiles and do not generate temporary ones. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **更新内置 nxnative。** 引擎从 `9b03dee` 更新至 `73150dd`，Mac 端引擎新增部分 Xbox One 手柄的 USB 直连支持。升级后请重新准备游戏，以更新运行时和着色器产物。[查看上游提交对比](https://github.com/seedds/nxnative/compare/9b03dee5d617138c6b98890abf8f1d68c0785511...73150dd93e3d3c8039a83c8ad83f5ceca2db0f05)
- **着色器准备与导出。** 游戏准备与 iOS 导出现在可校验镜像格式的着色器库。内置翻译器按 nxnative 当前的源码指纹校验，覆盖编译所用的 Ryujinx 源文件。

下载 **LumaNX-0.4.5-arm64.dmg**，按 GitHub Release 页面给出的 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：完整游戏流程与 iOS 设备仍待验收；NUP 与目录导入仅使用已登记配置，不自动生成临时配置。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
