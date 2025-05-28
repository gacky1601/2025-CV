import sys
import os
import cv2
import torch
import yaml
import re
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog,
    QVBoxLayout, QHBoxLayout, QMessageBox, QScrollArea, QSizePolicy, QGridLayout, QFrame
)
from PyQt5.QtGui import QPixmap, QFont
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtMultimedia import QSound
from models.detect import run_yolov7
from time import sleep
from PyQt5.QtCore import QTimer


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def load_class_names(yaml_path):
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data['names']


def split_image_to_tiles(image_path, tile_size=512, save_dir="temp_tiles"):
    img = cv2.imread(image_path)
    h, w, _ = img.shape

    os.makedirs(save_dir, exist_ok=True)
    tiles = []
    positions = []  # 記錄tile偏移位置

    count = 0
    for y in range(0, h, tile_size):
        for x in range(0, w, tile_size):
            tile = img[y:y+tile_size, x:x+tile_size]
            tile_path = os.path.join(save_dir, f"tile_{count:04d}.png")
            cv2.imwrite(tile_path, tile)
            tiles.append(tile_path)
            positions.append((x, y))
            count += 1

    return tiles, positions, (w, h)


class DefectDetectionApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fabric Defect Detection")
        self.resize(1300, 800)

        # Default paths (user can overwrite)
        self.input_path = ""
        self.model_path = "E:/yolov7_gui/yolov7.pt"  # default model path
        self.output_path = "E:/yolov7_gui/output"     # default output folder

        self.yaml_path = "E:/yolov7_gui/defect_data.yaml"  # default yaml path
        self.class_names = load_class_names(self.yaml_path)

        self.max_image_size = QSize(1024, 1024)  # max allowed image size for display
        self.original_pixmap = None  # store original image
        self.defect_streak = 0  # ✅ 這一行是連續有瑕疵次數
        if torch.cuda.is_available() and torch.cuda.device_count() > 0:
            self.device_mode = "cuda:0"  # 預設選用第0張卡
        else:
            self.device_mode = "cpu"
        print(f"Device Mode Auto Selected: {self.device_mode}")
        self.init_ui()

    def init_ui(self):
        main_layout = QGridLayout(self)

        # Image Preview
        self.image_label = QLabel("Detection Result Preview")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(400, 400)
        self.image_label.setFont(QFont("Arial", 12)) 
        main_layout.addWidget(self.image_label, 0, 0, 3, 2)   # addWidget(widget, row, column, rowSpan, columnSpan)

        # Framed Info Section
        self.info_frame = QFrame()
        # elf.info_frame.setFrameShape(QFrame.StyledPanel)
        self.info_frame.setStyleSheet("background-color: white;")
        self.info_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame_layout = QVBoxLayout(self.info_frame)

        self.info_label = QLabel("Filename: \nDefects:")
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignTop)
        self.info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        frame_layout.addWidget(self.info_label)
        main_layout.addWidget(self.info_frame, 0, 2, 3, 2)

        main_layout.setRowStretch(0, 3)
        main_layout.setRowStretch(1, 3)
        main_layout.setRowStretch(2, 1)
        main_layout.setRowStretch(3, 1)

        # Buttons - Top Row
        top_button_layout = QHBoxLayout()

        self.btn_select_image = QPushButton("Select Image")
        self.btn_select_image.clicked.connect(self.select_image)
        top_button_layout.addWidget(self.btn_select_image)

        self.btn_select_folder = QPushButton("Select Folder")
        self.btn_select_folder.clicked.connect(self.select_folder)
        top_button_layout.addWidget(self.btn_select_folder)

        self.btn_model = QPushButton("Select Model")
        self.btn_model.clicked.connect(self.select_model)
        top_button_layout.addWidget(self.btn_model)

        self.btn_output = QPushButton("Select Output Folder")
        self.btn_output.clicked.connect(self.select_output)
        top_button_layout.addWidget(self.btn_output)

        self.btn_yaml = QPushButton("Select YAML File")
        self.btn_yaml.clicked.connect(self.select_yaml)
        top_button_layout.addWidget(self.btn_yaml)

        main_layout.addLayout(top_button_layout, 3, 0, 1, 4)

        # Run / Exit Buttons - Bottom Row
        bottom_button_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Detection")
        self.btn_run.clicked.connect(self.run_detection)
        bottom_button_layout.addWidget(self.btn_run)

        self.btn_exit = QPushButton("Exit")
        self.btn_exit.clicked.connect(self.close)
        bottom_button_layout.addWidget(self.btn_exit)

        main_layout.addLayout(bottom_button_layout, 4, 0, 1, 4)

        # 美化按鈕樣式與字體大小
        button_style = """
            QPushButton {
                background-color: #007ACC;
                color: white;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #005999;
            }
            QPushButton:pressed {
                background-color: #003F73;
            }
        """

        for btn in [
            self.btn_select_image, self.btn_select_folder, self.btn_model,
            self.btn_output, self.btn_yaml, self.btn_run, self.btn_exit
        ]:
            btn.setMinimumHeight(70)
            btn.setFont(QFont("Arial", 10))  # 字體大一點
            btn.setStyleSheet(button_style)

        self.setLayout(main_layout)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.original_pixmap:
            scaled_pix = self.original_pixmap.scaled(
                self.max_image_size.boundedTo(self.image_label.size()),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pix)

        # Dynamically scale font size based on height
        new_font_size = max(10, self.height() // 100)
        self.info_label.setFont(QFont("Arial", new_font_size))

    def select_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Images (*.jpg *.png *.jpeg *.bmp)")
        if file_path:
            self.input_path = file_path
            print("Image is loaded!")
            pixmap = QPixmap(file_path)
            self.original_pixmap = pixmap
            self.image_label.setPixmap(pixmap.scaled(self.max_image_size.boundedTo(self.image_label.size()), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.info_label.setText(f"Filename: {os.path.basename(file_path)}")

    def select_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder_path:
            self.input_path = folder_path
            self.info_label.setText(f"Folder: {folder_path}")

    def select_model(self):
        model_path, _ = QFileDialog.getOpenFileName(self, "Select YOLOv7 Model", "", "Model (*.pt)")
        if model_path:
            self.model_path = model_path
            self.info_label.setText(f"Model: {model_path}")

    def select_yaml(self):
        yaml_path, _ = QFileDialog.getOpenFileName(self, "Select YAML File", "", "YAML Files (*.yaml *.yml)")
        if yaml_path:
            self.yaml_path = yaml_path
            self.class_names = load_class_names(yaml_path)
            self.info_label.setText(f"Yaml: {yaml_path}")

    def select_output(self):
        output_path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if output_path:
            self.output_path = output_path
            self.info_label.setText(f"Output folder: {output_path}")

    def flash_warning_frame(self):
        self.info_frame.setStyleSheet("background-color: red;")
        QTimer.singleShot(500, lambda: self.info_frame.setStyleSheet("background-color: white;"))

    def run_detection(self):
        if not self.input_path:
            QMessageBox.warning(self, "Missing Input", "Please select an image or folder first.")
            return

        if os.path.isdir(self.input_path):
            self.run_folder_detection()
        else:
            self.run_single_image_detection()

    # def run_single_image_detection(self):
    #     base_name = os.path.basename(self.input_path)
    #     self.info_label.setText(f"Filename: {base_name} Detecting...\n")  # temporary message
    #     QApplication.processEvents()  # force UI to update

    #     # Run YOLOv7
    #     result_dir = run_yolov7(weights=self.model_path, source=self.input_path, output_dir=self.output_path)

    #     # Get result image and label
    #     if os.path.isfile(self.input_path):  # Single image mode
    #         result_img = os.path.join(result_dir, base_name)
    #         label_file = os.path.splitext(result_img)[0] + ".txt"
    #         if os.path.exists(result_img):
    #             pixmap = QPixmap(result_img)
    #             self.original_pixmap = pixmap
    #             self.image_label.setPixmap(pixmap.scaled(self.max_image_size.boundedTo(self.image_label.size()), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    #         defect_info = ""
    #         played_sound = False  # 新增旗標
    #         if os.path.exists(label_file):
    #             with open(label_file, "r") as f:
    #                 for line in f:
    #                     parts = line.strip().split()
    #                     cls_id = int(parts[0])
    #                     x, y, w, h = parts[1:5]
    #                     if self.class_names and cls_id < len(self.class_names):
    #                         cls_name = self.class_names[cls_id]
    #                     else:
    #                         cls_name = f"Class {cls_id}"
    #                     defect_info += f"{cls_name}: ({x}, {y}, {w}, {h})\n"

    #                     played_sound = True  # 有偵測到至少一項就記錄

    #         if played_sound:   # 如果有偵測到瑕疵就播放聲音
    #             QSound.play("siren.wav")

    #         self.info_label.setText(f"\nFilename: {base_name}\n{defect_info if defect_info else '\nNo defect detected.'}")

    #     else:
    #         QMessageBox.information(self, "Batch Mode", "Detection complete. Please check output folder.")

    def run_single_image_detection(self):
        start_time = time.time()  # ✅ 開始計時
        base_name = os.path.basename(self.input_path)
        self.info_label.setText(f"Filename: {base_name} Detecting...\n")
        QApplication.processEvents()

        # Step 1: 切小圖
        tile_dir = os.path.join(self.output_path, "tiles")
        tiles, positions, (img_w, img_h) = split_image_to_tiles(self.input_path, tile_size=512, save_dir=tile_dir)

        # Step 2: 載入原始圖像當背景
        big_image = cv2.imread(self.input_path)

        # Step 3: 一塊一塊送去YOLO檢測
        defect_info = ""
        played_sound = False
        for tile_path, (x_offset, y_offset) in zip(tiles, positions):
            result_dir = run_yolov7(weights=self.model_path, source=tile_path, output_dir=self.output_path, device=self.device_mode)
            label_file = os.path.splitext(os.path.join(result_dir, os.path.basename(tile_path)))[0] + ".txt"

            if os.path.exists(label_file):
                with open(label_file, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        cls_id = int(parts[0])
                        rel_x, rel_y, rel_w, rel_h = map(float, parts[1:5])

                        abs_x = int((rel_x - rel_w / 2) * 512) + x_offset
                        abs_y = int((rel_y - rel_h / 2) * 512) + y_offset
                        abs_w = int(rel_w * 512)
                        abs_h = int(rel_h * 512)

                        # 繪製框框在大圖上
                        cv2.rectangle(big_image, (abs_x, abs_y), (abs_x + abs_w, abs_y + abs_h), (0, 255, 0), 2)

                        cls_name = self.class_names[cls_id] if self.class_names and cls_id < len(self.class_names) else f"Class {cls_id}"
                        defect_info += f"{cls_name}: ({abs_x}, {abs_y}, {abs_w}, {abs_h})\n"
                        played_sound = True

        # Step 4: 顯示檢測後的大圖
        result_img_path = os.path.join(self.output_path, f"{base_name}_result.png")
        cv2.imwrite(result_img_path, big_image)

        pixmap = QPixmap(result_img_path)
        self.original_pixmap = pixmap
        self.image_label.setPixmap(pixmap.scaled(self.max_image_size.boundedTo(self.image_label.size()), Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Step 5: 播放警告聲音與更新資訊
        if played_sound:
            QSound.play("siren.wav")

        self.info_label.setText(f"\nFilename: {base_name}\n{defect_info if defect_info else 'No defect detected.'}")

        # ✅ 加在偵測完之後：
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"Detection completed in {elapsed_time:.2f} seconds.")  # ✅ log 輸出

        # ✅ (可選) 顯示在 GUI info panel
        self.info_label.setText(
            self.info_label.text() + f"\nExecution time: {elapsed_time:.2f} s"
        )


    def run_folder_detection(self):
        if not os.path.isdir(self.input_path):
            QMessageBox.warning(self, "Folder Error", "Please select a valid folder.")
            return

        image_exts = ('.jpg', '.jpeg', '.png', '.bmp')
        all_files = os.listdir(self.input_path)
        image_files = [f for f in all_files if f.lower().endswith(image_exts)]
        image_files.sort(key=natural_sort_key)

        if not image_files:
            QMessageBox.information(self, "No Images", "No valid image files found in the folder.")
            return

        for img_name in image_files:
            img_path = os.path.join(self.input_path, img_name)

            single_start_time = time.time()  # ✅ 單張開始時間

            # Run detection
            result_dir = run_yolov7(weights=self.model_path, source=img_path, output_dir=self.output_path, device=self.device_mode)
            result_img = os.path.join(result_dir, img_name)
            label_file = os.path.splitext(result_img)[0] + ".txt"

            # 顯示圖片
            if os.path.exists(result_img):
                pixmap = QPixmap(result_img)
                self.original_pixmap = pixmap
                self.image_label.setPixmap(pixmap.scaled(
                    self.max_image_size.boundedTo(self.image_label.size()),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))

            # 顯示瑕疵資訊並播放聲音
            defect_info = ""
            played_sound = False

            if os.path.exists(label_file):
                with open(label_file, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        cls_id = int(parts[0])
                        x, y, w, h = parts[1:5]
                        cls_name = self.class_names[cls_id] if self.class_names and cls_id < len(self.class_names) else f"Class {cls_id}"
                        defect_info += f"{cls_name}: ({x}, {y}, {w}, {h})\n"
                        played_sound = True

            single_end_time = time.time()  # ✅ 單張結束時間
            single_elapsed = single_end_time - single_start_time
            print(f"{img_name} detection completed in {single_elapsed:.2f} seconds.")

            # ✅ 更新 GUI info
            self.info_label.setText(
                f"\nFilename: {img_name}\n{defect_info if defect_info else 'No defect detected.'}\nTime: {single_elapsed:.2f}s"
            )
            QApplication.processEvents()

            # 播放聲音：只有連續瑕疵第一張會響
            if played_sound:
                QSound.play("siren.wav")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DefectDetectionApp()
    window.show()
    sys.exit(app.exec_())
