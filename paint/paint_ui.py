# -*- coding: utf-8 -*-
"""
绘图助手 - UI界面模块
负责所有用户界面相关的功能
"""

import sys
import os
import time
import logging
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QGroupBox, QMessageBox,
    QFileDialog, QSpinBox, QTextEdit, QScrollArea, QFormLayout,
    QGridLayout, QFrame, QSizePolicy, QDoubleSpinBox, QLineEdit,
    QCheckBox, QProgressBar
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor, QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QTimer
from PIL import Image


def setup_logging():
    """设置日志配置"""
    try:
        # 创建logs目录 - 使用绝对路径确保在paint目录下
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logs_dir = os.path.join(current_dir, "logs")
        
        # 确保logs目录存在
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            print(f"创建日志目录: {logs_dir}")
        
        # 配置日志文件路径 - 添加时间戳
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(logs_dir, f"paint_app_{timestamp}.log")
        print(f"日志文件路径: {log_file}")
        
        # 检查是否已经配置了文件处理器
        has_file_handler = False
        for handler in logging.root.handlers:
            if isinstance(handler, logging.FileHandler):
                has_file_handler = True
                print(f"日志系统已经配置了文件处理器: {handler.baseFilename}")
                break
        
        if has_file_handler:
            print("日志系统已经配置，跳过重复配置")
            return
        
        # 清除之前的日志配置
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        
        # 设置日志级别为DEBUG，确保所有日志都能记录
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8', mode='a'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # 测试日志是否正常工作
        logging.info("=== 日志系统初始化完成 ===")
        logging.debug("DEBUG级别日志测试")
        logging.info("INFO级别日志测试")
        logging.warning("WARNING级别日志测试")
        logging.error("ERROR级别日志测试")
        
        print(f"日志系统初始化完成，日志文件: {log_file}")
        
        # 验证日志文件是否可写
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"# 日志文件测试写入 - {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            print("日志文件写入测试成功")
            
            # 再次测试日志写入
            logging.info(f"日志文件写入验证成功: {log_file}")
            
        except Exception as e:
            print(f"日志文件写入测试失败: {e}")
            logging.error(f"日志文件写入测试失败: {e}")
            
    except Exception as e:
        print(f"设置日志系统时发生错误: {e}")
        # 如果设置失败，至少确保有基本的控制台输出
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )


def pil_to_qpixmap(pil_img):
    """Convert PIL image to QPixmap with explicit stride and correct channel order."""
    # 统一为RGBA或RGB
    if pil_img.mode not in ("RGB", "RGBA"):
        try:
            pil_img = pil_img.convert("RGBA")
        except Exception:
            pil_img = pil_img.convert("RGB")

    w, h = pil_img.size
    mode = pil_img.mode
    data = pil_img.tobytes("raw", mode)

    if mode == "RGBA":
        fmt = QImage.Format_RGBA8888  # 与PIL RGBA顺序一致
        bytes_per_line = 4 * w
    else:  # RGB
        fmt = QImage.Format_RGB888
        bytes_per_line = 3 * w

    # 显式提供bytesPerLine，并复制数据以避免悬挂指针
    qimg = QImage(data, w, h, bytes_per_line, fmt).copy()
    return QPixmap.fromImage(qimg)


