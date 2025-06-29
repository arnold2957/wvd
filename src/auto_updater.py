import os
import sys
import json
import hashlib
import threading
from tkinter import messagebox
from urllib.request import urlopen, Request
from urllib.error import URLError
import subprocess
import time

class AutoUpdater:
    def __init__(self, tk, github_user, github_repo, current_version):
        self.tk = tk
        self.github_user = github_user
        self.github_repo = github_repo
        self.current_version = current_version
        self.update_url = f"https://{github_user}.github.io/{github_repo}/release.json"
        self.is_updating = False
        self.stop_event = threading.Event()
        
        # 启动后台检查线程
        self.update_thread = threading.Thread(
            target=self._update_check_loop, 
            daemon=True
        )
        self.update_thread.start()

    def _update_check_loop(self):
        """后台线程循环检查更新"""
        while not self.stop_event.is_set():
            try:
                if not self.is_updating:
                    print("开始检查")
                    self._check_update()
            except Exception as e:
                print(f"更新检查出错: {e}")
            finally:
                # 每10分钟检查一次（可根据需要调整）
                time.sleep(3600)

    def _check_update(self):
        """执行更新检查逻辑"""
        try:
            req = Request(self.update_url, headers={'Cache-Control': 'no-cache'})
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if self._is_newer_version(data['version']):
                self.is_updating = True
                # 使用after在主线程显示弹窗
                self.tk.after(0, self._show_update_prompt, data)
                
        except URLError as e:
            print(f"网络连接失败: {e}")
        except Exception as e:
            print(f"更新检查异常: {e}")

    def _is_newer_version(self, new_version):
        # 分割版本号
        new_parts = new_version.split('.')[:3]  # 只取前三个部分
        current_parts = self.current_version.split('.')[:3]  # 只取前三个部分
        
        # 确保两个列表都有3个元素（不足的补0）
        while len(new_parts) < 3:
            new_parts.append('0')
        while len(current_parts) < 3:
            current_parts.append('0')
        
        # 逐段比较版本号
        for i in range(3):
            new_num = int(new_parts[i])
            current_num = int(current_parts[i])
            
            if new_num > current_num:
                return True
            elif new_num < current_num:
                return False
        
        return False  # 所有部分都相等

    def _show_update_prompt(self, update_data):
        """显示更新提示对话框"""
        msg = f"发现新版本 {update_data['version']} (当前版本 {self.current_version})\n是否立即更新?"
        if messagebox.askyesno("发现更新", msg):
            threading.Thread(target=self._download_and_apply_update, args=(update_data,), daemon=True).start()
            self.is_updating = True
        else:
            self.is_updating = False

    def _download_and_apply_update(self, update_data):
        try:
            # 创建临时目录
            temp_dir = "__update_temp__"
            os.makedirs(temp_dir, exist_ok=True)
            
            # 下载压缩包
            download_url = update_data['download_url']
            archive_name = os.path.basename(download_url)
            archive_path = os.path.join(temp_dir, archive_name)
            
            with urlopen(download_url) as response, open(archive_path, 'wb') as out_file:
                out_file.write(response.read())
            
            # 验证MD5
            if not self._verify_md5(archive_path, update_data['md5']):
                messagebox.showerror("更新失败", "文件校验失败，请手动更新")
                return
                
            # 解压到临时目录的子文件夹
            unpack_dir = os.path.join(temp_dir, "unpacked")
            os.makedirs(unpack_dir, exist_ok=True)
            self._extract_archive(archive_path, unpack_dir)
            
            # 生成重启脚本
            self._create_restart_script(unpack_dir)
            
            # 退出当前应用
            self.tk.after(0, self._restart_application)
                
        except Exception as e:
            messagebox.showerror("更新错误", f"更新失败: {str(e)}")
    
    def _extract_archive(self, archive_path, target_dir):
        """解压压缩包"""
        if archive_path.lower().endswith('.zip'):
            # 使用Python内置zipfile模块解压
            import zipfile
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(target_dir)
        else:
            raise Exception(f"不支持的压缩格式: {os.path.splitext(archive_path)[1]}")

    def _verify_md5(self, file_path, expected_md5):
        """验证文件MD5哈希值"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest() == expected_md5

    def _create_restart_script(self, unpack_dir):
        """创建重启脚本(跨平台)"""
        if sys.platform == "win32":
            script = f"""@echo off
    REM 等待原始程序退出
    timeout /t 2 /nobreak >nul

    REM 复制解压后的文件到当前目录
    xcopy /E /Y /Q "{unpack_dir}\\*" "."

    REM 启动新版本程序
    start "" "{os.path.basename(sys.argv[0])}"

    REM 清理临时文件
    rmdir /S /Q "__update_temp__"

    REM 删除自身
    del "%~f0"
    """
            with open("_update_restart.bat", "w") as f:
                f.write(script)
                
        else:  # Linux/macOS
            script = f"""#!/bin/bash
    # 等待原始程序退出
    sleep 2

    # 移动解压后的文件到当前目录
    mv -f "{unpack_dir}"/* .

    # 添加执行权限（如果需要）
    chmod +x "{os.path.basename(sys.argv[0])}"

    # 启动新版本程序
    nohup ./{os.path.basename(sys.argv[0])} >/dev/null 2>&1 &

    # 清理临时文件
    rm -rf "__update_temp__"

    # 删除自身
    rm -- "$0"
    """
            with open("_update_restart.sh", "w") as f:
                f.write(script)

    def _restart_application(self):
        """重启应用程序"""
        if sys.platform == "win32":
            subprocess.Popen(["_update_restart.bat"], shell=True)
        else:
            os.system("nohup ./_update_restart.sh &")
        
        # 关闭当前应用
        self.tk.destroy()