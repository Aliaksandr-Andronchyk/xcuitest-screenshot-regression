import XCTest

/// The suite itself: walk the app and take one named shot per screen.
///
/// Adapt the queries to your app; the shape is what matters. Each test takes
/// shots only, asserts nothing about pixels: the verdict is `shotdiff`'s job
/// after the run, when it can show a human what changed.
final class AppScreenshotTests: XCTestCase {

    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = ScreenshotRegression.makeApp()
        app.launch()
    }

    override func tearDownWithError() throws {
        app.terminate()
        app = nil
    }

    func testFeed() throws {
        ScreenshotRegression.capture("feed", app: app)

        let firstCell = app.cells.firstMatch
        XCTAssertTrue(firstCell.waitForExistence(timeout: 5), "лента не наполнилась")
        firstCell.tap()
        ScreenshotRegression.capture("feed-detail", app: app)
    }

    func testPaywall() throws {
        app.tabBars.buttons["Профиль"].tap()
        let upgrade = app.buttons["upgrade"]
        XCTAssertTrue(upgrade.waitForExistence(timeout: 5), "кнопки апгрейда нет")
        upgrade.tap()
        ScreenshotRegression.capture("paywall", app: app)
    }

    func testSettings() throws {
        app.tabBars.buttons["Настройки"].tap()
        ScreenshotRegression.capture("settings", app: app)

        app.switches.firstMatch.tap()
        ScreenshotRegression.capture("settings-toggled", app: app)
    }

    /// Dark mode doubles the shot count and catches the bugs that only live
    /// in one appearance, which is most of them.
    func testSettingsDark() throws {
        app.terminate()
        app.launchArguments += ["-UITestAppearance", "dark"]
        app.launch()
        app.tabBars.buttons["Настройки"].tap()
        ScreenshotRegression.capture("settings-dark", app: app)
    }
}
