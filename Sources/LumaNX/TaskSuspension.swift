import Foundation
import Darwin

/// The kernel checks the audit token's PID generation when delivering a signal.
final class TaskSuspension {
    struct Identity: Codable, Equatable {
        let token: [UInt32]
        var pid: Int32 { Int32(bitPattern:token[5]) }
    }

    private typealias AuditSignal = @convention(c) (UnsafeMutablePointer<audit_token_t>, Int32) -> Int32
    private static let auditSignal: AuditSignal? = {
        guard let symbol = dlsym(dlopen(nil, RTLD_NOW), "proc_signal_with_audittoken") else { return nil }
        return unsafeBitCast(symbol, to:AuditSignal.self)
    }()

    private(set) var stopped: [Identity] = []
    private var guardian: Process?
    private var journal: FileHandle?
    private var root: Identity?
    private let deliver: (Identity, Int32) throws -> Bool

    init(deliver: @escaping (Identity, Int32) throws -> Bool = TaskSuspension.signal) {
        self.deliver = deliver
    }
    var hasPendingCleanup: Bool { !stopped.isEmpty }

    static func identity(_ pid: Int32) -> Identity? {
        guard pid > 1, auditSignal != nil else { return nil }
        var port: mach_port_name_t = 0
        guard task_name_for_pid(mach_task_self_, pid, &port) == KERN_SUCCESS else { return nil }
        defer { mach_port_deallocate(mach_task_self_, port) }
        var token = audit_token_t()
        var count = mach_msg_type_number_t(MemoryLayout<audit_token_t>.size / MemoryLayout<integer_t>.size)
        let status = withUnsafeMutablePointer(to:&token) { pointer in
            pointer.withMemoryRebound(to:integer_t.self,capacity:8) {
                task_info(port, task_flavor_t(TASK_AUDIT_TOKEN), $0, &count)
            }
        }
        guard status == KERN_SUCCESS, count == 8, token.val.5 == UInt32(pid) else { return nil }
        return Identity(token:withUnsafeBytes(of:&token) { Array($0.bindMemory(to:UInt32.self)) })
    }

    @discardableResult
    static func signal(_ identity: Identity, _ signal: Int32) throws -> Bool {
        guard let auditSignal, identity.token.count == 8 else { throw POSIXError(.ENOTSUP) }
        let a = identity.token
        var token = audit_token_t(val:(a[0],a[1],a[2],a[3],a[4],a[5],a[6],a[7]))
        if auditSignal(&token, signal) == 0 { return true }
        if errno == ESRCH { return false }
        throw POSIXError(POSIXErrorCode(rawValue:errno) ?? .EPERM)
    }

    private static func parent(of pid: Int32) -> Int32? {
        var info = proc_bsdinfo()
        let size = Int32(MemoryLayout<proc_bsdinfo>.size)
        guard proc_pidinfo(pid, PROC_PIDTBSDINFO, 0, &info, size) == size else { return nil }
        return Int32(bitPattern:info.pbi_ppid)
    }

    private static func relationships() throws -> [(pid:Int32,parent:Int32)] {
        let process = Process(), pipe = Pipe()
        process.executableURL = URL(fileURLWithPath:"/bin/ps")
        process.arguments = ["-axo","pid=,ppid="]
        process.standardOutput = pipe
        try process.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        process.waitUntilExit()
        guard process.terminationStatus == 0 else { throw CocoaError(.fileReadUnknown) }
        return String(decoding:data,as:UTF8.self).split(separator:"\n").compactMap { line in
            let fields = line.split(whereSeparator:\.isWhitespace)
            guard fields.count == 2, let pid = Int32(fields[0]), let parent = Int32(fields[1]) else { return nil }
            return (pid,parent)
        }
    }

    func pause(_ root: Identity) throws {
        guard stopped.isEmpty, root.pid != getpid(), Self.identity(root.pid) == root else {
            throw CocoaError(.executableNotLoadable)
        }
        self.root = root
        do {
            guard try stop(root) else { throw POSIXError(.ESRCH) }
            for _ in 0..<16 {
                let parents = Dictionary(uniqueKeysWithValues:stopped.map { ($0.pid,$0) })
                var added = false
                for candidate in try Self.relationships() {
                    guard parents[candidate.pid] == nil, let parent = parents[candidate.parent],
                          let child = Self.identity(candidate.pid) else { continue }
                    // Confirm the relationship belongs to the identities that will
                    // be signalled. The kernel rejects an exited token or reused PID.
                    guard Self.parent(of:child.pid) == parent.pid,
                          Self.identity(parent.pid) == parent,
                          Self.identity(child.pid) == child else { continue }
                    if try stop(child) { added = true }
                }
                if !added { return }
            }
            throw CocoaError(.executableRuntimeMismatch)
        } catch {
            resume()
            throw error
        }
    }

    private func stop(_ identity: Identity) throws -> Bool {
        if let journal {
            var record = try JSONEncoder().encode(identity)
            record.append(10)
            try journal.write(contentsOf:record)
        }
        guard try deliver(identity,SIGSTOP) else { return false }
        stopped.append(identity)
        return true
    }

    func guardAgainstAppExit(python: URL, script: URL, root: Identity) throws {
        let pipe = Pipe()
        let writer = pipe.fileHandleForWriting
        guard fcntl(writer.fileDescriptor,F_SETNOSIGPIPE,1) != -1 else {
            throw POSIXError(POSIXErrorCode(rawValue:errno) ?? .EPERM)
        }
        let process = Process()
        process.executableURL = python
        process.arguments = ["-B","-I",script.path,String(decoding:try JSONEncoder().encode(root),as:UTF8.self)]
        process.standardInput = pipe
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        try process.run()
        try? pipe.fileHandleForReading.close()
        guardian = process
        journal = writer
    }

    func cancel() throws {
        if let root { _ = try deliver(root,SIGTERM) }
        resume()
    }

    func resume() {
        var pending: [Identity] = []
        for process in stopped.reversed() {
            do { _ = try deliver(process,SIGCONT) }
            catch { pending.append(process) }
        }
        stopped = Array(pending.reversed())
        if stopped.isEmpty {
            if let journal {
                try? journal.write(contentsOf:Data("done\n".utf8))
                try? journal.close()
            }
            journal = nil
            guardian = nil
        }
    }
}
