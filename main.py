import ScreenCapturer as sc
import RoomDecision as rd
import cv2
import time
import pyautogui
import numpy as np
import win32gui # type: ignore
import ctypes

bot = rd.RoomDecision()

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

print("启动，监控中...")
while True:
    frame, rect = bot.capturer.capture()
    if frame is None:
        print("等待中：未找到游戏窗口...")
        time.sleep(2); continue

    beans = bot.get_bean_count(frame)

    if beans is None:
        # 若找不到豆子，显示主视图调试
        # cv2.imshow("Main View", cv2.resize(frame, (0, 0), fx=0.4, fy=0.4))
        # cv2.waitKey(1)
        continue
    else:
        target = "novice"
        if beans >= 50000: target = "advanced"
        elif beans >= 10000: target = "normal"
        
        print(f"当前豆子: {beans}, 目标: {target}")
        pos = bot.find_pos(frame, bot.ui_templates.get(target), conf=0.8)
        if pos:
            sx = rect["left"] + pos[0] + pos[2]//2
            sy = rect["top"] + pos[1] + pos[3]//2
            pyautogui.click(sx, sy)
            print(f"成功进入【{target}】场次！")
            break
    
    time.sleep(1.0)