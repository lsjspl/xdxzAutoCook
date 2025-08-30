# -*- coding: utf-8 -*-
"""
绘图助手 - 业务逻辑模块
负责绘图的核心业务逻辑
"""

import logging
import time
import threading
from PIL import ImageGrab
from PyQt5.QtCore import QObject, pyqtSignal
from image_processor import ImageProcessor


class PaintBusiness(QObject):
    """绘图助手业务逻辑类"""
    
    # 信号定义
    status_updated = pyqtSignal(str)
    image_processed = pyqtSignal(object)  # 图片处理完成
    color_palette_extracted = pyqtSignal(list)  # 颜色调色板提取完成
    drawing_progress = pyqtSignal(int, int)  # 绘图进度 (当前, 总数)
    drawing_completed = pyqtSignal()  # 绘图完成
    
    def __init__(self):
        super().__init__()
        
        # 图片处理器
        self.image_processor = ImageProcessor()
        
        # 添加线程锁来保护状态变量
        self._state_lock = threading.Lock()
        
        # 绘图区域和颜色区域
        self.draw_area_pos = None  # (x, y, width, height)
        self.color_area_pos = None  # (x, y, width, height)
        
        # 图片和处理结果
        self.selected_image_path = None
        self.pixelized_image = None
        self.color_palette = []
        self.pixel_info_list = []
        
        # 绘图状态
        self.is_drawing = False
        self.drawing_thread = None
        
        # 延迟配置
        self.color_click_delay = 0.5  # 颜色点击延迟
        self.draw_click_delay = 0.05  # 绘图点击延迟
        self.mouse_move_delay = 0.01  # 鼠标移动延迟
        
        logging.info("绘图业务逻辑初始化完成")
    
    def set_draw_area(self, position):
        """设置绘画区域"""
        with self._state_lock:
            self.draw_area_pos = position
            if position:
                logging.info(f"绘画区域已设置: {position}")
                self.status_updated.emit(f"绘画区域已设置: {position[2]}×{position[3]} 像素")
            else:
                logging.info("绘画区域已清除")
                self.status_updated.emit("绘画区域已清除")
    
    def set_color_area(self, position):
        """设置颜色区域"""
        with self._state_lock:
            self.color_area_pos = position
            if position:
                logging.info(f"颜色区域已设置: {position}")
                self.status_updated.emit(f"颜色区域已设置: {position[2]}×{position[3]} 像素")
                # 立即分析颜色区域
                self._analyze_color_area()
            else:
                logging.info("颜色区域已清除")
                self.status_updated.emit("颜色区域已清除")
                self.color_palette = []
    
    def _analyze_color_area(self):
        """分析颜色区域，提取颜色调色板"""
        try:
            if not self.color_area_pos:
                return
            
            # 截取当前屏幕
            screenshot = ImageGrab.grab()
            
            # 分析颜色区域
            colors = self.image_processor.analyze_color_region(screenshot, self.color_area_pos)
            
            if colors:
                self.color_palette = colors
                self.color_palette_extracted.emit(colors)
                logging.info(f"颜色调色板提取完成，共{len(colors)}种颜色")
                self.status_updated.emit(f"颜色调色板提取完成，共{len(colors)}种颜色")
            else:
                logging.error("颜色调色板提取失败")
                self.status_updated.emit("颜色调色板提取失败")
                
        except Exception as e:
            logging.error(f"分析颜色区域失败: {e}")
            self.status_updated.emit(f"分析颜色区域失败: {str(e)}")
    
    def set_selected_image(self, image_path):
        """设置选择的图片"""
        with self._state_lock:
            self.selected_image_path = image_path
            if image_path:
                logging.info(f"图片已选择: {image_path}")
                self.status_updated.emit(f"图片已选择: {image_path}")
            else:
                logging.info("图片选择已清除")
                self.status_updated.emit("图片选择已清除")
                self.pixelized_image = None
                self.pixel_info_list = []
    
    def process_image(self, aspect_ratio, pixel_count):
        """处理图片，进行像素化"""
        try:
            if not self.selected_image_path:
                self.status_updated.emit("请先选择图片")
                return False
            
            if not self.color_palette:
                self.status_updated.emit("请先设置颜色区域以获取颜色调色板")
                return False
            
            self.status_updated.emit("正在处理图片...")
            
            # 转换宽高比字符串为元组
            if isinstance(aspect_ratio, str):
                try:
                    width_str, height_str = aspect_ratio.split(':')
                    aspect_ratio_tuple = (int(width_str), int(height_str))
                except ValueError:
                    self.status_updated.emit(f"无效的宽高比格式: {aspect_ratio}")
                    return False
            else:
                aspect_ratio_tuple = aspect_ratio
            
            # 像素化图片
            self.pixelized_image = self.image_processor.pixelize_image(
                self.selected_image_path, 
                aspect_ratio_tuple, 
                pixel_count, 
                self.color_palette
            )
            
            if self.pixelized_image:
                # 发送处理完成信号
                self.image_processed.emit(self.pixelized_image)
                
                # 如果绘画区域已设置，计算像素位置信息
                if self.draw_area_pos:
                    self._calculate_pixel_positions()
                
                logging.info("图片处理完成")
                self.status_updated.emit("图片处理完成")
                return True
            else:
                logging.error("图片处理失败")
                self.status_updated.emit("图片处理失败")
                return False
                
        except Exception as e:
            logging.error(f"处理图片失败: {e}")
            self.status_updated.emit(f"处理图片失败: {str(e)}")
            return False
    
    def _calculate_pixel_positions(self):
        """计算像素位置信息"""
        try:
            if not self.pixelized_image or not self.draw_area_pos:
                return
            
            # 计算像素块尺寸
            draw_area_size = (self.draw_area_pos[2], self.draw_area_pos[3])
            pixel_image_size = self.pixelized_image.size
            pixel_size = self.image_processor.calculate_pixel_size(draw_area_size, pixel_image_size)
            
            # 获取像素位置信息
            self.pixel_info_list = self.image_processor.get_pixel_positions(
                self.draw_area_pos, 
                self.pixelized_image, 
                pixel_size
            )
            
            logging.info(f"像素位置计算完成，共{len(self.pixel_info_list)}个像素点")
            self.status_updated.emit(f"像素位置计算完成，共{len(self.pixel_info_list)}个像素点")
            
        except Exception as e:
            logging.error(f"计算像素位置失败: {e}")
            self.status_updated.emit(f"计算像素位置失败: {str(e)}")
    
    def start_drawing(self, delay_settings=None):
        """开始绘图"""
        try:
            # 更新延迟配置
            if delay_settings:
                self.color_click_delay = delay_settings.get('color_delay', 0.5)
                self.draw_click_delay = delay_settings.get('draw_delay', 0.05)
                self.mouse_move_delay = delay_settings.get('move_delay', 0.01)
                logging.info(f"延迟配置已更新: 颜色={self.color_click_delay}s, 绘图={self.draw_click_delay}s, 移动={self.mouse_move_delay}s")
            
            # 检查必要条件
            if not self.draw_area_pos:
                self.status_updated.emit("请先设置绘画区域")
                return False
            
            if not self.color_area_pos:
                self.status_updated.emit("请先设置颜色区域")
                return False
            
            if not self.pixelized_image:
                self.status_updated.emit("请先处理图片")
                return False
            
            if not self.pixel_info_list:
                self.status_updated.emit("像素位置信息未准备好")
                return False
            
            if self.is_drawing:
                self.status_updated.emit("绘图已在进行中")
                return False
            
            # 重新分析颜色区域以获取最新的颜色调色板
            self._analyze_color_area()
            
            if not self.color_palette:
                self.status_updated.emit("颜色调色板未准备好")
                return False
            
            # 启动绘图线程
            self.is_drawing = True
            self.drawing_thread = threading.Thread(target=self._drawing_worker)
            self.drawing_thread.daemon = True
            self.drawing_thread.start()
            
            logging.info("绘图已开始")
            self.status_updated.emit("绘图已开始")
            return True
            
        except Exception as e:
            logging.error(f"启动绘图失败: {e}")
            self.status_updated.emit(f"启动绘图失败: {str(e)}")
            return False
    
    def stop_drawing(self):
        """停止绘图"""
        with self._state_lock:
            if self.is_drawing:
                self.is_drawing = False
                logging.info("绘图已停止")
                self.status_updated.emit("绘图已停止")
                return True
            else:
                self.status_updated.emit("绘图未在进行中")
                return False
    
    def _drawing_worker(self):
        """绘图工作线程"""
        try:
            total_pixels = len(self.pixel_info_list)
            
            for i, pixel_info in enumerate(self.pixel_info_list):
                # 检查是否需要停止
                with self._state_lock:
                    if not self.is_drawing:
                        break
                
                # 获取像素信息
                position = pixel_info['position']
                target_color = pixel_info['color']
                
                # 找到最接近的颜色在调色板中的索引
                color_index = self.image_processor.find_closest_color_index(target_color, self.color_palette)
                
                # 计算颜色在颜色区域中的位置
                color_position = self._get_color_position(color_index)
                
                if color_position:
                    # 先点击颜色
                    self._click_position(color_position)
                    time.sleep(self.color_click_delay)  # 颜色点击延迟
                    
                    # 再点击绘图位置
                    self._click_position(position)
                    time.sleep(self.draw_click_delay)  # 绘图点击延迟
                    
                    # 更新进度
                    self.drawing_progress.emit(i + 1, total_pixels)
                    
                    # 每10个像素输出一次进度
                    if (i + 1) % 10 == 0:
                        progress_percent = (i + 1) / total_pixels * 100
                        logging.info(f"绘图进度: {i + 1}/{total_pixels} ({progress_percent:.1f}%)")
                        self.status_updated.emit(f"绘图进度: {i + 1}/{total_pixels} ({progress_percent:.1f}%)")
                
                else:
                    logging.warning(f"无法获取颜色{color_index}的位置")
            
            # 绘图完成
            with self._state_lock:
                self.is_drawing = False
            
            self.drawing_completed.emit()
            logging.info("绘图完成")
            self.status_updated.emit("绘图完成")
            
        except Exception as e:
            with self._state_lock:
                self.is_drawing = False
            logging.error(f"绘图过程中发生错误: {e}")
            self.status_updated.emit(f"绘图过程中发生错误: {str(e)}")
    
    def _get_color_position(self, color_index):
        """获取颜色在颜色区域中的位置"""
        try:
            if not self.color_area_pos or color_index >= 16:
                return None
            
            x, y, width, height = self.color_area_pos
            
            # 计算颜色块尺寸
            block_width = width // 2  # 2列
            block_height = height // 8  # 8行
            
            # 计算行列位置
            row = color_index // 2
            col = color_index % 2
            
            # 计算中心点位置
            center_x = x + col * block_width + block_width // 2
            center_y = y + row * block_height + block_height // 2
            
            return (center_x, center_y)
            
        except Exception as e:
            logging.error(f"获取颜色位置失败: {e}")
            return None
    
    def _click_position(self, position):
        """点击指定位置"""
        try:
            import pyautogui
            pyautogui.click(position[0], position[1])
        except ImportError:
            # 如果没有pyautogui，使用Windows API
            self._click_position_winapi(position)
        except Exception as e:
            logging.error(f"点击位置{position}失败: {e}")
    
    def _click_position_winapi(self, position):
        """使用Windows SendInput API点击位置"""
        try:
            import ctypes
            from ctypes import wintypes, Structure, c_long, c_ulong, byref
            
            # 定义Windows API结构体
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

            # 常量定义
            INPUT_MOUSE = 0
            MOUSEEVENTF_MOVE = 0x0001
            MOUSEEVENTF_LEFTDOWN = 0x0002
            MOUSEEVENTF_LEFTUP = 0x0004
            MOUSEEVENTF_ABSOLUTE = 0x8000
            
            x, y = position[0], position[1]
            
            # 获取屏幕尺寸用于坐标转换
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            
            # 转换为绝对坐标 (0-65535)
            abs_x = int(x * 65535 / screen_width)
            abs_y = int(y * 65535 / screen_height)
            
            logging.debug(f"点击坐标: 屏幕({x}, {y}) -> 绝对({abs_x}, {abs_y})")
            
            # 移动鼠标到目标位置
            self._send_mouse_input(abs_x, abs_y, MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE)
            time.sleep(0.01)
            
            # 执行点击
            self._send_mouse_input(abs_x, abs_y, MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE)
            time.sleep(0.01)
            self._send_mouse_input(abs_x, abs_y, MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE)
            
            logging.debug(f"点击完成: ({x}, {y})")
            
        except Exception as e:
            logging.error(f"Windows SendInput API点击失败: {e}")
    
    def _send_mouse_input(self, x, y, flags):
        """使用 SendInput API 发送鼠标事件"""
        try:
            import ctypes
            from ctypes import wintypes, Structure, c_long, c_ulong, byref
            
            # 定义结构体（如果还没定义）
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
            
            INPUT_MOUSE = 0
            
            # 创建 INPUT 结构体
            extra = ctypes.c_ulong(0)
            ii_ = INPUT()
            ii_.type = INPUT_MOUSE
            ii_.mi.dx = x
            ii_.mi.dy = y
            ii_.mi.mouseData = 0
            ii_.mi.dwFlags = flags
            ii_.mi.time = 0
            ii_.mi.dwExtraInfo = ctypes.pointer(extra)

            # 发送输入事件
            result = ctypes.windll.user32.SendInput(1, ctypes.byref(ii_), ctypes.sizeof(ii_))
            
            if result == 0:
                error_code = ctypes.windll.kernel32.GetLastError()
                logging.error(f"SendInput失败，错误代码: {error_code}")
                raise Exception(f"SendInput失败，错误代码: {error_code}")
            else:
                logging.debug(f"鼠标事件发送成功: flags={flags}, 坐标=({x}, {y})")
                
        except Exception as e:
            logging.error(f"发送鼠标输入失败: {e}")
            raise
    
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
    
    def get_pixel_info_list(self):
        """获取像素信息列表"""
        return self.pixel_info_list
    
    def is_ready_to_draw(self):
        """检查是否准备好绘图"""
        return (self.draw_area_pos is not None and 
                self.color_area_pos is not None and 
                self.pixelized_image is not None and
                len(self.color_palette) > 0 and
                len(self.pixel_info_list) > 0)


if __name__ == "__main__":
    # 测试代码
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    business = PaintBusiness()
    
    # 测试基本功能
    business.set_draw_area((100, 100, 400, 400))
    business.set_color_area((500, 100, 200, 400))
    
    print("绘图业务逻辑测试完成")