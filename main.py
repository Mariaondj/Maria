import dearpygui.dearpygui as dpg
import torch
from ultralytics import YOLO
import time
import bettercam
import ctypes
import PyQt5
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtGui import QPainter, QPen
import threading
import ctypes
import os
import json
import signal
import math
import glob

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
keycode = 0x02  # Virtual key code for CTRL (used for key hold)
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

x, y, width, height = region
screenshotcentre = [int((width - x) / 2), int((height - y) / 2)]
camera = bettercam.create()

# GUI Class
class Gui():
    def __init__(self):
        super().__init__()

    # GUI Initialization
    def initwindow(self):
        dpg.create_context()
        dpg.create_viewport(title="Astro AI | Version 1.0", width=500, height=300)
        dpg.setup_dearpygui()
        with dpg.window(label="Astro", width=800, height=600, tag="MainWindow"):
            with dpg.tab_bar():
                with dpg.tab(label="Softaim"):
                    self.softaim_checkbox = dpg.add_checkbox(label="Toggle Softaim", callback=self.togglesoftaim, default_value=softaim)
                    self.strength_slider = dpg.add_slider_float(label="Strength", default_value=strength, min_value=0.01, max_value=5, callback=self.changestrength)
                    self.fovsize_slider = dpg.add_slider_int(label="FOV Size", default_value=fovsize, min_value=10, max_value=MAX_FOV_SIZE, callback=self.changefovsize)
                    self.aimbone_radiobutton = dpg.add_radio_button(label="Aim Bone", items=["Head", "Neck", "Torso"], default_value="Head", horizontal=True, callback=self.changeaimbone)
                    
                with dpg.tab(label="Visuals"):
                    self.fovcircle_checkbox = dpg.add_checkbox(label="Draw FOV Circle", callback=self.togglefovcircle, default_value=fovcircle)
                    self.boxes_checkbox = dpg.add_checkbox(label="Draw Boxes", callback=self.toggleboxes, default_value=boxes)
                                  
                with dpg.tab(label="Misc"):
                    self.confidence_slider = dpg.add_slider_float(label="AI Confidence", default_value=confidence, min_value=0.1, max_value=1, callback=self.changeconfidence)
                    dpg.add_button(label="Save Config", callback=self.save_config)
                    
                    # ComboBox to select configuration file
                    self.config_files = self.get_config_files()  # Get available configuration files
                    self.config_dropdown = dpg.add_combo(label="Select Config", items=self.config_files, callback=self.load_config_from_dropdown)

        dpg.set_primary_window("MainWindow", True)
        dpg.show_viewport()

    # GUI Loop
    def rungui(self):
        self.initwindow()
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
        os.kill(os.getpid(), signal.SIGILL)

    # GUI Callbacks
    def togglesoftaim(self, sender, data: bool) -> bool:
        global softaim
        softaim = data

    def changestrength(self, sender, data: float) -> float:
        global strength
        strength = data

    def changefovsize(self, sender, data: float) -> float:
        global fovsize
        fovsize = data

    def changeconfidence(self, sender, data: float) -> float:
        global confidence
        confidence = data

    def changeaimbone(self, sender, data: str) -> str:
        global aimbone
        aimbone = data

    def togglefovcircle(self, sender, data: bool) -> bool:
        global fovcircle
        fovcircle = data
    
    def toggleboxes(self, sender, data: bool) -> bool:
        global boxes
        boxes = data

    # Save Configuration
    def save_config(self, sender, app_data):
        config = {
            "softaim": softaim,
            "strength": strength,
            "fovsize": fovsize,
            "confidence": confidence,
            "aimbone": aimbone,
            "fovcircle": fovcircle,
            "boxes": boxes
        }
        config_file = "config_{}.txt".format(int(time.time()))  # Save with a unique name based on timestamp
        with open(config_file, "w") as f:
            json.dump(config, f)
        print(f"Config saved as {config_file}!")

    # Load Configuration from File
    def load_config(self, sender, app_data):
        file_name = app_data  # Get the file name from combo box selection
        try:
            with open(file_name, "r") as f:
                config = json.load(f)
                global softaim, strength, fovsize, confidence, aimbone, fovcircle, boxes
                softaim = config["softaim"]
                strength = config["strength"]
                fovsize = config["fovsize"]
                confidence = config["confidence"]
                aimbone = config["aimbone"]
                fovcircle = config["fovcircle"]
                boxes = config["boxes"]

                # Update the GUI elements by referencing their tags
                dpg.set_value(self.softaim_checkbox, softaim)
                dpg.set_value(self.strength_slider, strength)
                dpg.set_value(self.fovsize_slider, fovsize)
                dpg.set_value(self.confidence_slider, confidence)
                dpg.set_value(self.aimbone_radiobutton, aimbone)
                dpg.set_value(self.fovcircle_checkbox, fovcircle)
                dpg.set_value(self.boxes_checkbox, boxes)
            print(f"Config loaded from {file_name}!")
        except Exception as e:
            print(f"Error loading config from {file_name}: {e}")

    # Load Configuration from ComboBox selection
    def load_config_from_dropdown(self, sender, app_data):
        self.load_config(sender, app_data)

    # Get Available Configuration Files
    def get_config_files(self):
        # Get all *.txt files from the current directory or a specific path
        config_files = glob.glob("*.txt")
        return config_files

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
                        movemouse(xdif * strength, ydif * strength)

            window.alltargets = alltargets
            window.closesttarget = closesttarget
            window.update()
            QApplication.processEvents()

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

    # Start GUI in Main Thread
    gui = Gui()
    gui.rungui()

    # Run Application
    app.exec_()
