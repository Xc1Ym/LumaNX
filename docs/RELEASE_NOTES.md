# LumaNX 0.4.6

## Changes

- **Game package preparation.** Fixed an extraction error that stopped preparation of imported NSP, XCI, NSZ and XCZ packages in v0.4.5. [#56](https://github.com/Xc1Ym/LumaNX/pull/56)
- **Task results.** The launcher reads the remaining worker output before finalizing a task, so a worker that exits immediately can still deliver its result. [#58](https://github.com/Xc1Ym/LumaNX/pull/58)
- **Shader extraction.** The launcher validates captured NRO files and makes them available to shader extraction for games that need them to read resource archives. [#53](https://github.com/Xc1Ym/LumaNX/pull/53)
- **Bundled nxnative update.** The engine advances from `73150dd` to `80f2749`. Prepare games again after updating to refresh their runtime and shader artifacts. [Compare upstream commits](https://github.com/seedds/nxnative/compare/73150dd93e3d3c8039a83c8ad83f5ceca2db0f05...80f27491457d507be5bbe5a1be8da3a9fb2ddd19)

## Installation and validation

Download **LumaNX-0.4.6-arm64.dmg** and verify the SHA-256 shown on the GitHub release. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Packages use **ad-hoc signing** and are distributed without notarization. Game preparation requires full Xcode with Metal. IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG and source audits, and runtime relocation before publishing the DMG. Full-game and iOS-device compatibility still need real-world testing. NUP and directory imports use registered game profiles. The package includes the launcher and dependencies under their respective licenses and excludes games, keys, firmware and player data.

---

## 中文说明

- **游戏包准备。** 修复 v0.4.5 中 NSP、XCI、NSZ 和 XCZ 导入后在解包阶段失败的问题。[#56](https://github.com/Xc1Ym/LumaNX/pull/56)
- **任务结果。** 启动器在判定任务状态前读完工作进程的输出，避免进程退出过快时丢失最终结果。[#58](https://github.com/Xc1Ym/LumaNX/pull/58)
- **着色器提取。** 校验捕获的 NRO 文件，并在着色器提取时提供给需要用它读取资源归档的游戏。[#53](https://github.com/Xc1Ym/LumaNX/pull/53)
- **更新内置 nxnative。** 引擎从 `73150dd` 更新至 `80f2749`。升级后请重新准备游戏，以更新运行时和着色器产物。[查看上游提交对比](https://github.com/seedds/nxnative/compare/73150dd93e3d3c8039a83c8ad83f5ceca2db0f05...80f27491457d507be5bbe5a1be8da3a9fb2ddd19)

下载 **LumaNX-0.4.6-arm64.dmg**，按 GitHub Release 页面给出的 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上。安装包采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python 和 Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG 和源码审计及搬移校验。完整游戏流程与 iOS 真机仍待验收。NUP 与目录导入使用已登记的游戏配置。安装包包含启动器及其依赖，保留各自许可，不附带游戏、密钥、固件或玩家数据。
