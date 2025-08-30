# -*- coding: utf-8 -*-
"""
钓鱼助手 - 工作线程模块
负责后台工作线程，包括点击操作、检测任务等
"""

import time
import random
import logging
import ctypes
from ctypes import wintypes, Structure, c_long, c_ulong, byref
from PyQt5.QtCore import QThread, pyqtSignal, QTimer

try:
    import pygetwindow as gw
    WINDOW_CONTROL_ENABLED = True
except ImportError:
    WINDOW_CONTROL_ENABLED = False
    logging.warning("pygetwindow 未安装，窗口控制功能将被禁用")

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


class ClickThread(QThread):
    """点击操作线程"""
    
    finished = pyqtSignal()
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)
    
    def __init__(self, click_config, target_pos, parent=None):
        super().__init__(parent)
        self.click_config = click_config
        self.target_pos = target_pos
        self.is_running = True
        
    def run(self):
        """线程主函数"""
        try:
            self.perform_click()
        except Exception as e:
            logging.error(f"点击线程执行错误: {e}")
            self.error.emit(str(e))
        finally:
            self.finished.emit()
    
    def stop(self):
        """停止线程"""
        self.is_running = False
        self.quit()
        # 设置超时等待，避免阻塞主线程
        if not self.wait(2000):  # 等待2秒
            logging.warning("ClickThread停止超时，强制终止")
            self.terminate()
            self.wait(1000)  # 再等待1秒
    
    def perform_click(self):
        """执行点击操作"""
        if not self.is_running or not WINDOW_CONTROL_ENABLED:
            return
            
        # 检查目标位置
        if self.target_pos is None or len(self.target_pos) < 2:
            self.error.emit("目标位置无效")
            return
            
        # 激活目标窗口
        window_title = self.click_config.get('window_title', '心动小镇')
        game_windows = gw.getWindowsWithTitle(window_title)
        if not game_windows:
            self.error.emit(f"未找到 '{window_title}' 窗口")
            return
        
        game_win = game_windows[0]
        if game_win.isMinimized:
            game_win.restore()

        # 1. 尝试激活窗口
        try:
            game_win.activate()
        except Exception:
            # Fallback: 点击标题栏激活窗口
            x, y = game_win.left + 20, game_win.top + 10
            self.send_mouse_input(x, y, MOUSEEVENTF_LEFTDOWN)
            time.sleep(0.05)
            self.send_mouse_input(x, y, MOUSEEVENTF_LEFTUP)
        
        time.sleep(0.5)  # 等待窗口激活

        # 2. 验证窗口是否真的被激活
        active_window = gw.getActiveWindow()
        if not active_window or window_title not in active_window.title:
            self.error.emit(f"'{window_title}' 窗口未能激活")
            return

        # 3. 移动到目标位置并点击（增加随机偏移和抖动）
        target_x, target_y = int(self.target_pos[0]), int(self.target_pos[1])
        
        # 动态获取屏幕尺寸
        try:
            screen_width = ctypes.windll.user32.GetSystemMetrics(0)
            screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            logging.info(f"检测到屏幕尺寸: {screen_width}x{screen_height}")
        except Exception as e:
            logging.error(f"获取屏幕尺寸失败: {e}")
            # 使用默认尺寸
            screen_width, screen_height = 1920, 1080
        
        # 添加随机偏移，避免总是点击图片正中心
        offset_range = 8  # 偏移范围：±8像素
        random_offset_x = random.randint(-offset_range, offset_range)
        random_offset_y = random.randint(-offset_range, offset_range)
        
        # 计算最终点击位置
        final_x = target_x + random_offset_x
        final_y = target_y + random_offset_y
        
        # 确保坐标在屏幕范围内
        final_x = max(0, min(final_x, screen_width - 1))
        final_y = max(0, min(final_y, screen_height - 1))
        
        logging.info(f"点击坐标: 原始({target_x}, {target_y}), 最终({final_x}, {final_y})")
        
        # 移动到目标位置（带随机偏移）
        self.send_mouse_input(final_x, final_y, MOUSEEVENTF_MOVE)
        time.sleep(self.click_config.get('move_delay', 0.15))

        # 添加点击前的微抖动
        jitter_delay = random.uniform(0.05, 0.15)
        time.sleep(jitter_delay)
        
        # 点击（带随机延迟）
        self.send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTDOWN)
        press_delay = self.click_config.get('press_delay', 0.1) + random.uniform(-0.02, 0.02)
        press_delay = max(0.05, press_delay)  # 确保最小延迟
        time.sleep(press_delay)
        
        self.send_mouse_input(final_x, final_y, MOUSEEVENTF_LEFTUP)
        
        # 等待点击完成（带随机延迟）
        final_delay = self.click_config.get('final_delay', 0.1) + random.uniform(-0.02, 0.02)
        final_delay = max(0.05, final_delay)  # 确保最小延迟
        time.sleep(final_delay)
        
        logging.info(f"点击完成: ({final_x}, {final_y})")
    
    def send_mouse_input(self, x, y, flags):
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


