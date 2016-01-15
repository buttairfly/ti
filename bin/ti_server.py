"""
A simple example of hooking the keyboard on Linux using pyxhook

Any key pressed prints out the keys values, program terminates when spacebar is pressed
"""

#Libraries we need
import sys
import time
import subprocess
import signal

import pyxhook

KEYS_ALREADY_PRESSED = set()
STATE = "stop"
CALLBACK = lambda state: None

#This function is called every time a key is presssed
def kbdown(event):
    global STATE
    if KEYS_ALREADY_PRESSED == set(("Control_L", "Alt_L")):
        if event.Key == "Page_Up":
            cmd = "ti on"
            STATE = "start"
        elif event.Key == "Next":
            cmd = "ti fin"
            STATE = "stop"
        elif event.Key == "i":
            cmd = "ti log today"
        elif event.Key == "s":
            cmd = "ti status"
        else:
            cmd = ""
        # print(cmd)
        if cmd != "":
            print(time.strftime("%Y-%m-%d %H:%M"))
            try:
                text = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE).communicate()[0]
            except subprocess.CalledProcessError:
                # We ignore non-0 system exits
                pass
            print(text.decode("utf-8").strip())
            CALLBACK(STATE)
    # elif KEYS_ALREADY_PRESSED == set(("Control_L",)):
    #     if event.Key == "c":
    #         sys.exit()
    if event.Key in ["Control_L", "Alt_L"]:
        KEYS_ALREADY_PRESSED.add(event.Key)

def kbup(event):
    if event.Key in ["Control_L", "Alt_L"] and event.Key in KEYS_ALREADY_PRESSED:
        KEYS_ALREADY_PRESSED.remove(event.Key)

#Create hookmanager
hookman = pyxhook.HookManager()
#Define our callback to fire when a key is pressed down
hookman.KeyDown = kbdown
hookman.KeyUp = kbup
#Hook the keyboard
hookman.HookKeyboard()

def main():

    #Start our listener
    hookman.start()

    #Create a loop to keep the application running
    # running = True
    # while running:
    #     time.sleep(0.1)
    # import ti_systray
    # ti_systray.main()

    #Close the listener when we are done
    # hookman.cancel()

if __name__ == "__main__":
    try:
        main()
    except:
        sys.exit()
