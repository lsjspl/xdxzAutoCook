#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
绘图助手主程序
从钓鱼助手改造而来，实现自动绘图功能
"""

import sys
import os
import logging
import traceback
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import QObject

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import isAdmin

# 导入绘图模块
from paint_ui import PaintMainUI, setup_logging
from paint_business import PaintBusiness
from paint_worker import DrawingWorker, HotkeyWorker


class PaintAppController(QObject):
    """绘图助手控制器，协调UI、业务逻辑和工作线程"""
    
    def __init__(self):
        super().__init__()
        
        # 确保日志系统已初始化
        setup_logging()
        
        # 初始化日志
        logging.info("绘图助手控制器初始化开始")
        
        # 创建业务逻辑实例
        self.business = PaintBusiness()
        
        # 创建UI实例
        self.ui = PaintMainUI()
        
        # 工作线程
        self.drawing_worker = None
        self.click_worker = None
        self.capture_worker = None
        self.hotkey_worker = None
        
        # 连接信号
        self._connect_ui_signals()
        self._connect_business_signals()
        self._setup_hotkeys()
        
        # 初始化配置系统
        self._initialize_config_system()
        
        # 不自动检测游戏窗口，由用户通过checkbox控制
        
        logging.info("绘图助手控制器初始化完成")
    
    def _connect_ui_signals(self):
        """连接UI信号与业务逻辑"""
        # UI -> 控制器
        self.ui.select_draw_area_requested.connect(self._on_select_draw_area)
        self.ui.select_parent_color_area_requested.connect(self._on_select_parent_color_area)
        self.ui.select_color_palette_button_requested.connect(self._on_select_color_palette_button)
        self.ui.select_color_swatch_return_button_requested.connect(self._on_select_color_swatch_return_button)
        self.ui.select_child_color_area_requested.connect(self._on_select_child_color_area)
        self.ui.select_background_color_button_requested.connect(self._on_select_background_color_button)
        self.ui.collect_colors_requested.connect(self._on_collect_colors)
        self.ui.select_image_requested.connect(self._on_select_image)
        self.ui.process_image_requested.connect(self._on_process_image)
        self.ui.start_drawing_requested.connect(self._on_start_drawing)
        self.ui.stop_drawing_requested.connect(self._on_stop_drawing)
        self.ui.clear_colors_requested.connect(self._on_clear_colors)
        
        # 配置管理信号连接
        self.ui.save_config_requested.connect(self._on_save_config)
        self.ui.load_config_requested.connect(self._on_load_config)
        self.ui.delete_config_requested.connect(self._on_delete_config)
        self.ui.config_changed.connect(self._on_config_changed)
        
        logging.info("UI信号连接完成")
    
    def _connect_business_signals(self):
        """连接业务逻辑信号"""
        # 业务逻辑 -> UI
        self.business.status_updated.connect(self.ui.update_status_text)
        self.business.image_processed.connect(self.ui.display_pixelized_image)
        self.business.drawing_progress.connect(self.ui.update_drawing_progress)
        self.business.drawing_completed.connect(self._on_drawing_completed)
        self.business.colors_collected.connect(self.ui.set_collected_colors)
        self.business.game_window_position_updated.connect(self.ui.show_game_window_position)
        
        logging.info("业务逻辑信号连接完成")
    
    def _setup_hotkeys(self):
        """设置全局热键"""
        try:
            self.hotkey_worker = HotkeyWorker()
            self.hotkey_worker.hotkey_pressed.connect(self._on_hotkey_pressed)
            self.hotkey_worker.start()
            logging.info("全局热键设置成功")
        except Exception as e:
            logging.error(f"设置全局热键失败: {e}")
    
    def _on_hotkey_pressed(self, key):
        """处理热键按下事件"""
        if key == 'p':
            logging.info("检测到全局P键按下，停止绘图")
            self._on_stop_drawing()
    
    def _on_select_draw_area(self):
        """处理选择绘画区域请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_draw_area(position)
                    self.ui.set_draw_area(position)  # 同时更新UI状态
                    logging.info(f"绘画区域已设置: {position}")
                else:
                    self.ui.update_status_text("绘画区域选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请框选绘画区域...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择绘画区域失败: {e}")
            self.ui.update_status_text(f"选择绘画区域失败: {str(e)}")
    
    def _on_select_parent_color_area(self):
        """处理选择父颜色区域请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_parent_color_area(position)
                    self.ui.set_parent_color_area(position)  # 同时更新UI状态
                    logging.info(f"父颜色区域已设置: {position}")
                else:
                    self.ui.update_status_text("父颜色区域选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请框选父颜色区域（2列×8行颜色块）...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择父颜色区域失败: {e}")
            self.ui.update_status_text(f"选择父颜色区域失败: {str(e)}")
    
    def _on_select_color_palette_button(self):
        """处理选择色盘按钮请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_color_palette_button(position)
                    self.ui.set_color_palette_button(position)  # 同时更新UI状态
                    logging.info(f"色盘按钮已设置: {position}")
                else:
                    self.ui.update_status_text("色盘按钮选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请点选色盘按钮...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择色盘按钮失败: {e}")
            self.ui.update_status_text(f"选择色盘按钮失败: {str(e)}")
    
    def _on_select_color_swatch_return_button(self):
        """处理选择色板返回按钮请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_color_swatch_return_button(position)
                    self.ui.set_color_swatch_return_button(position)  # 同时更新UI状态
                    logging.info(f"色板返回按钮已设置: {position}")
                else:
                    self.ui.update_status_text("色板返回按钮选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请点选色板返回按钮...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择色板返回按钮失败: {e}")
            self.ui.update_status_text(f"选择色板返回按钮失败: {str(e)}")
    
    def _on_select_child_color_area(self):
        """处理选择子颜色区域请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_child_color_area(position)
                    self.ui.set_child_color_area(position)  # 同时更新UI状态
                    logging.info(f"子颜色区域已设置: {position}")
                else:
                    self.ui.update_status_text("子颜色区域选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请框选子颜色区域（2列×最多5行颜色块）...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择子颜色区域失败: {e}")
            self.ui.update_status_text(f"选择子颜色区域失败: {str(e)}")
    
    def _on_select_background_color_button(self):
        """处理选择背景色按钮请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_background_color_button(position)
                    self.ui.set_background_color_button(position)  # 同时更新UI状态
                    logging.info(f"背景色按钮已设置: {position}")
                else:
                    self.ui.update_status_text("背景色按钮选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请点选背景色按钮...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择背景色按钮失败: {e}")
            self.ui.update_status_text(f"选择背景色按钮失败: {str(e)}")
    
    def _on_collect_colors(self):
        """处理收集颜色请求"""
        try:
            success = self.business.collect_colors()
            if success:
                # 收集完成后，启用收集颜色按钮
                self.ui.collect_colors_btn.setEnabled(True)
                # 检查是否可以开始绘图
                self._check_drawing_ready()
            else:
                self.ui.update_status_text("颜色收集失败，请检查设置")
                
        except Exception as e:
            logging.error(f"收集颜色失败: {e}")
            self.ui.update_status_text(f"收集颜色失败: {str(e)}")
    
    def _on_clear_colors(self):
        """处理清理颜色请求"""
        try:
            success = self.business.clear_collected_colors()
            if success:
                # 同时更新UI状态
                self.ui.set_collected_colors([])
                self.ui.update_status_text("已清理所有收集到的颜色")
                logging.info("已清理所有收集到的颜色")
            else:
                self.ui.update_status_text("清理颜色失败")
        except Exception as e:
            logging.error(f"清理颜色失败: {e}")
            self.ui.update_status_text(f"清理颜色失败: {str(e)}")
    
    def _auto_detect_game_window(self):
        """自动检测游戏窗口"""
        try:
            logging.info("开始自动检测游戏窗口...")
            success = self.business.get_game_window_info()
            if success:
                logging.info("游戏窗口自动检测成功")
                self.ui.update_status_text("游戏窗口自动检测成功")
            else:
                logging.warning("游戏窗口自动检测失败，请确保游戏正在运行")
                self.ui.update_status_text("游戏窗口自动检测失败，请确保游戏正在运行")
        except Exception as e:
            logging.error(f"自动检测游戏窗口时发生错误: {e}")
            self.ui.update_status_text(f"自动检测游戏窗口失败: {str(e)}")
    
    def _update_game_window_display(self):
        """更新游戏窗口和绘画区域显示"""
        try:
            # 更新游戏窗口显示（只在checkbox选中时）
            game_window_pos = self.business.get_game_window_position()
            if game_window_pos:
                pos, size = game_window_pos
                self.ui.show_game_window_position(pos, size)
                logging.info(f"游戏窗口显示已更新: 位置{pos}, 大小{size}")
            
            # 更新绘画区域显示（总是显示）
            draw_area_pos = self.business.get_draw_area_position()
            if draw_area_pos:
                self.ui.show_draw_area_position(draw_area_pos[:2], draw_area_pos[2:])
                logging.info(f"绘画区域显示已更新: 位置{draw_area_pos[:2]}, 大小: {draw_area_pos[2:]}")
        except Exception as e:
            logging.error(f"更新游戏窗口和绘画区域显示失败: {e}")
    

    
    def _on_select_image(self):
        """处理选择图片请求"""
        try:
            from PyQt5.QtWidgets import QFileDialog
            
            file_path, _ = QFileDialog.getOpenFileName(
                self.ui,
                "选择图片文件",
                "",
                "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif *.tiff);;所有文件 (*)"
            )
            
            if file_path:
                self.business.set_selected_image(file_path)
                self.ui.set_selected_image(file_path)  # 同时更新UI状态
                logging.info(f"图片已选择: {file_path}")
            else:
                self.ui.update_status_text("图片选择已取消")
                
        except Exception as e:
            logging.error(f"选择图片失败: {e}")
            self.ui.update_status_text(f"选择图片失败: {str(e)}")
    
    def _on_process_image(self, aspect_ratio, pixel_count):
        """处理图片处理请求"""
        try:
            success = self.business.process_image(aspect_ratio, pixel_count)
            if success:
                self.ui.update_status_text("图片处理完成")
                # 检查是否可以开始绘图
                self._check_drawing_ready()
            else:
                self.ui.update_status_text("图片处理失败")
                
        except Exception as e:
            logging.error(f"处理图片失败: {e}")
            self.ui.update_status_text(f"处理图片失败: {str(e)}")
    
    def _on_start_drawing(self):
        """处理开始绘图请求"""
        try:
            logging.info("开始绘图请求被触发")
            
            # 检查是否准备就绪
            ready = self.business.is_ready_to_draw()
            logging.debug(f"业务逻辑检查结果: {ready}")
            
            if not ready:
                missing = []
                draw_area = self.business.get_draw_area_position()
                colors = self.business.get_collected_colors()
                image_path = self.business.get_selected_image_path()
                pixelized = self.business.get_pixelized_image()
                pixel_info = self.business.get_pixel_info_list()
                
                logging.debug(f"检查结果:")
                logging.debug(f"  - 绘画区域: {draw_area}")
                logging.debug(f"  - 颜色数量: {len(colors) if colors else 0}")
                logging.debug(f"  - 图片路径: {image_path}")
                logging.debug(f"  - 像素化图片: {pixelized is not None}")
                logging.debug(f"  - 像素信息: {len(pixel_info) if pixel_info else 0}")
                
                if not draw_area:
                    missing.append("绘画区域")
                if not colors:
                    missing.append("颜色收集")
                if not image_path:
                    missing.append("图片")
                if not pixelized:
                    missing.append("图片处理")
                
                self.ui.update_status_text(f"请先完成: {', '.join(missing)}")
                logging.debug(f"缺少: {', '.join(missing)}")
                return
            
            logging.debug("所有检查通过，准备启动绘图")
            
            # 如果已经在绘图，先停止
            if self.drawing_worker and self.drawing_worker.isRunning():
                logging.debug("检测到正在绘图，先停止")
                self._on_stop_drawing()
                return
            
            # 获取绘图数据
            pixel_info_list = self.business.get_pixel_info_list()
            collected_colors = self.business.get_collected_colors()
            draw_area_pos = self.business.get_draw_area_position()
            
            # 添加调试日志，检查从business获取的颜色数据
            logging.info(f"=== PaintApp 从business获取颜色数据 ===")
            logging.info(f"总颜色数量: {len(collected_colors)}")
            
            # 统计父颜色和子颜色
            parent_colors = [c for c in collected_colors if c.get('is_parent', False)]
            child_colors = [c for c in collected_colors if not c.get('is_parent', False)]
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
            
            # 统计子级颜色数量
            child_colors = [c for c in collected_colors if not c.get('is_parent', False)]
            parent_colors = [c for c in collected_colors if c.get('is_parent', False)]
            
            logging.debug(f"绘图数据:")
            logging.debug(f"  - 像素信息数量: {len(pixel_info_list)}")
            logging.debug(f"  - 总颜色数量: {len(collected_colors)}")
            logging.debug(f"  - 父级颜色数量: {len(parent_colors)}")
            logging.debug(f"  - 子级颜色数量: {len(child_colors)} (将用于绘图)")
            logging.debug(f"  - 绘画区域: {draw_area_pos}")
            
            # 添加详细的调试信息
            logging.info(f"=== PaintApp 绘图启动调试信息 ===")
            logging.info(f"总颜色数量: {len(collected_colors)}")
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
            
            # 显示颜色统计信息给用户
            self.ui.update_status_text(f"准备绘图：共{len(collected_colors)}种颜色，其中{len(child_colors)}种子级颜色将用于绘图")
            
            if not pixel_info_list:
                self.ui.update_status_text("像素信息未准备好，请重新处理图片")
                logging.debug("像素信息未准备好")
                return
            
            if not collected_colors:
                self.ui.update_status_text("颜色未收集，请先收集颜色")
                logging.debug("颜色未收集")
                return
            
            # 获取延迟配置
            delay_settings = self.ui.get_delay_settings()
            logging.debug(f"延迟配置: {delay_settings}")
            
            # 获取按钮位置信息
            palette_button_pos = self.business.get_color_palette_button_position()
            return_button_pos = self.business.get_color_swatch_return_button_position()
            
            logging.debug(f"按钮位置信息:")
            logging.debug(f"  - 色盘按钮: {palette_button_pos}")
            logging.debug(f"  - 返回按钮: {return_button_pos}")
            
            # 创建绘图工作线程
            logging.debug("创建绘图工作线程")
            self.drawing_worker = DrawingWorker(
                pixel_info_list, 
                collected_colors, 
                draw_area_pos,
                palette_button_pos=palette_button_pos,
                return_button_pos=return_button_pos
            )
            
            # 设置延迟配置
            self.drawing_worker.set_click_delays(
                color_delay=delay_settings['color_delay'],
                draw_delay=delay_settings['draw_delay'],
                move_delay=delay_settings['move_delay']
            )
            
            # 连接信号
            self.drawing_worker.progress_updated.connect(self.ui.update_drawing_progress)
            self.drawing_worker.status_updated.connect(self.ui.update_status_text)
            self.drawing_worker.drawing_completed.connect(self._on_drawing_completed)
            self.drawing_worker.drawing_error.connect(self._on_drawing_error)
            
            # 启动绘图
            logging.debug("启动绘图工作线程")
            self.drawing_worker.start()
            
            # 更新UI状态
            self.ui.set_drawing_button_text("停止绘图")
            self.ui.set_drawing_button_enabled(True)
            self.ui.update_status_text(f"绘图已开始！使用{len(child_colors)}种子级颜色进行绘图")
            logging.info(f"绘图已开始，使用{len(child_colors)}种子级颜色")
            logging.debug("绘图启动完成")
            
        except Exception as e:
            logging.error(f"启动绘图失败: {e}")
            import traceback
            traceback.print_exc()
            self.ui.update_status_text(f"启动绘图失败: {str(e)}")
    
    def _on_stop_drawing(self):
        """处理停止绘图请求"""
        try:
            if self.drawing_worker and self.drawing_worker.isRunning():
                self.drawing_worker.stop_drawing()
                self.drawing_worker.wait(3000)  # 等待最多3秒
                
                if self.drawing_worker.isRunning():
                    self.drawing_worker.terminate()
                    self.drawing_worker.wait(1000)
                
                self.drawing_worker = None
            
            # 重置绘图状态，清理像素信息以避免下次绘图时出现问题
            self._reset_drawing_state()
            
            # 更新UI状态
            self.ui.set_drawing_button_text("开始绘图")
            self.ui.set_drawing_button_enabled(True)
            self.ui.update_status_text("绘图已停止，如需继续绘图请重新处理图片")
            logging.info("绘图已停止")
            
        except Exception as e:
            logging.error(f"停止绘图失败: {e}")
            self.ui.update_status_text(f"停止绘图失败: {str(e)}")
    
    def _on_drawing_completed(self):
        """处理绘图完成"""
        try:
            # 更新UI状态
            self.ui.set_drawing_button_text("开始绘图")
            self.ui.set_drawing_button_enabled(True)
            self.ui.update_status_text("绘图完成！")
            
            # 清理工作线程
            if self.drawing_worker:
                self.drawing_worker = None
            
            # 重置绘图状态，清理像素信息以避免第二次绘图时出现问题
            self._reset_drawing_state()
            
            logging.info("绘图完成")
            
            # 显示完成消息
            QMessageBox.information(self.ui, "绘图完成", "绘图任务已完成！")
            
        except Exception as e:
            logging.error(f"处理绘图完成失败: {e}")
    
    def _on_drawing_error(self, error_msg):
        """处理绘图错误"""
        try:
            # 更新UI状态
            self.ui.set_drawing_button_text("开始绘图")
            self.ui.set_drawing_button_enabled(True)
            self.ui.update_status_text(f"绘图错误: {error_msg}")
            
            # 清理工作线程
            if self.drawing_worker:
                self.drawing_worker = None
            
            # 重置绘图状态，清理像素信息以避免下次绘图时出现问题
            self._reset_drawing_state()
            
            logging.error(f"绘图错误: {error_msg}")
            
            # 显示错误消息
            QMessageBox.critical(self.ui, "绘图错误", f"绘图过程中发生错误:\n{error_msg}")
            
        except Exception as e:
            logging.error(f"处理绘图错误失败: {e}")
    
    def _check_drawing_ready(self):
        """检查是否可以开始绘图"""
        try:
            if self.business.is_ready_to_draw():
                self.ui.set_drawing_button_enabled(True)
                self.ui.update_status_text("已准备就绪，可以开始绘图")
            else:
                self.ui.set_drawing_button_enabled(False)
                missing = []
                if not self.business.get_draw_area_position():
                    missing.append("绘画区域")
                if not self.business.get_collected_colors():
                    missing.append("颜色收集")
                if not self.business.get_selected_image_path():
                    missing.append("图片选择")
                if not self.business.get_pixelized_image():
                    missing.append("图片处理")
                
                self.ui.update_status_text(f"请先完成: {', '.join(missing)}")
                
        except Exception as e:
            logging.error(f"检查绘图就绪状态失败: {e}")
    
    def _reset_drawing_state(self):
        """重置绘图状态，清理可能导致第二次绘图问题的数据"""
        try:
            # 清理业务逻辑中的像素信息，避免第二次绘图时使用旧数据
            if hasattr(self.business, 'pixel_info_list'):
                self.business.pixel_info_list = []
                logging.info("已清理像素信息列表，准备下次绘图")
            
            # 清理像素化图片，强制重新处理
            if hasattr(self.business, 'pixelized_image'):
                self.business.pixelized_image = None
                logging.info("已清理像素化图片，需要重新处理图片")
            
            # 更新UI状态，提示用户需要重新处理图片
            self.ui.update_status_text("绘图完成！如需继续绘图，请重新处理图片")
            
        except Exception as e:
            logging.error(f"重置绘图状态失败: {e}")
    
    # 配置管理方法
    def _on_save_config(self):
        """处理保存配置请求"""
        try:
            config_name = self.ui.get_current_config_name()
            
            # 验证配置名称
            is_valid, error_msg = self.ui.validate_config_name(config_name)
            if not is_valid:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.ui, '保存配置', error_msg)
                return
            
            # 保存配置
            success = self.business.save_config(config_name)
            if success:
                # 保存完成后重新加载配置列表
                self._load_config_list()
                # 确保新配置显示在下拉框中
                self.ui.add_new_config(config_name)
                # 清空配置名称输入框
                self.ui.clear_config_name()
            else:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.ui, '保存配置', '配置保存失败，请检查设置')
                
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            self.ui.update_status_text(f"保存配置失败: {str(e)}")
    
    def _on_load_config(self):
        """处理加载配置请求"""
        try:
            config_name = self.ui.config_combo.currentText()
            if not config_name:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.ui, '加载配置', '请选择要加载的配置')
                return
            
            # 加载配置
            success = self.business.load_config(config_name)
            if success:
                # 更新UI状态
                self._update_ui_from_config()
                # 设置配置名称到输入框
                self.ui.set_config_name(config_name)
                # 更新游戏窗口显示
                self._update_game_window_display()
            else:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.ui, '加载配置', '配置加载失败，请检查配置文件')
                
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            self.ui.update_status_text(f"加载配置失败: {str(e)}")
    
    def _on_delete_config(self):
        """处理删除配置请求"""
        try:
            config_name = self.ui.config_combo.currentText()
            if not config_name:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.ui, '删除配置', '请选择要删除的配置')
                return
            
            # 确认删除
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.ui, 
                '确认删除', 
                f'确定要删除配置 "{config_name}" 吗？\n此操作不可恢复！',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 删除配置
                success = self.business.delete_config(config_name)
                if success:
                    # 删除完成后重新加载配置列表
                    self._load_config_list()
                    # 清空配置名称输入框
                    self.ui.clear_config_name()
                else:
                    QMessageBox.warning(self.ui, '删除配置', '配置删除失败')
                
        except Exception as e:
            logging.error(f"删除配置失败: {e}")
            self.ui.update_status_text(f"删除配置失败: {str(e)}")
    
    def _on_config_changed(self, config_name):
        """处理配置改变事件"""
        try:
            if config_name:
                # 可以在这里添加配置改变时的处理逻辑
                logging.debug(f"配置改变: {config_name}")
        except Exception as e:
            logging.error(f"处理配置改变事件失败: {e}")
    
    def _load_config_list(self):
        """加载配置列表"""
        try:
            configs = self.business.get_config_list()
            self.ui.update_config_combo(configs)
            logging.info(f"配置列表加载完成，共{len(configs)}个配置")
        except Exception as e:
            logging.error(f"加载配置列表失败: {e}")
    
    def _update_ui_from_config(self):
        """从配置更新UI状态"""
        try:
            # 更新绘画区域状态
            draw_area_pos = self.business.get_draw_area_position()
            if draw_area_pos:
                self.ui.set_draw_area(draw_area_pos)
            
            # 更新父颜色区域状态
            parent_color_area_pos = self.business.get_color_area_position()
            if parent_color_area_pos:
                self.ui.set_parent_color_area(parent_color_area_pos)
            
            # 更新其他区域状态
            color_palette_button_pos = self.business.get_color_palette_button_position()
            if color_palette_button_pos:
                self.ui.set_color_palette_button(color_palette_button_pos)
            
            color_swatch_return_button_pos = self.business.get_color_swatch_return_button_position()
            if color_swatch_return_button_pos:
                self.ui.set_color_swatch_return_button(color_swatch_return_button_pos)
            
            child_color_area_pos = self.business.get_child_color_area_position()
            if child_color_area_pos:
                self.ui.set_child_color_area(child_color_area_pos)
            
            background_color_button_pos = self.business.get_background_color_button_position()
            if background_color_button_pos:
                self.ui.set_background_color_button(background_color_button_pos)
            
            # 更新收集到的颜色显示
            collected_colors = self.business.get_collected_colors()
            if collected_colors:
                self.ui.set_collected_colors(collected_colors)
            
            # 注意：不再从配置中恢复图片路径，用户需要重新选择图片
            # selected_image_path = self.business.get_selected_image_path()
            # if selected_image_path:
            #     self.ui.set_selected_image(selected_image_path)  # 已移除
            
            # 清空UI中的图片显示，确保用户重新选择图片
            self.ui.set_selected_image(None)
            
            # 更新游戏窗口和绘画区域显示
            self._update_game_window_display()
            
            logging.info("UI状态从配置更新完成")
            
        except Exception as e:
            logging.error(f"从配置更新UI状态失败: {e}")
    
    def _initialize_config_system(self):
        """初始化配置系统"""
        try:
            # 加载配置列表
            self._load_config_list()
            logging.info("配置系统初始化完成")
        except Exception as e:
            logging.error(f"配置系统初始化失败: {e}")
    
    def show(self):
        """显示主界面"""
        self.ui.show()
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止绘图
            if self.drawing_worker and self.drawing_worker.isRunning():
                self.drawing_worker.stop_drawing()
                self.drawing_worker.wait(3000)
                if self.drawing_worker.isRunning():
                    self.drawing_worker.terminate()
            
            # 停止热键工作线程
            if self.hotkey_worker and self.hotkey_worker.isRunning():
                self.hotkey_worker.stop()
                self.hotkey_worker.wait(3000)
                if self.hotkey_worker.isRunning():
                    self.hotkey_worker.terminate()
            
            # 清理其他工作线程
            if self.click_worker and self.click_worker.isRunning():
                self.click_worker.wait(1000)
                if self.click_worker.isRunning():
                    self.click_worker.terminate()
            
            if self.capture_worker and self.capture_worker.isRunning():
                self.capture_worker.wait(1000)
                if self.capture_worker.isRunning():
                    self.capture_worker.terminate()
            
            logging.info("资源清理完成")
            
        except Exception as e:
            logging.error(f"清理资源失败: {e}")


if __name__ == "__main__":
    try:
        # 设置正确的工作目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # 初始化日志系统
        setup_logging()
        
        logging.info("=== 绘图助手启动 ===")
        logging.info(f"Python版本: {sys.version}")
        logging.info(f"脚本目录: {script_dir}")
        logging.info(f"工作目录: {os.getcwd()}")

        # 检查管理员权限
        if not isAdmin.is_admin():
            logging.info("正在请求管理员权限...")
            # 确保日志写入到文件
            logging.shutdown()
            isAdmin.run_as_admin()
            sys.exit(0)  # 退出当前进程，等待管理员权限重启
        else:
            logging.info("已获得管理员权限，启动绘图助手...")
        
        logging.info("创建QApplication...")
        app = QApplication.instance() 
        if not app:
            app = QApplication(sys.argv)
        logging.info("QApplication创建成功")
        
        logging.info("创建绘图助手控制器...")
        controller = PaintAppController()
        logging.info("绘图助手控制器创建成功")
        
        logging.info("显示主窗口...")
        controller.show()
        logging.info("绘图助手启动完成，进入事件循环")
        
        # 程序退出时清理资源
        def cleanup_on_exit():
            controller.cleanup()
        
        app.aboutToQuit.connect(cleanup_on_exit)
        
        sys.exit(app.exec_())
        
    except Exception as e:
        logging.error(f"绘图助手启动失败: {e}")
        logging.error(f"错误详情: {traceback.format_exc()}")
        input("按回车键退出...")  # 防止窗口一闪而过
        sys.exit(1)
