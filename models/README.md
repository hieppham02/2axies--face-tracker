# Face detection model

The application uses `yolov11n-face.pt` from the
[yolo-face project](https://github.com/akanametov/yolo-face), release `1.0.0`.
This is a face detector, not the general COCO person detector and not an
identity recognition model. Tracking follows the center of a face box.

Download the weights from the project root in PowerShell if missing:

```powershell
Invoke-WebRequest -Uri 'https://github.com/akanametov/yolo-face/releases/download/1.0.0/yolov11n-face.pt' -OutFile 'models/yolov11n-face.pt'
```

Run the GUI using the existing virtual environment:

```powershell
.\.venv\Scripts\python.exe .\ui.py
```

The X/Y serial protocol and servo tuning are unchanged. With multiple faces,
tracking starts at the most confident detection and then prefers the nearest
previous face. When no face is detected, no new tracking angles are sent.
