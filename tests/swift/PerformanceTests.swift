import XCTest
import AppKit
@testable import LumaNX

@MainActor final class PerformanceTests:XCTestCase {
    func testLegacyPreferencesKeepDiagnosticsOptIn() throws {
        let data=Data(#"{"library":"","libraryId":"","developerDir":"/Applications/Xcode.app/Contents/Developer","onboardingComplete":true}"#.utf8)
        let prefs=try JSONDecoder().decode(Preferences.self,from:data)
        XCTAssertNil(prefs.performanceHUD);XCTAssertNil(prefs.recordPerformance)
    }
    func testTimingPanelCannotStealGameFocus() {
        let panel=BenchmarkPanel(contentRect:NSRect(x:0,y:0,width:330,height:245),styleMask:[.titled,.closable,.nonactivatingPanel],backing:.buffered,defer:true)
        XCTAssertFalse(panel.canBecomeKey);XCTAssertFalse(panel.canBecomeMain)
        XCTAssertTrue(panel.styleMask.contains(.nonactivatingPanel))
        panel.close()
    }
    func testLaunchPassesRecordingFlagsAndTimingPanelReadsBackendState() async throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {try? FileManager.default.removeItem(at:root)}
        let resources=root.appendingPathComponent("resources"),worker=resources.appendingPathComponent("Worker"),bin=resources.appendingPathComponent("Runtime/python/bin")
        try FileManager.default.createDirectory(at:worker,withIntermediateDirectories:true)
        try FileManager.default.createDirectory(at:bin,withIntermediateDirectories:true)
        try FileManager.default.createSymbolicLink(atPath:bin.appendingPathComponent("python3").path,withDestinationPath:"/usr/bin/python3")
        try #"""
import json,pathlib,sys
r=json.loads(pathlib.Path(sys.argv[2]).read_text());root=pathlib.Path(r['resources']).parent
with (root/'requests.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
result={'games':[],'jobs':[],'profiles':[],'keys':{'ready':False}} if r['operation']=='catalog' else {}
print(json.dumps(dict(schema=1,taskId=r['taskId'],type='result',state='completed',result=result)),flush=True)
"""#.write(to:worker.appendingPathComponent("main.py"),atomically:true,encoding:.utf8)
        let store=Store(privateRoot:root.appendingPathComponent("private"),resources:resources)
        defer {store.terminate()}
        var deadline=Date().addingTimeInterval(4)
        while !store.processes.isEmpty,Date()<deadline {try await Task.sleep(nanoseconds:20_000_000)}
        store.preferences.library=root.appendingPathComponent("library").path;store.preferences.libraryId="fixture"
        store.environmentReportComplete=true;store.checks=[ToolCheck(name:"Launch",ok:true,message:"",requiredFor:["launch"])]
        store.preferences.performanceHUD=true;store.preferences.recordPerformance=true
        let game=Game(id:"040074A01BF12000",name:"Fixture",display:"1",packages:[],hidden:false,ready:true)
        store.launch(game)
        deadline=Date().addingTimeInterval(4)
        while !store.processes.isEmpty,Date()<deadline {try await Task.sleep(nanoseconds:20_000_000)}
        let rows=try String(contentsOf:root.appendingPathComponent("requests.jsonl"),encoding:.utf8).split(separator:"\n").map {try JSONSerialization.jsonObject(with:Data($0.utf8)) as! [String:Any]}
        let launch=try XCTUnwrap(rows.first{$0["operation"] as? String=="launch"})
        XCTAssertEqual(launch["performanceHUD"] as? Bool,true);XCTAssertEqual(launch["recordPerformance"] as? Bool,true)
        let library=URL(fileURLWithPath:store.preferences.library),id="20261122T123456Z-1234abcd"
        let session=library.appendingPathComponent("benchmarks/\(game.id)/\(id)")
        try FileManager.default.createDirectory(at:session,withIntermediateDirectories:true)
        try Data(#"{"id":"20261122T123456Z-1234abcd"}"#.utf8).write(to:library.appendingPathComponent(".benchmark-\(game.id).json"))
        try Data(#"{"active":true,"label":"Gameplay","startMonotonic":1234.5}"#.utf8).write(to:session.appendingPathComponent("phase.json"))
        XCTAssertEqual(store.performancePhase(game)?.label,"Gameplay")
        XCTAssertEqual(store.performancePhase(game)?.startMonotonic,1234.5)
        try Data(#"{"id":"../../outside"}"#.utf8).write(to:library.appendingPathComponent(".benchmark-\(game.id).json"))
        XCTAssertNil(store.performanceSession(game))
    }
}
