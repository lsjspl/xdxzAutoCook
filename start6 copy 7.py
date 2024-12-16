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
from datetime import datetime, timedelta
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('cooking.log', encoding='utf-8')
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

class OverlayWindow:
    def __init__(self):
        """初始化覆盖窗口"""
        self.root = tk.Tk()
        self.root.title("Overlay")
        self.root.attributes('-alpha', 0.3, '-topmost', True)
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='black')
        self.root.attributes('-transparentcolor', 'black')
        
        self.canvas = tk.Canvas(
            self.root, 
            highlightthickness=0,
            bg='black'
        )
        self.canvas.pack(fill='both', expand=True)
        
    def update_overlay(self, matches):
        """更新覆盖层显示"""
        self.canvas.delete('all')  # 清除之前的矩形
        
        for match in matches:
            x, y, w, h, conf = match
            # 绘制绿色矩形框
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline='green',
                width=8
                
            )
            # 显示置信度
            self.canvas.create_text(
                x, y - 10,
                text=f'{conf:.2f}',
                fill='green',
                anchor='sw'
            )
        
        self.root.update()

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
        
        # 获取脚本目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.foods_dir = os.path.join(self.script_dir, "foods")
        
        # 定义多模板配置
        self.template_config = {
            'cook_menu': [
                'cook_menu.png',
                'cook_menu_1.png'
            ],
            'cook': [
                'cook.png',
                'cook_1.png'
            ],
            'finish': [
                'finish.png',
                'finish_1.png'
            ],
            'cook_start': ['cook_start.png'],  # 单模板
            'food': [f'{food_name}.png']  # 动态食物模板
        }
        
        # 分别存储普通模板和食物模板
        self.templates = self.load_templates()
        self.food_templates = self.load_food_templates()
        
        self.overlay = OverlayWindow()
        
        keyboard.add_hotkey('ctrl+q', self.stop)
        logger.info(f"当前选择的食物: {food_name}")
        logger.info("按 Ctrl+Q 可以退出程序")
        
        # 添加视角旋转相关配置
        self.screen_width = pyautogui.size().width
        self.screen_height = pyautogui.size().height
        self.rotation_duration = 0.1  # 旋转持续时间（秒）
        self.rotation_distance = 500  # 每次旋转的水平距离（像素）
        self.max_rotations = 4  # 最大旋转数
        self.current_rotations = 0  # 当前旋转次数
        
        # 定义视角旋转的起始点（屏幕右侧中间）
        self.rotation_start_x = int(self.screen_width * 0.8)  # 屏幕80%位置
        self.rotation_start_y = int(self.screen_height * 0.5)  # 屏幕中间
        
        # 添加状态计时相关属性
        self.state_start_time = datetime.now()
        self.timeout = 30  # 每个状态的超时时间（秒）
        self.max_retries = 3  # 最大重试次数
        self.retry_delay = 0.5  # 重试间隔（秒）
        self.retry_count = 0
        
        # 添加食物和开始按钮位置缓存
        self.food_button_pos = None
        self.start_button_pos = None
        
        # 优化截图和检测频率
        self.last_screenshot = None
        self.screenshot_interval = 0.1  # 截图间隔时间
        self.last_screenshot_time = 0
        
        # 优化模板匹配参数
        self.scale_factors = np.arange(0.8, 1.2, 0.1)  # 减少缩放范围
        self.nms_threshold = 0.4
        self.match_threshold = 0.7
        
        # 优化参数
        self.detection_interval = 0.2
        self.last_detection = None
        self.last_detection_time = 0
        self.roi_enabled = True
    
    def load_food_templates(self):
        """加载食物彩色模板"""
        food_templates = []
        for filename in self.template_config['food']:
            path = os.path.join(self.foods_dir, filename)
            template = cv2.imread(path)
            if template is None:
                logger.error(f"无法加载食物模板: {filename}")
                continue
            food_templates.append(template)
            logger.debug(f"已加载食物模板: {filename}")
        return food_templates
    
    def load_templates(self):
        """加载并预处理普通按钮模板"""
        templates = {}
        
        for key, template_files in self.template_config.items():
            if key == 'food':  # 跳过食物模板，它们会被单独处理
                continue
                
            templates[key] = []
            for filename in template_files:
                path = os.path.join(self.script_dir, filename)
                template = cv2.imread(path)
                if template is None:
                    logger.error(f"无法加载模板: {filename}")
                    continue
                    
                processed = self.preprocess_image(template)
                if processed is not None:
                    templates[key].append(processed)
                    logger.debug(f"已加载模板: {filename}")
        
        return templates
    
    def detect_food(self):
        """使用彩色图像检测食物按钮，优先选择左上角的图标"""
        try:
            screen = np.array(pyautogui.screenshot())
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            
            all_matches = []
            scale_factors = self.scale_factors
            threshold = 0.6
            
            for template in self.food_templates:
                template_matches = []
                
                for scale in scale_factors:
                    if scale != 1.0:
                        scaled_template = cv2.resize(
                            template, 
                            None, 
                            fx=scale, 
                            fy=scale, 
                            interpolation=cv2.INTER_LINEAR
                        )
                    else:
                        scaled_template = template
                    
                    result = cv2.matchTemplate(
                        screen_bgr, 
                        scaled_template, 
                        cv2.TM_CCOEFF_NORMED
                    )
                    
                    locations = np.where(result >= threshold)
                    h, w = scaled_template.shape[:2]
                    
                    for pt in zip(*locations[::-1]):
                        template_matches.append([
                            int(pt[0]), 
                            int(pt[1]), 
                            int(w), 
                            int(h), 
                            float(result[pt[1], pt[0]])
                        ])
                
                if template_matches:
                    # 对单个模板的结果进行NMS
                    rectangles = np.array(template_matches)
                    indices = cv2.dnn.NMSBoxes(
                        rectangles[:, :4].tolist(),
                        rectangles[:, 4].tolist(),
                        threshold,
                        0.4
                    )
                    if len(indices) > 0:
                        best_matches = rectangles[indices.flatten()]
                        all_matches.extend(best_matches)
            
            if all_matches:
                # 对所有匹配结果再次进行NMS
                rectangles = np.array(all_matches)
                indices = cv2.dnn.NMSBoxes(
                    rectangles[:, :4].tolist(),
                    rectangles[:, 4].tolist(),
                    threshold,
                    0.4
                )
                
                if len(indices) > 0:
                    best_matches = rectangles[indices.flatten()]
                    
                    # 按照位置排序（先按y坐标，再按x坐标）
                    sorted_matches = sorted(best_matches, key=lambda x: (x[1], x[0]))
                    
                    # 只选择最左上角的按钮
                    selected_match = sorted_matches[0]
                    
                    logger.info(f"[food] 检测到 {len(best_matches)} 个食物按钮，"
                              f"选择左上角按钮，位置: ({selected_match[0]}, {selected_match[1]})")
                    
                    # 只显示和返回左上角的按钮
                    self.overlay.update_overlay([selected_match])
                    return [selected_match]
            
            logger.info("[food] 未检测到食物按钮")
            self.overlay.update_overlay([])
            return []
            
        except Exception as e:
            logger.error(f"食物按钮检测失败: {e}")
            return []
    
    def get_screenshot(self):
        """获取屏幕截图，带缓存"""
        current_time = time.time()
        if (self.last_screenshot is None or 
            current_time - self.last_screenshot_time >= self.screenshot_interval):
            self.last_screenshot = np.array(pyautogui.screenshot())
            self.last_screenshot_time = current_time
        return self.last_screenshot
    
    def detect_buttons(self, template_name, threshold=0.6):
        """优化的按钮检测，添加阈值参数"""
        try:
            if template_name == 'food':
                return self.detect_food()
            
            screen = self.get_screenshot()
            if screen is None:
                logger.error("获取屏幕截图失败")
                return []
            
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            screen_processed = self.preprocess_image(screen_bgr)
            
            if screen_processed is None:
                logger.error("图像预处理失败")
                return []
            
            template_list = self.templates.get(template_name, [])
            if not template_list:
                logger.error(f"没有找到模板: {template_name}")
                return []
            
            all_matches = []
            
            for template in template_list:
                template_matches = []
                
                for scale in self.scale_factors:
                    if scale != 1.0:
                        scaled_template = cv2.resize(
                            template,
                            None,
                            fx=scale,
                            fy=scale,
                            interpolation=cv2.INTER_LINEAR
                        )
                    else:
                        scaled_template = template
                    
                    result = cv2.matchTemplate(
                        screen_processed,
                        scaled_template,
                        cv2.TM_CCOEFF_NORMED
                    )
                    
                    locations = np.where(result >= threshold)  # 用传入的阈值
                    h, w = scaled_template.shape[:2]
                    
                    for pt in zip(*locations[::-1]):
                        template_matches.append([
                            int(pt[0]),
                            int(pt[1]),
                            int(w),
                            int(h),
                            float(result[pt[1], pt[0]])
                        ])
                
                if template_matches:
                    all_matches.extend(template_matches)
            
            # 对所有匹配结果进行NMS
            if all_matches:
                rectangles = np.array(all_matches)
                indices = cv2.dnn.NMSBoxes(
                    rectangles[:, :4].tolist(),
                    rectangles[:, 4].tolist(),
                    threshold,
                    0.4
                )
                
                if len(indices) > 0:
                    best_matches = rectangles[indices.flatten()]
                    logger.debug(f"[{template_name}] 检测到 {len(best_matches)} 个按钮，"
                               f"置信度: {[f'{match[4]:.2f}' for match in best_matches]}")
                    self.overlay.update_overlay(best_matches)
                    return best_matches.tolist()
            
            logger.debug(f"[{template_name}] 未检测到按钮")
            self.overlay.update_overlay([])
            return []
            
        except Exception as e:
            logger.error(f"按钮检测失败: {e}")
            return []
    
    def process_scale(self, screen, template, scale, threshold):
        """优化的单一尺度处理"""
        try:
            if scale != 1.0:
                scaled_template = cv2.resize(
                    template,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_LINEAR
                )
            else:
                scaled_template = template
            
            result = cv2.matchTemplate(
                screen,
                scaled_template,
                cv2.TM_CCOEFF_NORMED
            )
            
            locations = np.where(result >= threshold)
            h, w = scaled_template.shape[:2]
            
            matches = []
            for pt in zip(*locations[::-1]):
                matches.append([
                    int(pt[0]),
                    int(pt[1]),
                    int(w),
                    int(h),
                    float(result[pt[1], pt[0]])
                ])
            
            return matches
            
        except Exception as e:
            logger.error(f"尺度处理失败: {e}")
            return []
    
    def set_food(self, food_name):
        """更改要制作的食物"""
        self.food_name = food_name
        self.template_config['food'] = [f'{food_name}.png']
        self.templates = self.load_templates()  # 重新加载有模板
        logger.info(f"已更改食物为: {food_name}")

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
            
            # 应用形态学操作来减噪声
            kernel = np.ones((3,3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            
            # 应用掩码
            result = cv2.bitwise_and(image, image, mask=mask)
            
            # 转为灰度
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

    def check_and_click_cook(self):
        """检查并点击cook按钮，如果点击成功返回True"""
        if self.menu_clicks >= 3:
            cook_buttons = self.detect_buttons('cook', threshold=0.6)  # 降低阈值以提高检测率
            if cook_buttons and len(cook_buttons) > 0:
                logger.info("=== 检测到cook按钮，立即处理 ===")
                try:
                    cook_button = cook_buttons[0].tolist() if isinstance(cook_buttons[0], np.ndarray) else list(cook_buttons[0])
                    x, y, w, h, conf = cook_button
                    logger.info(f"cook按钮位置: ({x}, {y}), 置信度: {conf:.2f}")
                    
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)
                    pyautogui.click(center_x, center_y)
                    logger.info(f"点击cook按钮 位置: ({center_x}, {center_y})")
                    time.sleep(0.5)
                    self.cook_clicks += 1
                    self.reset_rotation()
                    
                    # 检查菜单点击次数，决定下一个状态
                    if self.menu_clicks >= 3:
                        logger.info("菜单点击已完成3次，进入finish检测状态")
                        self.change_state(CookingState.CLICK_FINISH)
                    else:
                        logger.info(f"菜单点击次数不足（{self.menu_clicks}/3），继续点击菜单")
                        self.change_state(CookingState.CLICK_MENU)
                    return True
                    
                except Exception as e:
                    logger.error(f"处理cook按钮时出错: {e}")
        return False

    def rotate_view(self):
        """使用窗口中心点偏右上的位置旋转视角，同时检测cook按钮"""
        try:
            # 旋转前检测cook按钮
            if self.check_and_click_cook():
                return True
            
            # 获取窗口中心
            screen_width, screen_height = pyautogui.size()
            center_x = screen_width // 2
            center_y = screen_height // 2
            
            # 计算偏右上的位置（从中心点向右100像素，向上50像素）
            rotate_x = center_x + 200
            rotate_y = center_y - 100
            
            logger.debug(f"使用位置 ({rotate_x}, {rotate_y}) 进行视角旋转")
            
            # 分段旋转，每次旋转后检测cook按钮
            pyautogui.moveTo(rotate_x, rotate_y)
            pyautogui.mouseDown(button='left')
            time.sleep(0.1)
            
            # 计算每段旋转的距离
            segment_distance = self.rotation_distance // 4  # 将总旋转距离分4段
            
            # 分4次旋转，每次旋转后检测cook按钮
            for i in range(4):
                pyautogui.moveRel(segment_distance, 0, duration=0.2)
                pyautogui.mouseUp(button='left')
                
                # 每次移动后检测cook按钮
                if self.check_and_click_cook():
                    return True
                
                if i < 3:  # 如果不是最后一次移动，继续按下鼠标
                    pyautogui.mouseDown(button='left')
                    time.sleep(0.1)
            
            time.sleep(0.2)  # 等待画面稳定
            return True
            
        except Exception as e:
            logger.error(f"旋转视角失败: {e}")
            return False
    
    def reset_rotation(self):
        """重置旋转计数"""
        self.current_rotations = 0
        # 确保鼠标左键被释放
        pyautogui.mouseUp(button='left')
    
    def safe_exit(self):
        """安全退出，确保释放所有按键"""
        try:
            pyautogui.mouseUp(button='left')
            keyboard.unhook_all()
            self.executor.shutdown()
            self.overlay.root.destroy()
            logger.info("程序已安全退出")
        except Exception as e:
            logger.error(f"退出时发生错误: {e}")
    
    def reset_state_timer(self):
        """重置状态计时器"""
        self.state_start_time = datetime.now()
        self.retry_count = 0
    
    def is_state_timeout(self):
        """检查当前状态是否超时"""
        return (datetime.now() - self.state_start_time).total_seconds() > self.timeout
    
    def handle_timeout(self):
        """处理超时情况"""
        if self.retry_count >= self.max_retries:
            logger.error(f"状态 {self.state} 超过最大重试次数")
            return False
        
        self.retry_count += 1
        logger.warning(f"状态 {self.state} 超时，第 {self.retry_count} 次重试")
        time.sleep(self.retry_delay)
        return True
    
    def change_state(self, new_state):
        """切换状态"""
        logger.info(f"状态切换: {self.state} -> {new_state}")
        self.state = new_state
        self.reset_state_timer()
    
    def handle_menu_state(self):
        """处理菜单检测状态"""
        menu_buttons = self.detect_buttons('cook_menu')
        if len(menu_buttons) == 3:
            logger.info("=== 检测到3个菜单按钮，开始点击流程 ===")
            self.reset_rotation()
            self.change_state(CookingState.CLICK_MENU)
            return
        
        logger.debug(f"等待菜单按钮，当前检测到 {len(menu_buttons)} 个")
        # 检查遗留的完成按钮
        finish_buttons = self.detect_buttons('finish')
        if len(finish_buttons) > 0:
            logger.info("=== 检测到遗留的完成按钮，优先处理 ===")
            try:
                if self.click_button_with_verify(finish_buttons[0], 'finish', wait_time=0.3):
                    logger.info("完成按钮点击成功")
                    return
            except Exception as e:
                logger.error(f"点击完成按钮失败: {e}")
        
        # 尝试旋转视角寻找菜单按钮
        if not self.rotate_view():
            logger.warning("已旋转一圈仍未找到足够的菜单按钮")
            self.reset_rotation()
            if not self.handle_timeout():
                raise Exception("菜单检测超时")

    def handle_food_state(self):
        """处理食物检测状态 - 使用保存的食物按钮位置"""
        try:
            # 确保有保存的食物按钮位置
            if not self.food_button_pos:
                logger.warning("未保存食物按钮位置，返回菜单检测状态")
                self.change_state(CookingState.DETECT_MENU)
                return
            
            logger.info("=== 使用保存的食物按钮位置点击 ===")
            try:
                x, y, w, h, _ = self.food_button_pos
                center_x = int(x + w // 2)
                center_y = int(y + h // 2)
                
                pyautogui.click(center_x, center_y)
                pyautogui.click(center_x, center_y)  # 双击确保选中
                logger.info(f"点击食物按钮位置: ({center_x}, {center_y})")
                time.sleep(0.5)
                
                # 首次检测并保存开始按钮位置
                if not self.start_button_pos:
                    start_buttons = self.detect_buttons('cook_start', threshold=0.5)
                    if isinstance(start_buttons, list) and len(start_buttons) > 0:
                        logger.info("首次检测到开始按钮，保存位置")
                        self.start_button_pos = start_buttons[0].tolist() if isinstance(start_buttons[0], np.ndarray) else list(start_buttons[0])
                        self.food_clicked = True
                        self.change_state(CookingState.DETECT_START)
                    else:
                        logger.warning("未检测到开始按钮，重试食物点击")
                else:
                    self.food_clicked = True
                    self.change_state(CookingState.DETECT_START)
                    
            except Exception as e:
                logger.error(f"点击食物按钮失败: {e}")
                if not self.handle_timeout():
                    raise Exception("食物点击超时")
                
        except Exception as e:
            logger.error(f"处理食物状态时出错: {e}")
            if not self.handle_timeout():
                raise Exception("食物状态处理超时")

    def handle_start_state(self):
        """处理开始按钮状态"""
        if not self.food_clicked or self.start_button_pos is None:
            logger.warning("食物未点击或开始按钮位置未知，返回食物检测状态")
            self.change_state(CookingState.DETECT_FOOD)
            return
        
        logger.info("=== 点击开始按钮 ===")
        try:
            if self.click_button_with_verify(self.start_button_pos, 'cook_start', expected_count=0, wait_time=0.5):
                if self.menu_clicks >= 3:
                    logger.info("=== 菜单点击完成，等待cook按钮 ===")
                    self.change_state(CookingState.DETECT_COOK)
                else:
                    logger.info(f"=== 当前菜单点击次数: {self.menu_clicks}，继续点击菜单 ===")
                    # 在切换到CLICK_MENU之前，先检查是否能检测到菜单按钮
                    menu_buttons = self.detect_buttons('cook_menu')
                    if menu_buttons and len(menu_buttons) > 0:
                        self.change_state(CookingState.CLICK_MENU)
                    else:
                        logger.info("未检测到菜单按钮，先切换到菜单检测状态")
                        self.change_state(CookingState.DETECT_MENU)
            else:
                logger.warning("开始按钮点击未生效，重试")
                self.reset_button_positions()
                self.change_state(CookingState.DETECT_FOOD)
                
        except Exception as e:
            logger.error(f"点击开始按钮失败: {e}")
            self.reset_button_positions()
            if not self.handle_timeout():
                raise Exception("开始按钮点击超时")

    def handle_cook_state(self):
        """处理烹饪状态"""
        cook_buttons = self.detect_buttons('cook')
        if len(cook_buttons) > 0:
            logger.info(f"=== 点击烹饪按钮 ===")
            try:
                if self.click_button_with_verify(cook_buttons[0], 'finish', expected_count=3, wait_time=0.5):
                    self.cook_clicks += 1
                    self.reset_rotation()
                    self.change_state(CookingState.CLICK_FINISH)
                else:
                    logger.warning("烹饪按钮点击未生效，重试")
            except Exception as e:
                logger.error(f"点击烹饪按钮失败: {e}")
                if not self.handle_timeout():
                    raise Exception("烹饪按钮点击超时")
        else:
            if not self.rotate_view():
                logger.warning("已旋转一圈仍未找到烹饪按钮")
                self.reset_rotation()
                if not self.handle_timeout():
                    raise Exception("烹饪按��检测超时")

    def handle_finish_state(self):
        """处理完成状态 - 检测到finish按钮就点击，并验证点击结果"""
        try:
            finish_buttons = self.detect_buttons('finish')
            
            # 记录检测到的finish按钮数量
            logger.info(f"检测到 {len(finish_buttons)} 个finish按钮")
            
            # 处理遗留的finish按钮（在菜单点击未满3次时）
            if self.menu_clicks < 3 and finish_buttons and len(finish_buttons) > 0:
                logger.info("=== 检测到遗留的finish按钮，处理中 ===")
                try:
                    finish_button = finish_buttons[0].tolist() if isinstance(finish_buttons[0], np.ndarray) else list(finish_buttons[0])
                    x, y, w, h, _ = finish_button
                    pyautogui.click(int(x + w // 2), int(y + h // 2))
                    logger.info(f"点击遗留的finish按钮")
                    time.sleep(0.5)
                    
                    # 验证点击结果
                    verify_buttons = self.detect_buttons('finish')
                    if not verify_buttons or len(verify_buttons) < len(finish_buttons):
                        logger.info("遗留finish按钮点击成功（按钮消失）")
                    else:
                        logger.warning("遗留finish按钮点击可能未生效")
                    return
                    
                except Exception as e:
                    logger.error(f"点击遗留finish按钮失败: {e}")
                    
            # 正常的finish处理（完成3次菜单点击后）
            if self.menu_clicks >= 3:
                if finish_buttons and len(finish_buttons) > 0:
                    logger.info(f"=== 检测到 {len(finish_buttons)} 个finish按钮，继续点击 ===")
                    try:
                        # 点击检测到的每个finish按钮
                        for finish_button in finish_buttons:
                            button_data = finish_button.tolist() if isinstance(finish_button, np.ndarray) else list(finish_button)
                            x, y, w, h, conf = button_data
                            center_x = int(x + w // 2)
                            center_y = int(y + h // 2)
                            
                            logger.info(f"点击finish按钮 位置: ({center_x}, {center_y}), 置信度: {conf:.2f}")
                            pyautogui.click(center_x, center_y)
                            time.sleep(0.5)  # 点击后短暂等待
                            
                            # 验证点击结果
                            max_verify_attempts = 3
                            for attempt in range(max_verify_attempts):
                                verify_buttons = self.detect_buttons('finish')
                                if not verify_buttons or len(verify_buttons) < len(finish_buttons):
                                    logger.info("finish按钮点击成功（按钮消失）")
                                    self.finish_clicks += 1
                                    logger.info(f"当前finish点击次数: {self.finish_clicks}")
                                    break
                                elif attempt < max_verify_attempts - 1:
                                    logger.warning(f"第 {attempt + 1} 次验证：finish按钮点击可能未生效，等待后重试")
                                    time.sleep(0.5)
                                else:
                                    logger.warning("finish按钮点击未生效")
                                    continue
                            
                            if self.finish_clicks >= 3:
                                logger.info("=== 完成所有finish按钮点击 ===")
                                raise Exception("完成所有操作")
                                
                    except Exception as e:
                        if str(e) == "完成所有操作":
                            raise
                        logger.error(f"点击finish按钮失败: {e}")
                        if not self.handle_timeout():
                            raise Exception("finish按钮点击超时")
                else:
                    # 未检测到finish按钮时，继续旋转视角寻找
                    logger.info("未检测到finish按钮，继续寻找")
                    if not self.rotate_view():
                        logger.warning("已旋转一圈仍未找到finish按钮")
                        self.reset_rotation()
                        if not self.handle_timeout():
                            raise Exception("finish按钮检测超时")
                            
        except Exception as e:
            if str(e) == "完成所有操作":
                raise
            logger.error(f"处理finish状态时出错: {e}")
            if not self.handle_timeout():
                raise Exception("finish状态处理超时")

    def handle_click_menu_state(self):
        """处理菜单点击状态"""
        try:
            menu_buttons = self.detect_buttons('cook_menu')
            if not menu_buttons or len(menu_buttons) == 0:
                logger.warning("未检测到菜单按钮，切换到菜单检测状态")
                self.change_state(CookingState.DETECT_MENU)
                return
            
            logger.info(f"检测到 {len(menu_buttons)} 个菜单按钮")
            menu_button = menu_buttons[0]
            if isinstance(menu_button, np.ndarray):
                menu_button = menu_button.tolist()
            
            # 点击菜单按钮
            x, y, w, h, _ = menu_button
            center_x = int(x + w // 2)
            center_y = int(y + h // 2)
            
            logger.info(f"点击菜单按钮位置: ({center_x}, {center_y})")
            pyautogui.click(center_x, center_y)
            time.sleep(1.0)  # 增加等待时间，确保界面响应
            
            # 点击后验证：多次尝试检测食物或开始按钮
            max_verify_attempts = 3
            for attempt in range(max_verify_attempts):
                if self.food_clicked:
                    # ���果已经选择过食物，使用保存的开始按钮位置
                    if self.start_button_pos:
                        logger.info("菜单点击成功，使用已保存的开始按钮位置")
                        self.menu_clicks += 1
                        logger.info(f"当前菜单点击次数: {self.menu_clicks}")
                        self.change_state(CookingState.DETECT_START)
                        return
                else:
                    # 首次点击菜单，检测并保存食物按钮位置
                    if not self.food_button_pos:
                        food_buttons = self.detect_buttons('food')
                        if food_buttons:
                            logger.info("首次检测到食物按钮，保存位置")
                            self.food_button_pos = food_buttons[0].tolist() if isinstance(food_buttons[0], np.ndarray) else list(food_buttons[0])
                            self.menu_clicks += 1
                            logger.info(f"当前菜单点击次数: {self.menu_clicks}")
                            self.change_state(CookingState.DETECT_FOOD)
                            return
                    
                if attempt < max_verify_attempts - 1:
                    logger.info(f"第 {attempt + 1} 次验证未检测到目标按钮，等待后重试")
                    time.sleep(0.5)  # 每次验证间隔
            
            # 多次验证都失败，返回检测菜单状态
            logger.warning("多次验证后菜单点击未生效，返回菜单检测状态")
            self.change_state(CookingState.DETECT_MENU)
            if not self.handle_timeout():
                raise Exception("菜单点击超时")
                
        except Exception as e:
            logger.error(f"菜单点击状态处理失败: {e}")
            if not self.handle_timeout():
                raise Exception("菜单点击状态处理超时")

    def run(self):
        """主程序循环"""
        try:
            self.reset_state_timer()
            self.reset_button_positions()
            
            while self.running:
                # 每次循环开始都检查cook按钮（如果已完成3次菜单点击）
                if self.menu_clicks >= 3:
                    if self.check_and_click_cook():
                        continue
                
                if self.is_state_timeout():
                    if not self.handle_timeout():
                        break
                    continue
                
                # 正常状态处理流程
                if self.state == CookingState.DETECT_MENU:
                    # 检测��单前先检查cook
                    if self.menu_clicks >= 3 and self.check_and_click_cook():
                        continue
                    self.handle_menu_state()
                
                elif self.state == CookingState.CLICK_MENU:
                    # 点击菜单前先检查cook
                    if self.menu_clicks >= 3 and self.check_and_click_cook():
                        continue
                    self.handle_click_menu_state()
                
                elif self.state == CookingState.DETECT_FOOD:
                    # 检测食物前先检查cook
                    if self.menu_clicks >= 3 and self.check_and_click_cook():
                        continue
                    self.handle_food_state()
                
                elif self.state == CookingState.DETECT_START:
                    # 检测开始前先检查cook
                    if self.menu_clicks >= 3 and self.check_and_click_cook():
                        continue
                    self.handle_start_state()
                
                elif self.state == CookingState.CLICK_FINISH:
                    # 点击完成前先检查cook
                    if self.menu_clicks >= 3 and self.check_and_click_cook():
                        continue
                    self.handle_finish_state()
                
                # 每次状态处理后再检查一次cook
                if self.menu_clicks >= 3:
                    self.check_and_click_cook()
                
                time.sleep(0.1)
                
        except Exception as e:
            if str(e) == "完成所有操作":
                logger.info("程序正常完成")
            else:
                logger.error(f"程序发生错误: {str(e)}")
        finally:
            self.safe_exit()

    def get_optimized_screenshot(self):
        """获取优化后的截图"""
        current_time = time.time()
        if (self.last_screenshot is None or 
            current_time - self.last_screenshot_time >= self.screenshot_interval):
            screen = np.array(pyautogui.screenshot())
            screen = self.optimize_image_size(screen)
            self.last_screenshot = screen
            self.last_screenshot_time = current_time
        return self.last_screenshot
    
    def detect_with_roi(self, template_name):
        """使用ROI区域进行检测"""
        screen = self.get_optimized_screenshot()
        if not self.roi_enabled:
            return self.detect_buttons(screen, template_name)
            
        h, w = screen.shape[:2]
        roi_x = int(w * 0.2)
        roi_y = int(h * 0.2)
        roi_w = int(w * 0.6)
        roi_h = int(h * 0.6)
        
        roi = screen[roi_y:roi_y+roi_h, roi_x:roi_x+roi_w]
        matches = self.detect_buttons(roi, template_name)
        
        # 调整坐标以匹配始屏幕
        for match in matches:
            match[0] += roi_x
            match[1] += roi_y
            
        return matches

    def reset_button_positions(self):
        """重置按钮位置缓存"""
        self.food_button_pos = None
        self.start_button_pos = None
        logger.info("重置按钮位置缓存")

    def click_button_with_verify(self, button, template_name, expected_count=None, verify_start_button=False, wait_time=1.0):
        """优化的按钮点击验证
        
        Args:
            button: 点击的按钮信息 [x, y, w, h, confidence]
            template_name: 模板名称，用于验证
            expected_count: 期望点击后的按钮数量
            verify_start_button: 是否验证开始按钮
            wait_time: 点击后的等待时间
        
        Returns:
            bool: 点击是否成功
        """
        try:
            # 记录点击前的状态，用于后续验证
            initial_buttons = self.detect_buttons(template_name)
            initial_count = len(initial_buttons)
            logger.debug(f"点击前按钮数量: {initial_count}")
            
            # 确保button是列表或元组类型
            if isinstance(button, np.ndarray):
                button = button.tolist()
            
            # 计算并执行点击
            x, y, w, h, _ = button
            center_x = x + w // 2
            center_y = y + h // 2
            
            # 点击前短暂延迟，防止操作过快
            time.sleep(0.1)
            pyautogui.click(center_x, center_y)
            pyautogui.click(center_x, center_y)
            logger.info(f"点击按钮: ({center_x}, {center_y})")
            
            # 等待界面更新
            time.sleep(wait_time)
            
            # 根据不同情况验证点击效果
            if verify_start_button:
                # 特殊情况：验证食物和开始按钮是否同时存在
                food_buttons = self.detect_buttons('food')
                start_buttons = self.detect_buttons('cook_start')
                success = len(food_buttons) > 0 and len(start_buttons) > 0
                logger.debug(f"验证开始按钮: 食物按钮={len(food_buttons)}, 开始按钮={len(start_buttons)}")
                return success
            
            # 普通情况：检查按钮数量变化
            current_buttons = self.detect_buttons(template_name)
            current_count = len(current_buttons)
            logger.debug(f"点击后按钮数量: {current_count}")
            
            if expected_count is not None:
                # 如果指期望数量，直接比较
                success = current_count == expected_count
            else:
                # 否则只要数量发生变化认为成功
                success = current_count != initial_count
            
            logger.debug(f"点击验证结果: {success}")
            return success
            
        except Exception as e:
            logger.error(f"点击按钮验证失败: {e}")
            return False

def main():
    # 示例：如何使用不的食物模板
    food_name = "natie"  # 默认使用 foods/food.png
    bot = CookingBot(food_name)
    
    # 显示所有可用的食物模板
    available_foods = bot.get_available_foods()
    logger.info(f"可用的食物模板: {available_foods}")
    
    # 可以在运行过程中随时更食物
    # bot.set_food("food2")  # 切换到 foods/food2.png
    
    bot.run()

if __name__ == "__main__":
    main()