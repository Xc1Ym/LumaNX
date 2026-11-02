# LumaNX 0.3.0

## Changes

- **Import Switch 2 unpacked directories.** Folders containing `base/exefs` and `base/romfs` — along with chosen update and DLC directories — are added without keys; scanning a parent folder finds nested games too. The worker validates the NPDM program ID, NSO build IDs, paths and content before copying into the library, then follows the usual Mac preparation, launch, cleanup and rollback flow. Directory sources are Mac-only in this release.
- **Incremental preparation.** Unpacking, DLC, version configuration, rewrite, capture/decode, shaders and the host build each record their own input dependencies. Engine updates no longer discard the whole build cache: a controller-header change refreshes only the host stage, unchanged stages reuse the verified run version and IPA, and a new IPA export destination is validated and copied from the existing package. Existing caches continue when the engine snapshot and dependency sources verify; corrupt, failed or cancelled preparations never overwrite the last good run version or saves.
- **Corrected Switch Pro controller buttons.** The runtime and input-test page now follow the printed labels Apple's GameController reports, removing the double A/B and X/Y swap on Nintendo Switch Pro Controllers. Recognition for pads exposed as generic HID devices is planned next.
- **Refreshed documentation.** Bilingual usage and development docs, a new incremental-build guide and updated engine-modification notes.

## Installation and validation

Download **LumaNX-0.3.0-arm64.dmg** and verify the SHA-256 below. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real Switch Pro hardware, complete gameplay sessions and iOS devices remain pending acceptance, and the bundled engine does not implement `DM_INPUT_CONFIG` yet, so custom mappings are saved but not applied by the engine. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **支持导入 Switch 2 已解包目录。** 含 `base/exefs` 与 `base/romfs` 的目录，以及选定的更新与 DLC 目录，可在无密钥情况下加入游戏库；扫描父目录也能找到嵌套的游戏目录。工作进程校验 NPDM 程序 ID、NSO 构建 ID、路径与内容后复制入库，沿用常规的 Mac 准备、启动、清理与回滚流程。本版本目录来源仅限 Mac。
- **增量准备。** 解包、DLC、版本配置、重写、采集/解码、着色器与宿主各阶段记录独立输入依赖：引擎更新不再整包重建缓存，仅改手柄头文件时只刷新宿主阶段；未变化阶段复用已验证的运行版本与 IPA，新的 IPA 导出位置只校验并复制已有包。引擎快照与依赖来源可验证时旧缓存接续使用；损坏、失败或取消的准备不会覆盖最近一次成功的运行版本与存档。
- **修正 Switch Pro 手柄按键。** 运行时与输入测试页统一按 Apple GameController 报告的印刷标签处理，消除任天堂 Switch Pro 手柄 A/B、X/Y 的重复交换；以通用 HID 暴露的手柄识别将在后续版本跟进。
- **刷新文档。** 中英文使用与开发文档、新增增量构建指南及引擎修改说明。

下载 **LumaNX-0.3.0-arm64.dmg**，按下方 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：真实 Switch Pro 手柄、完整游戏流程与 iOS 设备仍待验收；当前内置引擎尚未实现 `DM_INPUT_CONFIG`，自定义映射仅保存、尚未由引擎应用。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
