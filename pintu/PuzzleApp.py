import sys, json
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QGroupBox, QMessageBox,
                             QSizePolicy, QInputDialog, QLineEdit, QCheckBox,
                             QDialog, QScrollArea, QFormLayout, QSpinBox, QDoubleSpinBox)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QSize, QDir, QTimer, pyqtSignal, QThread
from PIL import Image
import cv2
import numpy as np
from screen_cropper import crop_screen_region, crop_interactive_region
from mapping_overlay import create_mapping_overlay
import os
from datetime import datetime
import time # Add time for sleep

# 自动拖动功能依赖 - 改用 ctypes 调用 Windows API
try:
    import ctypes
    from ctypes import wintypes, Structure, c_long, c_ulong, c_ushort, byref
    import pygetwindow as gw
    import random
    
    # 定义 Windows API 结构体
    class POINT(Structure):
        _fields_ = [("x", c_long), ("y", c_long)]
    
    class MOUSEINPUT(Structure):
        _fields_ = [("dx", c_long),
                   ("dy", c_long),
                   ("mouseData", wintypes.DWORD),
                   ("dwFlags", wintypes.DWORD),
                   ("time", wintypes.DWORD),
                   ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]
    
    class INPUT(Structure):
        class _INPUT(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT)]
        _anonymous_ = ("_input",)
        _fields_ = [("type", wintypes.DWORD),
                   ("_input", _INPUT)]
    
    # Windows API 常量
    INPUT_MOUSE = 0
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_LEFTDOWN = 0x0002
    MOUSEEVENTF_LEFTUP = 0x0004
    MOUSEEVENTF_ABSOLUTE = 0x8000
    
    AUTO_DRAG_ENABLED = True
except ImportError:
    AUTO_DRAG_ENABLED = False

try:
    import keyboard
    HOTKEY_ENABLED = True
except ImportError:
    HOTKEY_ENABLED = False
    
# 修复导入路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import isAdmin


def pil_to_qpixmap(pil_img):
    """Convert PIL image to QPixmap."""
    if pil_img.mode == "RGBA":
        img_format = QImage.Format_ARGB32
    elif pil_img.mode == "RGB":
        img_format = QImage.Format_RGB888
    else:
        pil_img = pil_img.convert("RGB")
        img_format = QImage.Format_RGB888
    
    return QPixmap.fromImage(QImage(pil_img.tobytes(), pil_img.width, pil_img.height, pil_img.width * len(pil_img.getbands()), img_format))

def draw_arrow(img, start_point, end_point, color=(0, 255, 0), thickness=3, arrow_size=10):
    """在图像上绘制箭头"""
    # 绘制主线
    cv2.line(img, start_point, end_point, color, thickness)
    
    # 计算箭头方向
    dx = end_point[0] - start_point[0]
    dy = end_point[1] - start_point[1]
    angle = np.arctan2(dy, dx)
    
    # 计算箭头端点
    arrow_angle1 = angle + np.pi/6
    arrow_angle2 = angle - np.pi/6
    
    arrow_x1 = int(end_point[0] - arrow_size * np.cos(arrow_angle1))
    arrow_y1 = int(end_point[1] - arrow_size * np.sin(arrow_angle1))
    arrow_x2 = int(end_point[0] - arrow_size * np.cos(arrow_angle2))
    arrow_y2 = int(end_point[1] - arrow_size * np.sin(arrow_angle2))
    
    # 绘制箭头
    cv2.line(img, end_point, (arrow_x1, arrow_y1), color, thickness)
    cv2.line(img, end_point, (arrow_x2, arrow_y2), color, thickness)

class DragThread(QThread):
    """拖动操作线程"""
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)
    request_new_target = pyqtSignal()  # 请求新的目标位置
    
    def __init__(self, drag_config, start_pos, end_pos, parent=None):
        super().__init__(parent)
        self.drag_config = drag_config
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.is_running = True
        self.new_target_callback = None  # 新目标位置的回调函数
        
    def run(self):
        try:
            self.perform_drag()
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
    
    def stop(self):
        self.is_running = False
    
    def perform_drag(self):
        if not self.is_running:
            return
            
        # 激活目标窗口
        window_title = self.drag_config.get('window_title', '心动小镇')
        game_windows = gw.getWindowsWithTitle(window_title)
        if not game_windows:
            self.error.emit(f"未找到 '{window_title}' 窗口")
            return
        
        game_win = game_windows[0]
        if game_win.isMinimized:
            game_win.restore()

        # 1. 尝试激活窗口
        try:
            game_win.activate()
        except Exception:
            # Fallback: 点击标题栏激活窗口
            x, y = game_win.left + 20, game_win.top + 10
            self.send_mouse_input(x, y, MOUSEEVENTF_LEFTDOWN)
            time.sleep(0.05)
            self.send_mouse_input(x, y, MOUSEEVENTF_LEFTUP)
        
        time.sleep(0.5)  # 等待窗口激活

        # 2. 验证窗口是否真的被激活
        active_window = gw.getActiveWindow()
        if not active_window or window_title not in active_window.title:
            self.error.emit(f"'{window_title}' 窗口未能激活")
            return

        # 3. 使用 SendInput 进行硬件级别的鼠标拖动
        start_x, start_y = int(self.start_pos[0]), int(self.start_pos[1])
        end_x, end_y = int(self.end_pos[0]), int(self.end_pos[1])

        # 先做一个小的鼠标摆动来"唤醒"游戏的输入检测
        wiggle_count = self.drag_config.get('wiggle_count', 3)
        wiggle_range = self.drag_config.get('wiggle_range', 2)
        wiggle_delay = self.drag_config.get('wiggle_delay', 0.05)
        
        for _ in range(wiggle_count):
            if not self.is_running:
                return
            wiggle_x = start_x + random.randint(-wiggle_range, wiggle_range)
            wiggle_y = start_y + random.randint(-wiggle_range, wiggle_range)
            self.send_mouse_input(wiggle_x, wiggle_y, MOUSEEVENTF_MOVE)
            time.sleep(wiggle_delay)

        # 移动到起始位置
        self.send_mouse_input(start_x, start_y, MOUSEEVENTF_MOVE)
        time.sleep(self.drag_config.get('move_delay', 0.15))

        # 按下鼠标左键
        self.send_mouse_input(start_x, start_y, MOUSEEVENTF_LEFTDOWN)
        time.sleep(self.drag_config.get('press_delay', 0.25))

        # 平滑拖动到目标位置，增加随机变化
        min_steps = self.drag_config.get('min_steps', 25)
        max_steps = self.drag_config.get('max_steps', 35)
        num_steps = random.randint(min_steps, max_steps)
        
        min_step_delay = self.drag_config.get('min_step_delay', 0.008)
        max_step_delay = self.drag_config.get('max_step_delay', 0.015)
        noise_range = self.drag_config.get('noise_range', 1)
        
        # 检查是否需要中途等待
        mid_drag_wait = self.drag_config.get('mid_drag_wait', False)
        mid_drag_wait_ratio = self.drag_config.get('mid_drag_wait_ratio', 0.5)
        mid_drag_wait_time = self.drag_config.get('mid_drag_wait_time', 0.5)
        
        wait_step = int(num_steps * mid_drag_wait_ratio) if mid_drag_wait else -1
        
        # 记录当前鼠标位置，用于中途重新计算路径
        current_x, current_y = start_x, start_y
        
        for i in range(1, num_steps + 1):
            if not self.is_running:
                return
            
            # 检查是否需要中途等待
            if i == wait_step:
                self.status_update.emit("中途等待中...")
                # 请求新的目标位置
                self.request_new_target.emit()
                time.sleep(mid_drag_wait_time)
                # 等待主线程更新目标位置
                time.sleep(0.1)  # 给主线程一点时间更新目标
                
                # 重新计算剩余路径
                remaining_steps = num_steps - i
                if remaining_steps > 0:
                    # 从当前位置到新目标位置（使用更新后的目标位置）
                    new_end_x, new_end_y = self.end_pos
                    self.status_update.emit(f"目标已更新: ({new_end_x:.0f}, {new_end_y:.0f})")
                    for j in range(1, remaining_steps + 1):
                        if not self.is_running:
                            return
                        
                        progress = j / remaining_steps
                        # 从当前位置到新目标位置
                        intermediate_x = current_x + int((new_end_x - current_x) * progress)
                        intermediate_y = current_y + int((new_end_y - current_y) * progress)
                        
                        # 添加小的随机偏移
                        noise_x = random.randint(-noise_range, noise_range)
                        noise_y = random.randint(-noise_range, noise_range)
                        intermediate_x += noise_x
                        intermediate_y += noise_y
                        
                        self.send_mouse_input(intermediate_x, intermediate_y, MOUSEEVENTF_MOVE)
                        current_x, current_y = intermediate_x, intermediate_y
                        
                        # 随机化移动速度
                        time.sleep(random.uniform(min_step_delay, max_step_delay))
                    
                    # 确保到达最终位置
                    self.send_mouse_input(new_end_x, new_end_y, MOUSEEVENTF_MOVE)
                    time.sleep(self.drag_config.get('final_delay', 0.1))
                    
                    # 松开鼠标左键
                    self.send_mouse_input(new_end_x, new_end_y, MOUSEEVENTF_LEFTUP)
                    return  # 提前结束，因为已经完成了拖动
                
                self.status_update.emit("继续拖动...")
            
            # 正常拖动逻辑
            progress = i / num_steps
            # 使用贝塞尔曲线来模拟更自然的移动轨迹
            intermediate_x = start_x + int((end_x - start_x) * progress)
            intermediate_y = start_y + int((end_y - start_y) * progress)
            
            # 添加小的随机偏移
            noise_x = random.randint(-noise_range, noise_range)
            noise_y = random.randint(-noise_range, noise_range)
            intermediate_x += noise_x
            intermediate_y += noise_y
            
            self.send_mouse_input(intermediate_x, intermediate_y, MOUSEEVENTF_MOVE)
            current_x, current_y = intermediate_x, intermediate_y
            
            # 随机化移动速度
            time.sleep(random.uniform(min_step_delay, max_step_delay))

        # 确保到达最终位置
        self.send_mouse_input(end_x, end_y, MOUSEEVENTF_MOVE)
        time.sleep(self.drag_config.get('final_delay', 0.1))

        # 松开鼠标左键
        self.send_mouse_input(end_x, end_y, MOUSEEVENTF_LEFTUP)
    
    def send_mouse_input(self, x, y, flags):
        """使用 SendInput API 发送鼠标事件"""
        # 获取屏幕尺寸用于坐标转换
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        
        # 转换为绝对坐标 (0-65535)
        if flags & MOUSEEVENTF_MOVE or flags & MOUSEEVENTF_LEFTDOWN or flags & MOUSEEVENTF_LEFTUP:
            abs_x = int(x * 65535 / screen_width)
            abs_y = int(y * 65535 / screen_height)
            flags |= MOUSEEVENTF_ABSOLUTE
        else:
            abs_x, abs_y = x, y

        # 创建 INPUT 结构体
        extra = ctypes.c_ulong(0)
        ii_ = INPUT()
        ii_.type = INPUT_MOUSE
        ii_.mi.dx = abs_x
        ii_.mi.dy = abs_y
        ii_.mi.mouseData = 0
        ii_.mi.dwFlags = flags
        ii_.mi.time = 0
        ii_.mi.dwExtraInfo = ctypes.pointer(extra)

        # 发送输入事件
        ctypes.windll.user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))


class DragSettingsDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("自动拖动设置")
        self.setModal(True)
        self.resize(400, 500)
        
        self.config = config.copy() if config else {}
        
        layout = QVBoxLayout(self)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 窗口设置
        window_group = QGroupBox("窗口设置")
        window_layout = QFormLayout()
        self.window_title_edit = QLineEdit(self.config.get('window_title', '心动小镇'))
        window_layout.addRow("目标窗口标题:", self.window_title_edit)
        window_group.setLayout(window_layout)
        scroll_layout.addWidget(window_group)
        
        # 鼠标摆动设置
        wiggle_group = QGroupBox("鼠标摆动设置")
        wiggle_layout = QFormLayout()
        self.wiggle_count_edit = QLineEdit(str(self.config.get('wiggle_count', 3)))
        self.wiggle_count_edit.setPlaceholderText("0-10")
        wiggle_layout.addRow("摆动次数:", self.wiggle_count_edit)
        
        self.wiggle_range_edit = QLineEdit(str(self.config.get('wiggle_range', 2)))
        self.wiggle_range_edit.setPlaceholderText("0-10")
        wiggle_layout.addRow("摆动范围(像素):", self.wiggle_range_edit)
        
        self.wiggle_delay_edit = QLineEdit(str(self.config.get('wiggle_delay', 0.05)))
        self.wiggle_delay_edit.setPlaceholderText("0.01-0.5")
        wiggle_layout.addRow("摆动间隔(秒):", self.wiggle_delay_edit)
        wiggle_group.setLayout(wiggle_layout)
        scroll_layout.addWidget(wiggle_group)
        
        # 移动设置
        move_group = QGroupBox("移动设置")
        move_layout = QFormLayout()
        self.move_delay_edit = QLineEdit(str(self.config.get('move_delay', 0.15)))
        self.move_delay_edit.setPlaceholderText("0.05-1.0")
        move_layout.addRow("移动后延时(秒):", self.move_delay_edit)
        
        self.press_delay_edit = QLineEdit(str(self.config.get('press_delay', 0.25)))
        self.press_delay_edit.setPlaceholderText("0.1-1.0")
        move_layout.addRow("按下后延时(秒):", self.press_delay_edit)
        move_group.setLayout(move_layout)
        scroll_layout.addWidget(move_group)
        
        # 拖动设置
        drag_group = QGroupBox("拖动设置")
        drag_layout = QFormLayout()
        self.min_steps_edit = QLineEdit(str(self.config.get('min_steps', 25)))
        self.min_steps_edit.setPlaceholderText("10-100")
        drag_layout.addRow("最小步数:", self.min_steps_edit)
        
        self.max_steps_edit = QLineEdit(str(self.config.get('max_steps', 35)))
        self.max_steps_edit.setPlaceholderText("10-100")
        drag_layout.addRow("最大步数:", self.max_steps_edit)
        
        self.min_step_delay_edit = QLineEdit(str(self.config.get('min_step_delay', 0.008)))
        self.min_step_delay_edit.setPlaceholderText("0.001-0.1")
        drag_layout.addRow("最小步进延时(秒):", self.min_step_delay_edit)
        
        self.max_step_delay_edit = QLineEdit(str(self.config.get('max_step_delay', 0.015)))
        self.max_step_delay_edit.setPlaceholderText("0.001-0.1")
        drag_layout.addRow("最大步进延时(秒):", self.max_step_delay_edit)
        
        self.noise_range_edit = QLineEdit(str(self.config.get('noise_range', 1)))
        self.noise_range_edit.setPlaceholderText("0-5")
        drag_layout.addRow("随机噪声范围:", self.noise_range_edit)
        drag_group.setLayout(drag_layout)
        scroll_layout.addWidget(drag_group)
        
        # 其他设置
        other_group = QGroupBox("其他设置")
        other_layout = QFormLayout()
        self.final_delay_edit = QLineEdit(str(self.config.get('final_delay', 0.1)))
        self.final_delay_edit.setPlaceholderText("0.05-0.5")
        other_layout.addRow("到达目标后延时(秒):", self.final_delay_edit)
        
        self.cooldown_edit = QLineEdit(str(self.config.get('cooldown_time', 800)))
        self.cooldown_edit.setPlaceholderText("100-2000")
        other_layout.addRow("冷却时间(毫秒):", self.cooldown_edit)
        other_group.setLayout(other_layout)
        scroll_layout.addWidget(other_group)
        
        # 中途等待设置
        mid_wait_group = QGroupBox("中途等待设置")
        mid_wait_layout = QFormLayout()
        
        self.mid_drag_wait_time_edit = QLineEdit(str(self.config.get('mid_drag_wait_time', 0.5)))
        self.mid_drag_wait_time_edit.setPlaceholderText("0.1-2.0")
        mid_wait_layout.addRow("等待时间(秒):", self.mid_drag_wait_time_edit)
        
        self.mid_drag_wait_ratio_edit = QLineEdit(str(self.config.get('mid_drag_wait_ratio', 0.5)))
        self.mid_drag_wait_ratio_edit.setPlaceholderText("0.1-0.9")
        mid_wait_layout.addRow("等待位置比例:", self.mid_drag_wait_ratio_edit)
        mid_wait_group.setLayout(mid_wait_layout)
        scroll_layout.addWidget(mid_wait_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept_and_save)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        scroll_layout.addLayout(button_layout)
        
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
    
    def reset_to_defaults(self):
        """重置为默认值"""
        self.window_title_edit.setText('心动小镇')
        self.wiggle_count_edit.setText('3')
        self.wiggle_range_edit.setText('2')
        self.wiggle_delay_edit.setText('0.05')
        self.move_delay_edit.setText('0.15')
        self.press_delay_edit.setText('0.25')
        self.min_steps_edit.setText('25')
        self.max_steps_edit.setText('35')
        self.min_step_delay_edit.setText('0.008')
        self.max_step_delay_edit.setText('0.015')
        self.final_delay_edit.setText('0.1')
        self.cooldown_edit.setText('800')
        self.noise_range_edit.setText('1')
        self.mid_drag_wait_time_edit.setText('0.5')
        self.mid_drag_wait_ratio_edit.setText('0.5')
    
    def get_config(self):
        """获取当前配置"""
        def safe_float(text, default):
            try:
                return float(text)
            except ValueError:
                return default
        
        def safe_int(text, default):
            try:
                return int(text)
            except ValueError:
                return default
        
        # 从父窗口获取mid_drag_wait的值
        mid_drag_wait = False
        if hasattr(self.parent(), 'drag_config'):
            mid_drag_wait = self.parent().drag_config.get('mid_drag_wait', False)
        
        return {
            'window_title': self.window_title_edit.text(),
            'wiggle_count': safe_int(self.wiggle_count_edit.text(), 3),
            'wiggle_range': safe_int(self.wiggle_range_edit.text(), 2),
            'wiggle_delay': safe_float(self.wiggle_delay_edit.text(), 0.05),
            'move_delay': safe_float(self.move_delay_edit.text(), 0.15),
            'press_delay': safe_float(self.press_delay_edit.text(), 0.25),
            'min_steps': safe_int(self.min_steps_edit.text(), 25),
            'max_steps': safe_int(self.max_steps_edit.text(), 35),
            'min_step_delay': safe_float(self.min_step_delay_edit.text(), 0.008),
            'max_step_delay': safe_float(self.max_step_delay_edit.text(), 0.015),
            'final_delay': safe_float(self.final_delay_edit.text(), 0.1),
            'cooldown_time': safe_int(self.cooldown_edit.text(), 800),
            'noise_range': safe_int(self.noise_range_edit.text(), 1),
            'mid_drag_wait': mid_drag_wait,
            'mid_drag_wait_time': safe_float(self.mid_drag_wait_time_edit.text(), 0.5),
            'mid_drag_wait_ratio': safe_float(self.mid_drag_wait_ratio_edit.text(), 0.5)
        }
    
    def accept_and_save(self):
        """确定并保存配置"""
        # 获取当前配置
        new_config = self.get_config()
        # 更新父窗口的配置
        if hasattr(self.parent(), 'drag_config'):
            self.parent().drag_config = new_config
            # 立即保存到文件
            self.parent().save_drag_config_to_file()
        # 关闭对话框
        self.accept()


class MatchSettingsDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("拼图匹配设置")
        self.setModal(True)
        self.resize(450, 600)
        
        self.config = config.copy() if config else {}
        
        layout = QVBoxLayout(self)
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # 搜索边距设置
        search_group = QGroupBox("搜索边距设置")
        search_layout = QFormLayout()
        self.search_margin_100_edit = QLineEdit(str(self.config.get('search_margin_100', 20)))
        self.search_margin_100_edit.setPlaceholderText("10-50")
        search_layout.addRow("100块拼图搜索边距:", self.search_margin_100_edit)
        
        self.search_margin_other_edit = QLineEdit(str(self.config.get('search_margin_other', 10)))
        self.search_margin_other_edit.setPlaceholderText("5-30")
        search_layout.addRow("其他块数搜索边距:", self.search_margin_other_edit)
        search_group.setLayout(search_layout)
        scroll_layout.addWidget(search_group)
        
        # 100块拼图权重设置
        weight_100_group = QGroupBox("100块拼图权重设置")
        weight_100_layout = QFormLayout()
        self.gray_weight_100_edit = QLineEdit(str(self.config.get('gray_weight_100', 0.4)))
        self.gray_weight_100_edit.setPlaceholderText("0.1-1.0")
        weight_100_layout.addRow("灰度匹配权重:", self.gray_weight_100_edit)
        
        self.hist_weight_100_edit = QLineEdit(str(self.config.get('hist_weight_100', 0.3)))
        self.hist_weight_100_edit.setPlaceholderText("0.1-1.0")
        weight_100_layout.addRow("直方图匹配权重:", self.hist_weight_100_edit)
        
        self.edge_weight_100_edit = QLineEdit(str(self.config.get('edge_weight_100', 0.2)))
        self.edge_weight_100_edit.setPlaceholderText("0.1-1.0")
        weight_100_layout.addRow("边缘匹配权重:", self.edge_weight_100_edit)
        weight_100_group.setLayout(weight_100_layout)
        scroll_layout.addWidget(weight_100_group)
        
        # 其他块数权重设置
        weight_other_group = QGroupBox("其他块数权重设置")
        weight_other_layout = QFormLayout()
        self.gray_weight_other_edit = QLineEdit(str(self.config.get('gray_weight_other', 0.5)))
        self.gray_weight_other_edit.setPlaceholderText("0.1-1.0")
        weight_other_layout.addRow("灰度匹配权重:", self.gray_weight_other_edit)
        
        self.hist_weight_other_edit = QLineEdit(str(self.config.get('hist_weight_other', 0.3)))
        self.hist_weight_other_edit.setPlaceholderText("0.1-1.0")
        weight_other_layout.addRow("直方图匹配权重:", self.hist_weight_other_edit)
        
        self.edge_weight_other_edit = QLineEdit(str(self.config.get('edge_weight_other', 0.15)))
        self.edge_weight_other_edit.setPlaceholderText("0.1-1.0")
        weight_other_layout.addRow("边缘匹配权重:", self.edge_weight_other_edit)
        weight_other_group.setLayout(weight_other_layout)
        scroll_layout.addWidget(weight_other_group)
        
        # 边缘检测设置
        edge_group = QGroupBox("边缘检测设置")
        edge_layout = QFormLayout()
        self.canny_low_edit = QLineEdit(str(self.config.get('canny_low', 50)))
        self.canny_low_edit.setPlaceholderText("10-100")
        edge_layout.addRow("Canny低阈值:", self.canny_low_edit)
        
        self.canny_high_edit = QLineEdit(str(self.config.get('canny_high', 150)))
        self.canny_high_edit.setPlaceholderText("100-300")
        edge_layout.addRow("Canny高阈值:", self.canny_high_edit)
        
        self.edge_match_weight_edit = QLineEdit(str(self.config.get('edge_match_weight', 0.5)))
        self.edge_match_weight_edit.setPlaceholderText("0.1-1.0")
        edge_layout.addRow("边缘匹配权重系数:", self.edge_match_weight_edit)
        edge_group.setLayout(edge_layout)
        scroll_layout.addWidget(edge_group)
        
        # 直方图设置
        hist_group = QGroupBox("直方图设置")
        hist_layout = QFormLayout()
        self.hist_bins_edit = QLineEdit(str(self.config.get('hist_bins', 8)))
        self.hist_bins_edit.setPlaceholderText("4-16")
        hist_layout.addRow("直方图bin数量:", self.hist_bins_edit)
        hist_group.setLayout(hist_layout)
        scroll_layout.addWidget(hist_group)
        
        # 其他设置
        other_group = QGroupBox("其他设置")
        other_layout = QFormLayout()
        self.position_bonus_weight_edit = QLineEdit(str(self.config.get('position_bonus_weight', 0.1)))
        self.position_bonus_weight_edit.setPlaceholderText("0.05-0.2")
        other_layout.addRow("位置奖励权重:", self.position_bonus_weight_edit)
        
        self.confidence_threshold_edit = QLineEdit(str(self.config.get('confidence_threshold', 0.6)))
        self.confidence_threshold_edit.setPlaceholderText("0.3-0.9")
        other_layout.addRow("置信度阈值:", self.confidence_threshold_edit)
        other_group.setLayout(other_layout)
        scroll_layout.addWidget(other_group)
        
        # 按钮
        button_layout = QHBoxLayout()
        reset_btn = QPushButton("重置默认")
        reset_btn.clicked.connect(self.reset_to_defaults)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(self.accept_and_save)
        button_layout.addWidget(ok_btn)
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        scroll_layout.addLayout(button_layout)
        
        scroll.setWidget(scroll_widget)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
    
    def reset_to_defaults(self):
        """重置为默认值"""
        self.search_margin_100_edit.setText('20')
        self.search_margin_other_edit.setText('10')
        self.gray_weight_100_edit.setText('0.4')
        self.hist_weight_100_edit.setText('0.3')
        self.edge_weight_100_edit.setText('0.2')
        self.gray_weight_other_edit.setText('0.5')
        self.hist_weight_other_edit.setText('0.3')
        self.edge_weight_other_edit.setText('0.15')
        self.canny_low_edit.setText('50')
        self.canny_high_edit.setText('150')
        self.edge_match_weight_edit.setText('0.5')
        self.hist_bins_edit.setText('8')
        self.position_bonus_weight_edit.setText('0.1')
        self.confidence_threshold_edit.setText('0.6')
    
    def get_config(self):
        """获取当前配置"""
        def safe_float(text, default):
            try:
                return float(text)
            except ValueError:
                return default
        
        def safe_int(text, default):
            try:
                return int(text)
            except ValueError:
                return default
        
        return {
            'search_margin_100': safe_int(self.search_margin_100_edit.text(), 20),
            'search_margin_other': safe_int(self.search_margin_other_edit.text(), 10),
            'gray_weight_100': safe_float(self.gray_weight_100_edit.text(), 0.4),
            'hist_weight_100': safe_float(self.hist_weight_100_edit.text(), 0.3),
            'edge_weight_100': safe_float(self.edge_weight_100_edit.text(), 0.2),
            'gray_weight_other': safe_float(self.gray_weight_other_edit.text(), 0.5),
            'hist_weight_other': safe_float(self.hist_weight_other_edit.text(), 0.3),
            'edge_weight_other': safe_float(self.edge_weight_other_edit.text(), 0.15),
            'canny_low': safe_int(self.canny_low_edit.text(), 50),
            'canny_high': safe_int(self.canny_high_edit.text(), 150),
            'hist_bins': safe_int(self.hist_bins_edit.text(), 8),
            'position_bonus_weight': safe_float(self.position_bonus_weight_edit.text(), 0.1),
            'confidence_threshold': safe_float(self.confidence_threshold_edit.text(), 0.6),
            'edge_match_weight': safe_float(self.edge_match_weight_edit.text(), 0.5)
        }
    
    def accept_and_save(self):
        """确定并保存配置"""
        # 获取当前配置
        new_config = self.get_config()
        # 更新父窗口的配置
        if hasattr(self.parent(), 'match_config'):
            self.parent().match_config = new_config
            # 立即保存到文件
            self.parent().save_match_config_to_file()
        # 关闭对话框
        self.accept()


