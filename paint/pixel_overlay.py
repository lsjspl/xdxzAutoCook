#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
像素点Overlay窗口
用于在绘画区域上显示像素点分布的可视化界面
"""

import logging
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider, QCheckBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QFont


class PixelOverlay(QWidget):
    """像素点Overlay窗口"""
    
    def __init__(self, pixel_info_list, draw_area_pos):
        super().__init__()
        
        self.pixel_info_list = pixel_info_list
        self.draw_area_pos = draw_area_pos
        
        # 窗口设置
        self.setWindowTitle("像素点分布Overlay")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        
        # 设置窗口位置和大小
        area_x, area_y, area_width, area_height = draw_area_pos
        self.setGeometry(area_x, area_y, area_width, area_height)
        
        # 设置窗口透明度
        self.setWindowOpacity(0.8)
        
        # 初始化UI
        self.init_ui()
        
        # 绘制定时器
        self.draw_timer = QTimer()
        self.draw_timer.timeout.connect(self.update)
        self.draw_timer.start(100)  # 每100ms更新一次
        
        logging.info(f"像素点Overlay初始化完成，位置: {draw_area_pos}")
    
    def init_ui(self):
        """初始化UI"""
        # 创建控制面板
        control_panel = QWidget(self)
        control_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(0, 0, 0, 0.7);
                color: white;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QSlider {
                background-color: transparent;
            }
        """)
        
        # 控制面板布局
        control_layout = QVBoxLayout(control_panel)
        
        # 标题
        title_label = QLabel(f"像素点分布 (共{len(self.pixel_info_list)}个像素点)")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        control_layout.addWidget(title_label)
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.close)
        
        self.export_btn = QPushButton("导出坐标")
        self.export_btn.clicked.connect(self.export_coordinates)
        
        button_layout.addWidget(self.close_btn)
        button_layout.addWidget(self.export_btn)
        control_layout.addLayout(button_layout)
        
        # 显示选项
        self.show_grid_checkbox = QCheckBox("显示网格")
        self.show_grid_checkbox.setChecked(True)
        self.show_grid_checkbox.toggled.connect(self.update)
        
        self.show_coordinates_checkbox = QCheckBox("显示坐标")
        self.show_coordinates_checkbox.setChecked(False)
        self.show_coordinates_checkbox.toggled.connect(self.update)
        
        self.show_colors_checkbox = QCheckBox("显示颜色")
        self.show_colors_checkbox.setChecked(True)
        self.show_colors_checkbox.toggled.connect(self.update)
        
        control_layout.addWidget(self.show_grid_checkbox)
        control_layout.addWidget(self.show_coordinates_checkbox)
        control_layout.addWidget(self.show_colors_checkbox)
        
        # 点大小控制
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("点大小:"))
        
        self.point_size_slider = QSlider(Qt.Horizontal)
        self.point_size_slider.setMinimum(1)
        self.point_size_slider.setMaximum(10)
        self.point_size_slider.setValue(3)
        self.point_size_slider.valueChanged.connect(self.update)
        
        self.point_size_label = QLabel("3")
        self.point_size_slider.valueChanged.connect(
            lambda value: self.point_size_label.setText(str(value))
        )
        
        size_layout.addWidget(self.point_size_slider)
        size_layout.addWidget(self.point_size_label)
        control_layout.addLayout(size_layout)
        
        # 设置控制面板位置
        control_panel.setFixedSize(200, 200)
        control_panel.move(10, 10)
    
    def paintEvent(self, event):
        """绘制事件"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 获取窗口尺寸
        width = self.width()
        height = self.height()
        
        # 绘制背景
        painter.fillRect(0, 0, width, height, QColor(0, 0, 0, 50))
        
        # 绘制绘画区域边框
        painter.setPen(QPen(QColor(255, 255, 255, 200), 2))
        painter.drawRect(0, 0, width - 1, height - 1)
        
        # 绘制像素点
        self.draw_pixels(painter, width, height)
        
        # 绘制网格
        if self.show_grid_checkbox.isChecked():
            self.draw_grid(painter, width, height)
    
    def draw_pixels(self, painter, width, height):
        """绘制像素点"""
        if not self.pixel_info_list:
            return
        
        point_size = self.point_size_slider.value()
        show_colors = self.show_colors_checkbox.isChecked()
        show_coordinates = self.show_coordinates_checkbox.isChecked()
        
        # 计算坐标转换
        area_x, area_y, area_width, area_height = self.draw_area_pos
        
        for pixel_info in self.pixel_info_list:
            position = pixel_info['position']
            color = pixel_info['color']
            grid_pos = pixel_info.get('grid_pos', (0, 0))
            
            # 转换坐标到窗口坐标系
            x = position[0] - area_x
            y = position[1] - area_y
            
            # 确保在窗口范围内
            if 0 <= x < width and 0 <= y < height:
                # 设置画笔
                if show_colors:
                    # 使用像素的实际颜色
                    pen_color = QColor(*color)
                    brush_color = QColor(*color)
                else:
                    # 使用默认颜色
                    pen_color = QColor(255, 255, 255, 200)
                    brush_color = QColor(255, 255, 255, 150)
                
                painter.setPen(QPen(pen_color, 1))
                painter.setBrush(QBrush(brush_color))
                
                # 绘制像素点
                painter.drawEllipse(int(x - point_size/2), int(y - point_size/2), point_size, point_size)
                
                # 显示坐标
                if show_coordinates and point_size >= 5:
                    painter.setPen(QPen(QColor(255, 255, 255, 255), 1))
                    painter.setFont(QFont("Arial", 8))
                    coord_text = f"({grid_pos[0]},{grid_pos[1]})"
                    painter.drawText(int(x + point_size/2 + 2), int(y + point_size/2), coord_text)
    
    def draw_grid(self, painter, width, height):
        """绘制网格"""
        if not self.pixel_info_list:
            return
        
        # 计算网格尺寸
        grid_positions = [info.get('grid_pos', (0, 0)) for info in self.pixel_info_list]
        if not grid_positions:
            return
        
        max_x = max(pos[0] for pos in grid_positions)
        max_y = max(pos[1] for pos in grid_positions)
        
        if max_x == 0 or max_y == 0:
            return
        
        # 计算网格间距
        grid_width = width / (max_x + 1)
        grid_height = height / (max_y + 1)
        
        # 设置网格线样式
        painter.setPen(QPen(QColor(255, 255, 255, 50), 1, Qt.DashLine))
        
        # 绘制垂直线
        for i in range(max_x + 2):
            x = i * grid_width
            painter.drawLine(int(x), 0, int(x), height)
        
        # 绘制水平线
        for i in range(max_y + 2):
            y = i * grid_height
            painter.drawLine(0, int(y), width, int(y))
    
    def export_coordinates(self):
        """导出像素坐标"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "导出像素坐标",
                "pixel_coordinates.txt",
                "文本文件 (*.txt);;所有文件 (*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(f"像素坐标导出 (共{len(self.pixel_info_list)}个像素点)\n")
                    f.write("=" * 50 + "\n\n")
                    
                    for i, pixel_info in enumerate(self.pixel_info_list):
                        position = pixel_info['position']
                        color = pixel_info['color']
                        grid_pos = pixel_info.get('grid_pos', (0, 0))
                        
                        f.write(f"像素{i+1}: 坐标({position[0]},{position[1]}) 颜色RGB{color} 网格({grid_pos[0]},{grid_pos[1]})\n")
                
                logging.info(f"像素坐标已导出到: {file_path}")
                
        except Exception as e:
            logging.error(f"导出坐标失败: {e}")
    
    def closeEvent(self, event):
        """关闭事件"""
        if hasattr(self, 'draw_timer'):
            self.draw_timer.stop()
        event.accept()
