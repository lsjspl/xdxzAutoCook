# -*- coding: utf-8 -*-
"""
钓鱼助手 - 配置管理模块
负责配置的保存、加载、删除等管理功能
"""

import os
import json
import logging
from PIL import Image


class ConfigManager:
    """配置管理类"""
    
    def __init__(self, configs_dir="configs", configs_img_dir="configs/images"):
        """初始化配置管理器"""
        self.configs_dir = configs_dir
        self.configs_img_dir = configs_img_dir
        
        # 确保配置目录存在
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
        if not os.path.exists(self.configs_img_dir):
            os.makedirs(self.configs_img_dir)
    
    def save_config(self, config_name, button_data, button_images):
        """保存配置"""
        try:
            config_data = {
                'bag_button_pos': button_data.get('bag_button_pos'),
                'fish_button_pos': button_data.get('fish_button_pos'),
                'fish_tail_button_pos': button_data.get('fish_tail_button_pos'),
                'perfume_button_pos': button_data.get('perfume_button_pos'),
                'spray_button_pos': button_data.get('spray_button_pos'),
                'use_button_pos': button_data.get('use_button_pos'),
                'fish_tail_interval': button_data.get('fish_tail_interval', 300),
                'perfume_interval': button_data.get('perfume_interval', 120),
                'game_window_pos': button_data.get('game_window_pos'),
                'game_window_size': button_data.get('game_window_size'),
                'click_wait_time': button_data.get('click_wait_time', 1.0),
                'retry_wait_time': button_data.get('retry_wait_time', 2.0),
                'button_check_interval': button_data.get('button_check_interval', 0.5),
                'auto_fish_tail_enabled': button_data.get('auto_fish_tail_enabled', True),
                'auto_click_enabled': button_data.get('auto_click_enabled', True),
                'always_on_top_enabled': button_data.get('always_on_top_enabled', False),
                'show_game_window_enabled': button_data.get('show_game_window_enabled', True)
            }
            
            # 保存配置文件
            config_file = os.path.join(self.configs_dir, f"{config_name}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            # 保存图像文件 - 使用传入的图像参数
            if button_images.get('bag_img') is not None:
                bag_img_path = os.path.join(self.configs_img_dir, f"{config_name}_bag.png")
                button_images['bag_img'].save(bag_img_path)
                logging.info(f"保存背包图像: {bag_img_path}")
            
            if button_images.get('fish_img') is not None:
                fish_img_path = os.path.join(self.configs_img_dir, f"{config_name}_fish.png")
                button_images['fish_img'].save(fish_img_path)
                logging.info(f"保存钓鱼图像: {fish_img_path}")
            
            if button_images.get('fish_tail_img') is not None:
                fish_tail_img_path = os.path.join(self.configs_img_dir, f"{config_name}_fish_tail.png")
                button_images['fish_tail_img'].save(fish_tail_img_path)
                logging.info(f"保存鱼尾图像: {fish_tail_img_path}")
            
            if button_images.get('perfume_img') is not None:
                perfume_img_path = os.path.join(self.configs_img_dir, f"{config_name}_perfume.png")
                button_images['perfume_img'].save(perfume_img_path)
                logging.info(f"保存香水图像: {perfume_img_path}")
            
            if button_images.get('spray_img') is not None:
                spray_img_path = os.path.join(self.configs_img_dir, f"{config_name}_spray.png")
                button_images['spray_img'].save(spray_img_path)
                logging.info(f"保存喷雾图像: {spray_img_path}")
            
            if button_images.get('use_img') is not None:
                use_img_path = os.path.join(self.configs_img_dir, f"{config_name}_use.png")
                button_images['use_img'].save(use_img_path)
                logging.info(f"保存使用图像: {use_img_path}")
            
            logging.info(f"配置 '{config_name}' 保存成功")
            return True
            
        except Exception as e:
            logging.error(f"保存配置时发生错误: {e}")
            return False
    
    def load_config(self, config_name, button_data):
        """加载配置"""
        try:
            config_file = os.path.join(self.configs_dir, f"{config_name}.json")
            if not os.path.exists(config_file):
                return False
            
            # 加载配置文件
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 恢复配置 - 转换位置数据为tuple类型
            bag_pos = config_data.get('bag_button_pos')
            if bag_pos and isinstance(bag_pos, list):
                button_data['bag_button_pos'] = tuple(bag_pos)
            else:
                button_data['bag_button_pos'] = bag_pos
                
            fish_pos = config_data.get('fish_button_pos')
            if fish_pos and isinstance(fish_pos, list):
                button_data['fish_button_pos'] = tuple(fish_pos)
            else:
                button_data['fish_button_pos'] = fish_pos
                
            fish_tail_pos = config_data.get('fish_tail_button_pos')
            if fish_tail_pos and isinstance(fish_tail_pos, list):
                button_data['fish_tail_button_pos'] = tuple(fish_tail_pos)
            else:
                button_data['fish_tail_button_pos'] = fish_tail_pos
                
            perfume_pos = config_data.get('perfume_button_pos')
            if perfume_pos and isinstance(perfume_pos, list):
                button_data['perfume_button_pos'] = tuple(perfume_pos)
            else:
                button_data['perfume_button_pos'] = perfume_pos
                
            spray_pos = config_data.get('spray_button_pos')
            if spray_pos and isinstance(spray_pos, list):
                button_data['spray_button_pos'] = tuple(spray_pos)
            else:
                button_data['spray_button_pos'] = spray_pos
                
            use_pos = config_data.get('use_button_pos')
            if use_pos and isinstance(use_pos, list):
                button_data['use_button_pos'] = tuple(use_pos)
            else:
                button_data['use_button_pos'] = use_pos
                
            button_data['fish_tail_interval'] = config_data.get('fish_tail_interval', 300)
            button_data['perfume_interval'] = config_data.get('perfume_interval', 120)
            button_data['click_wait_time'] = config_data.get('click_wait_time', 1.0)
            button_data['retry_wait_time'] = config_data.get('retry_wait_time', 2.0)
            button_data['button_check_interval'] = config_data.get('button_check_interval', 0.5)
            button_data['auto_fish_tail_enabled'] = config_data.get('auto_fish_tail_enabled', True)
            button_data['auto_click_enabled'] = config_data.get('auto_click_enabled', True)
            button_data['always_on_top_enabled'] = config_data.get('always_on_top_enabled', False)
            button_data['show_game_window_enabled'] = config_data.get('show_game_window_enabled', True)
            
            # 转换游戏窗口位置数据为tuple类型
            game_window_pos = config_data.get('game_window_pos')
            if game_window_pos and isinstance(game_window_pos, list):
                button_data['game_window_pos'] = tuple(game_window_pos)
            else:
                button_data['game_window_pos'] = game_window_pos
                
            game_window_size = config_data.get('game_window_size')
            if game_window_size and isinstance(game_window_size, list):
                button_data['game_window_size'] = tuple(game_window_size)
            else:
                button_data['game_window_size'] = game_window_size
            
            # 加载图像文件
            bag_img_path = os.path.join(self.configs_img_dir, f"{config_name}_bag.png")
            if os.path.exists(bag_img_path):
                button_data['bag_button_img'] = Image.open(bag_img_path)
                logging.info(f"加载背包图像: {bag_img_path}")
            
            fish_img_path = os.path.join(self.configs_img_dir, f"{config_name}_fish.png")
            if os.path.exists(fish_img_path):
                button_data['fish_button_img'] = Image.open(fish_img_path)
                logging.info(f"加载钓鱼图像: {fish_img_path}")
            
            fish_tail_img_path = os.path.join(self.configs_img_dir, f"{config_name}_fish_tail.png")
            if os.path.exists(fish_tail_img_path):
                button_data['fish_tail_button_img'] = Image.open(fish_tail_img_path)
                logging.info(f"加载鱼尾图像: {fish_tail_img_path}")
            
            perfume_img_path = os.path.join(self.configs_img_dir, f"{config_name}_perfume.png")
            if os.path.exists(perfume_img_path):
                button_data['perfume_button_img'] = Image.open(perfume_img_path)
                logging.info(f"加载香水图像: {perfume_img_path}")
            
            spray_img_path = os.path.join(self.configs_img_dir, f"{config_name}_spray.png")
            if os.path.exists(spray_img_path):
                button_data['spray_button_img'] = Image.open(spray_img_path)
                logging.info(f"加载喷雾图像: {spray_img_path}")
            else:
                logging.warning(f"喷雾图像文件不存在: {spray_img_path}")
            
            use_img_path = os.path.join(self.configs_img_dir, f"{config_name}_use.png")
            if os.path.exists(use_img_path):
                button_data['use_button_img'] = Image.open(use_img_path)
                logging.info(f"加载使用图像: {use_img_path}")
            else:
                logging.warning(f"使用图像文件不存在: {use_img_path}")
            
            logging.info(f"配置 '{config_name}' 加载成功")
            return True
            
        except Exception as e:
            logging.error(f"加载配置时发生错误: {e}")
            return False
    
    def delete_config(self, config_name):
        """删除配置"""
        try:
            # 删除配置文件
            config_file = os.path.join(self.configs_dir, f"{config_name}.json")
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # 删除图像文件
            for suffix in ['_bag.png', '_fish.png', '_fish_tail.png', '_perfume.png', '_spray.png', '_use.png']:
                img_file = os.path.join(self.configs_img_dir, f"{config_name}{suffix}")
                if os.path.exists(img_file):
                    os.remove(img_file)
            
            # 从主配置文件中删除配置项
            main_config_file = os.path.join(self.configs_dir, "configs.json")
            if os.path.exists(main_config_file):
                with open(main_config_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                
                # 删除指定配置
                if config_name in configs_data:
                    del configs_data[config_name]
                    
                    # 保存更新后的配置文件
                    with open(main_config_file, 'w', encoding='utf-8') as f:
                        json.dump(configs_data, f, ensure_ascii=False, indent=4)
            
            logging.info(f"配置 '{config_name}' 删除成功")
            return True
            
        except Exception as e:
            logging.error(f"删除配置时发生错误: {e}")
            return False
    
    def get_available_configs(self):
        """获取可用配置列表"""
        try:
            configs = []
            if os.path.exists(self.configs_dir):
                for file in os.listdir(self.configs_dir):
                    if file.endswith('.json'):
                        config_name = file[:-5]  # 移除.json后缀
                        configs.append(config_name)
            return sorted(configs)
        except Exception as e:
            logging.error(f"获取配置列表时发生错误: {e}")
            return []
    
    def validate_button_position(self, button_name, position_data):
        """验证按钮位置数据格式"""
        try:
            if position_data is None:
                logging.warning(f"{button_name}位置数据为空")
                return False
            
            if not isinstance(position_data, (list, tuple)):
                logging.error(f"{button_name}位置数据格式错误: {type(position_data)}, 值: {position_data}")
                return False
            
            if len(position_data) != 4:
                logging.error(f"{button_name}位置数据长度错误: {len(position_data)}, 值: {position_data}")
                return False
            
            # 检查所有值都是数字
            for i, val in enumerate(position_data):
                if not isinstance(val, (int, float)):
                    logging.error(f"{button_name}位置数据[{i}]不是数字: {type(val)}, 值: {val}")
                    return False
            
            # 检查宽度和高度是否为正数
            x, y, w, h = position_data
            if w <= 0 or h <= 0:
                logging.error(f"{button_name}尺寸无效: 宽度={w}, 高度={h}")
                return False
            
            # 检查坐标是否在合理范围内
            if x < -1000 or y < -1000 or x > 3000 or y > 3000:
                logging.warning(f"{button_name}坐标超出合理范围: ({x}, {y})")
            
            logging.info(f"{button_name}位置数据验证通过: {position_data}")
            return True
            
        except Exception as e:
            logging.error(f"验证{button_name}位置数据时发生错误: {e}")
            return False
