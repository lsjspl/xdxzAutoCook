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
import win32gui
import win32con
import win32com.client

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

# 确保debug目录存在
os.makedirs("debug", exist_ok=True)


class CookingState(Enum):
    DETECT_MENU_AND_COOK = auto()  # 检测菜单和Cook按钮
    DETECT_FOOD_AND_START = auto()  # 检测食物和Start按钮
    DETECT_FINISH = auto()  # 检测Finish按钮


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
        
        # 添加鼠标状态显示相关变量
        self.mouse_position = None  # 当前鼠标位置
        self.mouse_is_down = False  # 鼠标按下状态
        self.mouse_circle_id = None  # 鼠标圆圈的Canvas ID
        self.drag_line_id = None    # 拖动线条的Canvas ID
        self.drag_start_pos = None  # 拖动起始位置

    def update_overlay(self, matches, button_name=None):
        """更新覆盖层显示
        
        Args:
            matches: 匹配的按钮列表，每个元素为 [x, y, w, h, conf]
            button_name: 按钮名称，如果提供则显示
        """
        self.canvas.delete('all')  # 清除之前的矩形

        for match in matches:
            x, y, w, h, conf = match
            # 绘制绿色矩形框
            self.canvas.create_rectangle(
                x, y, x + w, y + h,
                outline='green',
                width=5

            )
            # 显示按钮名称和置信度
            display_text = f'{conf:.2f}'
            if button_name:
                display_text = f'{button_name}: {display_text}'
                
            self.canvas.create_text(
                x, y - 10,
                text=display_text,
                fill='green',
                anchor='sw',
                font=('TkDefaultFont', 14, 'bold')  # 使用默认字体
            )
            
        # 重新绘制鼠标状态
        self.draw_mouse_state()
        
        self.root.update()
        
    def draw_mouse_state(self):
        """绘制鼠标状态"""
        if self.mouse_position:
            x, y = self.mouse_position
            
            # 绘制白色圆圈表示鼠标位置
            circle_radius = 10
            circle_color = 'yellow'
            circle_width = 2
            
            if self.mouse_is_down:
                # 如果鼠标按下，使用填充圆圈
                self.mouse_circle_id = self.canvas.create_oval(
                    x - circle_radius, y - circle_radius,
                    x + circle_radius, y + circle_radius,
                    outline=circle_color,
                    fill=circle_color,
                    width=circle_width
                )
                
                # 如果是拖动状态，绘制拖动线
                if self.drag_start_pos:
                    start_x, start_y = self.drag_start_pos
                    self.drag_line_id = self.canvas.create_line(
                        start_x, start_y, x, y,
                        fill=circle_color,
                        width=2,
                        dash=(4, 4)  # 虚线
                    )
            else:
                return
                # 如果鼠标释放，使用空心圆圈
                # self.mouse_circle_id = self.canvas.create_oval(
                #     x - circle_radius, y - circle_radius,
                #     x + circle_radius, y + circle_radius,
                #     outline=circle_color,
                #     width=circle_width
                # )
    
    def update_mouse_state(self, position, is_down, is_drag=False):
        """更新鼠标状态
        
        Args:
            position: 鼠标位置(x, y)
            is_down: 鼠标是否按下
            is_drag: 是否处于拖动状态
        """
        self.mouse_position = position
        self.mouse_is_down = is_down
        
        # 处理拖动状态
        if is_drag and is_down and self.drag_start_pos is None:
            # 开始拖动
            self.drag_start_pos = position
        elif not is_down:
            # 拖动结束
            self.drag_start_pos = None
            
        # 更新绘制
        self.draw_mouse_state()
        self.root.update()


