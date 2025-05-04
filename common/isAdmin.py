import sys
import os
import ctypes

def hide_console():
    """隐藏控制台窗口"""
    if sys.platform == 'win32':
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """请求管理员权限重新运行程序"""
    if not is_admin():
        try:
            # 获取当前脚本的路径
            script = os.path.abspath(sys.argv[0])
            # 使用shell执行命令请求管理员权限
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, script, None, 1)
            sys.exit()
        except Exception as e:
            print(f"请求管理员权限失败: {e}")
            return False
    return True