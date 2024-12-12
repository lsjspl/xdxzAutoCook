import cv2
import pyautogui
import numpy as np
import threading
import os
import time
import keyboard
import queue

# 设置阈值和图像处理相关参数
debug = False
threshold = 0.8

# 获取脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录：{script_dir}")

# 定义图标模板目录
icons_dict = {
    "cook_menu": [f"{script_dir}\\cook_menu.png", f"{script_dir}\\cook_menu_1.png"],  # 多个 cook_menu 模板
    "cook": [f"{script_dir}\\cook.png", f"{script_dir}\\cook_1.png"],  # 多个 cook 模板
    "finish": [f"{script_dir}\\finish.png", f"{script_dir}\\finish_1.png"],  # 多个 finish 模板
    "food": [f"{script_dir}\\food.png"],  # 当前只有一个 food 模板
    "cook_start": [f"{script_dir}\\cook_start.png"],  # 只有一个 cook_start 模板
}

# 设置 food 为一个全局变量，默认使用 food.png 模板
food = "food.png"

# 创建显示队列
image_queue = queue.Queue()
lock = threading.Lock()
can_click_food = True

# 存储图标缩放比例
scale_factor = None

# 检查是否支持 CUDA
def check_cuda():
    if cv2.cuda.getCudaEnabledDeviceCount() == 0:
        print("CUDA 不可用，程序将使用 CPU。")
        return False
    else:
        print("CUDA 可用，程序将使用 GPU 加速。")
        return True

use_cuda = check_cuda()

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

# 模板匹配
def match_template(icon, gray_screen, color_screen, threshold, result_queue):
    """ 模板匹配，可能会有多个匹配 """
    global scale_factor
    try:
        # 根据 icon 类型选择是否使用彩色模板
        if icon in icons_dict["food"] or icon in icons_dict["cook_start"]:
            # 彩色模板匹配
            template = preprocess_image_color_only(icon)
            if template is None:
                result_queue.put(None)
                return

            # 检测是否已经有缩放比例
            if scale_factor is None:
                scale_factor = find_best_scale(template, color_screen)

            # 模板匹配只需要一次缩放
            resized_template = cv2.resize(template, None, fx=scale_factor, fy=scale_factor)
            result = cv2.matchTemplate(color_screen, resized_template, cv2.TM_CCOEFF_NORMED)

            # 获取匹配的所有位置
            locations = np.where(result >= threshold)
            rectangles = []
            for pt in zip(*locations[::-1]):
                rectangles.append([pt[0], pt[1], resized_template.shape[1], resized_template.shape[0]])

            # 如果没有找到匹配项，则退出
            if not rectangles:
                print(f"{icon} 没有匹配项")
                result_queue.put(None)
                return

            # 使用非极大值抑制去除重叠的框
            indices = cv2.dnn.NMSBoxes(rectangles, [threshold] * len(rectangles), score_threshold=threshold, nms_threshold=0.4)

            if indices is None or len(indices) == 0:
                print(f"没有找到有效的框索引：{icon}")
                result_queue.put(None)
                return

            # 确保我们正确处理返回的结果
            if isinstance(indices, tuple):
                indices = indices[0]  # 取出元组中的第一个元素，这就是框的索引

            # 检查是否有索引，并用 `.flatten()` 来获取索引
            if indices is not None and len(indices) > 0:
                for i in indices.flatten():
                    box = rectangles[i]
                    result_queue.put((icon, (box[0], box[1]), (box[2], box[3])))

        else:
            # 灰度模板匹配
            template, mask, masked_template = preprocess_image_gray_only(icon)
            if template is None:
                result_queue.put(None)
                return

            # 检测是否已经有缩放比例
            if scale_factor is None:
                scale_factor = find_best_scale(masked_template, gray_screen)

            # 模板匹配只需要一次缩放
            resized_template = cv2.resize(masked_template, None, fx=scale_factor, fy=scale_factor)
            result = cv2.matchTemplate(gray_screen, resized_template, cv2.TM_CCOEFF_NORMED)

            # 获取匹配的所有位置
            locations = np.where(result >= threshold)
            rectangles = []
            for pt in zip(*locations[::-1]):
                rectangles.append([pt[0], pt[1], resized_template.shape[1], resized_template.shape[0]])

            # 如果没有找到匹配项，则退出
            if not rectangles:
                print(f"{icon} 没有匹配项")
                result_queue.put(None)
                return

            # 使用非极大值抑制去除重叠的框
            indices = cv2.dnn.NMSBoxes(rectangles, [threshold] * len(rectangles), score_threshold=threshold, nms_threshold=0.4)

            if indices is None or len(indices) == 0:
                print(f"没有找到有效的框索引：{icon}")
                result_queue.put(None)
                return

            # 确保我们正确处理返回的结果
            if isinstance(indices, tuple):
                indices = indices[0]  # 取出元组中的第一个元素，这就是框的索引

            # 检查是否有索引，并用 `.flatten()` 来获取索引
            if indices is not None and len(indices) > 0:
                for i in indices.flatten():
                    box = rectangles[i]
                    result_queue.put((icon, (box[0], box[1]), (box[2], box[3])))

    except Exception as e:
        print(f"模板匹配时发生错误：{e}")
        result_queue.put(None)