class CookingBot:
    def __init__(self, food_name="food", loop_count=1):
        """
        初始化烹饪机器人
        :param food_name: 食物模板的名称（不包含.png后缀）
        :param loop_count: 循环执行次数，-1表示无限循环
        """
        # 查找并激活心动小镇窗口
        self.game_hwnd = None  # 存储游戏窗口句柄
        self.window_rect = None  # 存储游戏窗口位置和大小
        self.find_and_activate_game_window()

        self.state = CookingState.DETECT_MENU_AND_COOK
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
            'food': [f'{food_name}.png', f'{food_name}_1.png'],  # 动态食物模板
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
        
        # 添加菜单按钮位置缓存
        self.menu_button_positions = []  # 保存找到的3个菜单按钮位置
        self.found_menu_buttons = False  # 标记是否已找到3个菜单按钮
        self.cook_button_pos = None  # cook按钮位置，但不会长期缓存
        self.finish_button_positions = []  # 不会长期缓存finish按钮位置列表
        
        # 添加菜单按钮状态跟踪
        self.menu_buttons_finished = []  # 已完成(finish已点击)的菜单按钮索引列表
        self.all_finish_clicked = False  # 标记是否所有finish按钮都已点击

        # 优化模板匹配参数
        self.scale_factors = np.arange(0.5, 1.5, 0.1)

        # 优化截图缓存
        self.last_screenshot = None
        self.last_screenshot_time = 0

        self.start_clicks = 0  # 添加开始按钮点击计数器
        self.cook_clicks = 0  # 添加cook按钮点击计数器

    def find_and_activate_game_window(self):
        """查找并激活心动小镇窗口"""
        try:
            logger.info("开始查找心动小镇窗口...")
            # 用于存储窗口句柄和标题
            windows = []
            
            # 定义窗口枚举回调函数
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_title = win32gui.GetWindowText(hwnd)
                    if window_title:
                        windows.append((hwnd, window_title))
                return True
            
            # 枚举所有窗口
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            # 寻找包含"心动小镇"的窗口标题
            game_hwnd = None
            for hwnd, title in windows:
                if "心动小镇" in title:
                    game_hwnd = hwnd
                    logger.info(f"找到心动小镇窗口: {title}, 窗口句柄: {game_hwnd}")
                    break
            
            if game_hwnd:
                # 存储窗口句柄
                self.game_hwnd = game_hwnd
                
                # 获取窗口位置和大小信息
                self.update_window_rect()
                
                # 获取窗口状态
                window_placement = win32gui.GetWindowPlacement(game_hwnd)
                logger.info(f"窗口状态: {window_placement[1]}")  # 1=正常, 2=最小化, 3=最大化
                
                # 如果窗口最小化, 先恢复
                if window_placement[1] == win32con.SW_SHOWMINIMIZED:
                    logger.info("窗口已最小化, 正在恢复...")
                    win32gui.ShowWindow(game_hwnd, win32con.SW_RESTORE)
                    # 恢复后重新获取窗口位置
                    time.sleep(0.5)
                    self.update_window_rect()
                
                # 激活窗口并置于前台
                logger.info("正在激活心动小镇窗口...")
                
                # 有时SetForegroundWindow会失败, 需要先发送Alt键激活
                shell = win32com.client.Dispatch("WScript.Shell")
                shell.SendKeys('%')
                
                win32gui.SetForegroundWindow(game_hwnd)
                
                # 等待窗口切换完成
                time.sleep(1)
                logger.info("心动小镇窗口已激活")
                
                # 打印窗口尺寸信息
                if self.window_rect:
                    left, top, right, bottom = self.window_rect
                    width = right - left
                    height = bottom - top
                    logger.info(f"窗口位置: 左={left}, 上={top}, 宽={width}, 高={height}")
                
                return True
            else:
                logger.warning("未找到心动小镇窗口!")
                return False
                
        except Exception as e:
            logger.error(f"激活游戏窗口时出错: {e}")
            return False
    
    def update_window_rect(self):
        """更新窗口位置和大小信息"""
        if self.game_hwnd:
            try:
                # 获取窗口客户区矩形
                client_rect = win32gui.GetClientRect(self.game_hwnd)
                # 获取窗口屏幕坐标
                left, top, right, bottom = win32gui.GetWindowRect(self.game_hwnd)
                
                # 计算窗口边框尺寸
                border_left = 0
                border_top = 0
                
                # 如果不是全屏模式，需要计算标题栏和边框的偏移
                if right - left > 0 and bottom - top > 0 and client_rect[2] > 0 and client_rect[3] > 0:
                    # 计算左右边框宽度
                    total_border_width = (right - left) - client_rect[2]
                    border_left = total_border_width // 2
                    
                    # 计算标题栏和上边框高度
                    total_border_height = (bottom - top) - client_rect[3]
                    border_top = total_border_height - border_left  # 假设下边框与左右边框等宽
                
                # 计算客户区在屏幕上的位置
                client_left = left + border_left
                client_top = top + border_top
                client_right = client_left + client_rect[2]
                client_bottom = client_top + client_rect[3]
                
                # 保存窗口客户区位置
                self.window_rect = (client_left, client_top, client_right, client_bottom)
                return True
            except Exception as e:
                logger.error(f"更新窗口位置信息失败: {e}")
                self.window_rect = None
                return False
        return False
    
    def capture_window_screenshot(self):
        """截取游戏窗口的截图"""
        try:
            # 更新窗口位置和大小
            self.update_window_rect()
            
            if not self.window_rect:
                logger.warning("无法获取窗口位置，将使用全屏截图")
                return np.array(pyautogui.screenshot())
            
            left, top, right, bottom = self.window_rect
            width = right - left
            height = bottom - top
            
            if width <= 0 or height <= 0:
                logger.warning(f"窗口尺寸异常 (宽={width}, 高={height})，将使用全屏截图")
                return np.array(pyautogui.screenshot())
            
            # 使用pyautogui截取窗口区域
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            return np.array(screenshot)
        except Exception as e:
            logger.error(f"窗口截图失败: {e}")
            logger.info("回退到全屏截图")
            return np.array(pyautogui.screenshot())

    def get_screenshot(self):
        """获取屏幕截图，带缓存"""
        current_time = time.time()
        if (self.last_screenshot is None or
                current_time - self.last_screenshot_time >= 0.1):  # 直接使用固定值0.1
            # 使用窗口截图代替全屏截图
            self.last_screenshot = self.capture_window_screenshot()
            self.last_screenshot_time = current_time
        return self.last_screenshot

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
            # 使用窗口截图代替全屏截图
            screen = self.capture_window_screenshot()
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
                    self.overlay.update_overlay([selected_match], button_name=self.food_name)
                    return [selected_match]

            logger.info("[food] 未检测到食物按钮")
            self.overlay.update_overlay([], button_name=self.food_name)
            return []

        except Exception as e:
            logger.error(f"食物按钮检测失败: {e}")
            return []

    def detect_buttons(self, template_name, threshold=0.7):
        """添加调试信息的按钮检测"""
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

            # 保存处理后的截图用于调试
            cv2.imwrite('./debug/debug_screen.png', screen_processed)

            template_list = self.templates.get(template_name, [])
            if not template_list:
                logger.error(f"没有找到模板: {template_name}")
                return []

            all_matches = []

            for idx, template in enumerate(template_list):
                # 保存处理后的模板用于调试
                cv2.imwrite(f'./debug/debug_template_{template_name}_{idx}.png', template)

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

                    # 输出最大匹配值
                    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
                    logger.debug(f"模板 {template_name}_{idx} 在缩放 {scale:.2f} 下的最大匹配值: {max_val:.3f}")

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
                    self.overlay.update_overlay(best_matches, button_name=template_name)
                    return best_matches.tolist()

            logger.debug(f"[{template_name}] 未检测到按钮")
            self.overlay.update_overlay([], button_name=template_name)
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
        self.template_config['food'] = [f'{food_name}.png', f'{food_name}_1.png']
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
        """简化的图像预处理方法"""
        try:
            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 应用简单的高斯模糊去噪
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)

            # 自适应阈值分割
            thresh = cv2.adaptiveThreshold(
                blurred, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11, 2
            )

            return thresh

        except Exception as e:
            logger.error(f"图像预处理失败: {e}")
            return None

    def safe_exit(self):
        """安全退出，确保释放所有按键"""
        try:
            # 释放鼠标按键并更新显示
            pyautogui.mouseUp(button='left')
            # 获取当前鼠标位置
            current_pos = pyautogui.position()
            # 更新鼠标状态为释放
            self.overlay.update_mouse_state((current_pos.x, current_pos.y), False)
            
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
        """处理菜单和cook按钮检测状态，优先点击cook按钮"""
        try:
            # 确保窗口保持激活状态
            active_window_title = self.get_active_window_title()
            if active_window_title and "心动小镇" not in active_window_title:
                logger.warning("心动小镇窗口不在前台，尝试重新激活...")
                self.find_and_activate_game_window()
                time.sleep(0.5)  # 等待窗口激活
            
            # 1. 首先检测cook按钮，如果有就优先点击
            cook_buttons = self.detect_buttons('cook', threshold=0.6)
            if cook_buttons and len(cook_buttons) > 0:
                logger.info("=== 检测到cook按钮，优先处理 ===")
                try:
                    cook_button = cook_buttons[0].tolist() if isinstance(cook_buttons[0], np.ndarray) else list(
                        cook_buttons[0])
                    x, y, w, h, conf = cook_button
                    
                    # 点击cook按钮
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)
                    self.mouse_click(center_x, center_y, double_click=False)
                    logger.info(f"点击cook按钮 位置: ({center_x}, {center_y})")
                    self.cook_clicks += 1
                    
                    # cook点击成功后继续检测菜单按钮
                    time.sleep(0.5)
                    return
                except Exception as e:
                    logger.error(f"点击cook按钮失败: {e}")
            
            # 2. 检测finish按钮数量，如果有3个就进入finish状态
            finish_buttons = self.detect_buttons('finish')
            if finish_buttons and len(finish_buttons) >= 3:
                logger.info(f"=== 检测到 {len(finish_buttons)} 个finish按钮，进入finish处理状态 ===")
                self.finish_button_positions = finish_buttons[:3]  # 只取前3个
                self.change_state(CookingState.DETECT_FINISH)
                return
            
            # 3. 检测菜单按钮
            menu_buttons = self.detect_buttons('cook_menu', threshold=0.6)
            logger.info(f"当前状态: DETECT_MENU_AND_COOK, 检测到菜单按钮数: {len(menu_buttons)}, start点击次数: {self.start_clicks}")
            
            # 如果找到了菜单按钮，选择一个未点击过的进行点击
            if menu_buttons and len(menu_buttons) > 0:
                # 保存菜单按钮位置
                if len(menu_buttons) == 3 and not self.found_menu_buttons:
                    logger.info("=== 检测到3个菜单按钮，保存位置 ===")
                    self.found_menu_buttons = True
                
                    
                # 点击选中的菜单按钮
                menu_button = menu_buttons[0]
                
                try:
                    button_data = menu_button.tolist() if isinstance(menu_button, np.ndarray) else list(menu_button)
                    x, y, w, h, conf = button_data
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)

                    # 点击菜单按钮
                    logger.info(f"点击菜单按钮 位置: ({center_x}, {center_y})")
                    self.mouse_click(center_x, center_y, double_click=False)
                    time.sleep(0.5)
                    
                    # 点击菜单按钮后，进入食物和start按钮检测状态
                    self.change_state(CookingState.DETECT_FOOD_AND_START)
                    return
                except Exception as e:
                    logger.error(f"点击菜单按钮失败: {e}")
            
            # 如果仍未找到菜单按钮，等待一段时间后继续
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"处理菜单和cook按钮状态时出错: {e}")
            if not self.handle_timeout():
                raise Exception("菜单和cook按钮检测状态处理超时")
    
    def get_active_window_title(self):
        """获取当前活动窗口的标题"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        except Exception as e:
            logger.error(f"获取活动窗口标题失败: {e}")
            return None

    def handle_food_state(self):
        """处理食物和start按钮检测状态"""
        try:
            
            # 2. 检测食物按钮
            if not self.food_clicked:
                food_buttons = self.detect_food()
                if food_buttons and len(food_buttons) > 0:
                    logger.info("=== 检测到食物按钮，准备点击 ===")
                    try:
                        food_button = food_buttons[0].tolist() if isinstance(food_buttons[0], np.ndarray) else list(
                            food_buttons[0])
                        x, y, w, h, conf = food_button
                        
                        # 保存食物按钮位置以便后续使用
                        self.food_button_pos = food_button
                        
                        # 点击食物按钮
                        center_x = int(x + w // 2)
                        center_y = int(y + h // 2)
                        self.mouse_click(center_x, center_y, double_click=False)
                        logger.info(f"点击食物按钮 位置: ({center_x}, {center_y})")
                        time.sleep(0.5)
                        
                        # 食物点击成功，设置标记
                        self.food_clicked = True
                    except Exception as e:
                        logger.error(f"点击食物按钮失败: {e}")
            
            # 3. 检测start按钮
            start_buttons = self.detect_buttons('cook_start', threshold=0.5)
            if start_buttons and len(start_buttons) > 0:
                logger.info("=== 检测到start按钮，准备点击 ===")
                try:
                    start_button = start_buttons[0].tolist() if isinstance(start_buttons[0], np.ndarray) else list(
                        start_buttons[0])
                    x, y, w, h, conf = start_button
                    
                    # 保存start按钮位置以便后续使用
                    self.start_button_pos = start_button
                    
                    # 点击start按钮
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)
                    self.mouse_click(center_x, center_y, double_click=False)
                    logger.info(f"点击start按钮 位置: ({center_x}, {center_y})")
                    time.sleep(0.5)
                    
                    # 验证点击是否成功
                    verify_buttons = self.detect_buttons('cook_start', threshold=0.5)
                    if not verify_buttons or len(verify_buttons) == 0:
                        logger.info("start按钮点击成功（按钮消失）")
                        # 增加start按钮点击计数
                        self.start_clicks += 1
                        logger.info(f"当前start按钮点击次数: {self.start_clicks}")
                        
                        # 点击成功后返回菜单检测状态
                        self.change_state(CookingState.DETECT_MENU_AND_COOK)
                        return
                    else:
                        logger.warning("start按钮点击未生效，检测back按钮")
                        # 检测并点击back按钮
                        back_buttons = self.detect_buttons('back', threshold=0.5)
                        if back_buttons and len(back_buttons) > 0:
                            logger.info("=== 检测到back按钮，进行处理 ===")
                            back_button = back_buttons[0].tolist() if isinstance(back_buttons[0], np.ndarray) else list(
                                back_buttons[0])
                            x, y, w, h, conf = back_button
                            center_x = int(x + w // 2)
                            center_y = int(y + h // 2)
                            self.mouse_click(center_x, center_y, double_click=False)
                            logger.info(f"点击back按钮 位置: ({center_x}, {center_y})")
                            time.sleep(0.5)
                except Exception as e:
                    logger.error(f"点击start按钮失败: {e}")
            
            
            # 如果长时间未找到按钮，返回菜单检测状态
            if self.is_state_timeout():
                logger.warning("长时间未找到食物或start按钮，返回菜单检测状态")
                self.change_state(CookingState.DETECT_MENU_AND_COOK)
                return
            
            # 等待一段时间后继续检测
            time.sleep(0.5)
                
        except Exception as e:
            logger.error(f"处理食物和start按钮状态时出错: {e}")
            if not self.handle_timeout():
                raise Exception("食物和start按钮检测状态处理超时")


    def handle_finish_state(self):
        """处理finish按钮检测和点击状态"""
        try:
            
            logger.info(f"=== 开始依次点击 {len(self.finish_button_positions)} 个finish按钮 ===")
            for i, finish_button in enumerate(self.finish_button_positions):
                # 每次点击前检查cook按钮
                cook_buttons = self.detect_buttons('cook', threshold=0.6)
                if cook_buttons and len(cook_buttons) > 0:
                    logger.info("=== 点击finish前检测到cook按钮，优先处理 ===")
                    cook_button = cook_buttons[0].tolist() if isinstance(cook_buttons[0], np.ndarray) else list(
                        cook_buttons[0])
                    x, y, w, h, conf = cook_button
                    center_x = int(x + w // 2)
                    center_y = int(y + h // 2)
                    self.mouse_click(center_x, center_y, double_click=False)
                    logger.info(f"点击cook按钮 位置: ({center_x}, {center_y})")
                    self.cook_clicks += 1
                    self.change_state(CookingState.DETECT_MENU_AND_COOK)
                    return
                
                # 点击当前finish按钮
                button_data = finish_button.tolist() if isinstance(finish_button, np.ndarray) else list(finish_button)
                x, y, w, h, conf = button_data
                center_x = int(x + w // 2)
                center_y = int(y + h // 2)

                logger.info(f"点击finish按钮 {i+1}/3 位置: ({center_x}, {center_y}), 置信度: {conf:.2f}")
                self.mouse_click(center_x, center_y, double_click=False)
                time.sleep(0.5)  # 点击后短暂等待
                self.finish_clicks += 1
            
            # 4. 验证是否成功点击了所有finish按钮
            finish_buttons = self.detect_buttons('finish')
            if not finish_buttons or len(finish_buttons) == 0:
                logger.info("=== 成功点击了所有finish按钮（按钮数量减少） ===")
                # 清空保存的finish按钮位置
                self.finish_button_positions = []
                # 设置标记以便重置菜单按钮点击记录
                self.all_finish_clicked = True
                self.start_clicks = 0  # 重置start按钮点击计数器
                self.change_state(CookingState.DETECT_MENU_AND_COOK)
                return
            else:
                logger.warning(f"=== 点击后仍检测到 {len(finish_buttons)} 个finish按钮，尝试重新点击 ===")
                self.finish_button_positions = finish_buttons[:3]  # 更新finish按钮位置
            
            # 如果长时间未点击成功，返回菜单检测状态
            if self.is_state_timeout():
                logger.warning("长时间未成功点击finish按钮，返回菜单检测状态")
                self.finish_button_positions = []
                self.change_state(CookingState.DETECT_MENU_AND_COOK)
                return
                
        except Exception as e:
            logger.error(f"处理finish按钮状态时出错: {e}")
            # 发生错误时返回菜单检测状态
            self.change_state(CookingState.DETECT_MENU_AND_COOK)


    def reset_state(self):
        """重置状态以开始新的循环"""
        self.state = CookingState.DETECT_MENU_AND_COOK
        self.menu_clicks = 0  # 重置菜单点击次数
        self.start_clicks = 0  # 重置开始按钮点击次数
        self.finish_clicks = 0  # 重置finish按钮点击次数
        self.food_clicked = False  # 重置食物点击状态
        self.food_button_pos = None  # 重置食物按钮位置
        self.start_button_pos = None  # 重置开始按钮位置
        self.cook_button_pos = None  # 重置cook按钮位置
        self.finish_button_positions = []  # 重置finish按钮位置
        self.retry_count = 0  # 重置重试次数
        self.state_start_time = datetime.now()  # 重置状态计时器
        
        # 重置菜单按钮的点击和完成状态
        self.menu_buttons_clicked = []
        self.menu_buttons_finished = []
        
        # 只有当所有finish按钮都被点击后，才重置已点击菜单按钮的记录
        if self.all_finish_clicked:
            logger.info("=== 所有finish按钮都已点击，重置菜单按钮点击记录 ===")
            self.clicked_menu_indices = []
            self.all_finish_clicked = False
        else:
            logger.info(f"=== 保留已点击的菜单按钮记录: {self.clicked_menu_indices} ===")
        
        # 注意：不重置menu_button_positions和found_menu_buttons，
        # 这样新循环仍然可以使用之前找到的菜单按钮位置
        
        logger.info(f"=== 重置所有状态和计数器，准备开始第 {self.current_loop + 1} 次循环 ===")
        if self.found_menu_buttons:
            logger.info(f"=== 保留已找到的 {len(self.menu_button_positions)} 个菜单按钮位置 ===")
        else:
            logger.info("=== 尚未找到菜单按钮位置，需要重新旋转寻找 ===")


    def run(self):
        """运行烹饪机器人"""
        try:
            # 确保在开始主循环前窗口处于激活状态
            self.find_and_activate_game_window()
            logger.info("开始自动烹饪流程...")
            logger.info("使用窗口截图模式，只截取心动小镇窗口区域")
            
            self.should_exit = False  # 添加新的标记
            last_window_update_time = time.time()  # 记录上次窗口位置更新时间
            
            while self.running:
                if self.loop_count != -1 and self.current_loop >= self.loop_count:
                    logger.info(f"=== 完成所有 {self.loop_count} 次循环，程序结束 ===")
                    break
                
                # 每隔一段时间更新窗口位置信息，以处理窗口移动的情况
                current_time = time.time()
                if current_time - last_window_update_time >= 10:  # 每10秒更新一次窗口位置
                    self.update_window_rect()
                    last_window_update_time = current_time
                    if self.window_rect:
                        left, top, right, bottom = self.window_rect
                        width = right - left
                        height = bottom - top
                        logger.debug(f"更新窗口位置: 左={left}, 上={top}, 宽={width}, 高={height}")

                try:
                    # 根据当前状态调用相应的处理方法
                    if self.state == CookingState.DETECT_MENU_AND_COOK:
                        self.handle_menu_state()
                    elif self.state == CookingState.DETECT_FOOD_AND_START:
                        self.handle_food_state()
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

        roi = screen[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
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


    def click_button(self, button, template_name, expected_count=None, verify_start_button=False,
                                wait_time=1.0):
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

            # 使用新的鼠标点击方法
            self.mouse_click(center_x, center_y, double_click=False)
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


    def save_debug_images(self, template_name):
        """保存调试用的图像"""
        try:
            # 保存原始截图
            screen = self.get_screenshot()
            cv2.imwrite('debug/original_screen.png', cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))

            # 保存处理后的截图
            screen_processed = self.preprocess_image(cv2.cvtColor(screen, cv2.COLOR_RGB2BGR))
            cv2.imwrite('debug/processed_screen.png', screen_processed)

            # 保存模板图像
            template_list = self.templates.get(template_name, [])
            for idx, template in enumerate(template_list):
                cv2.imwrite(f'debug/template_{template_name}_{idx}.png', template)

            logger.info(f"调试图像已保存到 debug 目录")

        except Exception as e:
            logger.error(f"保存调试图像失败: {e}")

    def mouse_click(self, x, y, double_click=False, delay=0.1):
        """使用mouseDown和mouseUp模拟点击
        
        Args:
            x: 鼠标x坐标
            y: 鼠标y坐标
            double_click: 是否双击
            delay: 按下和释放之间的延迟
        """
        try:
            # 移动到位置
            # pyautogui.moveTo(x, y)
            # 更新鼠标位置显示（鼠标释放状态）
            self.overlay.update_mouse_state((x, y), False)
            
            # 第一次点击
            pyautogui.mouseDown(x=x, y=y, button='left')
            # 更新鼠标状态为按下
            self.overlay.update_mouse_state((x, y), True)
            time.sleep(delay)  # 按下后稍等片刻
            pyautogui.mouseUp(x=x, y=y, button='left')
            # 更新鼠标状态为释放
            self.overlay.update_mouse_state((x, y), False)
            
            # 如果是双击，再点击一次
            if double_click:
                time.sleep(0.05)  # 两次点击之间短暂停顿
                pyautogui.mouseDown(x=x, y=y, button='left')
                # 更新鼠标状态为按下
                self.overlay.update_mouse_state((x, y), True)
                time.sleep(delay)  # 按下后稍等片刻
                pyautogui.mouseUp(x=x, y=y, button='left')
                # 更新鼠标状态为释放
                self.overlay.update_mouse_state((x, y), False)
            
            logger.debug(f"模拟点击: ({x}, {y}), 双击: {double_click}")
            
        except Exception as e:
            logger.error(f"模拟点击失败: {e}")
            # 确保鼠标按键被释放
            try:
                pyautogui.mouseUp(button='left')
                # 更新鼠标状态为释放
                self.overlay.update_mouse_state((x, y), False)
            except:
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='自动烹饪机器人')
    parser.add_argument('--food', type=str, default='葡萄酱', help='食物名称')
    parser.add_argument('--loop', type=int, default=-1, help='循环次数，-1表示无限循环')

    args = parser.parse_args()

    try:
        bot = CookingBot(food_name=args.food, loop_count=args.loop)
        # 显示所有可用的食物模板
        available_foods = bot.get_available_foods()
        logger.info(f"可用的食物模板: {available_foods}")
        bot.run()
    except Exception as e:
        logger.error(f"程序运行失败: {e}")
