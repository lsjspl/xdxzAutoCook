# -*- coding: utf-8 -*-
"""
绘图助手 - 图片处理模块
负责图片像素化、颜色量化等功能
"""

import logging
import os
import numpy as np
from PIL import Image, ImageDraw
# from sklearn.cluster import KMeans  # 移除sklearn依赖
from collections import Counter

def simple_color_clustering(pixels, n_colors):
    """
    简单的颜色聚类算法，替代sklearn的KMeans
    使用基于距离的聚类方法
    """
    if len(pixels) == 0:
        return []
    
    # 如果像素数量少于目标颜色数，直接返回所有唯一颜色
    unique_colors = np.unique(pixels, axis=0)
    if len(unique_colors) <= n_colors:
        return [tuple(color) for color in unique_colors]
    
    # 随机选择初始聚类中心
    np.random.seed(42)
    centers = pixels[np.random.choice(len(pixels), n_colors, replace=False)]
    
    # 简单的迭代聚类
    for _ in range(10):  # 最多迭代10次
        # 计算每个像素到最近聚类中心的距离
        distances = np.sqrt(((pixels[:, np.newaxis] - centers[np.newaxis, :]) ** 2).sum(axis=2))
        labels = np.argmin(distances, axis=1)
        
        # 更新聚类中心
        new_centers = np.array([pixels[labels == i].mean(axis=0) for i in range(n_colors)])
        
        # 检查收敛
        if np.allclose(centers, new_centers, atol=1):
            break
        centers = new_centers
    
    return [tuple(center.astype(int)) for center in centers]

