# -*- coding: utf-8 -*-
"""
绘图助手 - 点击操作工具模块
负责所有鼠标点击相关的功能
"""

import logging
import time
import ctypes
import random
from ctypes import wintypes, Structure, c_long

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
MOUSEEVENTF_LEFTCLICK = 0x0002 | 0x0004  # 左键按下和抬起


class ClickUtils:
    """点击操作工具类"""
    
    def __init__(self):
        # 延迟值完全从UI读取，不设置默认值
        self.color_delay = None
        self.draw_delay = None
        self.move_delay = None
        logging.info("点击操作工具模块初始化完成")
    
    def set_delays(self, color_delay, draw_delay, move_delay):
        """设置延迟参数"""
        self.color_delay = color_delay
        self.draw_delay = draw_delay
        self.move_delay = move_delay
        logging.info(f"ClickUtils延迟设置已更新: 颜色延迟={color_delay}s, 绘图延迟={draw_delay}s, 移动延迟={move_delay}s")
    
    def click_position(self, position):
        """点击指定位置"""
        try:
            # 强制使用Windows API，因为某些游戏可能阻止pyautogui
            return self._click_position_winapi(position)
            
        except Exception as e:
            logging.error(f"点击位置{position}失败: {e}")
            return False
    
    def drag_draw_line(self, start_position, end_position, steps=10):
        """拖动绘制直线，从起始位置拖动到结束位置（优化版）"""
        try:
            # 检查延迟值是否已设置
            if self.move_delay is None or self.draw_delay is None:
                raise ValueError("延迟值未设置，请先调用set_delays方法")
                
            import time
            start_time = time.time()
            
            start_x, start_y = int(start_position[0]), int(start_position[1])
            end_x, end_y = int(end_position[0]), int(end_position[1])
            
            logging.info(f"开始拖动绘制: 从({start_x}, {start_y})到({end_x}, {end_y})，共{steps}步")
            
            # 计算步长
            step_x = (end_x - start_x) / steps
            step_y = (end_y - start_y) / steps
            
            logging.debug(f"拖动步长：x={step_x:.2f}, y={step_y:.2f}")
            
            # 确保最后一步到达结束位置
            logging.debug(f"拖动范围：从({start_x}, {start_y})到({end_x}, {end_y})，距离{end_x - start_x}像素")
            
            # 移动到起始位置
            self._send_mouse_input(start_x, start_y, MOUSEEVENTF_MOVE)
            time.sleep(self.move_delay)  # 使用UI设置的移动延迟
            
            # 按下鼠标左键
            self._send_mouse_input(start_x, start_y, MOUSEEVENTF_LEFTDOWN)
            time.sleep(self.draw_delay)  # 使用UI设置的绘图延迟
            
            # 逐步拖动到结束位置
            for i in range(1, steps + 1):
                if i == steps:
                    # 最后一步确保到达结束位置
                    current_x = end_x
                    current_y = end_y
                else:
                    current_x = int(start_x + step_x * i)
                    current_y = int(start_y + step_y * i)
                
                # 移动到当前位置
                self._send_mouse_input(current_x, current_y, MOUSEEVENTF_MOVE)
                # 添加拖动过程中的延迟，让拖动过程更明显
                time.sleep(self.move_delay)  # 使用UI设置的移动延迟
            
            # 在结束位置松开鼠标左键
            self._send_mouse_input(end_x, end_y, MOUSEEVENTF_LEFTUP)
            time.sleep(self.draw_delay)  # 使用UI设置的绘图延迟
            
            end_time = time.time()
            drag_time = end_time - start_time
            logging.info(f"拖动绘制完成: 从({start_x}, {start_y})到({end_x}, {end_y})，共{steps}步，耗时{drag_time:.3f}秒")
            return True
            
        except Exception as e:
            logging.error(f"拖动绘制失败: {e}")
            return False
    
    def fast_drag_draw_line(self, start_position, end_position):
        """快速拖动绘制直线（极速版）"""
        try:
            start_x, start_y = int(start_position[0]), int(start_position[1])
            end_x, end_y = int(end_position[0]), int(end_position[1])
            
            # 使用SetCursorPos + mouse_event实现瞬间拖动
            # 设置鼠标位置到起始点
            ctypes.windll.user32.SetCursorPos(start_x, start_y)
            
            # 按下鼠标左键
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
            
            # 瞬间移动到结束点
            ctypes.windll.user32.SetCursorPos(end_x, end_y)
            
            # 松开鼠标左键
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
            
            logging.debug(f"瞬间拖动完成: 从({start_x}, {start_y})到({end_x}, {end_y})")
            return True
            
        except Exception as e:
            logging.error(f"瞬间拖动失败: {e}")
            return False
    
    def ultra_fast_drag_draw_line(self, start_position, end_position):
        """超高速拖动绘制直线（无延迟版）"""
        try:
            start_x, start_y = int(start_position[0]), int(start_position[1])
            end_x, end_y = int(end_position[0]), int(end_position[1])
            
            logging.info(f"开始瞬间拖动：从({start_x}, {start_y})到({end_x}, {end_y})")
            
            # 使用最底层的API实现真正的瞬间拖动
            # 直接调用SetCursorPos和mouse_event，无任何延迟
            
            # 移动到起始位置
            ctypes.windll.user32.SetCursorPos(start_x, start_y)
            
            # 立即按下鼠标左键
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            
            # 立即移动到结束位置
            ctypes.windll.user32.SetCursorPos(end_x, end_y)
            
            # 立即松开鼠标左键
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            
            logging.info(f"瞬间拖动完成: 从({start_x}, {start_y})到({end_x}, {end_y})")
            return True
            
        except Exception as e:
            logging.error(f"瞬间拖动失败: {e}")
            return False
    
    def _click_position_winapi(self, position):
        """使用Windows API点击位置，包含多种点击方法和重试机制"""
        try:
            # 检查延迟值是否已设置
            if self.move_delay is None or self.draw_delay is None:
                raise ValueError("延迟值未设置，请先调用set_delays方法")
                
            target_x, target_y = int(position[0]), int(position[1])
            
            # 直接点击目标位置
            final_x = target_x
            final_y = target_y
            
            # 直接移动到目标位置
            self._send_mouse_input(final_x, final_y, MOUSEEVENTF_MOVE)
            # 使用UI设置的移动延迟
            time.sleep(self.move_delay)
            
            # 尝试多种点击方法，提高游戏兼容性
            success = False
            
            # 方法1: SendInput API（主要方法）
            try:
                self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTDOWN)
                time.sleep(self.draw_delay)  # 使用UI设置的绘图延迟
                self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTUP)
                success = True
            except Exception as e:
                logging.warning(f"SendInput点击失败: {e}，尝试备用方法")
            
            # 方法2: SetCursorPos + mouse_event API（备用方法）
            if not success:
                try:
                    # 设置鼠标位置
                    ctypes.windll.user32.SetCursorPos(final_x, final_y)
                    time.sleep(self.move_delay)
                    
                    # 使用mouse_event API
                    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                    time.sleep(self.draw_delay)  # 使用UI设置的绘图延迟
                    ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
                    success = True
                except Exception as e:
                    logging.warning(f"mouse_event点击失败: {e}")
            
            # 方法3: 重复点击（某些游戏需要多次点击才能识别）
            if not success:
                try:
                    for attempt in range(2):
                        self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTDOWN)
                        time.sleep(self.draw_delay)
                        self._send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTUP)
                        time.sleep(self.draw_delay)
                    success = True
                except Exception as e:
                    logging.error(f"重复点击失败: {e}")
            
            # 等待点击完成
            time.sleep(self.draw_delay)  # 使用UI设置的绘图延迟
            
            if not success:
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
                
        except Exception as e:
            logging.error(f"发送鼠标输入失败: {e}")
            raise


# 创建全局实例
click_utils = ClickUtils()

# 便捷函数
def click_position(position):
    """便捷的点击位置函数"""
    return click_utils.click_position(position)

def drag_draw_line(start_position, end_position, steps=10):
    """便捷的拖动绘制函数"""
    return click_utils.drag_draw_line(start_position, end_position, steps)

def fast_drag_draw_line(start_position, end_position):
    """便捷的快速拖动绘制函数"""
    return click_utils.fast_drag_draw_line(start_position, end_position)

def ultra_fast_drag_draw_line(start_position, end_position):
    """便捷的超高速拖动绘制函数"""
    return click_utils.ultra_fast_drag_draw_line(start_position, end_position)
