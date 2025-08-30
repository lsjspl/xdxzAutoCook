# -*- coding: utf-8 -*-
"""
钓鱼助手 - UI界面模块
负责所有用户界面相关的功能
"""

import sys
import os
import time
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QGroupBox, QMessageBox,
    QInputDialog, QLineEdit, QCheckBox, QTextEdit,
    QDialog, QScrollArea, QFormLayout, QSpinBox, QListWidget, QListWidgetItem,
    QDoubleSpinBox, QCompleter
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QRect, QStringListModel
from PIL import Image


def setup_logging():
    """设置日志配置"""
    # 创建logs目录
    logs_dir = os.path.join("logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 配置日志
    log_file = os.path.join(logs_dir, "fishing_app.log")
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logging.info("日志系统初始化完成")


def pil_to_qpixmap(pil_img):
    """Convert PIL image to QPixmap."""
    if pil_img.mode == "RGBA":
        img_format = QImage.Format_ARGB32
    elif pil_img.mode == "RGB":
        img_format = QImage.Format_RGB888
    else:
        pil_img = pil_img.convert("RGB")
        img_format = QImage.Format_RGB888
    
    return QPixmap.fromImage(QImage(
        pil_img.tobytes(), 
        pil_img.width, 
        pil_img.height, 
        pil_img.width * len(pil_img.getbands()), 
        img_format
    ))


class DetectionOverlay(QWidget):
    """桌面检测框覆盖窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |  # 无边框
            Qt.WindowStaysOnTopHint |  # 置顶
            Qt.Tool |  # 工具窗口
            Qt.WindowTransparentForInput  # 透明输入
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 显示时不激活
        
        # 检测框列表
        self.detection_boxes = []
        
        # 游戏窗口位置信息
        self.game_window_pos = None
        self.game_window_size = None
        self.show_game_window = False
        
        # 设置窗口大小为全屏
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        
        # 创建定时器，用于自动清除检测框
        self.clear_timer = QTimer()
        self.clear_timer.timeout.connect(self._clear_expired_boxes)
        self.clear_timer.start(100)  # 每100ms检查一次
        
    def add_detection_box(self, x, y, w, h, confidence, button_type):
        """添加检测框"""
        try:
            logging.info(f"覆盖窗口: 添加检测框 - {button_type} at ({x}, {y}, {w}, {h}), 置信度: {confidence:.3f}")
            print(f"覆盖窗口: 添加检测框 - {button_type} at ({x}, {y}, {w}, {h}), 置信度: {confidence:.3f}")
            
            box_info = {
                'x': x, 'y': y, 'w': w, 'h': h,
                'confidence': confidence,
                'type': button_type,
                'time': time.time(),
                'expire_time': time.time() + 1.0  # 1秒后过期
            }
            self.detection_boxes.append(box_info)
            
            # 只保留最近5个检测框
            if len(self.detection_boxes) > 5:
                self.detection_boxes.pop(0)
            
            logging.info(f"覆盖窗口: 检测框已添加，当前检测框数量: {len(self.detection_boxes)}")
            print(f"覆盖窗口: 检测框已添加，当前检测框数量: {len(self.detection_boxes)}")
            
            # 强制重绘窗口
            self.update()
            
        except Exception as e:
            logging.error(f"覆盖窗口: 添加检测框时发生错误: {e}")
            print(f"覆盖窗口: 添加检测框时发生错误: {e}")
    
    def _clear_expired_boxes(self):
        """清除过期的检测框"""
        current_time = time.time()
        expired_boxes = []
        
        for box in self.detection_boxes:
            if current_time > box['expire_time']:
                expired_boxes.append(box)
        
        # 移除过期的检测框
        for expired_box in expired_boxes:
            self.detection_boxes.remove(expired_box)
            logging.info(f"覆盖窗口: 检测框已过期并移除 - {expired_box['type']}")
        
        # 如果有检测框被移除，重绘窗口
        if expired_boxes:
            self.update()
        
    def clear_detection_boxes(self):
        """清除所有检测框"""
        self.detection_boxes.clear()
        self.update()
    
    def set_game_window_position(self, pos, size):
        """设置游戏窗口位置和大小"""
        self.game_window_pos = pos
        self.game_window_size = size
        self.update()
    
    def show_game_window_overlay(self, show=True):
        """显示或隐藏游戏窗口位置"""
        self.show_game_window = show
        self.update()
        
    def paintEvent(self, event):
        """绘制检测框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制游戏窗口位置（绿色方框）
        if self.show_game_window and self.game_window_pos and self.game_window_size:
            x, y = self.game_window_pos
            width, height = self.game_window_size
            
            # 绘制绿色方框
            pen = QPen(QColor(0, 255, 0), 3)  # 绿色，3像素宽度
            painter.setPen(pen)
            painter.drawRect(x, y, width, height)
            
            # 绘制标签
            text = f"游戏窗口 ({width}x{height})"
            font = QFont("Arial", 12, QFont.Bold)
            painter.setFont(font)
            
            # 文本背景
            text_rect = painter.fontMetrics().boundingRect(text)
            text_rect.moveTop(y - text_rect.height() - 5)
            text_rect.moveLeft(x)
            
            # 绘制文本背景
            painter.fillRect(text_rect, QColor(0, 0, 0, 150))
            
            # 绘制文本
            painter.setPen(QColor(0, 255, 0))
            painter.drawText(text_rect, Qt.AlignCenter, text)
        
        # 绘制检测框
        for box in self.detection_boxes:
            # 根据置信度设置颜色
            if box['confidence'] >= 0.8:
                color = QColor(0, 255, 0, 180)  # 绿色，半透明
            elif box['confidence'] >= 0.7:
                color = QColor(255, 255, 0, 180)  # 黄色，半透明
            else:
                color = QColor(255, 0, 0, 180)  # 红色，半透明
            
            # 绘制矩形框
            pen = QPen(color, 3)  # 3像素宽度
            painter.setPen(pen)
            painter.drawRect(box['x'], box['y'], box['w'], box['h'])
            
            # 绘制置信度文本
            text = f"{box['type']}: {box['confidence']:.3f}"
            font = QFont("Arial", 10)
            painter.setFont(font)
            
            # 文本背景
            text_rect = painter.fontMetrics().boundingRect(text)
            text_rect.moveTop(box['y'] - text_rect.height() - 5)
            text_rect.moveLeft(box['x'])
            
            # 绘制文本背景
            painter.fillRect(text_rect, QColor(0, 0, 0, 150))
            
            # 绘制文本
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(text_rect, Qt.AlignCenter, text)


class ClickSettingsDialog(QDialog):
    """自动点击设置对话框"""
    
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle("自动点击设置")
        self.setModal(True)
        self.resize(400, 300)
        
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
        
        # 点击设置
        click_group = QGroupBox("点击设置")
        click_layout = QFormLayout()
        self.move_delay_edit = QLineEdit(str(self.config.get('move_delay', 0.15)))
        self.move_delay_edit.setPlaceholderText("0.05-1.0")
        click_layout.addRow("移动后延时(秒):", self.move_delay_edit)
        
        self.press_delay_edit = QLineEdit(str(self.config.get('press_delay', 0.1)))
        self.press_delay_edit.setPlaceholderText("0.05-0.5")
        click_layout.addRow("按下后延时(秒):", self.press_delay_edit)
        
        self.final_delay_edit = QLineEdit(str(self.config.get('final_delay', 0.1)))
        self.final_delay_edit.setPlaceholderText("0.05-0.5")
        click_layout.addRow("点击后延时(秒):", self.final_delay_edit)
        
        self.cooldown_edit = QLineEdit(str(self.config.get('cooldown_time', 500)))
        self.cooldown_edit.setPlaceholderText("100-2000")
        click_layout.addRow("冷却时间(毫秒):", self.cooldown_edit)
        click_group.setLayout(click_layout)
        scroll_layout.addWidget(click_group)
        
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
        self.move_delay_edit.setText('0.15')
        self.press_delay_edit.setText('0.1')
        self.final_delay_edit.setText('0.1')
        self.cooldown_edit.setText('500')
    
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
            'window_title': self.window_title_edit.text(),
            'move_delay': safe_float(self.move_delay_edit.text(), 0.15),
            'press_delay': safe_float(self.press_delay_edit.text(), 0.1),
            'final_delay': safe_float(self.final_delay_edit.text(), 0.1),
            'cooldown_time': safe_int(self.cooldown_edit.text(), 500)
        }
    
    def accept_and_save(self):
        """确定并保存配置"""
        # 获取当前配置
        new_config = self.get_config()
        # 更新父窗口的配置
        if hasattr(self.parent(), 'click_config'):
            self.parent().click_config = new_config
            # 立即保存到文件
            if hasattr(self.parent(), 'save_click_config_to_file'):
                self.parent().save_click_config_to_file()
        # 关闭对话框
        self.accept()


