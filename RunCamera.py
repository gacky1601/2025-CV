import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import cv2
import numpy as np
import zmq
import random
from pygame import mixer
from System.Data.CONSTANTS import *
from System.CameraNode import CameraNode

vidpath = ''
cities = ['Cairo', 'Alexandria', 'Gizah', 'Shubra El-Kheima', 'Port Said', 'Suez', 'Luxor', 'Al-Mansura',
         'Tanta', 'Asyut', 'Ismailia', 'Fayyum', 'Zagazig', 'Aswan', 'Damietta',
          'Damanhur', 'Al-Minya', 'Beni Suef', 'Qena', 'Sohag', 'Hurghada', 'Shibin El Kom',
          'Banha', 'Arish', 'Mallawi', 'Bilbais', 'Marsa Matruh',
          'Idfu, Mit Ghamr', 'Al-Hamidiyya', 'Desouk', 'Qalyub', 'Abu Kabir', 'Girga', 'Akhmim', 'Matareya']


class Button(QPushButton):
    def __init__(self, title, parent):
        super().__init__(title, parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.accept()
        else:
            e.ignore()

    def dropEvent(self, e):
        global vidpath
        if e.mimeData().hasUrls():
            self.parent().loadVideo(e.mimeData().urls()[0].toLocalFile())
            vidpath = e.mimeData().urls()[0].toLocalFile()
            print(vidpath)


class CameraNotificationListener(QObject):
    receive = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://" + CAMERAGUIIP + ":" + str(CAMERAGUIPORT))

    @pyqtSlot()
    def run(self):
        while True:
            message = self.socket.recv_pyobj()
            self.socket.send_pyobj("")
            self.receive.emit(message)



class Client(QWidget):
    def __init__(self, port=MASTERPORT, ip=MASTERIP):
        super().__init__()

        # self.setWindowTitle('Crash Detection')
        self.setWindowIcon(QIcon('UI/crash_detection.png'))
        self.setWindowTitle('CV Project: Road Traffic Accidents Detection')
        # self.setGeometry(200, 100, 900, 600)
        self.setGeometry(300, 50, 1100, 1200)

        font = QFont('SansSerif', 12)
        font.setBold(True)

        self.video_cap = None
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self.updateFrame)

        # 啟動 crash listener
        self.listener = CameraNotificationListener()
        self.listener_thread = QThread()
        self.listener.moveToThread(self.listener_thread)
        self.listener.receive.connect(self.handleCrashNotification)
        self.listener_thread.started.connect(self.listener.run)
        self.listener_thread.start()


        # ========= UI元件 =========
        # 標題Label
        self.titleLabel = QLabel("CV Project: Road Traffic Accidents Detection", self)
        self.titleLabel.setFont(QFont('SansSerif', 24, QFont.Bold))
        self.titleLabel.setGeometry(100, 80, 900, 60)

        self.processing_lable = self.make_lable('Processing...', 850, 30, 120, 40, True, 10)
        self.processing_lable.setVisible(False)
        self.gif = QMovie('UI/loading.gif')
        self.gif.setScaledSize(QSize(40, 40))
        self.processing_lable.setMovie(self.gif)
        # self.gif.start()

        self.select_vid = Button("📁 Select Video", self)
        self.select_vid.setGeometry(225, 215, 200, 80)
        self.select_vid.setFont(font)
        self.select_vid.setStyleSheet(self.buttonStyle())
        self.select_vid.clicked.connect(self.getfiles)

        self.process_btn = QPushButton("⚙️ Process", self)
        self.process_btn.setGeometry(475, 215, 200, 80)
        self.process_btn.setFont(font)
        self.process_btn.setStyleSheet(self.buttonStyle())
        self.process_btn.clicked.connect(self.sendToBk)

        self.play_vid = QPushButton(self)
        self.play_vid.setGeometry(135, 350, 850, 550)
        self.play_vid.setStyleSheet("background-color: #000000; border: 2px solid #888;")
        self.play_vid.clicked.connect(self.playVideo)

        # Logo at top-right corner
        self.logo_label = QLabel(self)
        self.logo_label.setGeometry(800, 180, 150, 150)
        logo = QPixmap("UI/crash_detection.png").scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.logo_label.setPixmap(logo)

        self.results = QListWidget(self)
        self.results.setGeometry(135, 950, 850, 200)
        self.results.setStyleSheet("background-color: #F0F0F0; border: 1px solid #999;")
        self.results.itemDoubleClicked.connect(self.listwidgetClicked)

        context = zmq.Context()
        print("Connecting to server...")
        self.socket = context.socket(zmq.REQ)
        self.socket.connect("tcp://" + ip + ":" + str(port))


        
    def handleCrashNotification(self, msg):
        if msg.get(FUNCTION) == NOTIFICATION:
            def delayed_alert():
                mixer.init()
                mixer.music.load('UI/siren.mp3')
                mixer.music.play()

                self.appendToList(
                    ID=msg[CAMERA_ID],
                    Image=msg[CRASH_PIC],
                    Date=msg[CRASH_TIME],
                    Time=msg[CRASH_TIME],
                    City=msg[CITY],
                    Location=msg[DISTRICT],
                    startFrame=msg[STARTING_FRAME_ID]
                )

            QTimer.singleShot(1000, delayed_alert)  # 延遲 3000 毫秒觸發 siren + 顯示
            # mixer.init()
            # mixer.music.load('UI/siren.mp3')
            # mixer.music.play()

            # self.appendToList(
            #     ID=msg[CAMERA_ID],
            #     Image=msg[CRASH_PIC],
            #     Date=msg[CRASH_TIME],
            #     Time=msg[CRASH_TIME],
            #     City=msg[CITY],
            #     Location=msg[DISTRICT],
            #     startFrame=msg[STARTING_FRAME_ID]
            # )

        elif msg.get(FUNCTION) == REP_VIDEO:
            self.playVideoFrames(msg[FRAMES])

    def appendToList(self, ID, Image, Date, Time, City, Location, startFrame):
        itemN = QListWidgetItem()
        widget = QWidget()

        widgetText = QLabel()
        if not isinstance(Image, np.ndarray):
            img = cv2.imread('UI/notfound.png')
        else:
            img = Image
        img = cv2.resize(img, (120, 90), interpolation=cv2.INTER_AREA)
        height, width, channel = img.shape
        bytesPerLine = 3 * width
        qImg = QImage(img.data, width, height, bytesPerLine, QImage.Format_BGR888)
        pixmap = QPixmap(qImg)
        widgetText.setPixmap(pixmap)

        startFrameID = QLabel()
        startFrameID.setText(f"{startFrame},{ID}")
        startFrameID.hide()

        info = QLabel()
        font = QFont('SansSerif', 9)
        font.setBold(True)
        info.setFont(font)
        info.setText(f"📹 Camera {ID}  |  {Date}")

        layout = QHBoxLayout()
        layout.addWidget(widgetText)
        layout.addWidget(info)
        layout.addWidget(startFrameID)
        layout.setStretch(1, 2)
        widget.setLayout(layout)

        itemN.setSizeHint(widget.sizeHint())
        self.results.insertItem(0, itemN)
        self.results.setItemWidget(itemN, widget)

    def listwidgetClicked(self, item):
        item = self.results.itemWidget(item)
        info = item.children()[-1]
        startFrameID, cameraID = info.text().split(',')
        self.requestCrashVideo(int(cameraID), int(startFrameID))

    def requestCrashVideo(self, camera_id, starting_frame_id):
        sendingMsg = {
            FUNCTION: REQ_VIDEO,
            CAMERA_ID: camera_id,
            STARTING_FRAME_ID: starting_frame_id
        }
        self.socket.send_pyobj(sendingMsg)
        self.socket.recv_pyobj()

    def playVideoFrames(self, frames):
        cv2.namedWindow("Crash Footage", cv2.WINDOW_NORMAL)  # 先創建視窗
        cv2.resizeWindow("Crash Footage", 1280, 720)          # 調整大小
        cv2.moveWindow("Crash Footage", 750, 600)           # 這裡控制位置 (x=100, y=100)

        for frame in frames:
            cv2.imshow("Crash Footage", frame)
            if cv2.waitKey(31) & 0xFF == ord('q'):
                break
        cv2.destroyAllWindows()

    def buttonStyle(self):
        return """
        QPushButton {
            background-color: #2d89ef;
            color: white;
            border-radius: 8px;
            padding: 8px 16px;
        }
        QPushButton:hover {
            background-color: #1b5faa;
        }
        """

    def sendToBk(self):
        global vidpath, cities

        if vidpath == '':
            return

        self.processing_lable.setVisible(True)

        # ✅ 每次送出處理時清除 list
        self.results.clear()

        video_id = vidpath.split('/')[-1].split('.')[0]
        try:
            video_id = int(video_id)
        except:
            video_id = random.randint(1000, 9999)

        CameraNode(video_id, 'videos/' + str(video_id) + '.mp4', files=Work_Detect_Files,
                   city=random.choice(cities), district_no='District ' + str(random.randint(1, 30))).start()
        self.playVideo()

    def playVideo(self):
        global vidpath
        if vidpath == '':
            return

        self.video_cap = cv2.VideoCapture(vidpath)
        if not self.video_cap.isOpened():
            print("Error opening video file")
            return

        self.video_timer.start(30)  # 每 30ms 播一幀（約等於 33 fps）

        # cap = cv2.VideoCapture(vidpath)
        # if not cap.isOpened():
        #     print("Error opening video file")
        #     return
        
        # while cap.isOpened():
        #     ret, frame = cap.read()
        #     if ret:
        #         cv2.namedWindow('Frame', cv2.WINDOW_NORMAL)
        #         cv2.resizeWindow('Frame', 1280, 720)
        #         cv2.imshow('Frame', frame)
        #         if cv2.waitKey(25) & 0xFF == ord('q'):
        #             break
        #     else:
        #         break
        # cap.release()
        # cv2.destroyAllWindows()

    def updateFrame(self):
        if not self.video_cap:
            return

        ret, frame = self.video_cap.read()
        if not ret:
            self.video_timer.stop()
            self.video_cap.release()
            self.video_cap = None
            return

        frame = cv2.resize(frame, (850, 550))  # 調整為 self.play_vid 大小
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        qt_img = QImage(frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_img)

        # ✅ 將影片畫面顯示到 self.play_vid 這個 QPushButton 上
        self.play_vid.setIcon(QIcon(pixmap))
        self.play_vid.setIconSize(QSize(850, 550))

    def getfiles(self):
        global vidpath

        fileName, _ = QFileDialog.getOpenFileName(self, 'Select Video File', 'C:/', '*.mp4 *.mkv *.avi')
        if fileName == '':
            return
        self.loadVideo(path=fileName)
        vidpath = fileName
        print('Video path:', vidpath)

    def loadVideo(self, path=''):
        cap = cv2.VideoCapture(path)
        ret, frame = cap.read()
        if not ret:
            return

        img = cv2.resize(frame, (351, 241))
        button = cv2.imread('UI/Play-Button-PNG-Picture.png')
        button = cv2.resize(button, (111, 111))

        height_needed = 241 - button.shape[0]
        width_needed = 351 - button.shape[1]
        top, bottom = height_needed // 2, height_needed - height_needed // 2
        left, right = width_needed // 2, width_needed - width_needed // 2

        border = cv2.copyMakeBorder(button, top, bottom, left, right, cv2.BORDER_CONSTANT, value=0)
        border = np.where(border < 150, img, border)
        border = cv2.resize(border, (850, 550))

        cv2.imwrite('UI/tempToLoad.png', border)
        self.play_vid.setStyleSheet("background-image : url(UI/tempToLoad.png);")

    def make_lable(self, text, x, y, width, height, bold=False, font=12):
        label = QLabel(self)
        label.setText(text)
        label.setGeometry(x, y, width, height)
        f = QFont('SansSerif', font)
        if bold:
            f.setBold(True)
        label.setFont(f)
        return label


if __name__ == "__main__":
    app = QApplication(sys.argv)
    form = Client()
    form.show()
    sys.exit(app.exec_())