import Foundation
import AppKit

@MainActor extension Store {
    func archiveGame(_ game:Game) {
        guard !executionBusy,queue.isEmpty,game.ready==true else {return}
        let panel=NSOpenPanel()
        panel.title=L("选择 NAS 归档文件夹")
        panel.prompt=L("选择")
        panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.canCreateDirectories=true
        if let root=preferences.archiveRoot {panel.directoryURL=URL(fileURLWithPath:root)}
        guard panel.runModal() == .OK,let url=panel.url else {return}
        let alert=NSAlert();alert.messageText=L("归档已编译游戏？")
        alert.informativeText=L("将复制并校验已编译游戏，然后移除本地运行文件以释放空间。存档和本地游戏缓存保留。恢复时不需要重新编译。")+"\n\n"+url.path
        alert.addButton(withTitle:L("归档到 NAS"));alert.addButton(withTitle:L("取消"))
        guard alert.runModal() == .alertFirstButtonReturn else {return}
        preferences.archiveRoot=url.path;savePreferences()
        runtimeTransfer("archiveGame",game:game,extra:["archiveRoot":url.path])
    }
    func restoreGame(_ game:Game) {
        guard game.archived==true else {return}
        runtimeTransfer("restoreGame",game:game)
    }
    func runtimeTransfer(_ operation:String,game:Game,extra:[String:Any]=[:]) {
        guard !executionBusy,queue.isEmpty,["archiveGame","restoreGame"].contains(operation) else {return}
        let libraryId=preferences.libraryId
        var request=extra;request["gameId"]=game.id
        selection="tasks"
        let id=worker(operation,extra:request) { _ in
            guard self.preferences.libraryId==libraryId else {return}
            self.notice=operation=="archiveGame" ? "游戏已归档到 NAS；存档保留在本地。" : "游戏已恢复到本地，无需重新编译；NAS 副本保留。"
            self.refresh()
        }
        executionTask=id
        if let root=request["archiveRoot"] as? String,let index=tasks.firstIndex(where:{$0.id==id}) {tasks[index].archiveRoot=root}
    }
}
