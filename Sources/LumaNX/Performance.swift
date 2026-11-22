import Foundation
import AppKit
import SwiftUI

struct BenchmarkPhase:Decodable {
    var active:Bool
    var label:String?
    var startMonotonic:Double?
}
/// Mouse controls must not steal the game's key-window status (which pauses it).
final class BenchmarkPanel:NSPanel {
    override var canBecomeKey:Bool {false}
    override var canBecomeMain:Bool {false}
}
@MainActor extension Store {
    func performanceSession(_ game:Game)->URL? {
        let root=URL(fileURLWithPath:preferences.library)
        guard let data=try? Data(contentsOf:root.appendingPathComponent(".benchmark-\(game.id).json")),
              let value=try? JSONSerialization.jsonObject(with:data) as? [String:Any],let id=value["id"] as? String,
              id.range(of:#"^\d{8}T\d{6}Z-[0-9a-f]{8}$"#,options:.regularExpression) != nil else {return nil}
        return root.appendingPathComponent("benchmarks/\(game.id)/\(id)")
    }
    func performancePhase(_ game:Game)->BenchmarkPhase? {
        guard let path=performanceSession(game),let data=try? Data(contentsOf:path.appendingPathComponent("phase.json")) else {return nil}
        return try? JSONDecoder().decode(BenchmarkPhase.self,from:data)
    }
    func markPerformance(_ game:Game,action:String,label:String) {
        worker("benchmarkMarker",extra:["gameId":game.id,"markerAction":action,"markerLabel":label,"markerMonotonic":Double(DispatchTime.now().uptimeNanoseconds)/1e9],visible:false)
    }
    func openPerformanceReports(_ game:Game) {
        let url=URL(fileURLWithPath:preferences.library).appendingPathComponent("benchmarks/\(game.id)")
        do {try FileManager.default.createDirectory(at:url,withIntermediateDirectories:true);NSWorkspace.shared.open(url)}
        catch {self.error=error.localizedDescription}
    }
    func showPerformancePanel(_ game:Game) {
        if let panel=performancePanels[game.id] {panel.orderFrontRegardless();return}
        let panel=BenchmarkPanel(contentRect:NSRect(x:0,y:0,width:330,height:245),styleMask:[.titled,.closable,.utilityWindow,.nonactivatingPanel],backing:.buffered,defer:false)
        panel.title=L("性能计时")+" · "+game.name
        panel.isFloatingPanel=true;panel.level = .floating;panel.hidesOnDeactivate=false
        panel.becomesKeyOnlyIfNeeded=true;panel.isReleasedWhenClosed=false
        panel.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary]
        panel.contentView=NSHostingView(rootView:PerformanceTimingView(game:game).environmentObject(self))
        performancePanels[game.id]=panel;panel.center();panel.orderFrontRegardless()
    }
}
struct PerformanceTimingView:View {
    @EnvironmentObject var store:Store
    let game:Game
    @State private var label="Gameplay"
    var body:some View {
        TimelineView(.periodic(from:.now,by:0.25)) {_ in
            let phase=store.performancePhase(game)
            let active=phase?.active==true
            let hasSession=store.performanceSession(game) != nil
            VStack(alignment:.leading,spacing:12) {
                Text(L("手动计时标记")).font(.headline)
                Picker(L("测试阶段"),selection:$label) {
                    Text(L("游戏过程")).tag("Gameplay")
                    Text(L("加载")).tag("Loading")
                    Text(L("场景切换")).tag("Transition")
                }.disabled(active)
                if active,let started=phase?.startMonotonic {
                    Text(String(format:"%.1f s",max(0,Double(DispatchTime.now().uptimeNanoseconds)/1e9-started))).font(.title.monospacedDigit())
                } else {Text(L(hasSession ? "可以开始阶段计时" : "请先启用性能记录并启动游戏")).font(.caption)}
                HStack {
                    Button(L("开始")){store.markPerformance(game,action:"start",label:label)}.disabled(!hasSession || active)
                    Button(L("停止")){store.markPerformance(game,action:"end",label:label)}.disabled(!hasSession || !active)
                    Button(L("标记卡顿")){store.markPerformance(game,action:"hitch",label:label)}.disabled(!hasSession)
                }
                Text(L("手动测量包含反应时间。点击此面板不会激活启动器。"))
                    .font(.caption).foregroundStyle(.secondary)
            }.padding(16).frame(width:330)
        }
    }
}
