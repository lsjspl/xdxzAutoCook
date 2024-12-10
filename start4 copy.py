import cv2
import pyautogui
import numpy as np
import threading
import os
import time
import keyboard
import tkinter as tk
import queue
import pygetwindow as gw

debug = False
threshold = 0.8

# 获取脚本所在的目录
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"脚本目录：{script_dir}")

icons = [f"{script_dir}\\cook.png", f"{script_dir}\\cook_menu.png", f"{script_dir}\\food.png", f"{script_dir}\\cook_start.png", f"{script_dir}\\finish.png"]

# 创建显示队列
image_queue = queue.Queue()
lock = threading.Lock()

# 检查是否支持 CUDA
def check_cuda():
    if cv2.cuda.getCudaEnabledDeviceCount() == 0:
        print("CUDA 不可用，程序将使用 CPU。")
        return False
    else:
        print("CUDA 可用，程序将使用 GPU 加速。")
        return True

use_cuda = check_cuda()

def show_images():
    """ 主线程显示图像窗口的逻辑，通过队列从子线程接收图像，并保存到文件。 """
    try:
        save_directory = os.path.join(script_dir, "test")
        os.makedirs(save_directory, exist_ok=True)

        image_index = 0
        while True:
            if not image_queue.empty():
                title, image = image_queue.get()
                if image is None:  # 退出信号
                    break

                file_path = os.path.join(save_directory, f"{title}_{image_index}.png")
                # cv2.imwrite(file_path, image)
                print(f"保存图片到: {file_path}")

                image_index += 1
    except Exception as e:
        print(f"在显示图像中发生错误：{e}")

def draw_rectangle(left, top, width, height, duration=5):
    """ 在屏幕上绘制绿色矩形框 """
    try:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        root.attributes('-transparentcolor', 'black')

        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        canvas = tk.Canvas(root, width=screen_width, height=screen_height, bg='black', highlightthickness=0)
        canvas.pack()

        x1, y1 = left, top
        x2, y2 = left + width, top + height
        canvas.create_rectangle(x1, y1, x2, y2, outline="green", width=3)

        root.after(int(duration * 1000), root.destroy)
        root.mainloop()
    except Exception as e:
        print(f"在绘制矩形时发生错误：{e}")

def preprocess_image_white_only(image_path):
    """ 处理模板图像，保留白色部分，其他部分变为黑色 """
    try:
        template = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            raise ValueError(f"无法读取图片 {image_path}，请检查路径。")

        gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray_template, 230, 255, cv2.THRESH_BINARY)
        masked_template = cv2.bitwise_and(template, template, mask=mask)
        masked_template = cv2.cvtColor(masked_template, cv2.COLOR_BGR2GRAY)
        return template, gray_template, mask, masked_template
    except Exception as e:
        print(f"预处理图像时发生错误：{e}")
        return None, None

def match_template_scaled(icon, gray_screen, threshold, result_queue):
    """ 为每个缩放比例进行模板匹配 """
    try:
        template, gray_template, mask, masked_template = preprocess_image_white_only(icon)
        if template is None:
            result_queue.put(None)
            return

        # 转换为 GPU 图像
        if use_cuda:
            gray_screen_gpu = cv2.cuda_GpuMat()
            gray_screen_gpu.upload(gray_screen)
            masked_template_gpu = cv2.cuda_GpuMat()
            masked_template_gpu.upload(masked_template)
        else:
            gray_screen_gpu = gray_screen
            masked_template_gpu = masked_template

        for scale in np.arange(0.7, 1.1, 0.1):  # 缩放范围从 70% 到 110%
            resized_template = cv2.resize(masked_template, None, fx=scale, fy=scale)

            # 将模板上传到 GPU
            if use_cuda:
                resized_template_gpu = cv2.cuda_GpuMat()
                resized_template_gpu.upload(resized_template)

                # 使用 GPU 进行模板匹配
                result_gpu = cv2.cuda.createTemplateMatching(gray_screen_gpu, cv2.TM_CCOEFF_NORMED).match(resized_template_gpu)
                result = result_gpu.download()
            else:
                result = cv2.matchTemplate(gray_screen, resized_template, cv2.TM_CCOEFF_NORMED)

            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

            if max_val >= threshold:
                result_queue.put((icon, max_loc, (resized_template.shape[1], resized_template.shape[0])))
                return
        result_queue.put(None)
    except Exception as e:
        print(f"模板匹配时发生错误：{e}")
        result_queue.put(None)

