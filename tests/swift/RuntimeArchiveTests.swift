import XCTest
@testable import LumaNX

@MainActor final class RuntimeArchiveTests:XCTestCase {
    func testSourceCleanupDoesNotPreventPlayingButBlocksRebuilding() {
        let game=Game(id:"fixture",name:"Fixture",display:"v1",packages:[],hidden:false,compatibility:"verified",missing:[],ready:true,buildMissing:["Source files were removed"])
        XCTAssertEqual(game.ready,true)
        XCTAssertEqual(game.missing,[])
        XCTAssertFalse(game.buildable)
    }
    func testArchiveRestoreOperationsUseTheSerializedWorkerAndPreserveDestination() async throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {try? FileManager.default.removeItem(at:root)}
        let resources=root.appendingPathComponent("resources"),worker=resources.appendingPathComponent("Worker"),bin=resources.appendingPathComponent("Runtime/python/bin")
        try FileManager.default.createDirectory(at:worker,withIntermediateDirectories:true)
        try FileManager.default.createDirectory(at:bin,withIntermediateDirectories:true)
        try FileManager.default.createSymbolicLink(atPath:bin.appendingPathComponent("python3").path,withDestinationPath:"/usr/bin/python3")
        try #"""
import json,pathlib,sys
r=json.loads(pathlib.Path(sys.argv[2]).read_text())
root=pathlib.Path(r['resources']).parent
with (root/'requests.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
result={'games':[],'jobs':[],'profiles':[],'keys':{'ready':False}} if r['operation']=='catalog' else {}
print(json.dumps(dict(schema=1,taskId=r['taskId'],type='result',state='completed',result=result)),flush=True)
"""#.write(to:worker.appendingPathComponent("main.py"),atomically:true,encoding:.utf8)
        let store=Store(privateRoot:root.appendingPathComponent("private"),resources:resources)
        defer {store.terminate()}
        store.preferences.library=root.appendingPathComponent("local-library").path
        store.preferences.libraryId="fixture"
        let game=Game(id:"fixture",name:"Fixture",display:"v1",packages:[],hidden:false,ready:true)
        let nas=root.appendingPathComponent("nas-simulation").path
        store.runtimeTransfer("archiveGame",game:game,extra:["archiveRoot":nas])
        var deadline=Date().addingTimeInterval(6)
        while !store.processes.isEmpty,Date()<deadline {try await Task.sleep(nanoseconds:20_000_000)}
        XCTAssertTrue(store.processes.isEmpty)
        var archived=game;archived.archived=true;archived.ready=false
        store.restoreGame(archived)
        deadline=Date().addingTimeInterval(6)
        while !store.processes.isEmpty,Date()<deadline {try await Task.sleep(nanoseconds:20_000_000)}
        XCTAssertTrue(store.processes.isEmpty)
        let rows=try String(contentsOf:root.appendingPathComponent("requests.jsonl"),encoding:.utf8).split(separator:"\n").map {try JSONSerialization.jsonObject(with:Data($0.utf8)) as! [String:Any]}
        XCTAssertEqual(rows.first{$0["operation"] as? String=="archiveGame"}?["archiveRoot"] as? String,nas)
        XCTAssertTrue(rows.contains{$0["operation"] as? String=="restoreGame"})
        XCTAssertTrue(rows.filter{$0["operation"] as? String != "catalog"}.allSatisfy{$0["gameId"] as? String=="fixture"})
    }
}
