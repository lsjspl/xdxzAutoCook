import cv2
import pyautogui
import numpy as np
import threading  # 导入线程模块
import os
import time
import keyboard  # 导入keyboard库
import tkinter as tk
import queue  # 用于线程安全的队列

debug = False
threshold = 0.8  # 设置匹配的阈值

# 获取脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录：{script_dir}")

icons = [f"{script_dir}\\cook.png",f"{script_dir}\\cook_menu.png", f"{script_dir}\\cook_start.png",  f"{script_dir}\\finish.png"]

def draw_rectangle(left, top, width, height, duration=5):
    # 创建一个全屏透明窗口
    root = tk.Tk()
    root.overrideredirect(True)  # 去掉窗口边框
    root.attributes('-topmost', True)  # 窗口置顶
    root.attributes('-transparentcolor', 'black')  # 设置透明背景

    # 设置窗口大小为屏幕大小
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    canvas = tk.Canvas(root, width=screen_width, height=screen_height, bg='black', highlightthickness=0)
    canvas.pack()

    # 绘制绿色矩形框
    x1, y1 = left, top
    x2, y2 = left + width, top + height
    canvas.create_rectangle(x1, y1, x2, y2, outline="green", width=3)

    # 在指定时间后关闭窗口
    root.after(int(duration * 1000), root.destroy)

    # 启动 tkinter 主循环（在主线程中运行）
    root.mainloop()

def preprocess_image(image_path):
    # 读取模板图片
    template = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        raise ValueError(f"无法读取图片 {image_path}，请检查路径。")

    # 将模板转换为灰度图并应用高斯模糊
    gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    return template, gray_template

def show_match_result(screen, template, match_position, template_size):
    """
    在屏幕截图上绘制矩形框并显示匹配结果。
    
    Parameters:
    - screen (ndarray): 屏幕截图图像。
    - template (ndarray): 模板图像。
    - match_position (tuple): 匹配位置的左上角坐标 (x, y)。
    - template_size (tuple): 模板图像的大小 (宽度, 高度)。
    """
    left, top = match_position
    width, height = template_size

    # 在匹配的屏幕截图上绘制矩形框
    bottom_right = (left + width, top + height)
    cv2.rectangle(screen, (left, top), bottom_right, (0, 255, 0), 2)

    # 显示匹配的屏幕截图和模板
    cv2.imshow("Matched Screen", screen)
    cv2.imshow("Template", template)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def match_template_scaled(icon, gray_screen, threshold, result_queue):
    """
    为每个缩放比例进行模板匹配，并返回匹配结果。
    
    Parameters:
    - icon (str): 图标文件路径。
    - gray_screen (ndarray): 截图的灰度图。
    - threshold (float): 匹配的阈值。
    
    Returns:
    - tuple: 如果匹配成功，返回左上角位置、宽高和模板，其他返回None。
    """
    template, gray_template = preprocess_image(icon)
    
    # 为每个缩放比例进行模板匹配
    for scale in np.arange(0.8, 1.1, 0.1):  # 缩放范围从 80% 到 130%
        resized_template = cv2.resize(gray_template, None, fx=scale, fy=scale)
        h, w = resized_template.shape

        # 模板匹配
        result = cv2.matchTemplate(gray_screen, resized_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            result_queue.put((max_loc, (w, h), template))  # 将匹配结果放入队列
            return
    result_queue.put(None)  # 如果没有找到匹配结果，放入 None

def handler():
    try:
        # 截取屏幕截图
        screen = pyautogui.screenshot()
        screen = np.array(screen)  # 将 PIL 图像转换为 NumPy 数组
        screen = cv2.cvtColor(screen, cv2.COLOR_BGR2RGB)  # 转换为 RGB

        # 转换为灰度图以匹配模板
        gray_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
        gray_screen = cv2.GaussianBlur(gray_screen, (5, 5), 0)  # 高斯模糊减少噪声

        # 创建一个线程安全的队列来存储结果
        result_queue = queue.Queue()
        threads = []

        # 为每个图标启动一个线程进行缩放匹配
        for icon in icons:
            thread = threading.Thread(target=match_template_scaled, args=(icon, gray_screen, threshold, result_queue))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 处理结果
        for icon in icons:
            result = result_queue.get()  # 从队列中取出匹配结果
            if result:
                match_position, template_size, template = result
                left, top = match_position
                width, height = template_size
                print(f"找到按钮{icon}位置：{match_position}")

                if debug:
                    show_match_result(screen, template, (left, top), (width, height))
                threading.Thread(target=draw_rectangle, args=(left, top, width, height, 1)).start()

                # 获取按钮的中心点
                button_center = (left + width // 2, top + height // 2)

                # 点击按钮
                pyautogui.click(button_center)
                print(f"已点击按钮{icon}：{button_center}")
                time.sleep(0.3)
                return
            else:
                print(f"未找到按钮{icon}。")
                
    except Exception as e:
        print(f"发生错误：{e}")

def main():
    # 设置键盘监听器来监听 'Q' 键
    def exit_program():
        print("检测到 'Q' 键，退出程序")
        exit()  # 退出程序

    keyboard.add_hotkey('q', exit_program)  # 绑定 'Q' 键触发退出程序

    while True:
        handler()
        time.sleep(0.1)
        if keyboard.is_pressed('q'):
            print("程序正在退出...")
            break  # 退出主循环


if __name__ == "__main__":
    main()
