import XCTest

/// An example suite: what a screenshot walk through an app looks like.
///
/// Replace the identifiers with the ones your app exposes. Keep the shape:
/// one test per screen or per state, one snapshot name per state, no sleeps.
final class ScreenshotRegressionUITests: ScreenshotCase {

    func testLaunchScreen() {
        snapshot("01_launch", after: app.otherElements["root"])
    }

    func testEmptyCart() {
        app.tabBars.buttons["cart"].tap()
        snapshot("02_cart_empty", after: app.staticTexts["cart.empty.title"])
    }

    func testCartWithItems() {
        app.tabBars.buttons["catalog"].tap()
        await(app.cells.firstMatch).tap()
        await(app.buttons["product.add"]).tap()
        app.tabBars.buttons["cart"].tap()
        snapshot("03_cart_filled", after: app.staticTexts["cart.total"])
    }

    func testDarkMode() {
        // The app reads this in its scene setup when launched under -UITest.
        app.terminate()
        app.launchEnvironment["UITEST_APPEARANCE"] = "dark"
        app.launch()
        snapshot("04_catalog_dark", after: app.otherElements["root"])
    }

    /// Landscape catches the layout breakages a portrait-only suite never sees.
    func testLandscape() {
        XCUIDevice.shared.orientation = .landscapeLeft
        defer { XCUIDevice.shared.orientation = .portrait }
        snapshot("05_catalog_landscape", after: app.otherElements["root"])
    }
}
