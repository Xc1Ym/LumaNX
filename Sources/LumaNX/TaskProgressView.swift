import SwiftUI

/// Counts are worker measurements. Unknown totals use an indeterminate linear bar.
struct TaskProgressView: View {
    let task: TaskRecord
    var compact = false
    private func amount(_ value: Double) -> String {
        if task.unit == "B" {
            return ByteCountFormatter.string(fromByteCount:Int64(min(Double(Int64.max-1024),max(0,value))),countStyle:.file)
        }
        return String(format:"%.0f",max(0,value))
    }
    var body: some View {
        VStack(alignment:.leading,spacing:8) {
            progressContent
            if task.state == "running" {TaskActivityView(task:task)}
        }
    }
    @ViewBuilder private var progressContent: some View {
        if task.state == "paused" {
            VStack(alignment:.leading,spacing:6) {
                Label(L("任务已暂停，点击继续任务以恢复。"),systemImage:"pause.circle")
                    .font(.caption).foregroundStyle(.secondary)
                if let fraction=task.progressFraction {ProgressView(value:fraction).tint(.secondary)}
            }
        } else if !(task.milestones ?? []).isEmpty,task.milestone != nil {
            MilestoneProgressView(task:task,compact:compact)
        } else {standard}
    }
    private var standard:some View {
        VStack(alignment:.leading,spacing:6) {
            if !compact,let fraction=task.stageFraction,let index=task.stageIndex,let count=task.stageCount {
                ProgressView(L("整体阶段 \(index)/\(count)"),value:fraction).tint(.teal)
            }
            if let fraction=task.progressFraction,let done=task.done,let total=task.total {
                ProgressView(value:fraction).progressViewStyle(.linear).tint(.teal)
                    .accessibilityLabel(L("当前阶段进度"))
                HStack {
                    Text("\(Int(fraction*100))%")
                    Text(amount(min(done,total))+" / "+amount(total))
                    if let unit=task.unit,let label=["files":"个文件","shaders":"个着色器","checks":"项检查"][unit] {Text(L(label))}
                    Spacer()
                    elapsed
                }.font(.caption).foregroundStyle(.secondary)
            } else {
                ProgressView().progressViewStyle(.linear).tint(.teal)
                    .accessibilityLabel(L("处理中，总量暂不可确定"))
                HStack {
                    if let done=task.done,done>0 {Text(L("已处理：")+amount(done))}
                    else {Text(L("处理中，总量暂不可确定"))}
                    Spacer();elapsed
                }.font(.caption).foregroundStyle(.secondary)
            }
        }
    }
    private var elapsed: some View {
        TimelineView(.periodic(from:.now,by:1)) {timeline in
            if let started=task.started {
                Text(L("已用 \(Int(min(315360000,max(0,timeline.date.timeIntervalSince1970-started)))) 秒"))
                    .monospacedDigit()
            }
        }
    }
}

struct ActiveTaskBanner: View {
    @EnvironmentObject var store: Store
    var body: some View {
        VStack(alignment:.leading,spacing:10) {
            HStack {
                Text(L("正在处理 \(store.activeTasks.count) 个任务")).font(.caption.bold())
                Spacer()
                Button(L("查看全部任务")) {store.selection="tasks"}
                    .buttonStyle(.borderless).controlSize(.small)
            }
            ForEach(Array(store.activeTasks.prefix(2))) {task in
                VStack(alignment:.leading,spacing:4) {
                    HStack {Text(task.title).font(.caption.bold());Text(L(task.stage ?? "")).font(.caption).foregroundStyle(.secondary).lineLimit(1)}
                    TaskProgressView(task:task,compact:true)
                }
            }
        }.padding(16).glassSurface(18).padding(.horizontal,24).padding(.bottom,16)
    }
}

/// A heartbeat confirms the worker connection, not forward progress.
struct TaskActivityView: View {
    let task:TaskRecord
    static func seconds(since time:Double?,now:Double)->Int? {
        guard let time,time.isFinite,now.isFinite else {return nil}
        return Int(min(315360000,max(0,now-time)))
    }
    private func age(_ seconds:Int)->String {seconds<60 ? "\(seconds)s" : "\(seconds/60)m \(seconds%60)s"}
    var body:some View {
        TimelineView(.periodic(from:.now,by:2)) {timeline in
            let now=timeline.date.timeIntervalSince1970
            let heartbeat=Self.seconds(since:task.lastHeartbeat,now:now)
            let progress=Self.seconds(since:task.lastProgressAt ?? task.started,now:now)
            VStack(alignment:.leading,spacing:3) {
                if let heartbeat {
                    Label(heartbeat<10 ? "Worker responding · heartbeat \(age(heartbeat)) ago" : "Worker heartbeat delayed · \(age(heartbeat)) ago",systemImage:heartbeat<10 ? "waveform.path" : "exclamationmark.circle")
                        .foregroundStyle(heartbeat<10 ? Color.secondary : Color.orange)
                } else {Text("Waiting for worker heartbeat…").foregroundStyle(.secondary)}
                if let progress {Text("Last measured progress change: \(age(progress)) ago").foregroundStyle(.secondary)}
                if let output=Self.seconds(since:task.lastOutputAt,now:now) {Text("Last log output: \(age(output)) ago").foregroundStyle(.secondary)}
                if let progress,progress>=60 {Text("No new measured progress. The task may still be working; check its log for details.").foregroundStyle(.orange)}
            }.font(.caption).textSelection(.enabled)
        }
    }
}
