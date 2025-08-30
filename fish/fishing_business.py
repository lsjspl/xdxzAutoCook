# -*- coding: utf-8 -*-
"""
钓鱼助手 - 业务逻辑模块
"""

import logging
import time
import threading
from PIL import ImageGrab
from PyQt5.QtCore import QObject, pyqtSignal
from config_manager import ConfigManager
from image_detector import ImageDetector


class FishingBusiness(QObject):
    """钓鱼助手业务逻辑类"""
    
    status_updated = pyqtSignal(str)
    button_detected = pyqtSignal(tuple, float, str)
    detection_box_added = pyqtSignal(int, int, int, int, float, str)
    auto_click_requested = pyqtSignal(tuple)
    game_window_position_updated = pyqtSignal(tuple, tuple)  # 位置, 大小
    
    def __init__(self):
        super().__init__()
        
        self.config_manager = ConfigManager()
        self.image_detector = ImageDetector()
        
        # 添加线程锁来保护状态变量
        self._state_lock = threading.Lock()
        
        # 按钮图像和屏幕坐标 (x, y, width, height)
        self.bag_button_img = None
        self.fish_button_img = None
        self.fish_tail_button_img = None
        self.perfume_button_img = None
        self.spray_button_img = None
        self.use_button_img = None
        self.bag_button_pos = None
        self.fish_button_pos = None
        self.fish_tail_button_pos = None
        self.perfume_button_pos = None
        self.spray_button_pos = None
        self.use_button_pos = None
        
        # 游戏窗口信息
        self.game_window_pos = None
        self.game_window_size = None
        
        # 状态
        self.is_detecting = False
        self.is_using_consumables = False
        self.is_waiting_for_fishing_completion = False  # 是否正在等待钓鱼完成
        self.last_click_time = 0
        self.click_cooldown = 1.0
        
        # 消耗品使用间隔配置
        self.last_perfume_time = 0
        self.perfume_interval = 120  # 香水使用间隔（秒）
        self.last_fish_tail_time = 0
        self.fish_tail_interval = 60  # 鱼尾使用间隔（秒）
        
        # 重试和等待时间配置
        self.click_wait_time = 1      # 点击后等待时间
        self.retry_wait_time = 0      # 重试前等待时间
        self.button_check_interval = 0.5  # 按钮检测间隔
        
        # 自动使用设置
        self.auto_fish_tail_enabled = True  # 默认开启自动使用鱼尾香水
        
        # 窗口设置
        self.always_on_top_enabled = False  # 默认不置顶
        self.show_game_window_enabled = True  # 默认显示游戏窗口位置
        
        self.detection_results = []
    
    def set_bag_button(self, img, position):
        """设置背包按钮"""
        if self.config_manager.validate_button_position('背包按钮', position):
            self.bag_button_img = img
            self.bag_button_pos = position
            logging.info(f"背包按钮已设置，位置: {position}")
    
    def set_fish_button(self, img, position):
        """设置钓鱼按钮"""
        if self.config_manager.validate_button_position('钓鱼按钮', position):
            self.fish_button_img = img
            self.fish_button_pos = position
            logging.info(f"钓鱼按钮已设置，位置: {position}")
    
    def set_fish_tail_button(self, img, position):
        """设置鱼尾按钮"""
        if self.config_manager.validate_button_position('鱼尾按钮', position):
            self.fish_tail_button_img = img
            self.fish_tail_button_pos = position
            logging.info(f"鱼尾按钮已设置，位置: {position}")
    
    def set_perfume_button(self, img, position):
        """设置香水按钮"""
        if self.config_manager.validate_button_position('香水按钮', position):
            self.perfume_button_img = img
            self.perfume_button_pos = position
            logging.info(f"香水按钮已设置，位置: {position}")
    
    def set_spray_button(self, img, position):
        """设置喷雾按钮"""
        if self.config_manager.validate_button_position('喷雾按钮', position):
            self.spray_button_img = img
            self.spray_button_pos = position
            logging.info(f"喷雾按钮已设置，位置: {position}")
    
    def set_use_button(self, img, position):
        """设置使用按钮"""
        if self.config_manager.validate_button_position('使用按钮', position):
            self.use_button_img = img
            self.use_button_pos = position
            logging.info(f"使用按钮已设置，位置: {position}")
    
    def can_start_detection(self):
        """检查是否可以开始检测"""
        return (self.bag_button_img is not None and 
                self.fish_button_img is not None and 
                self.bag_button_pos is not None and 
                self.fish_button_pos is not None)
    
    def set_detection_state(self, detecting):
        """设置检测状态"""
        with self._state_lock:
            self.is_detecting = detecting
    
    def start_detection(self, button_configs=None):
        """开始检测"""
        logging.info("开始检测：重置所有状态并开始新的检测流程")
        
        # 先重置所有状态
        self.reset_all_states()
        
        # 设置检测状态
        with self._state_lock:
            self.is_detecting = True
        
        # 应用配置参数
        if button_configs:
            if 'fish_tail_interval' in button_configs:
                self.fish_tail_interval = button_configs['fish_tail_interval']
                logging.info(f"设置鱼尾使用间隔: {self.fish_tail_interval}秒")
        
        logging.info("开始检测：状态重置完成，检测流程已启动")
        self.log_current_states()  # 记录当前状态
        self.status_updated.emit("检测已开始，状态已重置")
    
    def stop_detection(self):
        """停止检测"""
        logging.info("停止检测：开始重置所有状态")
        
        # 记录停止前的状态
        self.log_current_states()
        
        # 重置所有状态
        self.reset_all_states()
        
        logging.info("停止检测：所有状态已重置")
        self.status_updated.emit("检测已停止，状态已重置")
    
    def set_fish_tail_interval(self, interval):
        """设置鱼尾使用间隔"""
        self.fish_tail_interval = interval
    
    def set_perfume_interval(self, interval):
        """设置香水使用间隔"""
        self.perfume_interval = interval
    
    def set_retry_timing(self, click_wait_time=None, retry_wait_time=None, button_check_interval=None):
        """设置重试和等待时间配置"""
        if click_wait_time is not None:
            self.click_wait_time = click_wait_time
            logging.info(f"设置点击等待时间: {click_wait_time}秒")
        
        if retry_wait_time is not None:
            self.retry_wait_time = retry_wait_time
            logging.info(f"设置重试等待时间: {retry_wait_time}秒")
        
        if button_check_interval is not None:
            self.button_check_interval = button_check_interval
            logging.info(f"设置按钮检测间隔: {button_check_interval}秒")
    
    def get_retry_timing(self):
        """获取当前的重试时间配置"""
        return {
            'click_wait_time': self.click_wait_time,
            'retry_wait_time': self.retry_wait_time,
            'button_check_interval': self.button_check_interval
        }
    
    def reset_all_states(self):
        """重置所有状态变量"""
        logging.info("重置所有状态变量")
        
        with self._state_lock:
            # 重置检测相关状态
            self.is_detecting = False
            self.is_using_consumables = False
            self.is_waiting_for_fishing_completion = False # 重置等待钓鱼完成状态
        
        # 重置时间相关状态（保持用户配置，只重置运行时状态）
        self.last_click_time = 0
        self.last_fish_tail_time = 0  # 重置鱼尾使用计时器
        self.last_perfume_time = 0    # 重置香水使用计时器
        
        # 清空检测结果
        self.detection_results.clear()
        
        logging.info("所有状态变量已重置")
        return True
    
    def get_current_states(self):
        """获取当前状态信息（用于调试）"""
        current_time = time.time()
        states = {
            'is_detecting': self.is_detecting,
            'is_using_consumables': self.is_using_consumables,
            'is_waiting_for_fishing_completion': self.is_waiting_for_fishing_completion, # 添加等待状态
            'last_click_time': self.last_click_time,
            'click_cooldown_remaining': max(0, self.click_cooldown - (current_time - self.last_click_time)),
            'last_fish_tail_time': self.last_fish_tail_time,
            'fish_tail_interval_remaining': max(0, self.fish_tail_interval - (current_time - self.last_fish_tail_time)),
            'last_perfume_time': self.last_perfume_time,
            'perfume_interval_remaining': max(0, self.perfume_interval - (current_time - self.last_perfume_time)),
            'detection_results_count': len(self.detection_results)
        }
        return states
    
    def log_current_states(self):
        """记录当前状态信息到日志"""
        states = self.get_current_states()
        logging.info("当前状态信息:")
        for key, value in states.items():
            if isinstance(value, float):
                logging.info(f"  {key}: {value:.3f}")
            else:
                logging.info(f"  {key}: {value}")
    
    def auto_detect_buttons(self, auto_click_enabled=True, auto_fish_tail_enabled=False):
        """自动检测按钮"""
        # 使用线程锁保护状态检查
        with self._state_lock:
            if not self.is_detecting:
                return
            
            # 如果正在使用消耗品，暂停主循环检测，避免干扰消耗品使用流程
            if self.is_using_consumables:
                logging.debug("正在使用消耗品，暂停主循环检测")
                return
        
        current_time = time.time()
        
        # 检测背包和钓鱼按钮
        bag_result = self._detect_button_at_position('bag')
        fish_result = self._detect_button_at_position('fish')
        

        
        if auto_fish_tail_enabled:
            # 检查是否需要使用消耗品
            current_time = time.time()
            time_since_last_perfume = current_time - self.last_perfume_time
            time_since_last_fish_tail = current_time - self.last_fish_tail_time
            
            # 检查是否有任何消耗品需要更新
            perfume_needed = time_since_last_perfume > self.perfume_interval
            fish_tail_needed = time_since_last_fish_tail > self.fish_tail_interval
            
            # 添加额外的保护：如果最近刚使用过消耗品，增加冷却时间
            recent_consumables_use = (current_time - self.last_fish_tail_time < 5.0 or 
                                    current_time - self.last_perfume_time < 5.0)
            
            # 分别处理香水和鱼尾，独立使用
            if not self.is_using_consumables and not recent_consumables_use:
                # 检查是否是首次使用（两个消耗品都未使用过）
                is_initial_use = (self.last_perfume_time == 0 and self.last_fish_tail_time == 0)
                
                if is_initial_use:
                    # 首次使用：香水和鱼尾一起使用
                    logging.info("高级钓鱼：首次使用，香水和鱼尾一起使用")
                    if self._use_consumables():
                        logging.info("高级钓鱼：首次消耗品使用完成，准备执行钓鱼流程")
                        self._execute_advanced_fishing(bag_result, fish_result, auto_click_enabled, consumables_already_used=True)
                    else:
                        logging.warning("高级钓鱼：首次消耗品使用失败")
                elif perfume_needed:
                    # 后续使用：优先使用香水（因为间隔更长）
                    logging.info(f"高级钓鱼：使用香水（间隔: {time_since_last_perfume:.1f}秒）")
                    if self._use_perfume_only():
                        logging.info("高级钓鱼：香水使用完成，准备执行钓鱼流程")
                        self._execute_advanced_fishing(bag_result, fish_result, auto_click_enabled, consumables_already_used=True)
                    else:
                        logging.warning("高级钓鱼：香水使用失败")
                elif fish_tail_needed:
                    # 后续使用：使用鱼尾
                    logging.info(f"高级钓鱼：使用鱼尾（间隔: {time_since_last_fish_tail:.1f}秒）")
                    if self._use_fish_tail_only():
                        logging.info("高级钓鱼：鱼尾使用完成，准备执行钓鱼流程")
                        self._execute_advanced_fishing(bag_result, fish_result, auto_click_enabled, consumables_already_used=True)
                    else:
                        logging.warning("高级钓鱼：鱼尾使用失败")
                else:
                    # 不需要使用消耗品
                    perfume_remaining = max(0, self.perfume_interval - time_since_last_perfume)
                    fish_tail_remaining = max(0, self.fish_tail_interval - time_since_last_fish_tail)
                    logging.info(f"高级钓鱼：消耗品间隔未到（香水剩余: {perfume_remaining:.1f}秒，鱼尾剩余: {fish_tail_remaining:.1f}秒）")
                    self._execute_advanced_fishing(bag_result, fish_result, auto_click_enabled)
            else:
                if recent_consumables_use:
                    logging.info(f"高级钓鱼：消耗品最近刚使用过，跳过本次更新（冷却保护）")
                elif perfume_needed or fish_tail_needed:
                    if perfume_needed and fish_tail_needed:
                        logging.info(f"高级钓鱼：消耗品需要更新但正在使用中，跳过本次更新")
                    elif perfume_needed:
                        logging.info(f"高级钓鱼：香水需要更新但正在使用中，跳过本次更新")
                    else:
                        logging.info(f"高级钓鱼：鱼尾需要更新但正在使用中，跳过本次更新")
                else:
                    perfume_remaining = max(0, self.perfume_interval - time_since_last_perfume)
                    fish_tail_remaining = max(0, self.fish_tail_interval - time_since_last_fish_tail)
                    logging.info(f"高级钓鱼：消耗品间隔未到（香水剩余: {perfume_remaining:.1f}秒，鱼尾剩余: {fish_tail_remaining:.1f}秒）")
                
                self._execute_advanced_fishing(bag_result, fish_result, auto_click_enabled)
        else:
            self._execute_basic_fishing(bag_result, fish_result, auto_click_enabled)
    
    def _detect_button_at_position(self, button_type):
        """在指定位置检测按钮"""
        button_img = None
        button_pos = None
        
        if button_type == 'bag':
            button_img = self.bag_button_img
            button_pos = self.bag_button_pos
        elif button_type == 'fish':
            button_img = self.fish_button_img
            button_pos = self.fish_button_pos
        elif button_type == 'fish_tail':
            button_img = self.fish_tail_button_img
            button_pos = self.fish_tail_button_pos
        elif button_type == 'perfume':
            button_img = self.perfume_button_img
            button_pos = self.perfume_button_pos
        elif button_type == 'spray':
            button_img = self.spray_button_img
            button_pos = self.spray_button_pos
        elif button_type == 'use':
            button_img = self.use_button_img
            button_pos = self.use_button_pos
        
        if not button_img or not button_pos:
            return None
        
        # 截取按钮位置图像
        x, y, w, h = button_pos
        region_img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
        if not region_img:
            return None
        
        # 检测按钮
        result = self.image_detector.detect_button(region_img, button_img)
        if result:
            location, confidence = result
            global_x = x + location[0]
            global_y = y + location[1]
            
            self.status_updated.emit(f"检测到{button_type}按钮，位置: ({global_x}, {global_y})，置信度: {confidence:.3f}")
            
            detection_info = {
                'x': global_x, 'y': global_y, 'w': w, 'h': h,
                'confidence': confidence, 'type': button_type
            }
            self.detection_results.append(detection_info)
            self.detection_box_added.emit(global_x, global_y, w, h, confidence, button_type)
            
            return (global_x, global_y), confidence
        
        return None
    
    def _execute_basic_fishing(self, bag_result, fish_result, auto_click_enabled):
        """执行基础钓鱼模式"""
        if not auto_click_enabled or not fish_result:
            return
        
        # 如果正在等待钓鱼完成，跳过
        if self.is_waiting_for_fishing_completion:
            return
                
        current_time = time.time()
        if current_time - self.last_click_time < self.click_cooldown:
            return
        
        # 点击钓鱼按钮
        location, confidence = fish_result
        center_x = location[0] + self.fish_button_pos[2] // 2
        center_y = location[1] + self.fish_button_pos[3] // 2
        
        if self._click_with_confirmation((center_x, center_y), "钓鱼按钮", single_attempt=True):
            self.last_click_time = current_time
            self.is_waiting_for_fishing_completion = True  # 设置等待钓鱼完成状态
            self.status_updated.emit("基础钓鱼：点击钓鱼按钮")
            logging.info("基础钓鱼：钓鱼按钮点击成功，等待钓鱼完成")
            
            # 等待背包按钮出现（表示钓鱼完成）
            if self._wait_for_button_appearance('bag', max_wait_time=30):
                self.status_updated.emit("基础钓鱼：钓鱼完成，背包已出现，准备继续钓鱼")
                logging.info("基础钓鱼：钓鱼完成，背包已出现，准备继续钓鱼")
                # 重置等待状态，允许继续钓鱼
                self.is_waiting_for_fishing_completion = False
            else:
                self.status_updated.emit("基础钓鱼：等待背包按钮超时")
                logging.warning("基础钓鱼：等待背包按钮超时")
                # 超时后也重置状态
                self.is_waiting_for_fishing_completion = False
    
    def _execute_advanced_fishing(self, bag_result, fish_result, auto_click_enabled, consumables_already_used=False):
        """执行高级钓鱼模式"""
        if not auto_click_enabled:
            logging.info("高级钓鱼：自动点击未启用")
            return
        
        current_time = time.time()
        if current_time - self.last_click_time < self.click_cooldown:
            logging.info(f"高级钓鱼：点击冷却中，剩余时间: {self.click_cooldown - (current_time - self.last_click_time):.1f}秒")
            return
        
        # 消耗品检测统一在主循环中处理，这里只负责钓鱼逻辑
        if consumables_already_used:
            logging.info("高级钓鱼：消耗品已使用，直接开始钓鱼")
        else:
            logging.info("高级钓鱼：消耗品未使用，但检测逻辑在主循环中，直接开始钓鱼")
        
        # 点击钓鱼按钮
        if fish_result:
            location, confidence = fish_result
            center_x = location[0] + self.fish_button_pos[2] // 2
            center_y = location[1] + self.fish_button_pos[3] // 2
            
            logging.info(f"高级钓鱼：准备点击钓鱼按钮，位置: ({center_x}, {center_y})")
            
            if self._click_with_confirmation((center_x, center_y), "钓鱼按钮", single_attempt=True):
                self.last_click_time = current_time
                self.is_waiting_for_fishing_completion = True  # 设置等待钓鱼完成状态
                self.status_updated.emit("高级钓鱼：点击钓鱼按钮")
                logging.info("高级钓鱼：钓鱼按钮点击成功，等待钓鱼完成")
                
                # 等待背包按钮出现（表示钓鱼完成）
                if self._wait_for_button_appearance('bag', max_wait_time=30):
                    self.status_updated.emit("高级钓鱼：钓鱼完成，背包已出现，准备继续钓鱼")
                    logging.info("高级钓鱼：钓鱼完成，背包已出现，准备继续钓鱼")
                    # 重置等待状态，允许继续钓鱼
                    self.is_waiting_for_fishing_completion = False
                else:
                    self.status_updated.emit("高级钓鱼：等待背包按钮超时")
                    logging.warning("高级钓鱼：等待背包按钮超时")
                    # 超时后也重置状态
                    self.is_waiting_for_fishing_completion = False
        else:
            logging.warning("高级钓鱼：未检测到钓鱼按钮，无法开始钓鱼")
    
    def _use_consumables(self):
        """使用消耗品流程"""
        with self._state_lock:
            if self.is_using_consumables:
                logging.warning("消耗品使用：正在使用中，跳过重复调用")
                return False
                
            logging.info("消耗品使用：开始使用消耗品流程")
            self.is_using_consumables = True
        
        # 在消耗品使用期间，强制暂停主循环检测
        logging.info("消耗品使用：暂停主循环检测，确保流程完整性")
        
        try:
            # 第一步：点击背包，使用香水
            if self.perfume_button_img and self.perfume_button_pos:
                logging.info("消耗品使用：开始使用香水")
                if not self._click_bag_and_use_perfume():
                    logging.error("消耗品使用：香水使用失败")
                    return False
                logging.info("消耗品使用：香水使用完成")
                self.last_perfume_time = time.time()
            else:
                logging.info("消耗品使用：跳过香水使用（未配置）")
            
            # 第二步：点击背包，使用鱼尾
            if self.fish_tail_button_img and self.fish_tail_button_pos:
                logging.info("消耗品使用：开始使用鱼尾")
                if not self._click_bag_and_use_fish_tail():
                    logging.error("消耗品使用：鱼尾使用失败")
                    return False
                logging.info("消耗品使用：鱼尾使用完成")
                # 更新鱼尾使用时间
                self.last_fish_tail_time = time.time()
            else:
                logging.info("消耗品使用：跳过鱼尾使用（未配置）")
            
            self.status_updated.emit("消耗品使用完成")
            logging.info("消耗品使用：所有消耗品使用完成")
            return True
        
        finally:
            with self._state_lock:
                self.is_using_consumables = False
            logging.info("消耗品使用：流程结束，重置状态")
    
    def _use_perfume_only(self):
        """只使用香水"""
        with self._state_lock:
            if self.is_using_consumables:
                logging.warning("消耗品使用：正在使用中，跳过重复调用")
                return False
                
            logging.info("消耗品使用：开始使用香水")
            self.is_using_consumables = True
        
        try:
            # 只使用香水
            if self.perfume_button_img and self.perfume_button_pos:
                logging.info("消耗品使用：开始使用香水")
                if not self._click_bag_and_use_perfume():
                    logging.error("消耗品使用：香水使用失败")
                    return False
                logging.info("消耗品使用：香水使用完成")
                # 更新香水使用时间
                self.last_perfume_time = time.time()
            else:
                logging.info("消耗品使用：跳过香水使用（未配置）")
            
            self.status_updated.emit("香水使用完成")
            logging.info("消耗品使用：香水使用完成")
            return True
        
        finally:
            with self._state_lock:
                self.is_using_consumables = False
            logging.info("消耗品使用：流程结束，重置状态")
    
    def _use_fish_tail_only(self):
        """只使用鱼尾"""
        with self._state_lock:
            if self.is_using_consumables:
                logging.warning("消耗品使用：正在使用中，跳过重复调用")
                return False
                
            logging.info("消耗品使用：开始使用鱼尾")
            self.is_using_consumables = True
        
        try:
            # 只使用鱼尾
            if self.fish_tail_button_img and self.fish_tail_button_pos:
                logging.info("消耗品使用：开始使用鱼尾")
                if not self._click_bag_and_use_fish_tail():
                    logging.error("消耗品使用：鱼尾使用失败")
                    return False
                logging.info("消耗品使用：鱼尾使用完成")
                # 更新鱼尾使用时间
                self.last_fish_tail_time = time.time()
            else:
                logging.info("消耗品使用：跳过鱼尾使用（未配置）")
            
            self.status_updated.emit("鱼尾使用完成")
            logging.info("消耗品使用：鱼尾使用完成")
            return True
        
        finally:
            with self._state_lock:
                self.is_using_consumables = False
            logging.info("消耗品使用：流程结束，重置状态")
    
    def _click_bag_and_use_perfume(self):
        """点击背包并使用香水"""
        # 点击背包（只尝试一次）
        if not self._click_button_at_position('bag', "背包按钮", single_attempt=True):
            return False
        
        # 等待香水按钮出现
        if not self._wait_for_button_appearance('perfume', max_wait_time=5):
            return False
        
        # 点击香水（只尝试一次）
        if not self._click_button_at_position('perfume', "香水按钮", single_attempt=True):
            return False
        
        # 等待喷雾按钮出现
        if not self._wait_for_button_appearance('spray', max_wait_time=5):
            return False
            
        # 点击喷雾按钮（只尝试一次）
        if not self._click_button_at_position('spray', "喷雾按钮", single_attempt=True):
            return False
        
        # 等待2秒让香水使用完成
        time.sleep(2.0)
    
        return True
    
    def _click_bag_and_use_fish_tail(self):
        """点击背包并使用鱼尾"""
        if not self._click_button_at_position('bag', "背包按钮", single_attempt=True):
            return False
        
        if not self._wait_for_button_appearance('fish_tail', max_wait_time=5):
            return False
        
        if not self._click_button_at_position('fish_tail', "鱼尾按钮", single_attempt=True):
            logging.error("鱼尾按钮点击失败")
            return False
        
        if not self._wait_for_button_appearance('use', max_wait_time=5):
            logging.error("使用按钮等待超时")
            return False
        
        # 点击使用按钮（只尝试一次）
        if not self._click_button_at_position('use', "使用按钮", single_attempt=True):
            logging.error("使用按钮点击失败")
            return False
        
        time.sleep(2.0)
        return True
                
    def _click_button_at_position(self, button_type, button_name, single_attempt=False):
        """在指定位置点击按钮"""
        button_pos = None
        if button_type == 'bag':
            button_pos = self.bag_button_pos
        elif button_type == 'fish':
            button_pos = self.fish_button_pos
        elif button_type == 'fish_tail':
            button_pos = self.fish_tail_button_pos
        elif button_type == 'perfume':
            button_pos = self.perfume_button_pos
        elif button_type == 'spray':
            button_pos = self.spray_button_pos
        elif button_type == 'use':
            button_pos = self.use_button_pos
        
        if not button_pos:
            return False
    
        center_x = button_pos[0] + button_pos[2] // 2
        center_y = button_pos[1] + button_pos[3] // 2
        
        return self._click_with_confirmation((center_x, center_y), button_name, single_attempt)
    
    def _click_with_confirmation(self, coordinates, button_name, single_attempt=False):
        """点击按钮并确认成功"""
        if single_attempt:
            # 消耗品使用流程中只尝试一次
            max_attempts = 1
        else:
            # 普通流程尝试3次
            max_attempts = 3
        
        for attempt in range(max_attempts):
            logging.info(f"点击{button_name}，尝试 {attempt + 1}/{max_attempts}")
            self.auto_click_requested.emit(coordinates)
            self.status_updated.emit(f"点击{button_name}，尝试 {attempt + 1}/{max_attempts}")
            
            # 等待点击生效
            logging.info(f"等待{self.click_wait_time}秒让点击生效...")
            time.sleep(self.click_wait_time)
            
            # 这里可以添加真正的按钮状态检查逻辑
            # 目前简化处理，直接认为点击成功
            if attempt == max_attempts - 1:
                self.status_updated.emit(f"{button_name}点击完成")
                logging.info(f"{button_name}点击完成")
                return True
            
            # 如果不是最后一次尝试，等待更长时间后重试
            if attempt < max_attempts - 1:
                logging.info(f"等待{self.retry_wait_time}秒后重试...")
                time.sleep(self.retry_wait_time)
        
        self.status_updated.emit(f"{button_name}点击失败")
        logging.error(f"{button_name}点击失败，已尝试{max_attempts}次")
        return False
            
    def _wait_for_button_appearance(self, button_type, max_wait_time=10):
        """等待按钮出现"""
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            if self._detect_button_at_position(button_type):
                return True
            time.sleep(self.button_check_interval)
        
        logging.warning(f"{button_type}按钮等待超时")
        return False
    
    def clear_detection_results(self):
        """清除检测结果"""
        self.detection_results.clear()
    
    def get_button_images(self):
        """获取按钮图像"""
        return {
            'bag': self.bag_button_img,
            'fish': self.fish_button_img,
            'fish_tail': self.fish_tail_button_img,
            'perfume': self.perfume_button_img,
            'spray': self.spray_button_img,
            'use': self.use_button_img
        }
    
    def get_button_positions(self):
        """获取按钮位置"""
        return {
            'bag': self.bag_button_pos,
            'fish': self.fish_button_pos,
            'fish_tail': self.fish_tail_button_pos,
            'perfume': self.perfume_button_pos,
            'spray': self.spray_button_pos,
            'use': self.use_button_pos
        }
    
    def update_settings(self, settings):
        """更新设置"""
        try:
            if 'perfume_interval' in settings:
                self.perfume_interval = settings['perfume_interval']
                logging.info(f"设置香水使用间隔: {self.perfume_interval}秒")
            if 'fish_tail_interval' in settings:
                self.fish_tail_interval = settings['fish_tail_interval']
                logging.info(f"设置鱼尾使用间隔: {self.fish_tail_interval}秒")
            if 'click_wait_time' in settings:
                self.click_wait_time = settings['click_wait_time']
                logging.info(f"设置点击等待时间: {self.click_wait_time}秒")
            if 'retry_wait_time' in settings:
                self.retry_wait_time = settings['retry_wait_time']
                logging.info(f"设置重试等待时间: {self.retry_wait_time}秒")
            if 'button_check_interval' in settings:
                self.button_check_interval = settings['button_check_interval']
                logging.info(f"设置按钮检测间隔: {self.button_check_interval}秒")
            if 'auto_fish_tail_enabled' in settings:
                self.auto_fish_tail_enabled = settings['auto_fish_tail_enabled']
                logging.info(f"设置自动使用鱼尾香水: {self.auto_fish_tail_enabled}")
            if 'always_on_top_enabled' in settings:
                self.always_on_top_enabled = settings['always_on_top_enabled']
                logging.info(f"设置窗口置顶: {self.always_on_top_enabled}")
            if 'show_game_window_enabled' in settings:
                self.show_game_window_enabled = settings['show_game_window_enabled']
                logging.info(f"设置显示游戏窗口位置: {self.show_game_window_enabled}")
            if 'click_cooldown' in settings:
                self.click_cooldown = settings['click_cooldown']
            
            logging.info(f"设置更新成功: {settings}")
            self.status_updated.emit("设置更新成功")
            
        except Exception as e:
            logging.error(f"更新设置失败: {e}")
            self.status_updated.emit(f"更新设置失败: {str(e)}")
            raise
    
    def save_config(self, config_name, bag_img=None, fish_img=None, fish_tail_img=None, perfume_img=None, spray_img=None, use_img=None):
        """保存配置"""
        # 只保存位置数据，不保存图像对象
        button_data = {
            'bag_button_pos': self.bag_button_pos,
            'fish_button_pos': self.fish_button_pos,
            'fish_tail_button_pos': self.fish_tail_button_pos,
            'perfume_button_pos': self.perfume_button_pos,
            'spray_button_pos': self.spray_button_pos,
            'use_button_pos': self.use_button_pos,
            'fish_tail_interval': self.fish_tail_interval,
            'perfume_interval': self.perfume_interval,
            'game_window_pos': self.game_window_pos,
            'game_window_size': self.game_window_size,
            'click_wait_time': self.click_wait_time,
            'retry_wait_time': self.retry_wait_time,
            'button_check_interval': self.button_check_interval,
            'auto_fish_tail_enabled': self.auto_fish_tail_enabled,  # 使用实际设置
            'auto_click_enabled': True,      # 默认开启
            'always_on_top_enabled': getattr(self, 'always_on_top_enabled', False),  # 使用实际设置
            'show_game_window_enabled': getattr(self, 'show_game_window_enabled', True)  # 使用实际设置
        }
        
        # 图像文件：只包含有效的图像对象，过滤掉None值
        button_images = {}
        if bag_img is not None:
            button_images['bag_img'] = bag_img
        elif self.bag_button_img is not None:
            button_images['bag_img'] = self.bag_button_img
            
        if fish_img is not None:
            button_images['fish_img'] = fish_img
        elif self.fish_button_img is not None:
            button_images['fish_img'] = self.fish_button_img
            
        if fish_tail_img is not None:
            button_images['fish_tail_img'] = fish_tail_img
        elif self.fish_tail_button_img is not None:
            button_images['fish_tail_img'] = self.fish_tail_button_img
            
        if perfume_img is not None:
            button_images['perfume_img'] = perfume_img
        elif self.perfume_button_img is not None:
            button_images['perfume_img'] = self.perfume_button_img
            
        if spray_img is not None:
            button_images['spray_img'] = spray_img
        elif self.spray_button_img is not None:
            button_images['spray_img'] = self.spray_button_img
            
        if use_img is not None:
            button_images['use_img'] = use_img
        elif self.use_button_img is not None:
            button_images['use_img'] = self.use_button_img
        
        return self.config_manager.save_config(config_name, button_data, button_images)
    
    def load_config(self, config_name):
        """加载配置"""
        # 创建临时数据字典用于加载
        button_data = {}
        
        if self.config_manager.load_config(config_name, button_data):
            # 恢复位置数据
            self.bag_button_pos = button_data.get('bag_button_pos')
            self.fish_button_pos = button_data.get('fish_button_pos')
            self.fish_tail_button_pos = button_data.get('fish_tail_button_pos')
            self.perfume_button_pos = button_data.get('perfume_button_pos')
            self.spray_button_pos = button_data.get('spray_button_pos')
            self.use_button_pos = button_data.get('use_button_pos')
            
            # 确保所有位置数据都是tuple类型
            if self.bag_button_pos and isinstance(self.bag_button_pos, list):
                self.bag_button_pos = tuple(self.bag_button_pos)
            if self.fish_button_pos and isinstance(self.fish_button_pos, list):
                self.fish_button_pos = tuple(self.fish_button_pos)
            if self.fish_tail_button_pos and isinstance(self.fish_tail_button_pos, list):
                self.fish_tail_button_pos = tuple(self.fish_tail_button_pos)
            if self.perfume_button_pos and isinstance(self.perfume_button_pos, list):
                self.perfume_button_pos = tuple(self.perfume_button_pos)
            if self.spray_button_pos and isinstance(self.spray_button_pos, list):
                self.spray_button_pos = tuple(self.spray_button_pos)
            if self.use_button_pos and isinstance(self.use_button_pos, list):
                self.use_button_pos = tuple(self.use_button_pos)
            
            # 恢复游戏窗口信息
            self.game_window_pos = button_data.get('game_window_pos')
            self.game_window_size = button_data.get('game_window_size')
            
            # 确保游戏窗口位置数据是tuple类型
            if self.game_window_pos and isinstance(self.game_window_pos, list):
                logging.info(f"转换游戏窗口位置数据: {type(self.game_window_pos)} -> tuple")
                self.game_window_pos = tuple(self.game_window_pos)
            if self.game_window_size and isinstance(self.game_window_size, list):
                logging.info(f"转换游戏窗口大小数据: {type(self.game_window_size)} -> tuple")
                self.game_window_size = tuple(self.game_window_size)
            
            # 如果游戏窗口信息存在，发送更新信号
            if self.game_window_pos and self.game_window_size:
                self.game_window_position_updated.emit(self.game_window_pos, self.game_window_size)
            
            # 恢复设置
            self.fish_tail_interval = button_data.get('fish_tail_interval', 300)
            self.perfume_interval = button_data.get('perfume_interval', 120)
            self.click_wait_time = button_data.get('click_wait_time', 1.0)
            self.retry_wait_time = button_data.get('retry_wait_time', 2.0)
            self.button_check_interval = button_data.get('button_check_interval', 0.5)
            
            # 恢复自动使用设置
            self.auto_fish_tail_enabled = button_data.get('auto_fish_tail_enabled', True)
            
            # 恢复窗口设置
            self.always_on_top_enabled = button_data.get('always_on_top_enabled', False)
            self.show_game_window_enabled = button_data.get('show_game_window_enabled', True)
            
            # 图像对象会在ConfigManager中自动加载
            self.bag_button_img = button_data.get('bag_button_img')
            self.fish_button_img = button_data.get('fish_button_img')
            self.fish_tail_button_img = button_data.get('fish_tail_button_img')
            self.perfume_button_img = button_data.get('perfume_button_img')
            self.spray_button_img = button_data.get('spray_button_img')
            self.use_button_img = button_data.get('use_button_img')
            
            self.status_updated.emit(f"配置 '{config_name}' 加载成功")
            return True
        
        self.status_updated.emit(f"配置 '{config_name}' 加载失败")
        return False
    
    def delete_config(self, config_name):
        """删除配置"""
        return self.config_manager.delete_config(config_name)
    
    def get_available_configs(self):
        """获取可用配置列表"""
        return self.config_manager.get_available_configs()
    
    def get_game_window_info(self):
        """获取游戏窗口信息"""
        try:
            import win32gui
            import win32con
            
            logging.info("开始查找心动小镇游戏窗口...")
            
            # 查找心动小镇游戏窗口
            def enum_windows_callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    window_text = win32gui.GetWindowText(hwnd)
                    # 记录所有可见窗口（用于调试）
                    if window_text.strip():
                        logging.debug(f"发现窗口: '{window_text}'")
                    
                    # 专门查找心动小镇游戏窗口
                    if any(keyword in window_text for keyword in ['心动小镇', '心动', '小镇', '心动小镇游戏']):
                        windows.append(hwnd)
                        logging.info(f"找到心动小镇游戏窗口: '{window_text}'")
                return True
            
            windows = []
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            logging.info(f"总共找到 {len(windows)} 个心动小镇相关窗口")
            
            if windows:
                hwnd = windows[0]  # 使用第一个匹配的窗口
                rect = win32gui.GetWindowRect(hwnd)
                x, y, right, bottom = rect
                width = right - x
                height = bottom - y
                
                # 更新游戏窗口信息
                self.game_window_pos = (x, y)
                self.game_window_size = (width, height)
                
                # 发送游戏窗口位置更新信号
                self.game_window_position_updated.emit(self.game_window_pos, self.game_window_size)
                
                logging.info(f"获取到心动小镇游戏窗口信息: 位置({x}, {y}), 大小({width}x{height})")
                return True
            else:
                logging.warning("未找到心动小镇游戏窗口，请确保游戏正在运行")
                return False
                
        except ImportError:
            logging.warning("win32gui模块未安装，无法自动获取游戏窗口信息")
            return False
        except Exception as e:
            logging.error(f"获取游戏窗口信息失败: {e}")
            return False
    
