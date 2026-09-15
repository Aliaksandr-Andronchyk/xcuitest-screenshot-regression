"""xcshot: screenshot regression around an XCUITest run.

The pieces on purpose do not depend on each other:

  attachments  screenshots out of an .xcresult bundle (needs macOS and Xcode)
  png          8-bit PNG read and write, standard library only
  compare      baseline against current, pixel by pixel, with a diff image
  report       one self-contained HTML file

Only the first piece needs a Mac, so the comparison can be tested anywhere.
"""

__version__ = "1.0.0"
