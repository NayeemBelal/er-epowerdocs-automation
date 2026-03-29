"""
Run this script with EPOWERdoc open and the registration screen visible.
It will print all UI control identifiers to the terminal.
Copy and paste the full output to Claude.
"""

from pywinauto import Application

app = Application(backend="uia").connect(path="EPD.exe")
app.top_window().print_control_identifiers()
