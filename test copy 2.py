import cv2
import pyautogui
import numpy as np
import os
import time
import tkinter as tk
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from enum import Enum, auto
import keyboard

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('cooking.log')
    ]
)
logger = logging.getLogger(__name__)

class CookingState(Enum):
    DETECT_MENU = auto()
    CLICK_MENU = auto()
    DETECT_FOOD = auto()
    DETECT_START = auto()
    DETECT_COOK = auto()
    DETECT_FINISH = auto()
    CLICK_FINISH = auto()

class CookingBot:
    def __init__(self, food_name="food"):
        """
        初始化烹饪机器人
        :param food_name: 食物模板的名称（不包含.png后缀）
        """
        self.state = CookingState.DETECT_MENU
        self.menu_clicks = 0
        self.cook_clicks = 0
        self.finish_clicks = 0
        self.food_clicked = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running = True
        self.food_name = food_name
        
        # 获取脚本目录和foods目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.foods_dir = os.path.join(self.script_dir, "foods")
        
        # 确保foods目录存在
        if not os.path.exists(self.foods_dir):
            os.makedirs(self.foods_dir)
            logger.warning(f"创建foods目录: {self.foods_dir}")
        
        self.templates = self.load_templates()
        
        keyboard.add_hotkey('ctrl+q', self.stop)
        logger.info(f"当前选择的食物: {food_name}")
        logger.info("按 Ctrl+Q 可以退出程序")
    
    def load_templates(self):
        """加载所有模板图像"""
        templates = {}
        
        # 加载基础模板（在脚本目录中）
        base_templates = {
            'cook_menu': 'cook_menu.png',
            'cook_start': 'cook_start.png',
            'cook': 'cook.png',
            'finish': 'finish.png'
        }
        
        # 加载基础模板
        for key, filename in base_templates.items():
            path = os.path.join(self.script_dir, filename)
            template = cv2.imread(path)
            if template is None:
                logger.error(f"无法加载基础模板: {filename}")
                continue
            templates[key] = self.preprocess_image(template)
            logger.debug(f"已加载基础模板: {filename}")
        
        # 加载食物模板（从foods目录）
        food_path = os.path.join(self.foods_dir, f"{self.food_name}.png")
        food_template = cv2.imread(food_path)
        if food_template is None:
            logger.error(f"无法加载食物模板: {self.food_name}.png")
            available_foods = [f[:-4] for f in os.listdir(self.foods_dir) if f.endswith('.png')]
            logger.info(f"可用的食物模板: {available_foods}")
        else:
            templates['food'] = self.preprocess_image(food_template)
            logger.debug(f"已加载食物模板: {self.food_name}.png")
        
        return templates
    
    def set_food(self, food_name):
        """
        更改要制作的食物
        :param food_name: 新的食物名称（不包含.png后缀）
        """
        food_path = os.path.join(self.foods_dir, f"{food_name}.png")
        food_template = cv2.imread(food_path)
        if food_template is None:
            logger.error(f"无法加载食物模板: {food_name}.png")
            available_foods = [f[:-4] for f in os.listdir(self.foods_dir) if f.endswith('.png')]
            logger.info(f"可用的食物模板: {available_foods}")
            return False
        
        self.food_name = food_name
        self.templates['food'] = self.preprocess_image(food_template)
        logger.info(f"已更改食物为: {food_name}")
        return True

    def get_available_foods(self):
        """获取所有可用的食物模板列表"""
        foods = [f[:-4] for f in os.listdir(self.foods_dir) if f.endswith('.png')]
        return foods

    def stop(self):
        """停止程序的方法"""
        logger.info("收到退出信号")
        self.running = False

    def preprocess_image(self, image):
        """改进的图像预处理方法，处理复杂背景"""
        try:
            # 转换到HSV颜色空间
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # 创建多个颜色范围的掩码
            masks = []
            
            # 白色范围（按钮主体）
            masks.append(cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 30, 255])))
            
            # 浅灰色范围（按钮边缘）
            masks.append(cv2.inRange(hsv, np.array([0, 0, 150]), np.array([180, 30, 200])))
            
            # 深灰色范围（按钮阴影）
            masks.append(cv2.inRange(hsv, np.array([0, 0, 50]), np.array([180, 30, 150])))
            
            # 合并所有掩码
            mask = masks[0]
            for m in masks[1:]:
                mask = cv2.bitwise_or(mask, m)
            
            # 应用形态学操作来减少噪声
            kernel = np.ones((3,3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # 应用掩码
            result = cv2.bitwise_and(image, image, mask=mask)
            
            # 转换为灰度图
            gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
            
            # 应用自适应阈值
            thresh = cv2.adaptiveThreshold(
                gray, 255, 
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 
                15, 5
            )
            
            # 再次应用形态学操作
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            logger.debug("图像预处理完成")
            return thresh
            
        except Exception as e:
            logger.error(f"图像预处理失败: {str(e)}")
            return None

    def detect_buttons(self, template_name):
        """改进的按钮检测方法"""
        try:
            # 获取屏幕截图
            screen = np.array(pyautogui.screenshot())
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            
            # 预处理屏幕图像
            screen_processed = self.preprocess_image(screen_bgr)
            if screen_processed is None:
                return []
            
            template = self.templates.get(template_name)
            if template is None:
                logger.error(f"模板不存在: {template_name}")
                return []
            
            # 使用多个缩放比例
            scale_factors = np.arange(0.5, 2.1, 0.1)
            threshold = 0.6  # 降低阈值以提高检测率
            all_matches = []
            
            # 并行处理不同缩放比例
            process_func = partial(self.process_scale, screen_processed, template, threshold=threshold)
            futures = [self.executor.submit(process_func, scale) for scale in scale_factors]
            
            for future in futures:
                matches = future.result()
                all_matches.extend(matches)
            
            if all_matches:
                rectangles = np.array(all_matches)
                indices = cv2.dnn.NMSBoxes(
                    rectangles[:, :4].tolist(),
                    rectangles[:, 4].tolist(),
                    threshold,
                    0.4  # 增加NMS阈值以保留更多候选框
                )
                
                if len(indices) > 0:
                    best_matches = rectangles[indices.flatten()]
                    logger.debug(f"检测到 {len(best_matches)} 个 {template_name} 按钮")
                    return best_matches
            
            return []
            
        except Exception as e:
            logger.error(f"按钮检测失败: {str(e)}")
            return []

    def process_scale(self, screen_processed, template_processed, scale, threshold):
        """处理单个缩放比例的匹配"""
        width = int(template_processed.shape[1] * scale)
        height = int(template_processed.shape[0] * scale)
        resized_template = cv2.resize(template_processed, (width, height))
        
        result = cv2.matchTemplate(screen_processed, resized_template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)
        
        return [[pt[0], pt[1], width, height, result[pt[1], pt[0]]] 
                for pt in zip(*locations[::-1])]

    def click_button(self, button):
        """点击按钮"""
        x, y, w, h, _ = button
        center_x = x + w // 2
        center_y = y + h // 2
        pyautogui.click(center_x, center_y)
        time.sleep(1)  # 等待动画完成

    def run(self):
        """运行主循环"""
        try:
            while self.running:
                if self.state == CookingState.DETECT_MENU:
                    menu_buttons = self.detect_buttons('cook_menu')
                    logger.info(f"检测到{len(menu_buttons)}个菜单按钮")
                    if len(menu_buttons) == 3:
                        logger.info("检测到3个菜单")
                        self.state = CookingState.CLICK_MENU
                    
                elif self.state == CookingState.CLICK_MENU:
                    menu_buttons = self.detect_buttons('cook_menu')
                    if len(menu_buttons) > 0:
                        self.click_button(menu_buttons[0])
                        self.menu_clicks += 1
                        self.food_clicked = False
                        self.state = CookingState.DETECT_FOOD
                    
                elif self.state == CookingState.DETECT_FOOD:
                    food_buttons = self.detect_buttons('food')
                    if len(food_buttons) > 0:
                        self.click_button(food_buttons[0])
                        self.food_clicked = True
                        self.state = CookingState.DETECT_START
                    
                elif self.state == CookingState.DETECT_START:
                    if self.food_clicked:
                        start_buttons = self.detect_buttons('cook_start')
                        if len(start_buttons) > 0:
                            self.click_button(start_buttons[0])
                            if self.menu_clicks >= 3:
                                self.state = CookingState.DETECT_COOK
                            else:
                                self.state = CookingState.CLICK_MENU
                    
                elif self.state == CookingState.DETECT_COOK:
                    cook_buttons = self.detect_buttons('cook')
                    if len(cook_buttons) > 0:
                        self.click_button(cook_buttons[0])
                        finish_buttons = self.detect_buttons('finish')
                        if len(finish_buttons) == 3:
                            self.state = CookingState.CLICK_FINISH
                    
                elif self.state == CookingState.CLICK_FINISH:
                    finish_buttons = self.detect_buttons('finish')
                    if len(finish_buttons) > 0:
                        self.click_button(finish_buttons[0])
                        self.finish_clicks += 1
                        if self.finish_clicks >= 3:
                            logger.info("完成所有操作")
                            break
                
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"程序发生错误: {str(e)}")
        finally:
            keyboard.unhook_all()
            self.executor.shutdown()
            logger.info("程序已退出")

def main():
    # 示例：如何使用不同的食物模板
    food_name = "boluo"  # 默认使用 foods/food.png
    bot = CookingBot(food_name)
    
    # 显示所有可用的食物模板
    available_foods = bot.get_available_foods()
    logger.info(f"可用的食物模板: {available_foods}")
    
    # 可以在运行过程中随时更改食物
    # bot.set_food("food2")  # 切换到 foods/food2.png
    
    bot.run()

if __name__ == "__main__":
    main()