import cv2
import numpy as np
import os
# 确保 in_game_screen_capture.py 在同一个文件夹
from in_game_screen_capture import HandCardRecognizer 

def cv_imread(file_path):
    """
    专门解决 OpenCV 读取中文路径失败的问题
    """
    try:
        # 使用 numpy 读取文件流，再解码，完美避开路径编码问题
        cv_img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), -1)
        return cv_img
    except Exception as e:
        print(f"读取图片出错: {e}")
        return None

def get_temp_templates(img):
    """
    从你的截图中切出临时模板 (2, A, Q, J, 10, 7)
    """
    templates = {}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 坐标基于你的截图布局
    # 格式: [y_start:y_end, x_start:x_end]
    templates['2'] = gray[462:522, 60:95]
    templates['A'] = gray[462:522, 145:180]
    templates['Q'] = gray[462:522, 317:352]
    templates['J'] = gray[462:522, 445:480]
    templates['10'] = gray[462:522, 575:620]
    templates['7'] = gray[462:522, 703:738]
    
    print("✅ 已从截图中生成临时模板: 2, A, Q, J, 10, 7")
    return templates

def main():
    # --- 1. 设置绝对路径 (已修改为 .png) ---
    image_path = r"C:\Users\ASUS\Desktop\cardshark\屏幕截图 2025-12-26 215717.png"
    
    print(f"正在尝试读取: {image_path}")

    # 2. 检查文件是否存在
    if not os.path.exists(image_path):
        print(f"❌ 错误：文件不存在！请确认文件名是否完全正确（包括空格）。")
        return

    # 3. 读取图片
    frame = cv_imread(image_path)
    
    if frame is None:
        print(f"❌ 错误：图片读取失败，可能是文件损坏或格式不支持。")
        return

    # 4. 准备模板
    templates = get_temp_templates(frame)

    # 5. 初始化识别器
    recognizer = HandCardRecognizer(templates)

    # 6. 执行识别
    print("正在识别手牌...")
    results = recognizer.process_hand(frame)

    # 7. 输出结果
    print("=" * 40)
    print(f"识别结果: {results}")
    print(f"识别数量: {len(results)}")
    print("=" * 40)
    
    # 8. 可视化验证
    cv2.imshow("Test Image (Press any key to exit)", cv2.resize(frame, (0, 0), fx=0.8, fy=0.8))
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()