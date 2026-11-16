# LumaNX 0.4.3

## Changes

- **Current nxnative snapshot.** The bundled engine moves from upstream [38521863e191431f61f6a465eb1aed66078975c0](https://github.com/seedds/nxnative/commit/38521863e191431f61f6a465eb1aed66078975c0) to [33c734f61963c6af738e1b79d99fab0930ea3bf3](https://github.com/seedds/nxnative/commit/33c734f61963c6af738e1b79d99fab0930ea3bf3). It carries a broad set of upstream rendering, shader translation, sparse-texture, filesystem, save, audio/video, controller, packaging and game-profile updates. Prepare games again after updating so their runtime, shaders and pipeline archives match the new snapshot.
- **MetalFX and graphics updates.** Upstream adds reactive-mask input for MetalFX, wider input-size handling, scaler ordering fixes, pipeline-archive reliability improvements and further texture/view/residency corrections. LumaNX's synchronization layer now compile-guards the new SDK 27 reactive-mask properties while retaining the SDK 26 fallback.
- **Controllers, packing and profiles.** The snapshot adds original Joy-Con motion input on Mac, expands Switch 2 controller handling, reads additional Switch 2 and game shader-library formats, and introduces or refreshes multiple registered profiles. The LumaNX native harness now supplies the matching Joy-Con motion sinks so these interfaces remain link-tested.
- **Synchronization compatibility.** The daily import accepts nxnative's dynamic save-sync device check and both old and new metadata-extraction signatures. A verified candidate at this exact revision passed the complete Apple Silicon test, build, signing, DMG and relocation pipeline before it was committed.

## Installation and validation

Download **LumaNX-0.4.3-arm64.dmg** and verify the SHA-256 shown on the GitHub release. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real gameplay sessions and iOS devices remain pending acceptance. NUP and directory imports rely on the registered game profiles and do not generate temporary ones. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **当前 nxnative 快照。** 内置引擎从上游 [38521863e191431f61f6a465eb1aed66078975c0](https://github.com/seedds/nxnative/commit/38521863e191431f61f6a465eb1aed66078975c0) 更新至 [33c734f61963c6af738e1b79d99fab0930ea3bf3](https://github.com/seedds/nxnative/commit/33c734f61963c6af738e1b79d99fab0930ea3bf3)，带入大量上游渲染、着色器翻译、稀疏纹理、文件系统、存档、音视频、手柄、打包及游戏配置更新。升级后应重新准备游戏，使运行时、着色器和流水线归档与新快照一致。
- **MetalFX 与图形更新。** 上游新增 MetalFX 反应遮罩输入、更宽的输入尺寸范围、缩放器排序修复、流水线归档可靠性改进，以及更多纹理/视图/驻留修复。LumaNX 同步层现会对 SDK 27 新增的反应遮罩属性做编译期保护，同时保留 SDK 26 回退路径。
- **手柄、打包与配置。** 快照新增 Mac 上初代 Joy-Con 体感输入，扩展 Switch 2 手柄处理，读取更多 Switch 2 及游戏着色器库格式，并新增或刷新多个已登记配置。LumaNX 原生测试桩已补齐相应 Joy-Con 体感接口，持续执行链接验证。
- **同步兼容性。** 每日导入现可识别 nxnative 的动态存档同步设备检查，并同时适配新旧元数据提取签名。精确对应该上游提交的候选产物已在提交前通过完整 Apple Silicon 测试、构建、签名、DMG 与搬移校验。

下载 **LumaNX-0.4.3-arm64.dmg**，按 GitHub Release 页面给出的 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：完整游戏流程与 iOS 设备仍待验收；NUP 与目录导入仅使用已登记配置，不自动生成临时配置。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
