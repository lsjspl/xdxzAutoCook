# -*- coding: utf-8 -*-
"""
绘图助手 - 图片处理模块
负责图片像素化、颜色量化等功能
"""

import logging
import numpy as np
from PIL import Image, ImageDraw
from sklearn.cluster import KMeans


class ImageProcessor:
    """图片处理类"""
    
    def __init__(self):
        """初始化图片处理器"""
        pass
    
    def pixelize_image(self, image_path, aspect_ratio, pixel_count, color_palette=None):
        """
        像素化图片
        
        Args:
            image_path: 图片路径
            aspect_ratio: 宽高比例 (width_ratio, height_ratio)
            pixel_count: 横向像素数量
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
            
            # 计算目标尺寸
            width_ratio, height_ratio = aspect_ratio
            target_width = pixel_count
            target_height = int(pixel_count * height_ratio / width_ratio)
            
            logging.info(f"目标像素尺寸: {target_width}×{target_height}")
            
            # 调整图片尺寸以匹配目标比例
            image = self._resize_to_aspect_ratio(image, width_ratio, height_ratio)
            
            # 缩小到目标像素尺寸
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
    
    def _resize_to_aspect_ratio(self, image, width_ratio, height_ratio):
        """
        调整图片尺寸以匹配目标宽高比
        
        Args:
            image: PIL图片对象
            width_ratio: 宽度比例
            height_ratio: 高度比例
        
        Returns:
            PIL.Image: 调整后的图片
        """
        original_width, original_height = image.size
        target_ratio = width_ratio / height_ratio
        current_ratio = original_width / original_height
        
        if current_ratio > target_ratio:
            # 图片太宽，需要裁剪宽度
            new_width = int(original_height * target_ratio)
            left = (original_width - new_width) // 2
            image = image.crop((left, 0, left + new_width, original_height))
        elif current_ratio < target_ratio:
            # 图片太高，需要裁剪高度
            new_height = int(original_width / target_ratio)
            top = (original_height - new_height) // 2
            image = image.crop((0, top, original_width, top + new_height))
        
        return image
    
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
            
            # 使用K-means聚类提取主要颜色
            kmeans = KMeans(n_clusters=n_colors, random_state=42, n_init=10)
            kmeans.fit(pixels)
            
            # 获取聚类中心（主要颜色）
            colors = kmeans.cluster_centers_.astype(int)
            
            # 转换为元组列表
            color_list = [tuple(color) for color in colors]
            
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
        获取每个像素块在绘画区域中的位置和颜色
        
        Args:
            draw_area_pos: 绘画区域位置 (x, y, width, height)
            pixel_image: 像素化图片
            pixel_size: 像素块尺寸 (width, height)
        
        Returns:
            list: 像素信息列表 [{'position': (x, y), 'color': (r, g, b)}, ...]
        """
        try:
            area_x, area_y, area_width, area_height = draw_area_pos
            block_width, block_height = pixel_size
            
            pixel_info = []
            img_width, img_height = pixel_image.size
            
            for y in range(img_height):
                for x in range(img_width):
                    # 获取像素颜色
                    color = pixel_image.getpixel((x, y))
                    if isinstance(color, int):  # 灰度图
                        color = (color, color, color)
                    elif len(color) == 4:  # RGBA
                        color = color[:3]  # 只取RGB
                    
                    # 计算在绘画区域中的位置（像素块中心点）
                    # 使用浮点像素块尺寸，确保完全覆盖绘图区域
                    pixel_x = area_x + x * block_width + block_width / 2
                    pixel_y = area_y + y * block_height + block_height / 2
                    
                    # 确保像素位置不超出绘图区域边界
                    pixel_x = min(pixel_x, area_x + area_width - 1)
                    pixel_y = min(pixel_y, area_y + area_height - 1)
                    
                    pixel_info.append({
                        'position': (int(pixel_x), int(pixel_y)),
                        'color': color,
                        'grid_pos': (x, y)
                    })
            
            logging.info(f"生成了{len(pixel_info)}个像素点位置信息")
            return pixel_info
            
        except Exception as e:
            logging.error(f"获取像素位置失败: {e}")
            return []
    
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
            
            block_width, block_height = pixel_size
            
            for info in pixel_info:
                grid_x, grid_y = info['grid_pos']
                color = info['color']
                
                # 计算矩形位置，使用浮点像素块尺寸确保完全覆盖
                left = int(grid_x * block_width)
                top = int(grid_y * block_height)
                right = int((grid_x + 1) * block_width)
                bottom = int((grid_y + 1) * block_height)
                
                # 确保矩形不超出预览图片边界
                right = min(right, width)
                bottom = min(bottom, height)
                
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