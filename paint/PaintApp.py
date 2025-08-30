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
from PyQt5.QtCore import QObject, pyqtSignal

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import isAdmin

# 导入绘图模块
from paint_ui import PaintMainUI, setup_logging
from paint_business import PaintBusiness
from paint_worker import DrawingWorker, ClickWorker, ScreenCaptureWorker, HotkeyWorker


class PaintAppController(QObject):
    """绘图助手控制器，协调UI、业务逻辑和工作线程"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化日志
        setup_logging()
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
        
        logging.info("绘图助手控制器初始化完成")
    
    def _connect_ui_signals(self):
        """连接UI信号与业务逻辑"""
        # UI -> 控制器
        self.ui.select_draw_area_requested.connect(self._on_select_draw_area)
        self.ui.select_color_area_requested.connect(self._on_select_color_area)
        self.ui.select_image_requested.connect(self._on_select_image)
        self.ui.process_image_requested.connect(self._on_process_image)
        self.ui.start_drawing_requested.connect(self._on_start_drawing)
        self.ui.stop_drawing_requested.connect(self._on_stop_drawing)
        
        logging.info("UI信号连接完成")
    
    def _connect_business_signals(self):
        """连接业务逻辑信号"""
        # 业务逻辑 -> UI
        self.business.status_updated.connect(self.ui.update_status_text)
        self.business.image_processed.connect(self.ui.display_pixelized_image)
        self.business.color_palette_extracted.connect(self.ui.display_color_palette)
        self.business.drawing_progress.connect(self.ui.update_drawing_progress)
        self.business.drawing_completed.connect(self._on_drawing_completed)
        
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
    
    def _on_select_color_area(self):
        """处理选择颜色区域请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    self.business.set_color_area(position)
                    self.ui.set_color_area(position)  # 同时更新UI状态
                    logging.info(f"颜色区域已设置: {position}")
                else:
                    self.ui.update_status_text("颜色区域选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具
            self.ui.update_status_text("请框选颜色区域（2列×8行颜色块）...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择颜色区域失败: {e}")
            self.ui.update_status_text(f"选择颜色区域失败: {str(e)}")
    
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
            # 检查是否准备就绪
            if not self.business.is_ready_to_draw():
                missing = []
                if not self.business.get_draw_area_position():
                    missing.append("绘画区域")
                if not self.business.get_color_area_position():
                    missing.append("颜色区域")
                if not self.business.get_selected_image_path():
                    missing.append("图片")
                if not self.business.get_pixelized_image():
                    missing.append("图片处理")
                
                self.ui.update_status_text(f"请先完成: {', '.join(missing)}")
                return
            
            # 如果已经在绘图，先停止
            if self.drawing_worker and self.drawing_worker.isRunning():
                self._on_stop_drawing()
                return
            
            # 获取绘图数据
            pixel_info_list = self.business.get_pixel_info_list()
            color_palette = self.business.get_color_palette()
            color_area_pos = self.business.get_color_area_position()
            
            if not pixel_info_list:
                self.ui.update_status_text("像素信息未准备好，请重新处理图片")
                return
            
            if not color_palette:
                self.ui.update_status_text("颜色调色板未准备好，请重新设置颜色区域")
                return
            
            # 获取延迟配置
            delay_settings = self.ui.get_delay_settings()
            
            # 创建绘图工作线程
            self.drawing_worker = DrawingWorker(pixel_info_list, color_palette, color_area_pos)
            
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
            self.drawing_worker.start()
            
            # 更新UI状态
            self.ui.set_drawing_button_text("停止绘图")
            self.ui.set_drawing_button_enabled(True)
            self.ui.update_status_text("绘图已开始")
            logging.info("绘图已开始")
            
        except Exception as e:
            logging.error(f"启动绘图失败: {e}")
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
            
            # 更新UI状态
            self.ui.set_drawing_button_text("开始绘图")
            self.ui.set_drawing_button_enabled(True)
            self.ui.update_status_text("绘图已停止")
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
                if not self.business.get_color_area_position():
                    missing.append("颜色区域")
                if not self.business.get_selected_image_path():
                    missing.append("图片选择")
                if not self.business.get_pixelized_image():
                    missing.append("图片处理")
                
                self.ui.update_status_text(f"请先完成: {', '.join(missing)}")
                
        except Exception as e:
            logging.error(f"检查绘图就绪状态失败: {e}")
    
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
            print("正在请求管理员权限...")
            isAdmin.run_as_admin()
            sys.exit(0)  # 退出当前进程，等待管理员权限重启
        else:
            logging.info("已获得管理员权限，启动绘图助手...")
            print("已获得管理员权限，启动绘图助手...")
        
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
        print(f"绘图助手启动失败: {e}")
        print(f"详细错误信息已记录到日志文件")
        input("按回车键退出...")  # 防止窗口一闪而过
        sys.exit(1)
