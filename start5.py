import cv2
import pyautogui
import numpy as np
import threading
import os
import time
import keyboard
import queue
from concurrent.futures import ThreadPoolExecutor

# 设置阈值和图像处理相关参数
debug = True  # 开启调试模式
threshold = 0.8  # 降低阈值，使匹配更宽松

# 获取脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录：{script_dir}")

# 设置 food 为一个全局变量，默认使用 food.png 模板
food = "food.png"

# 定义图标模板目录
icons_dict = {
    "cook_menu": [os.path.join(script_dir, "cook_menu.png"), os.path.join(script_dir, "cook_menu_1.png")],
    "cook": [os.path.join(script_dir, "cook.png"), os.path.join(script_dir, "cook_1.png")],
    "finish": [os.path.join(script_dir, "finish.png"), os.path.join(script_dir, "finish_1.png")],
    "food": [os.path.join(script_dir, food)],
    "cook_start": [os.path.join(script_dir, "cook_start.png")],
}

# 预处理模板图像（仅适用于灰度图像）
def preprocess_image_gray_only(image_path):
    """ 处理模板图像，保留白色部分，其他部分变为黑色 """
    try:
        template = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise ValueError(f"无法读取图片 {image_path}，请检查路径。")

        _, mask = cv2.threshold(template, 240, 255, cv2.THRESH_BINARY)
        masked_template = cv2.bitwise_and(template, template, mask=mask)

        return template, mask, masked_template
    except Exception as e:
        print(f"预处理灰度图像时发生错误：{e}")
        return None, None, None

# 预处理彩色模板图像
def preprocess_image_color_only(image_path):
    """ 处理彩色模板图像 """
    try:
        template = cv2.imread(image_path)
        if template is None:
            raise ValueError(f"无法读取图片 {image_path}，请检查路径。")
        return template
    except Exception as e:
        print(f"预处理彩色图像时发生错误：{e}")
        return None

# 计算缩放比例
def calculate_scale_factor(icon):
    """
    计算当前图标与屏幕上实际图标的缩放比例
    返回: (scale_factor, confidence)
    """
    try:
        # 截取屏幕并转换为灰度图像
        screen = pyautogui.screenshot()
        screen = np.array(screen)
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
        color_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

        # 根据图标类型选择处理方式
        if icon in icons_dict["food"] or icon in icons_dict["cook_start"]:
            template = preprocess_image_color_only(icon)
            if template is None:
                return 1.0, 0.0
            
            screen_img = color_screen
        else:
            template, mask, masked_template = preprocess_image_gray_only(icon)
            if template is None:
                return 1.0, 0.0
            
            screen_img = gray_screen
            template = masked_template

        # 多尺度模板匹配
        scale_factors = np.linspace(0.5, 2.0, 30)  # 从0.5到2.0测试30个不同的缩放比例
        best_scale = 1.0
        best_confidence = 0.0

        for scale in scale_factors:
            # 调整模板大小
            resized_template = cv2.resize(template, None, fx=scale, fy=scale)
            
            # 模板匹配
            result = cv2.matchTemplate(screen_img, resized_template, cv2.TM_CCOEFF_NORMED)
            confidence = np.max(result)

            # 更新最佳匹配
            if confidence > best_confidence:
                best_confidence = confidence
                best_scale = scale

        print(f"图标 {os.path.basename(icon)} - 最佳缩放比例: {best_scale:.2f}, 置信度: {best_confidence:.2f}")

        # 如信度太低，返回默认值
        if best_confidence < threshold:
            print(f"警告: 图标 {os.path.basename(icon)} 匹配置信度过低")
            return 1.0, 0.0

        return best_scale, best_confidence

    except Exception as e:
        print(f"计算缩放比例时发生错误：{e}")
        return 1.0, 0.0

