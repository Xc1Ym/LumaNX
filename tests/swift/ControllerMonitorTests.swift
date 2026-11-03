import GameController
import XCTest
@testable import LumaNX

@MainActor final class ControllerMonitorTests: XCTestCase {
    func testInputPageReportsGameControllerLabelsWithoutAnotherSwap() {
        let controller=GCController.withExtendedGamepad()
        let pad=controller.extendedGamepad!
        let buttons=[pad.buttonA,pad.buttonB,pad.buttonX,pad.buttonY]
        XCTAssertEqual(ControllerMonitor.faceLabels(pad),[])
        for (button,label) in zip(buttons,["A","B","X","Y"]) {
            button.setValue(1)
            XCTAssertEqual(ControllerMonitor.faceLabels(pad),[label])
            button.setValue(0)
            XCTAssertEqual(ControllerMonitor.faceLabels(pad),[])
        }
        pad.buttonA.setValue(1);pad.buttonX.setValue(1)
        XCTAssertEqual(ControllerMonitor.faceLabels(pad),["A","X"])
    }
    func testHeldButtonAndRepeatedAxisEventsKeepOneLabel() {
        let pad=GCController.withExtendedGamepad().extendedGamepad!
        pad.buttonA.setValue(1)
        for i in 0..<1000 {
            pad.leftThumbstick.setValueForXAxis(Float(i%3)-1,yAxis:0)
            let reading=ControllerMonitor.reading(pad)
            XCTAssertEqual(reading.components(separatedBy:" · A").count-1,1)
            XCTAssertLessThan(reading.count,180)
        }
        pad.buttonA.setValue(0)
        XCTAssertFalse(ControllerMonitor.reading(pad).hasSuffix(" · A"))
    }
}

private final class LayoutTestController: GCController {
    var reportedVendor = ""
    var reportedCategory = ""
    let snapshotController = GCController.withExtendedGamepad()
    override var vendorName: String? { reportedVendor }
    override var productCategory: String { reportedCategory }
    override var extendedGamepad: GCExtendedGamepad? { snapshotController.extendedGamepad }
}

extension ControllerMonitorTests {
    func testDeviceIdentityPersistenceAndUnknownModeFallback() throws {
        let root=FileManager.default.temporaryDirectory.appendingPathComponent("layouts-"+UUID().uuidString)
        defer {try? FileManager.default.removeItem(at:root)}
        let key=ControllerLayouts.key(vendor:"8BitDo 布局测试",category:"HID")!
        XCTAssertEqual(key,"19:8BitDo 布局测试3:HID")
        XCTAssertNotEqual(ControllerLayouts.key(vendor:"ab",category:"c"),ControllerLayouts.key(vendor:"a",category:"bc"))
        XCTAssertNil(ControllerLayouts.key(vendor:"",category:""))
        let store=Store(privateRoot:root)
        store.saveControllerLayout(.switchPosition,for:key)
        let restarted=Store(privateRoot:root)
        XCTAssertEqual(restarted.controllerLayouts.layout(for:key),.switchPosition)
        XCTAssertEqual(restarted.controllerLayouts.layout(for:ControllerLayouts.key(vendor:"8BitDo 布局测试",category:"XInput")),.reported)
        XCTAssertEqual(restarted.controllerLayouts.layout(for:ControllerLayouts.key(vendor:"Other pad",category:"HID")),.reported)
        restarted.controllerLayouts.layouts["unknown"]="future-mode"
        XCTAssertEqual(restarted.controllerLayouts.layout(for:"unknown"),.reported)
        restarted.saveControllerLayout(.reported,for:key)
        XCTAssertEqual(Store(privateRoot:root).controllerLayouts.layout(for:key),.reported)
        XCTAssertNil(restarted.controllerLayouts.layouts[key])
        try Data("{\"schema\":99,\"layouts\":{}}".utf8).write(to:root.appendingPathComponent("controller-layouts.json"))
        XCTAssertEqual(Store(privateRoot:root).controllerLayouts,.init())
    }
    func testInputPreviewUsesSelectedDevicePolicyAcrossDisconnectAndReconnect() {
        let first=LayoutTestController();first.reportedVendor="First";first.reportedCategory="HID"
        let second=LayoutTestController();second.reportedVendor="Second";second.reportedCategory="HID"
        first.extendedGamepad!.buttonA.setValue(1);second.extendedGamepad!.buttonA.setValue(1)
        let monitor=ControllerMonitor()
        monitor.layouts.layouts[ControllerLayouts.key(first)!]="switchPosition"
        monitor.refresh(controllers:[first,second])
        XCTAssertTrue(monitor.value.hasSuffix(" · B"))
        monitor.selectedID=ObjectIdentifier(second)
        XCTAssertTrue(monitor.value.hasSuffix(" · A"))
        monitor.refresh(controllers:[first])
        XCTAssertTrue(monitor.value.hasSuffix(" · B"))
        monitor.refresh(controllers:[])
        XCTAssertTrue(monitor.devices.isEmpty)
        XCTAssertEqual(monitor.value,L("所有输入已清空"))
        let reconnected=LayoutTestController();reconnected.reportedVendor="First";reconnected.reportedCategory="HID"
        reconnected.extendedGamepad!.buttonX.setValue(1)
        monitor.refresh(controllers:[second,reconnected])
        monitor.selectedID=ObjectIdentifier(reconnected)
        XCTAssertTrue(monitor.value.hasSuffix(" · Y"))
        monitor.layouts = .init()
        XCTAssertTrue(monitor.value.hasSuffix(" · X"))
    }
}
