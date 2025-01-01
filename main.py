import ctypes
import time
import threading
import math
from ultralytics import YOLO
import bettercam
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen
from PyQt5.QtWidgets import QApplication, QMainWindow
import os

# Constants for Mouse Input
PUL = ctypes.POINTER(ctypes.c_ulong)

class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]

class Input_I(ctypes.Union):
    _fields_ = [("mi", MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", Input_I)]

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# Default State Values
softaim = False
strength = 0.01
confidence = 0.01
fovcircle = False
fovsize = 10
boxes = False
aimbone = "Head"
right_mouse_button_code = 0x02  # Virtual key code for right mouse button
MAX_FOV_SIZE = 150

# BETTERCAM CONFIG
MONITOR_WIDTH = ctypes.windll.user32.GetSystemMetrics(0)
MONITOR_HEIGHT = ctypes.windll.user32.GetSystemMetrics(1)
FRAME_SIZE = (MAX_FOV_SIZE * 2)  # max fov size x2 (obviously)
FRAME_WIDTH = int(FRAME_SIZE // 2)
FRAME_HEIGHT = int(FRAME_SIZE // 2)

region = (
    int(MONITOR_WIDTH / 2 - FRAME_WIDTH),
    int(MONITOR_HEIGHT / 2 - FRAME_HEIGHT),
    int(MONITOR_WIDTH / 2 - FRAME_WIDTH) + int(FRAME_SIZE),
    int(MONITOR_HEIGHT / 2 - FRAME_HEIGHT) + int(FRAME_SIZE)
)

screenshotcentre = [int((region[2] - region[0]) / 2), int((region[3] - region[1]) / 2)]
camera = bettercam.create()

# Function to check if a key or mouse button is pressed
def is_key_pressed(key_code):
    return ctypes.windll.user32.GetAsyncKeyState(key_code) & 0x8000 != 0

# Softaim Logic
class Softaim():
    @staticmethod
    def mainloop():
        modelpath = 'aa.onnx'  # Path to the model
        model = YOLO(modelpath)
        model.conf = confidence
        model.iou = 1

        prev_time = time.time()
        frame_count = 0
        camera.start(region, target_fps=240)

        while True:
            targetdistance = 100000000
            targets = -1
            frame = camera.get_latest_frame()
            results = model.predict(source=frame, verbose=False)
            boxes = results[0].boxes

            alltargets = []
            closesttarget = []

            def movemouse(x, y):
                ctypes.windll.user32.SendInput(1, ctypes.pointer(Input(type=INPUT_MOUSE, ii=Input_I(mi=MouseInput(dx=int(x), dy=int(y), mouseData=0, dwFlags=MOUSEEVENTF_MOVE, time=0, dwExtraInfo=None)))), ctypes.sizeof(Input))

            for i, box in enumerate(boxes):
                alltargets.append({'bbox': box.xyxy[0].tolist()})
                distance = box.conf[0].item()  # Assuming the model has a .conf field

                if distance < targetdistance:
                    targetdistance = distance
                    targets = i

            if targets != -1:  # if there is a target
                results = boxes[targets].xyxy[0]
                x1, y1, x2, y2 = results[0], results[1], results[2], results[3]
                closesttarget.append({'bbox': [int(x1), int(y1), int(x2), int(y2)]})

                # Adjust aimbone height based on user choice
                if aimbone == "Head":
                    aimbonediv = 2.5
                if aimbone == "Neck":
                    aimbonediv = 3
                if aimbone == "Torso":
                    aimbonediv = 5

                height = y2 - y1
                positionlist = [(x1 + x2) / 2, (y1 + y2) / 2 - height / aimbonediv]

                xdif = (positionlist[0] - screenshotcentre[0])
                ydif = (positionlist[1] - screenshotcentre[1])

                aimbonedistance = math.dist([positionlist[0], positionlist[1]], screenshotcentre)

                if softaim:
                    if aimbonedistance < fovsize:  # if inside the fov circle
                        # Only move the mouse if the right mouse button (button 0x02) is pressed
                        if is_key_pressed(right_mouse_button_code):
                            movemouse(xdif * strength, ydif * strength)

            window.alltargets = alltargets
            window.closesttarget = closesttarget
            window.update()

            # FPS Calculation
            current_time = time.time()
            frame_count += 1
            if current_time - prev_time >= 1.0:
                fps = frame_count / (current_time - prev_time)
                prev_time = current_time
                frame_count = 0
            else:
                fps = frame_count / (current_time - prev_time)

            print(f"FPS: {fps:.2f}", end="\r")

# Detection Window for Visuals
class DetectionWindow(QMainWindow):
    def __init__(self, alltargets, closesttarget):
        super().__init__()
        self.setWindowTitle("Visuals")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint
                            | QtCore.Qt.WindowStaysOnTopHint
                            | QtCore.Qt.WindowDoesNotAcceptFocus
                            | QtCore.Qt.WindowTransparentForInput
                            | QtCore.Qt.Tool
                            )
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setGeometry(0, 0, int(MONITOR_WIDTH), int(MONITOR_HEIGHT))

        self.Xoffsetfix = int((MONITOR_WIDTH / 2) - FRAME_WIDTH)
        self.Yoffsetfix = int((MONITOR_HEIGHT / 2) - FRAME_HEIGHT)

        self.Xcentre = int(MONITOR_WIDTH // 2)
        self.Ycentre = int(MONITOR_HEIGHT // 2)

        self.alltargets = alltargets
        self.closesttarget = closesttarget

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setOpacity(1)

        if fovcircle:
            painter.setPen(QPen(QtCore.Qt.white, 1, QtCore.Qt.SolidLine))
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.drawEllipse(self.Xcentre - fovsize, self.Ycentre - fovsize, fovsize * 2, fovsize * 2)

        for det in self.alltargets:
            x1, y1, x2, y2 = det['bbox']
            is_closest = False
            for close_det in self.closesttarget:
                if det['bbox'] == close_det['bbox']:
                    is_closest = True
                    break
            if not is_closest and boxes:
                painter.setPen(QPen(QtCore.Qt.white, 1, QtCore.Qt.SolidLine))
                painter.setRenderHint(QPainter.Antialiasing, False)
                painter.drawRect(int(x1) + self.Xoffsetfix, int(y1) + self.Yoffsetfix, int(x2) - int(x1), int(y2) - int(y1))

        for det in self.closesttarget:
            x1, y1, x2, y2 = det['bbox']
            if boxes:
                painter.setPen(QPen(QtCore.Qt.white, 1, QtCore.Qt.SolidLine))  # Only use white box for closest target
                painter.setRenderHint(QPainter.Antialiasing, False)
                painter.drawRect(int(x1) + self.Xoffsetfix, int(y1) + self.Yoffsetfix, int(x2) - int(x1), int(y2) - int(y1))

if __name__ == '__main__':
    app = QApplication([])

    # Initialize GUI Window
    window = DetectionWindow([], [])
    window.show()

    # Start Softaim Main Loop in a Thread
    main_thread = threading.Thread(target=Softaim.mainloop)
    main_thread.start()

    # Run Application
    app.exec_()
