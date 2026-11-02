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
