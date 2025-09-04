# -*- coding: utf-8 -*-
"""
绘图助手 - 点击操作工具模块
负责所有鼠标点击相关的功能
"""

import logging
import time
import ctypes
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
            
            # 将像素坐标夹紧到屏幕范围内
            sx = max(0, min(int(x), screen_width - 1))
            sy = max(0, min(int(y), screen_height - 1))
            
            # 转换为绝对坐标 (0-65535) - 使用(screen_size - 1)作为分母，避免边缘行/列映射不到位
            if flags & MOUSEEVENTF_MOVE or flags & MOUSEEVENTF_LEFTDOWN or flags & MOUSEEVENTF_LEFTUP:
                denom_w = max(1, screen_width - 1)
                denom_h = max(1, screen_height - 1)
                abs_x = int(round(sx * 65535 / denom_w))
                abs_y = int(round(sy * 65535 / denom_h))
                flags |= MOUSEEVENTF_ABSOLUTE
            else:
                abs_x, abs_y = sx, sy

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
