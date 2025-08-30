# -*- coding: utf-8 -*-
"""
绘图助手 - 工作线程模块
负责后台绘图任务和鼠标点击操作
"""

import logging
import time
import threading
import ctypes
import random
from ctypes import wintypes, Structure, c_long, c_ulong, byref
from PyQt5.QtCore import QThread, pyqtSignal

try:
    import keyboard
    HOTKEY_ENABLED = True
except ImportError:
    HOTKEY_ENABLED = False
    logging.warning("keyboard 未安装，热键功能将被禁用")

# Windows API 结构体定义
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


class DrawingWorker(QThread):
    """绘图工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int)  # 进度更新 (当前, 总数)
    status_updated = pyqtSignal(str)  # 状态更新
    drawing_completed = pyqtSignal()  # 绘图完成
    drawing_error = pyqtSignal(str)  # 绘图错误
    
    def __init__(self, pixel_info_list, color_palette, color_area_pos):
        super().__init__()
        
        self.pixel_info_list = pixel_info_list
        self.color_palette = color_palette
        self.color_area_pos = color_area_pos
        
        self.is_running = False
        self.should_stop = False
        
        # 点击延迟设置
        self.color_click_delay = 0.5  # 点击颜色后的延迟（保持不变避免反应不过来）
        self.draw_click_delay = 0.01  # 点击绘图位置后的延迟（减少延迟提高速度）
        self.mouse_move_delay = 0.005  # 鼠标移动延迟（减少延迟提高速度）
        

        
        logging.info("绘图工作线程初始化完成")
    
    def run(self):
        """线程主函数"""
        try:
            self.is_running = True
            self.should_stop = False
            
            total_pixels = len(self.pixel_info_list)
            self.status_updated.emit(f"开始绘图，共{total_pixels}个像素点")
            
            # 按颜色分组像素
            color_groups = self._group_pixels_by_color()
            total_colors = len(color_groups)
            
            self.status_updated.emit(f"按颜色分组完成，共{total_colors}种颜色")
            logging.info(f"按颜色分组完成，共{total_colors}种颜色")
            
            processed_pixels = 0
            
            for group_index, (color_idx, (color_position, pixel_positions)) in enumerate(color_groups.items()):
                # 检查是否需要停止
                if self.should_stop:
                    self.status_updated.emit("绘图已被用户停止")
                    break
                
                pixels_in_group = len(pixel_positions)
                self.status_updated.emit(f"开始绘制颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}），共{pixels_in_group}个像素点")
                logging.info(f"开始绘制颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}），共{pixels_in_group}个像素点")
                
                # 点击颜色
                success = self._click_position(color_position)
                if not success:
                    logging.warning(f"点击颜色位置{color_position}失败，跳过该颜色")
                    processed_pixels += pixels_in_group
                    continue
                
                # 在延迟期间检查停止标志
                self._interruptible_sleep(self.color_click_delay)
                if self.should_stop:
                    self.status_updated.emit("绘图已被用户停止")
                    break
                
                # 绘制该颜色的所有像素点
                for i, position in enumerate(pixel_positions):
                    # 检查是否需要停止
                    if self.should_stop:
                        self.status_updated.emit("绘图已被用户停止")
                        break
                    
                    # 点击绘图位置
                    success = self._click_position(position)
                    if not success:
                        logging.warning(f"点击绘图位置{position}失败")
                        continue
                    
                    # 在延迟期间检查停止标志
                    self._interruptible_sleep(self.draw_click_delay)
                    if self.should_stop:
                        self.status_updated.emit("绘图已被用户停止")
                        break
                    
                    processed_pixels += 1
                    
                    # 更新进度
                    self.progress_updated.emit(processed_pixels, total_pixels)
                    
                    # 每50个像素输出一次进度
                    if processed_pixels % 50 == 0:
                        progress_percent = processed_pixels / total_pixels * 100
                        self.status_updated.emit(f"绘图进度: {processed_pixels}/{total_pixels} ({progress_percent:.1f}%)")
                        logging.info(f"绘图进度: {processed_pixels}/{total_pixels} ({progress_percent:.1f}%)")
                
                # 完成当前颜色的绘制
                if not self.should_stop:
                    color_progress_percent = (group_index + 1) / total_colors * 100
                    self.status_updated.emit(f"颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}） 绘制完成 ({color_progress_percent:.1f}%)")
                    logging.info(f"颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}） 绘制完成")
            
            # 绘图完成
            if not self.should_stop:
                self.drawing_completed.emit()
                self.status_updated.emit("绘图完成")
                logging.info("绘图完成")
            
        except Exception as e:
            error_msg = f"绘图过程中发生错误: {str(e)}"
            logging.error(error_msg)
            self.drawing_error.emit(error_msg)
        
        finally:
            self.is_running = False
    
    def stop_drawing(self):
        """停止绘图"""
        self.should_stop = True
        logging.info("绘图停止请求已发送")
    
    def _group_pixels_by_color(self):
        """按颜色分组像素点"""
        color_groups = {}
        
        for pixel_info in self.pixel_info_list:
            position = pixel_info['position']
            target_color = pixel_info['color']
            
            # 找到最接近的颜色在调色板中的索引
            color_index = self._find_closest_color_index(target_color)
            
            # 计算颜色在颜色区域中的位置
            color_position = self._get_color_position(color_index)
            
            if color_position:
                # 使用颜色索引作为分组键
                if color_index not in color_groups:
                    color_groups[color_index] = (color_position, [])
                
                # 将像素位置添加到对应颜色组
                color_groups[color_index][1].append(position)
            else:
                logging.warning(f"无法获取颜色{color_index}的位置，跳过像素{position}")
        
        logging.info(f"颜色分组完成，共{len(color_groups)}种颜色")
        for color_idx, (color_pos, positions) in color_groups.items():
            logging.info(f"颜色{color_idx}: {len(positions)}个像素点")
        
        return color_groups
    
    def _interruptible_sleep(self, duration):
        """可中断的延迟函数"""
        if duration <= 0:
            return
        
        # 将延迟分成小段，每段检查停止标志
        step = 0.01  # 10ms检查一次
        elapsed = 0
        
        while elapsed < duration and not self.should_stop:
            sleep_time = min(step, duration - elapsed)
            time.sleep(sleep_time)
            elapsed += sleep_time
    
    def _find_closest_color_index(self, target_color):
        """找到最接近的颜色索引"""
        try:
            if not self.color_palette:
                return 0
            
            min_distance = float('inf')
            closest_index = 0
            
            for i, palette_color in enumerate(self.color_palette):
                # 计算颜色距离（欧几里得距离）
                distance = sum((a - b) ** 2 for a, b in zip(target_color[:3], palette_color[:3])) ** 0.5
                
                if distance < min_distance:
                    min_distance = distance
                    closest_index = i
            
            return closest_index
            
        except Exception as e:
            logging.error(f"查找最接近颜色失败: {e}")
            return 0
    
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
            # 强制使用Windows API，因为某些游戏可能阻止pyautogui
            return self._click_position_winapi(position)
            
        except Exception as e:
            logging.error(f"点击位置{position}失败: {e}")
            return False
    
    def _click_position_winapi(self, position):
        """使用Windows API点击位置，包含多种点击方法和重试机制"""
        try:
            target_x, target_y = int(position[0]), int(position[1])
            
            # 直接点击目标位置
            final_x = target_x
            final_y = target_y
            
            # 直接移动到目标位置
            self._send_mouse_input(final_x, final_y, MOUSEEVENTF_MOVE)
            logging.debug(f"点击坐标: ({final_x}, {final_y})")
            
            # 精确模式使用最小延迟
            time.sleep(0.005)
            
            # 尝试多种点击方法，提高游戏兼容性
            success = False
            
            # 方法1: SendInput API（主要方法）
            try:
                self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTDOWN)
                press_delay = random.uniform(0.008, 0.015)  # 减少按压时间提高速度
                time.sleep(press_delay)
                self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTUP)
                success = True
                logging.info(f"SendInput点击成功: ({final_x}, {final_y})")
            except Exception as e:
                logging.warning(f"SendInput点击失败: {e}，尝试备用方法")
            
            # 方法2: SetCursorPos + mouse_event API（备用方法）
            if not success:
                try:
                    # 设置鼠标位置
                    ctypes.windll.user32.SetCursorPos(final_x, final_y)
                    time.sleep(0.01)
                    
                    # 使用mouse_event API
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                    time.sleep(random.uniform(0.008, 0.015))  # 减少按压时间
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
                    success = True
                    logging.info(f"mouse_event点击成功: ({final_x}, {final_y})")
                except Exception as e:
                    logging.warning(f"mouse_event点击失败: {e}")
            
            # 方法3: 重复点击（某些游戏需要多次点击才能识别）
            if not success:
                try:
                    for attempt in range(2):
                        self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTDOWN)
                        time.sleep(0.02)
                        self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTUP)
                        time.sleep(0.05)
                    success = True
                    logging.info(f"重复点击成功: ({final_x}, {final_y})")
                except Exception as e:
                    logging.error(f"重复点击失败: {e}")
            
            # 等待点击完成（带随机延迟）
            final_delay = random.uniform(0.005, 0.015)  # 减少最终延迟提高速度
            time.sleep(final_delay)
            
            if success:
                logging.debug(f"点击完成: ({final_x}, {final_y})")
            else:
                logging.error(f"所有点击方法都失败: ({final_x}, {final_y})")
            
            return success
            
        except Exception as e:
            logging.error(f"Windows API点击失败: {e}")
            return False
    
    def _send_mouse_input(self, x, y, flags):
        """使用 SendInput API 发送鼠标事件"""
        try:
            # 获取屏幕尺寸用于坐标转换
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            
            # 转换为绝对坐标 (0-65535)
            if flags & MOUSEEVENTF_MOVE or flags & MOUSEEVENTF_LEFTDOWN or flags & MOUSEEVENTF_LEFTUP:
                abs_x = int(x * 65535 / screen_width)
                abs_y = int(y * 65535 / screen_height)
                flags |= MOUSEEVENTF_ABSOLUTE
                logging.debug(f"鼠标事件: 屏幕坐标({x}, {y}) -> 绝对坐标({abs_x}, {abs_y})")
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
    
    def set_click_delays(self, color_delay=0.5, draw_delay=0.05, move_delay=0.01):
        """设置点击延迟"""
        self.color_click_delay = color_delay
        self.draw_click_delay = draw_delay
        self.mouse_move_delay = move_delay
        logging.info(f"点击延迟已设置: 颜色={color_delay}s, 绘图={draw_delay}s, 移动={move_delay}s")
    



class ClickWorker(QThread):
    """点击工作线程（用于单次点击操作）"""
    
    # 信号定义
    click_completed = pyqtSignal(bool, str)  # 点击完成 (成功, 消息)
    
    def __init__(self, position, click_type="single"):
        super().__init__()
        
        self.position = position
        self.click_type = click_type  # "single", "double"
        
        logging.info(f"点击工作线程初始化: 位置={position}, 类型={click_type}")
    
    def run(self):
        """线程主函数"""
        try:
            success = False
            
            if self.click_type == "single":
                success = self._single_click()
            elif self.click_type == "double":
                success = self._double_click()
            
            if success:
                self.click_completed.emit(True, f"点击位置{self.position}成功")
            else:
                self.click_completed.emit(False, f"点击位置{self.position}失败")
                
        except Exception as e:
            error_msg = f"点击操作失败: {str(e)}"
            logging.error(error_msg)
            self.click_completed.emit(False, error_msg)
    
    def _single_click(self):
        """单击"""
        try:
            # 优先使用pyautogui
            try:
                import pyautogui
                pyautogui.click(self.position[0], self.position[1])
                return True
            except ImportError:
                pass
            
            # 使用Windows API
            return self._click_winapi()
            
        except Exception as e:
            logging.error(f"单击失败: {e}")
            return False
    
    def _double_click(self):
        """双击"""
        try:
            # 优先使用pyautogui
            try:
                import pyautogui
                pyautogui.doubleClick(self.position[0], self.position[1])
                return True
            except ImportError:
                pass
            
            # 使用Windows API执行两次单击
            success1 = self._click_winapi()
            time.sleep(0.05)
            success2 = self._click_winapi()
            
            return success1 and success2
            
        except Exception as e:
            logging.error(f"双击失败: {e}")
            return False
    
    def _click_winapi(self):
        """使用Windows API点击"""
        try:
            target_x, target_y = int(self.position[0]), int(self.position[1])
            
            # 添加随机偏移，避免总是点击正中心
            offset_range = 3  # 偏移范围：±3像素
            random_offset_x = random.randint(-offset_range, offset_range)
            random_offset_y = random.randint(-offset_range, offset_range)
            
            # 计算最终点击位置
            final_x = target_x + random_offset_x
            final_y = target_y + random_offset_y
            
            logging.debug(f"点击坐标: 原始({target_x}, {target_y}), 最终({final_x}, {final_y})")
            
            # 移动到目标位置（带随机偏移）
            self._send_mouse_input(final_x, final_y, MOUSEEVENTF_MOVE)
            time.sleep(0.01)
            
            # 添加点击前的微抖动延迟
            jitter_delay = random.uniform(0.02, 0.08)
            time.sleep(jitter_delay)
            
            # 执行点击（带随机延迟）
            self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTDOWN)
            press_delay = 0.01 + random.uniform(-0.005, 0.005)
            press_delay = max(0.005, press_delay)  # 确保最小延迟
            time.sleep(press_delay)
            
            self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTUP)
            
            # 等待点击完成（带随机延迟）
            final_delay = 0.01 + random.uniform(-0.005, 0.005)
            final_delay = max(0.005, final_delay)  # 确保最小延迟
            time.sleep(final_delay)
            
            logging.debug(f"点击完成: ({final_x}, {final_y})")
            return True
            
        except Exception as e:
            logging.error(f"Windows API点击失败: {e}")
            return False
    
    def _send_mouse_input(self, x, y, flags):
        """使用 SendInput API 发送鼠标事件"""
        try:
            # 获取屏幕尺寸用于坐标转换
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            
            # 转换为绝对坐标 (0-65535)
            if flags & MOUSEEVENTF_MOVE or flags & MOUSEEVENTF_LEFTDOWN or flags & MOUSEEVENTF_LEFTUP:
                abs_x = int(x * 65535 / screen_width)
                abs_y = int(y * 65535 / screen_height)
                flags |= MOUSEEVENTF_ABSOLUTE
                logging.debug(f"鼠标事件: 屏幕坐标({x}, {y}) -> 绝对坐标({abs_x}, {abs_y})")
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


class ScreenCaptureWorker(QThread):
    """屏幕截图工作线程"""
    
    # 信号定义
    capture_completed = pyqtSignal(object)  # 截图完成 (PIL Image)
    capture_error = pyqtSignal(str)  # 截图错误
    
    def __init__(self, region=None):
        super().__init__()
        
        self.region = region  # (x, y, width, height) 或 None 表示全屏
        
        logging.info(f"屏幕截图工作线程初始化: 区域={region}")
    
    def run(self):
        """线程主函数"""
        try:
            from PIL import ImageGrab
            
            if self.region:
                # 截取指定区域
                x, y, width, height = self.region
                bbox = (x, y, x + width, y + height)
                screenshot = ImageGrab.grab(bbox)
            else:
                # 截取全屏
                screenshot = ImageGrab.grab()
            
            self.capture_completed.emit(screenshot)
            logging.info("屏幕截图完成")
            
        except Exception as e:
            error_msg = f"屏幕截图失败: {str(e)}"
            logging.error(error_msg)
            self.capture_error.emit(error_msg)


class HotkeyWorker(QThread):
    """热键监听线程"""
    
    hotkey_pressed = pyqtSignal(str)  # 热键按下信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = True
        self.hotkeys_registered = False
        
    def run(self):
        """线程主函数"""
        if not HOTKEY_ENABLED:
            logging.warning("热键功能未启用")
            return
            
        try:
            # 注册热键
            keyboard.add_hotkey('p', self._on_p_pressed)
            self.hotkeys_registered = True
            logging.info("热键注册成功: P键停止绘图")
            
            # 保持线程运行
            while self.is_running:
                time.sleep(0.1)
                
        except Exception as e:
            logging.error(f"热键监听线程错误: {e}")
        finally:
            self._cleanup_hotkeys()
    
    def _on_p_pressed(self):
        """P键按下处理"""
        self.hotkey_pressed.emit('p')
    
    def stop(self):
        """停止线程"""
        self.is_running = False
        self._cleanup_hotkeys()
        self.quit()
        # 设置超时等待，避免阻塞主线程
        if not self.wait(2000):  # 等待2秒
            logging.warning("HotkeyWorker停止超时，强制终止")
            self.terminate()
            self.wait(1000)  # 再等待1秒
    
    def _cleanup_hotkeys(self):
        """清理热键注册"""
        if HOTKEY_ENABLED and self.hotkeys_registered:
            try:
                keyboard.remove_hotkey('p')
                self.hotkeys_registered = False
                logging.info("热键注册已清理")
            except Exception as e:
                logging.error(f"清理热键注册时发生错误: {e}")


if __name__ == "__main__":
    # 测试代码
    import sys
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # 测试点击功能
    def on_click_completed(success, message):
        print(f"点击完成: {success}, {message}")
        app.quit()
    
    click_worker = ClickWorker((100, 100))
    click_worker.click_completed.connect(on_click_completed)
    click_worker.start()
    
    sys.exit(app.exec_())