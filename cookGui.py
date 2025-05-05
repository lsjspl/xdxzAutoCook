import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import os
import sys
import logging
import ctypes
from cook import CookingBot
from common import isAdmin

class TkLogHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        self.text_widget.after(0, self.append, msg)

    def append(self, msg):
        self.text_widget.insert(tk.END, msg + '\n')
        self.text_widget.see(tk.END)

class CookingThread(threading.Thread):
    def __init__(self, food_name, loop_count, log_handler):
        super().__init__()
        self.food_name = food_name
        self.loop_count = loop_count
        self.log_handler = log_handler
        self.bot = None
        self._stop_event = threading.Event()

    def run(self):
        try:
            self.bot = CookingBot(food_name=self.food_name, loop_count=self.loop_count)
            logging.getLogger().addHandler(self.log_handler)
            self.bot.run()
        except Exception as e:
            self.log_handler.append(f"错误: {str(e)}")

    def stop(self):
        if self.bot:
            self.bot.stop()
        self._stop_event.set()

class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("自动烹饪机器人 (Tkinter版)")
        self.root.geometry("650x420")
        self.cooking_thread = None
        isAdmin.hide_console()
         # 检查管理员权限
        if not isAdmin.is_admin():
            if messagebox.askyesno("权限提示", "需要管理员权限才能正常运行，是否继续？"):
                isAdmin.run_as_admin()
                sys.exit()

        # 控件布局
        frm_top = tk.Frame(root)
        frm_top.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(frm_top, text="选择食物:").pack(side=tk.LEFT)
        self.food_var = tk.StringVar()
        self.food_combo = ttk.Combobox(frm_top, textvariable=self.food_var, state="readonly", width=25)
        self.food_combo.pack(side=tk.LEFT, padx=5)

        tk.Label(frm_top, text="循环次数:").pack(side=tk.LEFT, padx=(20,0))
        self.loop_var = tk.StringVar(value="-1")
        self.loop_entry = tk.Entry(frm_top, textvariable=self.loop_var, width=6)
        self.loop_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(frm_top, text="(-1为无限)").pack(side=tk.LEFT)

        self.btn_start = tk.Button(frm_top, text="开始", width=10, command=self.start_cooking)
        self.btn_start.pack(side=tk.LEFT, padx=20)
        self.btn_stop = tk.Button(frm_top, text="停止", width=10, command=self.stop_cooking, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)

        # 日志显示
        self.log_text = scrolledtext.ScrolledText(root, height=18, font=("Consolas", 10))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))
        self.log_text.config(state=tk.NORMAL)

        # 日志处理器
        self.log_handler = TkLogHandler(self.log_text)
        logging.getLogger().setLevel(logging.INFO)

        # 加载食物列表
        self.load_food_list()

        # 关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def load_food_list(self):
        try:
            foods_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "foods")
            foods = [f[:-4] for f in os.listdir(foods_dir) if f.endswith('.png') and '_1' not in f]
            self.food_combo['values'] = foods
            if foods:
                self.food_combo.current(0)
        except Exception as e:
            messagebox.showerror("错误", f"加载食物列表失败: {str(e)}")

    def start_cooking(self):
        food_name = self.food_var.get()
        try:
            loop_count = int(self.loop_var.get())
        except ValueError:
            messagebox.showwarning("警告", "循环次数请输入整数")
            return
        if not food_name:
            messagebox.showwarning("警告", "请选择食物")
            return
        self.log_text.delete(1.0, tk.END)
        self.cooking_thread = CookingThread(food_name, loop_count, self.log_handler)
        self.cooking_thread.start()
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.food_combo.config(state=tk.DISABLED)
        self.loop_entry.config(state=tk.DISABLED)

    def stop_cooking(self):
        if self.cooking_thread:
            self.cooking_thread.stop()
            self.cooking_thread.join()
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.food_combo.config(state=tk.NORMAL)
        self.loop_entry.config(state=tk.NORMAL)

    def on_close(self):
        if self.cooking_thread and self.cooking_thread.is_alive():
            if not messagebox.askyesno("确认", "程序正在运行，确定要退出吗？"):
                return
            self.stop_cooking()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    root.attributes('-topmost', True)  # 设置窗口置顶
    app = MainApp(root)
    root.mainloop() 