def get_optimal_scale_factor():
    """
    获取所有模板的最优缩放比例
    """
    scale_results = []
    
    # 测试所有模板
    for category, icons in icons_dict.items():
        for icon in icons:
            scale, confidence = calculate_scale_factor(icon)
            if confidence > threshold:
                scale_results.append((scale, confidence))
    
    if not scale_results:
        print("警告: 未能找到有效的缩放比例，使用默认值 1.0")
        return 1.0
    
    # 使用置信度作为权重计算加权平均缩放比例
    total_weight = sum(conf for _, conf in scale_results)
    weighted_scale = sum(scale * conf for scale, conf in scale_results) / total_weight
    
    print(f"最终计算的加权平均缩放比例: {weighted_scale:.2f}")
    return weighted_scale

# 模板匹配
def match_template(icon, gray_screen, color_screen, threshold, result_queue, scale_factor):
    try:
        # 根据 icon 类型选择是否使用彩色模板
        if icon in icons_dict["food"] or icon in icons_dict["cook_start"]:
            template = preprocess_image_color_only(icon)
            if template is None:
                print(f"无法加载模板图像: {icon}")
                result_queue.put(None)
                return

            resized_template = cv2.resize(template, None, fx=scale_factor, fy=scale_factor)
            result = cv2.matchTemplate(color_screen, resized_template, cv2.TM_CCOEFF_NORMED)
            screen_img = color_screen
        else:
            template, mask, masked_template = preprocess_image_gray_only(icon)
            if template is None:
                print(f"无法加载模板图像: {icon}")
                result_queue.put(None)
                return

            resized_template = cv2.resize(masked_template, None, fx=scale_factor, fy=scale_factor)
            result = cv2.matchTemplate(gray_screen, resized_template, cv2.TM_CCOEFF_NORMED)
            screen_img = gray_screen

        # 获取匹配结果
        locations = np.where(result >= threshold)
        rectangles = []
        for pt in zip(*locations[::-1]):
            rectangles.append([int(pt[0]), int(pt[1]), 
                             int(resized_template.shape[1]), 
                             int(resized_template.shape[0])])

        if debug:
            print(f"图标 {os.path.basename(icon)} 检测到 {len(rectangles)} 个匹配位置")
            if len(rectangles) > 0:
                print(f"最高匹配度: {np.max(result):.3f}")

        # 应用非最大值抑制
        if len(rectangles) > 0:
            rectangles = np.array(rectangles)
            weights = np.ones((len(rectangles), 1))
            rectangles = np.hstack((rectangles, weights))
            pick = non_max_suppression(rectangles, 0.3)
            
            if debug:
                print(f"非最大值抑制后剩余 {len(pick)} 个匹配位置")

            # 返回过滤后的结果
            for (x, y, w, h, _) in pick:
                result_queue.put((icon, (int(x), int(y)), (int(w), int(h))))

    except Exception as e:
        print(f"模板匹配时发生错误：{e}")
        result_queue.put(None)

def non_max_suppression(boxes, overlapThresh):
    """非最大值抑制函数"""
    if len(boxes) == 0:
        return []

    # 初始化选择的索引列表
    pick = []

    # 获取坐标
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = x1 + boxes[:, 2]
    y2 = y1 + boxes[:, 3]

    # 计算面积
    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        # 找到相交区域
        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

        # 计算重叠区域
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        overlap = (w * h) / area[idxs[:last]]

        # 删除重叠过大的框
        idxs = np.delete(idxs, np.concatenate(([last],
            np.where(overlap > overlapThresh)[0])))

    return boxes[pick]