class PuzzleApp(QWidget):
    stop_detection_signal = pyqtSignal()
    start_detection_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        # 设置主界面窗口始终置顶
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("🧩 拼图匹配工具（交互式截图）")

        self.reference_img = None
        self.puzzle_img = None
        self.mapping_area = None
        self.mapping_overlay = None
        self.cropper = None # To hold reference to the cropper widget
        
        # 添加拼图区域坐标和定时器
        self.puzzle_region = None  # 保存拼图区域坐标 (x, y, width, height)
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self.auto_detect_and_match)
        self.is_detecting = False
        self.is_dragging = False # a flag to prevent concurrent drags
        self.is_hotkey_setup = False
        self.drag_thread = None  # 拖动线程
        
        # 自动拖动配置
        self.drag_config = {
            'wiggle_count': 3,           # 鼠标摆动次数
            'wiggle_range': 2,           # 摆动范围
            'wiggle_delay': 0.05,        # 摆动间隔
            'move_delay': 0.15,          # 移动到起始位置后的延时
            'press_delay': 0.25,         # 按下鼠标后的延时
            'min_steps': 25,             # 最小移动步数
            'max_steps': 35,             # 最大移动步数
            'min_step_delay': 0.008,     # 最小步进延时
            'max_step_delay': 0.015,     # 最大步进延时
            'final_delay': 0.1,          # 到达目标位置后的延时
            'cooldown_time': 800,        # 冷却时间
            'noise_range': 1,            # 随机噪声范围
            'window_title': '心动小镇',  # 目标窗口标题
            'mid_drag_wait': False,      # 是否在拖动中途等待
            'mid_drag_wait_time': 0.5,   # 中途等待时间
            'mid_drag_wait_ratio': 0.5   # 中途等待位置比例
        }
        
        # 拼图匹配配置
        self.match_config = {
            'search_margin_100': 20,     # 100块拼图的搜索边距
            'search_margin_other': 10,   # 其他块数的搜索边距
            'gray_weight_100': 0.4,      # 100块拼图的灰度匹配权重
            'hist_weight_100': 0.3,      # 100块拼图的直方图匹配权重
            'edge_weight_100': 0.2,      # 100块拼图的边缘匹配权重
            'gray_weight_other': 0.5,    # 其他块数的灰度匹配权重
            'hist_weight_other': 0.3,    # 其他块数的直方图匹配权重
            'edge_weight_other': 0.15,   # 其他块数的边缘匹配权重
            'canny_low': 50,             # Canny边缘检测低阈值
            'canny_high': 150,           # Canny边缘检测高阈值
            'hist_bins': 8,              # 直方图bin数量
            'position_bonus_weight': 0.1, # 位置奖励权重
            'confidence_threshold': 0.6,  # 置信度阈值
            'edge_match_weight': 0.5     # 边缘匹配权重系数
        }
        
        self.configs_dir = os.path.join("pintu", "configs")
        self.configs_img_dir = os.path.join(self.configs_dir, "images")
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
        if not os.path.exists(self.configs_img_dir):
            os.makedirs(self.configs_img_dir)

        # 不再创建截图目录，因为不再保存截图到本地

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 减少主布局边距
        main_layout.setSpacing(8)  # 减少主布局间距

        # --- Config Management UI ---
        config_group = QGroupBox("配置管理")
        config_layout = QHBoxLayout()
        self.config_combo = QComboBox()
        self.config_combo.currentTextChanged.connect(self.on_config_changed)
        config_layout.addWidget(self.config_combo, 1)

        btn_load_config = QPushButton("加载")
        btn_load_config.clicked.connect(self.load_config)
        config_layout.addWidget(btn_load_config)

        btn_save_config = QPushButton("保存")
        btn_save_config.clicked.connect(self.save_config)
        config_layout.addWidget(btn_save_config)

        btn_delete_config = QPushButton("删除")
        btn_delete_config.clicked.connect(self.delete_config)
        config_layout.addWidget(btn_delete_config)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Button layout
        button_layout = QHBoxLayout()

        button_layout.addWidget(QLabel("① 拼图块数:"))
        self.block_combo = QComboBox()
        self.block_combo.addItems(["16", "36", "64", "100"])
        button_layout.addWidget(self.block_combo)
        
        self.btn_get_ref = QPushButton("② 选择完成拼图")
        self.btn_get_ref.clicked.connect(self.get_reference)
        button_layout.addWidget(self.btn_get_ref)
        
        self.btn_select_mapping = QPushButton("③ 选择映射区域")
        self.btn_select_mapping.clicked.connect(self.select_mapping_area)
        button_layout.addWidget(self.btn_select_mapping)

        self.btn_get_puzzle = QPushButton("④ 选择拼图区")
        self.btn_get_puzzle.clicked.connect(self.get_puzzle_region)
        button_layout.addWidget(self.btn_get_puzzle)
        
        # 添加开始/停止检测按钮
        self.btn_toggle_detection = QPushButton("⑤ 开始检测 (S)")
        self.btn_toggle_detection.clicked.connect(self.toggle_detection)
        self.btn_toggle_detection.setEnabled(False)
        button_layout.addWidget(self.btn_toggle_detection)

        button_layout.addStretch()

        button_group = QGroupBox("操作")
        
        # 使用垂直布局来容纳两行控件
        group_vbox = QVBoxLayout()
        group_vbox.addLayout(button_layout) # 第一行：按钮

        # 第二行：选项
        options_layout = QHBoxLayout()
        
        self.show_mapping_checkbox = QCheckBox("显示映射")
        self.show_mapping_checkbox.stateChanged.connect(self.toggle_overlay_visibility)
        # 初始状态：如果没有映射区域，禁用复选框
        self.show_mapping_checkbox.setEnabled(False)
        options_layout.addWidget(self.show_mapping_checkbox)
        
        # 添加显示箭头选项
        self.arrow_checkbox = QCheckBox("显示箭头")
        self.arrow_checkbox.setChecked(True)
        options_layout.addWidget(self.arrow_checkbox)
        
        # 添加自动拖动选项
        self.auto_drag_checkbox = QCheckBox("自动拖动")
        options_layout.addWidget(self.auto_drag_checkbox)
        if not AUTO_DRAG_ENABLED:
            self.auto_drag_checkbox.setToolTip("需要安装 pyautogui 和 pygetwindow 库: pip install pyautogui pygetwindow")
            self.auto_drag_checkbox.setEnabled(False)
        
        # 添加启用中途等待选项
        self.mid_drag_wait_checkbox = QCheckBox("启用中途等待")
        self.mid_drag_wait_checkbox.stateChanged.connect(self.on_mid_drag_wait_changed)
        self.mid_drag_wait_checkbox.setEnabled(AUTO_DRAG_ENABLED)
        options_layout.addWidget(self.mid_drag_wait_checkbox)
        
        # 添加自动拖动设置按钮
        self.btn_drag_settings = QPushButton("拖动设置")
        self.btn_drag_settings.clicked.connect(self.show_drag_settings)
        self.btn_drag_settings.setEnabled(AUTO_DRAG_ENABLED)
        options_layout.addWidget(self.btn_drag_settings)
        
        # 添加拼图匹配设置按钮
        self.btn_match_settings = QPushButton("匹配设置")
        self.btn_match_settings.clicked.connect(self.show_match_settings)
        options_layout.addWidget(self.btn_match_settings)
            
        options_layout.addStretch()
        group_vbox.addLayout(options_layout)

        button_group.setLayout(group_vbox)
        main_layout.addWidget(button_group)

        # Preview layout
        preview_layout = QHBoxLayout()
        
        # Reference preview
        ref_group = QGroupBox("完整图预览")
        ref_vbox = QVBoxLayout()
        self.ref_label = QLabel("未截图")
        self.ref_label.setFixedSize(200, 150)
        self.ref_label.setAlignment(Qt.AlignCenter)
        self.ref_label.setStyleSheet("border: 1px solid grey;")
        ref_vbox.addWidget(self.ref_label)
        ref_group.setLayout(ref_vbox)
        preview_layout.addWidget(ref_group)
        
        # Puzzle preview
        puzzle_group = QGroupBox("拼图区预览")
        puzzle_vbox = QVBoxLayout()
        self.puzzle_label = QLabel("未截图")
        self.puzzle_label.setFixedSize(200, 150)
        self.puzzle_label.setAlignment(Qt.AlignCenter)
        self.puzzle_label.setStyleSheet("border: 1px solid grey;")
        puzzle_vbox.addWidget(self.puzzle_label)
        puzzle_group.setLayout(puzzle_vbox)
        preview_layout.addWidget(puzzle_group)

        main_layout.addLayout(preview_layout)

        # Result display
        result_group = QGroupBox("匹配结果")
        result_layout = QHBoxLayout()  # 改为水平布局
        result_layout.setContentsMargins(5, 5, 5, 5)  # 减少边距
        result_layout.setSpacing(10)  # 设置合适的间距
        
        # 左侧文字区域
        self.result_text = QLabel()
        self.result_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.result_text.setFont(QFont("Arial", 9))
        self.result_text.setMinimumWidth(200)  # 设置文字区域最小宽度
        self.result_text.setMaximumWidth(250)  # 限制文字区域最大宽度
        result_layout.addWidget(self.result_text)
        
        # 右侧图片区域
        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_label.setMinimumSize(400, 250)  # 调整为更合理的尺寸
        self.result_label.setMaximumSize(600, 350)  # 限制最大尺寸
        result_layout.addWidget(self.result_label, 1)  # 给图片更多空间
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)

        # Status bar
        self.status_bar = QLabel("等待截图")
        self.status_bar.setStyleSheet("color: blue;")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.setMinimumSize(700, 750)  # 调整为更合理的窗口大小

        # Connect signal for thread-safe stopping
        self.stop_detection_signal.connect(self.handle_stop_request)
        # Connect signal for thread-safe starting
        self.start_detection_signal.connect(self.handle_start_request)
        
        self.populate_configs_dropdown()
        
        # 程序启动时自动加载配置
        self.load_drag_config_from_file()
        self.load_match_config_from_file()
        
        # 检查当前配置的拼图区域状态并更新按钮
        self.update_detection_button_state()
        
        # 检查当前配置的映射区域状态并更新复选框
        self.update_mapping_checkbox_state()

    def handle_stop_request(self):
        """A thread-safe slot to stop detection when the hotkey is pressed."""
        if self.is_detecting:
            self.toggle_detection()
            self.status_bar.setText("ℹ️ 检测已通过 P 键停止。")
            self.status_bar.setStyleSheet("color: blue;")

    def handle_start_request(self):
        """A thread-safe slot to start detection when the hotkey is pressed."""
        if not self.is_detecting and self.btn_toggle_detection.isEnabled():
            self.toggle_detection()
            self.status_bar.setText("ℹ️ 检测已通过 S 键开始。")
            self.status_bar.setStyleSheet("color: blue;")

    def on_p_pressed(self):
        """Callback for the keyboard library, emits a signal to the main thread."""
        self.stop_detection_signal.emit()

    def on_s_pressed(self):
        """Callback for the keyboard library, emits a signal to the main thread."""
        self.start_detection_signal.emit()

    def perform_auto_drag(self, start_pos, end_pos):
        if self.is_dragging:
            return # Prevent concurrent drags
        
        # 停止之前的拖动线程
        if self.drag_thread and self.drag_thread.isRunning():
            self.drag_thread.stop()
            self.drag_thread.wait()
        
        # 创建新的拖动线程
        self.drag_thread = DragThread(self.drag_config, start_pos, end_pos, self)
        self.drag_thread.finished.connect(self.on_drag_finished)
        self.drag_thread.error.connect(self.on_drag_error)
        self.drag_thread.status_update.connect(self.on_drag_status_update)
        self.drag_thread.request_new_target.connect(self.on_request_new_target)
        
        self.is_dragging = True
        self.drag_thread.start()
    
    def on_request_new_target(self):
        """处理新目标位置请求"""
        # 这里可以触发一次新的检测来获取最新的最佳匹配
        # 由于检测是自动进行的，我们只需要等待下一次检测结果
        self.status_bar.setText("🔄 等待新的最佳匹配...")
        self.status_bar.setStyleSheet("color: blue;")
    
    def update_drag_target(self, new_end_pos):
        """更新拖动线程的目标位置"""
        if self.drag_thread and self.drag_thread.isRunning():
            old_pos = self.drag_thread.end_pos
            self.drag_thread.end_pos = new_end_pos
            print(f"目标位置已更新: 从 {old_pos} 到 {new_end_pos}")
    
    def on_drag_finished(self):
        """拖动完成回调"""
        self.is_dragging = False
        cooldown_time = self.drag_config.get('cooldown_time', 800)
        QTimer.singleShot(cooldown_time, lambda: None)  # 冷却时间
    
    def on_drag_error(self, error_msg):
        """拖动错误回调"""
        self.status_bar.setText(f"❌ 自动拖动失败: {error_msg}")
        self.status_bar.setStyleSheet("color: red;")
        self.is_dragging = False
    
    def on_drag_status_update(self, status_msg):
        """拖动状态更新回调"""
        self.status_bar.setText(f"🔄 {status_msg}")
        self.status_bar.setStyleSheet("color: blue;")
    
    def on_mid_drag_wait_changed(self, state):
        """中途等待选项状态变化处理"""
        self.drag_config['mid_drag_wait'] = (state == Qt.Checked)
        # 自动保存配置
        self.save_drag_config_to_file()
        self.status_bar.setText("✅ 中途等待设置已保存")
        self.status_bar.setStyleSheet("color: green;")
        QTimer.singleShot(2000, lambda: self.status_bar.setText("等待截图"))

    def show_drag_settings(self):
        """显示拖动设置对话框"""
        dialog = DragSettingsDialog(self, self.drag_config)
        if dialog.exec_() == QDialog.Accepted:
            self.status_bar.setText("✅ 拖动设置已更新并保存")
            self.status_bar.setStyleSheet("color: green;")
            QTimer.singleShot(2000, lambda: self.status_bar.setText("等待截图"))
    
    def show_match_settings(self):
        """显示拼图匹配设置对话框"""
        dialog = MatchSettingsDialog(self, self.match_config)
        if dialog.exec_() == QDialog.Accepted:
            self.status_bar.setText("✅ 匹配设置已更新并保存")
            self.status_bar.setStyleSheet("color: green;")
            QTimer.singleShot(2000, lambda: self.status_bar.setText("等待截图"))
    
    def save_drag_config_to_file(self):
        """将当前拖动配置保存到文件"""
        try:
            drag_config_file = os.path.join(self.configs_dir, "drag_config.json")
            with open(drag_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.drag_config, f, indent=4, ensure_ascii=False)
            print(f"拖动配置已保存到: {drag_config_file}")
        except Exception as e:
            print(f"保存拖动配置失败: {e}")
    
    def load_drag_config_from_file(self):
        """从文件加载拖动配置"""
        try:
            drag_config_file = os.path.join(self.configs_dir, "drag_config.json")
            if os.path.exists(drag_config_file):
                with open(drag_config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                # 完全替换当前配置，而不是更新
                self.drag_config = saved_config
                print(f"拖动配置已从文件加载: {drag_config_file}")
            else:
                # 如果文件不存在，保存默认配置
                self.save_drag_config_to_file()
                print("创建默认拖动配置文件")
            
            # 更新主界面的中途等待复选框状态
            if hasattr(self, 'mid_drag_wait_checkbox'):
                self.mid_drag_wait_checkbox.setChecked(self.drag_config.get('mid_drag_wait', False))
        except Exception as e:
            print(f"加载拖动配置失败: {e}")
            # 如果加载失败，保存默认配置
            self.save_drag_config_to_file()
    
    def save_match_config_to_file(self):
        """将当前匹配配置保存到文件"""
        try:
            match_config_file = os.path.join(self.configs_dir, "match_config.json")
            with open(match_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.match_config, f, indent=4, ensure_ascii=False)
            print(f"匹配配置已保存到: {match_config_file}")
        except Exception as e:
            print(f"保存匹配配置失败: {e}")
    
    def load_match_config_from_file(self):
        """从文件加载匹配配置"""
        try:
            match_config_file = os.path.join(self.configs_dir, "match_config.json")
            if os.path.exists(match_config_file):
                with open(match_config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                # 完全替换当前配置，而不是更新
                self.match_config = saved_config
                print(f"匹配配置已从文件加载: {match_config_file}")
            else:
                # 如果文件不存在，保存默认配置
                self.save_match_config_to_file()
                print("创建默认匹配配置文件")
        except Exception as e:
            print(f"加载匹配配置失败: {e}")
            # 如果加载失败，保存默认配置
            self.save_match_config_to_file()

    def update_detection_button_state(self):
        """检查当前配置的拼图区域状态并更新检测按钮"""
        config_name = self.config_combo.currentText()
        if config_name == "选择一个配置...":
            # 如果没有选择配置，禁用检测按钮
            self.btn_toggle_detection.setEnabled(False)
            return
            
        configs_file = os.path.join(self.configs_dir, "configs.json")
        if not os.path.exists(configs_file):
            self.btn_toggle_detection.setEnabled(False)
            return
            
        try:
            with open(configs_file, 'r', encoding='utf-8') as f:
                configs_data = json.load(f)
            
            if config_name not in configs_data:
                self.btn_toggle_detection.setEnabled(False)
                return
                
            config_data = configs_data[config_name]
            saved_puzzle_region = config_data.get("puzzle_region")
            
            if saved_puzzle_region:
                # 如果配置中有拼图区域，启用检测按钮
                self.btn_toggle_detection.setEnabled(True)
                # 更新拼图区域按钮状态
                self.btn_get_puzzle.setText("④ 拼图区已设置")
                self.btn_get_puzzle.setStyleSheet("background-color: lightgreen;")
            else:
                # 如果配置中没有拼图区域，禁用检测按钮
                self.btn_toggle_detection.setEnabled(False)
                # 更新拼图区域按钮状态
                self.btn_get_puzzle.setText("④ 选择拼图区")
                self.btn_get_puzzle.setStyleSheet("")
        except Exception as e:
            print(f"检查拼图区域状态失败: {e}")
            self.btn_toggle_detection.setEnabled(False)

    def update_mapping_checkbox_state(self):
        """检查当前配置的映射区域状态并更新显示映射复选框"""
        config_name = self.config_combo.currentText()
        if config_name == "选择一个配置...":
            # 如果没有选择配置，禁用复选框
            self.show_mapping_checkbox.setEnabled(False)
            return
            
        configs_file = os.path.join(self.configs_dir, "configs.json")
        if not os.path.exists(configs_file):
            self.show_mapping_checkbox.setEnabled(False)
            return
            
        try:
            with open(configs_file, 'r', encoding='utf-8') as f:
                configs_data = json.load(f)
            
            if config_name not in configs_data:
                self.show_mapping_checkbox.setEnabled(False)
                return
                
            config_data = configs_data[config_name]
            saved_mapping_area = config_data.get("mapping_area")
            
            if saved_mapping_area:
                # 只要映射区域已设置就启用复选框
                self.show_mapping_checkbox.setEnabled(True)
                # 更新映射区域按钮状态
                self.btn_select_mapping.setText("③ 映射区已设置")
                self.btn_select_mapping.setStyleSheet("background-color: lightgreen;")
            else:
                # 如果配置中没有映射区域，禁用复选框
                self.show_mapping_checkbox.setEnabled(False)
                # 更新映射区域按钮状态
                self.btn_select_mapping.setText("③ 选择映射区域")
                self.btn_select_mapping.setStyleSheet("")
        except Exception as e:
            print(f"检查映射区域状态失败: {e}")
            self.show_mapping_checkbox.setEnabled(False)

    def on_config_changed(self):
        """配置下拉框变化时的处理"""
        # 更新检测按钮状态
        self.update_detection_button_state()
        # 更新映射复选框状态
        self.update_mapping_checkbox_state()

    def send_mouse_input(self, x, y, flags):
        """使用 SendInput API 发送鼠标事件"""
        # 获取屏幕尺寸用于坐标转换
        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)
        
        # 转换为绝对坐标 (0-65535)
        if flags & MOUSEEVENTF_MOVE or flags & MOUSEEVENTF_LEFTDOWN or flags & MOUSEEVENTF_LEFTUP:
            abs_x = int(x * 65535 / screen_width)
            abs_y = int(y * 65535 / screen_height)
            flags |= MOUSEEVENTF_ABSOLUTE
        else:
            abs_x, abs_y = x, y

        # 创建 INPUT 结构体
        extra = ctypes.c_ulong(0)
        ii_ = INPUT()
        ii_.type = INPUT_MOUSE
        ii_.mi.dx = abs_x
        ii_.mi.dy = abs_y
        ii_.mi.mouseData = 0
        ii_.mi.dwFlags = flags
        ii_.mi.time = 0
        ii_.mi.dwExtraInfo = ctypes.pointer(extra)

        # 发送输入事件
        ctypes.windll.user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))

    def populate_configs_dropdown(self):
        self.config_combo.clear()
        self.config_combo.addItem("选择一个配置...")
        
        configs_file = os.path.join(self.configs_dir, "configs.json")
        if os.path.exists(configs_file):
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                for config_name in sorted(configs_data.keys()):
                    self.config_combo.addItem(config_name)
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def save_config(self):
        if self.reference_img is None or self.mapping_area is None:
            QMessageBox.warning(self, "错误", "请先截取完整图并选择映射区域后再保存。")
            return
        
        # 检查是否有拼图区域（可选）
        if self.puzzle_region is None:
            reply = QMessageBox.question(self, '确认保存', 
                                        "当前未设置拼图区域，保存的配置将不包含拼图区域位置。\n是否继续保存？",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
            if reply == QMessageBox.No:
                return

        config_name, ok = QInputDialog.getText(self, "保存配置", "请输入配置名称:", QLineEdit.Normal, "")
        if not (ok and config_name):
            return # User cancelled
        
        # Sanitize filename
        config_name = "".join(c for c in config_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        if not config_name:
            QMessageBox.warning(self, "错误", "配置名称无效。")
            return
            
        configs_file = os.path.join(self.configs_dir, "configs.json")
        
        # 检查配置是否已存在
        existing_configs = {}
        if os.path.exists(configs_file):
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    existing_configs = json.load(f)
            except Exception as e:
                print(f"读取现有配置失败: {e}")
        
        if config_name in existing_configs:
            reply = QMessageBox.question(self, '覆盖确认', f"配置 '{config_name}' 已存在。要覆盖它吗？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        # Save reference image
        ref_img_filename = f"{config_name}.png"
        ref_img_path = os.path.abspath(os.path.join(self.configs_img_dir, ref_img_filename))
        print(f"Saving reference image to: {ref_img_path}")
        # 使用 imencode 替代 imwrite 来处理中文路径
        # 将RGB转换为BGR用于保存
        ref_img_bgr = cv2.cvtColor(self.reference_img, cv2.COLOR_RGB2BGR)
        ret, img_encoded = cv2.imencode('.png', ref_img_bgr)
        if ret:
            with open(ref_img_path, 'wb') as f:
                f.write(img_encoded.tobytes())
        else:
            raise Exception("图片编码失败")

        config_data = {
            "name": config_name,
            "reference_image_path": ref_img_path,
            "mapping_area": {
                "x": self.mapping_area['x'],
                "y": self.mapping_area['y'],
                "width": self.mapping_area['width'],
                "height": self.mapping_area['height'],
            },
            "puzzle_region": self.puzzle_region,  # 保存拼图区域位置
            "block_count": int(self.block_combo.currentText()),
            "show_arrow": self.arrow_checkbox.isChecked(),
        }

        try:
            # 将新配置添加到现有配置中
            existing_configs[config_name] = config_data
            
            # 保存所有配置到单个文件
            with open(configs_file, 'w', encoding='utf-8') as f:
                json.dump(existing_configs, f, indent=4, ensure_ascii=False)
            
            self.status_bar.setText(f"✅ 配置 '{config_name}' 已保存。")
            self.populate_configs_dropdown()
            self.config_combo.setCurrentText(config_name)
            # 更新检测按钮状态
            self.update_detection_button_state()
            # 更新映射复选框状态
            self.update_mapping_checkbox_state()
        except Exception as e:
            self.status_bar.setText(f"❌ 保存配置失败: {e}")
            self.status_bar.setStyleSheet("color: red;")

    def load_config(self):
        config_name = self.config_combo.currentText()
        if config_name == "选择一个配置...":
            return

        configs_file = os.path.join(self.configs_dir, "configs.json")
        if not os.path.exists(configs_file):
            QMessageBox.warning(self, "错误", f"配置文件 'configs.json' 未找到。")
            self.populate_configs_dropdown()
            return
            
        try:
            with open(configs_file, 'r', encoding='utf-8') as f:
                configs_data = json.load(f)
            
            if config_name not in configs_data:
                QMessageBox.warning(self, "错误", f"配置 '{config_name}' 未找到。")
                self.populate_configs_dropdown()
                return
                
            config_data = configs_data[config_name]

            # Load reference image
            ref_img_path = config_data.get("reference_image_path")
            if not (ref_img_path and os.path.exists(ref_img_path)):
                 QMessageBox.critical(self, "错误", f"引用的图片文件不存在:\n{ref_img_path}")
                 return
                 
            # 使用 numpy 读取文件，避免 cv2.imread 的中文路径问题
            img_array = np.fromfile(ref_img_path, dtype=np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_bgr is None:
                 QMessageBox.critical(self, "错误", f"无法加载图片:\n{ref_img_path}")
                 return

            # 转换为RGB格式存储
            self.reference_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(self.reference_img)
            self.display_reference_preview(pil_img)
            
            # 更新完整图按钮状态
            self.btn_get_ref.setText("② 完整图已设置")
            self.btn_get_ref.setStyleSheet("background-color: lightgreen;")

            # Load mapping area
            self.mapping_area = config_data.get("mapping_area")
            if self.mapping_overlay:
                self.mapping_overlay.close()
            
            if self.mapping_area:
                self.mapping_overlay = create_mapping_overlay(
                    self.mapping_area['x'], self.mapping_area['y'], 
                    self.mapping_area['width'], self.mapping_area['height'],
                    config_data.get("block_count", 36)
                )
                self.mapping_overlay.closed.connect(self.on_overlay_closed)
                # 只要映射区域已设置就启用复选框
                self.show_mapping_checkbox.setEnabled(True)
                self.show_mapping_checkbox.setChecked(True)
            else:
                self.mapping_overlay = None
                self.show_mapping_checkbox.setEnabled(False)
                self.show_mapping_checkbox.setChecked(False)
            
            # 更新映射区域按钮状态
            self.btn_select_mapping.setText("③ 映射区已设置")
            self.btn_select_mapping.setStyleSheet("background-color: lightgreen;")

            # Load block count
            block_count_str = str(config_data.get("block_count", "36"))
            index = self.block_combo.findText(block_count_str)
            if index != -1:
                self.block_combo.setCurrentIndex(index)

            # 恢复显示箭头选项
            self.arrow_checkbox.setChecked(config_data.get("show_arrow", True))
            
            # 加载拼图区域位置
            saved_puzzle_region = config_data.get("puzzle_region")
            if saved_puzzle_region:
                self.puzzle_region = saved_puzzle_region
                # 更新拼图区域按钮状态
                self.btn_get_puzzle.setText("④ 拼图区已设置")
                self.btn_get_puzzle.setStyleSheet("background-color: lightgreen;")
                # 启用检测按钮
                self.btn_toggle_detection.setEnabled(True)
            else:
                self.puzzle_region = None
                self.btn_get_puzzle.setText("④ 选择拼图区")
                self.btn_get_puzzle.setStyleSheet("")
                # 禁用检测按钮
                self.btn_toggle_detection.setEnabled(False)
            
            self.status_bar.setText(f"✅ 配置 '{config_name}' 已加载。")
            
            self.status_bar.setStyleSheet("color: green;")
            
            # 清除预览
            self.puzzle_label.setText("未截图") # Clear puzzle preview
            self.puzzle_label.setStyleSheet("border: 1px solid grey;")
            self.result_text.clear()
            self.result_label.clear()

        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载配置 '{config_name}' 失败: {e}")
            self.status_bar.setText(f"❌ 加载配置失败: {e}")
            self.status_bar.setStyleSheet("color: red;")
            
    def delete_config(self):
        config_name = self.config_combo.currentText()
        if config_name == "选择一个配置...":
            return

        reply = QMessageBox.question(self, '删除确认', f"确定要删除配置 '{config_name}' 吗？此操作不可撤销。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        configs_file = os.path.join(self.configs_dir, "configs.json")
        img_path_to_delete = None

        if os.path.exists(configs_file):
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                
                if config_name in configs_data:
                    img_path_to_delete = configs_data[config_name].get("reference_image_path")
                    # 从配置中删除指定配置
                    del configs_data[config_name]
                    
                    # 保存更新后的配置
                    with open(configs_file, 'w', encoding='utf-8') as f:
                        json.dump(configs_data, f, indent=4, ensure_ascii=False)
                else:
                    self.status_bar.setText(f"❌ 配置 '{config_name}' 不存在")
                    return
            except Exception as e:
                self.status_bar.setText(f"❌ 删除配置文件失败: {e}")
                return

        if img_path_to_delete and os.path.exists(img_path_to_delete):
            try:
                os.remove(img_path_to_delete)
            except Exception as e:
                 self.status_bar.setText(f"❌ 删除图片文件失败: {e}")
                 # continue to update UI

        self.status_bar.setText(f"✅ 配置 '{config_name}' 已删除。")
        self.populate_configs_dropdown()
        # 更新检测按钮状态
        self.update_detection_button_state()
        # 更新映射复选框状态
        self.update_mapping_checkbox_state()

    def save_screenshot(self, img, prefix):
        """Save screenshot to a file."""
        # 不再保存截图到本地
        return None

    def get_reference(self):
        self.status_bar.setText("请拖拽截图...")
        self.cropper = crop_screen_region(self.on_reference_cropped, return_position=False)

    def on_reference_cropped(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                # 直接使用RGB格式存储，避免颜色转换
                self.reference_img = np.array(img)
                self.display_reference_preview(img)
                self.save_screenshot(img, "reference")
                self.status_bar.setText(f"✅ 完整图已截取")
                self.status_bar.setStyleSheet("color: green;")
                
                # 更新按钮状态
                self.btn_get_ref.setText("② 完整图已设置")
                self.btn_get_ref.setStyleSheet("background-color: lightgreen;")
            except Exception as e:
                self.status_bar.setText(f"❌ 截图失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 截图取消或失败")
            self.status_bar.setStyleSheet("color: red;")

    def get_puzzle_region(self):
        self.status_bar.setText("请拖拽选择拼图区域...")
        self.cropper = crop_screen_region(self.on_puzzle_region_selected, return_position=True)

    def on_puzzle_region_selected(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                # 保存截图区域的坐标信息
                if position:
                    x, y = position
                    width, height = img.size
                    self.puzzle_region = (x, y, width, height)
                else:
                    # 如果无法获取坐标，使用默认值
                    self.puzzle_region = (0, 0, img.size[0], img.size[1])
                
                # 直接使用RGB格式存储，避免颜色转换
                self.puzzle_img = np.array(img)
                self.display_puzzle_preview(img)
                self.save_screenshot(img, "puzzle")
                self.status_bar.setText(f"✅ 拼图区域已选择")
                self.status_bar.setStyleSheet("color: green;")
                
                # 更新按钮状态
                self.btn_get_puzzle.setText("④ 拼图区已设置")
                self.btn_get_puzzle.setStyleSheet("background-color: lightgreen;")
                
                # 启用检测按钮
                self.btn_toggle_detection.setEnabled(True)
                
                # 立即执行一次匹配
                self.auto_detect_and_match()
            except Exception as e:
                self.status_bar.setText(f"❌ 选择拼图区域失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 选择拼图区域取消或失败")
            self.status_bar.setStyleSheet("color: red;")

    def on_puzzle_cropped(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                # 直接使用RGB格式存储，避免颜色转换
                self.puzzle_img = np.array(img)
                self.display_puzzle_preview(img)
                self.save_screenshot(img, "puzzle")
                self.status_bar.setText(f"✅ 拼图区已截取，开始自动匹配...")
                self.status_bar.setStyleSheet("color: green;")
                self.puzzle_region = (position[0], position[1], img.size[0], img.size[1])
                
                # 更新按钮状态
                self.btn_get_puzzle.setText("④ 拼图区已设置")
                self.btn_get_puzzle.setStyleSheet("background-color: lightgreen;")
                
                self.auto_detect_and_match()
            except Exception as e:
                self.status_bar.setText(f"❌ 截图失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 截图取消或失败")
            self.status_bar.setStyleSheet("color: red;")

    def select_mapping_area(self):
        if self.reference_img is None:
            QMessageBox.critical(self, "错误", "请先截图完整图")
            return
            
        self.status_bar.setText("请拖拽选择映射区域...")
        self.cropper = crop_screen_region(self.on_mapping_area_selected, return_position=True)
        
    def on_mapping_area_selected(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                ref_height, ref_width = self.reference_img.shape[:2]
                # 保存截图区域的坐标信息
                if position:
                    x, y = position
                    width, height = img.size
                else:
                    # 如果无法获取坐标，使用默认值
                    x, y = 0, 0
                    width, height = img.size
                
                self.mapping_area = {
                    'img': img, 'width': width, 'height': height,
                    'ref_width': ref_width, 'ref_height': ref_height,
                    'x': x, 'y': y
                }
                
                if self.mapping_overlay:
                    self.mapping_overlay.close()
                
                self.mapping_overlay = create_mapping_overlay(
                    x, y, width, height,
                    int(self.block_combo.currentText())
                )
                self.mapping_overlay.closed.connect(self.on_overlay_closed)
                
                self.show_mapping_checkbox.setEnabled(True)
                self.show_mapping_checkbox.setChecked(True)
                
                # 更新按钮状态
                self.btn_select_mapping.setText("③ 映射区已设置")
                self.btn_select_mapping.setStyleSheet("background-color: lightgreen;")
                
                self.status_bar.setText(f"✅ 映射区域已选择: {width}×{height}")
                self.status_bar.setStyleSheet("color: green;")
            except Exception as e:
                self.status_bar.setText(f"❌ 选择映射区域失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 选择映射区域失败")
            self.status_bar.setStyleSheet("color: red;")
    
    def on_overlay_closed(self):
        self.mapping_overlay = None
        self.show_mapping_checkbox.blockSignals(True)
        self.show_mapping_checkbox.setChecked(False)
        # 只要映射区域已设置就不禁用复选框
        if self.mapping_area:
            self.show_mapping_checkbox.setEnabled(True)
        else:
            self.show_mapping_checkbox.setEnabled(False)
        self.show_mapping_checkbox.blockSignals(False)


    def toggle_overlay_visibility(self, state):
        # 只要映射区域已设置就不禁用复选框
        if not self.mapping_area:
            self.show_mapping_checkbox.setChecked(False)
            self.show_mapping_checkbox.setEnabled(False)
            return
        
        # 启用复选框
        self.show_mapping_checkbox.setEnabled(True)
        
        # 如果勾选了显示
        if state == Qt.Checked:
            # 如果没有overlay实例，创建它
            if not self.mapping_overlay:
                self.mapping_overlay = create_mapping_overlay(
                    self.mapping_area['x'], self.mapping_area['y'],
                    self.mapping_area['width'], self.mapping_area['height'],
                    int(self.block_combo.currentText())
                )
                self.mapping_overlay.closed.connect(self.on_overlay_closed)
            # 显示overlay
            self.mapping_overlay.show()
        else:
            # 如果取消勾选，隐藏overlay
            if self.mapping_overlay:
                self.mapping_overlay.hide()

    def auto_detect_and_match(self):
        if self.reference_img is None or self.puzzle_region is None:
            self.status_bar.setText("❌ 请先截图完整图并选择拼图区域")
            self.status_bar.setStyleSheet("color: red;")
            return
            
        try:
            # 每次都重新截取屏幕指定区域
            x, y, width, height = self.puzzle_region
            
            # 使用PIL截取屏幕区域
            from PIL import ImageGrab
            puzzle_img_pil = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            puzzle_cv = np.array(puzzle_img_pil)
            
            # 更新保存的拼图图像和预览
            self.puzzle_img = puzzle_cv
            self.display_puzzle_preview(puzzle_img_pil)
            
            block_count = int(self.block_combo.currentText())
            grid_map = {16: (4, 4), 36: (6, 6), 64: (8, 8), 100: (10, 10)}
            grid_rows, grid_cols = grid_map.get(block_count, (6, 6))
            
            ref_height, ref_width = self.reference_img.shape[:2]
            puzzle_height, puzzle_width = puzzle_cv.shape[:2]
            
            ref_tile_width = ref_width // grid_cols
            ref_tile_height = ref_height // grid_rows
            
            # 计算拼图块的实际大小（基于拼图区域和网格）
            puzzle_tile_width = puzzle_width // grid_cols
            puzzle_tile_height = puzzle_height // grid_rows
            
            # 转为灰度图像
            puzzle_gray = cv2.cvtColor(puzzle_cv, cv2.COLOR_BGR2GRAY)
            ref_gray = cv2.cvtColor(self.reference_img, cv2.COLOR_RGB2GRAY)
            
            matches = []
            
            # 使用多种匹配策略
            # 根据块数调整搜索边距
            if block_count == 100:
                search_margin = max(self.match_config['search_margin_100'], min(ref_tile_width, ref_tile_height) // 4)
            else:
                search_margin = max(self.match_config['search_margin_other'], min(ref_tile_width, ref_tile_height) // 8)
            
            # 对每个网格位置进行匹配
            for row in range(grid_rows):
                for col in range(grid_cols):
                    tile_x = col * ref_tile_width
                    tile_y = row * ref_tile_height
                    
                    # 扩大搜索区域
                    search_x1 = max(0, tile_x - search_margin)
                    search_y1 = max(0, tile_y - search_margin)
                    search_x2 = min(ref_width, tile_x + ref_tile_width + search_margin)
                    search_y2 = min(ref_height, tile_y + ref_tile_height + search_margin)
                    
                    # 提取参考图中的搜索区域
                    search_area_gray = ref_gray[search_y1:search_y2, search_x1:search_x2]
                    search_area_color = self.reference_img[search_y1:search_y2, search_x1:search_x2]
                    
                    # 提取拼图块（当前整个拼图区域）
                    puzzle_block_gray = puzzle_gray
                    puzzle_block_color = puzzle_cv
                    
                    # 根据块数调整拼图块大小
                    search_h, search_w = search_area_gray.shape[:2]
                    puzzle_h, puzzle_w = puzzle_block_gray.shape[:2]
                    
                    # 对于非100块的拼图，需要放大到和完整拼图中单个块一样大
                    if block_count != 100:
                        # 计算目标大小：完整拼图中单个块的大小
                        target_width = ref_tile_width
                        target_height = ref_tile_height
                        
                        # 计算缩放比例
                        scale_x = target_width / puzzle_w
                        scale_y = target_height / puzzle_h
                        scale = min(scale_x, scale_y)  # 保持宽高比
                        
                        # 放大拼图块
                        new_w = int(puzzle_w * scale)
                        new_h = int(puzzle_h * scale)
                        puzzle_block_gray = cv2.resize(puzzle_block_gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                        puzzle_block_color = cv2.resize(puzzle_block_color, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                        
                        # 只在第一次匹配时显示缩放信息
                        if row == 0 and col == 0:
                            self.status_bar.setText(f"🔍 {block_count}块拼图 - 缩放比例: {scale:.2f}x, 目标大小: {target_width}x{target_height}")
                    else:
                        # 100块拼图保持原有逻辑：如果太大则缩小
                        if puzzle_h > search_h or puzzle_w > search_w:
                            scale_h = search_h / puzzle_h
                            scale_w = search_w / puzzle_w
                            scale = min(scale_h, scale_w)
                            new_h = int(puzzle_h * scale)
                            new_w = int(puzzle_w * scale)
                            puzzle_block_gray = cv2.resize(puzzle_block_gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
                            puzzle_block_color = cv2.resize(puzzle_block_color, (new_w, new_h), interpolation=cv2.INTER_AREA)
                    
                    # 多策略匹配
                    confidences = []
                    
                    # 策略1: 灰度图像模板匹配
                    methods = [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED, cv2.TM_SQDIFF_NORMED]
                    for method in methods:
                        try:
                            res = cv2.matchTemplate(search_area_gray, puzzle_block_gray, method)
                            if method == cv2.TM_SQDIFF_NORMED:
                                _, min_val, _, _ = cv2.minMaxLoc(res)
                                confidences.append(1.0 - min_val)  # 转换为相似度
                            else:
                                _, max_val, _, _ = cv2.minMaxLoc(res)
                                confidences.append(max_val)
                        except:
                            confidences.append(0.0)
                    
                    # 策略2: 颜色直方图比较
                    try:
                        # 计算颜色直方图
                        hist_bins = self.match_config['hist_bins']
                        puzzle_hist = cv2.calcHist([puzzle_block_color], [0, 1, 2], None, [hist_bins, hist_bins, hist_bins], [0, 256, 0, 256, 0, 256])
                        puzzle_hist = cv2.normalize(puzzle_hist, puzzle_hist).flatten()
                        
                        search_hist = cv2.calcHist([search_area_color], [0, 1, 2], None, [hist_bins, hist_bins, hist_bins], [0, 256, 0, 256, 0, 256])
                        search_hist = cv2.normalize(search_hist, search_hist).flatten()
                        
                        # 计算直方图相似度
                        hist_similarity = cv2.compareHist(puzzle_hist, search_hist, cv2.HISTCMP_CORREL)
                        confidences.append(max(0, hist_similarity))  # 确保非负
                    except:
                        confidences.append(0.0)
                    
                    # 策略3: 边缘检测匹配（降低权重）
                    try:
                        canny_low = self.match_config['canny_low']
                        canny_high = self.match_config['canny_high']
                        puzzle_edges = cv2.Canny(puzzle_block_gray, canny_low, canny_high)
                        search_edges = cv2.Canny(search_area_gray, canny_low, canny_high)
                        
                        res = cv2.matchTemplate(search_edges, puzzle_edges, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        confidences.append(max_val * self.match_config['edge_match_weight'])  # 使用配置的边缘匹配权重
                    except:
                        confidences.append(0.0)
                    
                    # 计算加权平均置信度
                    # 根据块数调整权重策略
                    if block_count == 100:
                        weights = [
                            self.match_config['gray_weight_100'],
                            self.match_config['hist_weight_100'], 
                            self.match_config['edge_weight_100'],
                            0.1  # 保留一个小的权重给其他因素
                        ]
                    else:
                        weights = [
                            self.match_config['gray_weight_other'],
                            self.match_config['hist_weight_other'],
                            self.match_config['edge_weight_other'],
                            0.05  # 保留一个小的权重给其他因素
                        ]
                    
                    total_confidence = sum(c * w for c, w in zip(confidences, weights))
                    
                    # 位置奖励：如果匹配位置接近预期位置，给予额外奖励
                    best_method = cv2.TM_CCOEFF_NORMED
                    res = cv2.matchTemplate(search_area_gray, puzzle_block_gray, best_method)
                    _, _, _, max_loc = cv2.minMaxLoc(res)
                    best_x = search_x1 + max_loc[0]
                    best_y = search_y1 + max_loc[1]
                    
                    # 计算位置偏差奖励
                    expected_x = tile_x
                    expected_y = tile_y
                    distance = ((best_x - expected_x) ** 2 + (best_y - expected_y) ** 2) ** 0.5
                    max_distance = (ref_tile_width ** 2 + ref_tile_height ** 2) ** 0.5
                    position_bonus = max(0, 1.0 - distance / max_distance) * self.match_config['position_bonus_weight']
                    
                    total_confidence += position_bonus
                    
                    matches.append({
                        'position': (row, col),
                        'confidence': total_confidence,
                        'location': (best_x, best_y),
                        'tile_size': (ref_tile_width, ref_tile_height),
                        'details': {
                            'gray_match': confidences[0] if len(confidences) > 0 else 0,
                            'hist_match': confidences[3] if len(confidences) > 3 else 0,
                            'edge_match': confidences[4] if len(confidences) > 4 else 0
                        }
                    })
                
            matches.sort(key=lambda x: x['confidence'], reverse=True)
            self.display_matches(matches, grid_rows, grid_cols, puzzle_cv)
            
        except Exception as e:
            self.status_bar.setText(f"❌ 检测匹配失败: {str(e)}")
            self.status_bar.setStyleSheet("color: red;")

    def display_matches(self, matches, grid_rows, grid_cols, current_puzzle_img=None):
        if not matches:
            self.status_bar.setText("❌ 未找到匹配")
            self.status_bar.setStyleSheet("color: red;")
            return
            
        self.result_text.clear()
        
        # 创建结果图像
        result_img = self.reference_img.copy()
        # 使用当前截取的拼图图像，如果没有则使用保存的图像
        if current_puzzle_img is not None:
            puzzle_result = current_puzzle_img.copy()
        else:
            puzzle_result = self.puzzle_img.copy() if hasattr(self, 'puzzle_img') and self.puzzle_img is not None else None
        
        best_match = matches[0]
        
        puzzle_center_x, puzzle_center_y, match_center_x, match_center_y = None, None, None, None

        if self.puzzle_region:
            best_x, best_y = best_match['location']
            tile_width, tile_height = best_match['tile_size']
            
            puzzle_x, puzzle_y, puzzle_width, puzzle_height = self.puzzle_region
            puzzle_center_x = puzzle_x + puzzle_width // 2
            puzzle_center_y = puzzle_y + puzzle_height // 2
            
            match_center_x = best_x + tile_width // 2
            match_center_y = best_y + tile_height // 2

        # 绘制从拼图区域到最佳匹配位置的箭头（受控于选项）
        if self.arrow_checkbox.isChecked() and puzzle_center_x is not None:
            confidence = best_match['confidence']
            # 根据置信度调整箭头颜色
            threshold = self.match_config['confidence_threshold']
            if confidence > 0.8:
                arrow_color = (0, 255, 0)  # 亮绿色
            elif confidence > threshold:
                arrow_color = (0, 204, 0)  # 中等绿色
            elif confidence > 0.4:
                arrow_color = (0, 153, 0)  # 深绿色
            else:
                arrow_color = (0, 102, 0)  # 暗绿色
            
            # 限制颜色分量在0~255
            arrow_color = tuple(min(255, max(0, c)) for c in arrow_color)
            # 在结果图像上绘制箭头
            draw_arrow(result_img, 
                      (puzzle_center_x, puzzle_center_y), 
                      (match_center_x, match_center_y), 
                      arrow_color, thickness=4, arrow_size=15)
        
        text_info = []
        for i, match in enumerate(matches[:5]):  # 显示前5个最佳匹配
            row, col = match['position']
            confidence = match['confidence']
            x, y = match['location']
            tile_width, tile_height = match['tile_size']
            
            # 边框颜色：置信度越高，绿色越深
            green_intensity = min(255, max(0, int(255 * confidence)))
            color = (0, green_intensity, 0)  # OpenCV为BGR，绿色为(0,255,0)
            # 文字颜色：根据置信度调整红色深浅
            threshold = self.match_config['confidence_threshold']
            if confidence > 0.8:
                color_name = "#FF0000"  # 亮红色
            elif confidence > threshold:
                color_name = "#CC0000"  # 中等红色
            elif confidence > 0.4:
                color_name = "#990000"  # 深红色
            else:
                color_name = "#660000"  # 暗红色
            
            # 在参考图上绘制矩形
            cv2.rectangle(result_img, (x, y), (x + tile_width, y + tile_height), color, 2)
            cv2.putText(result_img, f"{confidence:.2f}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 如果拼图图像存在，在拼图上绘制矩形
            if puzzle_result is not None:
                cv2.rectangle(puzzle_result, (x, y), (x + tile_width, y + tile_height), color, 2)
                cv2.putText(puzzle_result, f"({row+1},{col+1})", (x, y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 显示详细的置信度信息
            details = match.get('details', {})
            gray_match = details.get('gray_match', 0)
            hist_match = details.get('hist_match', 0)
            edge_match = details.get('edge_match', 0)
            
            detail_text = f'<font color="{color_name}">位置({row+1},{col+1}): 总置信度 {confidence:.3f}<br>'
            detail_text += f'&nbsp;&nbsp;灰度匹配: {gray_match:.3f}<br>'
            detail_text += f'&nbsp;&nbsp;颜色直方图: {hist_match:.3f}<br>'
            detail_text += f'&nbsp;&nbsp;边缘匹配: {edge_match:.3f}</font>'
            
            text_info.append(detail_text)
        
        self.result_text.setText("<br>".join(text_info))
        
        # 直接使用RGB格式显示
        result_pil = Image.fromarray(result_img)
        pixmap = pil_to_qpixmap(result_pil)
        # 使用更好的缩放策略，保持图片清晰度
        scaled_pixmap = pixmap.scaled(self.result_label.size() * 0.9, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.result_label.setPixmap(scaled_pixmap)
        
        # 更新拼图预览（显示当前截取的图像，不带匹配标记）
        if current_puzzle_img is not None:
            # 显示最新截取的干净图像
            puzzle_pil_clean = Image.fromarray(current_puzzle_img)
            puzzle_pixmap_clean = pil_to_qpixmap(puzzle_pil_clean)
            self.puzzle_label.setPixmap(puzzle_pixmap_clean.scaled(self.puzzle_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        best_match = matches[0]
        block_count = int(self.block_combo.currentText())
        threshold = self.match_config['confidence_threshold']
        if best_match['confidence'] > 0.8:
            self.status_bar.setText(f"✅ {block_count}块拼图 - 最佳匹配: 位置({best_match['position'][0]+1},{best_match['position'][1]+1}), 置信度: {best_match['confidence']:.2f}")
            self.status_bar.setStyleSheet("color: green;")
        elif best_match['confidence'] > threshold:
            self.status_bar.setText(f"⚠️ {block_count}块拼图 - 最佳匹配: 位置({best_match['position'][0]+1},{best_match['position'][1]+1}), 置信度: {best_match['confidence']:.2f} (中等)")
            self.status_bar.setStyleSheet("color: orange;")
        else:
            self.status_bar.setText(f"❌ {block_count}块拼图 - 最佳匹配: 位置({best_match['position'][0]+1},{best_match['position'][1]+1}), 置信度: {best_match['confidence']:.2f} (较低)")
            self.status_bar.setStyleSheet("color: red;")

        # 自动拖动逻辑 - 修正版
        if self.auto_drag_checkbox.isChecked() and not self.is_dragging:
            if self.puzzle_region and self.mapping_area:
                # 起始位置: 拼图块在屏幕上的中心点
                puzzle_x, puzzle_y, puzzle_width, puzzle_height = self.puzzle_region
                start_pos = (puzzle_x + puzzle_width // 2, puzzle_y + puzzle_height // 2)

                # 目标位置: 映射区域中对应方块的中心点
                row, col = best_match['position']
                map_x, map_y = self.mapping_area['x'], self.mapping_area['y']
                map_w, map_h = self.mapping_area['width'], self.mapping_area['height']
                
                block_w = map_w / grid_cols
                block_h = map_h / grid_rows
                
                # 计算目标方块中心点的屏幕坐标
                end_pos_x = map_x + col * block_w + block_w / 2
                end_pos_y = map_y + row * block_h + block_h / 2
                
                self.perform_auto_drag(start_pos, (end_pos_x, end_pos_y))
            else:
                # 如果缺少区域信息，在状态栏短暂提示
                current_text = self.status_bar.text()
                current_stylesheet = self.status_bar.styleSheet()
                self.status_bar.setText("⚠️ 拖动失败: 未设置拼图或映射区")
                self.status_bar.setStyleSheet("color: orange;")
                QTimer.singleShot(2000, lambda: (self.status_bar.setText(current_text), self.status_bar.setStyleSheet(current_stylesheet)))
        
        # 如果正在拖动且启用了中途等待，检查是否需要更新目标位置
        elif self.auto_drag_checkbox.isChecked() and self.is_dragging and self.drag_thread:
            # 检查是否启用了中途等待功能
            if self.drag_config.get('mid_drag_wait', False):
                # 计算新的目标位置
                row, col = best_match['position']
                map_x, map_y = self.mapping_area['x'], self.mapping_area['y']
                map_w, map_h = self.mapping_area['width'], self.mapping_area['height']
                
                block_w = map_w / grid_cols
                block_h = map_h / grid_rows
                
                # 计算新的目标方块中心点的屏幕坐标
                new_end_pos_x = map_x + col * block_w + block_w / 2
                new_end_pos_y = map_y + row * block_h + block_h / 2
                
                # 更新拖动线程的目标位置
                self.update_drag_target((new_end_pos_x, new_end_pos_y))
                
                # 显示更新信息
                self.status_bar.setText(f"🔄 目标已更新: 位置({row+1},{col+1}), 置信度: {best_match['confidence']:.2f}")
                self.status_bar.setStyleSheet("color: green;")
        
        if self.mapping_overlay:
            self.mapping_overlay.update_matches(matches, self.puzzle_region, show_arrow=self.arrow_checkbox.isChecked())

    def display_reference_preview(self, img_pil):
        pixmap = pil_to_qpixmap(img_pil)
        self.ref_label.setPixmap(pixmap.scaled(self.ref_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def display_puzzle_preview(self, img_pil):
        pixmap = pil_to_qpixmap(img_pil)
        self.puzzle_label.setPixmap(pixmap.scaled(self.puzzle_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        """Handle window resize to re-scale the result image."""
        super().resizeEvent(event)
        # Re-display the last result image to fit the new size
        if hasattr(self, 'result_label') and self.result_label.pixmap() and not self.result_label.pixmap().isNull():
             self.result_label.setPixmap(self.result_label.pixmap().scaled(self.result_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def toggle_detection(self):
        if self.is_detecting:
            self.detection_timer.stop()
            self.btn_toggle_detection.setText("开始检测 (S)")
            # Unregister the global hotkeys
            if HOTKEY_ENABLED and self.is_hotkey_setup:
                try:
                    keyboard.remove_hotkey('p')
                    keyboard.remove_hotkey('s')
                    self.is_hotkey_setup = False
                except Exception as e:
                    print(f"Failed to remove hotkeys: {e}")

            # 停止检测时关闭映射窗口
            if self.mapping_overlay:
                self.mapping_overlay.close()
                self.mapping_overlay = None
        else:
            # Register the global hotkeys
            if HOTKEY_ENABLED and not self.is_hotkey_setup:
                try:
                    keyboard.add_hotkey('p', self.on_p_pressed)
                    keyboard.add_hotkey('s', self.on_s_pressed)
                    self.is_hotkey_setup = True
                except Exception as e:
                    # Do not block the main functionality, just inform the user
                    QMessageBox.warning(self, "快捷键设置失败", 
                                        f"无法设置快捷键: {e}\n\n请确保以管理员身份运行，并已安装 'keyboard' 库。")

            self.detection_timer.start(1000)
            self.btn_toggle_detection.setText("停止检测 (P)")
            # 开始检测时自动打开映射窗口（如果有映射区域信息且未打开）
            if self.mapping_area and not self.mapping_overlay:
                from mapping_overlay import create_mapping_overlay
                self.mapping_overlay = create_mapping_overlay(
                    self.mapping_area['x'], self.mapping_area['y'],
                    self.mapping_area['width'], self.mapping_area['height'],
                    int(self.block_combo.currentText())
                )
                self.mapping_overlay.closed.connect(self.on_overlay_closed)
                self.show_mapping_checkbox.setEnabled(True)
                # 如果用户希望显示，则勾选并显示
                if self.show_mapping_checkbox.isChecked():
                    self.mapping_overlay.show()
        self.is_detecting = not self.is_detecting

# === Main Execution ===
if __name__ == "__main__":
    # 检查并请求管理员权限以确保鼠标穿透功能正常工作
    # isAdmin.hide_console()
    if not isAdmin.is_admin():
        print("检测到需要管理员权限以启用鼠标穿透功能...")
        print("正在请求管理员权限...")
        isAdmin.run_as_admin()
      
    else:
        print("已获得管理员权限，启动拼图匹配工具...")
    
    app = QApplication.instance() 
    if not app:
        app = QApplication(sys.argv)
    
    main_win = PuzzleApp()
    main_win.show()
    sys.exit(app.exec_())
