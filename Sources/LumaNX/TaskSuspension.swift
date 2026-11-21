import Foundation
import Darwin

/// Freeze parents before discovering descendants, including tools that create
/// their own process groups. Only recorded PID/start-time pairs are resumed.
final class TaskSuspension {
    struct Entry: Codable { let pid: Int32; let parent: Int32; let started: String }
    private(set) var stopped: [Entry] = []
    private var guardian: Process?
    func guardAgainstAppExit(python: URL, script: URL, root: Int32) throws {
        let process=Process()
        process.executableURL=python
        process.arguments=["-B","-I",script.path,String(getpid()),String(root),String(decoding:try JSONEncoder().encode(stopped),as:UTF8.self)]
        process.standardInput=FileHandle.nullDevice
        process.standardOutput=FileHandle.nullDevice
        process.standardError=FileHandle.nullDevice
        try process.run()
        guardian=process
    }
    static func snapshot() throws -> [Entry] {
        let process = Process(), pipe = Pipe()
        process.executableURL = URL(fileURLWithPath: "/bin/ps")
        process.arguments = ["-axo", "pid=,ppid=,lstart="]
        process.standardOutput = pipe
        try process.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { throw CocoaError(.fileReadUnknown) }
        return String(decoding: data, as: UTF8.self).split(separator: "\n").compactMap { line in
            let fields = line.split(maxSplits: 2, whereSeparator: { $0 == " " || $0 == "\t" })
            guard fields.count == 3, let pid = Int32(fields[0]), let parent = Int32(fields[1]) else { return nil }
            return Entry(pid: pid, parent: parent, started: String(fields[2]))
        }
    }
    static func descendants(of root: Int32, in entries: [Entry]) -> [Entry] {
        var parents: Set<Int32> = [root], result: [Entry] = []
        var remaining = entries.filter { $0.pid != root }
        while true {
            let children = remaining.filter { parents.contains($0.parent) }
            if children.isEmpty { return result }
            result += children
            let ids = Set(children.map(\.pid)); parents.formUnion(ids)
            remaining.removeAll { ids.contains($0.pid) }
        }
    }
    func pause(_ root: Int32) throws {
        guard stopped.isEmpty, root > 1, root != getpid(),
              let entry = try Self.snapshot().first(where: { $0.pid == root }) else { throw CocoaError(.executableNotLoadable) }
        do {
            try stop(entry)
            // Once all parents are stopped, no tool can create a new descendant.
            for _ in 0..<16 {
                let entries = try Self.snapshot()
                let ids = Set(stopped.map(\.pid))
                let children = Self.descendants(of: root, in: entries).filter { !ids.contains($0.pid) }
                if children.isEmpty { return }
                for child in children { try stop(child) }
            }
            throw CocoaError(.executableRuntimeMismatch)
        } catch { resume(); throw error }
    }
    private func stop(_ entry: Entry) throws {
        if kill(entry.pid, SIGSTOP) == 0 { stopped.append(entry) }
        else if errno != ESRCH { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EPERM) }
    }
    func resume() {
        guard !stopped.isEmpty else { return }
        // A failed identity lookup must not signal an unrelated recycled PID.
        guard let entries = try? Self.snapshot() else { return }
        let current = Dictionary(uniqueKeysWithValues: entries.map { ($0.pid, $0.started) })
        for entry in stopped.reversed() where current[entry.pid] == entry.started { kill(entry.pid, SIGCONT) }
        stopped.removeAll()
        if guardian?.isRunning == true {guardian?.terminate()};guardian=nil
    }
}
