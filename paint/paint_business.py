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
from config_manager import ConfigManager
from click_utils import click_position
import re
##
class PaintBusiness(QObject):
    """绘图助手业务逻辑类"""
    
    # 信号定义
    status_updated = pyqtSignal(str)
    image_processed = pyqtSignal(object)  # 图片处理完成
    drawing_progress = pyqtSignal(int, int)  # 绘图进度 (当前, 总数)
    drawing_completed = pyqtSignal()  # 绘图完成
    colors_collected = pyqtSignal(list)  # 颜色收集完成
    pixel_debug_requested = pyqtSignal(list)  # 像素调试信息请求

    
    def __init__(self):
        super().__init__()
        
        # 图片处理器
        self.image_processor = ImageProcessor()
        
        # 配置管理器
        self.config_manager = ConfigManager()
        
        # 添加线程锁来保护状态变量
        self._state_lock = threading.Lock()
        
        # 绘图区域和颜色区域
        self.draw_area_pos = None  # (x, y, width, height)
        self.parent_color_area_pos = None  # (x, y, width, height) - 父颜色区域
        self.color_palette_button_pos = None  # (x, y, width, height) - 色盘按钮
        self.color_swatch_return_button_pos = None  # (x, y, width, height) - 色板返回按钮
        self.child_color_area_pos = None  # (x, y, width, height) - 子颜色区域
        self.background_color_button_pos = None  # (x, y, width, height) - 背景色按钮
        
        # 图片和处理结果
        self.selected_image_path = None
        self.pixelized_image = None
        self.color_palette = []
        self.pixel_info_list = []
        

        
        # 新增：收集到的颜色信息
        self.collected_colors = []  # 存储收集到的所有颜色信息
        
        # 绘图状态
        self.is_drawing = False
        self.drawing_thread = None
        
        # 延迟配置
        self.color_click_delay = 0.5  # 颜色点击延迟
        self.draw_click_delay = 0.05  # 绘图点击延迟
        self.mouse_move_delay = 0.01  # 鼠标移动延迟
        
        logging.info("绘图业务逻辑初始化完成")
    
    def reset_image_related_data(self):
        """重置图片相关的数据，保留用户配置"""
        with self._state_lock:
            logging.info("重置business中的图片相关数据")
            
            # 重置图片相关的数据
            self.selected_image_path = None
            self.pixelized_image = None
            self.color_palette = []
            self.pixel_info_list = []
            
            logging.info("business中的图片相关数据已重置")
    
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
    
    def set_parent_color_area(self, position):
        """设置父颜色区域"""
        with self._state_lock:
            self.parent_color_area_pos = position
            if position:
                logging.info(f"父颜色区域已设置: {position}")
                self.status_updated.emit(f"父颜色区域已设置: {position[2]}×{position[3]} 像素")
            else:
                logging.info("父颜色区域已清除")
                self.status_updated.emit("父颜色区域已清除")
    
    def set_color_palette_button(self, position):
        """设置色盘按钮位置"""
        with self._state_lock:
            self.color_palette_button_pos = position
            if position:
                logging.info(f"色盘按钮已设置: {position}")
                self.status_updated.emit(f"色盘按钮已设置: ({position[0]}, {position[1]})")
            else:
                logging.info("色盘按钮已清除")
                self.status_updated.emit("色盘按钮已清除")
    
    def set_color_swatch_return_button(self, position):
        """设置色板返回按钮位置"""
        with self._state_lock:
            self.color_swatch_return_button_pos = position
            if position:
                logging.info(f"色板返回按钮已设置: {position}")
                self.status_updated.emit(f"色板返回按钮已设置: ({position[0]}, {position[1]})")
            else:
                logging.info("色板返回按钮已清除")
                self.status_updated.emit("色板返回按钮已清除")
    
    def set_child_color_area(self, position):
        """设置子颜色区域"""
        with self._state_lock:
            self.child_color_area_pos = position
            if position:
                logging.info(f"子颜色区域已设置: {position}")
                self.status_updated.emit(f"子颜色区域已设置: {position[2]}×{position[3]} 像素")
            else:
                logging.info("子颜色区域已清除")
                self.status_updated.emit("子颜色区域已清除")
    
    def set_background_color_button(self, position):
        """设置背景色按钮位置"""
        with self._state_lock:
            self.background_color_button_pos = position
            if position:
                logging.info(f"背景色按钮已设置: {position}")
                self.status_updated.emit(f"背景色按钮已设置: ({position[0]}, {position[1]})")
                # 立即读取背景色
                self._read_background_color()
            else:
                logging.info("背景色按钮已清除")
                self.status_updated.emit("背景色按钮已清除")
    
    def _read_background_color(self):
        """读取背景色按钮的颜色"""
        try:
            if not self.background_color_button_pos:
                return
            
            # 截取当前屏幕
            screenshot = ImageGrab.grab()
            
            # 计算按钮中心点
            center_x = self.background_color_button_pos[0] + self.background_color_button_pos[2] // 2
            center_y = self.background_color_button_pos[1] + self.background_color_button_pos[3] // 2
            
            # 获取中心点颜色
            color = screenshot.getpixel((center_x, center_y))
            
            # 如果是RGBA格式，转换为RGB
            if len(color) == 4:
                color = color[:3]
            
            logging.info(f"背景色读取完成: RGB{color}")
            self.status_updated.emit(f"背景色读取完成: RGB{color}")
            
        except Exception as e:
            logging.error(f"读取背景色失败: {e}")
            self.status_updated.emit(f"读取背景色失败: {str(e)}")
    
    def collect_colors(self):
        """收集颜色"""
        try:
            if not self._check_color_collection_ready():
                return False
            
            self.status_updated.emit("开始收集颜色...")
            logging.info("开始收集颜色")
            
            # 清空之前的收集结果
            self.collected_colors = []
            
            # 获取父颜色区域的颜色信息（不收集，只是分析）
            parent_color_info = self._analyze_parent_color_area()
            if not parent_color_info:
                self.status_updated.emit("父颜色区域分析失败")
                return False
            
            logging.info(f"父颜色区域分析完成，共{len(parent_color_info)}个颜色按钮")
            
            # 遍历每个父颜色按钮，收集其对应的子颜色
            for i, color_info in enumerate(parent_color_info):
                try:
                    self.status_updated.emit(f"正在收集第{i+1}/{len(parent_color_info)}个父颜色的子颜色...")
                    logging.info(f"开始收集第{i+1}个父颜色的子颜色: RGB{color_info['rgb']}")
                    
                    # 1. 点击父颜色按钮
                    success = click_position(color_info['position'])
                    if not success:
                        logging.warning(f"点击父颜色按钮失败，跳过: {color_info['rgb']}")
                        continue
                    
                    # 等待颜色选择生效
                    time.sleep(0.3)
                    
                    # 2. 点击色盘按钮进入子颜色区域
                    if self.color_palette_button_pos:
                        # 计算色盘按钮中心点
                        palette_x = self.color_palette_button_pos[0] + self.color_palette_button_pos[2] // 2
                        palette_y = self.color_palette_button_pos[1] + self.color_palette_button_pos[3] // 2
                        success = click_position((palette_x, palette_y))
                        if not success:
                            logging.warning(f"点击色盘按钮失败，跳过当前父颜色")
                            continue
                        
                        # 等待进入子颜色区域
                        time.sleep(0.5)
                        
                        # 3. 收集子颜色区域的颜色
                        child_colors = self._collect_child_colors()
                        if child_colors:
                            # 为每个子颜色添加父颜色信息
                            for child_color in child_colors:
                                child_color['parent_color'] = color_info['rgb']
                                child_color['parent_index'] = i
                                child_color['parent'] = f"父颜色{i+1}(RGB{color_info['rgb']})"
                                child_color['is_parent'] = False  # 明确标记为子颜色
                            
                            self.collected_colors.extend(child_colors)
                            logging.info(f"第{i+1}个父颜色收集到{len(child_colors)}种子颜色")
                        else:
                            logging.info(f"第{i+1}个父颜色没有收集到子颜色")
                        
                        # 4. 点击色板返回按钮返回到父颜色区域
                        if self.color_swatch_return_button_pos:
                            # 计算色板返回按钮中心点
                            return_x = self.color_swatch_return_button_pos[0] + self.color_swatch_return_button_pos[2] // 2
                            return_y = self.color_swatch_return_button_pos[1] + self.color_swatch_return_button_pos[3] // 2
                            success = click_position((return_x, return_y))
                            if success:
                                # 等待返回动画完成
                                time.sleep(0.3)
                                logging.info(f"第{i+1}个父颜色处理完成，已返回父颜色区域")
                            else:
                                logging.warning(f"点击色板返回按钮失败")
                        else:
                            logging.warning("色板返回按钮位置未设置")
                    
                    else:
                        logging.warning("色盘按钮位置未设置，无法进入子颜色区域")
                    
                except Exception as e:
                    logging.error(f"处理第{i+1}个父颜色时发生错误: {e}")
                    continue
            
            # 同时收集父颜色信息，用于绘图时的导航
            parent_colors = self._analyze_parent_color_area()
            if parent_colors:
                # 为父颜色添加标记和索引
                for i, parent_color in enumerate(parent_colors):
                    parent_color['is_parent'] = True
                    parent_color['parent_index'] = i
                    parent_color['parent'] = f"父颜色{i+1}(RGB{parent_color['rgb']})"
                
                # 将父颜色添加到收集结果中（用于导航，不用于绘图）
                self.collected_colors.extend(parent_colors)
                logging.info(f"收集到{len(parent_colors)}种父颜色用于导航")
                
                # 重新设置子颜色的父颜色索引，确保与父颜色索引一致
                for child_color in self.collected_colors:
                    if not child_color.get('is_parent', False):
                        # 从父颜色名称中提取索引
                        parent_name = child_color.get('parent', '')
                        if '父颜色' in parent_name:
                            try:
                                # 提取父颜色索引，格式如 "父颜色1(RGB(5, 22, 22))"
                                index_start = parent_name.find('父颜色') + 3
                                index_end = parent_name.find('(', index_start)
                                if index_end > index_start:
                                    parent_index = int(parent_name[index_start:index_end]) - 1  # 转换为0基索引
                                    child_color['parent_index'] = parent_index
                                    logging.debug(f"设置子颜色 RGB{child_color['rgb']} 的父颜色索引为: {parent_index}")
                            except (ValueError, IndexError) as e:
                                logging.warning(f"无法从父颜色名称提取索引: {parent_name}, 错误: {e}")
                                # 使用默认索引0
                                child_color['parent_index'] = 0
                        else:
                            # 如果没有父颜色名称，使用默认索引0
                            child_color['parent_index'] = 0
            
            # 去重处理
            unique_colors = self._deduplicate_colors(self.collected_colors)
            
            # 更新收集结果
            self.collected_colors = unique_colors
            
            # 发送收集完成信号
            self.colors_collected.emit(unique_colors)
            
            # 添加详细的调试信息
            logging.info(f"=== 颜色收集完成调试信息 ===")
            logging.info(f"总颜色数量: {len(unique_colors)}")
            
            # 统计父颜色和子颜色
            parent_colors = [c for c in unique_colors if c.get('is_parent', False)]
            child_colors = [c for c in unique_colors if not c.get('is_parent', False)]
            logging.info(f"父颜色数量: {len(parent_colors)}, 子颜色数量: {len(child_colors)}")
            
            # 显示父颜色信息
            for i, parent_color in enumerate(parent_colors):
                logging.info(f"父颜色{i}: RGB{parent_color['rgb']}, 索引: {parent_color.get('parent_index')}, 名称: {parent_color.get('parent')}")
            
            # 检查子颜色的父索引分布
            if child_colors:
                parent_indices = [c.get('parent_index') for c in child_colors if c.get('parent_index') is not None]
                if parent_indices:
                    logging.info(f"子颜色使用的父索引: {sorted(set(parent_indices))}")
                    logging.info(f"父索引范围: {min(parent_indices)} - {max(parent_indices)}")
            
            logging.info(f"=== 调试信息结束 ===")
            
            self.status_updated.emit(f"颜色收集完成，共{len(unique_colors)}种子级颜色")
            logging.info(f"颜色收集完成，共{len(unique_colors)}种子级颜色")
            
            return True
            
        except Exception as e:
            logging.error(f"收集颜色失败: {e}")
            self.status_updated.emit(f"收集颜色失败: {str(e)}")
            return False
    
    def _check_color_collection_ready(self):
        """检查颜色收集是否准备就绪"""
        missing = []
        
        if not self.parent_color_area_pos:
            missing.append("父颜色区域")
        if not self.color_palette_button_pos:
            missing.append("色盘按钮")
        if not self.color_swatch_return_button_pos:
            missing.append("色板返回按钮")
        if not self.child_color_area_pos:
            missing.append("子颜色区域")
        if not self.background_color_button_pos:
            missing.append("背景色按钮")
        
        if missing:
            self.status_updated.emit(f"请先设置: {', '.join(missing)}")
            return False
        
        return True
    
    def _analyze_parent_color_area(self):
        """分析父颜色区域，获取颜色按钮信息（不收集颜色）"""
        try:
            colors = []
            
            # 分析父颜色区域（2列×8行）
            screenshot = ImageGrab.grab()
            
            # 计算每个颜色按钮的大小和位置
            area_width = self.parent_color_area_pos[2]
            area_height = self.parent_color_area_pos[3]
            
            # 2列8行布局
            button_width = area_width // 2
            button_height = area_height // 8
            
            for row in range(8):
                for col in range(2):
                    # 计算按钮中心点
                    center_x = self.parent_color_area_pos[0] + col * button_width + button_width // 2
                    center_y = self.parent_color_area_pos[1] + row * button_height + button_height // 2
                    
                    # 获取颜色
                    color = screenshot.getpixel((center_x, center_y))
                    
                    # 如果是RGBA格式，转换为RGB
                    if len(color) == 4:
                        color = color[:3]
                    
                    # 检查是否为背景色（跳过）
                    if self._is_background_color(color):
                        continue
                    
                    # 记录颜色信息
                    color_info = {
                        'rgb': color,
                        'position': (center_x, center_y),
                        'parent': '父颜色区域',
                        'row': row,
                        'col': col
                    }
                    
                    colors.append(color_info)
            
            return colors
            
        except Exception as e:
            logging.error(f"分析父颜色区域失败: {e}")
            return []
    
    def _collect_parent_colors(self):
        """收集父颜色区域的颜色（兼容性方法）"""
        return self._analyze_parent_color_area()
    
    def _collect_child_colors(self):
        """收集子颜色区域的颜色"""
        try:
            colors = []
            
            # 分析子颜色区域（2列×最多5行）
            screenshot = ImageGrab.grab()
            
            # 计算每个颜色按钮的大小和位置
            area_width = self.child_color_area_pos[2]
            area_height = self.child_color_area_pos[3]
            
            # 2列最多5行布局
            button_width = area_width // 2
            button_height = area_height // 5
            
            for row in range(5):
                for col in range(2):
                    # 计算按钮中心点
                    center_x = self.child_color_area_pos[0] + col * button_width + button_width // 2
                    center_y = self.child_color_area_pos[1] + row * button_height + button_height // 2
                    
                    # 获取颜色
                    color = screenshot.getpixel((center_x, center_y))
                    
                    # 如果是RGBA格式，转换为RGB
                    if len(color) == 4:
                        color = color[:3]
                    
                    # 检查是否为背景色（跳过）
                    if self._is_background_color(color):
                        continue
                    
                    # 记录颜色信息
                    color_info = {
                        'rgb': color,
                        'position': (center_x, center_y),
                        'parent': '子颜色区域',
                        'row': row,
                        'col': col
                    }
                    
                    colors.append(color_info)
            
            # 注意：色板返回按钮的点击现在在 collect_colors 方法中处理
            
            return colors
            
        except Exception as e:
            logging.error(f"收集子颜色区域颜色失败: {e}")
            return []
    
    def _is_background_color(self, color):
        """判断是否为背景色"""
        try:
            if not self.background_color_button_pos:
                return False
            
            # 截取当前屏幕
            screenshot = ImageGrab.grab()
            
            # 计算背景色按钮中心点
            center_x = self.background_color_button_pos[0] + self.background_color_button_pos[2] // 2
            center_y = self.background_color_button_pos[1] + self.background_color_button_pos[3] // 2
            
            # 获取背景色
            bg_color = screenshot.getpixel((center_x, center_y))
            
            # 如果是RGBA格式，转换为RGB
            if len(bg_color) == 4:
                bg_color = bg_color[:3]
            
            # 计算颜色差异（简单的欧几里得距离）
            diff = sum((c1 - c2) ** 2 for c1, c2 in zip(color, bg_color)) ** 0.5
            
            # 如果差异小于阈值，认为是背景色
            threshold = 30  # 可以调整这个阈值
            return diff < threshold
            
        except Exception as e:
            logging.error(f"判断背景色失败: {e}")
            return False
    
    def _deduplicate_colors(self, colors):
        """对颜色进行去重处理"""
        try:
            # 分别处理父颜色和子颜色
            parent_colors = [c for c in colors if c.get('is_parent', False)]
            child_colors = [c for c in colors if not c.get('is_parent', False)]
            
            logging.debug(f"去重前: 父颜色{len(parent_colors)}个, 子颜色{len(child_colors)}个")
            
            # 父颜色去重（使用RGB值）- 父颜色主要用于导航，可以安全去重
            unique_parent_colors = []
            seen_parent_colors = set()
            for color_info in parent_colors:
                color_key = tuple(color_info['rgb'])
                if color_key not in seen_parent_colors:
                    seen_parent_colors.add(color_key)
                    unique_parent_colors.append(color_info)
            
            # 子颜色不去重 - 保留所有子颜色用于绘图
            # 因为即使RGB值相同，位置可能不同，绘图时需要所有位置
            unique_child_colors = child_colors.copy()
            
            logging.debug(f"去重后: 父颜色{len(unique_parent_colors)}个, 子颜色{len(unique_child_colors)}个, 总计{len(unique_parent_colors) + len(unique_child_colors)}个")
            
            # 合并结果：父颜色在前，子颜色在后
            unique_colors = unique_parent_colors + unique_child_colors
            
            logging.info(f"颜色去重完成: {len(colors)} -> {len(unique_colors)} (父颜色: {len(unique_parent_colors)}, 子颜色: {len(unique_child_colors)})")
            return unique_colors
                
        except Exception as e:
            logging.error(f"颜色去重失败: {e}")
            return colors
    
    def get_collected_colors(self):
        """获取收集到的颜色"""
        # 添加调试日志
        total_colors = len(self.collected_colors)
        parent_colors = [c for c in self.collected_colors if c.get('is_parent', False)]
        child_colors = [c for c in self.collected_colors if not c.get('is_parent', False)]
        
        logging.info(f"=== get_collected_colors 调用 ===")
        logging.info(f"总颜色数量: {total_colors}")
        logging.info(f"父颜色数量: {len(parent_colors)}")
        logging.info(f"子颜色数量: {len(child_colors)}")
        
        # 显示前几个颜色的详细信息
        for i, color in enumerate(self.collected_colors[:5]):
            color_type = "父颜色" if color.get('is_parent', False) else "子颜色"
            parent_idx = color.get('parent_index', '无')
            parent_name = color.get('parent', '无')
            logging.info(f"颜色{i}: {color_type}, RGB{color['rgb']}, 父索引: {parent_idx}, 父名称: {parent_name}")
        
        logging.info(f"=== get_collected_colors 结束 ===")
        
        return self.collected_colors.copy()
    
    def clear_collected_colors(self):
        """清理所有已收集的颜色"""
        try:
            with self._state_lock:
                # 清空收集的颜色
                self.collected_colors = []
                
                # 清空像素化图片和像素信息
                self.pixelized_image = None
                self.pixel_info_list = []
                
                # 发送状态更新
                self.status_updated.emit("已清理所有收集到的颜色")
                logging.info("已清理所有收集到的颜色")
                
                # 发送颜色收集信号（空列表）
                self.colors_collected.emit([])
                
                return True
                
        except Exception as e:
            error_msg = f"清理颜色失败: {e}"
            logging.error(error_msg)
            self.status_updated.emit(error_msg)
            return False
    
    def set_color_area(self, position):
        """设置颜色区域（兼容性方法，现在使用父颜色区域）"""
        self.set_parent_color_area(position)
    
    def _analyze_color_area(self):
        """分析颜色区域，提取颜色调色板（兼容性方法）"""
        # 现在使用收集到的颜色，不再需要这个方法
        pass
    
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
    
    def process_image(self, aspect_ratio, size_text):
        """处理图片，进行像素化"""
        try:
            if not self.selected_image_path:
                self.status_updated.emit("请先选择图片")
                return False
            
            if not self.collected_colors:
                self.status_updated.emit("请先收集颜色以获取颜色调色板")
                return False
            
            self.status_updated.emit("正在处理图片...")
            

            size_match = re.search(r'(\d+)个格子', size_text)
            if size_match:
                grid_count = int(size_match.group(1))
            else:
                self.status_updated.emit(f"无效的尺寸格式: {size_text}")
                return False
            
            # 使用格子数量作为像素数（简化逻辑）
            pixel_count = grid_count
            
            # 从收集到的颜色中提取RGB值作为调色板
            # 重要：只使用子级颜色，过滤掉父级颜色
            child_colors = [color_info for color_info in self.collected_colors if not color_info.get('is_parent', False)]
            
            if not child_colors:
                self.status_updated.emit("没有收集到子级颜色，无法处理图片")
                logging.error("没有收集到子级颜色，无法处理图片")
                return False
            
            color_palette = [color_info['rgb'] for color_info in child_colors]
            
            logging.info(f"使用{len(color_palette)}种子级颜色进行图片处理")
            self.status_updated.emit(f"使用{len(color_palette)}种子级颜色进行图片处理")
            
            # 像素化图片
            self.pixelized_image = self.image_processor.pixelize_image(
                self.selected_image_path, 
                pixel_count, 
                pixel_count,  # 使用相同的值作为高度（保持向后兼容）
                color_palette
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
    
    def process_image_with_dimensions(self, aspect_ratio, size_text, width, height):
        """使用具体尺寸处理图片，进行像素化"""
        try:
            if not self.selected_image_path:
                self.status_updated.emit("请先选择图片")
                return False
            
            if not self.collected_colors:
                self.status_updated.emit("请先收集颜色以获取颜色调色板")
                return False
            
            self.status_updated.emit(f"正在处理图片，目标尺寸: {width}×{height}...")
            
            # 直接使用传入的width和height
            target_width = width
            target_height = height
            
            logging.info(f"使用配置的尺寸: {target_width}×{target_height}")
            
            # 从收集到的颜色中提取RGB值作为调色板
            # 重要：只使用子级颜色，过滤掉父级颜色
            child_colors = [color_info for color_info in self.collected_colors if not color_info.get('is_parent', False)]
            
            if not child_colors:
                self.status_updated.emit("没有收集到子级颜色，无法处理图片")
                logging.error("没有收集到子级颜色，无法处理图片")
                return False
            
            color_palette = [color_info['rgb'] for color_info in child_colors]
            
            logging.info(f"使用{len(color_palette)}种子级颜色进行图片处理")
            
            # 调用图片处理器进行像素化
            pixelized_image = self.image_processor.pixelize_image(
                self.selected_image_path, 
                target_width,  # 使用配置的宽度
                target_height,  # 使用配置的高度
                color_palette
            )
            
            if not pixelized_image:
                self.status_updated.emit("图片像素化失败")
                return False
            
            # 保存像素化图片
            self.pixelized_image = pixelized_image
            
            # 生成像素信息列表（如果绘画区域已设置）
            if self.draw_area_pos:
                draw_area_size = (self.draw_area_pos[2], self.draw_area_pos[3])
                pixel_image_size = pixelized_image.size
                pixel_size = self.image_processor.calculate_pixel_size(draw_area_size, pixel_image_size)
                
                # 获取像素位置信息
                self.pixel_info_list = self.image_processor.get_pixel_positions(
                    self.draw_area_pos, 
                    pixelized_image, 
                    pixel_size
                )
            else:
                self.pixel_info_list = []
            
            # 发送处理完成信号
            self.image_processed.emit(pixelized_image)
            
            # 如果绘画区域已设置，计算像素位置信息
            if self.draw_area_pos:
                self._calculate_pixel_positions()
            
            logging.info(f"图片处理完成，实际尺寸: {pixelized_image.size}")
            self.status_updated.emit(f"图片处理完成，尺寸: {target_width}×{target_height}")
            return True
            
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
    
    def _get_color_position(self, color_index):
        """获取颜色在收集的颜色中的位置"""
        try:
            if not self.collected_colors or color_index >= len(self.collected_colors):
                return None
            
            # 直接从收集的颜色信息中获取位置
            color_info = self.collected_colors[color_index]
            return color_info['position']
            
        except Exception as e:
            logging.error(f"获取颜色位置失败: {e}")
            return None
    
    def get_draw_area_position(self):
        """获取绘画区域位置"""
        return self.draw_area_pos
    
    def get_color_area_position(self):
        """获取颜色区域位置（兼容性方法，返回父颜色区域）"""
        return self.parent_color_area_pos
    
    def get_color_palette_button_position(self):
        """获取色盘按钮位置"""
        return self.color_palette_button_pos
    
    def get_color_swatch_return_button_position(self):
        """获取色板返回按钮位置"""
        return self.color_swatch_return_button_pos
    
    def get_child_color_area_position(self):
        """获取子颜色区域位置"""
        return self.child_color_area_pos
    
    def get_background_color_button_position(self):
        """获取背景色按钮位置"""
        return self.background_color_button_pos
    
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
        draw_area_ready = self.draw_area_pos is not None
        
        # 重要：只检查子级颜色，不检查父级颜色
        child_colors = [color_info for color_info in self.collected_colors if not color_info.get('is_parent', False)]
        colors_ready = len(child_colors) > 0
        
        image_ready = self.pixelized_image is not None
        pixel_info_ready = len(self.pixel_info_list) > 0
        
        logging.debug(f"绘图准备检查:")
        logging.debug(f"  - 绘画区域: {draw_area_ready} ({self.draw_area_pos})")
        logging.debug(f"  - 子级颜色收集: {colors_ready} ({len(child_colors)} 种子级颜色，总共{len(self.collected_colors)}种颜色)")
        logging.debug(f"  - 像素化图片: {image_ready} ({self.pixelized_image is not None})")
        logging.debug(f"  - 像素信息: {pixel_info_ready} ({len(self.pixel_info_list)} 个)")
        
        result = (draw_area_ready and colors_ready and image_ready and pixel_info_ready)
        logging.debug(f"绘图准备检查结果: {result}")
        
        if not colors_ready:
            logging.warning("绘图准备失败：没有收集到子级颜色")
        
        return result
    
    def get_aspect_ratio_and_size(self):
        """获取比例和尺寸配置"""
        return getattr(self, 'aspect_ratio_and_size', None)
    
    def save_config(self, config_name, aspect_ratio_and_size=None):
        """保存配置"""
        try:
            config_data = {
                # 区域位置配置
                'draw_area_pos': self.draw_area_pos,
                'parent_color_area_pos': self.parent_color_area_pos,
                'color_palette_button_pos': self.color_palette_button_pos,
                'color_swatch_return_button_pos': self.color_swatch_return_button_pos,
                'child_color_area_pos': self.child_color_area_pos,
                'background_color_button_pos': self.background_color_button_pos,
                
                # 延迟配置
                'color_click_delay': self.color_click_delay,
                'draw_click_delay': self.draw_click_delay,
                'mouse_move_delay': self.mouse_move_delay,
                
                # 收集到的颜色信息
                'collected_colors': self.collected_colors,
                
                # 图片比例和尺寸配置
                'aspect_ratio_and_size': aspect_ratio_and_size,
                
                # 注意：不保存图片路径和像素化图片，避免配置文件过大和路径依赖问题
                # 'selected_image_path': self.selected_image_path,  # 已移除
                
                # 时间戳
                'save_time': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            success = self.config_manager.save_config(config_name, config_data)
            if success:
                self.status_updated.emit(f"配置 '{config_name}' 保存成功")
                logging.info(f"配置 '{config_name}' 保存成功")
            else:
                self.status_updated.emit(f"配置 '{config_name}' 保存失败")
                logging.error(f"配置 '{config_name}' 保存失败")
            
            return success
            
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            self.status_updated.emit(f"保存配置失败: {str(e)}")
            return False
    
    def load_config(self, config_name):
        """加载配置"""
        try:
            config_data = self.config_manager.load_config(config_name)
            if not config_data:
                self.status_updated.emit(f"配置 '{config_name}' 加载失败")
                return False
            
            # 恢复区域位置配置
            if config_data.get('draw_area_pos'):
                self.draw_area_pos = tuple(config_data['draw_area_pos'])
            
            if config_data.get('parent_color_area_pos'):
                self.parent_color_area_pos = tuple(config_data['parent_color_area_pos'])
            
            if config_data.get('color_palette_button_pos'):
                self.color_palette_button_pos = tuple(config_data['color_palette_button_pos'])
            
            if config_data.get('color_swatch_return_button_pos'):
                self.color_swatch_return_button_pos = tuple(config_data['color_swatch_return_button_pos'])
            
            if config_data.get('child_color_area_pos'):
                self.child_color_area_pos = tuple(config_data['child_color_area_pos'])
            
            if config_data.get('background_color_button_pos'):
                self.background_color_button_pos = tuple(config_data['background_color_button_pos'])
            
            # 恢复延迟配置
            if config_data.get('color_click_delay'):
                self.color_click_delay = config_data['color_click_delay']
            
            if config_data.get('draw_click_delay'):
                self.draw_click_delay = config_data['draw_click_delay']
            
            if config_data.get('mouse_move_delay'):
                self.mouse_move_delay = config_data['mouse_move_delay']
            
            # 恢复收集到的颜色信息
            if config_data.get('collected_colors'):
                self.collected_colors = config_data['collected_colors']
            
            # 恢复图片比例和尺寸配置
            aspect_ratio_and_size = config_data.get('aspect_ratio_and_size')
            if aspect_ratio_and_size:
                self.aspect_ratio_and_size = aspect_ratio_and_size
            else:
                self.aspect_ratio_and_size = None
            
            # 注意：不再从配置中恢复图片路径，用户需要重新选择图片
            # if config_data.get('selected_image_path'):
            #     self.selected_image_path = config_data['selected_image_path']  # 已移除
            
            # 清空图片相关状态，确保用户重新选择图片
            self.selected_image_path = None
            self.pixelized_image = None
            self.pixel_info_list = []
            

            
            self.status_updated.emit(f"配置 '{config_name}' 加载成功")
            logging.info(f"配置 '{config_name}' 加载成功")
            return True
            
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            self.status_updated.emit(f"加载配置失败: {str(e)}")
            return False
    
    def delete_config(self, config_name):
        """删除配置"""
        try:
            success = self.config_manager.delete_config(config_name)
            if success:
                self.status_updated.emit(f"配置 '{config_name}' 删除成功")
                logging.info(f"配置 '{config_name}' 删除成功")
            else:
                self.status_updated.emit(f"配置 '{config_name}' 删除失败")
                logging.error(f"配置 '{config_name}' 删除失败")
            
            return success
            
        except Exception as e:
            logging.error(f"删除配置失败: {e}")
            self.status_updated.emit(f"删除配置失败: {str(e)}")
            return False
    
    def get_config_list(self):
        """获取配置列表"""
        try:
            return self.config_manager.get_config_list()
        except Exception as e:
            logging.error(f"获取配置列表失败: {e}")
            return []
    
    def config_exists(self, config_name):
        """检查配置是否存在"""
        try:
            return self.config_manager.config_exists(config_name)
        except Exception as e:
            logging.error(f"检查配置是否存在失败: {e}")
            return False