class ImageProcessor:
    """图片处理类"""
    
    def __init__(self):
        """初始化图片处理器"""
        pass
    
    def pixelize_image(self, image_path, target_width, target_height, color_palette=None):
        """
        像素化图片
        
        Args:
            image_path: 图片路径
            target_width: 目标宽度
            target_height: 目标高度
            color_palette: 颜色调色板，如果提供则使用指定颜色
        
        Returns:
            PIL.Image: 像素化后的图片
        """
        try:
            # 加载图片
            image = Image.open(image_path)
            
            # 转换为RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            logging.info(f"目标像素尺寸: {target_width}×{target_height}")
            
            # 直接调整图片尺寸到目标尺寸
            small_image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            # 如果提供了颜色调色板，进行颜色量化
            if color_palette:
                logging.info(f"使用颜色调色板进行量化，调色板大小: {len(color_palette)}")
                original_mode = small_image.mode
                small_image = self._quantize_to_palette(small_image, color_palette)
                logging.info(f"量化前模式: {original_mode}, 量化后模式: {small_image.mode}")
            else:
                logging.info("未提供颜色调色板，跳过颜色量化")
            
            logging.info(f"图片像素化完成: {target_width}×{target_height}")
            return small_image
            
        except Exception as e:
            logging.error(f"图片像素化失败: {e}")
            return None
    
    def _quantize_to_palette(self, image, color_palette):
        """
        将图片量化到指定的颜色调色板
        
        Args:
            image: PIL图片对象
            color_palette: 颜色调色板 [(r,g,b), ...]
        
        Returns:
            PIL.Image: 量化后的图片
        """
        try:
            logging.info(f"开始颜色量化，调色板包含{len(color_palette)}种颜色")
            logging.debug(f"调色板颜色: {color_palette[:5]}...")  # 只显示前5种颜色
            
            # 确保图片是RGB模式
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # 转换为numpy数组
            img_array = np.array(image)
            height, width, channels = img_array.shape
            
            # 重塑为像素列表
            pixels = img_array.reshape(-1, 3)
            
            # 为每个像素找到最接近的调色板颜色
            quantized_pixels = np.zeros_like(pixels)
            
            # 转换调色板为numpy数组以提高性能
            palette_array = np.array(color_palette)
            
            for i, pixel in enumerate(pixels):
                # 计算与调色板中每种颜色的欧几里得距离
                distances = np.linalg.norm(palette_array - pixel, axis=1)
                # 找到最近的颜色
                closest_color_index = np.argmin(distances)
                quantized_pixels[i] = color_palette[closest_color_index]
            
            # 重塑回图片形状
            quantized_array = quantized_pixels.reshape(height, width, 3)
            
            # 确保数据类型正确
            quantized_array = np.clip(quantized_array, 0, 255).astype(np.uint8)
            
            # 转换回PIL图片
            result_image = Image.fromarray(quantized_array, 'RGB')
            
            logging.info(f"颜色量化完成，图片尺寸: {result_image.size}，模式: {result_image.mode}")
            return result_image
            
        except Exception as e:
            logging.error(f"颜色量化失败: {e}")
            return image
    
    def extract_dominant_colors(self, image, n_colors=16):
        """
        从图片中提取主要颜色
        
        Args:
            image: PIL图片对象
            n_colors: 要提取的颜色数量
        
        Returns:
            list: 颜色列表 [(r,g,b), ...]
        """
        try:
            # 转换为numpy数组
            img_array = np.array(image)
            
            # 重塑为像素列表
            pixels = img_array.reshape(-1, 3)
            
            # 使用简单聚类算法提取主要颜色
            color_list = simple_color_clustering(pixels, n_colors)
            
            logging.info(f"提取了{len(color_list)}种主要颜色")
            return color_list
            
        except Exception as e:
            logging.error(f"提取主要颜色失败: {e}")
            return []
    
    def analyze_color_region(self, screenshot, region_pos):
        """
        分析颜色区域，提取2列8行共16个颜色块的中心点颜色
        
        Args:
            screenshot: 屏幕截图 (PIL Image)
            region_pos: 颜色区域位置 (x, y, width, height)
        
        Returns:
            list: 16个颜色的RGB值 [(r,g,b), ...]
        """
        try:
            x, y, width, height = region_pos
            
            # 裁剪颜色区域
            color_region = screenshot.crop((x, y, x + width, y + height))
            
            # 计算每个颜色块的尺寸
            block_width = width // 2  # 2列
            block_height = height // 8  # 8行
            
            colors = []
            
            # 遍历2列8行
            for row in range(8):
                for col in range(2):
                    # 计算颜色块的位置
                    block_x = col * block_width
                    block_y = row * block_height
                    
                    # 计算中心点位置
                    center_x = block_x + block_width // 2
                    center_y = block_y + block_height // 2
                    
                    # 获取中心点颜色
                    try:
                        color = color_region.getpixel((center_x, center_y))
                        if isinstance(color, int):  # 灰度图
                            color = (color, color, color)
                        elif len(color) == 4:  # RGBA
                            color = color[:3]  # 只取RGB
                        colors.append(color)
                        
                        logging.debug(f"颜色块[{row},{col}]中心点({center_x},{center_y})颜色: {color}")
                    except Exception as e:
                        logging.warning(f"获取颜色块[{row},{col}]颜色失败: {e}")
                        colors.append((128, 128, 128))  # 默认灰色
            
            logging.info(f"成功分析颜色区域，提取了{len(colors)}种颜色")
            return colors
            
        except Exception as e:
            logging.error(f"分析颜色区域失败: {e}")
            return []
    
    def calculate_pixel_size(self, draw_area_size, pixel_image_size):
        """
        计算像素块在绘画区域中的大小
        
        Args:
            draw_area_size: 绘画区域尺寸 (width, height)
            pixel_image_size: 像素化图片尺寸 (width, height)
        
        Returns:
            tuple: 每个像素块的尺寸 (pixel_width, pixel_height)
        """
        draw_width, draw_height = draw_area_size
        pixel_width, pixel_height = pixel_image_size
        
        # 计算每个像素块的尺寸，使用浮点除法确保完全覆盖绘图区域
        block_width = draw_width / pixel_width
        block_height = draw_height / pixel_height
        
        # 确保像素块尺寸至少为1
        block_width = max(1.0, block_width)
        block_height = max(1.0, block_height)
        
        logging.info(f"像素块尺寸: {block_width:.2f}×{block_height:.2f} (浮点像素)")
        return (block_width, block_height)
    
    def get_pixel_positions(self, draw_area_pos, pixel_image, pixel_size):
        """
        获取每个像素块在绘画区域中的位置和颜色（简化累加版）
        
        思路：
        - 从左下角格子的中心点开始计算
        - 其他格子的坐标通过累加格子尺寸得到
        - 使用简单的浮点计算，避免复杂的整数分配
        - 确保每个格子都有合理的尺寸，避免空行
        
        Args:
            draw_area_pos: (x, y, width, height)
            pixel_image: 像素化后的 PIL Image
            pixel_size: 像素块尺寸 (width, height)
        
        Returns:
            list[dict]: [{'position': (x, y), 'color': (r,g,b), 'grid_pos': (gx,gy), 'block_bounds': (left, top, w, h)}]
        """
        try:
            area_x, area_y, area_width, area_height = draw_area_pos
            img_width, img_height = pixel_image.size

            if img_width <= 0 or img_height <= 0 or area_width <= 0 or area_height <= 0:
                logging.error("get_pixel_positions: 输入尺寸非法")
                return []

            # 计算每个格子的尺寸（使用浮点，更精确）
            cell_width = area_width / img_width
            cell_height = area_height / img_height
            
            logging.info(f"简化坐标计算: 网格={img_width}x{img_height}, 格子尺寸={cell_width:.2f}x{cell_height:.2f}")
            
            # 特别针对竖屏比例添加调试信息
            if img_height > img_width:  # 竖屏比例
                logging.info(f"竖屏比例检测: 高度{img_height} > 宽度{img_width}")
                logging.info(f"格子尺寸: 宽度={cell_width:.2f}, 高度={cell_height:.2f}")

            pixel_info = []

            # 从左下角开始，逐行逐列计算坐标
            # 使用高精度计算，确保每个格子都能被准确点击
            # 预计算每行的Y坐标，确保唯一性
            row_y_coords = []
            for gy in range(img_height):
                # 计算每行的Y坐标
                bottom = area_y + area_height - gy * cell_height
                top = area_y + area_height - (gy + 1) * cell_height
                center_y = (top + bottom) / 2.0
                row_y = int(round(center_y))
                row_y_coords.append(row_y)
            
            # 确保每行的Y坐标都是唯一的
            for i in range(1, len(row_y_coords)):
                if row_y_coords[i] == row_y_coords[i-1]:
                    row_y_coords[i] = row_y_coords[i-1] + 1
                    logging.warning(f"行{i}Y坐标与上行相同，强制递增到{row_y_coords[i]}")
            
            logging.info(f"行Y坐标序列: {row_y_coords}")
            
            for gy in range(img_height):  # gy: 网格Y坐标，从下到上
                for gx in range(img_width):  # gx: 网格X坐标，从左到右
                    
                    # 使用高精度浮点计算，避免累积误差
                    # 先计算格子的精确边界
                    left = area_x + gx * cell_width
                    right = area_x + (gx + 1) * cell_width
                    
                    # 计算格子中心点（使用高精度方法）
                    center_x = (left + right) / 2.0
                    
                    # 使用预计算的Y坐标，确保唯一性，并往下偏移1个像素
                    final_x = int(round(center_x))
                    final_y = row_y_coords[gy] + 1
                    
                    # 调试信息：记录每行的Y坐标
                    if gx == 0:  # 每行的第一个点
                        logging.debug(f"行{gy}: Y坐标={final_y}, X坐标={final_x}")
                    
                    # 颜色读取需按图像坐标系翻转Y以保持视觉不倒置
                    color = pixel_image.getpixel((gx, img_height - 1 - gy))
                    if isinstance(color, int):
                        color = (color, color, color)
                    elif len(color) == 4:
                        color = color[:3]

                    pixel_info.append({
                        'position': (final_x, final_y),
                        'color': color,
                        'grid_pos': (gx, gy),
                        'block_bounds': (int(left), int(top), int(right - left), int(bottom - top))
                    })

            # 验证坐标的唯一性和准确性
            positions = [info['position'] for info in pixel_info]
            unique_positions = set(positions)
            if len(positions) != len(unique_positions):
                logging.warning(f"检测到重复坐标: 总坐标{len(positions)}个，唯一坐标{len(unique_positions)}个")
                # 找出重复的坐标

                position_counts = Counter(positions)
                duplicates = [(pos, count) for pos, count in position_counts.items() if count > 1]
                if duplicates:
                    logging.warning(f"重复坐标详情: {duplicates[:5]}")  # 只显示前5个
            
            # 检查Y坐标的单调性（应该从下到上递减）
            y_coords = [info['position'][1] for info in pixel_info[0::img_width]]  # 每行首点Y
            if y_coords != sorted(y_coords, reverse=True):
                logging.warning("Y坐标不是单调递减的，可能存在空行问题")
                logging.warning(f"Y坐标序列: {y_coords}")
            
            # 检查X坐标的单调性（应该从左到右递增）
            x_coords = [info['position'][0] for info in pixel_info[:img_width]]  # 第一行所有X
            if x_coords != sorted(x_coords):
                logging.warning("X坐标不是单调递增的，可能存在空列问题")
                logging.warning(f"X坐标序列: {x_coords}")
            
            # 检查坐标范围是否在绘画区域内
            all_x = [pos[0] for pos in positions]
            all_y = [pos[1] for pos in positions]
            if all_x and (min(all_x) < area_x or max(all_x) >= area_x + area_width):
                logging.warning(f"X坐标超出绘画区域: 范围[{min(all_x)}, {max(all_x)}], 绘画区域[{area_x}, {area_x + area_width})")
            if all_y and (min(all_y) < area_y or max(all_y) >= area_y + area_height):
                logging.warning(f"Y坐标超出绘画区域: 范围[{min(all_y)}, {max(all_y)}], 绘画区域[{area_y}, {area_y + area_height})")

            logging.info(f"生成像素点完成：共{len(pixel_info)}个，使用高精度累加算法")
            return pixel_info

        except Exception as e:
            logging.error(f"获取像素位置失败: {e}")
            return []


    def _fix_duplicate_positions(self, pixel_info, draw_area_pos, block_width, block_height):
        """
        修复重复的像素位置
        
        Args:
            pixel_info: 原始像素信息列表
            draw_area_pos: 绘画区域位置
            block_width: 像素块宽度
            block_height: 像素块高度
        
        Returns:
            list: 修复后的像素信息列表
        """
        try:
            area_x, area_y, area_width, area_height = draw_area_pos
            used_positions = set()
            fixed_pixel_info = []
            skipped_count = 0
            fixed_count = 0
            
            logging.info(f"开始修复重复位置，原始像素数量: {len(pixel_info)}")
            logging.info(f"绘画区域: ({area_x}, {area_y}, {area_width}, {area_height})")
            logging.info(f"像素块尺寸: {block_width}×{block_height}")
            
            for info in pixel_info:
                grid_x, grid_y = info['grid_pos']
                original_pos = info['position']
                
                # 如果位置已被使用，尝试找到附近的有效位置
                if original_pos in used_positions:
                    # 在像素块范围内寻找可用位置
                    pixel_left = area_x + grid_x * block_width
                    pixel_top = area_y + grid_y * block_height
                    
                    # 尝试更多的偏移位置，确保能找到可用位置
                    offsets = [
                        (0, 0),  # 中心
                        (1, 0), (0, 1), (-1, 0), (0, -1),  # 上下左右
                        (1, 1), (-1, 1), (1, -1), (-1, -1),  # 对角线
                        (2, 0), (0, 2), (-2, 0), (0, -2),  # 更远的上下左右
                        (1, 2), (2, 1), (-1, 2), (2, -1),  # 更远的对角线
                        (-1, -2), (-2, -1), (1, -2), (-2, 1)
                    ]
                    
                    new_pos = None
                    for offset_x, offset_y in offsets:
                        test_x = pixel_left + block_width // 2 + offset_x
                        test_y = pixel_top + block_height // 2 + offset_y
                        
                        # 确保在边界内
                        test_x = max(area_x, min(test_x, area_x + area_width - 1))
                        test_y = max(area_y, min(test_y, area_y + area_height - 1))
                        
                        test_pos = (test_x, test_y)
                        if test_pos not in used_positions:
                            new_pos = test_pos
                            break
                    
                    if new_pos:
                        info['position'] = new_pos
                        fixed_count += 1
                        logging.debug(f"修复重复位置: ({grid_x}, {grid_y}) {original_pos} -> {new_pos}")
                    else:
                        skipped_count += 1
                        logging.warning(f"无法找到可用位置，跳过像素 ({grid_x}, {grid_y}) 原始位置: {original_pos}")
                        continue
                
                used_positions.add(info['position'])
                fixed_pixel_info.append(info)
            
            logging.info(f"位置修复完成:")
            logging.info(f"  - 原始像素数量: {len(pixel_info)}")
            logging.info(f"  - 修复位置数量: {fixed_count}")
            logging.info(f"  - 跳过像素数量: {skipped_count}")
            logging.info(f"  - 最终像素数量: {len(fixed_pixel_info)}")
            
            if skipped_count > 0:
                logging.warning(f"警告：跳过了{skipped_count}个像素点，这可能导致绘图不完整！")
            
            return fixed_pixel_info
            
        except Exception as e:
            logging.error(f"修复重复位置失败: {e}")
            return pixel_info
    
    def find_closest_color_index(self, target_color, color_palette):
        """
        在颜色调色板中找到最接近目标颜色的索引
        
        Args:
            target_color: 目标颜色 (r, g, b)
            color_palette: 颜色调色板 [(r, g, b), ...]
        
        Returns:
            int: 最接近颜色的索引
        """
        try:
            target = np.array(target_color)
            distances = [np.linalg.norm(target - np.array(color)) for color in color_palette]
            return np.argmin(distances)
        except Exception as e:
            logging.error(f"查找最接近颜色失败: {e}")
            return 0
    
    def create_preview_image(self, pixel_info, draw_area_size, pixel_size):
        """
        创建绘图预览图片
        
        Args:
            pixel_info: 像素信息列表
            draw_area_size: 绘画区域尺寸
            pixel_size: 像素块尺寸
        
        Returns:
            PIL.Image: 预览图片
        """
        try:
            width, height = draw_area_size
            preview = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(preview)
            
            # 使用整数像素块尺寸，与get_pixel_positions保持一致
            block_width = int(pixel_size[0] + 0.99)
            block_height = int(pixel_size[1] + 0.99)
            
            for info in pixel_info:
                grid_x, grid_y = info['grid_pos']
                color = info['color']
                
                # 使用block_bounds信息（如果可用）或重新计算
                if 'block_bounds' in info:
                    left, top, w, h = info['block_bounds']
                    right = left + w
                    bottom = top + h
                else:
                    # 重新计算矩形位置
                    left = int(grid_x * block_width)
                    top = int(grid_y * block_height)
                    right = left + block_width
                    bottom = top + block_height
                
                # 确保矩形不超出预览图片边界
                right = min(right, width)
                bottom = min(bottom, height)
                left = max(0, left)
                top = max(0, top)
                
                # 绘制矩形
                draw.rectangle([left, top, right, bottom], fill=color, outline='black')
            
            return preview
            
        except Exception as e:
            logging.error(f"创建预览图片失败: {e}")
            return None


if __name__ == "__main__":
    # 测试代码
    processor = ImageProcessor()
    
    # 测试像素化
    test_image = "test.jpg"
    if os.path.exists(test_image):
        pixelized = processor.pixelize_image(test_image, (1, 1), 50)
        if pixelized:
            pixelized.save("test_pixelized.png")
            logging.info("像素化测试完成")
    else:
        logging.warning("测试图片不存在")