class FishingMainUI(QWidget):
    """钓鱼助手主界面"""
    
    # 信号定义
    config_changed = pyqtSignal(str)  # 配置改变信号
    load_config_requested = pyqtSignal()  # 加载配置请求
    save_config_requested = pyqtSignal()  # 保存配置请求
    delete_config_requested = pyqtSignal()  # 删除配置请求
    
    select_bag_button_requested = pyqtSignal()  # 选择背包按钮请求
    select_fish_button_requested = pyqtSignal()  # 选择钓鱼按钮请求
    select_fish_tail_button_requested = pyqtSignal()  # 选择鱼尾按钮请求
    select_perfume_button_requested = pyqtSignal()  # 选择香水按钮请求
    select_spray_button_requested = pyqtSignal()  # 选择喷雾按钮请求
    select_use_button_requested = pyqtSignal()  # 选择使用按钮请求
    
    toggle_detection_requested = pyqtSignal()  # 切换检测状态请求
    click_settings_requested = pyqtSignal()  # 点击设置请求
    
    perfume_interval_changed = pyqtSignal(int)  # 香水使用间隔改变
    fish_tail_interval_changed = pyqtSignal(int)  # 鱼尾使用间隔改变
    game_window_position_display_requested = pyqtSignal(int, int, int, int) # 游戏窗口位置显示请求
    
    def __init__(self):
        super().__init__()
        
        # 设置主界面窗口始终置顶
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("🎣 钓鱼助手")
        
        # 创建检测覆盖层
        self.detection_overlay = DetectionOverlay()
        
        # 初始化UI组件
        self.init_ui()
        
        # 连接信号
        self.connect_signals()
    
    def init_ui(self):
        """初始化用户界面"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # --- Config Management UI ---
        config_group = QGroupBox("配置管理")
        config_layout = QHBoxLayout()
        
        # 添加配置名称标签
        config_label = QLabel("配置名称:")
        config_layout.addWidget(config_label)
        
        # 添加提示标签
        tip_label = QLabel("(输入时自动提示)")
        tip_label.setStyleSheet("color: gray; font-size: 10px;")
        config_layout.addWidget(tip_label)
        
        self.config_combo = QComboBox()
        self.config_combo.setEditable(True)  # 设置为可编辑
        # 设置插入策略，兼容不同版本的PyQt5
        try:
            self.config_combo.setInsertPolicy(QComboBox.NoInsert)  # 不自动插入新项
        except AttributeError:
            # 如果setInsertPolicy不可用，跳过设置
            pass
        # 设置最大可见项目数，兼容不同版本的PyQt5
        try:
            self.config_combo.setMaxVisibleItems(20)  # 最多显示20个配置
        except AttributeError:
            # 如果setMaxVisibleItems不可用，跳过设置
            pass
        # 设置占位符文本，兼容不同版本的PyQt5
        try:
            self.config_combo.setPlaceholderText("输入新配置名称或选择已有配置")
        except AttributeError:
            # 如果setPlaceholderText不可用，跳过设置
            pass
        
        # 启用自动完成功能
        
        # 设置自动完成策略
        # 创建自定义的completer
        self.config_completer = QCompleter()
        self.config_completer.setCaseSensitivity(Qt.CaseInsensitive)
        
        # 设置过滤模式，兼容不同版本的PyQt5
        try:
            self.config_completer.setFilterMode(Qt.MatchContains)  # 支持包含匹配
        except AttributeError:
            # 如果MatchContains不可用，使用默认模式
            pass
        
        # 设置完成模式，兼容不同版本的PyQt5
        try:
            self.config_completer.setCompletionMode(QCompleter.PopupCompletion)  # 弹出式完成
        except AttributeError:
            # 如果PopupCompletion不可用，使用默认模式
            pass
        
        self.config_combo.setCompleter(self.config_completer)
        config_layout.addWidget(self.config_combo, 1)

        self.btn_load_config = QPushButton("加载")
        config_layout.addWidget(self.btn_load_config)

        self.btn_save_config = QPushButton("保存")
        config_layout.addWidget(self.btn_save_config)

        self.btn_delete_config = QPushButton("删除")
        config_layout.addWidget(self.btn_delete_config)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Button layout
        button_layout = QVBoxLayout()

        # 第一行：按钮选择
        button_select_layout = QHBoxLayout()
        
        self.btn_select_bag = QPushButton("① 选择背包按钮")
        button_select_layout.addWidget(self.btn_select_bag)
        
        self.btn_select_fish = QPushButton("② 选择钓鱼按钮")
        button_select_layout.addWidget(self.btn_select_fish)
        
        button_layout.addLayout(button_select_layout)
        
        # 第二行：香水和鱼尾按钮选择
        perfume_fish_tail_layout = QHBoxLayout()
        
        self.btn_select_perfume = QPushButton("③ 选择香水按钮")
        perfume_fish_tail_layout.addWidget(self.btn_select_perfume)
        
        self.btn_select_fish_tail = QPushButton("④ 选择鱼尾按钮")
        perfume_fish_tail_layout.addWidget(self.btn_select_fish_tail)
        
        button_layout.addLayout(perfume_fish_tail_layout)
        
        # 第三行：喷雾和使用按钮选择
        spray_use_layout = QHBoxLayout()
        
        self.btn_select_spray = QPushButton("⑤ 选择喷雾按钮")
        spray_use_layout.addWidget(self.btn_select_spray)
        
        self.btn_select_use = QPushButton("⑥ 选择使用按钮")
        spray_use_layout.addWidget(self.btn_select_use)
        
        button_layout.addLayout(spray_use_layout)
        
        # 第四行：开始钓鱼
        fishing_layout = QHBoxLayout()
        
        self.btn_toggle_detection = QPushButton("⑦ 开始钓鱼 (O)")
        self.btn_toggle_detection.setEnabled(False)
        fishing_layout.addWidget(self.btn_toggle_detection)
        
        # 添加热键提示
        hotkey_label = QLabel("(O开始, P停止)")
        hotkey_label.setStyleSheet("color: gray; font-size: 10px;")
        fishing_layout.addWidget(hotkey_label)
        
        # 添加自动点击选项

        
        # 添加自动使用鱼尾和香水选项
        self.auto_fish_tail_checkbox = QCheckBox("自动使用鱼尾香水")
        self.auto_fish_tail_checkbox.setChecked(False)
        fishing_layout.addWidget(self.auto_fish_tail_checkbox)
        
        # 添加游戏窗口显示控制
        self.show_game_window_checkbox = QCheckBox("显示游戏窗口位置")
        self.show_game_window_checkbox.setChecked(True)
        self.show_game_window_checkbox.toggled.connect(self.update_game_window_display)
        fishing_layout.addWidget(self.show_game_window_checkbox)
        
        # 添加窗口置顶控制
        self.always_on_top_checkbox = QCheckBox("窗口置顶")
        self.always_on_top_checkbox.setChecked(False)
        self.always_on_top_checkbox.toggled.connect(self.toggle_always_on_top)
        fishing_layout.addWidget(self.always_on_top_checkbox)
        
        # 添加香水使用间隔设置
        fishing_layout.addWidget(QLabel("香水使用间隔:"))
        self.perfume_interval_spinbox = QSpinBox()
        self.perfume_interval_spinbox.setRange(60, 3600)
        self.perfume_interval_spinbox.setValue(120)
        self.perfume_interval_spinbox.setSuffix(" 秒")
        fishing_layout.addWidget(self.perfume_interval_spinbox)
        
        # 添加鱼尾使用间隔设置
        fishing_layout.addWidget(QLabel("鱼尾使用间隔:"))
        self.fish_tail_interval_spinbox = QSpinBox()
        self.fish_tail_interval_spinbox.setRange(60, 3600)
        self.fish_tail_interval_spinbox.setValue(60)
        self.fish_tail_interval_spinbox.setSuffix(" 秒")
        fishing_layout.addWidget(self.fish_tail_interval_spinbox)
        
        # 添加重试时间配置
        retry_timing_layout = QHBoxLayout()
        retry_timing_layout.addWidget(QLabel("点击等待:"))
        self.click_wait_time_spinbox = QDoubleSpinBox()
        self.click_wait_time_spinbox.setRange(1.0, 10.0)
        self.click_wait_time_spinbox.setSingleStep(0.1)
        self.click_wait_time_spinbox.setValue(1.0)
        self.click_wait_time_spinbox.setSuffix(" 秒")
        retry_timing_layout.addWidget(self.click_wait_time_spinbox)
        
        retry_timing_layout.addWidget(QLabel("重试等待:"))
        self.retry_wait_time_spinbox = QDoubleSpinBox()
        self.retry_wait_time_spinbox.setRange(2.0, 10.0)
        self.retry_wait_time_spinbox.setSingleStep(0.1)
        self.retry_wait_time_spinbox.setValue(2.0)
        self.retry_wait_time_spinbox.setSuffix(" 秒")
        retry_timing_layout.addWidget(self.retry_wait_time_spinbox)
        
        retry_timing_layout.addWidget(QLabel("检测间隔:"))
        self.button_check_interval_spinbox = QDoubleSpinBox()
        self.button_check_interval_spinbox.setRange(0.1, 10.0)
        self.button_check_interval_spinbox.setSingleStep(0.1)
        self.button_check_interval_spinbox.setValue(0.5)
        self.button_check_interval_spinbox.setSuffix(" 秒")
        retry_timing_layout.addWidget(self.button_check_interval_spinbox)
        
        button_layout.addLayout(retry_timing_layout)
        
        # 添加自动点击设置按钮
        self.btn_click_settings = QPushButton("点击设置")
        fishing_layout.addWidget(self.btn_click_settings)
        
        button_layout.addLayout(fishing_layout)

        button_group = QGroupBox("操作")
        button_group.setLayout(button_layout)
        main_layout.addWidget(button_group)

        # Preview layout
        preview_layout = QHBoxLayout()
        
        # Bag button preview
        bag_group = QGroupBox("背包按钮预览")
        bag_vbox = QVBoxLayout()
        self.bag_preview_label = QLabel("未选择")
        self.bag_preview_label.setAlignment(Qt.AlignCenter)
        self.bag_preview_label.setMinimumHeight(100)
        self.bag_preview_label.setStyleSheet("border: 1px solid gray;")
        bag_vbox.addWidget(self.bag_preview_label)
        bag_group.setLayout(bag_vbox)
        preview_layout.addWidget(bag_group)
        
        # Fish button preview
        fish_group = QGroupBox("钓鱼按钮预览")
        fish_vbox = QVBoxLayout()
        self.fish_preview_label = QLabel("未选择")
        self.fish_preview_label.setAlignment(Qt.AlignCenter)
        self.fish_preview_label.setMinimumHeight(100)
        self.fish_preview_label.setStyleSheet("border: 1px solid gray;")
        fish_vbox.addWidget(self.fish_preview_label)
        fish_group.setLayout(fish_vbox)
        preview_layout.addWidget(fish_group)
        
        # Fish tail button preview
        fish_tail_group = QGroupBox("鱼尾按钮预览")
        fish_tail_vbox = QVBoxLayout()
        self.fish_tail_preview_label = QLabel("未选择")
        self.fish_tail_preview_label.setAlignment(Qt.AlignCenter)
        self.fish_tail_preview_label.setMinimumHeight(100)
        self.fish_tail_preview_label.setStyleSheet("border: 1px solid gray;")
        fish_tail_vbox.addWidget(self.fish_tail_preview_label)
        fish_tail_group.setLayout(fish_tail_vbox)
        preview_layout.addWidget(fish_tail_group)
        
        # Perfume button preview
        perfume_group = QGroupBox("香水按钮预览")
        perfume_vbox = QVBoxLayout()
        self.perfume_preview_label = QLabel("未选择")
        self.perfume_preview_label.setAlignment(Qt.AlignCenter)
        self.perfume_preview_label.setMinimumHeight(100)
        self.perfume_preview_label.setStyleSheet("border: 1px solid gray;")
        perfume_vbox.addWidget(self.perfume_preview_label)
        perfume_group.setLayout(perfume_vbox)
        preview_layout.addWidget(perfume_group)
        
        # Spray button preview
        spray_group = QGroupBox("喷雾按钮预览")
        spray_vbox = QVBoxLayout()
        self.spray_preview_label = QLabel("未选择")
        self.spray_preview_label.setAlignment(Qt.AlignCenter)
        self.spray_preview_label.setMinimumHeight(100)
        self.spray_preview_label.setStyleSheet("border: 1px solid gray;")
        spray_vbox.addWidget(self.spray_preview_label)
        spray_group.setLayout(spray_vbox)
        preview_layout.addWidget(spray_group)
        
        # Use button preview
        use_group = QGroupBox("使用按钮预览")
        use_vbox = QVBoxLayout()
        self.use_preview_label = QLabel("未选择")
        self.use_preview_label.setAlignment(Qt.AlignCenter)
        self.use_preview_label.setMinimumHeight(100)
        self.use_preview_label.setStyleSheet("border: 1px solid gray;")
        use_vbox.addWidget(self.use_preview_label)
        use_group.setLayout(use_vbox)
        preview_layout.addWidget(use_group)
        
        preview_group = QGroupBox("预览")
        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)

        # Status display
        status_group = QGroupBox("状态")
        status_layout = QVBoxLayout()
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        status_layout.addWidget(self.status_text)
        status_group.setLayout(status_layout)
        main_layout.addWidget(status_group)
    
    def connect_signals(self):
        """连接信号和槽"""
        # 配置管理信号
        self.config_combo.currentTextChanged.connect(self.config_changed.emit)
        # 连接文本编辑信号，实现实时搜索
        self.config_combo.editTextChanged.connect(self.filter_configs)
        self.btn_load_config.clicked.connect(self.load_config_requested.emit)
        self.btn_save_config.clicked.connect(self.save_config_requested.emit)
        self.btn_delete_config.clicked.connect(self.delete_config_requested.emit)
        
        # 按钮选择信号
        self.btn_select_bag.clicked.connect(self.select_bag_button_requested.emit)
        self.btn_select_fish.clicked.connect(self.select_fish_button_requested.emit)
        self.btn_select_fish_tail.clicked.connect(self.select_fish_tail_button_requested.emit)
        self.btn_select_perfume.clicked.connect(self.select_perfume_button_requested.emit)
        self.btn_select_spray.clicked.connect(self.select_spray_button_requested.emit)
        self.btn_select_use.clicked.connect(self.select_use_button_requested.emit)
        
        # 检测和设置信号
        self.btn_toggle_detection.clicked.connect(self.toggle_detection_requested.emit)
        
        # 参数改变信号
        self.perfume_interval_spinbox.valueChanged.connect(self.perfume_interval_changed.emit)
        self.fish_tail_interval_spinbox.valueChanged.connect(self.fish_tail_interval_changed.emit)
    
    def update_config_combo(self, configs):
        """更新配置下拉框"""
        current_text = self.config_combo.currentText()
        self.config_combo.clear()
        
        # 添加配置列表
        if configs:
            self.config_combo.addItems(configs)
        
        # 如果当前文本不在配置列表中，但用户输入了新名称，保持当前文本
        if current_text and current_text.strip():
            if current_text not in configs:
                # 用户输入了新配置名，保持当前文本
                self.config_combo.setCurrentText(current_text)
            else:
                # 配置名在列表中，选择该配置
                self.config_combo.setCurrentText(current_text)
        elif configs:
            # 没有当前文本，选择第一个配置
            self.config_combo.setCurrentIndex(0)
        
        # 更新自定义completer的模型
        try:
            if hasattr(self, 'config_completer') and self.config_completer:
                from PyQt5.QtCore import QStringListModel
                model = QStringListModel(configs)
                self.config_completer.setModel(model)
        except Exception as e:
            # 如果completer更新失败，记录错误但不影响程序运行
            logging.warning(f"更新配置completer失败: {e}")
    
    def add_new_config(self, config_name):
        """添加新配置到下拉框"""
        if config_name and config_name not in [self.config_combo.itemText(i) for i in range(self.config_combo.count())]:
            self.config_combo.addItem(config_name)
            self.config_combo.setCurrentText(config_name)
    
    def filter_configs(self, search_text):
        """根据搜索文本过滤配置"""
        # 这个方法现在主要用于触发completer的更新
        # 实际的过滤由QCompleter自动处理
        pass
    
    def set_detection_button_enabled(self, enabled):
        """设置检测按钮是否可用"""
        self.btn_toggle_detection.setEnabled(enabled)
    
    def set_detection_button_text(self, text):
        """设置检测按钮文本"""
        self.btn_toggle_detection.setText(text)
    
    def set_click_settings_enabled(self, enabled):
        """设置点击设置按钮是否可用"""
        self.btn_click_settings.setEnabled(enabled)
    
    def display_bag_preview(self, img_pil):
        """显示背包按钮预览"""
        pixmap = pil_to_qpixmap(img_pil)
        self.bag_preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
        # 按钮变色表示已选择
        self.btn_select_bag.setStyleSheet("background-color: #90EE90; color: black;")
        self.btn_select_bag.setText("① 选择背包按钮 ✓")
    
    def display_fish_preview(self, img_pil):
        """显示钓鱼按钮预览"""
        pixmap = pil_to_qpixmap(img_pil)
        self.fish_preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
        # 按钮变色表示已选择
        self.btn_select_fish.setStyleSheet("background-color: #90EE90; color: black;")
        self.btn_select_fish.setText("② 选择钓鱼按钮 ✓")
    
    def display_fish_tail_preview(self, img_pil):
        """显示鱼尾按钮预览"""
        pixmap = pil_to_qpixmap(img_pil)
        self.fish_tail_preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
        # 按钮变色表示已选择
        self.btn_select_fish_tail.setStyleSheet("background-color: #90EE90; color: black;")
        self.btn_select_fish_tail.setText("④ 选择鱼尾按钮 ✓")
    
    def display_perfume_preview(self, img_pil):
        """显示香水按钮预览"""
        pixmap = pil_to_qpixmap(img_pil)
        self.perfume_preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
        # 按钮变色表示已选择
        self.btn_select_perfume.setStyleSheet("background-color: #90EE90; color: black;")
        self.btn_select_perfume.setText("③ 选择香水按钮 ✓")
    
    def display_spray_preview(self, img_pil):
        """显示喷雾按钮预览"""
        pixmap = pil_to_qpixmap(img_pil)
        self.spray_preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
        # 按钮变色表示已选择
        self.btn_select_spray.setStyleSheet("background-color: #90EE90; color: black;")
        self.btn_select_spray.setText("⑤ 选择喷雾按钮 ✓")
    
    def display_use_preview(self, img_pil):
        """显示使用按钮预览"""
        pixmap = pil_to_qpixmap(img_pil)
        self.use_preview_label.setPixmap(pixmap.scaled(100, 100, Qt.KeepAspectRatio))
        # 按钮变色表示已选择
        self.btn_select_use.setStyleSheet("background-color: #90EE90; color: black;")
        self.btn_select_use.setText("⑥ 选择使用按钮 ✓")
    
    def clear_bag_preview(self):
        """清空背包按钮预览"""
        self.bag_preview_label.clear()
        self.bag_preview_label.setText("未选择")
        self.btn_select_bag.setStyleSheet("")
        self.btn_select_bag.setText("① 选择背包按钮")
    
    def clear_fish_preview(self):
        """清空钓鱼按钮预览"""
        self.fish_preview_label.clear()
        self.fish_preview_label.setText("未选择")
        self.btn_select_fish.setStyleSheet("")
        self.btn_select_fish.setText("② 选择钓鱼按钮")


    def clear_perfume_preview(self):
        """清空香水按钮预览"""
        self.perfume_preview_label.clear()
        self.perfume_preview_label.setText("未选择")
        self.btn_select_perfume.setStyleSheet("")
        self.btn_select_perfume.setText("③ 选择香水按钮")
    
    def clear_fish_tail_preview(self):
        """清空鱼尾按钮预览"""
        self.fish_tail_preview_label.clear()
        self.fish_tail_preview_label.setText("未选择")
        self.btn_select_fish_tail.setStyleSheet("")
        self.btn_select_fish_tail.setText("④ 选择鱼尾按钮")
    

    
    def clear_spray_preview(self):
        """清空喷雾按钮预览"""
        self.spray_preview_label.clear()
        self.spray_preview_label.setText("未选择")
        self.btn_select_spray.setStyleSheet("")
        self.btn_select_spray.setText("⑤ 选择喷雾按钮")
    
    def clear_use_preview(self):
        """清空使用按钮预览"""
        self.use_preview_label.clear()
        self.use_preview_label.setText("未选择")
        self.btn_select_use.setStyleSheet("")
        self.btn_select_use.setText("⑥ 选择使用按钮")
    
    def update_status_text(self, new_text, max_lines=50):
        """更新状态文本"""
        current_text = self.status_text.toPlainText()
        lines = current_text.split('\n')
        
        # 添加新文本
        lines.append(new_text)
        
        # 限制行数
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
        
        # 更新显示
        self.status_text.setPlainText('\n'.join(lines))
        
        # 滚动到底部
        cursor = self.status_text.textCursor()
        cursor.movePosition(cursor.End)
        self.status_text.setTextCursor(cursor)
    
    def clear_status_text(self):
        """清空状态文本"""
        self.status_text.clear()
    
    def get_auto_click_enabled(self):
        """获取自动点击是否启用"""
        return self.auto_click_checkbox.isChecked()
    
    def get_auto_fish_tail_enabled(self):
        """获取自动使用鱼尾香水是否启用"""
        return self.auto_fish_tail_checkbox.isChecked()
    
    def set_auto_fish_tail_enabled(self, value):
        """设置自动使用鱼尾香水是否启用"""
        try:
            self.auto_fish_tail_checkbox.setChecked(bool(value))
            logging.info(f"设置自动使用鱼尾香水状态: {value}")
        except Exception as e:
            logging.warning(f"设置自动使用鱼尾香水状态失败: {e}")
            self.auto_fish_tail_checkbox.setChecked(False)
    
    def get_show_game_window_enabled(self):
        """获取是否显示游戏窗口位置"""
        return self.show_game_window_checkbox.isChecked()
    
    def set_show_game_window_enabled(self, value):
        """设置是否显示游戏窗口位置"""
        try:
            self.show_game_window_checkbox.setChecked(bool(value))
            # 立即应用设置
            self.update_game_window_display()
            logging.info(f"设置显示游戏窗口位置: {value}")
        except Exception as e:
            logging.warning(f"设置显示游戏窗口位置失败: {e}")
            self.show_game_window_checkbox.setChecked(True)
    
    def update_game_window_display(self):
        """根据checkbox状态更新游戏窗口显示"""
        if self.detection_overlay:
            if self.get_show_game_window_enabled():
                # 如果启用显示且有游戏窗口信息，则显示
                if hasattr(self, 'last_game_window_pos') and hasattr(self, 'last_game_window_size'):
                    if self.last_game_window_pos and self.last_game_window_size:
                        self.detection_overlay.set_game_window_position(self.last_game_window_pos, self.last_game_window_size)
                        self.detection_overlay.show_game_window_overlay(True)
                        if not self.detection_overlay.isVisible():
                            self.detection_overlay.show()
                            self.detection_overlay.raise_()
            else:
                # 如果禁用显示，则隐藏游戏窗口位置
                self.detection_overlay.show_game_window_overlay(False)
                self.detection_overlay.update()
    
    def show_game_window_position(self, pos, size):
        """显示游戏窗口位置"""
        # 保存游戏窗口信息
        self.last_game_window_pos = pos
        self.last_game_window_size = size
        
        if self.detection_overlay and self.get_show_game_window_enabled():
            self.detection_overlay.set_game_window_position(pos, size)
            self.detection_overlay.show_game_window_overlay(True)
            
            # 确保覆盖层可见
            if not self.detection_overlay.isVisible():
                self.detection_overlay.show()
                self.detection_overlay.raise_()
            
            self.update_status_text(f"游戏窗口位置: ({pos[0]}, {pos[1]}), 大小: {size[0]}x{size[1]}")
        else:
            self.update_status_text("游戏窗口位置信息不可用")
    
    def get_perfume_interval(self):
        """获取香水使用间隔"""
        return self.perfume_interval_spinbox.value()
    
    def set_perfume_interval(self, value):
        """设置香水使用间隔"""
        try:
            # 确保值是整数
            int_value = int(value)
            self.perfume_interval_spinbox.setValue(int_value)
        except (ValueError, TypeError) as e:
            logging.warning(f"设置香水间隔失败，使用默认值120: {e}")
            self.perfume_interval_spinbox.setValue(120)
    
    def get_fish_tail_interval(self):
        """获取鱼尾使用间隔"""
        return self.fish_tail_interval_spinbox.value()
    
    def set_fish_tail_interval(self, value):
        """设置鱼尾使用间隔"""
        try:
            # 确保值是整数
            int_value = int(value)
            self.fish_tail_interval_spinbox.setValue(int_value)
        except (ValueError, TypeError) as e:
            logging.warning(f"设置鱼尾间隔失败，使用默认值60: {e}")
            self.fish_tail_interval_spinbox.setValue(60)
    
    def get_current_config_name(self):
        """获取当前配置名称"""
        return self.config_combo.currentText()
    
    def set_current_config_name(self, name):
        """设置当前配置名称"""
        self.config_combo.setCurrentText(name)
    
    def update_detection_overlay(self, detection_results):
        """更新检测覆盖层"""
        if detection_results:
            # 清除旧的检测框
            self.detection_overlay.clear_detection_boxes()
            
            # 添加新的检测框
            for result in detection_results:
                if isinstance(result, dict) and all(key in result for key in ['x', 'y', 'w', 'h', 'confidence', 'type']):
                    self.detection_overlay.add_detection_box(
                        result['x'], result['y'], result['w'], result['h'],
                        result['confidence'], result['type']
                    )
            
            # 显示覆盖层
            if not self.detection_overlay.isVisible():
                self.detection_overlay.show()
            
            status_text = f"检测到 {len(detection_results)} 个目标"
            self.update_status_text(status_text)
        else:
            # 没有检测结果时隐藏覆盖层
            if self.detection_overlay.isVisible():
                self.detection_overlay.hide()
    
    def get_button_configs(self):
        """获取按钮配置信息"""
        return {
            'auto_click_enabled': True,  # 默认开启自动点击
            'auto_fish_tail_enabled': self.get_auto_fish_tail_enabled(),
            'perfume_interval': self.get_perfume_interval(),
            'fish_tail_interval': self.get_fish_tail_interval(),
            'click_wait_time': self.get_click_wait_time(),
            'retry_wait_time': self.get_retry_wait_time(),
            'button_check_interval': self.get_button_check_interval(),
            'always_on_top_enabled': self.get_always_on_top_enabled(),
            'show_game_window_enabled': self.get_show_game_window_enabled()
        }
    
    def get_click_wait_time(self):
        """获取点击等待时间"""
        return self.click_wait_time_spinbox.value()
    
    def get_retry_wait_time(self):
        """获取重试等待时间"""
        return self.retry_wait_time_spinbox.value()
    
    def get_button_check_interval(self):
        """获取按钮检测间隔"""
        return self.button_check_interval_spinbox.value()
    
    def set_click_wait_time(self, value):
        """设置点击等待时间"""
        try:
            # 确保值是浮点数
            float_value = float(value)
            self.click_wait_time_spinbox.setValue(float_value)
        except (ValueError, TypeError) as e:
            logging.warning(f"设置点击等待时间失败，使用默认值1.0: {e}")
            self.click_wait_time_spinbox.setValue(1.0)
    
    def set_retry_wait_time(self, value):
        """设置重试等待时间"""
        try:
            # 确保值是浮点数
            float_value = float(value)
            self.retry_wait_time_spinbox.setValue(float_value)
        except (ValueError, TypeError) as e:
            logging.warning(f"设置重试等待时间失败，使用默认值2.0: {e}")
            self.retry_wait_time_spinbox.setValue(2.0)
    
    def set_button_check_interval(self, value):
        """设置按钮检测间隔"""
        try:
            # 确保值是浮点数
            float_value = float(value)
            self.button_check_interval_spinbox.setValue(float_value)
        except (ValueError, TypeError) as e:
            logging.warning(f"设置按钮检测间隔失败，使用默认值0.5: {e}")
            self.button_check_interval_spinbox.setValue(0.5)
    
    def add_detection_box(self, x, y, w, h, confidence, button_type):
        """添加检测框"""
        try:
            logging.info(f"UI: 添加检测框 - {button_type} at ({x}, {y}, {w}, {h}), 置信度: {confidence:.3f}")
            
            # 调用覆盖窗口的add_detection_box方法
            self.detection_overlay.add_detection_box(x, y, w, h, confidence, button_type)
            
            # 确保覆盖窗口可见
            if not self.detection_overlay.isVisible():
                logging.info("UI: 检测框覆盖窗口不可见，正在显示...")
                self.detection_overlay.show()
                self.detection_overlay.raise_()
                self.detection_overlay.activateWindow()
            
            logging.info(f"UI: 检测框已添加")
            
        except Exception as e:
            logging.error(f"UI: 添加检测框时发生错误: {e}")
            print(f"UI: 添加检测框时发生错误: {e}")
    
    def clear_detection_overlay(self):
        """清除检测覆盖层"""
        if self.detection_overlay:
            self.detection_overlay.clear_detection_boxes()
            if self.detection_overlay.isVisible():
                self.detection_overlay.hide()
    
    def update_status(self, message):
        """更新状态信息（兼容旧接口）"""
        self.update_status_text(message)

    def update_ui_with_loaded_config(self, business):
        """使用加载的配置更新UI"""
        try:
            # 更新鱼尾间隔设置
            if hasattr(business, 'fish_tail_interval'):
                self.set_fish_tail_interval(business.fish_tail_interval)
            
            # 更新香水间隔设置
            if hasattr(business, 'perfume_interval'):
                self.set_perfume_interval(business.perfume_interval)
            
            # 更新时间设置
            if hasattr(business, 'click_wait_time'):
                self.set_click_wait_time(business.click_wait_time)
            if hasattr(business, 'retry_wait_time'):
                self.set_retry_wait_time(business.retry_wait_time)
            if hasattr(business, 'button_check_interval'):
                self.set_button_check_interval(business.button_check_interval)
            
            # 更新置顶设置
            if hasattr(business, 'always_on_top_enabled'):
                self.set_always_on_top_enabled(business.always_on_top_enabled)
            
            # 更新自动使用鱼尾香水设置
            if hasattr(business, 'auto_fish_tail_enabled'):
                self.set_auto_fish_tail_enabled(business.auto_fish_tail_enabled)
            
            # 更新显示游戏窗口位置设置
            if hasattr(business, 'show_game_window_enabled'):
                self.set_show_game_window_enabled(business.show_game_window_enabled)
            
            # 更新按钮预览图像
            if business.bag_button_img:
                self.display_bag_preview(business.bag_button_img)
            if business.fish_button_img:
                self.display_fish_preview(business.fish_button_img)
            if business.fish_tail_button_img:
                self.display_fish_tail_preview(business.fish_tail_button_img)
            if business.perfume_button_img:
                self.display_perfume_preview(business.perfume_button_img)
            if business.spray_button_img:
                self.display_spray_preview(business.spray_button_img)
            if business.use_button_img:
                self.display_use_preview(business.use_button_img)
            
            # 更新游戏窗口位置显示
            if hasattr(business, 'game_window_pos') and hasattr(business, 'game_window_size'):
                if business.game_window_pos and business.game_window_size:
                    self.show_game_window_position(business.game_window_pos, business.game_window_size)
                    
            logging.info("UI已更新为加载的配置")
            
        except Exception as e:
            logging.error(f"更新UI显示失败: {e}")
    
    def toggle_always_on_top(self, checked):
        """切换窗口置顶状态"""
        try:
            if checked:
                self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
                self.update_status_text("窗口已置顶")
            else:
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
                self.update_status_text("窗口已取消置顶")
            
            # 重新显示窗口以应用新的标志
            self.show()
            logging.info(f"窗口置顶状态已切换: {checked}")
        except Exception as e:
            logging.error(f"切换窗口置顶状态失败: {e}")
            self.update_status_text(f"切换置顶状态失败: {str(e)}")
    
    def get_always_on_top_enabled(self):
        """获取窗口置顶是否启用"""
        return self.always_on_top_checkbox.isChecked()
    
    def set_always_on_top_enabled(self, value):
        """设置窗口置顶是否启用"""
        try:
            self.always_on_top_checkbox.setChecked(bool(value))
            # 立即应用置顶状态
            self.toggle_always_on_top(bool(value))
        except Exception as e:
            logging.warning(f"设置窗口置顶状态失败: {e}")
            self.always_on_top_checkbox.setChecked(False)
    
    def validate_config_name(self, config_name):
        """验证配置名称是否有效"""
        if not config_name or not config_name.strip():
            return False, "配置名称不能为空"
        
        # 检查是否包含非法字符
        invalid_chars = ['<', '>', ':', '"', '|', '?', '*', '/', '\\']
        for char in invalid_chars:
            if char in config_name:
                return False, f"配置名称不能包含字符: {char}"
        
        # 检查长度
        if len(config_name.strip()) > 50:
            return False, "配置名称不能超过50个字符"
        
        return True, ""