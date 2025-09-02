# save as screen_cropper.py
from PyQt5 import QtWidgets, QtGui, QtCore
from PIL import ImageGrab
import logging

class Cropper(QtWidgets.QWidget):
    finished = QtCore.pyqtSignal(object, object)  # 修改信号，传递图片和坐标

    def __init__(self, return_position=False):
        super().__init__()
        self.setWindowTitle('选择区域')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setWindowOpacity(0.3)
        self.setStyleSheet("background-color: black;")
        self.screen = QtWidgets.QApplication.primaryScreen()
        self.setGeometry(self.screen.geometry())
        self.begin = QtCore.QPoint()
        self.end = QtCore.QPoint()
        self.return_position = return_position  # 是否返回坐标信息

    def mousePressEvent(self, event):
        self.begin = event.pos()
        self.end = event.pos()
        self.update()

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()

    def mouseReleaseEvent(self, event):
        x1 = min(self.begin.x(), self.end.x())
        y1 = min(self.begin.y(), self.end.y())
        x2 = max(self.begin.x(), self.end.x())
        y2 = max(self.begin.y(), self.end.y())
        
        self.hide()
        # 延迟一下确保窗口完全隐藏
        QtCore.QTimer.singleShot(100, lambda: self._do_capture(x1, y1, x2, y2))
        
    def _do_capture(self, x1, y1, x2, y2):
        if x2 > x1 and y2 > y1:
            try:
                img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                if img and img.size[0] > 0 and img.size[1] > 0:
                    if self.return_position:
                        # 返回完整的坐标信息：(x, y, width, height)
                        width = x2 - x1
                        height = y2 - y1
                        self.finished.emit(img, (x1, y1, width, height))
                    else:
                        self.finished.emit(img, None)  # 只返回图片，坐标为None
                else:
                    self.finished.emit(None, None)
            except Exception:
                self.finished.emit(None, None)
        else:
            self.finished.emit(None, None)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.finished.emit(None, None)
            self.close()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        # 使用更细更透明的绿色边框
        qp.setPen(QtGui.QPen(QtGui.QColor(76, 175, 80, 200), 1))  # 绿色，1像素宽度，半透明
        qp.drawRect(QtCore.QRect(self.begin, self.end))


class InteractiveCropper(QtWidgets.QWidget):
    finished = QtCore.pyqtSignal(object, object)

    def __init__(self, initial_size=None):
        super().__init__()
        self.setWindowTitle('交互式截图工具')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setWindowOpacity(0.3)
        self.setStyleSheet("background-color: black;")
        self.screen = QtWidgets.QApplication.primaryScreen()
        self.setGeometry(self.screen.geometry())
        
        if initial_size:
            self.box_width, self.box_height = initial_size
        else:
            self.box_width, self.box_height = 80, 80
            
        self.box_x, self.box_y = 0, 0
        self.is_resizing = False
        self.setMouseTracking(True)
        self.show_instructions()
        self.auto_detect_enabled = True

    def show_instructions(self):
        self.instruction_window = QtWidgets.QWidget()
        self.instruction_window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("• 鼠标移动：移动截图框\n"
                                "• 左键点击：截图当前区域\n"
                                "• 右键拖拽：调整框大小\n"
                                "• ESC键：取消截图")
        layout.addWidget(label)
        self.instruction_window.setLayout(layout)
        self.instruction_window.show()
        QtCore.QTimer.singleShot(3000, self.instruction_window.close)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.capture_current_area()
        elif event.button() == QtCore.Qt.RightButton:
            self.is_resizing = True

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.is_resizing = False

    def mouseMoveEvent(self, event):
        if not self.is_resizing:
            self.box_x = event.x() - self.box_width // 2
            self.box_y = event.y() - self.box_height // 2
        else:
            new_width = self.box_x + self.box_width - event.x()
            new_height = self.box_y + self.box_height - event.y()
            if new_width > 20 and new_height > 20:
                 self.box_width, self.box_height = new_width, new_height
                 self.box_x, self.box_y = event.x(), event.y()
        self.update()

    def capture_current_area(self):
        self.hide()
        QtCore.QTimer.singleShot(100, self._do_capture)
    
    def _do_capture(self):
        x1 = max(0, self.box_x)
        y1 = max(0, self.box_y)
        x2 = min(self.screen.geometry().width(), self.box_x + self.box_width)
        y2 = min(self.screen.geometry().height(), self.box_y + self.box_height)
        
        if x2 > x1 and y2 > y1:
            try:
                img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                if img and img.size[0] > 0 and img.size[1] > 0:
                    # 返回完整的坐标信息：(x, y, width, height)
                    width = x2 - x1
                    height = y2 - y1
                    self.finished.emit(img, (x1, y1, width, height))
                else:
                    self.finished.emit(None, None)
            except Exception:
                self.finished.emit(None, None)
        else:
            self.finished.emit(None, None)
        self.close()

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key_Escape:
            self.finished.emit(None, None)
            self.close()

    def paintEvent(self, event):
        qp = QtGui.QPainter(self)
        qp.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))
        # 使用更细更透明的绿色边框
        qp.setPen(QtGui.QPen(QtGui.QColor(76, 175, 80, 200), 1))  # 绿色，1像素宽度，半透明
        qp.drawRect(self.box_x, self.box_y, self.box_width, self.box_height)
        qp.setPen(QtGui.QPen(QtGui.QColor('white'), 1))
        qp.drawText(self.box_x + 5, self.box_y + 20, f"{self.box_width}×{self.box_height}")


