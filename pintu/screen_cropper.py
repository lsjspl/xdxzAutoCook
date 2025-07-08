# save as screen_cropper.py
from PyQt5 import QtWidgets, QtGui, QtCore
import sys
from PIL import ImageGrab
import cv2
import numpy as np

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
                        self.finished.emit(img, (x1, y1))  # 返回图片和坐标
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
        qp.setPen(QtGui.QPen(QtGui.QColor('red'), 2))
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
                    self.finished.emit(img, (x1, y1))
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
        qp.setPen(QtGui.QPen(QtGui.QColor('red'), 2))
        qp.drawRect(self.box_x, self.box_y, self.box_width, self.box_height)
        qp.setPen(QtGui.QPen(QtGui.QColor('white'), 1))
        qp.drawText(self.box_x + 5, self.box_y + 20, f"{self.box_width}×{self.box_height}")


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
