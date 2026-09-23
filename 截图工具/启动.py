import os
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

# 尝试导入 Windows 剪贴板模块，用于复制图片
try:
    import win32clipboard
    import io
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

class ImageAnnotatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片查看与框选工具")
        self.root.geometry("1100x650")
        
        # 变量初始化
        self.folder_path = tk.StringVar(value=r"D:\Documents\MuMu共享文件夹\Screenshots")
        self.image_list = []
        self.current_image = None
        self.tk_image = None
        self.image_on_canvas = None
        self.current_selection_index = -1
        
        # 图片缩放与坐标映射
        self.scale = 1.0
        self.img_x_offset = 0
        self.img_y_offset = 0
        
        # 框选相关
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.bbox = (0, 0, 0, 0) # x, y, w, h
        
        self.create_widgets()

    def create_widgets(self):
        # 1. 顶部地址栏
        top_frame = tk.Frame(self.root, bd=2, relief=tk.SOLID)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Label(top_frame, text="地址:").pack(side=tk.LEFT, padx=5)
        self.path_entry = tk.Entry(top_frame, textvariable=self.folder_path)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        tk.Button(top_frame, text="选择地址", command=self.select_folder).pack(side=tk.RIGHT, padx=5)

        # 2. 主内容区（保持三列布局）
        main_frame = tk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- 第1列：左侧列表 ---
        left_frame = tk.Frame(main_frame, bd=2, relief=tk.SOLID, width=200)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        # 【修改部分】列表顶部：同一行，先文本，后刷新符号
        list_header_frame = tk.Frame(left_frame)
        list_header_frame.pack(fill=tk.X, padx=5, pady=(5, 0))
        
        tk.Label(list_header_frame, text="列表").pack(side=tk.LEFT)
        # 使用紧凑的符号按钮
        tk.Button(
            list_header_frame, text="🔄", command=self.refresh_list, 
            width=3, bd=0, bg="white", activebackground="lightgray", cursor="hand2"
        ).pack(side=tk.RIGHT)
        
        # 列表主体
        self.listbox = tk.Listbox(left_frame)
        self.listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.listbox.bind('<<ListboxSelect>>', self.on_image_select)
        
        scrollbar = tk.Scrollbar(self.listbox)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.listbox.yview)

        # --- 第3列：右侧操作区（先 pack 右侧，确保它占据固定宽度）---
        right_main_frame = tk.Frame(main_frame, bd=2, relief=tk.SOLID, width=220)
        right_main_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        right_main_frame.pack_propagate(False)

        # 右侧操作区 - 第1行：根据坐标框选
        right_top_frame = tk.Frame(right_main_frame, bd=1, relief=tk.SOLID)
        right_top_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        tk.Label(right_top_frame, text="根据坐标框选", font=("Arial", 10, "bold")).pack(pady=(5, 0))
        tk.Label(right_top_frame, text="(x,y,w,h):").pack()
        
        coord_input_frame = tk.Frame(right_top_frame)
        coord_input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.coord_entry = tk.Entry(coord_input_frame)
        self.coord_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(coord_input_frame, text="框选", command=self.select_by_coords).pack(side=tk.RIGHT, padx=(5, 0))

        # 右侧操作区 - 第2行：原有操作区
        right_bottom_frame = tk.Frame(right_main_frame)
        right_bottom_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        tk.Label(right_bottom_frame, text="框选操作", font=("Arial", 12, "bold")).pack(pady=10)

        # 复制框选内容
        tk.Button(right_bottom_frame, text="复制框选内容", command=self.copy_cropped_image).pack(fill=tk.X, padx=10, pady=(5, 0))
        self.tip_copy_img = tk.Label(right_bottom_frame, text="", fg="green", font=("Arial", 9))
        self.tip_copy_img.pack(pady=(0, 10))
        
        # 框选范围
        tk.Label(right_bottom_frame, text="框选范围 (x,y,w,h):").pack(pady=(5, 0))
        self.bbox_entry = tk.Entry(right_bottom_frame, state='readonly', bg="white", fg="black")
        self.bbox_entry.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(right_bottom_frame, text="复制范围", command=self.copy_bbox).pack(fill=tk.X, padx=10)
        self.tip_copy_bbox = tk.Label(right_bottom_frame, text="", fg="green", font=("Arial", 9))
        self.tip_copy_bbox.pack(pady=(0, 10))

        # 框选中心
        tk.Label(right_bottom_frame, text="中心 / 点击位置 (x,y):").pack(pady=(5, 0))
        self.center_entry = tk.Entry(right_bottom_frame, state='readonly', bg="white", fg="black")
        self.center_entry.pack(fill=tk.X, padx=10, pady=5)
        tk.Button(right_bottom_frame, text="复制中心点", command=self.copy_center).pack(fill=tk.X, padx=10)
        self.tip_copy_center = tk.Label(right_bottom_frame, text="", fg="green", font=("Arial", 9))
        self.tip_copy_center.pack(pady=(0, 10))

        # 启动Windows画图
        tk.Button(right_bottom_frame, text="启动Windows画图", command=self.open_ms_paint, bg="#e1e1e1").pack(fill=tk.X, padx=10, pady=(20, 10))

        # --- 第2列：中间详细内容（最后 pack，自动占据剩余空间）---
        center_frame = tk.Frame(main_frame, bd=2, relief=tk.SOLID)
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        tk.Label(center_frame, text="详细内容 (点击显示坐标，拖拽或输入坐标框选)").pack(anchor=tk.NW, padx=5, pady=2)
        
        self.canvas = tk.Canvas(center_frame, bg="gray90", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

    def select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.folder_path.set(folder_selected)
            self.load_image_list()

    def refresh_list(self):
        if not self.folder_path.get():
            return
        self.load_image_list()
        if self.current_selection_index != -1 and self.current_selection_index < self.listbox.size():
            self.listbox.selection_set(self.current_selection_index)
            self.listbox.see(self.current_selection_index)
            self.on_image_select(None)

    def load_image_list(self):
        folder = self.folder_path.get()
        if not os.path.isdir(folder):
            return
        
        self.listbox.delete(0, tk.END)
        self.image_list = []
        
        valid_extensions = ('.png', '.jpg', '.jpeg', '.bmp', '.gif')
        try:
            for f in os.listdir(folder):
                if f.lower().endswith(valid_extensions):
                    full_path = os.path.join(folder, f)
                    mtime = os.path.getmtime(full_path)
                    self.image_list.append((full_path, mtime, f))
            
            self.image_list.sort(key=lambda x: x[1], reverse=True)
            
            for _, _, fname in self.image_list:
                self.listbox.insert(tk.END, fname)
                
        except Exception as e:
            messagebox.showerror("错误", f"读取文件夹失败: {e}")

    def on_image_select(self, event):
        selection = self.listbox.curselection()
        if not selection:
            return
        
        self.current_selection_index = selection[0]
        img_path = self.image_list[self.current_selection_index][0]
        
        try:
            self.current_image = Image.open(img_path)
            self.display_image()
            self.reset_selection()
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片: {e}")

    def display_image(self):
        if not self.current_image:
            return
        
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1 or canvas_height <= 1:
            self.root.after(100, self.display_image)
            return

        img_w, img_h = self.current_image.size
        
        self.scale = min(canvas_width / img_w, canvas_height / img_h)
        new_w = int(img_w * self.scale)
        new_h = int(img_h * self.scale)
        
        self.img_x_offset = (canvas_width - new_w) // 2
        self.img_y_offset = (canvas_height - new_h) // 2
        
        resized_img = self.current_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_img)
        
        self.canvas.delete("all")
        self.image_on_canvas = self.canvas.create_image(
            self.img_x_offset, self.img_y_offset, anchor=tk.NW, image=self.tk_image
        )

    def reset_selection(self):
        self.start_x = None
        self.start_y = None
        self.bbox = (0, 0, 0, 0)
        self.bbox_entry.config(state='normal')
        self.bbox_entry.delete(0, tk.END)
        self.bbox_entry.config(state='readonly')
        self.center_entry.config(state='normal')
        self.center_entry.delete(0, tk.END)
        self.center_entry.config(state='readonly')
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self.clear_all_tips()

    def on_mouse_down(self, event):
        if not self.current_image:
            return
        if (self.img_x_offset <= event.x <= self.img_x_offset + self.tk_image.width() and
            self.img_y_offset <= event.y <= self.img_y_offset + self.tk_image.height()):
            self.start_x = event.x
            self.start_y = event.y
            if self.rect_id:
                self.canvas.delete(self.rect_id)
            self.rect_id = self.canvas.create_rectangle(
                self.start_x, self.start_y, self.start_x, self.start_y, outline="red", width=2
            )

    def on_mouse_drag(self, event):
        if self.start_x is not None and self.start_y is not None:
            cur_x = max(self.img_x_offset, min(event.x, self.img_x_offset + self.tk_image.width()))
            cur_y = max(self.img_y_offset, min(event.y, self.img_y_offset + self.tk_image.height()))
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, cur_x, cur_y)

    def on_mouse_up(self, event):
        if self.start_x is None or self.start_y is None:
            return
        
        dx = abs(event.x - self.start_x)
        dy = abs(event.y - self.start_y)
        if dx < 5 and dy < 5:
            self.handle_click(event.x, event.y)
            self.start_x = None
            self.start_y = None
            return

        end_x = max(self.img_x_offset, min(event.x, self.img_x_offset + self.tk_image.width()))
        end_y = max(self.img_y_offset, min(event.y, self.img_y_offset + self.tk_image.height()))
        
        canvas_x1 = min(self.start_x, end_x)
        canvas_y1 = min(self.start_y, end_y)
        canvas_x2 = max(self.start_x, end_x)
        canvas_y2 = max(self.start_y, end_y)
        
        orig_x1 = int((canvas_x1 - self.img_x_offset) / self.scale)
        orig_y1 = int((canvas_y1 - self.img_y_offset) / self.scale)
        orig_x2 = int((canvas_x2 - self.img_x_offset) / self.scale)
        orig_y2 = int((canvas_y2 - self.img_y_offset) / self.scale)
        
        w = orig_x2 - orig_x1
        h = orig_y2 - orig_y1
        
        if w > 0 and h > 0:
            self.update_selection_data(orig_x1, orig_y1, w, h)
        else:
            if self.rect_id:
                self.canvas.delete(self.rect_id)
                self.rect_id = None

        self.start_x = None
        self.start_y = None

    def update_selection_data(self, x, y, w, h):
        self.bbox = (x, y, w, h)
        
        self.bbox_entry.config(state='normal')
        self.bbox_entry.delete(0, tk.END)
        self.bbox_entry.insert(0, f"{x}, {y}, {w}, {h}")
        self.bbox_entry.config(state='readonly')
        
        cx, cy = x + w // 2, y + h // 2
        self.center_entry.config(state='normal')
        self.center_entry.delete(0, tk.END)
        self.center_entry.insert(0, f"{cx}, {cy}")
        self.center_entry.config(state='readonly')
        
        self.clear_all_tips()

    def handle_click(self, canvas_x, canvas_y):
        if not self.current_image:
            return
        if not (self.img_x_offset <= canvas_x <= self.img_x_offset + self.tk_image.width() and
                self.img_y_offset <= canvas_y <= self.img_y_offset + self.tk_image.height()):
            return

        orig_x = int((canvas_x - self.img_x_offset) / self.scale)
        orig_y = int((canvas_y - self.img_y_offset) / self.scale)

        self.bbox = (0, 0, 0, 0)
        self.bbox_entry.config(state='normal')
        self.bbox_entry.delete(0, tk.END)
        self.bbox_entry.config(state='readonly')
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None

        self.center_entry.config(state='normal')
        self.center_entry.delete(0, tk.END)
        self.center_entry.insert(0, f"{orig_x}, {orig_y}")
        self.center_entry.config(state='readonly')

    def select_by_coords(self):
        if not self.current_image:
            messagebox.showwarning("提示", "请先选择一张图片")
            return
            
        text = self.coord_entry.get().strip()
        if not text:
            messagebox.showwarning("提示", "请输入坐标 (x,y,w,h)")
            return
            
        try:
            text = text.replace('，', ',')
            parts = list(map(int, text.split(',')))
            if len(parts) != 4:
                raise ValueError
            x, y, w, h = parts
            if w <= 0 or h <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入有效的格式: x,y,w,h")
            return
            
        img_w, img_h = self.current_image.size
        if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
            messagebox.showerror("错误", f"框选范围超出图片边界\n(图片尺寸: {img_w}x{img_h})")
            return
            
        canvas_x1 = x * self.scale + self.img_x_offset
        canvas_y1 = y * self.scale + self.img_y_offset
        canvas_x2 = (x + w) * self.scale + self.img_x_offset
        canvas_y2 = (y + h) * self.scale + self.img_y_offset
        
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            canvas_x1, canvas_y1, canvas_x2, canvas_y2, outline="red", width=2
        )
        
        self.update_selection_data(x, y, w, h)

    def show_tip(self, label_widget, text="已复制！"):
        label_widget.config(text=text)
        self.root.after(2000, lambda: self.clear_tip(label_widget))

    def clear_tip(self, label_widget):
        label_widget.config(text="")

    def clear_all_tips(self):
        self.tip_copy_img.config(text="")
        self.tip_copy_bbox.config(text="")
        self.tip_copy_center.config(text="")

    def copy_text_to_clipboard(self, text, tip_label):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        self.show_tip(tip_label)

    def copy_bbox(self):
        x, y, w, h = self.bbox
        if w == 0 or h == 0:
            messagebox.showwarning("提示", "请先框选范围")
            return
        self.copy_text_to_clipboard(f"{x}, {y}, {w}, {h}", self.tip_copy_bbox)

    def copy_center(self):
        text = self.center_entry.get()
        if not text:
            messagebox.showwarning("提示", "请先点击图片或框选范围")
            return
        self.copy_text_to_clipboard(text, self.tip_copy_center)

    def copy_cropped_image(self):
        x, y, w, h = self.bbox
        if w == 0 or h == 0 or not self.current_image:
            messagebox.showwarning("提示", "请先框选范围")
            return
        
        try:
            cropped_img = self.current_image.crop((x, y, x + w, y + h))
            
            if HAS_WIN32:
                output = io.BytesIO()
                cropped_img.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()
                
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
                self.show_tip(self.tip_copy_img, "框选内容已复制！")
            else:
                temp_path = os.path.join(os.path.expanduser("~"), "cropped_temp.png")
                cropped_img.save(temp_path)
                self.copy_text_to_clipboard(temp_path, self.tip_copy_img)
                self.show_tip(self.tip_copy_img, "路径已复制！")
                
        except Exception as e:
            messagebox.showerror("错误", f"复制图片失败: {e}")

    def open_ms_paint(self):
        try:
            os.startfile("mspaint.exe")
        except AttributeError:
            messagebox.showerror("错误", "当前系统不是 Windows，无法启动画图程序。")
        except Exception as e:
            messagebox.showerror("错误", f"无法启动画图程序: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageAnnotatorApp(root)
    root.mainloop()