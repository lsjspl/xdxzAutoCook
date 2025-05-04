import time
import easyocr
from PIL import Image, ImageTk, ImageOps
import re
import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import ctypes
import sys
import keyboard
import shutil
from paddleocr import PaddleOCR
import win32gui
import win32con
import win32api
from ctypes import wintypes
import cv2
import numpy as np
from common.isAdmin import is_admin, run_as_admin, hide_console

# 定义SendInput所需的常量
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("ki", KEYBDINPUT)
    ]



# 创建乐谱文件夹
SCORES_DIR = "scores"
if not os.path.exists(SCORES_DIR):
    os.makedirs(SCORES_DIR)

def get_score_list():
    """获取乐谱列表"""
    scores = []
    for file in os.listdir(SCORES_DIR):
        if file.endswith(('.png', '.jpg', '.jpeg')):
            name = os.path.splitext(file)[0]
            scores.append((name, os.path.join(SCORES_DIR, file)))
    return scores

def add_score(image_path):
    """添加新乐谱到文件夹"""
    try:
        # 获取文件名
        filename = os.path.basename(image_path)
        # 目标路径
        target_path = os.path.join(SCORES_DIR, filename)
        # 复制文件
        shutil.copy2(image_path, target_path)
        return True
    except Exception as e:
        print(f"添加乐谱失败: {e}")
        return False

# 简谱数字到键盘按键的映射
key_map = {
    '1': 'a', '2': 's', '3': 'd', '4': 'f', '5': 'g', '6': 'h', '7': 'j',      # 中音
    '1_high': 'q', '2_high': 'w', '3_high': 'e', '4_high': 'r', '5_high': 't', '6_high': 'y', '7_high': 'u',  # 高音
    '1_low': 'z', '2_low': 'x', '3_low': 'c', '4_low': 'v', '5_low': 'b', '6_low': 'n', '7_low': 'm',         # 低音
}

