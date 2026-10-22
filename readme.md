# Hệ thống camera bám theo khuôn mặt

## Mô tả ngắn gọn project

Ứng dụng Python nhận diện khuôn mặt từ camera bằng YOLO, tính góc điều khiển và gửi đến STM32 qua serial. Hai servo xoay camera theo trục ngang (X) và dọc (Y), đưa khuôn mặt về giữa khung hình.

## Mô tả phần cứng, GPIO

- **STM32F103C8T6 Blue Pill:** nhận lệnh điều khiển, đọc joystick và tạo PWM cho servo.
- **2 servo MG99R:** điều khiển góc quay ngang và dọc của camera.
- **Joystick 2 trục:** điều khiển camera thủ công qua hai tín hiệu analog VRx, VRy.
- **Camera:** Webcam bình thường mua trên shopee
- **PC:** (Ưu tiên PC có GPU NVIDIA) thu hình, chạy mô hình YOLO; kết nối STM32 qua bộ chuyển USB–UART.
- **Khung in 3D:** [File STL](https://makerworld.com/en/models/973248-pan-tilt-servo-antenna-tracker-mg996r#profileId-945437)

| Kết nối | GPIO |
| --- | --- |
| Tín hiệu servo X, Y | PA7, PB1 |
| Joystick VRx, VRy | PA4, PA5 |
| USB–UART TX → STM32 RX | PA9 TX, PA10 RX |
| GND các thiết bị | Chung GND |

Servo sử dụng nguồn ngoài phù hợp (5V ~ 9V, > 1A), nối chung GND với STM32; joystick cấp 3,3 V để tín hiệu analog phù hợp với ADC. **Chưa có firmware STM32 trong thư mục này nên chưa xác định số chân GPIO cụ thể.**

## Mô tả các chức năng

- Hiển thị camera, khung khuôn mặt, độ tin cậy, sai lệch tâm và góc hai servo.
- Tự động bám theo một khuôn mặt qua hai trục X/Y.
- Chọn cổng COM, chuyển camera giữa chỉ số 0 và 2.
- Điều chỉnh hệ số điều khiển, vùng chết, hệ số lọc và bước góc tối đa trên giao diện.
- Khi mất khuôn mặt, dừng gửi góc bám mới.

## Mô tả thuật toán, ứng dụng mô hình YOLO

1. Đọc và lật ngang khung hình bằng OpenCV.
2. Chạy mô hình `models/yolov11n-face.pt` với kích thước suy luận 416, ngưỡng tin cậy 0,5; dùng GPU CUDA nếu có, nếu không dùng CPU.
3. Ban đầu chọn khuôn mặt có độ tin cậy cao nhất; các khung hình tiếp theo ưu tiên khuôn mặt gần vị trí trước đó. Sau 5 khung hình mất mục tiêu, cho phép chọn lại.
4. Tính sai lệch giữa tâm khuôn mặt và tâm ảnh cho từng trục. Lọc sai lệch bằng trung bình mũ, áp dụng điều khiển tỉ lệ để tăng/giảm góc servo.
5. Dùng vùng chết để giảm rung, giới hạn bước góc và góc trong khoảng 0–180°. Chu kỳ cập nhật điều khiển là 0,1 giây; chỉ gửi khi góc thay đổi ít nhất 1°.

Mô hình phát hiện vị trí khuôn mặt, không nhận dạng danh tính.

## Mô tả thuật toán, logic phía STM32

Phần dưới mô tả logic cần triển khai; chưa được xác minh bằng firmware trong thư mục này:

- **Tự động:** nhận từng dòng UART ở 115200 baud. Lệnh `90\n` đặt góc trục X là 90°; `Y:90\n` đặt góc trục Y là 90°. Phân tích lệnh, kiểm tra góc hợp lệ rồi cập nhật độ rộng xung PWM cho servo tương ứng.
- **Thủ công:** đọc ADC của hai trục joystick, đặt vùng chết quanh vị trí giữa và chuyển độ lệch thành điều chỉnh góc servo.
- Cần quy định cách chọn chế độ và ưu tiên giữa joystick với lệnh UART trong firmware.

## Ảnh, video demo

![Demo](images/demo.gif)
![Board and Frame](images/img.jpg)