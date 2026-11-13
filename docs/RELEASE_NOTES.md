# LumaNX 0.4.2

## Changes

- **Large engine snapshot update.** The bundled nxnative snapshot moves from upstream [b2d46b86d03f4b03afe11ea61c67cdf00d7a5345](https://github.com/seedds/nxnative/commit/b2d46b86d03f4b03afe11ea61c67cdf00d7a5345) to [38521863e191431f61f6a465eb1aed66078975c0](https://github.com/seedds/nxnative/commit/38521863e191431f61f6a465eb1aed66078975c0), retaining LumaNX's controller and SDK compatibility policy. The update refreshes registered game profiles and brings upstream rendering, shader-pipeline, packing, save-sync, audio/video and runtime fixes. Games should be prepared again after updating so their runtime and shader libraries match the new snapshot.
- **Graphics and runtime improvements from upstream.** The snapshot includes task/mesh pipeline prewarming, pipeline-archive and texture-residency fixes, broader Switch 2 controller support, and multiple Ocarina of Time rendering/performance fixes. These are upstream changes carried by the bundled engine; LumaNX's release validation covers builds and fixtures, not complete gameplay sessions.
- **Switch 2 controller test coverage.** The native controller harness now covers the additional HID service calls made by the current Switch 2 controller path, keeping those symbols verified without changing production controller behavior.
- **Daily engine synchronization repaired.** LumaNX now tolerates both old and new nxnative extraction interfaces, accepts GitHub's `VirtualMac` ARM runner identity in the upstream save-sync fixture, and explicitly disables NativeAOT when rebuilding LumaNX's private metadata-reader adapter. The tested candidate can again pass the complete synchronization pipeline before being committed.

## Installation and validation

Download **LumaNX-0.4.2-arm64.dmg** and verify the SHA-256 shown on the GitHub release. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real gameplay sessions and iOS devices remain pending acceptance. NUP and directory imports rely on the registered game profiles and do not generate temporary ones. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **大幅同步引擎快照。** 内置 nxnative 从上游 [b2d46b86d03f4b03afe11ea61c67cdf00d7a5345](https://github.com/seedds/nxnative/commit/b2d46b86d03f4b03afe11ea61c67cdf00d7a5345) 更新至 [38521863e191431f61f6a465eb1aed66078975c0](https://github.com/seedds/nxnative/commit/38521863e191431f61f6a465eb1aed66078975c0)，并保留 LumaNX 的手柄与 SDK 兼容策略。本次更新刷新已登记游戏配置，并带入上游渲染、着色器流水线、打包、存档同步、音视频和运行时修复。升级后应重新准备游戏，使运行时和着色器库与新快照一致。
- **上游图形与运行时改进。** 新快照包含 task/mesh 流水线预热、流水线归档与纹理驻留修复、更完整的 Switch 2 手柄支持，以及多项《塞尔达传说 时之笛》渲染与性能修复。这些能力来自随包引擎；LumaNX 的发布验证覆盖构建与测试夹具，不等同于完整游戏流程验收。
- **Switch 2 手柄测试覆盖。** 原生手柄测试桩现已覆盖当前 Switch 2 手柄路径新增的 HID 服务调用，在不改变生产手柄行为的前提下持续验证相关符号。
- **修复每日引擎同步。** LumaNX 现可同时适配 nxnative 新旧提取接口，允许上游存档同步夹具识别 GitHub ARM runner 的 `VirtualMac` 设备名，并在重建 LumaNX 私有元数据读取适配器时显式关闭 NativeAOT。候选引擎恢复为通过完整同步流水线后才会提交。

下载 **LumaNX-0.4.2-arm64.dmg**，按 GitHub Release 页面给出的 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：完整游戏流程与 iOS 设备仍待验收；NUP 与目录导入仅使用已登记配置，不自动生成临时配置。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
