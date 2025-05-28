import sys
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import cv2
import zmq
from numpy.core.multiarray import ndarray
from pygame import mixer

from System.Data.CONSTANTS import *
from System.Controller.JsonEncoder import JsonEncoder

class WorkerThread(QObject):
    receive = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://" + GUIIP + ":" + str(GUIPORT))

    @pyqtSlot()
    def run(self):
        while True:
            message = self.socket.recv_pyobj()
            self.socket.send_pyobj("")
            self.receive.emit(message)


class SearchForm(QWidget):
    def __init__(self, port=GUIPORT, ip=GUIIP):
        super().__init__()

        self.encoder = JsonEncoder()
        self.setWindowIcon(QIcon('UI/crash_detection.png'))
        self.setWindowTitle('CV Project: Road Traffic Accidents Detection')
        self.setGeometry(300, 50, 1100, 950)  # 改大一點

        self.setStyleSheet("background-color: #D3D3D3;")

        # 設定背景圖片
        oImage = QImage("UI/crash_detection.png")
        sImage = oImage.scaled(QSize(300, 200))
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(sImage))
        self.setPalette(palette)

        self.worker = WorkerThread()
        self.workerThread = QThread()
        self.workerThread.started.connect(self.worker.run)
        self.worker.receive.connect(self.decode)
        self.worker.moveToThread(self.workerThread)
        self.workerThread.start()

        # ========= UI元件 =========
        # 標題Label
        self.titleLabel = QLabel("CV Project: Road Traffic Accidents Detection", self)
        self.titleLabel.setFont(QFont('SansSerif', 20, QFont.Bold))
        # self.titleLabel.setAlignment(Qt.AlignCenter)
        self.titleLabel.setGeometry(100, 50, 800, 40)

        # Camera ID 搜尋欄位
        self.make_lable('Camera ID:', 150, 140, 170, 35, bold=True, font=14)
        self.cameraIDEdit = QLineEdit(self)
        self.cameraIDEdit.setGeometry(300, 140, 150, 30)

        # 搜尋按鈕
        search = QPushButton("Search", self)
        # search.setGeometry(450, 135, 80, 35)
        search.clicked.connect(self.searchClicked)
        search.setGeometry(480, 130, 120, 50)
        search.setFont(QFont('SansSerif', 12, QFont.Bold))  # 字體大小 & 加粗

        # 顯示最近紀錄按鈕
        recent = QPushButton("Recent", self)
        # recent.setGeometry(550, 135, 80, 35)
        recent.clicked.connect(self.recentlyClicked)
        recent.setGeometry(610, 130, 120, 50)
        recent.setFont(QFont('SansSerif', 12, QFont.Bold))

        # 顯示事故紀錄清單
        self.results = QListWidget(self)
        self.results.setGeometry(100, 220, 900, 700)
        self.results.itemDoubleClicked.connect(self.listwidgetClicked)
        self.results.setStyleSheet("background-color: #C0C0C0;")

        # Logo 圖示
        widgetText = QLabel(self)
        widgetText.setGeometry(900, 35, 150, 150)
        img = QImage("UI/crash_detection.png").convertToFormat(QImage.Format_ARGB32)
        pixmap = QPixmap(img).scaled(150, 150, Qt.KeepAspectRatio)
        widgetText.setPixmap(pixmap)

        # 初始載入
        self.recentlyClicked()

    def make_lable(self, text, x, y, width, height, bold=False, font=12):
        label = QLabel(text, self)
        label.setGeometry(x, y, width, height)
        f = QFont('SansSerif', font)
        if bold:
            f.setBold(True)
        label.setFont(f)
        return label

    def searchClicked(self):
        camera_id = self.cameraIDEdit.text()
        if camera_id.isdigit():
            self.encoder.requestCameraIdData(int(camera_id))
        else:
            QMessageBox.warning(self, "Invalid Input", "請輸入有效的Camera ID（數字）")

    def recentlyClicked(self):
        self.encoder.getRecentCrashes()

    def listwidgetClicked(self, item):
        item = self.results.itemWidget(item)
        info = item.children()[-1]
        startFrameID, cameraID = info.text().split(',')
        self.encoder.requestVideo(camera_id=int(cameraID), starting_frame_id=int(startFrameID))

    def appendToList(self, ID=3, Image=None, Date='a', Time='d', City='f', Location='g', startFrame=1, list=True):
        itemN = QListWidgetItem()
        widget = QWidget()

        widgetText = QLabel()
        img = Image if isinstance(Image, ndarray) else cv2.imread('UI/notfound.png')
        img = cv2.resize(img, (120, 100))
        qImg = QImage(img.data, img.shape[1], img.shape[0], img.shape[1]*3, QImage.Format_BGR888)
        pixmap = QPixmap(qImg)
        widgetText.setPixmap(pixmap)

        startFrameID = QLabel(f"{startFrame},{ID}")
        startFrameID.hide()

        info = QLabel(f"   Camera Id: {ID}  Date: {Date}    City: {City}   Location: {Location}")
        info.setFont(QFont('SansSerif', 10, QFont.Bold))

        layout = QHBoxLayout()
        layout.addWidget(widgetText)
        layout.addWidget(info)
        layout.addWidget(startFrameID)
        layout.addStretch()
        layout.setSizeConstraint(QLayout.SetFixedSize)
        widget.setLayout(layout)
        widget.setStyleSheet("background-color: none;")

        itemN.setSizeHint(widget.sizeHint())

        if list:
            self.results.addItem(itemN)
            self.results.setItemWidget(itemN, widget)
        else:
            mixer.init()
            mixer.music.load('UI/siren.mp3')
            mixer.music.play()
            itemN.setBackground(QColor('#7fc97f'))
            self.results.insertItem(0, itemN)
            self.results.setItemWidget(itemN, widget)

    def playVideo(self, video):
        for frame in video:
            cv2.namedWindow('Frame', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('Frame', 1280, 720)
            cv2.imshow('Frame', frame)
            if cv2.waitKey(31) & 0xFF == ord('q'):
                break
        cv2.destroyAllWindows()

    def decode(self, msg):
        func = msg[FUNCTION]
        if func == REP_QUERY:
            self.results.clear()
            for item in msg[LIST_OF_CRASHES]:
                self.appendToList(ID=item[CAMERA_ID], Image=item[CRASH_PIC], Date=item[CRASH_TIME], Time=item[CRASH_TIME],
                                  City=item[CITY], Location=item[DISTRICT], startFrame=item[STARTING_FRAME_ID], list=True)
        elif func == NOTIFICATION:
            self.appendToList(ID=msg[CAMERA_ID], Image=msg[CRASH_PIC], Date=msg[CRASH_TIME], Time=msg[CRASH_TIME],
                              City=msg[CITY], Location=msg[DISTRICT], startFrame=msg[STARTING_FRAME_ID], list=False)
        elif func == REP_VIDEO:
            self.playVideo(msg[FRAMES])

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    form = SearchForm()
    form.show()
    sys.exit(app.exec_())
