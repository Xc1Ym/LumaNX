<p align="center">
  <img src="Assets/LumaNX.png" width="112" alt="璃游图标">
</p>
<h1 align="center">璃游 · LumaNX</h1>
<p align="center">在 Mac 上，图形化构建与打包 Switch 游戏。</p>
<p align="center"><a href="README.md">English</a> · <strong>简体中文</strong></p>
<p align="center">
  <a href="https://github.com/Xc1Ym/LumaNX/releases/latest">下载 DMG</a> ·
  <a href="docs/使用说明.md">使用指南</a> ·
  <a href="docs/开发说明.md">源码构建</a> ·
  <a href="https://github.com/Xc1Ym/LumaNX/issues">反馈问题</a>
</p>

璃游 LumaNX 是面向 Apple Silicon Mac 的 **[nxnative](https://github.com/seedds/nxnative) 第三方图形界面**。导入游戏文件，准备 Mac 运行版本，从游戏库启动，或导出未签名的 iPhone / iPad IPA。nxnative 提供原生执行与 Metal 图形能力，璃游用 SwiftUI 将这些操作集中到一个工作空间。

**现已支持内置 nxnative 快照中已适配的 Switch 2 游戏，通过免密钥的 NUP 或已解包目录导入并在 Mac 上运行。** 游戏及版本兼容范围以引擎配置为准，准备流程按阶段增量更新。

<img src="docs/screenshots/library-zh.jpg" width="1000" alt="璃游 0.2.19 浅色外观游戏库">

## 从游戏文件到运行版本

| 工作空间 | 可以做什么 |
| --- | --- |
| **游戏库** | 添加 NSP/XCI/NSZ/XCZ 或扫描文件夹，管理本体、更新与 DLC；压缩文件先解压再导入。 |
| **游戏准备** | 准备代码、着色器与运行文件，校验和复用缓存；查看阶段进度、实际计数与参考估时，取消或重试任务。 |
| **Mac 与移动设备** | 在 Mac 上启动已准备的游戏，或在详情中生成未签名的 iPhone / iPad IPA。 |
| **文件转换** | 使用内置转换工具转换 NSP/XCI、压缩或解压 NSZ/XCZ、合并文件。 |
| **存档恢复** | 备份并校验存档、从备份恢复；切换已准备的运行版本前自动备份存档。 |
| **偏好设置** | 选择中英文、浅色或深色外观、游戏语言，并使用引擎支持的输入配置。 |

Switch Pro、Xbox、PlayStation 手柄通过 Apple GameController 框架接入。原生按键策略将 Switch A / Xbox A / PlayStation 叉键映射为游戏 A。更新引擎后，重新准备已有游戏即可应用运行时变更。

当前版本：**0.4.2** · [发行说明](docs/RELEASE_NOTES.md)

## 开始使用

**需要 Apple Silicon Mac 与 macOS 26 或更新版本。** 准备游戏还需完整 Xcode 及 Metal 组件。安装包内置 nxnative、元数据读取器、着色器翻译器与运行依赖。

1. 从 [Releases](https://github.com/Xc1Ym/LumaNX/releases/latest) 下载 ARM64 DMG，核对发布说明中的 SHA-256，将 **LumaNX.app** 拖入“应用程序”。当前安装包采用 ad-hoc 签名，尚未公证。
2. 打开璃游，按首次设置向导检查环境，并**准备引擎工具**。
3. 选择游戏库，添加有权使用的游戏本体、更新与 DLC。游戏包需要自己的 `prod.keys`；NUP 与 Switch 2 已解包目录无需密钥，可在向导中跳过密钥步骤。
4. 准备完成后点击**启动游戏**；移动设备请选择游戏详情中的**生成 IPA…**。

IPA 导出还需 Xcode 的 **iOS 平台**与 **XcodeGen**（`brew install xcodegen`）。导出后使用自己的安装工具签名，再安装到设备。

兼容性随游戏、版本和引擎而变化。准备成功不代表完整可玩，iOS 真机兼容性尚未验收。升级或试验性运行前，请备份存档。

### Switch 2 已解包游戏（Mac，实验性）

点击“添加游戏”，选择 `.nup` 文件（也可扫描含 NUP 的文件夹），或选择含有 `base/exefs` 与 `base/romfs` 的根目录。璃游校验程序标识和模块构建 ID，将目录复制到游戏库，再使用内置 nxnative 准备并启动游戏，无需 `prod.keys`。仅接受 nxnative 已适配的游戏及其指定版本；当前上游有《咚奇刚 蕉力全开》（`040074A01BF12000`，更新 `458752`）的 Mac 开场区域测试记录，不代表所有 Switch 2 游戏或完整流程可玩。

```text
DonkeyKongBananza/
  base/exefs/                       main、main.npdm、sdk、rtld 等
  base/romfs/
  updates/458752/exefs/              可选更新，目录名为十进制版本号
  updates/458752/romfs/              合并更新后的完整资源，不是增量补丁
  dlc/040074a01bf13001/0/romfs/       可选 DLC
```

NUP 导入会校验容器与每个文件的哈希，本体、更新和 DLC 共用一份托管副本；容器带控制数据时读取游戏名称、版本与封面。资源及 DLC 直接打包为镜像。按上游规则支持空本体占位或无本体的完整更新：无本体记录时更新必须标记 `standalone_update`，并包含完整代码及资源。仍须满足配置要求的版本，不会伪造 v0。NUP 与目录导入均要求已登记的游戏配置，不自动生成临时配置。

更新不会与本体目录再次叠加；游戏配置要求的版本缺失或构建 ID 不符时会阻止准备。同一游戏的 NUP、游戏包与已解包目录不能混用。目录导入复用游戏库的缓存、存档和运行版本回滚；目前仅开放 Mac 运行，禁用 IPA 导出。LumaNX 的自动化验证使用合成文件，真实游戏仍需实测。上游的[目录格式](https://github.com/seedds/nxnative#switch-2-games)和[游戏测试记录](https://github.com/seedds/nxnative/blob/main/dm/games/040074A01BF12000/README.md)可供对照。

## 界面预览

截图拍摄于 **2026-10-30**，取自 **0.2.19 界面预览构建**，使用浅色外观与独立空白数据目录，不含游戏、密钥或玩家数据。首次设置展示了此预览构建中组件尚待修复的状态。

<details>
<summary>首次设置与偏好设置</summary>

<img src="docs/screenshots/setup-zh.jpg" width="1000" alt="璃游首次设置向导">
<img src="docs/screenshots/settings-zh.jpg" width="1000" alt="璃游偏好设置">

</details>

## 文档

| 指南 | 内容 |
| --- | --- |
| [使用说明](docs/使用说明.md) | 首次设置、IPA 导出、手柄、语言与数据管理 |
| [环境要求与修复](docs/环境要求.md) | 依赖安装与工具链排错 |
| [开发说明](docs/开发说明.md) | 测试、本地 App / DMG 构建与 CI |
| [更新说明](docs/RELEASE_NOTES.md) | 中英文版本变更 |
| [架构说明](docs/架构说明.md) · [引擎接口](docs/引擎修改.md) · [验收记录](docs/验收记录.md) | 实现细节与已记录的验证范围 |

报错时，打开任务日志或复制脱敏错误摘要。[提交 Issue](https://github.com/Xc1Ym/LumaNX/issues) 请附应用、芯片、macOS、Xcode 版本及复现步骤。分享前检查诊断内容，排除游戏、密钥、固件、存档与私人缓存。

## 引擎同步与版本发布

nxnative **每天同步一次上游**，通过 CI 验证后才更新到 `main`；如果上游变更未通过验证，则保留上一个已验证快照。

**没有常规功能更新时，璃游每周发布一次版本**，汇总这段时间的 nxnative 更新；功能更新按其发布安排进行。每日同步引擎与每周发布 DMG 是两个独立步骤，已安装的应用使用其构建时内置的引擎。

如果希望在下次发版前使用最新已成功同步的 nxnative，请按下面的步骤拉取当前 `main` 自行编译。使用新版引擎后，重新准备游戏以更新对应运行版本。

## 从源码正确编译

需要 **Apple Silicon Mac 与 macOS 26 或更新版本**，并在原生 `arm64` 终端中操作（用 `uname -m` 确认）。先安装 [Homebrew](https://brew.sh/) 和 **[.NET 10 SDK（macOS Arm64）](https://dotnet.microsoft.com/en-us/download/dotnet/10.0)**；打开完整 Xcode，自行接受许可并完成首次组件安装。Xcode 不在默认位置时，修改下面的 `DEVELOPER_DIR`。

1. 获取最新已验证源码并准备工具链。`dotnet --list-sdks` 必须列出 `10.0.x` SDK，Metal 命令必须输出 Apple Metal 编译器版本。

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

2. 在仓库根目录执行启动器检查。

   ```bash
   actionlint .github/workflows/*.yml
   work/python-venv/bin/python -B -m unittest discover -s tests -v
   swift test --disable-sandbox --cache-path "$PWD/work/spm-cache" -c release
   ```

3. 按以下顺序构建。脚本依次收集固定版本的转换依赖、便携运行环境，编译元数据读取器，再编译并签名应用、生成 DMG。依赖收集和首次构建读取器时需要联网。

   ```bash
   swift scripts/make_icons.swift
   work/python-venv/bin/python -B scripts/bundle_converter.py
   work/python-venv/bin/python -B scripts/bundle_runtime.py
   work/python-venv/bin/python -B scripts/bundle_engine.py
   work/python-venv/bin/python -B scripts/package.py
   work/python-venv/bin/python -B scripts/source_archive.py
   work/python-venv/bin/python -B scripts/verify_release.py
   ```

产物为 `release/LumaNX.app`、`release/LumaNX-<version>-arm64.dmg`、源码 ZIP 和 `release/SHA256SUMS`，其中 `<version>` 取自 `product.json`。最后一条命令校验签名、DMG、源码内容、校验和及运行库搬移。再次构建前，请退出此输出目录中仍在运行的应用；打包采用 ad-hoc 签名，无需 Apple Developer 签名账号。

以后更新时，在此 `main` 工作副本中执行 `git pull --ff-only`，再重复检查和构建步骤。内置引擎提交记录在 `Engine/nxnative/manifest.json`。原生引擎及 iOS 检查命令见 [CI 工作流](.github/workflows/ci.yml)和[开发说明](docs/开发说明.md)，其中 Metal/iOS 样例检查还需安装 Xcode 的 iOS 平台。编译启动器及其发行包不需要游戏或密钥。

璃游原名 **LumaDock**。原有图标、应用标识、游戏库与设置继续兼容已有安装。

## 致谢与许可

感谢 **[nxnative](https://github.com/seedds/nxnative)** 提供执行与图形能力，感谢 **[MacNativeGames](https://github.com/ly05010419/MacNativeGames)** 与 **[d2r-mobile](https://github.com/jhaizhou-ops/d2r-mobile)** 的上游贡献。文件转换参考 **[SAK-Mac](https://github.com/ggaoph-lab/SAK-Mac)**。这些组件及 Ryujinx / Spv.Generator、LibHac、SPIRV-Cross、CPython、.NET 等依赖的许可见[第三方声明](docs/第三方许可.md)。

启动器代码与原创图标采用 **[MIT License](LICENSE)**，第三方组件保留各自许可。项目不附带游戏、更新、DLC、固件、密钥、游戏封面或玩家缓存。请仅使用有权使用的内容。Nintendo 及游戏商标归相应权利人所有；璃游与 Nintendo 或游戏发行商没有隶属或认可关系。
