import cv2
import numpy as np
import pyautogui
import threading
import time
import os
import keyboard
import tkinter as tk
import queue
import pygetwindow as gw  # 导入窗口管理库

debug = True  # 是否开启调试模式
threshold = 0.8  # 匹配的阈值

script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录：{script_dir}")

icons = [f"{script_dir}\\cook.png", f"{script_dir}\\cook_menu.png", f"{script_dir}\\cook_start.png", f"{script_dir}\\finish.png"]

# 创建显示队列
image_queue = queue.Queue()

def show_images():
    """ 主线程显示图像窗口的逻辑，通过队列从子线程接收图像。 """
    while True:
        if not image_queue.empty():
            title, image = image_queue.get()
            if image is None:  # 退出信号q
                break
            cv2.imshow(title, image)
            cv2.waitKey(1)  # 非阻塞等待
    cv2.destroyAllWindows()

def draw_rectangle(left, top, width, height, duration=5):
    """ 绘制一个绿色矩形框在屏幕指定位置。 """
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.attributes('-transparentcolor', 'black')
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    canvas = tk.Canvas(root, width=screen_width, height=screen_height, bg='black', highlightthickness=0)
    canvas.pack()
    canvas.create_rectangle(left, top, left + width, top + height, outline="green", width=3)
    root.after(int(duration * 1000), root.destroy)
    root.mainloop()

def preprocess_image_with_mask(image_path):
    """ 读取模板图像并提取其白色区域生成掩码。 """
    template = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if template is None:
        raise ValueError(f"无法读取图片 {image_path}，请检查路径。")
    
    gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray_template, 220, 255, cv2.THRESH_BINARY)
    masked_template = cv2.bitwise_and(template, template, mask=mask)

    if debug:
        image_queue.put(("---",masked_template))


    return masked_template, mask

def get_window_screenshot(window_title):
    """ 获取特定窗口的截图。 """
    window = gw.getWindowsWithTitle(window_title)
    if not window:
        raise ValueError(f"未找到窗口标题为 '{window_title}' 的窗口。")
    
    window = window[0]  # 假设窗口标题唯一，获取第一个匹配的窗口
    left, top, width, height = window.left, window.top, window.width, window.height

    screenshot = pyautogui.screenshot(region=(left, top, width, height))
    screenshot = np.array(screenshot)
    screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2RGB)
    return screenshot

def show_screenshot(screen):
    """ 显示截图。 """
    cv2.imshow("Window Screenshot", screen)
    cv2.waitKey(0)  # 等待键盘输入来关闭窗口
    cv2.destroyAllWindows()

def match_template_orb(icon, screen, threshold, result_queue):
    """ 使用 ORB 特征进行多尺度匹配，只匹配模板中的白色部分。 """
    masked_template, mask = preprocess_image_with_mask(icon)

    orb = cv2.ORB_create(nfeatures=5000, scaleFactor=1.2, nlevels=8, edgeThreshold=31, patchSize=31)
    kp_template, des_template = orb.detectAndCompute(masked_template, mask)

    if des_template is None:
        result_queue.put(None)
        return

    # 尝试不同的缩放比例
    scales = np.arange(0.5, 1.1, 0.1).tolist()   # 可以根据实际情况调整这些缩放比例
    best_match = None
    best_match_score = float('inf')

    for scale in scales:
        scaled_template = cv2.resize(masked_template, (0, 0), fx=scale, fy=scale)
        gray_scaled_template = cv2.cvtColor(scaled_template, cv2.COLOR_BGR2GRAY)
        kp_scaled, des_scaled = orb.detectAndCompute(gray_scaled_template, None)

        if des_scaled is None:
            continue

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(des_template, des_scaled)

        if matches:
            matches = sorted(matches, key=lambda x: x.distance)
            good_matches = [m for m in matches if m.distance < 0.75 * min([match.distance for match in matches])]

            if len(good_matches) > 10:
                src_pts = np.float32([kp_template[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp_scaled[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

                matrix, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                if matrix is not None:
                    h, w = scaled_template.shape[:2]
                    corners = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
                    transformed_corners = cv2.perspectiveTransform(corners, matrix)

                    x_min = int(min(transformed_corners[:, 0, 0]))
                    y_min = int(min(transformed_corners[:, 0, 1]))
                    x_max = int(max(transformed_corners[:, 0, 0]))
                    y_max = int(max(transformed_corners[:, 0, 1]))

                    match_score = sum([m.distance for m in good_matches])

                    # 保存最佳匹配
                    if match_score < best_match_score:
                        best_match = ((x_min, y_min), (x_max - x_min, y_max - y_min))
                        best_match_score = match_score

    if best_match is not None:
        result_queue.put(best_match)
    else:
        result_queue.put(None)

def handler(window_title):
    """ 主处理逻辑：捕获特定窗口截图，执行 ORB 匹配并执行操作。 """
    try:
        screen = get_window_screenshot(window_title)
        # show_screenshot(screen)  # 显示截图
        result_queue = queue.Queue()
        threads = []
        for icon in icons:
            thread = threading.Thread(target=match_template_orb, args=(icon, screen, threshold, result_queue))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        for icon in icons:
            result = result_queue.get()
            if result:
                match_position, template_size = result
                left, top = match_position
                width, height = template_size
                button_center = (left + width // 2, top + height // 2)

                threading.Thread(target=draw_rectangle, args=(left, top, width, height, 0.5)).start()
                # pyautogui.click(button_center)
                print(f"已点击按钮 {icon}：{button_center}")
                if "cook.png" in icon:
                    time.sleep(0.5)
                else:
                    time.sleep(1.2)
                return True
            else:
                print(f"未找到按钮 {icon}。")
    except Exception as e:
        print(f"发生错误：{e}")

def main():
    """ 主函数，监听键盘退出并持续运行处理逻辑。 """
    def exit_program():
        print("检测到 'Q' 键，退出程序")
        image_queue.put((None, None))  # 发送退出信号到显示线程
        exit()

    keyboard.add_hotkey('q', exit_program)
    display_thread = threading.Thread(target=show_images, daemon=True)
    display_thread.start()

    window_title = "五五的大号"  # 替换为要匹配的窗口的标题

    while True:
        handler(window_title)
        time.sleep(0.2)
        if keyboard.is_pressed('q'):
            print("程序正在退出...")
            image_queue.put((None, None))  # 发送退出信号到显示线程
            display_thread.join()
            return

if __name__ == "__main__":
    main()
