import XCTest

/// Takes named screenshots inside a UI test and attaches them to the result
/// bundle, where `shotdiff extract` picks them up.
///
/// Two rules keep the shots comparable between runs:
///  1. the simulator is put into a fixed state (see `SimulatorState`) before
///     the first shot, so time, battery and locale do not drift;
///  2. every shot waits for the UI to settle, because a screenshot of a
///     half-finished animation is a guaranteed false positive.
enum ScreenshotRegression {

    /// Attachment names carry this prefix so the extractor can tell our shots
    /// apart from the automatic ones XCTest takes on failure.
    static let attachmentPrefix = "shot:"

    /// Capture the whole screen and attach it under `name`.
    ///
    /// - Parameters:
    ///   - name: file name of the shot, without extension; becomes `<name>.png`
    ///   - app: the application under test
    ///   - settleFor: how long the UI must stay quiet before the shutter fires
    static func capture(
        _ name: String,
        app: XCUIApplication,
        settleFor interval: TimeInterval = 0.4,
        file: StaticString = #filePath,
        line: UInt = #line
    ) {
        XCTAssertTrue(
            app.wait(for: .runningForeground, timeout: 10),
            "приложение не в переднем плане, снимок \(name) бессмыслен",
            file: file,
            line: line
        )
        waitUntilStill(app: app, interval: interval)

        let screenshot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: screenshot)
        attachment.name = attachmentPrefix + name
        attachment.lifetime = .keepAlways
        XCTContext.runActivity(named: "снимок \(name)") { activity in
            activity.add(attachment)
        }
    }

    /// Waits until two consecutive screenshots are identical, i.e. animations
    /// and spinners have stopped. Gives up after `timeout` and takes the shot
    /// anyway, so a permanently animated screen fails loudly on the diff
    /// instead of hanging the suite.
    static func waitUntilStill(app: XCUIApplication, interval: TimeInterval, timeout: TimeInterval = 5) {
        let deadline = Date().addingTimeInterval(timeout)
        var previous = XCUIScreen.main.screenshot().pngRepresentation
        while Date() < deadline {
            Thread.sleep(forTimeInterval: interval)
            let current = XCUIScreen.main.screenshot().pngRepresentation
            if current == previous { return }
            previous = current
        }
    }

    /// Launch arguments the app should honour to become screenshot-stable:
    /// no animations, fixed seed data, no network, no onboarding.
    static var stableLaunchArguments: [String] {
        ["-UITest", "-UITestDisableAnimations", "-UITestSeededData", "-AppleLanguages", "(ru)"]
    }

    /// Prepares an app instance that is safe to screenshot.
    static func makeApp() -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments += stableLaunchArguments
        app.launchEnvironment["UITEST_FROZEN_CLOCK"] = "2026-09-13T09:41:00Z"
        return app
    }
}