# 尝试不同的缩放比例，返回最合适的比例
def find_best_scale(template, screen):
    max_similarity = 0
    best_scale = 1.0
    scales = [0.8, 0.9, 1.0, 1.1, 1.2]  # 尝试不同的缩放比例

    for scale in scales:
        resized_template = cv2.resize(template, None, fx=scale, fy=scale)
        result = cv2.matchTemplate(screen, resized_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        if max_val > max_similarity:
            max_similarity = max_val
            best_scale = scale

    print(f"最佳缩放比例: {best_scale}，相似度: {max_similarity}")
    return best_scale

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
def handle_window():
    screen = pyautogui.screenshot()
    screen = np.array(screen)
    gray_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
    gray_screen = cv2.GaussianBlur(gray_screen, (5, 5), 0)

    # 使用原始彩色屏幕用于彩色模板匹配
    color_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)

    result_queue = queue.Queue()
    threads = []

    # 为每个图标启动线程进行模板匹配
    for category, icons in icons_dict.items():
        for icon in icons:
            print(f"正在匹配图标: {icon}")
            thread = threading.Thread(target=match_template, args=(icon, gray_screen, color_screen, threshold, result_queue))
            threads.append(thread)
            thread.start()

    # 等待所有线程完成
    for thread in threads:
        thread.join()

    # 从队列中获取所有匹配结果
    results = {}
    while not result_queue.empty():
        result = result_queue.get()
        if result:
            matched_icon, match_position, template_size = result
            if matched_icon not in results:
                results[matched_icon] = []
            results[matched_icon].append((match_position, template_size))

    return results

# 主函数
def main():
    global can_click_food, food

    try:
        while True:
            results = handle_window()

            if "cook_menu.png" in results and len(results["cook_menu.png"]) == 3:
                for cook_menu_button in results["cook_menu.png"]:
                    click_button("cook_menu.png", cook_menu_button)
                    results = handle_window()
                    time.sleep(1)

                    if food in results:
                        click_button(food, results[food])
                        can_click_food = True
                        results = handle_window()

                    if "cook_start.png" in results and can_click_food:
                        click_button("cook_start.png", results["cook_start.png"])

            while "finish.png" in results and len(results["finish.png"]) < 3:
                if "cook.png" in results:
                    click_button("cook.png", results["cook.png"][0])
                    results = handle_window()
                    time.sleep(1)

            if "finish.png" in results:
                for finish_button in results["finish.png"][:3]:
                    click_button("finish.png", finish_button)
                    results = handle_window()
                    time.sleep(1)

            if keyboard.is_pressed('q'):
                print("程序正在退出...")
                break

    except Exception as e:
        print(f"程序发生错误：{e}")

# 程序入口
if __name__ == "__main__":
    main()
