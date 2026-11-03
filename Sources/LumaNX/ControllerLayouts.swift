import Foundation
import GameController

// Exact reported identity, independent of player slot and connection order.
// GameController supplies no per-unit persistent identifier: identical devices
// share this setting. Never infer Nintendo layout from a fuzzy product name.
enum ControllerLayout: String, CaseIterable {
    case reported, switchPosition
    var name: String { self == .reported ? L("按报告字母") : L("按 Switch 物理位置") }
    var faceLabels: [String] { self == .reported ? ["A","B","X","Y"] : ["B","A","Y","X"] }
}
struct ControllerLayouts: Codable, Equatable {
    var schema = 1
    var layouts: [String:String] = [:]
    static func key(vendor: String, category: String) -> String? {
        guard !vendor.isEmpty || !category.isEmpty else { return nil }
        return "\(vendor.utf8.count):\(vendor)\(category.utf8.count):\(category)"
    }
    static func key(_ controller: GCController) -> String? {
        key(vendor:controller.vendorName ?? "",category:controller.productCategory)
    }
    func layout(for key: String?) -> ControllerLayout {
        guard schema == 1, let key, let raw=layouts[key], let mode=ControllerLayout(rawValue:raw) else { return .reported }
        return mode
    }
    static func load(_ url: URL) -> ControllerLayouts {
        guard let data=try? Data(contentsOf:url), let value=try? JSONDecoder().decode(Self.self,from:data), value.schema == 1 else { return .init() }
        return value
    }
}
