import sys
log = open("_wsu.log", "w", encoding="utf-8")
def L(*a):
    print(*a, file=log); log.flush()

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import main

L("start")
app = QApplication(sys.argv)
win = main.MainWindow()
win.show()
hs = win.pages["home"]
L("window built, WS ishga tushdi")

# WS signallarini kuzatamiz
flags = {"status": False, "link": False}
win.ws.status.connect(lambda d: flags.__setitem__("status", True))
win.ws.link.connect(lambda ok: flags.__setitem__("link", ok))

def check():
    L("WS link (ulangan): %s" % flags["link"])
    L("status_update keldimi: %s" % flags["status"])
    L("home speed (WS orqali): %s" % hs.speed_val.text())
    L("home location: %s" % hs.loc_val.text())
    # Announcement bannerini sinash
    win.show_announcement("Keyingi bekat: Samarqand")
    L("banner ko'rinadi: %s | matn: %s" % (win.banner.isVisible(), win.banner.text()))
    L("USER WS TEST O'TDI")
    win.ws.stop()
    app.quit()

QTimer.singleShot(3000, check)  # WS ulanib status kelishini kutamiz
app.exec()
log.close()
