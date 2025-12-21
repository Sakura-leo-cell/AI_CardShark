import cv2
import numpy as np
import mss
import win32gui # type: ignore
import win32print # type: ignore
import win32con # type: ignore
import ctypes

class ScreenCapturer:
    def __init__(self, window_title="欢乐斗地主"):
        self.window_title = window_title
        # 核心：设置进程的 DPI 感知，防止缩放导致的截不到位
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1) # 1 = 系统 DPI 感知
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()

    def get_window_rect(self):
        """获取指定窗口的真实物理坐标"""
        hwnd = win32gui.FindWindow(None, self.window_title)
        if not hwnd:
            # 微信小程序有时窗口名后会带空格或特殊字符，尝试模糊匹配
            def callback(h, extra):
                if self.window_title in win32gui.GetWindowText(h):
                    extra.append(h)
            hwnds = []
            win32gui.EnumWindows(callback, hwnds)
            if hwnds:
                hwnd = hwnds[0]
            else:
                return None

        # 获取窗口矩形坐标 (left, top, right, bottom)
        rect = win32gui.GetWindowRect(hwnd)
        x, y, w, h = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]
        return {"top": y, "left": x, "width": w, "height": h}

    def capture(self):
        """截取当前游戏窗口"""
        rect = self.get_window_rect()
        if not rect:
            print(f"错误：未找到窗口 '{self.window_title}'")
            return None

        with mss.mss() as sct:
            # 截取特定区域
            img = sct.grab(rect)
            # 转换为 OpenCV 格式 (BGRA -> BGR)
            frame = np.array(img)
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            return frame

if __name__ == "__main__":
    # --- 测试代码 ---
    capturer = ScreenCapturer("欢乐斗地主")
    
    print("请确保欢乐斗地主小程序已打开...")
    while True:
        frame = capturer.capture()
        if frame is not None:
            # 缩小显示，防止 4K 屏幕显示不下
            display_frame = cv2.resize(frame, (0, 0), fx=0.7, fy=0.7)
            cv2.imshow("Game Capture Test", display_frame)
            
        # 按 'q' 键退出预览
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cv2.destroyAllWindows()