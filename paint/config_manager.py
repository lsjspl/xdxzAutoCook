# -*- coding: utf-8 -*-
"""
绘图助手 - 配置管理模块
负责配置的保存、加载、删除等管理功能
"""

import os
import json
import logging


class ConfigManager:
    """配置管理类"""
    
    def __init__(self, configs_dir="paint_configs", configs_img_dir="paint_configs/images"):
        """初始化配置管理器"""
        self.configs_dir = configs_dir
        self.configs_img_dir = configs_img_dir
        
        # 确保配置目录存在
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
        if not os.path.exists(self.configs_img_dir):
            os.makedirs(self.configs_img_dir)
    
    def save_config(self, config_name, config_data):
        """保存配置"""
        try:
            # 保存配置文件
            config_file = os.path.join(self.configs_dir, f"{config_name}.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"配置 '{config_name}' 保存成功: {config_file}")
            return True
            
        except Exception as e:
            logging.error(f"保存配置失败: {e}")
            return False
    
    def load_config(self, config_name):
        """加载配置"""
        try:
            config_file = os.path.join(self.configs_dir, f"{config_name}.json")
            if not os.path.exists(config_file):
                logging.warning(f"配置文件不存在: {config_file}")
                return None
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            logging.info(f"配置 '{config_name}' 加载成功")
            return config_data
            
        except Exception as e:
            logging.error(f"加载配置失败: {e}")
            return None
    
    def delete_config(self, config_name):
        """删除配置"""
        try:
            config_file = os.path.join(self.configs_dir, f"{config_name}.json")
            if os.path.exists(config_file):
                os.remove(config_file)
                logging.info(f"配置 '{config_name}' 删除成功")
                return True
            else:
                logging.warning(f"配置文件不存在: {config_file}")
                return False
                
        except Exception as e:
            logging.error(f"删除配置失败: {e}")
            return False
    
    def get_config_list(self):
        """获取配置列表"""
        try:
            configs = []
            if os.path.exists(self.configs_dir):
                for filename in os.listdir(self.configs_dir):
                    if filename.endswith('.json'):
                        config_name = filename[:-5]  # 去掉.json后缀
                        configs.append(config_name)
            
            configs.sort()  # 按名称排序
            logging.info(f"获取到 {len(configs)} 个配置")
            return configs
            
        except Exception as e:
            logging.error(f"获取配置列表失败: {e}")
            return []
    
    def config_exists(self, config_name):
        """检查配置是否存在"""
        config_file = os.path.join(self.configs_dir, f"{config_name}.json")
        return os.path.exists(config_file)
