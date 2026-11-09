# LumaNX 0.4.1

## Changes

- **Engine snapshot sync.** The bundled nxnative snapshot moves from upstream [2eb71820aece65dbc30dd17df5483a20483eac0d](https://github.com/seedds/nxnative/commit/2eb71820aece65dbc30dd17df5483a20483eac0d) to [b2d46b86d03f4b03afe11ea61c67cdf00d7a5345](https://github.com/seedds/nxnative/commit/b2d46b86d03f4b03afe11ea61c67cdf00d7a5345), keeping the local gamepad and SDK compatibility patches. The translator binaries are rebuilt with it (a new shader-chain stamp), and Mac / iOS games rebuild their shader libraries on first launch after the update.
- **Three more registered games.** ŌKAMI HD, Sonic Superstars and Minecraft Dungeons II join the registered profiles, and several existing profiles gain refreshed shader tables.
- **Damaged game files stop the build early.** Files whose bytes do not start as their names promise — a `.zs` texture that is not a zstd stream, as found in a damaged Ocarina of Time copy that pegged the CPU in the background loader — now stop packing with a clear list instead of producing a broken install; `--allow-damaged` packs them as they are. The check is cached beside the image, so an unchanged game is not read again.
- **Shader-library images.** Shader libraries are now stored as single images (`b-<chain>.img`) instead of folder trees, shrinking game caches and speeding up incremental runs; bug reports and regression tooling read both layouts.
- **Progress and reporting.** Shader-build progress is reported from the build tool itself (per-stage counts instead of file watching), and audio, video-codec, display-history and probe fixes land with the snapshot alongside a broadened engine test suite.
- **Daily-sync robustness.** The native input harness now stubs the controller applet's HID service call, so the daily engine sync's link check stays green without touching production engine code.

## Installation and validation

Download **LumaNX-0.4.1-arm64.dmg** and verify the SHA-256 below. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real gameplay sessions and iOS devices remain pending acceptance. NUP and directory imports rely on the registered game profiles and do not generate temporary ones. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **引擎快照同步。** 内置 nxnative 从上游 [2eb71820aece65dbc30dd17df5483a20483eac0d](https://github.com/seedds/nxnative/commit/2eb71820aece65dbc30dd17df5483a20483eac0d) 同步至 [b2d46b86d03f4b03afe11ea61c67cdf00d7a5345](https://github.com/seedds/nxnative/commit/b2d46b86d03f4b03afe11ea61c67cdf00d7a5345)，保留本地手柄与 SDK 兼容补丁。翻译器二进制随之重建（新的着色器链印记），更新后 Mac / iOS 游戏首次启动会重建着色器库。
- **再登记三款游戏。** ŌKAMI HD（大神 HD）、Sonic Superstars（索尼克 超级群星）与 Minecraft Dungeons II（我的世界 地下城 2）加入已登记配置，多款既有配置的着色器表同步刷新。
- **损坏游戏文件提前拦截。** 文件字节与其扩展名承诺不符——例如不是 zstd 流的 `.zs` 贴图（一份损坏的《塞尔达传说 时之笛》正因此导致后台加载器 CPU 占用异常）——现在会在打包时以清晰清单中止，而不再产出坏安装包；`--allow-damaged` 可按原样打包。检查结果缓存于镜像旁，未变更的游戏不会重复读取。
- **着色器库镜像化。** 着色器库改为单一镜像文件（`b-<chain>.img`）而非目录树，游戏缓存更小、增量运行更快；问题报告与回归工具同时兼容两种布局。
- **进度与修复。** 着色器构建进度改由构建工具自身上报（按阶段计数，替代文件监视）；快照同时带来音频、视频解码、显示历史与探针修复，并扩充引擎测试覆盖。
- **每日同步更稳。** 原生输入测试为控制器弹窗的 HID 服务调用补充测试桩，每日引擎同步的链接检查保持通过，生产引擎代码零改动。

下载 **LumaNX-0.4.1-arm64.dmg**，按下方 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：完整游戏流程与 iOS 设备仍待验收；NUP 与目录导入仅使用已登记配置，不自动生成临时配置。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
