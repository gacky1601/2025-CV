import cv2
from PIL import Image
from Car_Detection.detect import detect_image
from Car_Detection.darknet import Darknet
import numpy as np
from Car_Detection_TF.yolo import YOLO
from Mosse_Tracker.TrackerManager import Tracker


class Detection:
    def __init__(self,yolo):
        self.yolo = yolo

#uncomment these two lines if you will use yolo
        # self.model = Darknet("E:/road_crash_detection/Car_Detection/config/yolov3.cfg", CUDA=False)
        # self.model.load_weight("E:/road_crash_detection/Car_Detection/config/yolov3.weights")


    def detect(self,frames,frame_width,frame_height,read_file,boxes_file = None, read_file_self=False, tf=True, save_txt_path=None):
        boxes = []
        # detect vehicles
        if read_file_self:
            # From files
            boxes = boxes_file
        elif tf:   # 目前走這段~
            img = Image.fromarray(frames[0])
            _, boxes = self.yolo.detect_image(img, save_txt_path=save_txt_path)
        else:
            boxes = detect_image(frames[0], self.model)

        return boxes