# 点击按钮
def click_button(icon, result):
    match_position, template_size = result
    left, top = match_position
    width, height = template_size
    button_center = (left + width // 2, top + height // 2)
    pyautogui.click(button_center)
    print(f"已点击按钮 {icon}：{button_center}")
    time.sleep(1)

# 处理窗口截图，检测按钮并按顺序点击
def handle_window(scale_factor, executor=None):
    try:
        screen = pyautogui.screenshot()
        screen = np.array(screen)
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
        gray_screen = cv2.GaussianBlur(gray_screen, (5, 5), 0)
        color_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

        if debug:
            print("\n开始新一轮按钮检测...")
            print(f"屏幕尺寸: {screen.shape}")
            print(f"当前缩放比例: {scale_factor}")

        result_queue = queue.Queue()
        futures = []

        for category, icons in icons_dict.items():
            for icon in icons:
                if executor:
                    futures.append(
                        executor.submit(match_template, icon, gray_screen, color_screen, threshold, result_queue, scale_factor)
                    )
                else:
                    match_template(icon, gray_screen, color_screen, threshold, result_queue, scale_factor)

        if executor:
            for future in futures:
                future.result()

        results = {}
        while not result_queue.empty():
            result = result_queue.get()
            if result:
                matched_icon, match_position, template_size = result
                base_name = os.path.basename(matched_icon)
                base_name = base_name.split('_')[0] + '.png'
                if base_name not in results:
                    results[base_name] = []
                results[base_name].append((match_position, template_size))

        if debug:
            print(f"检测结果: {', '.join([f'{k}: {len(v)}个' for k, v in results.items()])}")

        return results

    except Exception as e:
        print(f"处理窗口截图时发生错误：{e}")
        return {}

def wait_for_button(executor, scale_factor, button_name, count=1, timeout=30):
    """通用的按钮等待函数"""
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            return None
        
        results = handle_window(scale_factor, executor)
        if button_name in results and len(results[button_name]) >= count:
            return results[button_name]
        
        time.sleep(0.5)

# 主函数
def main():
    # 计算最优缩放比例
    scale_factor = get_optimal_scale_factor()
    print(f"使用的缩放比例: {scale_factor}")

    try:
        with ThreadPoolExecutor() as executor:
            while True:
                try:
                    # 检测初始状态
                    results = handle_window(scale_factor, executor)
                    
                    # 输出检测到的 cook_menu 按钮数量
                    cook_menu_count = len(results.get("cook_menu.png", []))
                    print(f"当前检测到 {cook_menu_count} 个 cook_menu 按钮")
                    
                    # 检查是否有3个cook_menu按钮
                    if "cook_menu.png" in results and len(results["cook_menu.png"]) == 3:
                        print("检测到3个cook_menu按钮��开始处理...")
                        # 等待3个cook_menu按钮
                        cook_menu_buttons = wait_for_button(executor, scale_factor, "cook_menu.png", count=3, timeout=30)
                        if not cook_menu_buttons:
                            print("检测到足够的cook_menu按钮")
                            continue

                        # 处理每个cook_menu按钮
                        for i in range(3):
                            # 重新检测cook_menu位置
                            cook_menu_buttons = wait_for_button(executor, scale_factor, "cook_menu.png", count=3-i)
                            if not cook_menu_buttons:
                                continue

                            click_button("cook_menu.png", cook_menu_buttons[0])
                            
                            # 等待food按钮
                            food_button = wait_for_button(executor, scale_factor, os.path.basename(food))
                            if food_button:
                                click_button(os.path.basename(food), food_button[0])
                                
                                # 等待cook_start按钮
                                cook_start_button = wait_for_button(executor, scale_factor, "cook_start.png")
                                if cook_start_button:
                                    click_button("cook_start.png", cook_start_button[0])

                        # 等待并处理finish按钮
                        while True:
                            cook_button = wait_for_button(executor, scale_factor, "cook.png")
                            if cook_button:
                                click_button("cook.png", cook_button[0])

                            finish_buttons = wait_for_button(executor, scale_factor, "finish.png", count=3, timeout=5)
                            if finish_buttons:
                                for finish_button in finish_buttons[:3]:
                                    click_button("finish.png", finish_button)
                                break

                            time.sleep(0.5)

                    time.sleep(1)  # 添加延时避免输出太快

                    if keyboard.is_pressed('q'):
                        print("程序正在退出...")
                        break

                except Exception as e:
                    print(f"循环中发生错误：{e}")
                    time.sleep(1)
                    continue

    except Exception as e:
        print(f"程序出现错误：{e}")
    finally:
        cv2.destroyAllWindows()

# 执行主程序
if __name__ == "__main__":
    main()
