# LumaNX 0.4.0

## Changes

- **Import Switch 2 NUP packages.** Switch 2 `.nup` containers are now imported without keys and prepared like directory sources, using the registered nxnative game profiles and versions. The base, update and DLC payloads inside the container are read and verified against a single managed copy; full standalone updates and empty-base placeholders per the upstream layout are supported, and the name, version and cover from the control data are shown. NUP sources cannot be mixed with other sources, and Switch 2 games keep IPA export disabled.
- **One-pass copy with safer catalogue updates.** The original file is copied and hashed in a single pass, then every payload — including versions and DLC not selected to run — is verified from the staged copy. A failed or cancelled save restores the existing cover and catalogue, and temporary files never outlive the attempt. Update records must identify the same application family, control data is size-bounded before parsing, and covers are accepted only with JPEG/PNG magic and sane sizes; invalid optional metadata falls back to the registered profile defaults.
- **Resource images and DLC shaders.** Shader processing, Mac installation and launch now cover `RomFS.img` and DLC images, and IPA packaging works for regular packages. Incremental preparation records the resource-image and DLC-shader dependencies, keeps cancellation state, and preserves the last good run version on failure.
- **Engine sync and pinned ZBIC.** The bundled nxnative snapshot is synced to upstream [2eb71820aece65dbc30dd17df5483a20483eac0d](https://github.com/seedds/nxnative/commit/2eb71820aece65dbc30dd17df5483a20483eac0d) while keeping the local gamepad and SDK compatibility patches. The bundled `zbic==1.0.1.post1` runs a decode check on every build, and the runtime package retains the original sources, fixed hash and license.
- **Updated documentation.** Bilingual import hints, usage and engine-modification docs, acceptance records, and broader release checks that NUP player files never enter distributed archives.

## Installation and validation

Download **LumaNX-0.4.0-arm64.dmg** and verify the SHA-256 below. Quit the app and active tasks before replacing the application. The application identifier and existing libraries, saves and settings are retained.

Requires Apple Silicon and macOS 26+. Uses **ad-hoc signing and is not notarized**. Game preparation requires full Xcode with Metal; IPA export also requires the iOS platform and XcodeGen.

The release workflow runs Python and Swift regression tests, native controller and engine checks, Metal diagnostics, unsigned synthetic iOS packaging, portable runtime bundling, app signing, DMG/source audits and runtime relocation before publishing the DMG. These checks do not establish full-game or iOS-device compatibility: real gameplay sessions and iOS devices remain pending acceptance. NUP and directory imports rely on the registered game profiles and do not generate temporary ones. No games, keys, firmware or player data are included; bundled dependencies retain their licenses.

---

## 中文说明

- **支持导入 Switch 2 NUP 封包。** `.nup` 文件现在可免密钥导入，按已登记的 nxnative 游戏配置与版本像目录来源一样准备。容器内的本体、更新与 DLC 读取校验后共用一份托管副本；支持上游规定的完整独立更新与空本体占位，并读取控制数据中的名称、版本与封面。NUP 不能与其他来源混用，Switch 2 继续禁用 IPA 导出。
- **单遍复制，目录更新更安全。** 原文件单遍复制并计算哈希，再从暂存副本校验每个 payload（含未选用的版本与 DLC）。保存失败或取消时恢复已有封面与目录，临时文件不遗留。更新记录必须属于同一应用家族，控制数据先限长再解析，封面只接受 JPEG/PNG 魔数与合理大小；无效可选元数据回退到登记配置默认值。
- **资源镜像与 DLC 着色器。** `RomFS.img` 与 DLC 镜像接入着色器处理、Mac 安装与启动，普通游戏包支持 IPA 打包。增量准备记录资源镜像与 DLC 着色器依赖，保留取消状态，失败时保留最近一次成功运行版本。
- **引擎同步与固定 ZBIC。** 内置 nxnative 同步至上游 [2eb71820aece65dbc30dd17df5483a20483eac0d](https://github.com/seedds/nxnative/commit/2eb71820aece65dbc30dd17df5483a20483eac0d)，保留本地手柄与 SDK 兼容补丁；内置 `zbic==1.0.1.post1` 每次构建执行解码检查，运行包保留原版源码、固定哈希与许可证。
- **更新文档。** 中英文导入提示、使用与引擎修改文档、验收记录，并扩展发行包对 NUP 玩家文件的排除检查。

下载 **LumaNX-0.4.0-arm64.dmg**，按下方 SHA-256 校验，退出应用及任务后替换应用。应用标识、现有游戏库、存档与设置保持兼容。

要求 Apple Silicon、macOS 26 及以上；采用临时签名，尚未公证。准备游戏需完整 Xcode 与 Metal，导出 IPA 另需 iOS 平台与 XcodeGen。

标签流水线在发布前完成 Python/Swift 回归、原生手柄与引擎检查、Metal 诊断、合成未签名 iOS 包、运行库封装、应用签名、DMG/源码审计及搬移校验。这些检查不代表完整游戏或 iOS 真机验收：完整游戏流程与 iOS 设备仍待验收；NUP 与目录导入仅使用已登记配置，不自动生成临时配置。不附带游戏、密钥、固件或玩家数据，内置依赖保留各自许可。
