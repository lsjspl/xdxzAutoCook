# -*- coding: utf-8 -*-
"""
钓鱼助手 - 图像检测模块
负责图像检测、按钮识别、模板匹配等核心检测功能
"""

import cv2
import numpy as np
import logging


class ImageDetector:
    """图像检测类"""
    
    def __init__(self):
        """初始化图像检测器"""
        pass
    
    def detect_button(self, screen_img, button_img):
        """检测按钮位置 - 基于坐标位置的检测"""
        if screen_img is None or button_img is None:
            return None
        
        try:
            # 转换为OpenCV格式
            screen_cv = cv2.cvtColor(np.array(screen_img), cv2.COLOR_RGB2BGR)
            button_cv = cv2.cvtColor(np.array(button_img), cv2.COLOR_RGB2BGR)
            
            # 模板匹配
            result = cv2.matchTemplate(screen_cv, button_cv, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
            
            # 降低置信度阈值，使检测更容易成功
            threshold = 0.5
            if max_val >= threshold:
                logging.info(f"按钮检测成功，置信度: {max_val:.3f}，位置: {max_loc}")
                return max_loc, max_val
            else:
                logging.info(f"按钮检测失败，最高置信度: {max_val:.3f}，阈值: {threshold}")
            
            return None
            
        except Exception as e:
            logging.error(f"按钮检测时发生错误: {e}")
            return None
    
    def detect_use_button_in_region(self, region_image, offset_x, offset_y):
        """在指定区域检测使用按钮"""
        try:
            # 转换为OpenCV格式
            region_cv = cv2.cvtColor(np.array(region_image), cv2.COLOR_RGB2BGR)
            
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(region_cv, cv2.COLOR_BGR2HSV)
            
            # 定义蓝色范围（使用按钮通常是蓝色）
            lower_blue = np.array([100, 50, 50])
            upper_blue = np.array([130, 255, 255])
            
            # 创建蓝色掩码
            mask = cv2.inRange(hsv, lower_blue, upper_blue)
            
            # 查找轮廓
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                # 计算轮廓面积
                area = cv2.contourArea(contour)
                if 500 < area < 5000:  # 过滤掉太小或太大的区域
                    # 获取边界矩形
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # 检查长宽比
                    aspect_ratio = w / h
                    if 1.5 < aspect_ratio < 4.0:  # 使用按钮通常是矩形
                        # 计算在原图中的位置
                        abs_x = offset_x + x
                        abs_y = offset_y + y
                        
                        # 计算置信度（基于面积和长宽比）
                        confidence = min(0.9, area / 3000.0 + 0.3)
                        
                        return (abs_x, abs_y, w, h), confidence
            
            return None
            
        except Exception as e:
            logging.error(f"检测使用按钮时发生错误: {e}")
            return None
    
    def detect_spray_button_in_region(self, perfume_region_img):
        """在香水按钮区域检测喷雾按钮（使用按钮）"""
        try:
            if perfume_region_img is None:
                return None
            
            # 转换为OpenCV格式
            region_cv = cv2.cvtColor(np.array(perfume_region_img), cv2.COLOR_RGB2BGR)
            
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(region_cv, cv2.COLOR_BGR2HSV)
            
            # 定义多个蓝色范围（喷雾按钮可能是不同深浅的蓝色）
            blue_ranges = [
                # 深蓝色
                (np.array([100, 50, 50]), np.array([130, 255, 255])),
                # 浅蓝色
                (np.array([90, 30, 100]), np.array([120, 255, 255])),
                # 蓝绿色
                (np.array([80, 50, 50]), np.array([110, 255, 255]))
            ]
            
            best_button = None
            best_score = 0
            
            for i, (lower_blue, upper_blue) in enumerate(blue_ranges):
                # 创建蓝色掩码
                mask = cv2.inRange(hsv, lower_blue, upper_blue)
                
                # 查找轮廓
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    # 计算轮廓面积
                    area = cv2.contourArea(contour)
                    
                    # 放宽面积限制
                    if 100 < area < 10000:  # 扩大面积范围
                        # 获取边界矩形
                        x, y, w, h = cv2.boundingRect(contour)
                        
                        # 检查长宽比（放宽限制）
                        aspect_ratio = w / h
                        if 0.8 < aspect_ratio < 5.0:  # 放宽长宽比限制
                            # 计算中心点
                            center_x = x + w // 2
                            center_y = y + h // 2
                            
                            # 计算按钮质量分数（面积越大，长宽比越接近2:1越好）
                            ideal_ratio = 2.0
                            ratio_score = 1.0 / (1.0 + abs(aspect_ratio - ideal_ratio))
                            area_score = min(area / 2000, 1.0)  # 标准化面积分数
                            total_score = ratio_score * area_score
                            
                            if total_score > best_score:
                                best_score = total_score
                                best_button = (center_x, center_y, area, aspect_ratio)
            
            if best_button:
                center_x, center_y, area, aspect_ratio = best_button
                logging.info(f"✅ 检测到喷雾按钮，位置: ({center_x}, {center_y}), 面积: {area}, 长宽比: {aspect_ratio:.2f}, 分数: {best_score:.3f}")
                return center_x, center_y
            else:
                logging.info("❌ 未检测到喷雾按钮")
                return None
            
        except Exception as e:
            logging.error(f"检测喷雾按钮失败: {e}")
            return None
    
    def detect_use_button_in_region(self, fish_tail_region_img):
        """在鱼尾按钮区域检测使用按钮"""
        try:
            if fish_tail_region_img is None:
                return None
            
            # 转换为OpenCV格式
            region_cv = cv2.cvtColor(np.array(fish_tail_region_img), cv2.COLOR_RGB2BGR)
            
            # 转换为HSV颜色空间
            hsv = cv2.cvtColor(region_cv, cv2.COLOR_BGR2HSV)
            
            # 定义多个绿色范围（使用按钮可能是不同深浅的绿色）
            green_ranges = [
                # 深绿色
                (np.array([40, 50, 50]), np.array([80, 255, 255])),
                # 浅绿色
                (np.array([35, 30, 100]), np.array([85, 255, 255])),
                # 黄绿色
                (np.array([30, 50, 50]), np.array([70, 255, 255]))
            ]
            
            best_button = None
            best_score = 0
            
            for i, (lower_green, upper_green) in enumerate(green_ranges):
                # 创建绿色掩码
                mask = cv2.inRange(hsv, lower_green, upper_green)
                
                # 查找轮廓
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    # 计算轮廓面积
                    area = cv2.contourArea(contour)
                    
                    # 放宽面积限制
                    if 100 < area < 10000:  # 扩大面积范围
                        # 获取边界矩形
                        x, y, w, h = cv2.boundingRect(contour)
                        
                        # 检查长宽比（放宽限制）
                        aspect_ratio = w / h
                        if 0.8 < aspect_ratio < 5.0:  # 放宽长宽比限制
                            # 计算中心点
                            center_x = x + w // 2
                            center_y = y + h // 2
                            
                            # 计算按钮质量分数（面积越大，长宽比越接近2:1越好）
                            ideal_ratio = 2.0
                            ratio_score = 1.0 / (1.0 + abs(aspect_ratio - ideal_ratio))
                            area_score = min(area / 2000, 1.0)  # 标准化面积分数
                            total_score = ratio_score * area_score
                            
                            if total_score > best_score:
                                best_score = total_score
                                best_button = (center_x, center_y, area, aspect_ratio)
            
            if best_button:
                center_x, center_y, area, aspect_ratio = best_button
                logging.info(f"✅ 检测到使用按钮，位置: ({center_x}, {center_y}), 面积: {area}, 长宽比: {aspect_ratio:.2f}, 分数: {best_score:.3f}")
                return center_x, center_y
            else:
                logging.info("❌ 未检测到使用按钮")
                return None
            
        except Exception as e:
            logging.error(f"检测使用按钮失败: {e}")
            return None