class DetectionWorker(QThread):
    """检测工作线程"""
    
    detection_completed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, business_logic, auto_click_enabled=True, auto_fish_tail_enabled=False, parent=None):
        super().__init__(parent)
        self.business_logic = business_logic
        self.auto_click_enabled = auto_click_enabled
        self.auto_fish_tail_enabled = auto_fish_tail_enabled
        self.is_running = True
        
    def run(self):
        """线程主函数"""
        try:
            while self.is_running:
                if self.business_logic.is_detecting:
                    self.business_logic.auto_detect_buttons(
                        self.auto_click_enabled, 
                        self.auto_fish_tail_enabled
                    )
                
                # 检测间隔
                self.msleep(100)  # 100ms间隔
                
        except Exception as e:
            logging.error(f"检测工作线程错误: {e}")
            self.error_occurred.emit(str(e))
        finally:
            self.detection_completed.emit()
    
    def stop(self):
        """停止线程"""
        self.is_running = False
        self.quit()
        # 设置超时等待，避免阻塞主线程
        if not self.wait(2000):  # 等待2秒
            logging.warning("DetectionWorker停止超时，强制终止")
            self.terminate()
            self.wait(1000)  # 再等待1秒
    
    def update_settings(self, auto_click_enabled, auto_fish_tail_enabled):
        """更新设置"""
        self.auto_click_enabled = auto_click_enabled
        self.auto_fish_tail_enabled = auto_fish_tail_enabled


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
            keyboard.add_hotkey('o', self._on_o_pressed)
            keyboard.add_hotkey('p', self._on_p_pressed)
            self.hotkeys_registered = True
            logging.info("热键注册成功: O键开始检测, P键停止检测")
            
            # 保持线程运行
            while self.is_running:
                time.sleep(0.1)
                
        except Exception as e:
            logging.error(f"热键监听线程错误: {e}")
        finally:
            self._cleanup_hotkeys()
    
    def _on_o_pressed(self):
        """O键按下处理"""
        self.hotkey_pressed.emit('o')
    
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
                keyboard.remove_hotkey('o')
                keyboard.remove_hotkey('p')
                self.hotkeys_registered = False
                logging.info("热键注册已清理")
            except Exception as e:
                logging.error(f"清理热键注册时发生错误: {e}")


class TimerWorker(QThread):
    """定时器工作线程"""
    
    timeout = pyqtSignal()  # 超时信号
    
    def __init__(self, interval_ms=100, parent=None):
        super().__init__(parent)
        self.interval_ms = interval_ms
        self.is_running = True
        
    def run(self):
        """线程主函数"""
        try:
            while self.is_running:
                self.timeout.emit()
                self.msleep(self.interval_ms)
        except Exception as e:
            logging.error(f"定时器工作线程错误: {e}")
    
    def stop(self):
        """停止线程"""
        self.is_running = False
        self.quit()
        # 设置超时等待，避免阻塞主线程
        if not self.wait(2000):  # 等待2秒
            logging.warning("TimerWorker停止超时，强制终止")
            self.terminate()
            self.wait(1000)  # 再等待1秒
    
    def set_interval(self, interval_ms):
        """设置间隔时间"""
        self.interval_ms = interval_ms


