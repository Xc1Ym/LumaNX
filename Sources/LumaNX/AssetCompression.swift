import Foundation
import AppKit

@MainActor extension Store {
    func confirmAssetCompression(_ game:Game,enabled:Bool) {
        guard !executionBusy,queue.isEmpty else {return}
        let alert=NSAlert()
        alert.messageText=L(enabled ? "使用压缩游戏资源？" : "使用未压缩游戏资源？")
        alert.informativeText=L(game.assetCompressionCapable==true ? "切换前会校验替换版本，随后移除之前的活动版本以释放空间。其他运行版本和存档保留。需要临时可用空间。此选择也适用于以后的准备。" : "此选择适用于下次准备。当前已编译游戏仍可运行。如有需要，请重新导入源文件并再次准备，以启用新的资源读取器。")
        alert.addButton(withTitle:L(enabled ? "使用压缩" : "保持未压缩"));alert.addButton(withTitle:L("取消"))
        guard alert.runModal() == .alertFirstButtonReturn else {return}
        setAssetCompression(game,enabled:enabled)
    }
    func setAssetCompression(_ game:Game,enabled:Bool) {
        guard !executionBusy,queue.isEmpty else {return}
        let libraryId=preferences.libraryId;selection="tasks"
        executionTask=worker(enabled ? "compressAssets" : "uncompressAssets",extra:["gameId":game.id]) {result in
            guard self.preferences.libraryId==libraryId else {return}
            self.notice=result["requiresPreparation"] as? Bool==true ? "已为下次准备选择压缩。当前游戏文件已保留。" : "资源存储偏好已更新。"
            self.refresh()
        }
    }
}