def ocr_image(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    # 打开图片并反色
    img = Image.open(image_path).convert('L')
    img = ImageOps.invert(img)
    # 二值化（保持灰度模式，不用'1'模式）
    img = img.point(lambda x: 0 if x < 128 else 255)
    img.save('temp_ocr.png')  # 临时保存
    reader = easyocr.Reader(['ch_sim', 'en'])
    result = reader.readtext('temp_ocr.png', detail=0)
    os.remove('temp_ocr.png')
    return '\n'.join(result)

def ocr_image_paddle(image_path):
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片文件不存在: {image_path}")
    # 图片增强
    img = Image.open(image_path).convert('L')
    img = ImageOps.invert(img)
    img = img.point(lambda x: 0 if x < 140 else 255)  # 提高对比度
    img = img.resize((img.width * 2, img.height * 2))  # 放大
    temp_path = 'temp_paddle_ocr.png'
    img.save(temp_path)
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    result = ocr.ocr(temp_path, cls=True)
    os.remove(temp_path)
    lines = []
    for line in result:
        for word_info in line:
            lines.append(word_info[1][0])
    return '\n'.join(lines)

def cv_imread_chinese(file_path):
    with open(file_path, 'rb') as f:
        img_bytes = np.asarray(bytearray(f.read()), dtype=np.uint8)
        img = cv2.imdecode(img_bytes, cv2.IMREAD_COLOR)
    return img

def detect_dots_and_underline_and_duration(image_path):
    import re
    img = cv_imread_chinese(image_path)
    if img is None:
        print(f"图片读取失败: {image_path}")
        return []
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ocr = PaddleOCR(use_angle_cls=True, lang='ch')
    result = ocr.ocr(image_path, cls=True)
    print("OCR结果：", result)
    notes = []
    for line in result:
        for word_info in line:
            text = word_info[1][0]
            box = word_info[0]
            # 只处理纯数字串
            if re.match(r'^[1234567]+$', text.replace(' ', '')):
                digits = text.replace(' ', '')
                for idx, char in enumerate(digits):
                    # 计算每个数字的区域（简单均分）
                    x_min = int(min([p[0] for p in box]))
                    x_max = int(max([p[0] for p in box]))
                    y_min = int(min([p[1] for p in box]))
                    y_max = int(max([p[1] for p in box]))
                    width = (x_max - x_min) // len(digits)
                    digit_x_min = x_min + idx * width
                    digit_x_max = digit_x_min + width
                    # 检测高音点
                    roi_y1 = max(0, y_min - (y_max - y_min)//2 - 5)
                    roi_y2 = y_min
                    roi = gray[roi_y1:roi_y2, digit_x_min:digit_x_max]
                    dot_count = 0
                    if roi.size != 0:
                        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        for cnt in contours:
                            area = cv2.contourArea(cnt)
                            if 2 < area < 30:
                                dot_count += 1
                    # 修正低音检测区域和阈值
                    underline_height = int((y_max - y_min) * 0.3)
                    underline_y1 = y_max + int((y_max - y_min) * 0.1)
                    underline_y2 = underline_y1 + underline_height
                    underline_y2 = min(gray.shape[0], underline_y2)
                    underline_roi = gray[underline_y1:underline_y2, digit_x_min:digit_x_max]
                    low = False
                    if underline_roi.size != 0:
                        _, binary = cv2.threshold(underline_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
                        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        for cnt in contours:
                            area = cv2.contourArea(cnt)
                            if area > 30:  # 阈值调大
                                low = True
                                break
                    # 时值暂时设为1（如需更精确可结合正则）
                    duration = 1
                    note = char
                    if dot_count > 0:
                        note += '_high'
                    if low:
                        note += '_low'
                    notes.append((dot_count, note, duration))
                    print(f"检测到音符: 高音点={dot_count}, 低音={low}, 音符={note}, 时值={duration}")
    print("最终解析notes：", notes)
    return notes

def parse_score(text):
    """解析简谱文本"""
    print("\n开始解析简谱...")
    print(f"原始文本:\n{text}")
    
    # 只保留简谱主旋律，支持高音点、低音下划线
    notes = []
    lines = text.split('\n')
    for line in lines:
        if re.search(r'[1-7i]', line):
            line = line.replace('i', '1_high')
            # 兼容多种高音点符号，统计点数
            # 匹配如"··1", "·1", ".1", "•1"等
            note_matches = re.finditer(r'([\.·•]*)([1-7](?:_low|_high)?)([-~]*)', line)
            for match in note_matches:
                dots = match.group(1)
                note = match.group(2)
                duration = len(match.group(3)) + 1  # 横线数量加1表示时值
                dot_count = len(dots)
                notes.append((dot_count, note, duration))
                print(f"解析到音符: 高音点={dot_count}, 音符={note}, 时值={duration}")
        else:
            # 添加空格表示换行
            notes.append((0, ' ', 1))
            print("解析到换行")
    print(f"解析完成，共 {len(notes)} 个音符")
    return notes

def press_key(key, duration=0.1):
    """使用多种方式发送按键"""
    try:
        if app.game_hwnd:
            # 确保窗口存在
            if not win32gui.IsWindow(app.game_hwnd):
                print("窗口句柄无效")
                return
                
            # 获取虚拟键码
            vk_code = win32api.VkKeyScan(key)
            if vk_code == -1:
                print(f"无法获取键码: {key}")
                return
                
            # 激活窗口
            win32gui.SetForegroundWindow(app.game_hwnd)
            time.sleep(0.1)  # 等待窗口激活
            
            print(f"开始发送按键: {key} (VK: {vk_code})")
            
            # 增加按键持续时间
            press_duration = max(duration, 0.2)  # 至少0.2秒
            
            # 方式1：使用PostMessage
            print("尝试PostMessage方式...")
            win32gui.PostMessage(app.game_hwnd, win32con.WM_KEYDOWN, vk_code, 0)
            time.sleep(press_duration)
            win32gui.PostMessage(app.game_hwnd, win32con.WM_KEYUP, vk_code, 0)
            time.sleep(0.05)  # 按键间隔
            
            # 方式2：使用SendInput
            print("尝试SendInput方式...")
            extra = ctypes.pointer(wintypes.ULONG(0))
            # 按下按键
            input_down = INPUT(type=INPUT_KEYBOARD,
                             ki=KEYBDINPUT(wVk=vk_code,
                                         wScan=0,
                                         dwFlags=0,
                                         time=0,
                                         dwExtraInfo=extra))
            input_up = INPUT(type=INPUT_KEYBOARD,
                           ki=KEYBDINPUT(wVk=vk_code,
                                       wScan=0,
                                       dwFlags=KEYEVENTF_KEYUP,
                                       time=0,
                                       dwExtraInfo=extra))
            
            # 发送按键
            ctypes.windll.user32.SendInput(1, ctypes.pointer(input_down), ctypes.sizeof(INPUT))
            time.sleep(press_duration)
            ctypes.windll.user32.SendInput(1, ctypes.pointer(input_up), ctypes.sizeof(INPUT))
            time.sleep(0.05)  # 按键间隔
            
            # 方式3：使用keyboard库作为备选
            print("尝试keyboard库方式...")
            keyboard.press(key)
            time.sleep(press_duration)
            keyboard.release(key)
            time.sleep(0.05)  # 按键间隔
            
            print(f"按键发送完成: {key}")
        else:
            print(f"未选择游戏窗口")
    except Exception as e:
        print(f"发送按键失败: {e}")


def save_score_data(image_path, score_data):
    """保存乐谱数据到JSON文件"""
    json_path = os.path.splitext(image_path)[0] + '.json'
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(score_data, f, ensure_ascii=False, indent=2)

def load_score_data(image_path):
    """从JSON文件加载乐谱数据"""
    json_path = os.path.splitext(image_path)[0] + '.json'
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

class NoteFrame(tk.Frame):
    """音符显示和时长调节框架"""
    def __init__(self, parent, dot_count, note, duration, index, on_duration_change):
        super().__init__(parent, bg='white')
        self.dot_count = dot_count
        self.note = note
        self.index = index
        self.on_duration_change = on_duration_change
        self.fill_progress = 0  # 填充进度
        
        # 创建音符区域框架
        self.note_area = tk.Frame(self, bg='white')
        self.note_area.pack(pady=0)
        
        # 高音点显示
        if note == ' ':
            self.dot_label = tk.Label(self.note_area, text="", font=('Arial', 10), bg='white')
        else:
            self.dot_label = tk.Label(self.note_area, text="·" * dot_count, font=('Arial', 10), bg='white')
        self.dot_label.pack(pady=0)
        
        # 音符显示
        if note == ' ':
            self.note_label = tk.Label(self.note_area, text="", font=('Arial', 10), bg='white')
        else:
            self.note_label = tk.Label(self.note_area, text=note, font=('Arial', 10), bg='white')
        self.note_label.pack(pady=0)
        
        # 时长调节滑块
        self.duration_var = tk.DoubleVar(value=0.2)  # 默认值改为0.2
        self.scale = tk.Scale(self, from_=0.1, to=2.0, variable=self.duration_var,
                              orient=tk.HORIZONTAL, length=60, bg='white', highlightthickness=0,
                              troughcolor='white', activebackground='white', resolution=0.1,  # 设置最小间隔为0.1
                              sliderrelief='flat',  # 扁平样式
                              sliderlength=10,  # 滑块长度
                              showvalue=0)  # 不显示数值
        self.scale.pack(pady=2)
        
        # 时长显示
        self.duration_label = tk.Label(self, text=f"{0.2:.1f}", font=('Arial', 8), bg='white')
        self.duration_label.pack()
        
        # 绑定滑块值变化事件
        self.scale.configure(command=self.on_scale_change)
        
        # 绑定点击事件（只绑定音符区域）
        if note != ' ':
            self.note_area.bind('<Button-1>', self.on_click)
            self.dot_label.bind('<Button-1>', self.on_click)
            self.note_label.bind('<Button-1>', self.on_click)
        
    def on_scale_change(self, value):
        duration = float(value)
        self.duration_label.configure(text=f"{duration:.1f}")
        self.on_duration_change(self.index, duration)
    
    def on_click(self, event):
        """点击音符时发送按键"""
        if self.note != ' ':
            key = key_map.get(self.note)
            if key:
                # 创建按键发送线程
                def send_key():
                    press_key(key, self.duration_var.get())
                
                # 启动按键发送线程
                key_thread = threading.Thread(target=send_key)
                key_thread.daemon = True
                key_thread.start()
    
    def highlight(self, is_highlighted, progress=0):
        self.fill_progress = progress
        if is_highlighted:
            # 颜色从白色到蓝色渐变
            r = int(255 - 255 * progress)  # 255->0
            g = int(255 - 255 * progress)  # 255->0
            b = 255  # 保持蓝色
            color = f'#{r:02x}{g:02x}{b:02x}'
            self.configure(bg=color)
            self.note_area.configure(bg=color)
            self.dot_label.configure(bg=color)
            self.note_label.configure(bg=color)
            self.duration_label.configure(bg=color)
            self.scale.configure(bg=color, troughcolor=color, activebackground=color)
        else:
            self.configure(bg='white')
            self.note_area.configure(bg='white')
            self.dot_label.configure(bg='white')
            self.note_label.configure(bg='white')
            self.duration_label.configure(bg='white')
            self.scale.configure(bg='white', troughcolor='white', activebackground='white')

class PianoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自动弹琴")
        self.root.geometry("1000x800")
        
        # 创建样式
        style = ttk.Style()
        style.configure('Note.TFrame', background='white')
        style.configure('Note.TLabel', background='white')
        
        # 检查管理员权限
        if not is_admin():
            if messagebox.askyesno("权限提示", "需要管理员权限才能正常运行，是否继续？"):
                run_as_admin()
                sys.exit()
        
        self.notes = None
        self.image_path = None
        self.base_delay = 0.4  # 基础时值（四分音符）
        self.duration_settings = {}  # 存储每个音符的时长设置
        self.note_frames = []  # 存储音符框架
        self.current_note_index = -1  # 当前播放的音符索引
        self.game_hwnd = None  # 游戏窗口句柄
        self.game_title = None  # 游戏窗口标题
        
        self.create_widgets()
        self.update_score_list()
        
    def create_widgets(self):
        # 乐谱列表区域
        list_frame = ttk.LabelFrame(self.root, text="乐谱列表", padding=10)
        list_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 乐谱列表
        self.score_list = tk.Listbox(list_frame, height=5)
        self.score_list.pack(fill=tk.X, padx=5, pady=5)
        self.score_list.bind('<<ListboxSelect>>', self.on_select_score)
        
        # 按钮区域
        button_frame = ttk.Frame(list_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(button_frame, text="添加新乐谱", command=self.add_new_score).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="刷新列表", command=self.update_score_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="选择游戏窗口", command=self.select_game_window).pack(side=tk.LEFT, padx=5)
        
        # 游戏窗口信息显示
        self.game_window_var = tk.StringVar(value="未选择游戏窗口")
        game_window_label = ttk.Label(button_frame, textvariable=self.game_window_var)
        game_window_label.pack(side=tk.LEFT, padx=5)
        
        # 乐谱显示区域
        score_frame = ttk.LabelFrame(self.root, text="乐谱", padding=5)
        score_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 创建画布和滚动条
        self.canvas = tk.Canvas(score_frame)
        scrollbar = ttk.Scrollbar(score_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 控制按钮区域
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(control_frame, text="开始弹奏", command=self.start_playing).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="停止", command=self.stop_playing).pack(side=tk.LEFT, padx=5)
        
        # 状态显示区域
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(self.root, textvariable=self.status_var)
        status_label.pack(fill=tk.X, padx=10, pady=5)
        
        self.playing = False
        
    def update_score_list(self):
        """更新乐谱列表"""
        self.score_list.delete(0, tk.END)
        scores = get_score_list()
        for name, _ in scores:
            self.score_list.insert(tk.END, name)
            
    def update_note_display(self):
        # 清空所有行Frame
        for child in self.scrollable_frame.winfo_children():
            child.destroy()
        self.note_frames.clear()
        if self.notes:
            current_line = ttk.Frame(self.scrollable_frame)
            current_line.pack(fill=tk.X)
            notes_in_line = 0
            for i, (dot_count, note, duration) in enumerate(self.notes):
                if notes_in_line >= 12 or note == ' ':
                    current_line = ttk.Frame(self.scrollable_frame)
                    current_line.pack(fill=tk.X)
                    notes_in_line = 0
                    if note == ' ':
                        continue
                current_duration = self.duration_settings.get(i, duration)
                frame = NoteFrame(current_line, dot_count, note, current_duration, i, self.on_duration_change)
                frame.pack(side=tk.LEFT, padx=2, pady=2)
                self.note_frames.append(frame)
                notes_in_line += 1
            self.canvas.yview_moveto(0)
            
    def on_duration_change(self, index, duration):
        """时长变化时的处理"""
        self.duration_settings[index] = duration
        # 保存设置
        if self.image_path:
            score_data = {
                'notes': self.notes,
                'durations': self.duration_settings
            }
            save_score_data(self.image_path, score_data)
            
    def on_select_score(self, event):
        """选择乐谱时的处理"""
        selection = self.score_list.curselection()
        if selection:
            index = selection[0]
            scores = get_score_list()
            if index < len(scores):
                _, image_path = scores[index]
                self.image_path = image_path
                self.parse_image()
                
    def add_new_score(self):
        """添加新乐谱"""
        file_path = filedialog.askopenfilename(
            title="选择简谱图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg")]
        )
        if file_path:
            if add_score(file_path):
                self.update_score_list()
                self.status_var.set("添加乐谱成功")
            else:
                self.status_var.set("添加乐谱失败")
                
    def parse_image(self):
        if not self.image_path:
            self.status_var.set("请先选择乐谱")
            return
        self.status_var.set("正在解析...")
        self.root.update()
        try:
            score_data = load_score_data(self.image_path)
            if score_data is None:
                # 用图像算法检测高音点、低音和时值
                notes = detect_dots_and_underline_and_duration(self.image_path)
                score_data = {
                    'notes': notes,
                    'durations': {}
                }
                save_score_data(self.image_path, score_data)
                self.notes = notes
                self.duration_settings = {}
            else:
                self.notes = score_data['notes']
                self.duration_settings = score_data.get('durations', {})
            self.update_note_display()
            self.status_var.set("解析完成")
        except Exception as e:
            self.status_var.set(f"解析失败: {str(e)}")
            
    def start_playing(self):
        if not self.notes:
            self.status_var.set("请先解析图片")
            return
            
        if self.playing:
            return
            
        self.playing = True
        self.status_var.set("开始弹奏")
        self.root.update()
        
        # 在新线程中运行弹奏
        threading.Thread(target=self.play_thread, daemon=True).start()
            
    def stop_playing(self):
        self.playing = False
        self.current_note_index = -1
        self.root.after(0, lambda: self.update_highlight(0))
        self.status_var.set("已停止")
        
    def play_thread(self):
        try:
            for i, (dot_count, note, duration) in enumerate(self.notes):
                if not self.playing:
                    break
                # 更新当前音符索引
                self.current_note_index = i
                # 计算每个音符的播放时间
                current_duration = self.duration_settings.get(i, self.base_delay)
                total_time = self.base_delay * current_duration
                
                print(f"\n处理音符 {i+1}/{len(self.notes)}:")
                print(f"音符: {note}, 高音点: {dot_count}, 原始时值: {duration}, 当前时值: {current_duration}")
                
                # 开始播放前更新高亮状态
                self.root.after(0, lambda: self.update_highlight(0))
                key = key_map.get(note)
                if key:
                    # 实时更新状态栏
                    self.status_var.set(f"按下: {key} (音符: {note}, 时值: {current_duration})")
                    print(f"映射到按键: {key}")
                    
                    # 创建按键发送线程
                    def send_key():
                        # 获取虚拟键码
                        vk_code = win32api.VkKeyScan(key)
                        if vk_code == -1:
                            print(f"无法获取键码: {key}")
                            return
                            
                        # 激活窗口
                        win32gui.SetForegroundWindow(app.game_hwnd)
                        time.sleep(0.1)  # 等待窗口激活
                        
                        # 使用PostMessage发送按键
                        win32gui.PostMessage(app.game_hwnd, win32con.WM_KEYDOWN, vk_code, 0)
                        
                        # 在播放过程中更新高亮进度
                        start_time = time.time()
                        while time.time() - start_time < total_time and self.playing:
                            progress = (time.time() - start_time) / total_time
                            self.root.after(0, lambda p=progress: self.update_highlight(p))
                            self.root.after(0, lambda idx=self.current_note_index: self.scroll_to_note_if_needed(idx))
                            time.sleep(0.05)  # 更新频率
                        
                        # 发送按键释放消息
                        win32gui.PostMessage(app.game_hwnd, win32con.WM_KEYUP, vk_code, 0)
                    
                    # 启动按键发送线程
                    key_thread = threading.Thread(target=send_key)
                    key_thread.daemon = True
                    key_thread.start()
                    
                    # 等待按键发送完成
                    key_thread.join()
                    time.sleep(0.1)  # 音符间隔
                elif note != ' ':  # 如果不是空格，说明是未知音符
                    print(f"警告: 未知音符: {note}")
                    self.status_var.set(f"未知音符: {note}")
                    # 对于未知音符，仍然显示进度条
                    start_time = time.time()
                    while time.time() - start_time < total_time and self.playing:
                        progress = (time.time() - start_time) / total_time
                        self.root.after(0, lambda p=progress: self.update_highlight(p))
                        self.root.after(0, lambda idx=self.current_note_index: self.scroll_to_note_if_needed(idx))
                        time.sleep(0.05)
                    time.sleep(0.1)  # 音符间隔
            if self.playing:
                self.status_var.set("弹奏完成")
                self.playing = False
                self.current_note_index = -1
                self.root.after(0, lambda: self.update_highlight(0))
        except Exception as e:
            print(f"弹奏出错: {str(e)}")
            self.status_var.set(f"弹奏出错: {str(e)}")
            self.playing = False
            self.current_note_index = -1
            self.root.after(0, lambda: self.update_highlight(0))
            
    def update_highlight(self, progress):
        """更新高亮显示"""
        for i, frame in enumerate(self.note_frames):
            frame.highlight(i == self.current_note_index, progress)

    def scroll_to_note_if_needed(self, note_index):
        if note_index < 0 or note_index >= len(self.note_frames):
            return
        frame = self.note_frames[note_index]
        self.canvas.update_idletasks()
        y = frame.winfo_y()
        h = frame.winfo_height()
        total_height = self.scrollable_frame.winfo_height()
        canvas_height = self.canvas.winfo_height()
        canvas_top = self.canvas.canvasy(0)
        canvas_bottom = canvas_top + canvas_height
        # 只有当音符底部超出可见区域时才滚动
        if y + h > canvas_bottom - 40:
            # 让音符出现在可见区域的2/3处
            target = max(0, min((y + h - int(canvas_height * 2 / 3)) / max(1, total_height), 1))
            self.canvas.yview_moveto(target)
        # 如果音符顶部高于可见区域，也滚动到上方
        elif y < canvas_top + 20:
            target = max(0, min((y - int(canvas_height / 3)) / max(1, total_height), 1))
            self.canvas.yview_moveto(target)

    def select_game_window(self):
        """选择游戏窗口"""
        def callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    # 获取窗口类名
                    class_name = win32gui.GetClassName(hwnd)
                    windows.append((hwnd, title, class_name))
        
        windows = []
        win32gui.EnumWindows(callback, windows)
        
        # 创建选择窗口
        select_window = tk.Toplevel(self.root)
        select_window.title("选择游戏窗口")
        select_window.geometry("600x400")
        
        # 创建列表框
        listbox = tk.Listbox(select_window)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 添加窗口列表
        for hwnd, title, class_name in windows:
            listbox.insert(tk.END, f"{title} [{class_name}]")
        
        def on_select(event):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                self.game_hwnd = windows[index][0]
                self.game_title = windows[index][1]
                self.game_class = windows[index][2]
                self.game_window_var.set(f"已选择: {self.game_title} [{self.game_class}]")
                select_window.destroy()
        
        listbox.bind('<<ListboxSelect>>', on_select)
        
        # 添加确定按钮
        ttk.Button(select_window, text="确定", command=select_window.destroy).pack(pady=10)

if __name__ == "__main__":
    # 隐藏控制台窗口
    hide_console()
    root = tk.Tk()
    app = PianoApp(root)
    root.mainloop()