class WorkerManager:
    """工作线程管理器"""
    
    def __init__(self):
        self.click_thread = None
        self.detection_worker = None
        self.hotkey_worker = None
        self.timer_worker = None
        
    def start_click_thread(self, click_config, target_pos):
        """启动点击线程"""
        if self.click_thread and self.click_thread.isRunning():
            self.click_thread.stop()
            # 设置超时等待，避免阻塞主线程
            if not self.click_thread.wait(2000):  # 等待2秒
                logging.warning("ClickThread启动等待超时，强制终止")
                self.click_thread.terminate()
                self.click_thread.wait(1000)  # 再等待1秒
        
        self.click_thread = ClickThread(click_config, target_pos)
        self.click_thread.start()
        return self.click_thread
    
    def start_detection_worker(self, business_logic, auto_click_enabled=True, auto_fish_tail_enabled=False):
        """启动检测工作线程"""
        if self.detection_worker and self.detection_worker.isRunning():
            self.detection_worker.stop()
            # 设置超时等待，避免阻塞主线程
            if not self.detection_worker.wait(2000):  # 等待2秒
                logging.warning("DetectionWorker启动等待超时，强制终止")
                self.detection_worker.terminate()
                self.detection_worker.wait(1000)  # 再等待1秒
        
        self.detection_worker = DetectionWorker(business_logic, auto_click_enabled, auto_fish_tail_enabled)
        self.detection_worker.start()
        return self.detection_worker
    
    def start_hotkey_worker(self):
        """启动热键监听线程"""
        if self.hotkey_worker and self.hotkey_worker.isRunning():
            self.hotkey_worker.stop()
            # 设置超时等待，避免阻塞主线程
            if not self.hotkey_worker.wait(2000):  # 等待2秒
                logging.warning("HotkeyWorker启动等待超时，强制终止")
                self.hotkey_worker.terminate()
                self.hotkey_worker.wait(1000)  # 再等待1秒
        
        self.hotkey_worker = HotkeyWorker()
        self.hotkey_worker.start()
        return self.hotkey_worker
    
    def start_timer_worker(self, interval_ms=100):
        """启动定时器工作线程"""
        if self.timer_worker and self.timer_worker.isRunning():
            self.timer_worker.stop()
            # 设置超时等待，避免阻塞主线程
            if not self.timer_worker.wait(2000):  # 等待2秒
                logging.warning("TimerWorker启动等待超时，强制终止")
                self.timer_worker.terminate()
                self.timer_worker.wait(1000)  # 再等待1秒
        
        self.timer_worker = TimerWorker(interval_ms)
        self.timer_worker.start()
        return self.timer_worker
    
    def stop_all_workers(self):
        """停止所有工作线程"""
        workers = [self.click_thread, self.detection_worker, self.hotkey_worker, self.timer_worker]
        worker_names = ["click_thread", "detection_worker", "hotkey_worker", "timer_worker"]
        
        for worker, name in zip(workers, worker_names):
            if worker and worker.isRunning():
                try:
                    logging.info(f"正在停止 {name}...")
                    worker.stop()
                    # 设置超时时间为3秒，防止无限等待
                    if not worker.wait(3000):  # 3000ms = 3秒
                        logging.warning(f"{name} 停止超时，强制终止")
                        worker.terminate()
                        worker.wait(1000)  # 等待1秒让线程完全终止
                    else:
                        logging.info(f"{name} 已成功停止")
                except Exception as e:
                    logging.error(f"停止 {name} 时发生错误: {e}")
                    try:
                        worker.terminate()
                        worker.wait(1000)
                    except Exception as terminate_error:
                        logging.error(f"强制终止 {name} 时发生错误: {terminate_error}")
        
        logging.info("所有工作线程已停止")
    
    def is_click_thread_running(self):
        """检查点击线程是否在运行"""
        return self.click_thread and self.click_thread.isRunning()
    
    def is_detection_worker_running(self):
        """检查检测工作线程是否在运行"""
        return self.detection_worker and self.detection_worker.isRunning()
    
    def is_hotkey_worker_running(self):
        """检查热键监听线程是否在运行"""
        return self.hotkey_worker and self.hotkey_worker.isRunning()
    
    def is_timer_worker_running(self):
        """检查定时器工作线程是否在运行"""
        return self.timer_worker and self.timer_worker.isRunning()
    
    def update_detection_settings(self, auto_click_enabled, auto_fish_tail_enabled):
        """更新检测设置"""
        if self.detection_worker:
            self.detection_worker.update_settings(auto_click_enabled, auto_fish_tail_enabled)
    
    def set_timer_interval(self, interval_ms):
        """设置定时器间隔"""
        if self.timer_worker:
            self.timer_worker.set_interval(interval_ms)