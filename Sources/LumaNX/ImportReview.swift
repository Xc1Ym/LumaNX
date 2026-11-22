import SwiftUI

struct ImportPreviewEntry: Decodable, Identifiable {
    struct Package: Decodable {
        let type: String
        let version: Int
        let display: String?
        let titleId: String
        let name: String?
    }

    var id: String { path }
    let path: String
    let name: String
    let format: String
    let size: Int64?
    let requiresKeys: Bool
    let title: String?
    let packages: [Package]
    let requirements: [String]?
    let metadataDeferred: Bool?
    let error: String?
}

struct ImportReview: Identifiable {
    let id = UUID()
    let libraryId: String
    let entries: [ImportPreviewEntry]
}

struct ImportReviewView: View {
    @EnvironmentObject var store: Store
    let review: ImportReview
    @State private var selected: Set<String>
    @State private var prepare: Bool

    init(review: ImportReview, prepare: Bool) {
        self.review = review
        _selected = State(initialValue:Set(review.entries.filter { $0.error == nil }.map(\.path)))
        _prepare = State(initialValue:prepare)
    }

    var body: some View {
        VStack(alignment:.leading,spacing:16) {
            Text(L("检查要导入的游戏")).font(.title2.bold())
            Text(L("请选择要复制到游戏库的文件或文件夹。")).foregroundStyle(.secondary)
            List(review.entries) { entry in
                VStack(alignment:.leading,spacing:5) {
                    Toggle(entry.title ?? entry.name,isOn:Binding(
                        get:{ selected.contains(entry.path) },
                        set:{ if $0 { selected.insert(entry.path) } else { selected.remove(entry.path) } }
                    )).disabled(entry.error != nil).fontWeight(.medium)
                    Text([entry.format, entry.size.map { ByteCountFormatter.string(fromByteCount:$0,countStyle:.file) }, entry.title == nil ? nil : entry.name].compactMap { $0 }.joined(separator:" · "))
                        .textSelection(.enabled)
                    ForEach(Array(entry.packages.enumerated()),id:\.offset) { _, package in
                        let kind = ["base":L("本体"),"update":L("更新"),"dlc":"DLC"][package.type] ?? package.type
                        let internalVersion = "v\(package.version)"
                        let version = package.display.flatMap { $0.isEmpty || $0 == internalVersion ? nil : $0 } ?? internalVersion
                        Text([package.name == entry.title ? nil : package.name, kind, version, package.titleId].compactMap { $0 }.joined(separator:" · "))
                            .textSelection(.enabled)
                    }
                    if entry.metadataDeferred == true {
                        Text(L("此文件的详细内容将在导入时读取。"))
                    }
                    ForEach(Array((entry.requirements ?? []).enumerated()),id:\.offset) { _, warning in
                        Text(L(warning)).foregroundStyle(.orange)
                    }
                    if let error = entry.error { Text(L(error)).foregroundStyle(.red) }
                }.font(.callout).padding(.vertical,6)
            }
            Toggle(L("导入后准备游戏"),isOn:$prepare)
            HStack {
                Spacer()
                Button(L("取消")) { store.importReview = nil }.keyboardShortcut(.cancelAction)
                Button(L("导入所选内容")) { store.confirmImport(review,paths:selected,prepare:prepare) }
                    .keyboardShortcut(.defaultAction)
                    .disabled(selected.isEmpty)
            }
        }.padding(22).frame(width:720,height:500)
    }
}