class PointSelector(QtWidgets.QWidget):
    """点选式区域选择器 - 通过点击两个点来精确选择绘图区域"""
    finished = QtCore.pyqtSignal(object, object)  # 传递图片和坐标信息

    def __init__(self, return_position=True):
        super().__init__()
        self.setWindowTitle('点选绘图区域')
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setWindowOpacity(0.3)
        self.setStyleSheet("background-color: black;")
        self.screen = QtWidgets.QApplication.primaryScreen()
        self.setGeometry(self.screen.geometry())
        
        # 点选状态
        self.first_point = None  # 第一个点（左上角）
        self.second_point = None  # 第二个点（右下角）
        self.selection_step = 1  # 1: 选择第一个点, 2: 选择第二个点
        
        # 设置鼠标追踪
        self.setMouseTracking(True)
        
        # 显示操作说明
        self.show_instructions()
        
        logging.info("点选式区域选择器已启动")

    def show_instructions(self):
        """显示操作说明窗口"""
        self.instruction_window = QtWidgets.QWidget()
        self.instruction_window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.Tool)
        self.instruction_window.setStyleSheet("""
            QWidget {
                background-color: #2b2b2b;
                color: white;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                padding: 10px;
            }
            QLabel {
                font-size: 12px;
                font-weight: bold;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout()
        
        # 根据当前步骤显示不同的说明
        if self.selection_step == 1:
            instruction_text = "🎯 第一步：点击左上角可绘画的点\n\n" \
                             "• 请点击绘图区域的左上角位置\n" \
                             "• 点击后会自动进入第二步\n" \
                             "• ESC键：取消选择"
        else:
            instruction_text = "🎯 第二步：点击右下角可绘画的点\n\n" \
                             "• 请点击绘图区域的右下角位置\n" \
                             "• 点击后会自动计算并截图\n" \
                             "• ESC键：取消选择"
        
        label = QtWidgets.QLabel(instruction_text)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        self.instruction_window.setLayout(layout)
        self.instruction_window.show()
        
        # 3秒后自动关闭说明窗口
        QtCore.QTimer.singleShot(3000, self.instruction_window.close)

    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == QtCore.Qt.LeftButton:
            if self.selection_step == 1:
                # 第一步：选择左上角点
                self.first_point = QtCore.QPoint(event.pos())
                self.selection_step = 2
                logging.info(f"第一个点已选择: ({self.first_point.x()}, {self.first_point.y()})")
                
                # 更新说明
                self.show_instructions()
                
            elif self.selection_step == 2:
                # 第二步：选择右下角点
                self.second_point = QtCore.QPoint(event.pos())
                logging.info(f"第二个点已选择: ({self.second_point.x()}, {self.second_point.y()})")
                
                # 计算区域并截图
                self._calculate_and_capture()
        
        self.update()

    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 实时显示选择框"""
        if self.first_point:
            # 如果已选择第一个点，实时显示选择框
            self.second_point = QtCore.QPoint(event.pos())
            self.update()

    def _calculate_and_capture(self):
        """计算选择区域并截图"""
        if not self.first_point or not self.second_point:
            return
        
        # 计算左上角和右下角坐标
        x1 = min(self.first_point.x(), self.second_point.x())
        y1 = min(self.first_point.y(), self.second_point.y())
        x2 = max(self.first_point.x(), self.second_point.x())
        y2 = max(self.first_point.y(), self.second_point.y())
        
        # 计算宽度和高度
        width = x2 - x1
        height = y2 - y1
        
        # 检查区域是否有效
        if width < 10 or height < 10:
            logging.warning("选择区域太小，请重新选择")
            # 重置选择
            self.first_point = None
            self.second_point = None
            self.selection_step = 1
            self.show_instructions()
            self.update()
            return
        
        logging.info(f"选择区域: 左上角({x1}, {y1}), 右下角({x2}, {y2}), 尺寸{width}×{height}")
        
        # 隐藏窗口并截图
        self.hide()
        QtCore.QTimer.singleShot(100, lambda: self._do_capture(x1, y1, x2, y2))

    def _do_capture(self, x1, y1, x2, y2):
        """执行截图"""
        try:
            # 确保坐标在屏幕范围内
            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(self.screen.geometry().width(), x2)
            y2 = min(self.screen.geometry().height(), y2)
            
            if x2 > x1 and y2 > y1:
                # 截图
                img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
                if img and img.size[0] > 0 and img.size[1] > 0:
                    # 返回完整的坐标信息：(x, y, width, height)
                    width = x2 - x1
                    height = y2 - y1
                    position = (x1, y1, width, height)
                    
                    logging.info(f"截图成功: {width}×{height} 像素")
                    self.finished.emit(img, position)
                else:
                    logging.error("截图失败：图片无效")
                    self.finished.emit(None, None)
            else:
                logging.error("截图失败：区域坐标无效")
                self.finished.emit(None, None)
                
        except Exception as e:
            logging.error(f"截图过程中发生错误: {e}")
            self.finished.emit(None, None)
        finally:
            self.close()

    def keyPressEvent(self, event):
        """键盘事件"""
        if event.key() == QtCore.Qt.Key_Escape:
            logging.info("用户取消区域选择")
            self.finished.emit(None, None)
            self.close()

    def paintEvent(self, event):
        """绘制事件"""
        qp = QtGui.QPainter(self)
        
        # 绘制半透明背景
        qp.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 100))
        
        # 如果已选择第一个点，绘制选择框
        if self.first_point and self.second_point:
            # 计算选择框
            x1 = min(self.first_point.x(), self.second_point.x())
            y1 = min(self.first_point.y(), self.second_point.y())
            x2 = max(self.first_point.x(), self.second_point.x())
            y2 = max(self.first_point.y(), self.second_point.y())
            
            # 绘制选择框 - 更细更透明的绿色边框
            qp.setPen(QtGui.QPen(QtGui.QColor(76, 175, 80, 200), 1))  # 绿色，1像素宽度，半透明
            qp.drawRect(x1, y1, x2 - x1, y2 - y1)
            
            # 绘制选择框内的半透明填充
            qp.fillRect(x1, y1, x2 - x1, y2 - y1, QtGui.QColor(76, 175, 80, 30))  # 更透明
            
            # 绘制尺寸信息
            width = x2 - x1
            height = y2 - y1
            size_text = f"{width} × {height}"
            
            # 在右上角显示尺寸
            font = QtGui.QFont()
            font.setPointSize(10)
            font.setBold(True)
            qp.setFont(font)
            qp.setPen(QtGui.QPen(QtGui.QColor('white'), 1))
            
            # 计算文本位置（右上角）
            text_rect = qp.fontMetrics().boundingRect(size_text)
            text_x = x2 - text_rect.width() - 10
            text_y = y1 + text_rect.height() + 10
            
            # 绘制文本背景
            qp.fillRect(text_x - 5, text_y - text_rect.height() - 5, 
                       text_rect.width() + 10, text_rect.height() + 10, 
                       QtGui.QColor(0, 0, 0, 150))
            
            # 绘制文本
            qp.drawText(text_x, text_y, size_text)
        
        # 绘制已选择的点
        if self.first_point:
            # 绘制第一个点（左上角）
            qp.setPen(QtGui.QPen(QtGui.QColor('#FF5722'), 2))  # 橙色
            qp.setBrush(QtGui.QBrush(QtGui.QColor('#FF5722')))
            qp.drawEllipse(self.first_point, 6, 6)
            
            # 绘制标签
            qp.setPen(QtGui.QPen(QtGui.QColor('white'), 1))
            qp.setFont(QtGui.QFont('Arial', 8, QtGui.QFont.Bold))
            qp.drawText(self.first_point.x() + 10, self.first_point.y() - 10, "左上角")
        
        if self.second_point and self.selection_step == 2:
            # 绘制第二个点（右下角）
            qp.setPen(QtGui.QPen(QtGui.QColor('#2196F3'), 2))  # 蓝色
            qp.setBrush(QtGui.QBrush(QtGui.QColor('#2196F3')))
            qp.drawEllipse(self.second_point, 6, 6)
            
            # 绘制标签
            qp.setPen(QtGui.QPen(QtGui.QColor('white'), 1))
            qp.setFont(QtGui.QFont('Arial', 8, QtGui.QFont.Bold))
            qp.drawText(self.second_point.x() + 10, self.second_point.y() + 20, "右下角")


def crop_screen_region(callback, return_position=False):
    cropper = Cropper(return_position=return_position)
    cropper.finished.connect(callback)
    cropper.show()
    return cropper

def crop_interactive_region(callback, initial_size=None):
    cropper = InteractiveCropper(initial_size)
    cropper.finished.connect(callback)
    cropper.show()
    return cropper

def crop_point_region(callback, return_position=True):
    """启动点选式区域选择器"""
    selector = PointSelector(return_position=return_position)
    selector.finished.connect(callback)
    selector.show()
    return selector
