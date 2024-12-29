import cv2
import numpy as np
import pyautogui
import time

def find_cook_menu_buttons():
    # 截取整个屏幕
    screenshot = pyautogui.screenshot()
    screenshot = np.array(screenshot)
    # 转换颜色空间从RGB到BGR(OpenCV使用BGR)
    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR)
    
    # 加载模板图像
    template = cv2.imread('./btns/cook_menu.png')
    
    if template is None:
        raise FileNotFoundError("请确保cook_menu_template.png文件存在")
    
    # 获取模板尺寸
    w, h = template.shape[1], template.shape[0]
    
    # 创建一个结果图像用于显示
    result_image = screenshot.copy()
    
    # 执行模板匹配
    # 使用TM_CCOEFF_NORMED方法，这是一种归一化的相关系数匹配方法
    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    
    # 设置阈值
    threshold = 0.8
    locations = np.where(result >= threshold)
    locations = list(zip(*locations[::-1]))
    
    found_buttons = []
    
    # 在结果图像上标记找到的位置
    for loc in locations:
        # 存储找到的按钮位置
        found_buttons.append({
            'position': (loc[0] + w//2, loc[1] + h//2),  # 按钮中心位置
            'confidence': result[loc[1], loc[0]]  # 匹配度
        })
        
        # 在图像上画矩形
        top_left = loc
        bottom_right = (loc[0] + w, loc[1] + h)
        cv2.rectangle(result_image, top_left, bottom_right, (0, 255, 0), 2)
        
        # 显示匹配度
        cv2.putText(result_image, 
                   f'{result[loc[1], loc[0]]:.2f}', 
                   (loc[0], loc[1] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, 
                   (0, 255, 0), 
                   2)
    
    # 显示结果
    cv2.imshow('Found Cook Menu Buttons', result_image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    return found_buttons

def main():
    try:
        print("开始查找cook_menu按钮...")
        buttons = find_cook_menu_buttons()
        print(f"找到 {len(buttons)} 个按钮")
        for i, button in enumerate(buttons, 1):
            print(f"按钮 {i}:")
            print(f"  位置: {button['position']}")
            print(f"  匹配度: {button['confidence']:.2f}")
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
