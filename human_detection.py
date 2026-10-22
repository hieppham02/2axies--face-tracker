from pathlib import Path
from time import monotonic

import cv2
import numpy as np
import serial
import torch
from ultralytics import YOLO


MODEL_PATH = Path(__file__).resolve().parent / "models" / "yolov11n-face.pt"
SERIAL_PORT = "COM8"
SERIAL_BAUD_RATE = 115200
FACE_CLASS_ID = 0
CONFIDENCE_THRESHOLD = 0.5
IMAGE_SIZE = 416
CENTER_ANGLE = 90

PROPORTIONAL_GAIN = 0.025
DEAD_ZONE_PIXELS = 30
ERROR_ALPHA = 0.75
MAX_STEP = 4
CONTROL_INTERVAL = 0.1

SERVO_DIRECTION = 1
SERVO_Y_DIRECTION = 1
MIN_ANGLE = 0
MAX_ANGLE = 180
MIN_SEND_CHANGE = 1
TARGET_MISSING_FRAMES = 5
SEARCH_ANGLES = (0, 90, 180)
SEARCH_INTERVAL = 1.0


class FaceDetector:

    def __init__(self, serial_port: str | None = SERIAL_PORT) -> None:
        self.device = 0 if torch.cuda.is_available() else "cpu"
        if not MODEL_PATH.is_file():
            raise FileNotFoundError(
                f"Face model not found: {MODEL_PATH}. See models/README.md for download instructions."
            )
        self.model = YOLO(MODEL_PATH)
        self.serial_port = serial_port
        self.serial_connection = self._open_serial_connection(serial_port)
        self.last_sent_angle = None
        self.last_sent_angle_y = None
        self.servo_angle = float(CENTER_ANGLE)
        self.servo_angle_y = float(CENTER_ANGLE)
        self.filtered_error = 0.0
        self.filtered_error_y = 0.0
        self.last_control_time = None
        self.last_control_time_y = None
        self.target_center = None
        self.missing_frames = 0
        self.proportional_gain = PROPORTIONAL_GAIN
        self.dead_zone_pixels = DEAD_ZONE_PIXELS
        self.error_alpha = ERROR_ALPHA
        self.max_step = MAX_STEP
        self.search_index = 0
        self.next_search_time = None
        self._warm_up()

    def update_control_parameters(
        self,
        proportional_gain: float,
        dead_zone_pixels: int,
        error_alpha: float,
        max_step: int,
    ) -> None:
        self.proportional_gain = proportional_gain
        self.dead_zone_pixels = dead_zone_pixels
        self.error_alpha = error_alpha
        self.max_step = max_step

    @staticmethod
    def _open_serial_connection(serial_port: str | None):
        if not serial_port:
            return None
        try:
            connection = serial.Serial(
                serial_port, SERIAL_BAUD_RATE, timeout=1)
            print(f"Serial connected: {serial_port} ({SERIAL_BAUD_RATE} baud)")
            return connection
        except serial.SerialException as error:
            print(f"Cannot open {serial_port}: {error}")
            return None

    def set_serial_port(self, serial_port: str | None) -> bool:
        if self.serial_connection is not None and self.serial_connection.is_open:
            self.serial_connection.close()

        self.serial_port = serial_port
        self.serial_connection = self._open_serial_connection(serial_port)
        self.last_sent_angle = None
        self.last_sent_angle_y = None
        return self.serial_connection is not None

    def _warm_up(self) -> None:
        sample_frame = np.zeros(
            (IMAGE_SIZE, IMAGE_SIZE, 3),
            dtype=np.uint8,
        )
        self.model(
            sample_frame,
            classes=[FACE_CLASS_ID],
            imgsz=IMAGE_SIZE,
            device=self.device,
            verbose=False,
        )

    def process_frame(self, frame):
        frame_height, frame_width = frame.shape[:2]
        screen_center = (frame_width // 2, frame_height // 2)
        cv2.circle(frame, screen_center, 6, (255, 0, 0), -1)

        results = self.model(
            frame,
            classes=[FACE_CLASS_ID],
            conf=CONFIDENCE_THRESHOLD,
            imgsz=IMAGE_SIZE,
            device=self.device,
            verbose=False,
        )

        targets = []
        for result in results:
            for box in result.boxes:
                target = self._read_target(box, screen_center)
                self._draw_target(frame, target, screen_center)

                targets.append(target)

        best_target = self._select_target(targets, frame_width)
        if best_target is not None:
            servo_angle = self._calculate_servo_angle(best_target["error_x"])
            servo_angle_y = self._calculate_servo_angle(
                best_target["error_y"], axis="Y")
            self._send_angle(servo_angle)
            self._send_angle(servo_angle_y, axis="Y")
            self._draw_tracking_text(
                frame, best_target, servo_angle, servo_angle_y)
        else:
            self.filtered_error = 0.0
            self.filtered_error_y = 0.0
            self.last_control_time = None
            self.last_control_time_y = None

        return frame

    def _select_target(self, targets: list, frame_width: int):
        if self.target_center is None:
            selected = max(
                targets, key=lambda target: target["confidence"], default=None)
        else:
            def distance(target):
                return sum((a - b) ** 2 for a, b in zip(target["center"], self.target_center))

            selected = min(targets, key=distance, default=None)
            if selected is not None and distance(selected) > (frame_width * 0.25) ** 2:
                selected = None

        if selected is None:
            self.missing_frames += 1
            if self.missing_frames >= TARGET_MISSING_FRAMES:
                self.target_center = None
            return None

        self.target_center = selected["center"]
        self.missing_frames = 0
        self.search_index = 0
        self.next_search_time = None
        return selected

    def _update_search_pattern(self) -> None:
        now = monotonic()
        if self.next_search_time is not None and now < self.next_search_time:
            return

        angle = SEARCH_ANGLES[self.search_index]
        self.servo_angle = float(angle)
        self._send_angle(angle)
        self.search_index = (self.search_index + 1) % len(SEARCH_ANGLES)
        self.next_search_time = now + SEARCH_INTERVAL

    def _send_angle(self, angle: int, axis: str = "X") -> None:
        if axis not in ("X", "Y"):
            raise ValueError("Unknown servo axis")
        last_sent_attribute = "last_sent_angle_y" if axis == "Y" else "last_sent_angle"
        last_sent = getattr(self, last_sent_attribute)
        rounded_angle = int(round(angle))
        if self.serial_connection is None:
            return
        if last_sent is not None and abs(rounded_angle - last_sent) < MIN_SEND_CHANGE:
            return

        try:
            prefix = "Y:" if axis == "Y" else ""
            self.serial_connection.write(
                f"{prefix}{rounded_angle}\n".encode("ascii"))
            print(f"Angle {axis}: {rounded_angle}")
            setattr(self, last_sent_attribute, rounded_angle)
        except serial.SerialException as error:
            print(f"Serial send failed: {error}")
            self.serial_connection = None

    def close(self) -> None:
        if self.serial_connection is not None and self.serial_connection.is_open:
            self.serial_connection.close()
        self.serial_connection = None

    @staticmethod
    def _read_target(box, screen_center: tuple[int, int]) -> dict:
        x1, y1, x2, y2 = map(int, box.xyxy[0])
        face_center = ((x1 + x2) // 2, (y1 + y2) // 2)

        return {
            "box": (x1, y1, x2, y2),
            "confidence": float(box.conf[0]),
            "center": face_center,
            "error_x": face_center[0] - screen_center[0],
            "error_y": face_center[1] - screen_center[1],
        }

    @staticmethod
    def _draw_target(frame, target: dict, screen_center: tuple[int, int]) -> None:
        x1, y1, x2, y2 = target["box"]
        face_center = target["center"]

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame, face_center, 6, (0, 0, 255), -1)
        cv2.line(frame, screen_center, face_center, (0, 255, 255), 2)

    def _calculate_servo_angle(self, error_x: int, axis: str = "X") -> int:
        if axis not in ("X", "Y"):
            raise ValueError("Unknown servo axis")
        suffix = "_y" if axis == "Y" else ""
        angle_attribute = "servo_angle" + suffix
        error_attribute = "filtered_error" + suffix
        time_attribute = "last_control_time" + suffix
        angle = getattr(self, angle_attribute)
        filtered_error = getattr(self, error_attribute)
        last_control_time = getattr(self, time_attribute)
        direction = SERVO_Y_DIRECTION if axis == "Y" else SERVO_DIRECTION
        now = monotonic()
        if abs(error_x) <= self.dead_zone_pixels:
            setattr(self, error_attribute, 0.0)
            setattr(self, time_attribute, now)
            return int(round(angle))

        if last_control_time is not None and now - last_control_time < CONTROL_INTERVAL:
            return int(round(angle))
        setattr(self, time_attribute, now)
        filtered_error = self.error_alpha * error_x + \
            (1 - self.error_alpha) * filtered_error
        setattr(self, error_attribute, filtered_error)
        if abs(filtered_error) > self.dead_zone_pixels:
            step = direction * self.proportional_gain * filtered_error
            step = max(-self.max_step, min(self.max_step, step))
            angle = max(MIN_ANGLE, min(MAX_ANGLE, angle + step))
            setattr(self, angle_attribute, angle)
        return int(round(angle))

    @staticmethod
    def _draw_tracking_text(frame, target: dict, servo_angle: int, servo_angle_y: int) -> None:
        text = (
            f"Face {target['confidence']:.2f} | "
            f"errorX={target['error_x']} errorY={target['error_y']} | "
            f"X={servo_angle} Y={servo_angle_y}"
        )
        cv2.putText(
            frame,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
