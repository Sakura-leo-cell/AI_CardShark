import cv2
import numpy as np
import os
import ScreenCapturer as sc

class RoomDecision:
    def __init__(self):
        self.capturer = sc.ScreenCapturer("欢乐斗地主")
        print("success")
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
        
        res = cv2.matchTemplate(frame, temp, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        
        if max_val >= conf:
            return (*max_loc, temp.shape[1], temp.shape[0])
        return None


    # 通过双通道解耦实现欢乐豆读数（目前最大以万为单位）
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
        roi_digit = top_roi[iy - 5 : iy + th + 10, ix + tw - 5 : ix + tw + 130] 
        roi_gray = cv2.cvtColor(roi_digit, cv2.COLOR_BGR2GRAY)
        
        # cv2.imshow("3. Digit ROI (Crop)", roi_digit)
        # cv2.waitKey(1)

        # --- 通道一：识别数字和小数点（修复版） ---
        detected_num = []
        # 记录所有匹配结果，用于调试画框
        debug_roi = roi_digit.copy() 

        for char_key in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."]:
            temp = self.char_templates.get(char_key)
            if temp is None: continue
            
            res_char = cv2.matchTemplate(roi_gray, temp, cv2.TM_CCOEFF_NORMED)
            
            # 【优化1】统一降低阈值到 0.85，确保不漏掉渲染稍有差异的数字
            current_conf = 0.9
            
            loc = np.where(res_char >= current_conf)
            for pt in zip(*loc[::-1]):
                # 【优化2】将去重间距从 6 缩小到 4
                # 游戏字体紧凑时，4 像素是更安全的界限
                if not any(abs(pt[0] - ex) < 4 for ex, _ in detected_num):
                    detected_num.append((pt[0], char_key))
                    
                    # --- 调试代码：在小窗口画出识别到的每个字符 ---
                    tw, th = temp.shape[1], temp.shape[0]
                    cv2.rectangle(debug_roi, pt, (pt[0] + tw, pt[1] + th), (0, 255, 0), 1)
                    cv2.putText(debug_roi, char_key, (pt[0], pt[1]-2), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

        # 实时显示识别框，检查 3.383 是否每个字符都被框住了
        # cv2.imshow("4. Recognition Debug", debug_roi)
        # cv2.waitKey(1)

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