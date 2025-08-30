#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
钓鱼助手主程序
重构后的版本，UI和业务逻辑分离到不同的文件和线程中
"""

import sys
import os
import logging
import traceback
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QObject, pyqtSignal

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import isAdmin

# 导入重构后的模块
from fishing_ui import FishingMainUI, setup_logging
from fishing_business import FishingBusiness
from fishing_worker import WorkerManager, HotkeyWorker


class FishingAppController(QObject):
    """钓鱼助手控制器，协调UI、业务逻辑和工作线程"""
    
    def __init__(self):
        super().__init__()
        
        # 初始化日志
        setup_logging()
        logging.info("钓鱼助手控制器初始化开始")
        
        # 创建业务逻辑实例
        self.business = FishingBusiness()
        
        # 创建工作线程管理器
        self.worker_manager = WorkerManager()
        
        # 创建UI实例
        self.ui = FishingMainUI()
        
        # 创建热键监听器
        self.hotkey_worker = HotkeyWorker()
        
        # 连接信号
        self._connect_ui_signals()
        self._setup_hotkeys()
        
        # 初始化配置列表
        self._load_config_list()
        
        logging.info("钓鱼助手控制器初始化完成")
    
    def _connect_ui_signals(self):
        """连接UI信号与业务逻辑"""
        # 检测和设置信号
        self.ui.toggle_detection_requested.connect(self._on_detection_toggled)
        # 连接按钮选择信号
        self.ui.select_bag_button_requested.connect(lambda: self._select_button('bag'))
        self.ui.select_fish_button_requested.connect(lambda: self._select_button('fish'))
        self.ui.select_fish_tail_button_requested.connect(lambda: self._select_button('fish_tail'))
        self.ui.select_perfume_button_requested.connect(lambda: self._select_button('perfume'))
        self.ui.select_spray_button_requested.connect(lambda: self._select_button('spray'))
        self.ui.select_use_button_requested.connect(lambda: self._select_button('use'))
        self.ui.save_config_requested.connect(self._on_config_save)
        self.ui.load_config_requested.connect(self._on_config_load)
        self.ui.delete_config_requested.connect(self._on_config_delete)
        self.ui.perfume_interval_changed.connect(self._on_perfume_interval_changed)
        self.ui.fish_tail_interval_changed.connect(self._on_fish_tail_interval_changed)

        
        # 业务逻辑 -> UI
        self.business.button_detected.connect(self._on_button_detected)
        self.business.detection_box_added.connect(self.ui.add_detection_box)
        self.business.status_updated.connect(self.ui.update_status_text)
        self.business.auto_click_requested.connect(self._on_auto_click_requested)
        self.business.game_window_position_updated.connect(self.ui.show_game_window_position)
        
        # 工作线程信号将在启动时连接
        
        logging.info("UI信号连接完成")
    
    def _setup_hotkeys(self):
        """设置热键监听"""
        self.hotkey_worker.hotkey_pressed.connect(self._on_hotkey_pressed)
        self.hotkey_worker.start()
        logging.info("热键监听设置完成")
        
    def _load_config_list(self):
        """加载配置列表"""
        try:
            # 使用ConfigManager获取可用配置列表
            config_names = self.business.get_available_configs()
            self.ui.update_config_combo(config_names)
            logging.info(f"已加载 {len(config_names)} 个配置: {config_names}")
        except Exception as e:
            logging.error(f"加载配置列表失败: {e}")
            self.ui.update_config_combo([])
        
    def _load_config_from_json(self, config_name):
        """从ConfigManager加载指定配置"""
        try:
            # 使用ConfigManager加载配置
            success = self.business.load_config(config_name)
            if success:
                # 更新UI显示
                self._update_ui_with_loaded_config()
                # 检查是否可以开始检测
                self._check_detection_ready()
                logging.info(f"配置 '{config_name}' 加载成功")
                return True
            else:
                logging.error(f"配置 '{config_name}' 加载失败")
                return False
                
        except Exception as e:
            logging.error(f"从ConfigManager加载配置失败: {e}")
            return False
    
    def _update_ui_with_loaded_config(self):
        """更新UI显示加载的配置"""
        try:
            # 使用新的UI更新方法
            self.ui.update_ui_with_loaded_config(self.business)
            
        except Exception as e:
            logging.error(f"更新UI显示失败: {e}")
        
    def _on_detection_toggled(self):
        """处理检测开关"""
        if self.business.is_detecting:
            self._stop_detection()
        else:
            self._start_detection()
    
    def _start_detection(self):
        """开始检测"""
        try:
            # 检查必要的按钮是否已设置
            button_images = self.business.get_button_images()
            if not button_images['bag'] or not button_images['fish']:
                self.ui.update_status_text("请先选择背包按钮和钓鱼按钮")
                return
            
            # 获取UI中的按钮配置
            button_configs = self.ui.get_button_configs()
            
            # 设置重试时间配置（优先使用UI设置）
            click_wait_time = button_configs.get('click_wait_time')
            retry_wait_time = button_configs.get('retry_wait_time')
            button_check_interval = button_configs.get('button_check_interval')
            
            if click_wait_time is not None:
                self.business.set_retry_timing(click_wait_time=click_wait_time)
                logging.info(f"设置点击等待时间: {click_wait_time}秒")
            if retry_wait_time is not None:
                self.business.set_retry_timing(retry_wait_time=retry_wait_time)
                logging.info(f"设置重试等待时间: {retry_wait_time}秒")
            if button_check_interval is not None:
                self.business.set_retry_timing(button_check_interval=button_check_interval)
                logging.info(f"设置按钮检测间隔: {button_check_interval}秒")
            
            # 设置消耗品间隔配置（优先使用UI设置）
            perfume_interval = button_configs.get('perfume_interval')
            fish_tail_interval = button_configs.get('fish_tail_interval')
            
            if perfume_interval is not None:
                self.business.set_perfume_interval(perfume_interval)
                logging.info(f"设置香水使用间隔: {perfume_interval}秒")
            if fish_tail_interval is not None:
                self.business.set_fish_tail_interval(fish_tail_interval)
                logging.info(f"设置鱼尾使用间隔: {fish_tail_interval}秒")
            
            # 启动业务逻辑检测
            self.business.start_detection(button_configs)
            
            # 启动检测工作线程
            detection_worker = self.worker_manager.start_detection_worker(
                self.business, 
                auto_click_enabled=button_configs.get('auto_click_enabled', True), 
                auto_fish_tail_enabled=button_configs.get('auto_fish_tail_enabled', False)
            )
            
            # 连接检测工作线程信号
            if detection_worker:
                detection_worker.detection_completed.connect(self._on_detection_completed)
                detection_worker.error_occurred.connect(self.ui.update_status_text)
            
            # 更新UI状态
            self.ui.set_detection_button_text("⑥ 停止钓鱼 (S)")
            self.ui.update_status_text("检测已开始")
            logging.info("检测已开始")
            
        except AttributeError as e:
            error_msg = f"方法调用错误: {e}"
            logging.error(error_msg)
            self.ui.update_status_text(error_msg)
        except Exception as e:
            error_msg = f"启动检测失败: {e}"
            logging.error(error_msg)
            self.ui.update_status_text(error_msg)
    
    def _stop_detection(self):
        """停止检测"""
        try:
            self.business.stop_detection()
            self.worker_manager.stop_all_workers()
            
            # 清除检测覆盖层
            self.ui.clear_detection_overlay()
            
            # 更新UI状态
            self.ui.set_detection_button_text("⑥ 开始钓鱼 (O)")
            self.ui.update_status_text("检测已停止")
            logging.info("检测已停止")
            
        except Exception as e:
            error_msg = f"停止检测失败: {e}"
            logging.error(error_msg)
            self.ui.update_status_text(error_msg)
    
    def _select_button(self, button_type):
        """处理按钮选择请求"""
        try:
            from screen_cropper import crop_screen_region
            
            def on_crop_finished(img, position):
                if img and position:
                    # 设置按钮图像和位置到业务逻辑
                    if button_type == 'bag':
                        self.business.set_bag_button(img, position)
                        self.ui.display_bag_preview(img)
                    elif button_type == 'fish':
                        self.business.set_fish_button(img, position)
                        self.ui.display_fish_preview(img)
                    elif button_type == 'fish_tail':
                        self.business.set_fish_tail_button(img, position)
                        self.ui.display_fish_tail_preview(img)
                    elif button_type == 'perfume':
                        self.business.set_perfume_button(img, position)
                        self.ui.display_perfume_preview(img)
                    elif button_type == 'spray':
                        self.business.set_spray_button(img, position)
                        self.ui.display_spray_preview(img)
                    elif button_type == 'use':
                        self.business.set_use_button(img, position)
                        self.ui.display_use_preview(img)
                    
                    self.ui.update_status_text(f"{button_type}按钮已设置")
                    
                    # 检查是否所有必要按钮都已设置
                    self._check_detection_ready()
                else:
                    self.ui.update_status_text(f"{button_type}按钮选择已取消")
                
                # 清理cropper引用
                if hasattr(self, '_current_cropper'):
                    self._current_cropper = None
            
            # 启动屏幕截图工具并保持引用
            self.ui.update_status_text(f"请框选{button_type}按钮区域...")
            self._current_cropper = crop_screen_region(on_crop_finished, return_position=True)
            
        except Exception as e:
            logging.error(f"选择{button_type}按钮失败: {e}")
            self.ui.update_status_text(f"选择{button_type}按钮失败: {e}")
    
    def _check_detection_ready(self):
        """检查是否可以开始检测"""
        button_images = self.business.get_button_images()
        if button_images['bag'] and button_images['fish']:
            self.ui.set_detection_button_enabled(True)
            self.ui.update_status_text("已准备就绪，可以开始钓鱼")
        else:
            self.ui.set_detection_button_enabled(False)
            missing = []
            if not button_images['bag']:
                missing.append("背包按钮")
            if not button_images['fish']:
                missing.append("钓鱼按钮")
            self.ui.update_status_text(f"请先选择: {', '.join(missing)}")
    
    def _on_button_clicked(self, button_type, position):
        """处理按钮点击"""
        try:
            # 检查位置参数
            if position is None:
                self.ui.update_status_text(f"请先选择{button_type}按钮位置")
                return
            
            # 通过工作线程执行点击
            click_config = {'type': button_type, 'interval': 100}
            click_thread = self.worker_manager.start_click_thread(click_config, position)
            
            # 连接点击线程信号
            if click_thread:
                click_thread.finished.connect(lambda: self.ui.update_status_text(f"{button_type}点击完成"))
                click_thread.error.connect(self.ui.update_status_text)
            
        except Exception as e:
            logging.error(f"执行点击失败: {e}")
            self.ui.update_status_text(f"点击失败: {e}")
    
    def _on_hotkey_pressed(self, key):
        """处理热键按下"""
        if key == 'o':
            # O键开始检测
            if not self.business.is_detecting:
                self._start_detection()
                self.ui.update_status_text("O键开始检测")
            else:
                self.ui.update_status_text("检测已在运行中")
        elif key == 'p':
            # P键停止检测
            if self.business.is_detecting:
                self._stop_detection()
                self.ui.update_status_text("P键停止检测")
            else:
                self.ui.update_status_text("检测未在运行，无需停止")
    
    def _on_button_detected(self, position, confidence, button_type):
        """处理按钮检测"""
        logging.info(f"检测到{button_type}按钮，位置: {position}, 置信度: {confidence:.2f}")
        self.ui.update_status_text(f"检测到{button_type}按钮，置信度: {confidence:.2f}")
    
    def _on_detection_box_added(self, x, y, w, h, confidence, button_type):
        """处理检测框添加"""
        logging.info(f"添加检测框: {button_type} at ({x}, {y}, {w}, {h}), 置信度: {confidence:.3f}")
        # 添加检测框到UI覆盖层
        self.ui.add_detection_box(x, y, w, h, confidence, button_type)
    
    def _on_detection_completed(self):
        """处理检测完成"""
        # 获取业务逻辑中的检测结果
        detection_results = self.business.detection_results
        # 更新UI覆盖层
        self.ui.update_detection_overlay(detection_results)
    
    def _on_auto_click_requested(self, position):
        """处理自动点击请求"""
        try:
            logging.info(f"自动点击请求: {position}")
            self.ui.update_status_text(f"自动点击位置: {position}")
            
            # 创建点击配置
            click_config = {
                'window_title': '心动小镇',
                'move_delay': 0.1,
                'press_delay': 0.1,
                'final_delay': 0.1
            }
            
            # 通过工作线程管理器执行点击
            click_thread = self.worker_manager.start_click_thread(click_config, position)
            if click_thread:
                # 连接点击完成信号
                click_thread.finished.connect(lambda: self.ui.update_status_text(f"点击完成: {position}"))
                click_thread.error.connect(lambda err: self.ui.update_status_text(f"点击失败: {err}"))
            
        except Exception as e:
            logging.error(f"执行自动点击失败: {e}")
            self.ui.update_status_text(f"点击失败: {str(e)}")
    
    def _on_config_save(self):
        """处理配置保存"""
        try:
            config_name = self.ui.get_current_config_name()
            
            # 验证配置名称
            is_valid, error_msg = self.ui.validate_config_name(config_name)
            if not is_valid:
                from PyQt5.QtWidgets import QMessageBox
                QMessageBox.warning(self.ui, '保存配置', error_msg)
                return
            
            # 自动获取游戏窗口信息
            self.business.get_game_window_info()
            
            # 获取UI中的配置数据
            button_configs = self.ui.get_button_configs()
            
            # 更新业务逻辑中的配置
            self.business.update_settings(button_configs)
            
            # 调用save_config，传递UI配置数据
            success = self.business.save_config(config_name)
            if success:
                self.ui.update_status_text(f"配置 '{config_name}' 保存成功")
                # 保存完成后重新加载配置列表
                self._load_config_list()
                # 确保新配置显示在下拉框中
                self.ui.add_new_config(config_name)
            else:
                self.ui.update_status_text(f"配置 '{config_name}' 保存失败")
            
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            self.ui.update_status_text(f"保存配置失败: {e}")
    
    def _on_config_load(self):
        """处理配置加载"""
        try:
            config_name = self.ui.get_current_config_name()
            if config_name:
                success = self._load_config_from_json(config_name)
                if success:
                    self.ui.update_status_text(f"配置 '{config_name}' 加载成功")
                else:
                    self.ui.update_status_text(f"配置 '{config_name}' 加载失败")
            
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            self.ui.update_status_text(f"加载配置失败: {e}")
    
    def _on_config_delete(self):
        """处理配置删除"""
        try:
            config_name = self.ui.get_current_config_name()
            if config_name:
                from PyQt5.QtWidgets import QMessageBox
                reply = QMessageBox.question(self.ui, '删除配置', 
                                           f"确定要删除配置 '{config_name}' 吗？",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    success = self.business.delete_config(config_name)
                    if success:
                        self.ui.update_status_text(f"配置 '{config_name}' 删除成功")
                        # 重新加载配置列表
                        self._load_config_list()
                        # 清空当前UI状态
                        self._clear_current_config()
                    else:
                        self.ui.update_status_text(f"配置 '{config_name}' 删除失败")
            else:
                self.ui.update_status_text("请先选择要删除的配置")
            
        except Exception as e:
            logging.error(f"删除配置失败: {e}")
            self.ui.update_status_text(f"删除配置失败: {e}")
    
    def _clear_current_config(self):
        """清空当前配置状态"""
        try:
            # 清空业务逻辑中的按钮数据
            self.business.bag_button_img = None
            self.business.fish_button_img = None
            self.business.fish_tail_button_img = None
            self.business.perfume_button_img = None
            self.business.spray_button_img = None
            self.business.use_button_img = None
            self.business.bag_button_pos = None
            self.business.fish_button_pos = None
            self.business.fish_tail_button_pos = None
            self.business.perfume_button_pos = None
            self.business.spray_button_pos = None
            self.business.use_button_pos = None
            
            # 清空UI预览图像
            self.ui.clear_bag_preview()
            self.ui.clear_fish_preview()
            self.ui.clear_fish_tail_preview()
            self.ui.clear_perfume_preview()
            self.ui.clear_spray_preview()
            self.ui.clear_use_preview()
            
            # 重新检查检测就绪状态
            self._check_detection_ready()
            
            logging.info("当前配置状态已清空")
            
        except Exception as e:
            logging.error(f"清空配置状态失败: {e}")
    
    def _on_perfume_interval_changed(self, interval_seconds):
        """处理香水使用间隔变化"""
        try:
            settings = {'perfume_interval': interval_seconds}
            self.business.update_settings(settings)
            logging.info(f"香水使用间隔更新为: {interval_seconds}秒")
            
        except Exception as e:
            logging.error(f"更新香水使用间隔失败: {e}")
            self.ui.update_status_text(f"更新香水使用间隔失败: {e}")
    
    def _on_fish_tail_interval_changed(self, interval_seconds):
        """处理鱼尾使用间隔变化"""
        try:
            settings = {'fish_tail_interval': interval_seconds}
            self.business.update_settings(settings)
            logging.info(f"鱼尾使用间隔更新为: {interval_seconds}秒")
            
        except Exception as e:
            logging.error(f"更新鱼尾使用间隔失败: {e}")
            self.ui.update_status_text(f"更新鱼尾使用间隔失败: {e}")
    
    def _on_settings_changed(self, settings):
        """处理设置变更"""
        try:
            self.business.update_settings(settings)
            self.worker_manager.update_settings(settings)
            logging.info("设置更新成功")
            
        except Exception as e:
            logging.error(f"更新设置失败: {e}")
            self.ui.update_status_text(f"更新设置失败: {e}")
    
    def show(self):
        """显示主界面"""
        self.ui.show()
    
    def cleanup(self):
        """清理资源"""
        self.worker_manager.cleanup()
        self.hotkey_worker.stop()
        self.business.cleanup()
        logging.info("资源清理完成")



if __name__ == "__main__":
    try:
        # 设置正确的工作目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        
        # 初始化日志系统
        setup_logging()
        
        logging.info("=== 钓鱼助手启动 ===")
        logging.info(f"Python版本: {sys.version}")
        logging.info(f"脚本目录: {script_dir}")
        logging.info(f"工作目录: {os.getcwd()}")

        # isAdmin.hide_console()
        # 检查管理员权限
        if not isAdmin.is_admin():
            logging.warning("检测到需要管理员权限以启用鼠标穿透功能...")
            print("检测到需要管理员权限以启用鼠标穿透功能...")
            print("正在请求管理员权限...")
            isAdmin.run_as_admin()
        else:
            logging.info("已获得管理员权限，启动钓鱼助手...")
            print("已获得管理员权限，启动钓鱼助手...")
        
        logging.info("创建QApplication...")
        app = QApplication.instance() 
        if not app:
            app = QApplication(sys.argv)
        logging.info("QApplication创建成功")
        
        logging.info("创建钓鱼助手控制器...")
        controller = FishingAppController()
        logging.info("钓鱼助手控制器创建成功")
        
        logging.info("显示主窗口...")
        controller.show()
        logging.info("钓鱼助手启动完成，进入事件循环")
        
        sys.exit(app.exec_())
        
    except Exception as e:
        logging.error(f"钓鱼助手启动失败: {e}")
        logging.error(f"错误详情: {traceback.format_exc()}")
        print(f"钓鱼助手启动失败: {e}")
        print(f"详细错误信息已记录到日志文件")
        input("按回车键退出...")  # 防止窗口一闪而过
        sys.exit(1)