def safe_run_thread(target, *args):
    try:
        target(*args)
    except Exception as e:
        print(f"线程执行时发生错误：{e}")

def handler(window_title, can_click_food=True):
    """ 主处理逻辑，获取截图并进行模板匹配和点击 """
    try:
        print(f"开始处理窗口: {window_title}")
        screen = pyautogui.screenshot()
        screen = np.array(screen)
        if screen is None:
            print("无法获取窗口截图，跳过本次循环")
            return

        gray_screen = cv2.cvtColor(screen, cv2.COLOR_RGB2GRAY)
        gray_screen = cv2.GaussianBlur(gray_screen, (5, 5), 0)

        with lock:
            image_queue.put(("winshoot", gray_screen))

        result_queue = queue.Queue()
        threads = []

        # 为每个图标启动一个线程进行缩放匹配
        for icon in icons:
            thread = threading.Thread(target=safe_run_thread, args=(match_template_scaled, icon, gray_screen, threshold, result_queue))
            threads.append(thread)
            thread.start()

        # 等待所有线程完成
        for thread in threads:
            thread.join()

        # 处理匹配结果并点击
        results = {}
        for icon in icons:
            result = result_queue.get(timeout=5)  # 设置超时时间
            if result:
                matched_icon, match_position, template_size = result
                results[matched_icon] = (match_position, template_size)
            else:
                print(f"未找到按钮{icon}。")

        # 优先点击cook.png
        if f"{script_dir}\\cook.png" in results:
            match_position, template_size = results[f"{script_dir}\\cook.png"]
            left, top = match_position
            width, height = template_size
            threading.Thread(target=draw_rectangle, args=(left, top, width, height, 0.5)).start()

            button_center = (left + width // 2, top + height // 2)
            pyautogui.click(button_center)
            pyautogui.click(button_center)
            print(f"已点击按钮 cook.png：{button_center}")
            time.sleep(0.3)
            return True

        # 其他按钮的点击逻辑
        for icon in icons:
            if icon in results and icon != f"{script_dir}\\cook.png":  # 排除cook.png
                match_position, template_size = results[icon]
                left, top = match_position
                width, height = template_size
                threading.Thread(target=draw_rectangle, args=(left, top, width, height, 0.5)).start()

                button_center = (left + width // 2, top + height // 2)
            

                if "food.png" in icon and can_click_food:
                    time.sleep(0.5)  # 可以点击 cook_start
                    can_click_food = False  # 防止再点击 food
                    pyautogui.click(button_center)
                    pyautogui.click(button_center)
                    print(f"已点击按钮{icon}：{button_center}")
                elif "cook_start.png" in icon and not can_click_food:
                    time.sleep(0.5)  # 点击 cook_start 后继续下一次
                    can_click_food = True  # 恢复可以点击 food
                    pyautogui.click(button_center)
                    pyautogui.click(button_center)
                    print(f"已点击按钮{icon}：{button_center}")
                elif "cook_menu.png" or "finish.png" in icon:
                    pyautogui.click(button_center)
                    pyautogui.click(button_center)
                    print(f"已点击按钮{icon}：{button_center}")
                    time.sleep(1)

                
                return True

    except Exception as e:
        print(f"处理过程中发生错误：{e}")
    return False

def main():
    """ 主程序入口 """
    window_title = "五五的大号"  # 替换为要匹配的窗口的标题
    can_click_food = True  # 初始状态允许点击 food

    try:
        while True:
            handler(window_title, can_click_food)
            time.sleep(0.1)
            if keyboard.is_pressed('q'):
                print("程序正在退出...") 
                image_queue.put((None, None))  # 发送退出信号到显示线程
                return  # 优雅退出
    except Exception as e:
        print(f"程序发生错误，正在退出：{e}")
        image_queue.put((None, None))

if __name__ == "__main__":
    main()
