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
    QGridLayout, QFrame, QSizePolicy, QDoubleSpinBox
)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QPen, QColor, QKeySequence
from PyQt5.QtCore import Qt, pyqtSignal, QRect
from PIL import Image


def setup_logging():
    """设置日志配置"""
    # 创建logs目录
    logs_dir = os.path.join("logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # 配置日志
    log_file = os.path.join(logs_dir, "paint_app.log")
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
    
    w, h = pil_img.size
    qimg = QImage(pil_img.tobytes(), w, h, img_format)
    if pil_img.mode == "RGB":
        qimg = qimg.rgbSwapped()
    return QPixmap.fromImage(qimg)


class PaintMainUI(QWidget):
    """绘图助手主界面"""
    
    # 信号定义
    select_draw_area_requested = pyqtSignal()  # 选择绘画区域请求
    select_color_area_requested = pyqtSignal()  # 选择颜色区域请求
    select_image_requested = pyqtSignal()  # 选择图片请求
    process_image_requested = pyqtSignal(str, int)  # 处理图片请求(比例, 像素数量)
    start_drawing_requested = pyqtSignal()  # 开始绘图请求
    stop_drawing_requested = pyqtSignal()  # 停止绘图请求
    
    def __init__(self):
        super().__init__()
        
        # 初始化变量
        self.draw_area_pos = None
        self.color_area_pos = None
        self.selected_image_path = None
        self.pixelized_image = None
        self.color_palette = []
        
        self.init_ui()
        self.connect_signals()
        
        # 设置焦点策略，确保能接收键盘事件
        self.setFocusPolicy(Qt.StrongFocus)
        
        logging.info("绘图助手UI初始化完成")
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("绘图助手 - 心动小镇自动绘图工具")
        self.setGeometry(100, 100, 1000, 800)
        
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
        self.draw_area_status = QLabel("未选择绘画区域")
        self.draw_area_status.setStyleSheet("color: red;")
        
        step1_layout.addWidget(self.select_draw_area_btn)
        step1_layout.addWidget(self.draw_area_status)
        step1_group.setLayout(step1_layout)
        
        # 步骤2: 选择颜色区域
        step2_group = QGroupBox("步骤2: 选择颜色区域")
        step2_layout = QVBoxLayout()
        
        self.select_color_area_btn = QPushButton("选择颜色区域")
        self.select_color_area_btn.setMinimumHeight(40)
        self.color_area_status = QLabel("未选择颜色区域")
        self.color_area_status.setStyleSheet("color: red;")
        
        step2_layout.addWidget(self.select_color_area_btn)
        step2_layout.addWidget(self.color_area_status)
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
        
        # 像素数量设置
        self.pixel_count_spin = QSpinBox()
        self.pixel_count_spin.setRange(10, 500)
        self.pixel_count_spin.setValue(100)
        self.pixel_count_spin.setSuffix(" 像素")
        
        # 延迟配置设置
        self.color_delay_spin = QDoubleSpinBox()
        self.color_delay_spin.setRange(0.1, 5.0)
        self.color_delay_spin.setValue(0.5)
        self.color_delay_spin.setSingleStep(0.1)
        self.color_delay_spin.setSuffix(" 秒")
        self.color_delay_spin.setDecimals(1)
        
        self.draw_delay_spin = QDoubleSpinBox()
        self.draw_delay_spin.setRange(0.01, 1.0)
        self.draw_delay_spin.setValue(0.05)
        self.draw_delay_spin.setSingleStep(0.01)
        self.draw_delay_spin.setSuffix(" 秒")
        self.draw_delay_spin.setDecimals(2)
        
        self.move_delay_spin = QDoubleSpinBox()
        self.move_delay_spin.setRange(0.001, 0.1)
        self.move_delay_spin.setValue(0.01)
        self.move_delay_spin.setSingleStep(0.001)
        self.move_delay_spin.setSuffix(" 秒")
        self.move_delay_spin.setDecimals(3)
        


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
        step3_layout.addRow("横向像素数:", self.pixel_count_spin)
        step3_layout.addRow("颜色点击延迟:", self.color_delay_spin)
        step3_layout.addRow("绘图点击延迟:", self.draw_delay_spin)
        step3_layout.addRow("鼠标移动延迟:", self.move_delay_spin)
        step3_layout.addRow("处理图片:", self.process_image_btn)
        step3_group.setLayout(step3_layout)
        
        # 步骤4: 开始绘图
        step4_group = QGroupBox("步骤4: 开始绘图")
        step4_layout = QVBoxLayout()
        
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
        
        step4_layout.addWidget(self.start_drawing_btn)
        step4_group.setLayout(step4_layout)
        
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
        layout.addWidget(step1_group)
        layout.addWidget(step2_group)
        layout.addWidget(step3_group)
        layout.addWidget(step4_group)
        layout.addWidget(status_group)
        layout.addStretch()
        
        panel.setLayout(layout)
        return panel
    
    def create_preview_panel(self):
        """创建右侧预览面板"""
        panel = QWidget()
        layout = QVBoxLayout()
        
        # 原图预览
        original_group = QGroupBox("原图预览")
        original_layout = QVBoxLayout()
        
        self.original_image_label = QLabel("请选择图片")
        self.original_image_label.setAlignment(Qt.AlignCenter)
        self.original_image_label.setMinimumHeight(200)
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
        self.pixelized_image_label.setStyleSheet("""
            QLabel {
                border: 2px dashed #cccccc;
                background-color: #f9f9f9;
            }
        """)
        
        pixelized_layout.addWidget(self.pixelized_image_label)
        pixelized_group.setLayout(pixelized_layout)
        
        # 颜色调色板预览
        palette_group = QGroupBox("颜色调色板 (2列×8行)")
        palette_layout = QVBoxLayout()
        
        self.palette_frame = QFrame()
        self.palette_frame.setMinimumHeight(200)
        self.palette_frame.setStyleSheet("""
            QFrame {
                border: 2px dashed #cccccc;
                background-color: #f9f9f9;
            }
        """)
        
        palette_layout.addWidget(self.palette_frame)
        palette_group.setLayout(palette_layout)
        
        # 添加所有组件到面板
        layout.addWidget(original_group)
        layout.addWidget(pixelized_group)
        layout.addWidget(palette_group)
        
        panel.setLayout(layout)
        return panel
    
    def connect_signals(self):
        """连接信号"""
        self.select_draw_area_btn.clicked.connect(self.select_draw_area_requested.emit)
        self.select_color_area_btn.clicked.connect(self.select_color_area_requested.emit)
        self.select_image_btn.clicked.connect(self.select_image_requested.emit)
        self.process_image_btn.clicked.connect(self.on_process_image_clicked)
        self.start_drawing_btn.clicked.connect(self.start_drawing_requested.emit)
        
        # 设置变化时的处理
        self.aspect_ratio_combo.currentTextChanged.connect(self.on_settings_changed)
        self.pixel_count_spin.valueChanged.connect(self.on_settings_changed)
    
    def on_settings_changed(self):
        """设置变化时的处理"""
        if self.selected_image_path:
            self.update_status_text("设置已更改，请重新处理图片")
    
    def on_process_image_clicked(self):
        """处理图片按钮点击事件"""
        if self.selected_image_path:
            ratio_text = self.aspect_ratio_combo.currentText()
            pixel_count = self.pixel_count_spin.value()
            self.process_image_requested.emit(ratio_text, pixel_count)
            self.update_status_text(f"开始处理图片，比例: {ratio_text}, 像素数: {pixel_count}")
    
    def set_draw_area(self, position):
        """设置绘画区域"""
        self.draw_area_pos = position
        if position:
            self.draw_area_status.setText(f"已选择: ({position[0]}, {position[1]}, {position[2]}×{position[3]})")
            self.draw_area_status.setStyleSheet("color: green;")
            self.update_status_text(f"绘画区域已设置: {position[2]}×{position[3]} 像素")
        else:
            self.draw_area_status.setText("未选择绘画区域")
            self.draw_area_status.setStyleSheet("color: red;")
        self.check_ready_state()
    
    def set_color_area(self, position):
        """设置颜色区域"""
        self.color_area_pos = position
        if position:
            self.color_area_status.setText(f"已选择: ({position[0]}, {position[1]}, {position[2]}×{position[3]})")
            self.color_area_status.setStyleSheet("color: green;")
            self.update_status_text(f"颜色区域已设置: {position[2]}×{position[3]} 像素")
        else:
            self.color_area_status.setText("未选择颜色区域")
            self.color_area_status.setStyleSheet("color: red;")
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
        """显示原图预览"""
        try:
            image = Image.open(image_path)
            # 缩放图片以适应预览区域
            image.thumbnail((300, 200), Image.Resampling.LANCZOS)
            pixmap = pil_to_qpixmap(image)
            self.original_image_label.setPixmap(pixmap)
            self.original_image_label.setText("")
        except Exception as e:
            logging.error(f"显示原图预览失败: {e}")
            self.original_image_label.setText(f"图片加载失败: {str(e)}")
    
    def display_pixelized_image(self, pixelized_image):
        """显示像素化图片预览"""
        try:
            self.pixelized_image = pixelized_image
            # 放大像素化图片以便查看
            display_image = pixelized_image.resize((300, 300), Image.NEAREST)
            pixmap = pil_to_qpixmap(display_image)
            self.pixelized_image_label.setPixmap(pixmap)
            self.pixelized_image_label.setText("")
            self.update_status_text("图片像素化完成")
        except Exception as e:
            logging.error(f"显示像素化图片失败: {e}")
            self.pixelized_image_label.setText(f"像素化失败: {str(e)}")
    
    def display_color_palette(self, colors):
        """显示颜色调色板"""
        try:
            self.color_palette = colors
            
            # 清除旧的布局
            if self.palette_frame.layout():
                for i in reversed(range(self.palette_frame.layout().count())):
                    self.palette_frame.layout().itemAt(i).widget().setParent(None)
            
            # 创建2列8行的网格布局
            grid_layout = QGridLayout()
            
            for i, color in enumerate(colors[:16]):  # 最多16个颜色
                row = i // 2
                col = i % 2
                
                color_label = QLabel()
                color_label.setFixedSize(60, 20)
                color_label.setStyleSheet(f"background-color: rgb({color[0]}, {color[1]}, {color[2]}); border: 1px solid black;")
                color_label.setToolTip(f"RGB({color[0]}, {color[1]}, {color[2]})")
                
                grid_layout.addWidget(color_label, row, col)
            
            self.palette_frame.setLayout(grid_layout)
            self.update_status_text(f"颜色调色板已生成，共{len(colors)}种颜色")
            
        except Exception as e:
            logging.error(f"显示颜色调色板失败: {e}")
            self.update_status_text(f"颜色调色板生成失败: {str(e)}")
    
    def check_ready_state(self):
        """检查是否准备就绪"""
        ready = (self.draw_area_pos is not None and 
                self.color_area_pos is not None and 
                self.selected_image_path is not None and
                self.pixelized_image is not None and
                len(self.color_palette) > 0)
        
        self.start_drawing_btn.setEnabled(ready)
        
        if ready:
            self.update_status_text("所有设置完成，可以开始绘图！")
        else:
            missing = []
            if not self.draw_area_pos:
                missing.append("绘画区域")
            if not self.color_area_pos:
                missing.append("颜色区域")
            if not self.selected_image_path:
                missing.append("图片")
            if not self.pixelized_image:
                missing.append("图片像素化")
            if len(self.color_palette) == 0:
                missing.append("颜色调色板")
            
            self.update_status_text(f"还需要设置: {', '.join(missing)}")
    
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
    
    def get_pixel_count(self):
        """获取横向像素数量"""
        return self.pixel_count_spin.value()
    
    def update_status_text(self, text):
        """更新状态文本"""
        self.status_text.append(f"[{time.strftime('%H:%M:%S')}] {text}")
        # 自动滚动到底部
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def update_drawing_progress(self, progress_text):
        """更新绘图进度"""
        self.update_status_text(f"绘图进度: {progress_text}")
    
    def get_draw_area_position(self):
        """获取绘画区域位置"""
        return self.draw_area_pos
    
    def get_color_area_position(self):
        """获取颜色区域位置"""
        return self.color_area_pos
    
    def get_selected_image_path(self):
        """获取选择的图片路径"""
        return self.selected_image_path
    
    def get_pixelized_image(self):
        """获取像素化图片"""
        return self.pixelized_image
    
    def get_color_palette(self):
        """获取颜色调色板"""
        return self.color_palette
    
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
    



if __name__ == "__main__":
    import time
    app = QApplication(sys.argv)
    window = PaintMainUI()
    window.show()
    sys.exit(app.exec_())