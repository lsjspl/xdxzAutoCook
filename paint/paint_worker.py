# -*- coding: utf-8 -*-
"""
绘图助手 - 工作线程模块
负责后台绘图任务和鼠标点击操作
"""

import logging
import time
from PyQt5.QtCore import QThread, pyqtSignal
from click_utils import click_position
import keyboard
from click_utils import click_utils
import time
from PIL import ImageGrab

HOTKEY_ENABLED = True

class DrawingWorker(QThread):
    """绘图工作线程"""
    
    # 信号定义
    progress_updated = pyqtSignal(int, int)  # 进度更新 (当前, 总数)
    status_updated = pyqtSignal(str)  # 状态更新
    drawing_completed = pyqtSignal()  # 绘图完成
    drawing_error = pyqtSignal(str)  # 绘图错误
    
    def __init__(self, pixel_info_list=None, collected_colors=None, draw_area_pos=None, palette_button_pos=None, return_button_pos=None, is_debug_mode=False):
        super().__init__()
        
        self.pixel_info_list = pixel_info_list or []
        self.collected_colors = collected_colors or []
        self.draw_area_pos = draw_area_pos
        self.palette_button_pos = palette_button_pos
        self.return_button_pos = return_button_pos
        self.is_debug_mode = is_debug_mode
        
        # 重要：只使用子级颜色，过滤掉父级颜色
        child_colors = [color_info for color_info in self.collected_colors if not color_info.get('is_parent', False)]
        
        # 从收集的颜色中提取调色板（只包含子颜色）
        self.color_palette = [color_info['rgb'] for color_info in child_colors] if child_colors else []
        
        # 记录调试信息
        if child_colors:
            logging.info(f"绘图工作线程初始化：共{len(child_colors)}种子级颜色")
            # 检查子颜色的父颜色索引
            parent_indices = set()
            for color_info in child_colors:
                parent_idx = color_info.get('parent_index')
                if parent_idx is not None:
                    parent_indices.add(parent_idx)
                else:
                    logging.warning(f"子颜色 RGB{color_info['rgb']} 缺少父颜色索引")
            
            logging.info(f"子颜色使用的父颜色索引: {sorted(parent_indices)}")
        else:
            logging.warning("绘图工作线程初始化：没有收集到子级颜色")
        
        # 检查父颜色信息
        parent_colors = [color_info for color_info in self.collected_colors if color_info.get('is_parent', False)]
        if parent_colors:
            logging.info(f"可用父颜色数量: {len(parent_colors)}")
            for i, parent_color in enumerate(parent_colors):
                logging.debug(f"父颜色{i}: RGB{parent_color['rgb']}, 索引: {parent_color.get('parent_index')}")
        else:
            logging.warning("没有找到父颜色信息")
        
        # 添加详细的调试信息
        logging.info(f"=== DrawingWorker 初始化调试信息 ===")
        logging.info(f"总颜色数量: {len(self.collected_colors)}")
        
        # 统计父颜色和子颜色
        parent_count = len([c for c in self.collected_colors if c.get('is_parent', False)])
        child_count = len([c for c in self.collected_colors if not c.get('is_parent', False)])
        logging.info(f"父颜色数量: {parent_count}, 子颜色数量: {child_count}")
        
        # 显示前几个颜色的详细信息
        for i, color in enumerate(self.collected_colors[:5]):
            color_type = "父颜色" if color.get('is_parent', False) else "子颜色"
            parent_idx = color.get('parent_index', '无')
            parent_name = color.get('parent', '无')
            logging.info(f"颜色{i}: {color_type}, RGB{color['rgb']}, 父索引: {parent_idx}, 父名称: {parent_name}")
        
        # 检查子颜色的父索引分布
        if child_count > 0:
            parent_indices = [c.get('parent_index') for c in self.collected_colors if not c.get('is_parent', False) and c.get('parent_index') is not None]
            if parent_indices:
                logging.info(f"子颜色使用的父索引: {sorted(set(parent_indices))}")
                logging.info(f"父索引范围: {min(parent_indices)} - {max(parent_indices)}")
        
        logging.info(f"=== 调试信息结束 ===")
        
        # 记录按钮位置信息
        if palette_button_pos:
            logging.info(f"色盘按钮位置: {palette_button_pos}")
        else:
            logging.warning("色盘按钮位置未设置")
            
        if return_button_pos:
            logging.info(f"返回按钮位置: {return_button_pos}")
        else:
            logging.warning("返回按钮位置未设置")
        
        self.is_running = False
        self.should_stop = False
        
        # 点击延迟设置 - 完全从UI读取，不设置默认值
        self.color_click_delay = None
        self.draw_click_delay = None
        self.mouse_move_delay = None
        

        self.click_utils = click_utils
        
        logging.info("绘图工作线程初始化完成")
    
    def set_click_delays(self, color_delay, draw_delay, move_delay):
        """设置点击延迟参数"""
        # 验证延迟值是否有效
        if color_delay is None or draw_delay is None or move_delay is None:
            raise ValueError("延迟值不能为空，请确保UI输入框有有效值")
        
        self.color_click_delay = color_delay
        self.draw_click_delay = draw_delay
        self.mouse_move_delay = move_delay
        
        # 同时设置ClickUtils的延迟
        if hasattr(self, 'click_utils'):
            self.click_utils.set_delays(color_delay, draw_delay, move_delay)
        
        logging.info(f"DrawingWorker延迟设置已更新: 颜色延迟={color_delay}s, 绘图延迟={draw_delay}s, 移动延迟={move_delay}s")
    
    def run(self):
        """线程主函数"""
        try:

            start_time = time.time()
            
            self.is_running = True
            self.should_stop = False
            
            logging.info(f"开始绘画任务 - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 调试模式：直接显示像素点，不进行颜色选择
            if self.is_debug_mode:
                self._run_debug_mode()
                return
            
            total_pixels = len(self.pixel_info_list)
            self.status_updated.emit(f"开始绘图，共{total_pixels}个像素点")
            
            # 按颜色分组像素
            color_groups = self._group_pixels_by_color()
            total_colors = len(color_groups)
            
            self.status_updated.emit(f"按颜色分组完成，共{total_colors}种颜色")
            logging.info(f"按颜色分组完成，共{total_colors}种颜色")
            
            processed_pixels = 0
            
            for group_index, (color_idx, (color_info, pixel_positions)) in enumerate(color_groups.items()):
                # 检查是否需要停止
                if self.should_stop:
                    self.status_updated.emit("绘图已被用户停止")
                    break
                
                pixels_in_group = len(pixel_positions)
                self.status_updated.emit(f"开始绘制颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}），共{pixels_in_group}个像素点")
                logging.info(f"开始绘制颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}），共{pixels_in_group}个像素点")
                
                # 实现正确的游戏操作流程
                success = self._select_color_for_drawing(color_info)
                if not success:
                    logging.warning(f"选择颜色失败，跳过该颜色: RGB{color_info.get('rgb', 'Unknown')}")
                    processed_pixels += pixels_in_group
                    continue
                
                # 绘制该颜色的所有像素点
                # 逐个点击像素
                group_processed = self._draw_pixels_individual(pixel_positions, processed_pixels, total_pixels)
                processed_pixels += group_processed
                
                # 完成当前颜色的绘制后，返回到父颜色区域
                if not self.should_stop:
                    self._return_to_parent_colors()
                    color_progress_percent = (group_index + 1) / total_colors * 100
                    self.status_updated.emit(f"颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}） 绘制完成 ({color_progress_percent:.1f}%)")
                    logging.info(f"颜色 {group_index + 1}/{total_colors}（颜色索引{color_idx}） 绘制完成")
            
            # 绘图完成
            if not self.should_stop:
                end_time = time.time()
                total_time = end_time - start_time
                self.drawing_completed.emit()
                self.status_updated.emit(f"绘图完成，总耗时：{total_time:.2f}秒")
                logging.info(f"绘图完成 - 总耗时：{total_time:.2f}秒 ({time.strftime('%Y-%m-%d %H:%M:%S')})")
            
        except Exception as e:
            error_msg = f"绘图过程中发生错误: {str(e)}"
            logging.error(error_msg)
            self.drawing_error.emit(error_msg)
        
        finally:
            self.is_running = False
            logging.info("绘图工作线程已结束")
    
    def stop_drawing(self):
        """停止绘图"""
        self.should_stop = True
        logging.info("绘图停止请求已发送")
    
    def _run_debug_mode(self):
        """调试模式：直接显示像素点"""
        try:
            total_pixels = len(self.pixel_info_list)
            self.status_updated.emit(f"调试模式：开始显示{total_pixels}个像素点")
            logging.info(f"调试模式：开始显示{total_pixels}个像素点")
            
            processed_pixels = 0
            
            for i, pixel_info in enumerate(self.pixel_info_list):
                # 检查是否需要停止
                if self.should_stop:
                    self.status_updated.emit("调试显示已被用户停止")
                    break
                
                position = pixel_info['position']
                color = pixel_info['color']
                grid_pos = pixel_info.get('grid_pos', (0, 0))
                
                # 直接点击像素位置（不选择颜色）
                success = click_position(position)
                if not success:
                    logging.warning(f"调试模式：点击位置{position}失败")
                    continue
                
                # 短暂延迟
                self._interruptible_sleep(0.01)  # 10ms延迟
                if self.should_stop:
                    self.status_updated.emit("调试显示已被用户停止")
                    break
                
                processed_pixels += 1
                
                # 更新进度
                self.progress_updated.emit(processed_pixels, total_pixels)
                
                # 每100个像素输出一次进度
                if processed_pixels % 100 == 0:
                    progress_percent = processed_pixels / total_pixels * 100
                    self.status_updated.emit(f"调试进度: {processed_pixels}/{total_pixels} ({progress_percent:.1f}%)")
                    logging.info(f"调试进度: {processed_pixels}/{total_pixels} ({progress_percent:.1f}%)")
            
            # 调试完成
            if not self.should_stop:
                self.drawing_completed.emit()
                self.status_updated.emit("调试显示完成")
                logging.info("调试显示完成")
            else:
                self.status_updated.emit("调试显示已停止")
                logging.info("调试显示已停止")
            
        except Exception as e:
            error_msg = f"调试模式过程中发生错误: {str(e)}"
            logging.error(error_msg)
            self.drawing_error.emit(error_msg)
        finally:
            # 确保线程状态正确设置
            self.is_running = False
    
    def _group_pixels_by_color(self):
        """按颜色分组像素点"""
        color_groups = {}
        
        for pixel_info in self.pixel_info_list:
            position = pixel_info['position']
            target_color = pixel_info['color']
            
            # 直接通过RGB值获取颜色信息，避免索引错位
            color_info = self._get_color_info_by_rgb(target_color)
            
            if color_info:
                # 使用RGB值作为分组键，确保唯一性
                rgb_key = str(color_info['rgb'])
                if rgb_key not in color_groups:
                    color_groups[rgb_key] = (color_info, [])
                
                # 将像素位置添加到对应颜色组
                color_groups[rgb_key][1].append(position)
            else:
                logging.warning(f"无法获取颜色RGB{target_color}的信息，跳过像素{position}")
        
        logging.info(f"颜色分组完成，共{len(color_groups)}种颜色")
        for rgb_key, (color_info, positions) in color_groups.items():
            # 获取颜色信息用于调试
            color_type = "父级颜色" if color_info.get('is_parent', False) else "子级颜色"
            parent_info = color_info.get('parent', '未知父颜色')
            parent_idx = color_info.get('parent_index', '无')
            logging.info(f"颜色RGB{rgb_key}({color_type}): RGB{color_info['rgb']}, 父颜色: {parent_info}, 父索引: {parent_idx}, {len(positions)}个像素点")
        
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
    
    def _draw_pixels_individual(self, pixel_positions, base_processed_pixels, total_pixels):
        """传统模式：逐个点击像素"""
        group_processed_pixels = 0
        
        for i, position in enumerate(pixel_positions):
            # 检查是否需要停止
            if self.should_stop:
                self.status_updated.emit("绘图已被用户停止")
                break
            
            # 点击绘图位置
            success = click_position(position)
            if not success:
                logging.warning(f"点击绘图位置{position}失败")
                continue
            
            # 在延迟期间检查停止标志
            self._interruptible_sleep(self.draw_click_delay)
            if self.should_stop:
                self.status_updated.emit("绘图已被用户停止")
                break
            
            group_processed_pixels += 1
            current_total_processed = base_processed_pixels + group_processed_pixels
            
            # 更新进度
            self.progress_updated.emit(current_total_processed, total_pixels)
            
            # 每50个像素输出一次进度
            if current_total_processed % 50 == 0:
                progress_percent = current_total_processed / total_pixels * 100
                self.status_updated.emit(f"绘图进度: {current_total_processed}/{total_pixels} ({progress_percent:.1f}%)")
                logging.info(f"绘图进度: {current_total_processed}/{total_pixels} ({progress_percent:.1f}%)")
        
        return group_processed_pixels
    

    def _get_color_info(self, color_index):
        """获取颜色的完整信息"""
        try:
            if not self.collected_colors or color_index >= len(self.collected_colors):
                return None
            
            # 直接从收集的颜色信息中获取完整信息
            color_info = self.collected_colors[color_index]
            return color_info
            
        except Exception as e:
            logging.error(f"获取颜色信息失败: {e}")
            return None
    
    def _get_color_info_by_rgb(self, target_rgb):
        """通过RGB值获取颜色信息"""
        try:
            if not self.collected_colors:
                return None
            
            # 找到最接近的颜色
            min_distance = float('inf')
            closest_color_info = None
            
            for color_info in self.collected_colors:
                if not color_info.get('is_parent', False):  # 只考虑子颜色
                    rgb = color_info['rgb']
                    distance = sum((a - b) ** 2 for a, b in zip(target_rgb[:3], rgb[:3])) ** 0.5
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_color_info = color_info
            
            return closest_color_info
            
        except Exception as e:
            logging.error(f"通过RGB获取颜色信息失败: {e}")
            return None
    
    def _select_color_for_drawing(self, color_info):
        """选择颜色进行绘图的完整流程"""
        try:
            # 检查是否需要停止
            if self.should_stop:
                return False
            
            # 获取父颜色信息
            parent_index = color_info.get('parent_index')
            if parent_index is None:
                logging.warning(f"颜色信息中缺少父颜色索引: {color_info}")
                return False
            
            # 1. 点击对应的父颜色按钮
            parent_color_info = self._get_parent_color_info(parent_index)
            if not parent_color_info:
                logging.warning(f"无法获取父颜色信息，索引: {parent_index}")
                return False
            
            logging.info(f"步骤1: 点击父颜色 RGB{parent_color_info['rgb']}")
            success = click_position(parent_color_info['position'])
            if not success:
                logging.warning(f"点击父颜色失败: {parent_color_info['position']}")
                return False
            
            # 等待父颜色选择生效
            self._interruptible_sleep(0.3)
            if self.should_stop:
                return False
            
            # 2. 点击色盘按钮进入子颜色区域
            palette_button_pos = self._get_palette_button_position()
            if not palette_button_pos:
                logging.warning("色盘按钮位置未设置")
                return False
            
            logging.info(f"步骤2: 点击色盘按钮进入子颜色区域")
            success = click_position(palette_button_pos)
            if not success:
                logging.warning(f"点击色盘按钮失败: {palette_button_pos}")
                return False
            
            # 等待进入子颜色区域
            self._interruptible_sleep(0.5)
            if self.should_stop:
                return False
            
            # 3. 点击对应的子颜色
            logging.info(f"步骤3: 选择子颜色 RGB{color_info['rgb']}")
            success = click_position(color_info['position'])
            if not success:
                logging.warning(f"点击子颜色失败: {color_info['position']}")
                return False
            
            # 等待子颜色选择生效
            self._interruptible_sleep(self.color_click_delay)
            if self.should_stop:
                return False
            
            logging.info(f"颜色选择完成: RGB{color_info['rgb']}")
            return True
            
        except Exception as e:
            logging.error(f"选择颜色失败: {e}")
            return False
    
    def _return_to_parent_colors(self):
        """返回到父颜色区域"""
        try:
            # 检查是否需要停止
            if self.should_stop:
                return
            
            # 点击色板返回按钮
            return_button_pos = self._get_return_button_position()
            if not return_button_pos:
                logging.warning("色板返回按钮位置未设置")
                return
            
            logging.info("返回到父颜色区域")
            success = click_position(return_button_pos)
            if success:
                # 等待返回动画完成
                self._interruptible_sleep(0.3)
                logging.info("已返回父颜色区域")
            else:
                logging.warning(f"点击色板返回按钮失败: {return_button_pos}")
                
        except Exception as e:
            logging.error(f"返回父颜色区域失败: {e}")
    
    def _get_parent_color_info(self, parent_index):
        """获取父颜色信息"""
        try:
            # 从collected_colors中查找对应的父颜色
            for color_info in self.collected_colors:
                if color_info.get('is_parent', False) and color_info.get('parent_index') == parent_index:
                    return color_info
            
            # 如果没有找到父颜色信息，尝试从业务逻辑中获取
            # 这里需要访问业务逻辑层的父颜色信息
            logging.warning(f"未找到父颜色信息，索引: {parent_index}")
            
            # 尝试通过索引直接查找（如果父颜色是按顺序排列的）
            parent_colors = [c for c in self.collected_colors if c.get('is_parent', False)]
            if 0 <= parent_index < len(parent_colors):
                return parent_colors[parent_index]
            
            logging.error(f"父颜色索引 {parent_index} 超出范围，可用父颜色数量: {len(parent_colors)}")
            return None
            
        except Exception as e:
            logging.error(f"获取父颜色信息失败: {e}")
            return None
    
    def _get_palette_button_position(self):
        """获取色盘按钮位置"""
        if self.palette_button_pos:
            # 计算按钮中心点
            center_x = self.palette_button_pos[0] + self.palette_button_pos[2] // 2
            center_y = self.palette_button_pos[1] + self.palette_button_pos[3] // 2
            return (center_x, center_y)
        return None
    
    def _get_return_button_position(self):
        """获取色板返回按钮位置"""
        if self.return_button_pos:
            # 计算按钮中心点
            center_x = self.return_button_pos[0] + self.return_button_pos[2] // 2
            center_y = self.return_button_pos[1] + self.return_button_pos[3] // 2
            return (center_x, center_y)
        return None
    



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
