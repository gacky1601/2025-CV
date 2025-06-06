# -*- coding: utf-8 -*-
"""
Class definition of YOLO_v3 style detection model on image and video
"""
import colorsys
from timeit import default_timer as timer

import numpy as np
from keras import backend as K
from keras.models import load_model
from keras.layers import Input
from PIL import Image, ImageFont, ImageDraw

from Car_Detection_TF.yolo3.model import yolo_eval, yolo_body, tiny_yolo_body
from Car_Detection_TF.yolo3.utils import letterbox_image
import os
from keras.utils import multi_gpu_model

class YOLO(object):
    _defaults = {
        "model_path": 'Car_Detection_TF/model_data/yolo.h5',
        "anchors_path": 'Car_Detection_TF/model_data/yolo_anchors.txt',
        "classes_path": 'Car_Detection_TF/model_data/coco_classes.txt',
        "score": 0.3,
        "iou": 0.45,
        "model_image_size": (416, 416),
        "gpu_num": 1,
    }

    @classmethod
    def get_defaults(cls, n):
        if n in cls._defaults:
            return cls._defaults[n]
        else:
            return "Unrecognized attribute name '" + n + "'"

    def __init__(self, **kwargs):
        self.__dict__.update(self._defaults) # set up default values
        self.__dict__.update(kwargs) # and update with user overrides
        self.class_names = self._get_class()
        self.anchors = self._get_anchors()
        self.sess = K.get_session()
        self.boxes, self.scores, self.classes = self.generate()

    def _get_class(self):
        classes_path = os.path.expanduser(self.classes_path)
        with open(classes_path) as f:
            class_names = f.readlines()
        class_names = [c.strip() for c in class_names]
        return class_names

    def _get_anchors(self):
        anchors_path = os.path.expanduser(self.anchors_path)
        with open(anchors_path) as f:
            anchors = f.readline()
        anchors = [float(x) for x in anchors.split(',')]
        return np.array(anchors).reshape(-1, 2)

    def generate(self):
        model_path = os.path.expanduser(self.model_path)
        assert model_path.endswith('.h5'), 'Keras model or weights must be a .h5 file.'

        # Load model, or construct model and load weights.
        num_anchors = len(self.anchors)
        num_classes = len(self.class_names)
        is_tiny_version = num_anchors==6 # default setting
        try:
            self.yolo_model = load_model(model_path, compile=False)
        except:
            self.yolo_model = tiny_yolo_body(Input(shape=(None,None,3)), num_anchors//2, num_classes) \
                if is_tiny_version else yolo_body(Input(shape=(None,None,3)), num_anchors//3, num_classes)
            self.yolo_model.load_weights(self.model_path) # make sure model, anchors and classes match
        else:
            assert self.yolo_model.layers[-1].output_shape[-1] == \
                num_anchors/len(self.yolo_model.output) * (num_classes + 5), \
                'Mismatch between model and given anchor and class sizes'

        print('{} model, anchors, and classes loaded.'.format(model_path))

        # Generate colors for drawing bounding boxes.
        hsv_tuples = [(x / len(self.class_names), 1., 1.)
                      for x in range(len(self.class_names))]
        self.colors = list(map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples))
        self.colors = list(
            map(lambda x: (int(x[0] * 255), int(x[1] * 255), int(x[2] * 255)),
                self.colors))
        np.random.seed(10101)  # Fixed seed for consistent colors across runs.
        np.random.shuffle(self.colors)  # Shuffle colors to decorrelate adjacent classes.
        np.random.seed(None)  # Reset seed to default.

        # Generate output tensor targets for filtered bounding boxes.
        self.input_image_shape = K.placeholder(shape=(2, ))
        if self.gpu_num>=2:
            self.yolo_model = multi_gpu_model(self.yolo_model, gpus=self.gpu_num)
        boxes, scores, classes = yolo_eval(self.yolo_model.output, self.anchors,
                len(self.class_names), self.input_image_shape,
                score_threshold=self.score, iou_threshold=self.iou)
        return boxes, scores, classes

    def intersection_over_union(self, boxA, boxB, threshold=0.5):
        if boxA[0] >= boxB[0] and boxA[1] >= boxB[1] and boxA[2] <= boxB[2] and boxA[3] <= boxB[3]:
            # print('dfdgh', boxA, boxB)
            # time.sleep(555)
            return True
        if boxB[0] >= boxA[0] and boxB[1] >= boxA[1] and boxB[2] <= boxA[2] and boxB[3] <= boxA[3]:
            # print('1fdgh', boxA, boxB)
            # time.sleep(555)
            return True


        xA = max(boxA[1], boxB[1])
        yA = max(boxA[0], boxB[0])
        xB = min(boxA[3], boxB[3])
        yB = min(boxA[2], boxB[2])

        # print(xA, xB, yA, yB)
        # print(abs(xB-xA))
        # compute the area of intersection rectangle
        interArea = max(xB - xA, 0) * max((yB - yA), 0)
        # interArea = abs(max((xA - xB, 0)) * max((yA - yB), 0))
        if interArea == 0:
            return False
        # compute the area of both the prediction and ground-truth
        # rectangles
        boxAArea = (boxA[3] - boxA[1]) * (boxA[2] - boxA[0])
        boxBArea = (boxB[3] - boxB[1]) * (boxB[2] - boxB[0])

        # compute the intersection over union by taking the intersection
        # area and dividing it by the sum of prediction + ground-truth
        # areas - the interesection area
        iou = interArea / float(boxAArea + boxBArea - interArea)
        # print('****************************', iou)
        if iou >= threshold:
            return True
        # return the intersection over union value
        return False

    def filterBoxes(self, t, c, out_boxes, out_classes, out_scores, same=False):
        index = []
        # print('-----------------------', t, c)
        for i, Truck in enumerate(t):
            for j, Car in enumerate(c):
                if same and i == j:
                    continue
                if self.intersection_over_union(Truck[0], Car[0]):
                    if Truck[1] > Car[1]:
                        index.append(Car[2])

                    else:
                        index.append(Truck[2])
                    break

        out_classes = np.delete(out_classes, index, 0)
        out_boxes = np.delete(out_boxes, index, 0)
        out_scores = np.delete(out_scores, index, 0)
        return out_boxes, out_classes, out_scores

    def detect_image(self, image, save_txt_path=None):
        start = timer()

        if self.model_image_size != (None, None):
            assert self.model_image_size[0]%32 == 0, 'Multiples of 32 required'
            assert self.model_image_size[1]%32 == 0, 'Multiples of 32 required'
            boxed_image = letterbox_image(image, tuple(reversed(self.model_image_size)))
        else:
            new_image_size = (image.width - (image.width % 32),
                              image.height - (image.height % 32))
            boxed_image = letterbox_image(image, new_image_size)
        image_data = np.array(boxed_image, dtype='float32')

        image_data /= 255.
        image_data = np.expand_dims(image_data, 0)  # Add batch dimension.

        out_boxes, out_scores, out_classes = self.sess.run(
            [self.boxes, self.scores, self.classes],
            feed_dict={
                self.yolo_model.input: image_data,
                self.input_image_shape: [image.size[1], image.size[0]],
                K.learning_phase(): 0
            })

        print('Found {} boxes for {}'.format(len(out_boxes), 'img'))

        font = ImageFont.truetype(font='Car_Detection_TF/font/FiraMono-Medium.otf',
                    size=np.floor(3e-2 * image.size[1] + 0.5).astype('int32'))
        thickness = (image.size[0] + image.size[1]) // 300
        ret = []
        cc = []
        t = []
        b = []
        ind = []
        for i, c in reversed(list(enumerate(out_classes))):
            if (out_boxes[i][2]-out_boxes[i][0])*(out_boxes[i][3]-out_boxes[i][1]) > 0.75*480*360:
                ind.append(i)

            if self.class_names[c] == 'car':
                cc.append([out_boxes[i], out_scores[i], i])
            elif self.class_names[c] == 'truck':
                t.append([out_boxes[i], out_scores[i], i])
            elif self.class_names[c] == 'bus':
                b.append([out_boxes[i], out_scores[i], i])

        out_classes = np.delete(out_classes, ind, 0)
        out_boxes = np.delete(out_boxes, ind, 0)
        out_scores = np.delete(out_scores, ind, 0)

        out_boxes, out_classes, out_scores = self.filterBoxes(t, cc, out_boxes, out_classes, out_scores)
        out_boxes, out_classes, out_scores = self.filterBoxes(t, b, out_boxes, out_classes, out_scores)
        out_boxes, out_classes, out_scores =self.filterBoxes(b, cc, out_boxes, out_classes, out_scores)
        out_boxes, out_classes, out_scores =self.filterBoxes(cc, cc, out_boxes, out_classes, out_scores, same=True)
        # print(out_boxes)

        for i, c in reversed(list(enumerate(out_classes))):
            # if i != len(list(out_classes)) - 1 and self.intersection_over_union(out_boxes[i], out_boxes[i+1]):
            #     continue

            predicted_class = self.class_names[c]
            box = out_boxes[i]
            score = out_scores[i]

            if predicted_class != 'car'and predicted_class != 'truck' and predicted_class != 'bus':
                continue

            label = '{} {:.2f}'.format(predicted_class, score)
            draw = ImageDraw.Draw(image)
            label_size = draw.textsize(label, font)

            top, left, bottom, right = box
            ret.append([predicted_class, left, right, top, bottom, score])
            top = max(0, np.floor(top + 0.5).astype('int32'))
            left = max(0, np.floor(left + 0.5).astype('int32'))
            bottom = min(image.size[1], np.floor(bottom + 0.5).astype('int32'))
            right = min(image.size[0], np.floor(right + 0.5).astype('int32'))
            # print(label, (left, top), (right, bottom))

            if top - label_size[1] >= 0:
                text_origin = np.array([left, top - label_size[1]])
            else:
                text_origin = np.array([left, top + 1])

            # My kingdom for a good redistributable image drawing library.
            for i in range(thickness):
                draw.rectangle(
                    [left + i, top + i, right - i, bottom - i],
                    outline=self.colors[c])
            draw.rectangle(
                [tuple(text_origin), tuple(text_origin + label_size)],
                fill=self.colors[c])
            draw.text(text_origin, label, fill=(0, 0, 0), font=font)
            del draw

        end = timer()
        # print(end - start)

        # ✅ 儲存 box 資訊
        if save_txt_path:
            import os
            os.makedirs(os.path.dirname(save_txt_path), exist_ok=True)
            with open(save_txt_path, 'a') as f:
                f.write("--\n")
                for item in ret:
                    label, left, right, top, bottom, score = item
                    f.write(f"{label} {left:.6f} {right:.6f} {top:.6f} {bottom:.6f} {score:.6f}\n")

        return image, ret

    def close_session(self):
        self.sess.close()

def detect_video(yolo, video_path, output_path=""):
    import cv2
    vid = cv2.VideoCapture(video_path)
    # os.makedirs("boxes", exist_ok=True)
    # print(f"[INFO] Start detecting {video_path}, will save to boxes/{video_path}.txt")

    if not vid.isOpened():
        raise IOError("Couldn't open webcam or video")
    video_FourCC = int(vid.get(cv2.CAP_PROP_FOURCC))
    video_fps = vid.get(cv2.CAP_PROP_FPS)
    video_size = (int(vid.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        int(vid.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    isOutput = True if output_path != "" else False
    if isOutput:
        print("!!! TYPE:", type(output_path), type(video_FourCC), type(video_fps), type(video_size))
        out = cv2.VideoWriter(output_path, video_FourCC, video_fps, video_size)
    accum_time = 0
    curr_fps = 0
    fps = "FPS: ??"
    prev_time = timer()

    video_path = video_path.split('/')
    video_path = video_path[len(video_path) - 1].split('.')[0]

    count = 1
    while True:
        return_value, frame = vid.read()
        if not return_value:
            return
        image = Image.fromarray(frame)
        image, ret = yolo.detect_image(image)

        f = open("boxes/" + video_path + ".txt", "a")
        f.write("--" + '\n')
        count = count + 1
        print('lllllllllllllllllllllllllllllllllllllllllllll')
        for k in range(len(ret)):
            print('aaaaaaaaaaaaaaaaaaaaaaaaa',type(ret[k][0]))
            f.write(str(ret[k][0])+' '+str(ret[k][1])+' '+str(ret[k][2])+' '+str(ret[k][3])+' '+str(ret[k][4])+' '+str(ret[k][5])+'\n')
        f.close()
        result = np.asarray(image)
        curr_time = timer()
        exec_time = curr_time - prev_time
        prev_time = curr_time
        accum_time = accum_time + exec_time
        curr_fps = curr_fps + 1
        if accum_time > 1:
            accum_time = accum_time - 1
            fps = "FPS: " + str(curr_fps)
            curr_fps = 0
        cv2.putText(result, text=fps, org=(3, 15), fontFace=cv2.FONT_HERSHEY_SIMPLEX,
                    fontScale=0.50, color=(255, 0, 0), thickness=2)
        cv2.namedWindow("result", cv2.WINDOW_NORMAL)
        cv2.imshow("result", result)
        if isOutput:
            out.write(result)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            f.close()
            break
    yolo.close_session()

