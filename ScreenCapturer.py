import cv2
import numpy as np
import mss
import win32gui # type: ignore

class ScreenCapturer:
    def __init__(self, window_title="欢乐斗地主"):
        self.window_title = window_title

    def get_window_rect(self):
        hwnd = win32gui.FindWindow(None, self.window_title)
        if not hwnd:
            def callback(h, extra):
                if self.window_title in win32gui.GetWindowText(h): extra.append(h)
            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            hwnd = hwnds[0] if hwnds else None
        
        if not hwnd: return None
        rect = win32gui.GetWindowRect(hwnd)
        return {"top": rect[1], "left": rect[0], "width": rect[2] - rect[0], "height": rect[3] - rect[1], "hwnd": hwnd}

    def capture(self):
        rect = self.get_window_rect()
        if not rect: return None, None
        monitor = {"top": rect["top"], "left": rect["left"], "width": rect["width"], "height": rect["height"]}
        with mss.mss() as sct:
            img = sct.grab(monitor)
            frame = cv2.cvtColor(np.array(img), cv2.COLOR_BGRA2BGR)
            return frame, rect

