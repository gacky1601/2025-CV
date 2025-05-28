from time import time

import cv2

from Mosse_Tracker.TrackerManager import Tracker, TrackerType, draw_trajectory
from System.Data.CONSTANTS import Work_Tracker_Type_Mosse


class Tracking:
    def __init__(self):
        pass

    def track(self,frames,boxes,frame_width,frame_height):
        trackers = []
        trackerId = 0
        frame = frames[0]
        for _, box in enumerate(boxes):
            xmin = int(box[1])
            xmax = int(box[2])
            ymin = int(box[3])
            ymax = int(box[4])

            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            trackerId += 1
            # no need for frame_width and frame_height
            xmax = min(xmax, frame_width - 1)
            ymax = min(ymax, frame_height - 1)

            if Work_Tracker_Type_Mosse:
                trackers.append(Tracker(frame_gray, (xmin, ymin, xmax, ymax), frame_width, frame_height, trackerId,TrackerType.MOSSE))
            else:
                trackers.append(Tracker(frame_gray, (xmin, ymin, xmax, ymax), frame_width, frame_height, trackerId,TrackerType.DLIB))

        t = time()
        tot = 0
        for i in range(1,len(frames)):
            frame = frames[i]
            frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            print(f"\n🟩 Frame {i+1} tracking results:")

            # updating trackers
            for i, tracker in enumerate(trackers):
                tracker.update(frame_gray)
                t1 = time()
                tracker.futureFramePosition()

                # 印出 ID 與當前框位置（bbox）與中心點
                bbox = tracker.getTrackerPosition()  # 正確寫法
                cx = int((bbox[0] + bbox[2]) / 2)
                cy = int((bbox[1] + bbox[3]) / 2)
                print(f"  🚗 ID {tracker.tracker_id} → bbox={bbox}, center=({cx}, {cy})")

                # 🔮 取得未來預測 bbox
                future_bbox = tracker.futureFramePosition()
                if future_bbox != (-1, -1, -1, -1):
                    fcx = int((future_bbox[0] + future_bbox[2]) / 2)
                    fcy = int((future_bbox[1] + future_bbox[3]) / 2)
                    print(f"    🔮 Predicted bbox={future_bbox}, center=({fcx}, {fcy})")
                else:
                    print("    🔮 Prediction skipped (not enough movement data)")
                
                draw_trajectory(frame, tracker, trail_length=20)  # 加上這行！

        return trackers
 