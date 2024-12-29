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
import argparse

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
        self.root.attributes('-alpha', 1.0, '-topmost', True)
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
                width=5
                
            )
            # 显示置信度
            self.canvas.create_text(
                x, y - 10,
                text=f'{conf:.2f}',
                fill='green',
                anchor='sw',
                font=('Arial', 12, 'bold')  # 加粗字体
            )
        
        self.root.update()

class CookingBot:
    def __init__(self, food_name="food", loop_count=1):
        """
        初始化烹饪机器人
        :param food_name: 食物模板的名称（不包含.png后缀）
        :param loop_count: 循环执行次数，-1表示无限循环
        """
        self.state = CookingState.DETECT_MENU
        self.menu_clicks = 0
        self.finish_clicks = 0
        self.food_clicked = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.running = True
        self.food_name = food_name
        self.loop_count = loop_count
        self.current_loop = 0
        
        # 获取脚本目录
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.btns_dir = os.path.join(self.script_dir, "btns")
        self.foods_dir = os.path.join(self.script_dir, "foods")
        
        # 定义多模板配置
        self.template_config = {
            'cook_menu': [
                'cook_menu.png'
            ],
            'cook': [
                'cook.png'
            ],
            'finish': [
                'finish.png'
            ],
            'cook_start': ['cook_start.png'],  # 单模板
            'food': [f'{food_name}.png',f'{food_name}_1.png'],  # 动态食物模板
            'back': ['back.png'],
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
        
        # 添加状态计时相关属性
        self.state_start_time = datetime.now()
        self.timeout = 30  # 每个状态的超时时间（秒）
        self.max_retries = 3  # 最大重试次数
        self.retry_count = 0
        
        # 添加食物和开始按钮位置缓存
        self.food_button_pos = None
        self.start_button_pos = None
        
        # 优化模板匹配参数
        self.scale_factors = np.arange(0.5, 2, 0.1)
        
        # 优化截图缓存
        self.last_screenshot = None
        self.last_screenshot_time = 0
        
        self.start_clicks = 0  # 添加开始按钮点击计数器

    def load_food_templates(self):
        """加载食物彩色模板"""
        food_templates = []
        for filename in self.template_config['food']:
            path = os.path.join(self.foods_dir, filename)
            template = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

            if template is None:
                logger.error(f"无法加载食物模板: {path}")
                continue
            food_templates.append(template)
            logger.debug(f"已加载食物模板: {path}")
        return food_templates
    
    def load_templates(self):
        """加载并预处理普通按钮模板"""
        templates = {}
        
        for key, template_files in self.template_config.items():
            if key == 'food':  # 跳过食物模板，它们会被单独处理
                continue
                
            templates[key] = []
            for filename in template_files:
                path = os.path.join(self.btns_dir, filename)
                template = cv2.imread(path)
                if template is None:
                    logger.error(f"无法加载模板: {path}")
                    continue
                    
                processed = self.preprocess_image(template)
                if processed is not None:
                    templates[key].append(processed)
                    logger.debug(f"已加载模板: {path}")
        
        return templates
    
    def detect_food(self):
        """使用彩色图像检测食物按钮，优先选择左上角的图标"""
        try:
            screen = np.array(pyautogui.screenshot())
            screen_bgr = cv2.cvtColor(screen, cv2.COLOR_RGB2BGR)
            
            all_matches = []
            scale_factors = self.scale_factors
            threshold = 0.8
            
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
                    
                    # 显示和返回左上角的按钮
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
            current_time - self.last_screenshot_time >= 0.1):  # 直接使用固定值0.1
            self.last_screenshot = np.array(pyautogui.screenshot())
            self.last_screenshot_time = current_time
        return self.last_screenshot
    
    def detect_buttons(self, template_name, threshold=0.8):
        """优化的按钮检测"""
        try:
            if template_name == 'cook':
                # cook按钮使用更快的检测参数
                self.scale_factors = np.arange(0.9, 1.1, 0.1)
                threshold = 0.5
            else:
                self.scale_factors = np.arange(0.8, 1.2, 0.1)
                threshold = 0.6
            
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
            
            # 对所有匹配结果进行NMS，使用固定阈值0.4
            if all_matches:
                rectangles = np.array(all_matches)
                indices = cv2.dnn.NMSBoxes(
                    rectangles[:, :4].tolist(),
                    rectangles[:, 4].tolist(),
                    threshold,
                    0.4  # 直接使用固定值
                )
                
                if len(indices) > 0:
                    best_matches = rectangles[indices.flatten()]
                    logger.debug(f"[{template_name}] 检测到 {len(best_matches)} 个按钮"
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
        self.template_config['food'] = [f'{food_name}.png',f'{food_name}_1.png']
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
        """改进的图像预处理方法，处理复杂景"""
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
        """优化的cook按钮检测和点击"""
        if self.menu_clicks >= 3:
            # 降低阈值提高检测率
            cook_buttons = self.detect_buttons('cook', threshold=0.6)
            if cook_buttons and len(cook_buttons) > 0:
                logger.info("=== 检测到cook按钮，立即处理 ===")
                try:
                    cook_button = cook_buttons[0].tolist() if isinstance(cook_buttons[0], np.ndarray) else list(cook_buttons[0])
                    x, y, w, h, conf = cook_button
                    
                    # 立即点击,不等待
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)
                    pyautogui.click(center_x, center_y)
                    pyautogui.click(center_x, center_y)
                    logger.info(f"点击cook按钮 位置: ({center_x}, {center_y})")
                    
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
        """优化的视角旋转和按钮检测"""
        try:
            logger.info(f"开始旋转视角检测，当前菜单点击次数: {self.menu_clicks}")
            
            # 旋转前检测cook按钮
            if self.check_and_click_cook():
                return True
            
            # 获取窗口中心点
            screen_width, screen_height = pyautogui.size()
            center_x = screen_width // 2
            center_y = screen_height // 2
            
            # 计算偏右上的位置
            rotate_x = center_x + 200
            rotate_y = center_y - 200

            rotation_distance = 800  # 每次旋转的水平距离（像素）

            # 分段旋转,每段都检测按钮
            segment_distance = rotation_distance // 4
            mouse_is_down = False  # 跟踪鼠标状态
            
            for i in range(4):
                try:
                    logger.info(f"第 {i+1}/4 段旋转")
                    # 移动到起始位置
                    pyautogui.moveTo(rotate_x, rotate_y)
                    pyautogui.mouseDown(button='left')
                    mouse_is_down = True
                    
                    # 缓慢旋转一段距离
                    pyautogui.moveRel(segment_distance, 0, duration=0.1)
                    pyautogui.mouseUp(button='left')
                    mouse_is_down = False
                    
                    # 等待画面完全稳定
                    time.sleep(0.3)
                    
                    # 检测按钮
                    if self.state == CookingState.DETECT_MENU:
                        # 多次尝试检测菜单按钮
                        for attempt in range(2):
                            menu_buttons = self.detect_buttons('cook_menu')
                            logger.info(f"旋转检测第 {attempt+1} 次: 检测到 {len(menu_buttons)} 个按钮")
                            if menu_buttons:
                                if self.menu_clicks == 0:
                                    # 第一次必须检测到3个按钮
                                    if len(menu_buttons) >= 3:
                                        logger.info(f"=== 首次检测到 {len(menu_buttons)} 个菜单按钮，停止旋转 ===")
                                        return True
                                    else:
                                        logger.info("首次检测未满3个按钮，继续旋转")
                                        continue
                                else:
                                    # 后续只要检测到按钮就停止旋转
                                    logger.info(f"=== 检测到 {len(menu_buttons)} 个菜单按钮，已点击 {self.menu_clicks} 次，停止旋转 ===")
                                    return True
                            time.sleep(0.3)
                            
                    elif self.state == CookingState.DETECT_FINISH:
                        finish_buttons = self.detect_buttons('finish')
                        if finish_buttons and len(finish_buttons) > 0:
                            return True
                    
                    # 检测cook按钮
                    if self.check_and_click_cook():
                        return True
                    
                    # 继续下一段旋转前的等待
                    if i < 3:
                        time.sleep(0.3)
                        
                except Exception as e:
                    logger.error(f"旋转过程中出错: {e}")
                    if mouse_is_down:
                        pyautogui.mouseUp(button='left')
                        mouse_is_down = False
                    raise
            
            return True
                
        except Exception as e:
            logger.error(f"旋转视角失败: {e}")
            return False
            
        finally:
            # 确保在任何情况下都释放鼠标
            try:
                pyautogui.mouseUp(button='left')
            except:
                pass
    
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
        if (datetime.now() - self.state_start_time).seconds >= self.timeout:
            if self.retry_count < self.max_retries:
                self.retry_count += 1
                logger.warning(f"状态 {self.state} 超时，第 {self.retry_count} 次重试")
                time.sleep(0.5)  # 直接使用固定值
                return True
            else:
                logger.error(f"状态 {self.state} 超过最大重试次数")
                return False
        return True
    
    def change_state(self, new_state):
        """切换状态"""
        logger.info(f"状态切换: {self.state} -> {new_state}, 当前菜单点击次数: {self.menu_clicks}")
        self.state = new_state
        self.reset_state_timer()
    
    def handle_menu_state(self):
        """处理菜单检测状态"""
        # 如果已经点击过start按钮，优先检测cook按钮
        if self.start_clicks > 0:
            logger.info("已有start点击记录，优先检测cook按钮")
            cook_buttons = self.detect_buttons('cook', threshold=0.5)
            if cook_buttons and len(cook_buttons) > 0:
                logger.info("=== 检测到cook按钮，立即处理 ===")
                try:
                    cook_button = cook_buttons[0].tolist() if isinstance(cook_buttons[0], np.ndarray) else list(cook_buttons[0])
                    x, y, w, h, conf = cook_button
                    logger.info(f"cook按钮置信度: {conf:.2f}")
                    
                    # 立即点击,不等待
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)
                    pyautogui.click(center_x, center_y)
                    pyautogui.click(center_x, center_y)
                    logger.info(f"点击cook按钮 位置: ({center_x}, {center_y})")
                    
                    self.cook_clicks += 1
                    self.reset_rotation()
                    
                    # 检查菜单点击次数，决定下一个状态
                    if self.menu_clicks >= 3:
                        logger.info("菜单点击已完成3次，进入finish检测状态")
                        self.change_state(CookingState.DETECT_FINISH)
                    else:
                        logger.info(f"菜单点击次数不足（{self.menu_clicks}/3），继续点击菜单")
                        self.change_state(CookingState.CLICK_MENU)
                    return
                except Exception as e:
                    logger.error(f"处理cook按钮时出错: {e}")
        
        # 常规的菜单按钮检测逻辑，降低阈值到0.5
        menu_buttons=self.menu_buttons = self.detect_buttons('cook_menu', threshold=0.6)
        logger.info(f"当前状态: DETECT_MENU, 菜单点击次数: {self.menu_clicks}, 检测到按钮数: {len(menu_buttons)}")
        
        if len(menu_buttons) == 3 and self.menu_clicks == 0:
            logger.info("=== 检测到3个菜单按钮，开始点击流程 ===")
            self.reset_rotation()
            self.change_state(CookingState.CLICK_MENU)
            return
        elif len(menu_buttons) > 0 and self.menu_clicks > 0:
            logger.info(f"=== 检测到 {len(menu_buttons)} 个菜单按钮，已点击 {self.menu_clicks} 次，继续点击流程 ===")
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
        
        # 尝试旋转视角找菜单按钮
        if self.rotate_view():
            # 旋转找到按钮后，直接进入点击状态
            self.reset_rotation()
            self.change_state(CookingState.CLICK_MENU)
            return
        else:
            logger.warning("已旋转一圈仍未找到足够的菜单按钮")
            self.reset_rotation()
            if not self.handle_timeout():
                raise Exception("菜单检测超时")

    def handle_food_state(self):
        """处理食物检测状态 - 用保存的食物按钮位置"""
        try:
            # 确保有保存的食物按钮位置
            if not self.food_button_pos:
                logger.warning("未保存食物按钮位置，返回菜单检测状态")
                # self.change_state(CookingState.DETECT_MENU)
                return
            
            logger.info("=== 使用保存的食物按钮位置点击 ===")
            try:
                x, y, w, h, _ = self.food_button_pos
                center_x = int(x + w // 2)
                center_y = int(y + h // 2)
                
                pyautogui.click(center_x, center_y)
                pyautogui.click(center_x, center_y)  # 双击确保选中
                logger.info(f"点击食物按钮位置: ({center_x}, {center_y})")
                time.sleep(0.3)
                
                # 首次检测并保存开始按钮位置
                if not self.start_button_pos:
                    start_buttons = self.detect_buttons('cook_start', threshold=0.5)
                    if isinstance(start_buttons, list) and len(start_buttons) > 0:
                        logger.info("首次检测到开始按钮，保存位置")
                        self.start_button_pos = start_buttons[0].tolist() if isinstance(start_buttons[0], np.ndarray) else list(start_buttons[0])
                        self.food_clicked = True
                        self.change_state(CookingState.DETECT_START)
                    else:
                        logger.warning(f"未检测到开始按钮，第 {self.retry_count + 1}/3 次重试")
                        self.retry_count += 1
                        if self.retry_count >= 3:
                            logger.error("=== 连续3次未检测到开始按钮，程序将退出 ===")
                            self.should_exit = True  # 设置退出标记
                            raise Exception("完成所有操作")  # 触发程序退出
                        # 继续保持当前状态进行重试
                else:
                    self.food_clicked = True
                    self.change_state(CookingState.DETECT_START)
                    
            except Exception as e:
                if str(e) == "完成所有操作":
                    raise
                logger.error(f"点击食物按钮失败: {e}")
                if not self.handle_timeout():
                    raise Exception("食物点击超时")
                
        except Exception as e:
            if str(e) == "完成所有操作":
                raise
            logger.error(f"处理食物状态时出错: {e}")
            if not self.handle_timeout():
                raise Exception("食物状态处理超时")

    def handle_start_state(self):
        """处理开始按钮状态"""
        try:
            # 使用保存的开始按钮位置
            if not self.start_button_pos:
                logger.warning("未保存开始按钮位置，返回菜单检测状态")
                self.change_state(CookingState.DETECT_MENU)
                return
            
            logger.info("=== 使用保存的开始按钮位置点击 ===")
            try:
                x, y, w, h, _ = self.start_button_pos
                center_x = int(x + w // 2)
                center_y = int(y + h // 2)
                
                pyautogui.click(center_x, center_y)
                pyautogui.click(center_x, center_y)
                logger.info(f"点击开始按钮位置: ({center_x}, {center_y})")
                time.sleep(0.5)
                
                # 验证点击是否成功
                start_buttons = self.detect_buttons('cook_start', threshold=0.5)
                if not start_buttons or len(start_buttons) == 0:
                    logger.info("开始按钮点击成功（按钮消失）")
                    # 增加开始按钮点击计数
                    self.start_clicks += 1
                    logger.info(f"当前开始按钮点击次数: {self.start_clicks}")
                    
                    # 检查开始按钮点击次数
                    if self.start_clicks >= 3:
                        logger.info("=== 已完成3次开始按钮点击，进入完成状态 ===")
                        self.change_state(CookingState.DETECT_FINISH)  # 切换到 DETECT_FINISH
                    else:
                        logger.info(f"=== 开始按钮点击未完成（{self.start_clicks}/3），继续点击菜单 ===")
                        self.change_state(CookingState.DETECT_MENU)
                else:
                    logger.warning("开始按钮点击未生效，检测back按钮")
                    # 检测并点击back按钮
                    back_buttons = self.detect_buttons('back', threshold=0.5)
                    if back_buttons and len(back_buttons) > 0:
                        logger.info("=== 检测到back按钮，进行处理 ===")
                        try:
                            back_button = back_buttons[0].tolist() if isinstance(back_buttons[0], np.ndarray) else list(back_buttons[0])
                            x, y, w, h, conf = back_button
                            center_x = int(x + w // 2)
                            center_y = int(y + h // 2)
                            
                            pyautogui.click(center_x, center_y)
                            logger.info(f"点击back按钮 位置: ({center_x}, {center_y})")
                            time.sleep(0.5)
                            
                            # 直接进入finish状态并设置标记以结束程序
                            logger.warning("检测到back按钮，本轮结束后将停止程序")
                            self.should_exit = True  # 添加新的标记
                            self.change_state(CookingState.DETECT_FINISH)
                            return
                            
                        except Exception as e:
                            logger.error(f"点击back按钮失败: {e}")
                    
                    if not self.handle_timeout():
                        raise Exception("开始按钮点击超时")
                
            except Exception as e:
                logger.error(f"点击开始按钮失败: {e}")
                if not self.handle_timeout():
                    raise Exception("开始按钮点击超时")
                
        except Exception as e:
            logger.error(f"处理开始状态时出错: {e}")
            if not self.handle_timeout():
                raise Exception("开始状态处理超时")

    def handle_cook_state(self):
        """处理烹饪状态"""
        cook_buttons = self.detect_buttons('cook')
        if len(cook_buttons) > 0:
            logger.info(f"=== 点击烹饪按钮 ===")
            try:
                if self.click_button_with_verify(cook_buttons[0], 'finish', expected_count=3, wait_time=0.8):
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
                    raise Exception("烹饪按钮检测超时")

    def handle_finish_state(self):
        """处理完成状态 - finish按钮数量需要等于start成功点击次数"""
        try:
            finish_buttons = self.detect_buttons('finish')
            logger.info(f"检测到 {len(finish_buttons)} 个finish按钮，start成功点击次数: {self.start_clicks}")
            
            # 处理遗留的finish按钮（在菜单点击未满3次时）
            if self.menu_clicks < 3 and finish_buttons and len(finish_buttons) > 0 and self.start_clicks==0:
                logger.info("=== 检测到遗留的finish按钮，处理中 ===")
                try:
                    finish_button = finish_buttons[0].tolist() if isinstance(finish_buttons[0], np.ndarray) else list(finish_buttons[0])
                    x, y, w, h, _ = finish_button
                    pyautogui.click(int(x + w // 2), int(y + h // 2))
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
                    
            # 正常的finish处理（完成start点击后）
            if self.start_clicks > 0:  # 只要有成功的start点击就可以处理finish
                if finish_buttons and len(finish_buttons) >= self.start_clicks:  # finish按钮数量需要等于start点击次数
                    logger.info(f"=== 检测到 {len(finish_buttons)} 个finish按钮，开始点击 ===")
                    try:
                        # 点击检测到的每个finish按钮
                        for finish_button in finish_buttons:
                            button_data = finish_button.tolist() if isinstance(finish_button, np.ndarray) else list(finish_button)
                            x, y, w, h, conf = button_data
                            center_x = int(x + w // 2)
                            center_y = int(y + h // 2)
                            
                            logger.info(f"点击finish按钮 位置: ({center_x}, {center_y}), 置信度: {conf:.2f}")
                            pyautogui.click(center_x, center_y)
                            pyautogui.click(center_x, center_y)
                            time.sleep(0.5)  # 点击后短暂等待
                            
                            # 验证点击结果
                            verify_buttons = self.detect_buttons('finish')
                            if not verify_buttons or len(verify_buttons) < len(finish_buttons):
                                logger.info("finish按钮点击成功（按钮消失）")
                                self.finish_clicks += 1
                                logger.info(f"当前finish点击次数: {self.finish_clicks}")
                                if self.finish_clicks >= self.start_clicks:  # 修改这里，与start点击次数匹配
                                    logger.info("=== 完成所有finish按钮点击 ===")
                                    raise Exception("完成所有操作")
                            else:
                                logger.warning("finish按钮点击可能未生效")
                                
                    except Exception as e:
                        if str(e) == "完成所有操作":
                            raise
                        logger.error(f"点击finish按钮失败: {e}")
                else:
                    # 未检测到足够的finish按钮，继续寻找
                    logger.info(f"未检测到足够的finish按钮（当前: {len(finish_buttons)}, 需要: {self.start_clicks}），继续寻找")
                    if self.rotate_view():
                        # 旋转找到按钮后，再次验证按钮数量
                        finish_buttons = self.detect_buttons('finish')
                        if len(finish_buttons) < self.start_clicks:
                            logger.info(f"旋转后仍未找到足够的finish按钮（当前: {len(finish_buttons)}，需要: {self.start_clicks}），继续寻找")
                        self.reset_rotation()
                    else:
                        logger.info("完成一圈旋转，继续寻找finish按钮")
                        self.reset_rotation()
                    return  # 返回主循环继续检测
                        
        except Exception as e:
            if str(e) == "完成所有操作":
                raise
            logger.error(f"处理finish状态时出错: {e}")

    def handle_click_menu_state(self):
        """处理菜单点击状态"""
        try:
            menu_buttons = self.menu_buttons
            logger.info(f"点击菜单状态: 检测到 {len(menu_buttons)} 个按钮, 当前点击次数: {self.menu_clicks}")
            
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
            time.sleep(1.5)  # 增加等待时间，确保界面响应
            
            # 点击后验证：多次尝试检测食物或开始按钮
            max_verify_attempts = 3
            for attempt in range(max_verify_attempts):
                if self.food_clicked:
                    # 果已经选择过食物，使用保存的开始按钮位置
                    if self.start_button_pos:
                        logger.info("菜单点击成功，使用已保存的开始食物位置")
                        self.menu_clicks += 1
                        logger.info(f"当前菜单点击次数: {self.menu_clicks}")
                        self.change_state(CookingState.DETECT_START)
                        time.sleep(0.3)
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
                    logger.info(f"第 {attempt + 1} 次验证未检测到目标按钮，等待重试")
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

    def reset_state(self):
        """重置状态以开始新的循环"""
        self.state = CookingState.DETECT_MENU
        self.menu_clicks = 0      # 重置菜单点击次数
        self.start_clicks = 0     # 重置开始按钮点击次数
        self.finish_clicks = 0    # 重置完成按钮点击次数
        self.food_clicked = False # 重置食物点击状态
        self.food_button_pos = None  # 重置食物按钮位置
        self.start_button_pos = None # 重置开始按钮位置
        self.retry_count = 0      # 重置重试次数
        self.state_start_time = datetime.now()  # 重置状态计时器
        logger.info(f"=== 重置所有状态和计数器，准备开始第 {self.current_loop + 1} 次循环 ===")

    def run(self):
        """运行烹饪机器人"""
        try:
            self.should_exit = False  # 添加新的标记
            while self.running:
                if self.loop_count != -1 and self.current_loop >= self.loop_count:
                    logger.info(f"=== 完成所有 {self.loop_count} 次循环，程序结束 ===")
                    break

                try:
                    if self.state == CookingState.DETECT_MENU:
                        self.handle_menu_state()
                    elif self.state == CookingState.CLICK_MENU:
                        self.handle_click_menu_state()
                    elif self.state == CookingState.DETECT_FOOD:
                        self.handle_food_state()
                    elif self.state == CookingState.DETECT_START:
                        self.handle_start_state()
                    elif self.state == CookingState.DETECT_FINISH:
                        self.handle_finish_state()
                        
                except Exception as e:
                    if str(e) == "完成所有操作":
                        logger.info(f"=== 完成第 {self.current_loop + 1} 次循环 ===")
                        self.current_loop += 1
                        
                        # 检查是否需要退出程序
                        if self.should_exit:
                            logger.warning("=== 检测到back按钮，程序将停止 ===")
                            break
                        
                        if self.loop_count == -1 or self.current_loop < self.loop_count:
                            self.reset_state()
                            time.sleep(1)  # 循环间隔
                            continue
                        else:
                            logger.info(f"=== 完成所有 {self.loop_count} 次循环，程序结束 ===")
                            break
                    else:
                        raise
                        
                time.sleep(0.1)  # 主循环间隔
                
        except KeyboardInterrupt:
            logger.info("收到键盘中断信号，程序结束")
        except Exception as e:
            logger.error(f"程序运行出错: {e}")
        finally:
            self.executor.shutdown()
            logger.info("程序已退出")

    def get_optimized_screenshot(self):
        """获取优化后的截图"""
        current_time = time.time()
        if (self.last_screenshot is None or 
            current_time - self.last_screenshot_time >= 0.1):  # 直接使用固定值0.1
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
        
        # 调整坐标以匹配始幕
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
            
            # 计算并行点击
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='自动烹饪机器人')
    parser.add_argument('--food', type=str, default='葡萄酱', help='食物名称')
    parser.add_argument('--loop', type=int, default=10, help='循环次数，-1表示无限循环')
    
    args = parser.parse_args()
    
    try:
        bot = CookingBot(food_name=args.food, loop_count=args.loop)
            # 显示所有可用的食物模板
        available_foods = bot.get_available_foods()
        logger.info(f"可用的食物模板: {available_foods}")
        bot.run()
    except Exception as e:
        logger.error(f"程序运行失败: {e}")