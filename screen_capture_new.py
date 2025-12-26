import cv2
import numpy as np
import mss
import win32gui # type: ignore
import ctypes
import pyautogui
import time
import os

# 1. 强制开启 DPI 意识，确保坐标不偏移
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()

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

class GameBot:
    def __init__(self):
        self.capturer = ScreenCapturer("欢乐斗地主")
        self.char_templates = {} 
        self.ui_templates = {}   
        self._load_assets()

    def _load_assets(self):
        # 加载数字、小数点、万字模板
        for i in range(10):
            self._add_char_temp(str(i), f"assets/{i}.png")
        self._add_char_temp(".", "assets/dot.png")
        self._add_char_temp("wan", "assets/wan.png")
        
        # 加载 UI 组件
        ui_files = {"bean": "assets/bean_icon.png", "novice": "assets/room_novice.png", 
                    "normal": "assets/room_normal.png", "advanced": "assets/room_advanced.png"}
        for key, path in ui_files.items():
            if os.path.exists(path): self.ui_templates[key] = cv2.imread(path)

    def _add_char_temp(self, key, path):
        if os.path.exists(path):
            # 以灰度模式读取数字模板，提高匹配稳定性
            self.char_templates[key] = cv2.imread(path, cv2.IMREAD_GRAYSCALE)

    def find_pos(self, frame, temp, conf=0.8, debug_name=""):
        """带调试功能的匹配函数"""
        if temp is None: return None
        
        # 【回退到彩色匹配试试】对于金色的豆子，彩色匹配通常比灰度更准
        # 如果你的模板是彩色的，这里用彩色匹配
        res = cv2.matchTemplate(frame, temp, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        # --- 调试核心 ---
        if debug_name:
            print(f"[{debug_name}] 最高匹配度: {max_val:.4f} (阈值: {conf})")
            # 在画面上画出程序认为最像的位置（红框）
            debug_img = frame.copy()
            h, w = temp.shape[:2]
            cv2.rectangle(debug_img, max_loc, (max_loc[0]+w, max_loc[1]+h), (0, 0, 255), 3)
            cv2.putText(debug_img, f"{max_val:.2f}", max_loc, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
            # 弹窗显示程序“看”到的结果
            cv2.imshow(f"Debug: {debug_name}", cv2.resize(debug_img, (0,0), fx=0.6, fy=0.6))
            cv2.waitKey(1) 
        # ----------------
        
        if max_val >= conf:
            return (*max_loc, temp.shape[1], temp.shape[0])
        return None

    def get_bean_count(self, frame):
        """双通道识别版：分别识别数值和单位"""
        h, w = frame.shape[:2]
        
        # 1. 划定搜索区域（Top-ROI）
        roi_h = int(h * 0.18)
        top_roi = frame[0:roi_h, :]
        
        temp_bean = self.ui_templates.get("bean")
        if temp_bean is None: return None

        res = cv2.matchTemplate(top_roi, temp_bean, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        
        if max_val < 0.75: return None

        # 2. 确定识别区域 (ROI)
        ix, iy = max_loc
        th, tw = temp_bean.shape[:2]
        # 宽度拉长到 240，确保即使数字很长也能包含“万”字
        roi_digit = top_roi[iy - 5 : iy + th + 10, ix + tw - 5 : ix + tw + 240] 
        roi_gray = cv2.cvtColor(roi_digit, cv2.COLOR_BGR2GRAY)
        
        cv2.imshow("3. Digit ROI (Crop)", roi_digit)
        cv2.waitKey(1)

        # --- 通道一：识别数字和小数点 ---
        detected_num = []
        for char_key in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."]:
            temp = self.char_templates.get(char_key)
            if temp is None: continue
            
            res_char = cv2.matchTemplate(roi_gray, temp, cv2.TM_CCOEFF_NORMED)
            # 针对性阈值：数字 0.9，小数点 0.85（放宽以抓取微小特征）
            current_conf = 0.85 if char_key == "." else 0.9
            
            loc = np.where(res_char >= current_conf)
            for pt in zip(*loc[::-1]):
                # 间距缩小到 6，防止小数点被误删
                if not any(abs(pt[0] - ex) < 6 for ex, _ in detected_num):
                    detected_num.append((pt[0], char_key))
        
        detected_num.sort(key=lambda x: x[0])
        
        # --- 通道二：专门识别“万”字 ---
        is_wan = False
        temp_wan = self.char_templates.get("wan")
        if temp_wan is not None:
            res_wan = cv2.matchTemplate(roi_gray, temp_wan, cv2.TM_CCOEFF_NORMED)
            _, max_wan_val, _, _ = cv2.minMaxLoc(res_wan)
            # 万字识别阈值设为 0.8，增加包容度
            if max_wan_val >= 0.8:
                is_wan = True

        # --- 第三阶段：数据聚合 ---
        if not detected_num: return None
        
        res_str = ""
        dot_count = 0
        for _, char in detected_num:
            if char == ".":
                # 逻辑过滤：确保只取第一个合法的小数点
                if dot_count == 0 and len(res_str) > 0:
                    res_str += char
                    dot_count += 1
            else:
                res_str += char 

        try:
            res_str = res_str.strip('.') # 清洗末尾可能的噪音点
            if not res_str: return None
            
            val = float(res_str)
            if is_wan: val *= 10000 
            
            print(f"通道1(数值): {res_str} | 通道2(万字): {'有' if is_wan else '无'} -> 结果: {int(val)}")
            return int(val)
        except Exception as e:
            print(f"解析失败: {res_str}, 错误: {e}")
            return None

    def run(self):
        print("Bot 启动，监控中...")
        while True:
            frame, rect = self.capturer.capture()
            if frame is None:
                print("等待中：未找到游戏窗口...")
                time.sleep(2); continue

            beans = self.get_bean_count(frame)

            if beans is None:
                # 若找不到豆子，显示主视图调试
                # cv2.imshow("Main View", cv2.resize(frame, (0, 0), fx=0.4, fy=0.4))
                cv2.waitKey(1)
            else:
                target = "novice"
                if beans >= 50000: target = "advanced"
                elif beans >= 10000: target = "normal"
                
                print(f"当前豆子: {beans}, 目标: {target}")
                pos = self.find_pos(frame, self.ui_templates.get(target), conf=0.8)
                if pos:
                    sx = rect["left"] + pos[0] + pos[2]//2
                    sy = rect["top"] + pos[1] + pos[3]//2
                    pyautogui.click(sx, sy)
                    print(f"成功进入【{target}】场次！")
                    break
            
            time.sleep(1.0)

if __name__ == "__main__":
    bot = GameBot()
    bot.run()