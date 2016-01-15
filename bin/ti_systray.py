import os
import sys
from PyQt4 import QtGui, QtCore
from PyQt4.QtCore import QTimer
import signal
import subprocess

# import ti_server

def exit():
    # ti_server.hookman.cancel()
    QtCore.QCoreApplication.quit()

def myicon(icon):
    dirname = os.path.dirname(os.path.realpath(__file__))
    icon = os.path.join(dirname, icon)
    return QtGui.QIcon(icon)

class SystemTrayIcon(QtGui.QSystemTrayIcon):
    def __init__(self, icon, parent=None):
        QtGui.QSystemTrayIcon.__init__(self, icon, parent)
        menu = QtGui.QMenu(parent)
        exitAction = QtGui.QAction("&Exit", menu)
        exitAction.triggered.connect(exit)
        menu.addAction(exitAction)
        self.setContextMenu(menu)


def main():
    signal.signal(signal.SIGINT, lambda *args: QtGui.QApplication.quit())
    app = QtGui.QApplication(sys.argv)

    w = QtGui.QWidget()
    trayIcon = SystemTrayIcon(myicon("stop.svg"), w)

    def show_icon(icon):
        trayIcon.setToolTip("<i>unko!</i>")
        trayIcon.setIcon(icon)
        trayIcon.show()

    def callback(state):
        show_icon(myicon("%s.svg"%state))

    def check_status():
        status = subprocess.Popen("ti status --no-gui-notification".split(), stdout=subprocess.PIPE).communicate()[0]
        if status.find("Not working on any task.") != -1:
            state = "stop"
        elif status.find("Working on ") != -1:
            state = "start"
        else:
            raise Exception()
        callback(state)

    check_status()
    timer = QTimer()
    timer.start(1000)  # You may change this if you wish.
    timer.timeout.connect(check_status)  # Let the interpreter run each 500 ms.

    # ti_server.CALLBACK = callback
    # ti_server.main()
    app.exec_()
    sys.exit()

if __name__ == '__main__':
    main()
