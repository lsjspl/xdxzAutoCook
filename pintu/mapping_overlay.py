from PyQt5 import QtWidgets, QtGui, QtCore

class MappingOverlay(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()

    def __init__(self, x, y, width, height, block_count):
        super().__init__()
        self.setWindowTitle('拼图映射覆盖层')
        # 恢复无边框窗口，但保持置顶
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        
        # 添加小的标题栏高度
        self.title_bar_height = 25
        self.setGeometry(x, y - self.title_bar_height, width, height + self.title_bar_height)
        
        self.block_count = block_count
        self.matches = []
        
        # 用于拖动的变量
        self.dragging = False
        self.drag_start_position = QtCore.QPoint()
        
        grid_map = {16: (4, 4), 36: (6, 6), 64: (8, 8), 100: (10, 10)}
        self.grid_rows, self.grid_cols = grid_map.get(block_count, (6, 6))
        
        self.mapping_width = width
        self.mapping_height = height
        self.tile_width = width // self.grid_cols
        self.tile_height = height // self.grid_rows
        
        # 设置鼠标穿透（仅对映射区域）
        self.enable_mouse_passthrough()
        
        self.show()

    def enable_mouse_passthrough(self):
        """启用鼠标穿透功能"""
        try:
            import ctypes
            from ctypes import wintypes
            
            # 获取窗口句柄
            hwnd = int(self.winId())
            
            # Windows API 常量
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x80000
            WS_EX_TRANSPARENT = 0x20
            
            # 获取当前扩展样式
            extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            
            # 添加透明和分层属性
            new_style = extended_style | WS_EX_LAYERED | WS_EX_TRANSPARENT
            
            # 设置新的扩展样式
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
            
            print("已启用鼠标穿透功能")
        except Exception as e:
            print(f"启用鼠标穿透失败: {e}")

    def disable_mouse_passthrough(self):
        """禁用鼠标穿透功能（用于拖动）"""
        try:
            import ctypes
            
            hwnd = int(self.winId())
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x20
            
            # 获取当前扩展样式
            extended_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            
            # 移除透明属性
            new_style = extended_style & ~WS_EX_TRANSPARENT
            
            # 设置新的扩展样式
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except Exception as e:
            print(f"禁用鼠标穿透失败: {e}")

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def update_matches(self, matches):
        """更新匹配结果"""
        self.matches = matches[:3]
        self.update()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # 绘制小的标题栏
        title_rect = QtCore.QRect(0, 0, self.width(), self.title_bar_height)
        qp.fillRect(title_rect, QtGui.QColor(60, 60, 60, 180))
        qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))
        qp.setFont(QtGui.QFont('Arial', 8, QtGui.QFont.Bold))
        qp.drawText(title_rect, QtCore.Qt.AlignCenter, f"拼图映射 ({self.block_count}块) - 拖动此栏移动")
        
        # 映射区域 - 半透明背景
        mapping_rect = QtCore.QRect(0, self.title_bar_height, self.mapping_width, self.mapping_height)
        qp.fillRect(mapping_rect, QtGui.QColor(0, 0, 0, 30))
        
        # 绘制网格线
        qp.setPen(QtGui.QPen(QtGui.QColor(255, 0, 0), 2))
        for i in range(1, self.grid_cols):
            x = i * self.tile_width
            qp.drawLine(x, self.title_bar_height, x, self.height())
        for i in range(1, self.grid_rows):
            y = self.title_bar_height + i * self.tile_height
            qp.drawLine(0, y, self.width(), y)
        
        # 绘制匹配结果
        for i, match in enumerate(self.matches):
            row, col = match['position']
            confidence = match['confidence']
            
            x = col * self.tile_width
            y = self.title_bar_height + row * self.tile_height
            
            # 置信度越高，绿色越亮，越低越接近白色
            base = 220
            r = int(base * (1 - confidence))
            g = 255
            b = int(base * (1 - confidence))
            color = QtGui.QColor(r, g, b)
            pen_width = 4 if i == 0 else 2
            qp.setPen(QtGui.QPen(color, pen_width))
            qp.drawRect(x, y, self.tile_width, self.tile_height)
            # 文字颜色
            text_color = QtGui.QColor(0, 0, 0) if confidence > 0.5 else QtGui.QColor(255, 255, 255)
            qp.setPen(QtGui.QPen(text_color, 1))
            qp.setFont(QtGui.QFont('Arial', 10, QtGui.QFont.Bold))
            text = f"{confidence:.2f}"
            qp.drawText(x, y, self.tile_width, self.tile_height, QtCore.Qt.AlignCenter, text)

    def mousePressEvent(self, event):
        """只在标题栏区域响应拖动"""
        if event.button() == QtCore.Qt.LeftButton and event.y() <= self.title_bar_height:
            self.disable_mouse_passthrough()  # 临时禁用鼠标穿透以进行拖动
            self.dragging = True
            self.drag_start_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
        else:
            # 映射区域不响应鼠标事件，实现穿透
            event.ignore()

    def mouseMoveEvent(self, event):
        """处理拖动"""
        if event.buttons() == QtCore.Qt.LeftButton and self.dragging:
            self.move(event.globalPos() - self.drag_start_position)
            event.accept()
        else:
            event.ignore()

    def mouseReleaseEvent(self, event):
        """结束拖动"""
        if event.button() == QtCore.Qt.LeftButton and self.dragging:
            self.dragging = False
            self.enable_mouse_passthrough()  # 重新启用鼠标穿透
            event.accept()
        else:
            event.ignore()

def create_mapping_overlay(x, y, width, height, block_count):
    """创建映射区域覆盖层的工厂函数"""
    overlay = MappingOverlay(x, y, width, height, block_count)
    return overlay 