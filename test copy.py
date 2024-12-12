import cv2
import pyautogui
import numpy as np
import os
import time
import tkinter as tk
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# 配置日志
logging.basicConfig(
    level=logging.INFO,  # 改为INFO级别减少输出
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('template_matching.log')
    ]
)
logger = logging.getLogger(__name__)

def preprocess_image(image):
    """预处理图像，使用更高效的方法"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # 使用位运算合并多个掩码
    mask = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 40, 255])) | \
           cv2.inRange(hsv, np.array([0, 0, 80]), np.array([180, 50, 200]))
    
    # 直接处理灰度图
    gray = cv2.cvtColor(cv2.bitwise_and(image, image, mask=mask), cv2.COLOR_BGR2GRAY)
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                               cv2.THRESH_BINARY, 15, 5)

def process_scale(screen_processed, template_processed, scale, threshold):
    """处理单个缩放比例的匹配"""
    width = int(template_processed.shape[1] * scale)
    height = int(template_processed.shape[0] * scale)
    resized_template = cv2.resize(template_processed, (width, height))
    
    result = cv2.matchTemplate(screen_processed, resized_template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)
    
    matches = []
    for pt in zip(*locations[::-1]):
        matches.append([pt[0], pt[1], width, height, result[pt[1], pt[0]]])
    
    return matches

class OverlayWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Overlay")
        self.root.attributes('-alpha', 0.3, '-topmost', True, 
                           '-fullscreen', True, '-transparentcolor', 'black')
        
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg='black')
        self.canvas.pack(fill='both', expand=True)
        self.root.bind('<Escape>', lambda e: self.root.quit())
        self.current_rectangles = []

    def update_overlay(self, matches):
        """更高效的更新方法"""
        # 批量删除旧矩形
        if self.current_rectangles:
            self.canvas.delete(*self.current_rectangles)
            self.current_rectangles.clear()
        
        # 批量创建新矩形
        for rect in matches:
            x, y, w, h, conf = rect
            self.current_rectangles.extend([
                self.canvas.create_rectangle(
                    x, y, x + w, y + h,
                    outline='green', width=2
                ),
                self.canvas.create_text(
                    x, y - 10,
                    text=f"{conf:.2f}",
                    fill='green'
                )
            ])
        
        self.root.update()

def main():
    overlay = OverlayWindow()
    template = None
    template_processed = None
    executor = ThreadPoolExecutor(max_workers=4)  # 创建线程池
    
    try:
        # 预先加载和处理模板
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cook_menu.png")
        template = cv2.imread(template_path)
        if template is None:
            raise FileNotFoundError(f"无法读取模板图像: {template_path}")
        template_processed = preprocess_image(template)
        
        threshold = 0.5
        scale_factors = np.arange(0.5, 2.1, 0.1)  # 增加步长减少计算量
        
        while True:
            start_time = time.time()
            
            # 截图和预处理
            screen = np.array(pyautogui.screenshot())
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            screen_processed = preprocess_image(screen_bgr)
            
            # 并行处理不同缩放比例
            process_func = partial(process_scale, screen_processed, template_processed, threshold=threshold)
            all_matches = []
            
            # 使用线程池并行处理
            futures = [executor.submit(process_func, scale) for scale in scale_factors]
            for future in futures:
                matches = future.result()
                all_matches.extend(matches)
            
            # 处理匹配结果
            if all_matches:
                rectangles = np.array(all_matches)
                # 使用更高效的NMS实现
                indices = cv2.dnn.NMSBoxes(
                    rectangles[:, :4].tolist(),
                    rectangles[:, 4].tolist(),
                    threshold,
                    0.4
                )
                
                if len(indices) > 0:
                    best_matches = rectangles[indices.flatten()]
                    overlay.update_overlay(best_matches)
                    
                    process_time = time.time() - start_time
                    logger.info(f"处理时间: {process_time:.3f}秒, 找到 {len(best_matches)} 个匹配")
            
            # 动态调整延迟
            process_time = time.time() - start_time
            sleep_time = max(0.1, 0.5 - process_time)  # 确保至少有0.1秒的延迟
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序发生错误: {str(e)}")
    finally:
        executor.shutdown()
        overlay.root.destroy()

if __name__ == "__main__":
    main()