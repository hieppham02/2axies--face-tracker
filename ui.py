import tkinter as tk
import customtkinter as ctk

import cv2
from PIL import Image
from serial.tools import list_ports

from human_detection import FaceDetector, SERIAL_PORT


CAMERA_INDEX = 0
SECONDARY_CAMERA_INDEX = 2
FRAME_DELAY_MS = 15
VIDEO_WIDTH = 800
VIDEO_HEIGHT = 600
DEFAULT_PROPORTIONAL_GAIN = 0.02
DEFAULT_DEAD_ZONE = 30
DEFAULT_ERROR_ALPHA = 0.2
DEFAULT_MAX_STEP = 3
DEFAULT_CONTROL_INTERVAL = 0.1
NO_SERIAL_PORT = "Không tìm thấy cổng COM"


class TrackingApp:

    def __init__(self, window: ctk.CTk) -> None:
        self.window = window
        self.camera = None
        self.detector = None
        self.is_running = False
        self.camera_index = CAMERA_INDEX
        self.serial_ports = sorted(port.device for port in list_ports.comports())

        self.window.title("Face Tracking")
        self.window.configure(fg_color="#F1F5F9")
        self.font = ctk.CTkFont(family="Segoe UI", size=13)
        self.button_font = ctk.CTkFont(family="Segoe UI", size=14, weight="bold")
        self.window.protocol("WM_DELETE_WINDOW", self.close)

        self.video_container = ctk.CTkFrame(
            self.window,
            width=VIDEO_WIDTH,
            height=VIDEO_HEIGHT,
            fg_color="#0F172A",
            corner_radius=0,
        )
        self.video_container.pack(padx=16, pady=(16, 10))
        self.video_container.pack_propagate(False)

        self.video_panel = ctk.CTkLabel(
            self.video_container,
            text="Nhấn nút để bật camera",
            fg_color="#0F172A",
            text_color="#94A3B8",
            font=self.font,
        )
        self.video_panel.pack(fill="both", expand=True)

        self.button_panel = ctk.CTkFrame(self.window, fg_color="transparent")
        self.button_panel.pack(pady=(0, 8))

        self.start_button = ctk.CTkButton(
            self.button_panel,
            text="Tracking",
            font=self.button_font,
            width=190,
            height=36,
            corner_radius=8,
            fg_color="#2563EB",
            hover_color="#1D4ED8",
            command=self.start_tracking,
        )
        self.start_button.pack(side="left", padx=(0, 8))

        self.change_camera_button = ctk.CTkButton(
            self.button_panel,
            text=f"Camera {self.camera_index}",
            font=self.button_font,
            width=190,
            height=36,
            corner_radius=8,
            fg_color="#E2E8F0",
            hover_color="#CBD5E1",
            text_color="#0F172A",
            command=self.change_camera,
        )
        self.change_camera_button.pack(side="left")

        self.serial_panel = ctk.CTkFrame(self.window, fg_color="transparent")
        self.serial_panel.pack(pady=(0, 8))
        ctk.CTkLabel(
            self.serial_panel,
            text="Cổng serial",
            font=self.font,
            text_color="#475569",
        ).pack(side="left", padx=(0, 8))

        selected_port = (
            SERIAL_PORT
            if SERIAL_PORT in self.serial_ports
            else self.serial_ports[0] if self.serial_ports else NO_SERIAL_PORT
        )
        self.serial_port = tk.StringVar(value=selected_port)
        self.serial_combobox = ctk.CTkComboBox(
            self.serial_panel,
            values=self.serial_ports or [NO_SERIAL_PORT],
            variable=self.serial_port,
            width=180,
            height=32,
            font=self.font,
            dropdown_font=self.font,
            state="readonly" if self.serial_ports else "disabled",
            command=self.change_serial_port,
        )
        self.serial_combobox.pack(side="left")

        self.control_panel = ctk.CTkFrame(
            self.window,
            fg_color="white",
            corner_radius=10,
            border_width=1,
            border_color="#E2E8F0",
        )
        self.control_panel.pack(fill="x", padx=16, pady=(0, 12))
        ctk.CTkLabel(
            self.control_panel, text="Điều chỉnh tracking", anchor="w",
            font=self.button_font, text_color="#0F172A", height=24,
        ).pack(fill="x", padx=14, pady=(8, 2))

        self.proportional_gain = tk.DoubleVar(value=DEFAULT_PROPORTIONAL_GAIN)
        self.dead_zone = tk.IntVar(value=DEFAULT_DEAD_ZONE)
        self.error_alpha = tk.DoubleVar(value=DEFAULT_ERROR_ALPHA)
        self.max_step = tk.IntVar(value=DEFAULT_MAX_STEP)
        self.control_interval = tk.DoubleVar(value=DEFAULT_CONTROL_INTERVAL)

        self._create_slider("PROPORTIONAL_GAIN", self.proportional_gain, 0.0, 0.1, 0.005)
        self._create_slider("DEAD_ZONE_PIXELS", self.dead_zone, 0, 100, 1)
        self._create_slider("ERROR_ALPHA", self.error_alpha, 0.05, 1.0, 0.05)
        self._create_slider("MAX_STEP", self.max_step, 1, 10, 1)
        self._create_slider("DEFAULT_CONTROL_INTERVAL", self.control_interval, 0.0, 1, 0.1)

        self.window.update_idletasks()
        self.window.tk.call("wm", "geometry", self.window._w, "")
        self.window.resizable(False, False)
        self._center_window()

    def _center_window(self) -> None:
        window_width = self.window.winfo_reqwidth()
        window_height = self.window.winfo_reqheight()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        position_x = max(0, (screen_width - window_width) // 2)
        position_y = max(0, (screen_height - window_height) // 2)
        self.window.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

    def _selected_serial_port(self) -> str | None:
        selected_port = self.serial_port.get()
        return selected_port if selected_port in self.serial_ports else None

    def change_serial_port(self, selected_port: str) -> None:
        if self.detector is not None:
            self.detector.set_serial_port(selected_port)

    def _create_slider(self, label, variable, minimum, maximum, resolution) -> None:
        row = ctk.CTkFrame(self.control_panel, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(row, text=label.replace("DEFAULT_", ""), width=200,
                     anchor="w", height=22, font=self.font,
                     text_color="#475569").pack(side="left")
        value_text = tk.StringVar(value=f"{variable.get():g}")
        ctk.CTkLabel(row, textvariable=value_text, width=48, height=22,
                     anchor="e", font=self.font, text_color="#2563EB").pack(side="right")

        def on_change(value):
            value_text.set(f"{variable.get():g}")
            self._update_control_parameters()

        ctk.CTkSlider(
            row,
            variable=variable,
            from_=minimum,
            to=maximum,
            number_of_steps=round((maximum - minimum) / resolution),
            orientation="horizontal",
            height=16,
            width=480,
            progress_color="#2563EB",
            button_color="#2563EB",
            button_hover_color="#1D4ED8",
            fg_color="#E2E8F0",
            command=on_change,
        ).pack(side="left", fill="x", expand=True, padx=8)

    def _update_control_parameters(self, _value=None) -> None:
        if self.detector is not None:
            self.detector.update_control_parameters(
                proportional_gain=self.proportional_gain.get(),
                dead_zone_pixels=self.dead_zone.get(),
                error_alpha=self.error_alpha.get(),
                max_step=self.max_step.get(),
            )

    def start_tracking(self) -> None:
        if self.is_running:
            return

        self.video_panel.configure(text="Đang tải mô hình...", image=None)
        self.window.update_idletasks()
        if self.detector is None:
            self.detector = FaceDetector(self._selected_serial_port())
        self._update_control_parameters()
        self.camera = cv2.VideoCapture(self.camera_index)

        if not self.camera.isOpened():
            self.video_panel.configure(text="Không thể mở camera")
            self.camera.release()
            self.camera = None
            return

        self.is_running = True
        self.start_button.configure(state="disabled", text="Đang nhận diện")
        self.update_video()

    def change_camera(self) -> None:
        if not self.is_running:
            return

        next_index = (
            SECONDARY_CAMERA_INDEX
            if self.camera_index == CAMERA_INDEX
            else CAMERA_INDEX
        )
        new_camera = cv2.VideoCapture(next_index)
        if not new_camera.isOpened():
            new_camera.release()
            self.video_panel.configure(text=f"Không thể mở camera {next_index}")
            return

        previous_camera = self.camera
        self.camera = new_camera
        self.camera_index = next_index
        previous_camera.release()
        self.change_camera_button.configure(text=f"Camera {next_index}")

    def update_video(self) -> None:
        if not self.is_running or self.camera is None:
            return

        frame_read, frame = self.camera.read()
        if not frame_read:
            self.video_panel.configure(text="Không đọc được khung hình", image=None)
            self.stop_tracking()
            return

        frame = cv2.flip(frame, 1)
        processed_frame = self.detector.process_frame(frame)
        display_frame = cv2.resize(
            processed_frame,
            (VIDEO_WIDTH, VIDEO_HEIGHT),
            interpolation=cv2.INTER_AREA,
        )
        rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        photo = ctk.CTkImage(light_image=Image.fromarray(rgb_frame),
                             size=(VIDEO_WIDTH, VIDEO_HEIGHT))

        self.video_panel.configure(image=photo, text="")
        self.video_panel.image = photo
        self.window.after(FRAME_DELAY_MS, self.update_video)

    def stop_tracking(self) -> None:
        self.is_running = False
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.start_button.configure(state="normal", text="Tracking")

    def close(self) -> None:
        self.stop_tracking()
        if self.detector is not None:
            self.detector.close()
        self.window.destroy()


def main() -> None:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    window = ctk.CTk()
    TrackingApp(window)
    window.mainloop()


if __name__ == "__main__":
    main()
