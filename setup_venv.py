import os
import subprocess
import sys
import platform


def create_virtualenv(venv_dir):
    """ 创建虚拟环境 """
    if not os.path.exists(venv_dir):
        print(f"Creating virtual environment at {venv_dir}...")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
    else:
        print(f"Virtual environment already exists at {venv_dir}.")


def install_requirements(venv_dir):
    """ 安装 requirements.txt 中的依赖 """
    # 判断操作系统来选择正确的路径
    if platform.system() == "Windows":
        pip_executable = os.path.join(venv_dir, "Scripts", "pip.exe")  # Windows 路径
    else:
        pip_executable = os.path.join(venv_dir, "bin", "pip")  # Linux/macOS 路径

    requirements_file = "requirements.txt"

    if os.path.exists(requirements_file):
        print(f"Installing dependencies from {requirements_file}...")
        subprocess.check_call([pip_executable, "install", "-r", requirements_file])
    else:
        print(f"{requirements_file} does not exist. Please create it first using 'pip freeze > requirements.txt'.")


def main():
    venv_dir = "venv"  # 定义虚拟环境的文件夹名
    create_virtualenv(venv_dir)
    install_requirements(venv_dir)


if __name__ == "__main__":
    main()
