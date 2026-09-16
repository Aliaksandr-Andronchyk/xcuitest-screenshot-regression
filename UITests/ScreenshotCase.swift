import XCTest

/// Base class for screenshot tests.
///
/// Two rules make a screenshot run repeatable:
/// the app starts from a known state every time, and the snapshot is taken
/// only after the element it is about actually exists on screen. Everything
/// else here is bookkeeping.
open class ScreenshotCase: XCTestCase {

    public private(set) var app: XCUIApplication!

    /// How long to wait for an element before giving up on a case.
    open var waitTimeout: TimeInterval { 10 }

    /// Launch arguments that make the app deterministic: no animation, no
    /// onboarding, fixed data. The app has to honour them, this is the
    /// contract between the app and its screenshot suite.
    open var launchArguments: [String] {
        ["-UITest", "-UIPreferredContentSizeCategoryName", "UICTContentSizeCategoryM"]
    }

    open var launchEnvironment: [String: String] {
        ["UITEST_SEED": "1", "UITEST_DISABLE_ANIMATIONS": "1"]
    }

    open override func setUpWithError() throws {
        try super.setUpWithError()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = launchArguments
        app.launchEnvironment = launchEnvironment
        app.launch()
    }

    open override func tearDownWithError() throws {
        app = nil
        try super.tearDownWithError()
    }

    /// Wait until `element` is on screen, and fail the case with a readable
    /// message if it never shows up.
    @discardableResult
    public func await(_ element: XCUIElement,
                      file: StaticString = #filePath,
                      line: UInt = #line) -> XCUIElement {
        let exists = element.waitForExistence(timeout: waitTimeout)
        XCTAssertTrue(exists,
                      "element never appeared: \(element.debugDescription)",
                      file: file, line: line)
        return element
    }

    /// Attach a screenshot under `name`.
    ///
    /// The name becomes the file name on disk, so it must be stable across
    /// runs: `cart_empty`, not `cart \(Date())`. `.keepAlways` is what makes
    /// the attachment survive a passing test, which is the whole point here.
    public func snapshot(_ name: String) {
        let shot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: shot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    /// Wait for an element, then snapshot. The common case.
    public func snapshot(_ name: String,
                         after element: XCUIElement,
                         file: StaticString = #filePath,
                         line: UInt = #line) {
        await(element, file: file, line: line)
        snapshot(name)
    }
}
