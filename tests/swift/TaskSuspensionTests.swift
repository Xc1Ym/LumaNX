import XCTest
import Darwin
@testable import LumaNX

final class TaskSuspensionTests: XCTestCase {
    func testPauseFreezesWorkerAndChildThenResumes() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try FileManager.default.createDirectory(at:root,withIntermediateDirectories:true)
        defer {try? FileManager.default.removeItem(at:root)}
        let output=root.appendingPathComponent("ticks")
        let child=root.appendingPathComponent("child")
        let process=Process()
        process.executableURL=URL(fileURLWithPath:"/bin/sh")
        process.arguments=["-c","/bin/sh -c 'while :; do echo tick >> \"$1\"; sleep 0.05; done' fixture \"$1\" & echo $! > \"$2\"; wait", "fixture",output.path,child.path]
        try process.run()
        let suspension=TaskSuspension()
        defer {
            suspension.resume()
            if let text=try? String(contentsOf:child,encoding:.utf8),let pid=Int32(text.trimmingCharacters(in:.whitespacesAndNewlines)) {kill(pid,SIGTERM)}
            if process.isRunning {process.terminate()}
        }
        let deadline=Date().addingTimeInterval(5)
        while !FileManager.default.fileExists(atPath:output.path),Date()<deadline {Thread.sleep(forTimeInterval:0.02)}
        XCTAssertTrue(FileManager.default.fileExists(atPath:output.path))
        try suspension.pause(process.processIdentifier)
        XCTAssertGreaterThanOrEqual(suspension.stopped.count,2)
        Thread.sleep(forTimeInterval:0.1)
        let paused=try Data(contentsOf:output)
        Thread.sleep(forTimeInterval:0.25)
        XCTAssertEqual(try Data(contentsOf:output),paused,"The child must stop writing too")
        suspension.resume()
        XCTAssertTrue(suspension.stopped.isEmpty)
        Thread.sleep(forTimeInterval:0.25)
        XCTAssertGreaterThan(try Data(contentsOf:output).count,paused.count)
    }
    func testDescendantSelectionExcludesUnrelatedProcesses() {
        let entries=[TaskSuspension.Entry(pid:10,parent:1,started:"a"),.init(pid:20,parent:10,started:"b"),.init(pid:30,parent:20,started:"c"),.init(pid:40,parent:1,started:"d")]
        XCTAssertEqual(TaskSuspension.descendants(of:10,in:entries).map(\.pid),[20,30])
    }
}

@MainActor final class TaskPauseStoreTests: XCTestCase {
    func testHeartbeatDoesNotPretendCountersAdvanced() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {try? FileManager.default.removeItem(at:root)}
        let store=Store(privateRoot:root,resources:root)
        var task=TaskRecord(id:"activity",operation:"build",state:"running")
        task.done=5;task.total=100;task.lastProgressAt=123
        store.tasks=[task]
        store.event(["schema":1,"taskId":task.id,"type":"heartbeat","outputAt":456],visible:true)
        XCTAssertNotNil(store.tasks[0].lastHeartbeat)
        XCTAssertEqual(store.tasks[0].lastProgressAt,123)
        XCTAssertEqual(store.tasks[0].lastOutputAt,456)
        store.event(["schema":1,"taskId":task.id,"type":"progress","done":5,"total":100],visible:true)
        XCTAssertEqual(store.tasks[0].lastProgressAt,123)
        store.event(["schema":1,"taskId":task.id,"type":"progress","done":6,"total":100],visible:true)
        XCTAssertGreaterThan(store.tasks[0].lastProgressAt ?? 0,123)
    }
    func testCancelAndQuitReleasePausedWorkers() async throws {
        for quit in [false,true] {
            let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            defer {try? FileManager.default.removeItem(at:root)}
            let worker=root.appendingPathComponent("Worker")
            let bin=root.appendingPathComponent("Runtime/python/bin")
            try FileManager.default.createDirectory(at:worker,withIntermediateDirectories:true)
            try FileManager.default.createDirectory(at:bin,withIntermediateDirectories:true)
            try FileManager.default.createSymbolicLink(atPath:bin.appendingPathComponent("python3").path,withDestinationPath:"/usr/bin/python3")
            let source=URL(fileURLWithPath:#filePath).deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent().appendingPathComponent("Worker/task_pause_guardian.py")
            try FileManager.default.copyItem(at:source,to:worker.appendingPathComponent("task_pause_guardian.py"))
            let store=Store(privateRoot:root,resources:root)
            let process=Process();process.executableURL=URL(fileURLWithPath:"/bin/sleep");process.arguments=["30"]
            try process.run()
            defer {if process.isRunning {kill(process.processIdentifier,SIGKILL)}}
            let task=TaskRecord(id:"fixture",operation:"build",state:"running")
            store.tasks=[task];store.processes[task.id]=process
            store.togglePause(task)
            XCTAssertEqual(store.tasks.first?.state,"paused")
            XCTAssertNotNil(store.suspensions[task.id])
            if quit {store.terminate()} else {store.cancel(store.tasks[0])}
            let deadline=Date().addingTimeInterval(5)
            while process.isRunning,Date()<deadline {try await Task.sleep(nanoseconds:20_000_000)}
            XCTAssertFalse(process.isRunning)
            XCTAssertTrue(store.suspensions.isEmpty)
        }
    }
    func testPausedTaskRemainsActiveAndDoesNotLoseStateToBufferedHeartbeat() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        defer {try? FileManager.default.removeItem(at:root)}
        let store=Store(privateRoot:root,resources:root)
        let task=TaskRecord(id:"pause-fixture",operation:"build",state:"paused")
        XCTAssertTrue(task.active)
        store.tasks=[task]
        store.suspensions[task.id]=TaskSuspension()
        store.event(["schema":1,"taskId":task.id,"type":"heartbeat","state":"running"],visible:true)
        XCTAssertEqual(store.tasks.first?.state,"paused")
        store.event(["schema":1,"taskId":task.id,"type":"result","state":"completed"],visible:true)
        XCTAssertEqual(store.tasks.first?.state,"completed")
    }
}
