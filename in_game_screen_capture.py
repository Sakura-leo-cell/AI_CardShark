import cv2
import numpy as np

class HandCardRecognizer:
    def __init__(self, templates):
        """
        :param templates: 字典, {'3': img, '4': img, ..., 'DX': img, 'XX': img}
                          建议模板只包含卡牌左上角的数字+小花色，宽约30px，高约40px
        """
        self.templates = templates
        # 匹配阈值：数字通常很清晰，阈值可以设高一点以防误判
        self.threshold = 0.88 
        
        # 定义手牌区域 (ROI) 在全屏中的相对比例
        # 基于你的截图：牌大约在垂直方向 70%~95% 的位置，水平方向 5%~95%
        self.roi_top_ratio = 0.65  # 稍微高一点，覆盖弹起的牌
        self.roi_bottom_ratio = 0.95
        self.roi_left_ratio = 0.02
        self.roi_right_ratio = 0.98

    def process_hand(self, frame):
        """
        核心函数：传入全屏截图，返回识别到的手牌列表（从左到右）
        """
        if frame is None: return []

        # 1. 裁剪 ROI (Region of Interest)
        h, w = frame.shape[:2]
        y1, y2 = int(h * self.roi_top_ratio), int(h * self.roi_bottom_ratio)
        x1, x2 = int(w * self.roi_left_ratio), int(w * self.roi_right_ratio)
        
        hand_roi = frame[y1:y2, x1:x2]
        # 转灰度，减少计算量，且对颜色不敏感（除非区分大小王）
        hand_gray = cv2.cvtColor(hand_roi, cv2.COLOR_BGR2GRAY)

        # 调试：显示ROI区域，确保没切歪 (运行时可注释掉)
        # cv2.imshow("Hand ROI", hand_gray)

        all_detections = []

        # 2. 遍历所有模板进行匹配
        for card_name, template in self.templates.items():
            # 确保模板也是灰度
            if len(template.shape) == 3:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            # 模板匹配
            res = cv2.matchTemplate(hand_gray, template, cv2.TM_CCOEFF_NORMED)
            locs = np.where(res >= self.threshold)
            
            # 收集所有符合的点
            for pt in zip(*locs[::-1]): # pt is (x, y)
                score = res[pt[1]][pt[0]]
                all_detections.append({
                    'name': card_name,
                    'x': pt[0],
                    'y': pt[1],
                    'score': score
                })

        # 3. 空间去重 (Non-Maximum Suppression 的简化版)
        # 只要两个识别结果距离太近 (比如小于15像素)，就认为是同一张牌，保留分高的
        unique_cards = self._nms_deduplicate(all_detections, dist_threshold=15)

        # 4. 排序：按 X 坐标从左到右排序
        unique_cards.sort(key=lambda c: c['x'])

        # 5. 返回结果列表
        result_names = [c['name'] for c in unique_cards]
        
        # 调试输出
        # print(f"Raw Detections: {len(all_detections)} -> Unique: {len(result_names)}")
        return result_names

    def _nms_deduplicate(self, detections, dist_threshold):
        """
        去重逻辑：优先保留高置信度的结果
        """
        if not detections: return []
        
        # 按分数从高到低排序
        detections.sort(key=lambda x: x['score'], reverse=True)
        
        final_cards = []
        for det in detections:
            is_new = True
            for exist in final_cards:
                # 计算水平距离 (手牌主要看水平重叠)
                if abs(det['x'] - exist['x']) < dist_threshold:
                    is_new = False
                    break
            
            if is_new:
                final_cards.append(det)
                
        return final_cards

# --- 集成示例 ---
# 假设你已经有了 GameBot 类
# 在 GameBot 初始化时：
# self.card_recognizer = HandCardRecognizer(self.card_templates)

# 在主循环中：
# current_hand = self.card_recognizer.process_hand(frame)
# print(f"当前手牌: {current_hand}")