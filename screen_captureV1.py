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
            """深度调试版：识别欢乐豆数量"""
            h, w = frame.shape[:2]
            
            # 1. 划定搜索区域（Top-ROI）：只看屏幕顶部 25% 的区域
            roi_h = int(h * 0.20)
            top_roi = frame[0:roi_h, :]
            
            # --- 可视化调试：显示绿色搜索框 ---
            debug_search = frame.copy()
            cv2.rectangle(debug_search, (0, 0), (w, roi_h), (0, 255, 0), 2)
            cv2.putText(debug_search, "Search Area", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("1. Search Area (Green Box)", cv2.resize(debug_search, (0, 0), fx=0.6, fy=0.6))
            # ----------------------------

            # 2. 寻找豆子图标，降低阈值到 0.7 提高容错性
            # 注意：此处直接在函数内做匹配以便输出 max_val 调试
            temp_bean = self.ui_templates.get("bean")
            if temp_bean is None:
                print("错误：未加载 bean_icon.png 模板")
                return None

            res = cv2.matchTemplate(top_roi, temp_bean, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
            
            # --- 可视化调试：显示红框匹配点 ---
            debug_match = top_roi.copy()
            th, tw = temp_bean.shape[:2]
            cv2.rectangle(debug_match, max_loc, (max_loc[0] + tw, max_loc[1] + th), (0, 0, 255), 2)
            cv2.putText(debug_match, f"Match: {max_val:.2f}", (max_loc[0], max_loc[1] - 10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("2. Best Match (Red Box)", debug_match)
            # ----------------------------

            if max_val < 0.7:  # 如果最高匹配度连 0.7 都不到，说明模板彻底不匹配
                print(f"警告：未找到豆子图标，最高匹配度仅为: {max_val:.4f}")
                return None

            # 3. 确定数字区域 (ROI)：在豆子图标右侧
            ix, iy = max_loc
            # 增加宽度到 240，确保能装下“1.65万”所有字符
            roi_digit = top_roi[iy - 5 : iy + th + 10, ix + tw - 2 : ix + tw + 150]
            roi_gray = cv2.cvtColor(roi_digit, cv2.COLOR_BGR2GRAY)
            
            # 调试预览：确保这个小窗口里能看到完整的“数字+万”
            cv2.imshow("3. Digit ROI (Crop)", roi_digit)
            cv2.waitKey(1)

            detected = []
            # 4. 匹配所有数字、点、万字
            for char_key, temp in self.char_templates.items():
                res_char = cv2.matchTemplate(roi_gray, temp, cv2.TM_CCOEFF_NORMED)
                # 阈值设为 0.85，兼顾准确与召回
                loc = np.where(res_char >= 0.85)
                for pt in zip(*loc[::-1]):
                    # 减小去重间距到 2 像素，防止数字拥挤
                    if not any(abs(pt[0] - ex) < 8 for ex, _ in detected):
                        detected.append((pt[0], char_key))
            
            # 5. 物理位置排序（从左到右）
            detected.sort(key=lambda x: x[0])
            
            if not detected: return None
            
            res_str = ""
            is_wan = False
            dot_count = 0

            for _, char in detected:
                if char == "wan": 
                    is_wan = True
                elif char == ".":
                    # 只允许出现一个小数点，且小数点不能在开头（干扰点过滤）
                    if dot_count == 0 and len(res_str) > 0:
                        res_str += char
                        dot_count += 1
                else:
                    res_str += char 
            
            try:
                # 去除末尾可能误识别的干扰点
                res_str = res_str.strip('.')
                if not res_str: return None
                
                val = float(res_str)
                if is_wan: val *= 10000 
                print(f"识别结果: {res_str}{'万' if is_wan else ''} -> 数值: {int(val)}")
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
