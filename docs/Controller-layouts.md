# 手柄布局 / Controller layouts

Mac 输入编辑器的“原生手柄自动识别”中，可选择已连接的 GameController 设备并切换面键布局。此项自动保存；“输入测试”即时显示游戏将收到的 A/B/X/Y。无需保存下方的键鼠配置，也无需引擎支持 `DM_INPUT_CONFIG`。游戏下次启动读取布局文件；已有旧宿主需重新准备一次，此后切换布局无需编译。iOS 仍保持默认报告字母，不自动导入 Mac 的设备设置。

| 布局 | GameController buttonA/B/X/Y → 游戏 |
| --- | --- |
| 按报告字母（默认） | A/B/X/Y |
| 按 Switch 物理位置（显式选择） | B/A/Y/X |

默认保持标准 Switch Pro、Xbox、PlayStation 的已有约定。不会根据“Pro”“Nintendo”“8BitDo”等模糊产品名称自动交换。物理位置选项针对把底部/右侧/左侧/顶部报告为 A/B/X/Y 的驱动模式；如果按键已经按印刷字母报告，应保留默认。可在输入测试页分别按四个面键，核对是否符合自己的预期。

持久化身份由准确的 `vendorName` 与 `productCategory` 组成，不使用玩家插槽或连接顺序。文件为私有数据目录中的 `controller-layouts.json`，schema 1，`layouts` 将 UTF-8 字节数前缀编码的身份映射到 `switchPosition`；没有覆盖或无法读取的配置使用默认报告字母。`DM_CONTROLLER_LAYOUTS` 由 Worker 指向这个文件，运行时每个进程读取一次。同一设备重新连接、换玩家插槽仍保持设置。不同名称或类别隔离；连接方式/设备模式若报告相同身份则共享设置。GameController 没有可靠的逐台持久 ID，所以身份完全相同的同型号设备不能单独保存。

不由 GameController 列出的原始 HID 设备沿用上游 `pad_hid` / `DM_HID_MAP` 路径，不会被此选择器列出，也不会被产品名猜测规则改动；HID usage 到按钮的对应关系仍需设备报告验证。体感、震动和自定义键鼠映射不属于这两个面键布局选项。

自动化验证使用 Apple 可写 GameController 快照和合成身份，覆盖 UTF-8 身份一致性、两种布局、组合/摇杆、多人隔离、断开清空、重连与配置重启持久化，以及未知配置回退。模拟设备不提供真实蓝牙/USB/驱动的报告证据。实体设备矩阵（NS Pro、8BitDo 等设备的蓝牙/USB及工作模式）仍待有硬件后验收，不能据此宣称实机通过。

## English

The Mac input editor lets each connected GameController identity choose **Use reported letters** (A/B/X/Y → A/B/X/Y, default) or **Use Switch physical positions** (A/B/X/Y → B/A/Y/X). It saves automatically, previews immediately and applies on the next game launch, independently of `DM_INPUT_CONFIG`. Prepare older runtimes once to install the new host. iOS retains the default and does not import the Mac settings.

No product-name heuristic changes standard Nintendo, Xbox or PlayStation behavior. Exact reported vendor name and category form a length-prefixed UTF-8 key in the private `controller-layouts.json` schema 1 file; player slots and connection order are excluded. Reconnection preserves settings. Different reported identities remain isolated. Identical devices, or modes reporting the same identity, share a setting because GameController has no reliable persistent per-unit identifier. Missing, invalid or unknown settings fall back to reported letters.

Raw HID devices outside GameController retain upstream `pad_hid` / `DM_HID_MAP` behavior and are outside this picker. Automated tests exercise writable Apple snapshots, persistence, reconnects, multiplayer isolation and fallback behavior. They do not establish physical Bluetooth/USB button reports, motion or haptics. The real-device matrix remains pending until hardware is available.