class PaintMainUI(QWidget):
    """绘图助手主界面"""
    
    # 信号定义
    select_draw_area_requested = pyqtSignal()  # 选择绘画区域请求
    select_parent_color_area_requested = pyqtSignal()  # 选择父颜色区域请求
    select_color_palette_button_requested = pyqtSignal()  # 选择色盘按钮请求
    select_color_swatch_return_button_requested = pyqtSignal()  # 选择色板返回按钮请求
    select_child_color_area_requested = pyqtSignal()  # 选择子颜色区域请求
    select_background_color_button_requested = pyqtSignal()  # 选择背景色按钮请求
    collect_colors_requested = pyqtSignal()  # 收集颜色请求
    clear_colors_requested = pyqtSignal()  # 清理颜色请求
    select_image_requested = pyqtSignal()  # 选择图片请求
    process_image_requested = pyqtSignal(str, str)  # 处理图片请求(比例, 尺寸)
    start_drawing_requested = pyqtSignal()  # 开始绘图请求
    stop_drawing_requested = pyqtSignal()  # 停止绘图请求
    debug_pixels_requested = pyqtSignal()  # 调试像素请求
    
    # 配置管理信号
    config_changed = pyqtSignal(str)  # 配置改变
    save_config_requested = pyqtSignal()  # 保存配置请求
    load_config_requested = pyqtSignal()  # 加载配置请求
    delete_config_requested = pyqtSignal()  # 删除配置请求
    
    def __init__(self):
        super().__init__()
        
        # 设置全局异常处理器，捕获Qt异常
        self._setup_exception_handling()
        
        # 初始化所有状态变量
        self.draw_area_pos = None
        self.parent_color_area_pos = None
        self.color_palette_button_pos = None
        self.color_swatch_return_button_pos = None
        self.child_color_area_pos = None
        self.background_color_button_pos = None
        self.selected_image_path = None
        self.pixelized_image = None
        self.color_palette = []
        self.collected_colors = []
        self.pixel_info_list = []
        

        
        # 初始化UI
        self.init_ui()
        self.connect_signals()
        
        # 创建检测覆盖层
        self.detection_overlay = DetectionOverlay()
        

        
        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        
        # 设置初始状态
        self.update_status_text("🎨 绘图助手已启动，请选择图片并收集颜色")
        
        # 检查就绪状态（在所有属性初始化之后）
        self.check_ready_state()
        
        logging.info("绘图助手UI初始化完成")
    
    def reset_image_related_data(self):
        """重置UI中的图片相关数据，保留用户配置"""
        logging.info("重置UI中的图片相关数据")
        
        # 重置图片相关的数据
        self.selected_image_path = None
        self.pixelized_image = None
        self.color_palette = []
        self.pixel_info_list = []
        
        # 重置UI显示
        self.image_path_label.setText("未选择图片")
        self.image_path_label.setStyleSheet("color: red;")
        self.original_image_label.setText("请选择图片")
        self.process_image_btn.setEnabled(False)
        
        # 清除像素化图片预览
        if hasattr(self, 'pixelized_image_label'):
            self.pixelized_image_label.setText("请先处理图片")
        
        # 注意：不重置以下用户配置相关的数据
        # - draw_area_pos (绘画区域)
        # - parent_color_area_pos (父颜色区域)
        # - color_palette_button_pos (色盘按钮)
        # - color_swatch_return_button_pos (色板返回按钮)
        # - child_color_area_pos (子颜色区域)
        # - background_color_button_pos (背景色按钮)
        # - collected_colors (收集的颜色)
        
        # 重新检查就绪状态
        self.check_ready_state()
        
        logging.info("UI中的图片相关数据已重置")
    
    def _setup_exception_handling(self):
        """设置全局异常处理器，捕获Qt异常"""
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            
            logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
            sys.stderr.write(f"Error: {exc_value}\n")
            sys.stderr.write("Please check the logs for more details.\n")
            sys.stderr.flush()
            sys.stdout.flush()
        
        sys.excepthook = handle_exception
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("绘图助手 - 心动小镇自动绘图工具")
        self.setGeometry(100, 100, 1200, 800)
        
        # 创建主布局
        main_layout = QHBoxLayout()
        
        # 左侧控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel, 1)
        
        # 右侧预览面板
        preview_panel = self.create_preview_panel()
        main_layout.addWidget(preview_panel, 2)
        
        self.setLayout(main_layout)
    
    def create_control_panel(self):
        """创建左侧控制面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # 步骤1: 选择绘画区域
        step1_group = QGroupBox("步骤1: 选择绘画区域")
        step1_layout = QVBoxLayout()
        
        self.select_draw_area_btn = QPushButton("选择绘画区域")
        self.select_draw_area_btn.setMinimumHeight(40)
        
        step1_layout.addWidget(self.select_draw_area_btn)
        step1_group.setLayout(step1_layout)
        
        # 步骤2: 颜色区域设置
        step2_group = QGroupBox("步骤2: 颜色区域设置")
        step2_layout = QVBoxLayout()
        
        # 创建按钮网格布局（每行3个）
        buttons_grid_layout = QGridLayout()
        buttons_grid_layout.setSpacing(10)
        
        # 第一行：父颜色区域、色盘按钮、色板返回按钮
        self.select_parent_color_area_btn = QPushButton("选择父颜色区域")
        self.select_parent_color_area_btn.setMinimumHeight(35)
        
        self.select_color_palette_button_btn = QPushButton("选择色盘按钮")
        self.select_color_palette_button_btn.setMinimumHeight(35)
        
        self.select_color_swatch_return_button_btn = QPushButton("选择色板返回按钮")
        self.select_color_swatch_return_button_btn.setMinimumHeight(35)
        
        # 第二行：子颜色区域、背景色按钮、收集颜色按钮
        self.select_child_color_area_btn = QPushButton("选择子颜色区域")
        self.select_child_color_area_btn.setMinimumHeight(35)
        
        self.select_background_color_button_btn = QPushButton("选择背景色按钮")
        self.select_background_color_button_btn.setMinimumHeight(35)
        
        self.collect_colors_btn = QPushButton("收集颜色")
        self.collect_colors_btn.setMinimumHeight(40)
        self.collect_colors_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.collect_colors_btn.setEnabled(False)
        
        # 添加清理颜色按钮
        self.clear_colors_btn = QPushButton("清理颜色")
        self.clear_colors_btn.setMinimumHeight(40)
        self.clear_colors_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.clear_colors_btn.setEnabled(False)
        
        # 将按钮添加到网格布局中
        # 第一行
        buttons_grid_layout.addWidget(self.select_parent_color_area_btn, 0, 0)
        buttons_grid_layout.addWidget(self.select_color_palette_button_btn, 0, 1)
        buttons_grid_layout.addWidget(self.select_color_swatch_return_button_btn, 0, 2)
        
        # 第二行
        buttons_grid_layout.addWidget(self.select_child_color_area_btn, 1, 0)
        buttons_grid_layout.addWidget(self.select_background_color_button_btn, 1, 1)
        buttons_grid_layout.addWidget(self.collect_colors_btn, 1, 2)
        
        # 第三行：收集颜色和清理颜色按钮
        buttons_grid_layout.addWidget(self.collect_colors_btn, 2, 0, 1, 2)  # 跨2列
        buttons_grid_layout.addWidget(self.clear_colors_btn, 2, 2)
        
        # 将按钮网格布局添加到垂直布局中
        step2_layout.addLayout(buttons_grid_layout)
        
        step2_group.setLayout(step2_layout)
        
        # 步骤3: 选择图片和设置
        step3_group = QGroupBox("步骤3: 图片设置")
        step3_layout = QFormLayout()
        
        # 选择图片
        self.select_image_btn = QPushButton("选择图片")
        self.select_image_btn.setMinimumHeight(40)
        self.image_path_label = QLabel("未选择图片")
        self.image_path_label.setStyleSheet("color: red;")
        
        # 图片比例选择
        self.aspect_ratio_combo = QComboBox()
        self.aspect_ratio_combo.addItems(["1:1", "16:9", "4:3", "3:4", "9:16"])
        self.aspect_ratio_combo.setCurrentText("1:1")
        
        # 尺寸选择
        self.size_combo = QComboBox()
        self.size_combo.addItems(["30个格子", "50个格子", "100个格子", "150个格子"])
        self.size_combo.setCurrentText("100个格子")
        
        # 连接比例变化事件，更新尺寸选项
        self.aspect_ratio_combo.currentTextChanged.connect(self.update_size_options)
        
        # 初始化尺寸选项
        self.update_size_options()
        
        # 延迟配置设置
        self.color_delay_spin = QDoubleSpinBox()
        self.color_delay_spin.setRange(0.01, 10.0)
        self.color_delay_spin.setValue(0.5)
        self.color_delay_spin.setSingleStep(0.01)
        self.color_delay_spin.setSuffix(" 秒")
        self.color_delay_spin.setDecimals(5)
        
        self.draw_delay_spin = QDoubleSpinBox()
        self.draw_delay_spin.setRange(0.001, 10.0)
        self.draw_delay_spin.setValue(0.011)
        self.draw_delay_spin.setSingleStep(0.001)
        self.draw_delay_spin.setSuffix(" 秒")
        self.draw_delay_spin.setDecimals(5)
        
        self.move_delay_spin = QDoubleSpinBox()
        self.move_delay_spin.setRange(0.001, 10)
        self.move_delay_spin.setValue(0.001)
        self.move_delay_spin.setSingleStep(0.001)
        self.move_delay_spin.setSuffix(" 秒")
        self.move_delay_spin.setDecimals(5)


        # 处理图片按钮
        self.process_image_btn = QPushButton("处理图片")
        self.process_image_btn.setMinimumHeight(40)
        self.process_image_btn.setEnabled(False)
        self.process_image_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        step3_layout.addRow("选择图片:", self.select_image_btn)
        step3_layout.addRow("图片路径:", self.image_path_label)
        step3_layout.addRow("图片比例:", self.aspect_ratio_combo)
        step3_layout.addRow("尺寸选择:", self.size_combo)
        step3_layout.addRow("颜色点击延迟:", self.color_delay_spin)
        step3_layout.addRow("绘图点击延迟:", self.draw_delay_spin)
        step3_layout.addRow("鼠标移动延迟:", self.move_delay_spin)
        step3_layout.addRow("处理图片:", self.process_image_btn)
        step3_group.setLayout(step3_layout)
        
        # 步骤4: 开始绘图
        step4_group = QGroupBox("步骤4: 开始绘图")
        step4_layout = QVBoxLayout()
        
        # 绘图按钮布局
        drawing_buttons_layout = QHBoxLayout()
        
        self.start_drawing_btn = QPushButton("开始绘图")
        self.start_drawing_btn.setMinimumHeight(50)
        self.start_drawing_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_drawing_btn.setEnabled(False)
        
        self.debug_pixels_btn = QPushButton("调试像素")
        self.debug_pixels_btn.setMinimumHeight(50)
        self.debug_pixels_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.debug_pixels_btn.setEnabled(False)
        
        drawing_buttons_layout.addWidget(self.start_drawing_btn)
        drawing_buttons_layout.addWidget(self.debug_pixels_btn)
        
        step4_layout.addLayout(drawing_buttons_layout)
        step4_group.setLayout(step4_layout)
        
        # 配置管理组
        config_group = QGroupBox("配置管理")
        config_layout = QVBoxLayout()
        
        # 配置选择下拉框
        self.config_combo = QComboBox()
        self.config_combo.setMinimumHeight(30)
        self.config_combo.setEditable(True)
        self.config_combo.setPlaceholderText("选择或输入配置名称")
        
        # 配置操作按钮
        config_buttons_layout = QHBoxLayout()
        self.btn_save_config = QPushButton("保存配置")
        self.btn_load_config = QPushButton("加载配置")
        self.btn_delete_config = QPushButton("删除配置")
        
        # 设置按钮样式
        for btn in [self.btn_save_config, self.btn_load_config, self.btn_delete_config]:
            btn.setMinimumHeight(35)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #607D8B;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #455A64;
                }
                QPushButton:disabled {
                    background-color: #cccccc;
                    color: #666666;
                }
            """)
        
        config_buttons_layout.addWidget(self.btn_save_config)
        config_buttons_layout.addWidget(self.btn_load_config)
        config_buttons_layout.addWidget(self.btn_delete_config)
        
        config_layout.addWidget(self.config_combo)
        config_layout.addLayout(config_buttons_layout)
        config_group.setLayout(config_layout)
        
        # 绘画区域显示控制组
        draw_area_display_group = QGroupBox("绘画区域显示控制")
        draw_area_display_layout = QVBoxLayout()
        
        # 创建绘画区域显示控制checkbox
        self.show_draw_area_checkbox = QCheckBox("显示绘画区域框")
        self.show_draw_area_checkbox.setChecked(True)  # 默认显示
        self.show_draw_area_checkbox.stateChanged.connect(self._on_draw_area_checkbox_changed)
        
        draw_area_display_layout.addWidget(self.show_draw_area_checkbox)
        draw_area_display_group.setLayout(draw_area_display_layout)
        
        # 添加所有组件到面板
        layout.addWidget(step1_group)
        layout.addWidget(step2_group)
        layout.addWidget(step3_group)
        layout.addWidget(step4_group)
        layout.addWidget(config_group)
        layout.addWidget(draw_area_display_group)
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def create_preview_panel(self):
        """创建右侧预览面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # 创建图片预览行（原图预览和像素化预览并排）
        image_preview_layout = QHBoxLayout()
        
        # 原图预览
        original_group = QGroupBox("原图预览")
        original_layout = QVBoxLayout()
        
        self.original_image_label = QLabel("请选择图片")
        self.original_image_label.setAlignment(Qt.AlignCenter)
        self.original_image_label.setMinimumHeight(200)
        self.original_image_label.setMinimumWidth(300)
        self.original_image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #cccccc;
                background-color: #f9f9f9;
            }
        """)
        
        original_layout.addWidget(self.original_image_label)
        original_group.setLayout(original_layout)
        
        # 像素化预览
        pixelized_group = QGroupBox("像素化预览")
        pixelized_layout = QVBoxLayout()
        
        self.pixelized_image_label = QLabel("等待图片像素化")
        self.pixelized_image_label.setAlignment(Qt.AlignCenter)
        self.pixelized_image_label.setMinimumHeight(200)
        self.pixelized_image_label.setMinimumWidth(300)
        self.pixelized_image_label.setScaledContents(False)  # 禁用自动拉伸
        self.pixelized_image_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)  # 允许自由调整大小
        self.pixelized_image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #cccccc;
                background-color: #f9f9f9;
            }
        """)
        
        pixelized_layout.addWidget(self.pixelized_image_label)
        pixelized_group.setLayout(pixelized_layout)
        
        # 将两个预览组添加到水平布局中
        image_preview_layout.addWidget(original_group)
        image_preview_layout.addWidget(pixelized_group)
        
        # 收集到的颜色显示
        collected_colors_group = QGroupBox("收集到的颜色（用于绘图）")
        collected_colors_layout = QVBoxLayout()
        
        # 创建滚动区域
        self.collected_colors_scroll = QScrollArea()
        self.collected_colors_scroll.setMinimumHeight(100)
        self.collected_colors_scroll.setWidgetResizable(True)
        self.collected_colors_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.collected_colors_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.collected_colors_scroll.setStyleSheet("""
            QScrollArea {
                border: 2px dashed #cccccc;
                background-color: #f9f9f9;
            }
        """)
        
        # 创建内容容器
        self.collected_colors_frame = QFrame()
        self.collected_colors_frame.setStyleSheet("""
            QFrame {
                background-color: #f9f9f9;
            }
        """)
        
        # 创建固定的主布局结构
        self._colors_main_layout = QVBoxLayout()
        self._colors_main_layout.setSpacing(15)
        self._colors_main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 设置容器的布局
        self.collected_colors_frame.setLayout(self._colors_main_layout)
        
        # 将内容容器设置为滚动区域的widget
        self.collected_colors_scroll.setWidget(self.collected_colors_frame)
        
        collected_colors_layout.addWidget(self.collected_colors_scroll)
        collected_colors_group.setLayout(collected_colors_layout)
        
        # 绘图进度显示
        progress_group = QGroupBox("绘图进度")
        progress_layout = QVBoxLayout()
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimumHeight(25)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("进度: %p% (%v/%m)")
        
        # 进度标签
        self.progress_label = QLabel("等待开始绘图...")
        self.progress_label.setStyleSheet("color: #666; font-size: 12px;")
        
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.progress_label)
        progress_group.setLayout(progress_layout)
        
        # 状态显示
        status_group = QGroupBox("状态信息")
        status_layout = QVBoxLayout()
        
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(150)
        self.status_text.setReadOnly(True)
        self.status_text.append("绘图助手已启动，请按步骤操作...")
        
        status_layout.addWidget(self.status_text)
        status_group.setLayout(status_layout)
        
        # 添加所有组件到面板
        layout.addLayout(image_preview_layout)  # 添加图片预览行
        layout.addWidget(collected_colors_group)
        layout.addWidget(progress_group)
        layout.addWidget(status_group)
        
        panel.setLayout(layout)
        return panel
    
    def connect_signals(self):
        """连接信号"""
        self.select_draw_area_btn.clicked.connect(self.select_draw_area_requested.emit)
        self.select_parent_color_area_btn.clicked.connect(self.select_parent_color_area_requested.emit)
        self.select_color_palette_button_btn.clicked.connect(self.select_color_palette_button_requested.emit)
        self.select_color_swatch_return_button_btn.clicked.connect(self.select_color_swatch_return_button_requested.emit)
        self.select_child_color_area_btn.clicked.connect(self.select_child_color_area_requested.emit)
        self.select_background_color_button_btn.clicked.connect(self.select_background_color_button_requested.emit)
        self.collect_colors_btn.clicked.connect(self.collect_colors_requested.emit)
        self.clear_colors_btn.clicked.connect(self.clear_colors_requested.emit)
        self.select_image_btn.clicked.connect(self.select_image_requested.emit)
        self.process_image_btn.clicked.connect(self.on_process_image_clicked)
        self.start_drawing_btn.clicked.connect(self.start_drawing_requested.emit)
        self.debug_pixels_btn.clicked.connect(self.debug_pixels_requested.emit)
        
        # 配置管理信号连接
        self.btn_save_config.clicked.connect(self.save_config_requested.emit)
        self.btn_load_config.clicked.connect(self.load_config_requested.emit)
        self.btn_delete_config.clicked.connect(self.delete_config_requested.emit)
        self.config_combo.currentTextChanged.connect(self.config_changed.emit)
        
        # 设置变化时的处理
        self.aspect_ratio_combo.currentTextChanged.connect(self.on_settings_changed)
        self.size_combo.currentTextChanged.connect(self.on_settings_changed)
    
    def on_settings_changed(self):
        """设置变化时的处理"""
        if self.selected_image_path:
            self.update_status_text("设置已更改，请重新处理图片")
    
    def on_process_image_clicked(self):
        """处理图片按钮点击事件"""
        if self.selected_image_path:
            ratio_text = self.aspect_ratio_combo.currentText()
            size_text = self.size_combo.currentText()
            self.process_image_requested.emit(ratio_text, size_text)
            self.update_status_text(f"开始处理图片，比例: {ratio_text}, 尺寸: {size_text}")
    
    def set_draw_area(self, position):
        """设置绘画区域"""
        self.draw_area_pos = position
        if position:
            self.select_draw_area_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_status_text(f"绘画区域已设置: {position[2]}×{position[3]} 像素")
            
            # 保存绘画区域位置信息，用于显示控制
            self.last_draw_area_pos = position[:2]
            self.last_draw_area_size = position[2:]
            
            # 根据checkbox状态决定是否显示绘画区域
            if hasattr(self, 'show_draw_area_checkbox') and self.show_draw_area_checkbox.isChecked():
                if hasattr(self, 'detection_overlay') and self.detection_overlay:
                    self.detection_overlay.set_draw_area_position(position[:2], position[2:])
                    self.detection_overlay.show_draw_area_overlay(True)
                    # 确保覆盖层可见
                    if not self.detection_overlay.isVisible():
                        self.detection_overlay.show()
                        self.detection_overlay.raise_()
        else:
            self.select_draw_area_btn.setStyleSheet("")
            # 隐藏绘画区域显示
            if hasattr(self, 'detection_overlay') and self.detection_overlay:
                self.detection_overlay.show_draw_area_overlay(False)
        self.check_ready_state()
    
    def set_parent_color_area(self, position):
        """设置父颜色区域"""
        self.parent_color_area_pos = position
        if position:
            self.select_parent_color_area_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_status_text(f"父颜色区域已设置: {position[2]}×{position[3]} 像素")
        else:
            self.select_parent_color_area_btn.setStyleSheet("")
        self.check_ready_state()
    
    def set_color_palette_button(self, position):
        """设置色盘按钮"""
        self.color_palette_button_pos = position
        if position:
            self.select_color_palette_button_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_status_text(f"色盘按钮已设置: {position[2]}×{position[3]} 像素")
        else:
            self.select_color_palette_button_btn.setStyleSheet("")
        self.check_ready_state()
    
    def set_color_swatch_return_button(self, position):
        """设置色板返回按钮"""
        self.color_swatch_return_button_pos = position
        if position:
            self.select_color_swatch_return_button_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_status_text(f"色板返回按钮已设置: {position[2]}×{position[3]} 像素")
        else:
            self.select_color_swatch_return_button_btn.setStyleSheet("")
        self.check_ready_state()
    
    def set_child_color_area(self, position):
        """设置子颜色区域"""
        self.child_color_area_pos = position
        if position:
            self.select_child_color_area_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_status_text(f"子颜色区域已设置: {position[2]}×{position[3]} 像素")
        else:
            self.select_child_color_area_btn.setStyleSheet("")
        self.check_ready_state()
    
    def set_background_color_button(self, position):
        """设置背景色按钮"""
        self.background_color_button_pos = position
        if position:
            self.select_background_color_button_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            self.update_status_text(f"背景色按钮已设置: {position[2]}×{position[3]} 像素")
        else:
            self.select_background_color_button_btn.setStyleSheet("")
        self.check_ready_state()
    
    def set_selected_image(self, image_path):
        """设置选择的图片"""
        self.selected_image_path = image_path
        if image_path:
            self.image_path_label.setText(os.path.basename(image_path))
            self.image_path_label.setStyleSheet("color: green;")
            self.update_status_text(f"已选择图片: {os.path.basename(image_path)}")
            
            # 显示原图预览
            self.display_original_image(image_path)
            # 启用处理图片按钮
            self.process_image_btn.setEnabled(True)
        else:
            self.image_path_label.setText("未选择图片")
            self.image_path_label.setStyleSheet("color: red;")
            self.original_image_label.setText("请选择图片")
            self.process_image_btn.setEnabled(False)
        self.check_ready_state()
    
    def display_original_image(self, image_path):
        """显示原图预览（使用Qt内置方法）"""
        try:
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                raise Exception("无法加载图片")
            # 按比例缩放至预览区域大小
            target_w, target_h = 300, 200
            scaled = pixmap.scaled(target_w, target_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.original_image_label.setPixmap(scaled)
            self.original_image_label.setAlignment(Qt.AlignCenter)
            self.original_image_label.setText("")
        except Exception as e:
            logging.error(f"显示原图预览失败: {e}")
            self.original_image_label.setText(f"图片加载失败: {str(e)}")
    
    def display_pixelized_image(self, pixelized_image):
        """显示像素化图片预览"""
        try:
            self.pixelized_image = pixelized_image
            
            # 计算等比例缩放的尺寸，保持原始比例
            original_width, original_height = pixelized_image.size
            max_display_size = 300  # 最大显示尺寸
            
            # 计算缩放比例，保持宽高比
            scale_ratio = min(max_display_size / original_width, max_display_size / original_height)
            
            # 计算新的尺寸
            new_width = int(original_width * scale_ratio)
            new_height = int(original_height * scale_ratio)
            
            # 使用NEAREST插值保持像素化效果，等比例缩放
            display_image = pixelized_image.resize((new_width, new_height), Image.NEAREST)
            pixmap = pil_to_qpixmap(display_image)
            
            # 设置QLabel的固定尺寸以匹配图片尺寸，防止拉伸
            self.pixelized_image_label.setFixedSize(new_width, new_height)
            self.pixelized_image_label.setPixmap(pixmap)
            self.pixelized_image_label.setText("")
            self.update_status_text("图片像素化完成")
            # 图片像素化完成后，检查就绪状态
            self.check_ready_state()
        except Exception as e:
            logging.error(f"显示像素化图片失败: {e}")
            self.pixelized_image_label.setText(f"像素化失败: {str(e)}")
    
    def display_pixel_debug_info(self, pixel_info_list):
        """显示像素调试信息"""
        try:
            if not pixel_info_list:
                self.update_status_text("没有像素信息可显示")
                return
            
            # 创建调试信息文本
            debug_text = f"像素调试信息 (共{len(pixel_info_list)}个像素点):\n\n"
            
            # 显示前20个像素的详细信息
            for i, pixel_info in enumerate(pixel_info_list[:20]):
                position = pixel_info['position']
                color = pixel_info['color']
                grid_pos = pixel_info.get('grid_pos', (0, 0))
                debug_text += f"像素{i+1}: 坐标({position[0]},{position[1]}) 颜色RGB{color} 网格({grid_pos[0]},{grid_pos[1]})\n"
            
            if len(pixel_info_list) > 20:
                debug_text += f"\n... 还有{len(pixel_info_list)-20}个像素点\n"
            
            # 统计信息
            positions = [info['position'] for info in pixel_info_list]
            unique_positions = len(set(positions))
            debug_text += f"\n统计信息:\n"
            debug_text += f"- 总像素数: {len(pixel_info_list)}\n"
            debug_text += f"- 唯一位置数: {unique_positions}\n"
            debug_text += f"- 重复位置数: {len(positions) - unique_positions}\n"
            
            # 显示在状态栏
            self.update_status_text(debug_text)
            
            # 同时输出到日志
            logging.info(f"像素调试信息: {debug_text}")
            
            # 询问用户是否要在绘画区域显示像素点
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, 
                '显示像素点', 
                f'是否要在绘画区域显示所有{len(pixel_info_list)}个像素点？\n这将帮助您直观地看到像素分布。',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            
            if reply == QMessageBox.Yes:
                self.display_pixels_on_screen(pixel_info_list)
            
        except Exception as e:
            logging.error(f"显示像素调试信息失败: {e}")
            self.update_status_text(f"显示像素调试信息失败: {str(e)}")
    
    def display_pixels_on_screen(self, pixel_info_list):
        """在屏幕上显示像素点overlay"""
        try:
            if not pixel_info_list:
                self.update_status_text("没有像素信息可显示")
                return
            
            if not self.draw_area_pos:
                self.update_status_text("没有绘画区域信息，无法显示overlay")
                return
            
            self.update_status_text(f"正在创建像素点overlay，共{len(pixel_info_list)}个像素点...")
            
            # 创建像素点overlay窗口
            from pixel_overlay import PixelOverlay
            self.pixel_overlay = PixelOverlay(
                pixel_info_list=pixel_info_list,
                draw_area_pos=self.draw_area_pos
            )
            
            # 显示overlay
            self.pixel_overlay.show()
            
            logging.info(f"像素点overlay已显示，共{len(pixel_info_list)}个像素点")
            
        except Exception as e:
            logging.error(f"显示像素点overlay失败: {e}")
            self.update_status_text(f"显示像素点overlay失败: {str(e)}")
    
    def on_debug_drawing_completed(self):
        """调试绘图完成回调"""
        try:
            self.update_status_text("像素点显示完成！")
            logging.info("调试像素点显示完成")
            
            # 清理工作线程
            if hasattr(self, 'debug_worker'):
                self.debug_worker.quit()
                self.debug_worker.wait(5000)  # 等待最多5秒
                if self.debug_worker.isRunning():
                    self.debug_worker.terminate()
                    self.debug_worker.wait(2000)  # 再等待2秒
                delattr(self, 'debug_worker')
                
        except Exception as e:
            logging.error(f"调试绘图完成处理失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 清理所有工作线程
            if hasattr(self, 'debug_worker'):
                self.debug_worker.quit()
                self.debug_worker.wait(3000)  # 等待3秒
                if self.debug_worker.isRunning():
                    self.debug_worker.terminate()
                    self.debug_worker.wait(2000)  # 再等待2秒
            
            # 关闭像素overlay
            if hasattr(self, 'pixel_overlay'):
                self.pixel_overlay.close()
                
        except Exception as e:
            logging.error(f"窗口关闭时清理线程失败: {e}")
        
        event.accept()
    

    
    def check_ready_state(self):
        """检查是否准备就绪"""
        logging.debug(f"[DEBUG] UI状态检查开始")
        
        draw_area_ready = self.draw_area_pos is not None
        parent_color_ready = self.parent_color_area_pos is not None
        palette_button_ready = self.color_palette_button_pos is not None
        return_button_ready = self.color_swatch_return_button_pos is not None
        child_color_ready = self.child_color_area_pos is not None
        background_button_ready = self.background_color_button_pos is not None
        image_ready = self.selected_image_path is not None
        pixelized_ready = self.pixelized_image is not None
        
        # 重要：只检查子级颜色，不检查父级颜色
        child_colors_count = len([c for c in self.collected_colors if not c.get('is_parent', False)])
        colors_ready = child_colors_count > 0
        
        logging.debug(f"[DEBUG] UI状态检查结果:")
        logging.debug(f"  - 绘画区域: {draw_area_ready} ({self.draw_area_pos})")
        logging.debug(f"  - 父颜色区域: {parent_color_ready} ({self.parent_color_area_pos})")
        logging.debug(f"  - 色盘按钮: {palette_button_ready} ({self.color_palette_button_pos})")
        logging.debug(f"  - 色板返回按钮: {return_button_ready} ({self.color_swatch_return_button_pos})")
        logging.debug(f"  - 子颜色区域: {child_color_ready} ({self.child_color_area_pos})")
        logging.debug(f"  - 背景色按钮: {background_button_ready} ({self.background_color_button_pos})")
        logging.debug(f"  - 图片选择: {image_ready} ({self.selected_image_path})")
        logging.debug(f"  - 图片像素化: {pixelized_ready} ({self.pixelized_image is not None})")
        logging.debug(f"  - 子级颜色收集: {colors_ready} ({child_colors_count} 种子级颜色，总共{len(self.collected_colors)}种颜色)")
        
        ready = (draw_area_ready and 
                parent_color_ready and 
                palette_button_ready and
                return_button_ready and
                child_color_ready and
                background_button_ready and
                image_ready and
                pixelized_ready and
                colors_ready)
        
        logging.debug(f"[DEBUG] UI总体就绪状态: {ready}")
        
        self.start_drawing_btn.setEnabled(ready)
        
        # 检查调试像素按钮状态（只要有像素化图片就可以调试）
        debug_ready = pixelized_ready
        self.debug_pixels_btn.setEnabled(debug_ready)
        
        # 检查收集颜色按钮状态
        collect_ready = (parent_color_ready and 
                        palette_button_ready and
                        return_button_ready and
                        child_color_ready and
                        background_button_ready)
        self.collect_colors_btn.setEnabled(collect_ready)
        
        # 检查清理颜色按钮状态（只有在有颜色时才启用）
        self.clear_colors_btn.setEnabled(len(self.collected_colors) > 0)
        
        if ready:
            self.update_status_text("所有设置完成，可以开始绘图！")
            logging.debug(f"[DEBUG] 所有设置完成，可以开始绘图！")
        else:
            missing = []
            if not draw_area_ready:
                missing.append("绘画区域")
            if not parent_color_ready:
                missing.append("父颜色区域")
            if not palette_button_ready:
                missing.append("色盘按钮")
            if not return_button_ready:
                missing.append("色板返回按钮")
            if not child_color_ready:
                missing.append("子颜色区域")
            if not background_button_ready:
                missing.append("背景色按钮")
            if not image_ready:
                missing.append("图片")
            if not pixelized_ready:
                missing.append("图片像素化")
            if not colors_ready:
                missing.append(f"颜色收集(当前{child_colors_count}种子级颜色)")
            
            status_msg = f"还需要设置: {', '.join(missing)}"
            self.update_status_text(status_msg)
            logging.debug(f"[DEBUG] {status_msg}")
    
    def get_aspect_ratio(self):
        """获取选择的图片比例"""
        ratio_text = self.aspect_ratio_combo.currentText()
        ratio_map = {
            "1:1": (1, 1),
            "16:9": (16, 9),
            "4:3": (4, 3),
            "3:4": (3, 4),
            "9:16": (9, 16)
        }
        return ratio_map.get(ratio_text, (1, 1))
    
    def update_size_options(self):
        """根据比例更新尺寸选项"""
        ratio = self.aspect_ratio_combo.currentText()
        
        # 根据比例设置不同的尺寸选项
        if ratio in ["16:9", "4:3", "1:1"]:
            # 16:9, 4:3, 1:1 使用相同的尺寸选项
            sizes = ["30个格子", "50个格子", "100个格子", "150个格子"]
        elif ratio == "3:4":
            # 3:4 使用不同的尺寸选项
            sizes = ["24个格子", "38个格子", "76个格子", "114个格子"]
        elif ratio == "9:16":
            # 9:16 使用不同的尺寸选项
            sizes = ["18个格子", "28个格子", "56个格子", "84个格子"]
        else:
            # 默认选项
            sizes = ["30个格子", "50个格子", "100个格子", "150个格子"]
        
        # 保存当前选择
        current_text = self.size_combo.currentText()
        
        # 更新选项
        self.size_combo.clear()
        self.size_combo.addItems(sizes)
        
        # 尝试恢复之前的选择，如果不存在则选择第一个
        if current_text in sizes:
            self.size_combo.setCurrentText(current_text)
        else:
            self.size_combo.setCurrentIndex(0)
    
    def get_size_info(self):
        """获取当前选择的尺寸信息"""
        ratio_text = self.aspect_ratio_combo.currentText()
        size_text = self.size_combo.currentText()
        
        # 从尺寸文本中提取数字
        import re
        size_match = re.search(r'(\d+)个格子', size_text)
        if size_match:
            grid_count = int(size_match.group(1))
        else:
            grid_count = 100  # 默认值
        
        return ratio_text, size_text, grid_count
    
    def get_aspect_ratio_and_size(self):
        """获取当前选择的比例和尺寸信息（用于配置保存）"""
        return {
            'aspect_ratio': self.aspect_ratio_combo.currentText(),
            'size': self.size_combo.currentText()
        }
    
    def set_aspect_ratio_and_size(self, aspect_ratio, size):
        """设置比例和尺寸（用于配置加载）"""
        try:
            logging.info(f"开始设置比例和尺寸: {aspect_ratio}, {size}")
            
            # 设置比例
            if aspect_ratio and aspect_ratio in ["1:1", "16:9", "4:3", "3:4", "9:16"]:
                logging.info(f"设置比例下拉框为: {aspect_ratio}")
                self.aspect_ratio_combo.setCurrentText(aspect_ratio)
                # 比例改变会自动更新尺寸选项
                
                # 等待一下让尺寸选项更新
                import time
                time.sleep(0.1)
                
                # 设置尺寸
                if size:
                    logging.info(f"设置尺寸下拉框为: {size}")
                    # 检查尺寸选项是否可用
                    available_sizes = [self.size_combo.itemText(i) for i in range(self.size_combo.count())]
                    logging.info(f"当前可用的尺寸选项: {available_sizes}")
                    
                    if size in available_sizes:
                        self.size_combo.setCurrentText(size)
                        logging.info(f"成功设置尺寸: {size}")
                    else:
                        logging.warning(f"尺寸选项 '{size}' 不在可用选项中: {available_sizes}")
                        # 尝试设置第一个可用选项
                        if available_sizes:
                            self.size_combo.setCurrentIndex(0)
                            logging.info(f"设置默认尺寸: {available_sizes[0]}")
                    
                logging.info(f"已设置比例: {aspect_ratio}, 尺寸: {size}")
                return True
            else:
                logging.warning(f"无效的比例设置: {aspect_ratio}")
                return False
        except Exception as e:
            logging.error(f"设置比例和尺寸失败: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return False
    
    def update_status_text(self, text):
        """更新状态文本"""
        self.status_text.append(f"[{time.strftime('%H:%M:%S')}] {text}")
        # 自动滚动到底部
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_drawing_progress(self, progress_text):
        """更新绘图进度"""
        self.update_status_text(f"绘图进度: {progress_text}")
    
    def update_progress_bar(self, current, total):
        """更新进度条"""
        try:
            if total > 0:
                percentage = int((current / total) * 100)
                self.progress_bar.setValue(percentage)
                
                # 更新进度标签
                self.progress_label.setText(f"正在绘制: {current}/{total} ({percentage}%)")
                
                # 根据进度改变颜色
                if percentage < 30:
                    self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }")
                elif percentage < 70:
                    self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #2196F3; }")
                else:
                    self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
            else:
                self.progress_bar.setValue(0)
                self.progress_label.setText("等待开始绘图...")
        except Exception as e:
            logging.error(f"更新进度条失败: {e}")
    
    def reset_progress_bar(self):
        """重置进度条"""
        try:
            self.progress_bar.setValue(0)
            self.progress_label.setText("等待开始绘图...")
            self.progress_bar.setStyleSheet("")
        except Exception as e:
            logging.error(f"重置进度条失败: {e}")
    
    def set_progress_bar_max(self, max_value):
        """设置进度条最大值"""
        try:
            self.progress_bar.setMaximum(max_value)
            self.progress_bar.setValue(0)
            self.progress_label.setText(f"准备绘制: 0/{max_value} (0%)")
        except Exception as e:
            logging.error(f"设置进度条最大值失败: {e}")
    
    def get_draw_area_position(self):
        """获取绘画区域位置"""
        return self.draw_area_pos
    
    def get_parent_color_area_position(self):
        """获取父颜色区域位置"""
        return self.parent_color_area_pos
    
    def get_color_palette_button_position(self):
        """获取色盘按钮位置"""
        return self.color_palette_button_pos
    
    def get_color_swatch_return_button_position(self):
        """获取色板返回按钮位置"""
        return self.color_swatch_return_button_pos
    
    def get_child_color_area_position(self):
        """获取子颜色区域位置"""
        return self.child_color_area_pos
    
    def get_background_color_button_position(self):
        """获取背景色按钮位置"""
        return self.background_color_button_pos
    
    def get_selected_image_path(self):
        """获取选择的图片路径"""
        return self.selected_image_path
    
    def get_pixelized_image(self):
        """获取像素化图片"""
        return self.pixelized_image
    
    def get_color_palette(self):
        """获取颜色调色板"""
        return self.color_palette
    
    def display_collected_colors(self, colors):
        """显示收集到的颜色（使用固定布局结构，避免运行时布局冲突）"""
        try:
            logging.info(f"display_collected_colors 开始，收到 {len(colors) if colors else 0} 个颜色")
            
            if not colors:
                # 显示提示信息
                self._show_no_colors_message()
                return
            
            # 分析颜色数据结构
            parent_colors = [c for c in colors if c.get('is_parent', False)]
            child_colors = [c for c in colors if not c.get('is_parent', False)]
            logging.info(f"颜色分析: 父颜色{len(parent_colors)}个, 子颜色{len(child_colors)}个")
            
            # 检查子颜色的父颜色信息
            for i, child_color in enumerate(child_colors[:5]):  # 只检查前5个
                parent_info = child_color.get('parent', '无')
                parent_idx = child_color.get('parent_index', '无')
                logging.debug(f"子颜色{i}: RGB{child_color['rgb']}, 父颜色: {parent_info}, 父索引: {parent_idx}")
            
            # 按父级分组颜色
            color_groups = self._group_colors_by_parent(colors)
            
            # 使用固定布局结构显示颜色
            self._display_colors_with_fixed_layout(color_groups)
            
            # 更新状态
            total_colors = len(colors)
            total_groups = len(color_groups)
            self.update_status_text(f"🎨 显示收集到的颜色，共{total_colors}种，分为{total_groups}个父级组")
            logging.info(f"状态更新完成: 共{total_colors}种颜色，{total_groups}个组")
            
        except Exception as e:
            logging.error(f"显示收集到的颜色失败: {e}")
            import traceback
            traceback.print_exc()
            self.update_status_text(f"显示收集到的颜色失败: {str(e)}")
    
    def _show_no_colors_message(self):
        """显示无颜色提示"""
        # 清空现有内容，只显示提示
        self._clear_colors_display()
        
        label = QLabel("暂无收集到的颜色")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #666666; font-size: 12px;")
        
        # 使用现有的布局结构
        if not hasattr(self, '_no_colors_label'):
            self._no_colors_label = label
            self._colors_main_layout.addWidget(label)
        else:
            # 如果已存在，更新文本
            self._no_colors_label.setText("暂无收集到的颜色")
    
    def _group_colors_by_parent(self, colors):
        """按父级分组颜色"""
        logging.info("开始按父级分组颜色")
        
        # 只处理子级颜色，过滤掉父级颜色
        child_colors = [color_info for color_info in colors if not color_info.get('is_parent', False)]
        logging.info(f"过滤后剩余{len(child_colors)}种子级颜色")
        
        color_groups = {}
        for color_info in child_colors:
            parent_key = color_info.get('parent', '未知来源')
            logging.debug(f"颜色 RGB{color_info['rgb']} 分组到: {parent_key}")
            if parent_key not in color_groups:
                color_groups[parent_key] = []
            color_groups[parent_key].append(color_info)
        
        logging.info(f"颜色分组完成，共{len(color_groups)}个组")
        for group_name, group_colors in color_groups.items():
            logging.debug(f"组 '{group_name}': {len(group_colors)}个颜色")
        
        return color_groups
    
    def _display_colors_with_fixed_layout(self, color_groups):
        """使用固定布局结构显示颜色"""
        # 清空现有内容
        self._clear_colors_display()
        
        # 为每个颜色组创建或更新显示
        for i, (parent_name, group_colors) in enumerate(color_groups.items()):
            if i >= 16:  # 限制最多16个组
                logging.warning(f"颜色组数量超过16个，跳过第{i+1}组: {parent_name}")
                break
            
            self._create_or_update_color_group(i, parent_name, group_colors)
    
    def _clear_colors_display(self):
        """清空颜色显示区域"""
        # 隐藏无颜色提示标签
        if hasattr(self, '_no_colors_label'):
            self._no_colors_label.hide()
        
        # 隐藏所有颜色组容器
        for i in range(16):
            group_key = f'_color_group_{i}'
            if hasattr(self, group_key):
                getattr(self, group_key).hide()
    
    def _create_or_update_color_group(self, group_index, parent_name, group_colors):
        """创建或更新颜色组显示"""
        group_key = f'_color_group_{group_index}'
        
        # 如果颜色组容器不存在，创建它
        if not hasattr(self, group_key):
            self._create_color_group_container(group_index, parent_name)
        
        # 获取颜色组容器
        group_container = getattr(self, group_key)
        group_container.show()  # 显示容器
        
        # 更新颜色组内容
        self._update_color_group_content(group_container, parent_name, group_colors)
    
    def _create_color_group_container(self, group_index, parent_name):
        """创建颜色组容器"""
        group_key = f'_color_group_{group_index}'
        
        # 创建父级组容器
        group_container = QFrame()
        group_container.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        # 创建布局
        group_layout = QVBoxLayout()
        group_layout.setSpacing(8)
        group_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建标题行（包含父级颜色色块）
        title_row_layout = QHBoxLayout()
        title_row_layout.setSpacing(10)
        title_row_layout.setContentsMargins(0, 0, 0, 0)
        
        # 创建标题文本
        title_key = f'_color_group_title_{group_index}'
        group_title = QLabel(f"🎨 父级颜色: {parent_name}")
        group_title.setStyleSheet("""
            QLabel {
                color: #2c3e50;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 12px;
                background-color: #3498db;
                color: white;
                border-radius: 6px;
                margin-bottom: 5px;
            }
        """)
        title_row_layout.addWidget(group_title)
        
        # 创建父级颜色色块
        parent_color_key = f'_color_group_parent_color_{group_index}'
        parent_color_block = QFrame()
        parent_color_block.setFixedSize(32, 32)
        parent_color_block.setStyleSheet("""
            QFrame {
                background-color: #cccccc;
                border: 2px solid #999999;
                border-radius: 6px;
            }
        """)
        parent_color_block.setToolTip("父级颜色色块")
        title_row_layout.addWidget(parent_color_block)
        
        # 添加弹性空间
        title_row_layout.addStretch()
        
        # 将标题行添加到组布局
        group_layout.addLayout(title_row_layout)
                
                # 创建颜色说明
        subtitle_key = f'_color_group_subtitle_{group_index}'
        subtitle = QLabel(f"包含 0 种子级颜色:")
        subtitle.setStyleSheet("""
            QLabel {
                color: #7f8c8d;
                font-size: 11px;
                font-style: italic;
                padding: 2px 0px;
            }
        """)
        group_layout.addWidget(subtitle)
        
        # 创建颜色网格
        grid_key = f'_color_group_grid_{group_index}'
        color_grid = QGridLayout()
        color_grid.setSpacing(4)
        color_grid.setContentsMargins(5, 5, 5, 5)
        group_layout.addLayout(color_grid)
        
        # 设置容器布局
        group_container.setLayout(group_layout)
        
        # 将容器添加到主布局
        self._colors_main_layout.addWidget(group_container)
        
        # 保存引用
        setattr(self, group_key, group_container)
        setattr(self, title_key, group_title)
        setattr(self, parent_color_key, parent_color_block)
        setattr(self, subtitle_key, subtitle)
        setattr(self, grid_key, color_grid)
        
        logging.debug(f"创建颜色组容器 {group_index}: {parent_name}")
    
    def _update_color_group_content(self, group_container, parent_name, group_colors):
        """更新颜色组内容"""
        # 从容器名称中提取组索引
        group_index = 0
        for i in range(16):
            if hasattr(self, f'_color_group_{i}') and getattr(self, f'_color_group_{i}') == group_container:
                group_index = i
                break
        
        # 更新标题
        title_key = f'_color_group_title_{group_index}'
        if hasattr(self, title_key):
            title = getattr(self, title_key)
            title.setText(f"🎨 父级颜色: {parent_name}")
        
        # 更新父级颜色色块
        parent_color_key = f'_color_group_parent_color_{group_index}'
        if hasattr(self, parent_color_key):
            parent_color_block = getattr(self, parent_color_key)
            # 从父级名称中提取RGB值
            rgb_color = self._extract_rgb_from_parent_name(parent_name)
            if rgb_color:
                self._update_parent_color_block(parent_color_block, rgb_color)
        
        # 更新副标题
        subtitle_key = f'_color_group_subtitle_{group_index}'
        if hasattr(self, subtitle_key):
            subtitle = getattr(self, subtitle_key)
            subtitle.setText(f"包含 {len(group_colors)} 种子级颜色:")
        
        # 更新颜色网格
        grid_key = f'_color_group_grid_{group_index}'
        if hasattr(self, grid_key):
            color_grid = getattr(self, grid_key)
            
            # 清空现有颜色块
            while color_grid.count():
                item = color_grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # 添加新的颜色块
            cols_per_row = 10
            for i, color_info in enumerate(group_colors):
                row = i // cols_per_row
                col = i % cols_per_row
                
                color_block = self._create_color_block(color_info)
                color_grid.addWidget(color_block, row, col)
                logging.debug(f"添加颜色块 {i+1}/{len(group_colors)}: RGB{color_info['rgb']}")
    
    def _extract_rgb_from_parent_name(self, parent_name):
        """从父级名称中提取RGB值"""
        try:
            # 尝试从名称中提取RGB值，格式如 "父级颜色1(RGB(5, 22, 22))"
            if "RGB(" in parent_name and ")" in parent_name:
                rgb_start = parent_name.find("RGB(") + 4
                rgb_end = parent_name.find(")", rgb_start)
                rgb_text = parent_name[rgb_start:rgb_end]
                
                # 解析RGB值
                rgb_parts = rgb_text.split(",")
                if len(rgb_parts) == 3:
                    r = int(rgb_parts[0].strip())
                    g = int(rgb_parts[1].strip())
                    b = int(rgb_parts[2].strip())
                    return (r, g, b)
        except Exception as e:
            logging.debug(f"无法从父级名称提取RGB值: {parent_name}, 错误: {e}")
        
        return None
    
    def _update_parent_color_block(self, parent_color_block, rgb_color):
        """更新父级颜色色块的颜色"""
        r, g, b = rgb_color
        
        # 根据颜色亮度调整边框颜色
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        border_color = "#333333" if brightness > 128 else "#ffffff"
        
        parent_color_block.setStyleSheet(f"""
            QFrame {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid {border_color};
                border-radius: 6px;
            }}
            QFrame:hover {{
                border: 3px solid #e74c3c;
                transform: scale(1.1);
            }}
        """)
        
        # 更新工具提示
        parent_color_block.setToolTip(f"父级颜色: RGB({r}, {g}, {b})")
    
    def _create_color_block(self, color_info):
        """创建颜色块"""
        color_block = QFrame()
        color_block.setFixedSize(28, 28)
        
        # 根据颜色亮度调整边框颜色
        r, g, b = color_info['rgb']
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        border_color = "#333333" if brightness > 128 else "#ffffff"
        
        color_block.setStyleSheet(f"""
            QFrame {{
                background-color: rgb({r}, {g}, {b});
                border: 2px solid {border_color};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border: 3px solid #e74c3c;
            }}
        """)
                    
        # 创建工具提示
        color_type = "父级颜色" if color_info.get('is_parent', False) else "子级颜色"
        tooltip = f"🎨 {color_type}\nRGB: {color_info['rgb']}\n位置: ({color_info['position'][0]}, {color_info['position'][1]})\n来源: {color_info['parent']}"
        color_block.setToolTip(tooltip)
                    
        return color_block
    
    def set_collected_colors(self, colors):
        """设置收集到的颜色列表"""
        try:
            logging.info(f"set_collected_colors 被调用，收到 {len(colors) if colors else 0} 个颜色")
            if colors:
                logging.debug(f"前3个颜色示例: {colors[:3]}")
            
            self.collected_colors = colors
            logging.debug("准备调用 display_collected_colors")
                
                # 调用显示方法
            self.display_collected_colors(colors)
                
            logging.info("display_collected_colors 调用完成")
                
            # 收集颜色完成后，检查就绪状态
            self.check_ready_state()
            
        except Exception as e:
            error_msg = f"set_collected_colors 失败: {e}"
            logging.error(error_msg)
            import traceback
            logging.error(f"详细错误信息: {traceback.format_exc()}")
            # 显示错误信息给用户
            self.update_status_text(f"设置收集到的颜色失败: {str(e)}")
            # 重新抛出异常，确保能被上层捕获
            raise
    
    def set_drawing_button_text(self, text):
        """设置绘图按钮的文本"""
        self.start_drawing_btn.setText(text)
    
    def set_drawing_button_enabled(self, enabled):
        """设置绘图按钮的启用状态"""
        self.start_drawing_btn.setEnabled(enabled)
        if enabled:
            self.update_status_text("绘图功能已启用")
        else:
            self.update_status_text("绘图功能已禁用")
    
    def keyPressEvent(self, event):
        """处理键盘按键事件"""
        if event.key() == Qt.Key_P:
            # 按下P键立即停止绘图
            logging.info("检测到P键按下，立即停止绘图")
            self.update_status_text("按下P键，立即停止绘图")
            self.stop_drawing_requested.emit()
            event.accept()
        else:
            # 其他按键交给父类处理
            super().keyPressEvent(event)
    
    def get_delay_settings(self):
        """获取延迟配置"""
        return {
            'color_delay': self.color_delay_spin.value(),
            'draw_delay': self.draw_delay_spin.value(),
            'move_delay': self.move_delay_spin.value()
        }
    

    
    # 配置管理方法
    def get_current_config_name(self):
        """获取当前配置名称"""
        return self.config_combo.currentText().strip()
    
    def validate_config_name(self, config_name):
        """验证配置名称"""
        if not config_name:
            return False, "配置名称不能为空"
        
        if len(config_name) > 50:
            return False, "配置名称不能超过50个字符"
        
        # 检查是否包含非法字符
        import re
        if re.search(r'[<>:"/\\|?*]', config_name):
            return False, "配置名称不能包含以下字符: < > : \" / \\ | ? *"
        
        return True, ""
    
    def update_config_combo(self, configs):
        """更新配置下拉框"""
        current_text = self.config_combo.currentText()
        self.config_combo.clear()
        self.config_combo.addItems(configs)
        
        # 尝试恢复之前的选择
        if current_text and current_text in configs:
            self.config_combo.setCurrentText(current_text)
    
    def add_new_config(self, config_name):
        """添加新配置到下拉框"""
        if config_name not in [self.config_combo.itemText(i) for i in range(self.config_combo.count())]:
            self.config_combo.addItem(config_name)
            self.config_combo.setCurrentText(config_name)
    
    def set_config_name(self, config_name):
        """设置配置名称"""
        self.config_combo.setCurrentText(config_name)
    
    def clear_config_name(self):
        """清空配置名称"""
        self.config_combo.clearEditText()
    
    def show_draw_area_position(self, pos, size):
        """显示绘画区域位置"""
        # 保存绘画区域信息
        self.last_draw_area_pos = pos
        self.last_draw_area_size = size
        
        # 只有在checkbox选中时才显示绘画区域框
        if hasattr(self, 'show_draw_area_checkbox') and self.show_draw_area_checkbox.isChecked():
            if hasattr(self, 'detection_overlay') and self.detection_overlay:
                self.detection_overlay.set_draw_area_position(pos, size)
                self.detection_overlay.show_draw_area_overlay(True)
                
                # 确保覆盖层可见
                if not self.detection_overlay.isVisible():
                    self.detection_overlay.show()
                    self.detection_overlay.raise_()
                
                self.update_status_text(f"绘画区域已显示: 位置({pos[0]}, {pos[1]}), 大小: {size[0]}x{size[1]}")
            else:
                self.update_status_text("检测覆盖层不可用")
        else:
            self.update_status_text(f"绘画区域已更新: 位置({pos[0]}, {pos[1]}), 大小: {size[0]}x{size[1]} (框已隐藏)")
    
    def _on_draw_area_checkbox_changed(self, state):
        """处理绘画区域显示checkbox状态改变"""
        try:
            if state == Qt.Checked:
                # 显示绘画区域框
                if hasattr(self, 'detection_overlay') and self.detection_overlay:
                    # 如果有保存的绘画区域位置，直接显示
                    if hasattr(self, 'last_draw_area_pos') and hasattr(self, 'last_draw_area_size'):
                        if self.last_draw_area_pos and self.last_draw_area_size:
                            self.detection_overlay.set_draw_area_position(self.last_draw_area_pos, self.last_draw_area_size)
                            self.detection_overlay.show_draw_area_overlay(True)
                            if not self.detection_overlay.isVisible():
                                self.detection_overlay.show()
                                self.detection_overlay.raise_()
                            self.update_status_text("绘画区域框已显示")
                        else:
                            # 没有保存的位置，提示用户先选择绘画区域
                            self.update_status_text("没有保存的绘画区域位置，请先选择绘画区域")
                    else:
                        self.update_status_text("没有保存的绘画区域位置，请先选择绘画区域")
                else:
                    self.update_status_text("检测覆盖层不可用")
            else:
                # 隐藏绘画区域框
                if hasattr(self, 'detection_overlay') and self.detection_overlay:
                    self.detection_overlay.show_draw_area_overlay(False)
                    self.update_status_text("绘画区域框已隐藏")
        except Exception as e:
            logging.error(f"处理绘画区域checkbox状态改变失败: {e}")
            self.update_status_text(f"绘画区域控制失败: {str(e)}")


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
        
        # 绘画区域位置信息
        self.draw_area_pos = None
        self.draw_area_size = None
        self.show_draw_area = False
        
        # 设置窗口大小为全屏
        screen = QApplication.primaryScreen()
        self.setGeometry(screen.geometry())
        

    
    def set_draw_area_position(self, pos, size):
        """设置绘画区域位置和大小"""
        self.draw_area_pos = pos
        self.draw_area_size = size
        self.update()
    
    def show_draw_area_overlay(self, show=True):
        """显示或隐藏绘画区域位置"""
        self.show_draw_area = show
        self.update()
        
    def paintEvent(self, event):
        """绘制检测框"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 绘制绘画区域位置（绿色方框）
        if self.show_draw_area and self.draw_area_pos and self.draw_area_size:
            x, y = self.draw_area_pos
            width, height = self.draw_area_size
            
            # 绘制绿色方框 - 更细更透明
            pen = QPen(QColor(76, 175, 80, 200), 1)  # 绿色，1像素宽度，半透明
            painter.setPen(pen)
            painter.drawRect(x, y, width, height)
            
            # 绘制标签
            text = f"绘画区域 ({width}x{height})"
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


if __name__ == "__main__":
    import time
    app = QApplication(sys.argv)
    window = PaintMainUI()
    window.show()
    sys.exit(app.exec_())