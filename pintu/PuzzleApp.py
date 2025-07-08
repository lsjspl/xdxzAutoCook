import sys, json
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QLabel, QComboBox, QGroupBox, QMessageBox,
                             QSizePolicy, QInputDialog, QLineEdit)
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QColor, QPen
from PyQt5.QtCore import Qt, QSize, QDir, QTimer
from PIL import Image
import cv2
import numpy as np
from screen_cropper import crop_screen_region, crop_interactive_region
from mapping_overlay import create_mapping_overlay
import os
from datetime import datetime

def pil_to_qpixmap(pil_img):
    """Convert PIL image to QPixmap."""
    # 直接使用原始颜色，不进行BGR/RGB转换
    if pil_img.mode == "RGBA":
        img_format = QImage.Format_ARGB32
    else:
        # 确保是RGB模式
        if pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        img_format = QImage.Format_RGB888
        
    image = QImage(pil_img.tobytes(), pil_img.width, pil_img.height, pil_img.width * len(pil_img.getbands()), img_format)
    return QPixmap.fromImage(image)

class PuzzleApp(QWidget):
    def __init__(self):
        super().__init__()
        # 设置主界面窗口始终置顶
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("🧩 拼图匹配工具（交互式截图）")

        self.reference_img = None
        self.puzzle_img = None
        self.mapping_area = None
        self.mapping_overlay = None
        self.cropper = None # To hold reference to the cropper widget
        
        # 添加拼图区域坐标和定时器
        self.puzzle_region = None  # 保存拼图区域坐标 (x, y, width, height)
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self.auto_detect_and_match)
        self.is_detecting = False
        
        self.configs_dir = os.path.join("pintu", "configs")
        self.configs_img_dir = os.path.join(self.configs_dir, "images")
        if not os.path.exists(self.configs_dir):
            os.makedirs(self.configs_dir)
        if not os.path.exists(self.configs_img_dir):
            os.makedirs(self.configs_img_dir)

        # 不再创建截图目录，因为不再保存截图到本地

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)  # 减少主布局边距
        main_layout.setSpacing(8)  # 减少主布局间距

        # --- Config Management UI ---
        config_group = QGroupBox("配置管理")
        config_layout = QHBoxLayout()
        self.config_combo = QComboBox()
        config_layout.addWidget(self.config_combo, 1)

        btn_load_config = QPushButton("加载")
        btn_load_config.clicked.connect(self.load_config)
        config_layout.addWidget(btn_load_config)

        btn_save_config = QPushButton("保存")
        btn_save_config.clicked.connect(self.save_config)
        config_layout.addWidget(btn_save_config)

        btn_delete_config = QPushButton("删除")
        btn_delete_config.clicked.connect(self.delete_config)
        config_layout.addWidget(btn_delete_config)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # Button layout
        button_layout = QHBoxLayout()

        button_layout.addWidget(QLabel("① 拼图块数:"))
        self.block_combo = QComboBox()
        self.block_combo.addItems(["16", "36", "64", "100"])
        button_layout.addWidget(self.block_combo)
        
        btn_get_ref = QPushButton("② 选择完成拼图")
        btn_get_ref.clicked.connect(self.get_reference)
        button_layout.addWidget(btn_get_ref)
        

        
        btn_select_mapping = QPushButton("③ 选择映射区域")
        btn_select_mapping.clicked.connect(self.select_mapping_area)
        button_layout.addWidget(btn_select_mapping)
        
        self.toggle_overlay_btn = QPushButton("④ 显示映射")
        self.toggle_overlay_btn.clicked.connect(self.toggle_overlay_visibility)
        self.toggle_overlay_btn.setEnabled(False)
        button_layout.addWidget(self.toggle_overlay_btn)

        self.btn_get_puzzle = QPushButton("⑤ 选择拼图区")
        self.btn_get_puzzle.clicked.connect(self.get_puzzle_region)
        button_layout.addWidget(self.btn_get_puzzle)
        
        # 添加开始/停止检测按钮
        self.btn_toggle_detection = QPushButton("⑥ 开始检测")
        self.btn_toggle_detection.clicked.connect(self.toggle_detection)
        self.btn_toggle_detection.setEnabled(False)
        button_layout.addWidget(self.btn_toggle_detection)

        
        button_layout.addStretch()

        button_group = QGroupBox("操作")
        button_group.setLayout(button_layout)
        main_layout.addWidget(button_group)

        # Preview layout
        preview_layout = QHBoxLayout()
        
        # Reference preview
        ref_group = QGroupBox("完整图预览")
        ref_vbox = QVBoxLayout()
        self.ref_label = QLabel("未截图")
        self.ref_label.setFixedSize(200, 150)
        self.ref_label.setAlignment(Qt.AlignCenter)
        self.ref_label.setStyleSheet("border: 1px solid grey;")
        ref_vbox.addWidget(self.ref_label)
        ref_group.setLayout(ref_vbox)
        preview_layout.addWidget(ref_group)
        
        # Puzzle preview
        puzzle_group = QGroupBox("拼图区预览")
        puzzle_vbox = QVBoxLayout()
        self.puzzle_label = QLabel("未截图")
        self.puzzle_label.setFixedSize(200, 150)
        self.puzzle_label.setAlignment(Qt.AlignCenter)
        self.puzzle_label.setStyleSheet("border: 1px solid grey;")
        puzzle_vbox.addWidget(self.puzzle_label)
        puzzle_group.setLayout(puzzle_vbox)
        preview_layout.addWidget(puzzle_group)

        main_layout.addLayout(preview_layout)

        # Result display
        result_group = QGroupBox("匹配结果")
        result_layout = QHBoxLayout()  # 改为水平布局
        result_layout.setContentsMargins(5, 5, 5, 5)  # 减少边距
        result_layout.setSpacing(10)  # 设置合适的间距
        
        # 左侧文字区域
        self.result_text = QLabel()
        self.result_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.result_text.setFont(QFont("Arial", 9))
        self.result_text.setMinimumWidth(200)  # 设置文字区域最小宽度
        self.result_text.setMaximumWidth(250)  # 限制文字区域最大宽度
        result_layout.addWidget(self.result_text)
        
        # 右侧图片区域
        self.result_label = QLabel()
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_label.setMinimumSize(400, 250)  # 调整为更合理的尺寸
        self.result_label.setMaximumSize(600, 350)  # 限制最大尺寸
        result_layout.addWidget(self.result_label, 1)  # 给图片更多空间
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)

        # Status bar
        self.status_bar = QLabel("等待截图")
        self.status_bar.setStyleSheet("color: blue;")
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)
        self.setMinimumSize(700, 750)  # 调整为更合理的窗口大小
        
        self.populate_configs_dropdown()

    def populate_configs_dropdown(self):
        self.config_combo.clear()
        self.config_combo.addItem("选择一个配置...")
        
        configs_file = os.path.join(self.configs_dir, "configs.json")
        if os.path.exists(configs_file):
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                for config_name in sorted(configs_data.keys()):
                    self.config_combo.addItem(config_name)
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def save_config(self):
        if self.reference_img is None or self.mapping_area is None:
            QMessageBox.warning(self, "错误", "请先截取完整图并选择映射区域后再保存。")
            return

        config_name, ok = QInputDialog.getText(self, "保存配置", "请输入配置名称:", QLineEdit.Normal, "")
        if not (ok and config_name):
            return # User cancelled
        
        # Sanitize filename
        config_name = "".join(c for c in config_name if c.isalnum() or c in (' ', '_', '-')).rstrip()
        if not config_name:
            QMessageBox.warning(self, "错误", "配置名称无效。")
            return
            
        configs_file = os.path.join(self.configs_dir, "configs.json")
        
        # 检查配置是否已存在
        existing_configs = {}
        if os.path.exists(configs_file):
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    existing_configs = json.load(f)
            except Exception as e:
                print(f"读取现有配置失败: {e}")
        
        if config_name in existing_configs:
            reply = QMessageBox.question(self, '覆盖确认', f"配置 '{config_name}' 已存在。要覆盖它吗？",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.No:
                return

        # Save reference image
        ref_img_filename = f"{config_name}.png"
        ref_img_path = os.path.abspath(os.path.join(self.configs_img_dir, ref_img_filename))
        print(f"Saving reference image to: {ref_img_path}")
        # 使用 imencode 替代 imwrite 来处理中文路径
        # 将RGB转换为BGR用于保存
        ref_img_bgr = cv2.cvtColor(self.reference_img, cv2.COLOR_RGB2BGR)
        ret, img_encoded = cv2.imencode('.png', ref_img_bgr)
        if ret:
            with open(ref_img_path, 'wb') as f:
                f.write(img_encoded.tobytes())
        else:
            raise Exception("图片编码失败")

        config_data = {
            "name": config_name,
            "reference_image_path": ref_img_path,
            "mapping_area": {
                "x": self.mapping_area['x'],
                "y": self.mapping_area['y'],
                "width": self.mapping_area['width'],
                "height": self.mapping_area['height'],
            },
            "block_count": int(self.block_combo.currentText()),
        }

        try:
            # 将新配置添加到现有配置中
            existing_configs[config_name] = config_data
            
            # 保存所有配置到单个文件
            with open(configs_file, 'w', encoding='utf-8') as f:
                json.dump(existing_configs, f, indent=4, ensure_ascii=False)
            self.status_bar.setText(f"✅ 配置 '{config_name}' 已保存。")
            self.populate_configs_dropdown()
            self.config_combo.setCurrentText(config_name)
        except Exception as e:
            self.status_bar.setText(f"❌ 保存配置失败: {e}")
            self.status_bar.setStyleSheet("color: red;")

    def load_config(self):
        config_name = self.config_combo.currentText()
        if config_name == "选择一个配置...":
            return

        configs_file = os.path.join(self.configs_dir, "configs.json")
        if not os.path.exists(configs_file):
            QMessageBox.warning(self, "错误", f"配置文件 'configs.json' 未找到。")
            self.populate_configs_dropdown()
            return
            
        try:
            with open(configs_file, 'r', encoding='utf-8') as f:
                configs_data = json.load(f)
            
            if config_name not in configs_data:
                QMessageBox.warning(self, "错误", f"配置 '{config_name}' 未找到。")
                self.populate_configs_dropdown()
                return
                
            config_data = configs_data[config_name]

            # Load reference image
            ref_img_path = config_data.get("reference_image_path")
            if not (ref_img_path and os.path.exists(ref_img_path)):
                 QMessageBox.critical(self, "错误", f"引用的图片文件不存在:\n{ref_img_path}")
                 return
                 
            # 使用 numpy 读取文件，避免 cv2.imread 的中文路径问题
            img_array = np.fromfile(ref_img_path, dtype=np.uint8)
            img_bgr = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            if img_bgr is None:
                 QMessageBox.critical(self, "错误", f"无法加载图片:\n{ref_img_path}")
                 return

            # 转换为RGB格式存储
            self.reference_img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(self.reference_img)
            self.display_reference_preview(pil_img)

            # Load mapping area
            self.mapping_area = config_data.get("mapping_area")
            if self.mapping_overlay:
                self.mapping_overlay.close()
                
            self.mapping_overlay = create_mapping_overlay(
                self.mapping_area['x'], self.mapping_area['y'], 
                self.mapping_area['width'], self.mapping_area['height'],
                config_data.get("block_count", 36)
            )
            self.mapping_overlay.closed.connect(self.on_overlay_closed)
            self.toggle_overlay_btn.setEnabled(True)
            self.toggle_overlay_btn.setText("④ 隐藏映射")

            # Load block count
            block_count_str = str(config_data.get("block_count", "36"))
            index = self.block_combo.findText(block_count_str)
            if index != -1:
                self.block_combo.setCurrentIndex(index)
            
            self.puzzle_label.setText("未截图") # Clear puzzle preview
            self.puzzle_label.setStyleSheet("border: 1px solid grey;")
            self.result_text.clear()
            self.result_label.clear()

            self.status_bar.setText(f"✅ 配置 '{config_name}' 已加载。")
            self.status_bar.setStyleSheet("color: green;")

        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载配置 '{config_name}' 失败: {e}")
            self.status_bar.setText(f"❌ 加载配置失败: {e}")
            self.status_bar.setStyleSheet("color: red;")
            
    def delete_config(self):
        config_name = self.config_combo.currentText()
        if config_name == "选择一个配置...":
            return

        reply = QMessageBox.question(self, '删除确认', f"确定要删除配置 '{config_name}' 吗？此操作不可撤销。",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        configs_file = os.path.join(self.configs_dir, "configs.json")
        img_path_to_delete = None

        if os.path.exists(configs_file):
            try:
                with open(configs_file, 'r', encoding='utf-8') as f:
                    configs_data = json.load(f)
                
                if config_name in configs_data:
                    img_path_to_delete = configs_data[config_name].get("reference_image_path")
                    # 从配置中删除指定配置
                    del configs_data[config_name]
                    
                    # 保存更新后的配置
                    with open(configs_file, 'w', encoding='utf-8') as f:
                        json.dump(configs_data, f, indent=4, ensure_ascii=False)
                else:
                    self.status_bar.setText(f"❌ 配置 '{config_name}' 不存在")
                    return
            except Exception as e:
                self.status_bar.setText(f"❌ 删除配置文件失败: {e}")
                return

        if img_path_to_delete and os.path.exists(img_path_to_delete):
            try:
                os.remove(img_path_to_delete)
            except Exception as e:
                 self.status_bar.setText(f"❌ 删除图片文件失败: {e}")
                 # continue to update UI

        self.status_bar.setText(f"✅ 配置 '{config_name}' 已删除。")
        self.populate_configs_dropdown()

    def save_screenshot(self, img, prefix):
        """Save screenshot to a file."""
        # 不再保存截图到本地
        return None

    def get_reference(self):
        self.status_bar.setText("请拖拽截图...")
        self.cropper = crop_screen_region(self.on_reference_cropped, return_position=False)

    def on_reference_cropped(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                # 直接使用RGB格式存储，避免颜色转换
                self.reference_img = np.array(img)
                self.display_reference_preview(img)
                self.save_screenshot(img, "reference")
                self.status_bar.setText(f"✅ 完整图已截取")
                self.status_bar.setStyleSheet("color: green;")
            except Exception as e:
                self.status_bar.setText(f"❌ 截图失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 截图取消或失败")
            self.status_bar.setStyleSheet("color: red;")

    def get_puzzle_region(self):
        self.status_bar.setText("请拖拽选择拼图区域...")
        self.cropper = crop_screen_region(self.on_puzzle_region_selected, return_position=True)

    def on_puzzle_region_selected(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                # 保存截图区域的坐标信息
                if position:
                    x, y = position
                    width, height = img.size
                    self.puzzle_region = (x, y, width, height)
                else:
                    # 如果无法获取坐标，使用默认值
                    self.puzzle_region = (0, 0, img.size[0], img.size[1])
                
                # 直接使用RGB格式存储，避免颜色转换
                self.puzzle_img = np.array(img)
                self.display_puzzle_preview(img)
                self.save_screenshot(img, "puzzle")
                self.status_bar.setText(f"✅ 拼图区域已选择")
                self.status_bar.setStyleSheet("color: green;")
                
                # 启用检测按钮
                self.btn_toggle_detection.setEnabled(True)
                
                # 立即执行一次匹配
                self.auto_detect_and_match()
            except Exception as e:
                self.status_bar.setText(f"❌ 选择拼图区域失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 选择拼图区域取消或失败")
            self.status_bar.setStyleSheet("color: red;")

    def on_puzzle_cropped(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                # 直接使用RGB格式存储，避免颜色转换
                self.puzzle_img = np.array(img)
                self.display_puzzle_preview(img)
                self.save_screenshot(img, "puzzle")
                self.status_bar.setText(f"✅ 拼图区已截取，开始自动匹配...")
                self.status_bar.setStyleSheet("color: green;")
                self.puzzle_region = (position[0], position[1], img.size[0], img.size[1])
                self.auto_detect_and_match()
            except Exception as e:
                self.status_bar.setText(f"❌ 截图失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 截图取消或失败")
            self.status_bar.setStyleSheet("color: red;")

    def select_mapping_area(self):
        if self.reference_img is None:
            QMessageBox.critical(self, "错误", "请先截图完整图")
            return
            
        ref_height, ref_width = self.reference_img.shape[:2]
        self.status_bar.setText("请选择映射区域...")
        self.cropper = crop_interactive_region(
            self.on_mapping_area_selected, 
            initial_size=(ref_width, ref_height)
        )
        
    def on_mapping_area_selected(self, img, position):
        if img and img.size[0] > 0 and img.size[1] > 0:
            try:
                ref_height, ref_width = self.reference_img.shape[:2]
                self.mapping_area = {
                    'img': img, 'width': img.size[0], 'height': img.size[1],
                    'ref_width': ref_width, 'ref_height': ref_height,
                    'x': position[0] if position else 0, 'y': position[1] if position else 0
                }
                
                if self.mapping_overlay:
                    self.mapping_overlay.close()
                
                self.mapping_overlay = create_mapping_overlay(
                    position[0], position[1], img.size[0], img.size[1],
                    int(self.block_combo.currentText())
                )
                self.mapping_overlay.closed.connect(self.on_overlay_closed)
                
                self.toggle_overlay_btn.setEnabled(True)
                self.toggle_overlay_btn.setText("④ 隐藏映射")
                
                self.status_bar.setText(f"✅ 映射区域已选择: {img.size[0]}×{img.size[1]}")
                self.status_bar.setStyleSheet("color: green;")
            except Exception as e:
                self.status_bar.setText(f"❌ 选择映射区域失败: {str(e)}")
                self.status_bar.setStyleSheet("color: red;")
        else:
            self.status_bar.setText("❌ 选择映射区域失败")
            self.status_bar.setStyleSheet("color: red;")
    
    def on_overlay_closed(self):
        self.mapping_overlay = None
        self.toggle_overlay_btn.setText("④ 显示映射")
        self.toggle_overlay_btn.setEnabled(False)

    def toggle_overlay_visibility(self):
        if self.mapping_overlay:
            if self.mapping_overlay.isVisible():
                self.mapping_overlay.hide()
                self.toggle_overlay_btn.setText("④ 显示映射")
            else:
                self.mapping_overlay.show()
                self.toggle_overlay_btn.setText("④ 隐藏映射")

    def auto_detect_and_match(self):
        if self.reference_img is None or self.puzzle_region is None:
            self.status_bar.setText("❌ 请先截图完整图并选择拼图区域")
            self.status_bar.setStyleSheet("color: red;")
            return
            
        try:
            # 每次都重新截取屏幕指定区域
            x, y, width, height = self.puzzle_region
            
            # 使用PIL截取屏幕区域
            from PIL import ImageGrab
            puzzle_img_pil = ImageGrab.grab(bbox=(x, y, x + width, y + height))
            puzzle_cv = np.array(puzzle_img_pil)
            
            # 更新保存的拼图图像和预览
            self.puzzle_img = puzzle_cv
            self.display_puzzle_preview(puzzle_img_pil)
            
            block_count = int(self.block_combo.currentText())
            grid_map = {16: (4, 4), 36: (6, 6), 64: (8, 8), 100: (10, 10)}
            grid_rows, grid_cols = grid_map.get(block_count, (6, 6))
            
            ref_height, ref_width = self.reference_img.shape[:2]
            puzzle_height, puzzle_width = puzzle_cv.shape[:2]
            
            ref_tile_width = ref_width // grid_cols
            ref_tile_height = ref_height // grid_rows
            
            # 转为灰度图像
            puzzle_gray = cv2.cvtColor(puzzle_cv, cv2.COLOR_BGR2GRAY)
            ref_gray = cv2.cvtColor(self.reference_img, cv2.COLOR_RGB2GRAY)
            puzzle_height, puzzle_width = puzzle_gray.shape[:2]
            ref_tile_width = ref_width // grid_cols
            ref_tile_height = ref_height // grid_rows
            matches = []
            # 使用多种匹配方法
            methods = [cv2.TM_CCOEFF_NORMED, cv2.TM_CCORR_NORMED]
            weights = [0.7, 0.3]  # 权重
            search_margin = 8  # 放大搜索范围（像素）
            canny_low, canny_high = 80, 180
            # 拼图区边缘图
            puzzle_edges = cv2.Canny(puzzle_gray, canny_low, canny_high)
            for row in range(grid_rows):
                for col in range(grid_cols):
                    tile_x = col * ref_tile_width
                    tile_y = row * ref_tile_height
                    # 扩大搜索区域
                    search_x1 = max(0, tile_x - search_margin)
                    search_y1 = max(0, tile_y - search_margin)
                    search_x2 = min(ref_width, tile_x + ref_tile_width + search_margin)
                    search_y2 = min(ref_height, tile_y + ref_tile_height + search_margin)
                    search_area = ref_gray[search_y1:search_y2, search_x1:search_x2]
                    search_area_edges = cv2.Canny(search_area, canny_low, canny_high)
                    # 拼图区块（模板）
                    puzzle_block = puzzle_edges
                    ph, pw = puzzle_block.shape[:2]
                    rh, rw = search_area_edges.shape[:2]
                    # 如果拼图区块比搜索区域大，先resize
                    if ph > rh or pw > rw:
                        puzzle_block = cv2.resize(puzzle_block, (rw, rh), interpolation=cv2.INTER_AREA)
                    # 匹配
                    total_confidence = 0
                    for method, weight in zip(methods, weights):
                        res = cv2.matchTemplate(search_area_edges, puzzle_block, method)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        total_confidence += max_val * weight
                    best_x = search_x1 + max_loc[0]
                    best_y = search_y1 + max_loc[1]
                    matches.append({
                        'position': (row, col),
                        'confidence': total_confidence,
                        'location': (best_x, best_y),
                        'tile_size': (ref_tile_width, ref_tile_height)
                    })
                
            matches.sort(key=lambda x: x['confidence'], reverse=True)
            self.display_matches(matches, grid_rows, grid_cols, puzzle_cv)
            
        except Exception as e:
            self.status_bar.setText(f"❌ 检测匹配失败: {str(e)}")
            self.status_bar.setStyleSheet("color: red;")

    def display_matches(self, matches, grid_rows, grid_cols, current_puzzle_img=None):
        if not matches:
            self.status_bar.setText("❌ 未找到匹配")
            self.status_bar.setStyleSheet("color: red;")
            return
            
        self.result_text.clear()
        
        # 创建结果图像
        result_img = self.reference_img.copy()
        # 使用当前截取的拼图图像，如果没有则使用保存的图像
        if current_puzzle_img is not None:
            puzzle_result = current_puzzle_img.copy()
        else:
            puzzle_result = self.puzzle_img.copy() if hasattr(self, 'puzzle_img') and self.puzzle_img is not None else None
        
        text_info = []
        for i, match in enumerate(matches[:5]):  # 显示前5个最佳匹配
            row, col = match['position']
            confidence = match['confidence']
            x, y = match['location']
            tile_width, tile_height = match['tile_size']
            
            # 置信度越高，绿色越亮，越低越接近白色
            base = 220
            r = int(base * (1 - confidence))
            g = 255
            b = int(base * (1 - confidence))
            color = (b, g, r)  # OpenCV为BGR
            # 文字颜色
            color_name = "black" if confidence > 0.5 else "white"
            
            # 在参考图上绘制矩形
            cv2.rectangle(result_img, (x, y), (x + tile_width, y + tile_height), color, 2)
            cv2.putText(result_img, f"{confidence:.2f}", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 如果拼图图像存在，在拼图上绘制矩形
            if puzzle_result is not None:
                cv2.rectangle(puzzle_result, (x, y), (x + tile_width, y + tile_height), color, 2)
                cv2.putText(puzzle_result, f"({row+1},{col+1})", (x, y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            text_info.append(f'<font color="{color_name}">位置({row+1},{col+1}): 置信度 {confidence:.2f}</font>')
        
        self.result_text.setText("<br>".join(text_info))
        
        # 直接使用RGB格式显示
        result_pil = Image.fromarray(result_img)
        pixmap = pil_to_qpixmap(result_pil)
        # 使用更好的缩放策略，保持图片清晰度
        scaled_pixmap = pixmap.scaled(self.result_label.size() * 0.9, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.result_label.setPixmap(scaled_pixmap)
        
        # 更新拼图预览（显示当前截取的图像，不带匹配标记）
        if current_puzzle_img is not None:
            # 显示最新截取的干净图像
            puzzle_pil_clean = Image.fromarray(current_puzzle_img)
            puzzle_pixmap_clean = pil_to_qpixmap(puzzle_pil_clean)
            self.puzzle_label.setPixmap(puzzle_pixmap_clean.scaled(self.puzzle_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        best_match = matches[0]
        block_count = int(self.block_combo.currentText())
        if best_match['confidence'] > 0.8:
            self.status_bar.setText(f"✅ {block_count}块拼图 - 最佳匹配: 位置({best_match['position'][0]+1},{best_match['position'][1]+1}), 置信度: {best_match['confidence']:.2f}")
            self.status_bar.setStyleSheet("color: green;")
        elif best_match['confidence'] > 0.6:
            self.status_bar.setText(f"⚠️ {block_count}块拼图 - 最佳匹配: 位置({best_match['position'][0]+1},{best_match['position'][1]+1}), 置信度: {best_match['confidence']:.2f} (中等)")
            self.status_bar.setStyleSheet("color: orange;")
        else:
            self.status_bar.setText(f"❌ {block_count}块拼图 - 最佳匹配: 位置({best_match['position'][0]+1},{best_match['position'][1]+1}), 置信度: {best_match['confidence']:.2f} (较低)")
            self.status_bar.setStyleSheet("color: red;")
        
        if self.mapping_overlay:
            self.mapping_overlay.update_matches(matches)

    def display_reference_preview(self, img_pil):
        pixmap = pil_to_qpixmap(img_pil)
        self.ref_label.setPixmap(pixmap.scaled(self.ref_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def display_puzzle_preview(self, img_pil):
        pixmap = pil_to_qpixmap(img_pil)
        self.puzzle_label.setPixmap(pixmap.scaled(self.puzzle_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        """Handle window resize to re-scale the result image."""
        super().resizeEvent(event)
        # Re-display the last result image to fit the new size
        if hasattr(self, 'result_label') and self.result_label.pixmap() and not self.result_label.pixmap().isNull():
             self.result_label.setPixmap(self.result_label.pixmap().scaled(self.result_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def toggle_detection(self):
        if self.is_detecting:
            self.detection_timer.stop()
            self.btn_toggle_detection.setText("开始检测")
            # 停止检测时关闭映射窗口
            if self.mapping_overlay:
                self.mapping_overlay.close()
                self.mapping_overlay = None
        else:
            self.detection_timer.start(1000)
            self.btn_toggle_detection.setText("停止检测")
            # 开始检测时自动打开映射窗口（如果有映射区域信息且未打开）
            if self.mapping_area and not self.mapping_overlay:
                from mapping_overlay import create_mapping_overlay
                self.mapping_overlay = create_mapping_overlay(
                    self.mapping_area['x'], self.mapping_area['y'],
                    self.mapping_area['width'], self.mapping_area['height'],
                    int(self.block_combo.currentText())
                )
                self.mapping_overlay.closed.connect(self.on_overlay_closed)
                self.toggle_overlay_btn.setEnabled(True)
                self.toggle_overlay_btn.setText("④ 隐藏映射")
        self.is_detecting = not self.is_detecting

# === Main Execution ===
if __name__ == "__main__":
    # 检查并请求管理员权限以确保鼠标穿透功能正常工作
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common import isAdmin
    isAdmin.hide_console()
    if not isAdmin.is_admin():
        print("检测到需要管理员权限以启用鼠标穿透功能...")
        print("正在请求管理员权限...")
        isAdmin.run_as_admin()
      
    else:
        print("已获得管理员权限，启动拼图匹配工具...")
    
    app = QApplication.instance() 
    if not app:
        app = QApplication(sys.argv)
    
    main_win = PuzzleApp()
    main_win.show()
    sys.exit(app.exec_())
