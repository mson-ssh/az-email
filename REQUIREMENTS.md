# REQUIREMENTS – cần cài gì để chạy / phát triển AZ Email

> File dành cho người hoặc AI tiếp nhận dự án. Đọc hết trước khi cài đặt hay sửa code.

## 1. Tóm tắt kỹ thuật

| Thành phần | Công nghệ |
|---|---|
| Web server | Python 3.10+ **thư viện chuẩn** (`http.server`), không framework, không DB |
| OCR server (Linux / Windows) | **PaddleOCR 2.10.0** + **PaddlePaddle 3.0.0** (CPU) hoặc `paddlepaddle-gpu` (GPU NVIDIA) |
| OCR macOS | Apple Vision qua `app/ocr.swift` (cần `swiftc` – Xcode Command Line Tools) |
| OCR dự phòng | Tesseract 5 + gói ngôn ngữ `vie`, `eng` |
| Xử lý ảnh | Pillow 11 |
| Đóng gói | Docker 24+ / Docker Compose v2 |
| HTTPS | Bắt buộc (clipboard API của trình duyệt) – Caddy / Nginx + certbot / Cloudflare Tunnel |

## 2. Cách A – Docker (khuyên dùng cho server)

**Cần có trên máy chủ:**
- Docker Engine 24+ và Docker Compose v2.
- Khoảng **3GB đĩa trống** (image khoảng 2GB) và **2GB RAM** trở lên.
- Internet **khi build** (tải PaddlePaddle và mô hình OCR). Khi chạy thì không cần.
- GPU (tuỳ chọn): driver NVIDIA và **NVIDIA Container Toolkit**, build bằng `Dockerfile.gpu`.

```bash
cp .env.example .env                 # BẮT BUỘC đặt EMAIL_KEY_PASS
docker compose up -d --build
```

## 3. Cách B – chạy trực tiếp (không Docker)

**Linux / Windows:**
```bash
python3 -m pip install paddlepaddle==3.0.0 paddleocr==2.10.0 pillow==11.0.0
# Linux thiếu thư viện hệ thống thì cài thêm: libgl1 libglib2.0-0 libgomp1
cp .env.example .env
python3 app/web.py
```

**macOS:** chỉ cần Python 3.10+ và `xcode-select --install` (để có `swiftc`). Không cần pip.

**Chỉ muốn dùng Tesseract** (nhẹ, kém chính xác hơn):
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-vie tesseract-ocr-eng && pip install pillow
OCR_ENGINE=tesseract python3 app/web.py
```

## 4. HTTPS (bắt buộc khi dùng từ máy khác)

Nút **Paste ở đây!** (`navigator.clipboard.read`) và **Sao chép email** (`navigator.clipboard.write`) **chỉ chạy trên HTTPS hoặc localhost**. Chọn một cách:

- **Caddy:** `key.laptopaz.vn { reverse_proxy 127.0.0.1:8889 }`, tự cấp chứng chỉ.
- **Nginx + certbot:** `proxy_pass http://127.0.0.1:8889;`, đặt `client_max_body_size 20m;` để dán ảnh lớn.
- **Cloudflare Tunnel:** `cloudflared tunnel --url http://127.0.0.1:8889`, không cần mở cổng.

## 5. Biến môi trường (`.env`)

Bắt buộc: `EMAIL_KEY_PASS`. Thiếu biến này thì chương trình dừng.

Tuỳ chọn:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `EMAIL_KEY_USER` | `admin` | Tài khoản đăng nhập |
| `HOST` | `127.0.0.1` | Địa chỉ nghe (Docker: `0.0.0.0`) |
| `PORT` | `8889` | Cổng |
| `DATA_DIR` | `./data` | Thư mục dữ liệu |
| `OCR_ENGINE` | `auto` | `paddle`, `vision` hoặc `tesseract` |
| `OCR_GPU` | `0` | `1` = PaddleOCR dùng GPU |
| `OCR_LANG` | `vie+eng` | Ngôn ngữ cho Tesseract |
| `AUTH_BYPASS_LOCAL` | `0` | `1` = mở từ 127.0.0.1 không hỏi mật khẩu |

`AUTH_BYPASS_LOCAL` chỉ bật trên máy cá nhân, **không bật** sau reverse proxy.

## 6. Kiểm tra sau khi cài

```bash
curl http://127.0.0.1:8889/healthz                         # → ok
curl -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8889/  # → 401 (đúng: cần đăng nhập)
curl -u admin:<mật khẩu> -X POST http://127.0.0.1:8889/phan_tich \
  -H 'Content-Type: application/json' \
  -d '{"text":"Tên hàng hóa: Office Home 2024 (EP2-06796)\nSố lượng: 1\nMã keys:\nBBBBB-CCCCC-DDDDD-FFFFF-GGGGG"}'
# → JSON có "sp": "EP2-06796" và 1 key
```

Log khởi động phải có dòng `OCR: paddle` (server) hoặc `OCR: vision` (macOS).

## 7. Quy tắc khi sửa dự án

- **Không lưu key** ở bất kỳ đâu: không file, không DB, không log. `log_message` của server cố ý để trống.
- **Không commit** `.env` và `data/`. Không đưa key thật vào test hay ảnh mẫu.
- **Thêm sản phẩm:** sửa `SAN_PHAM` trong `app/tao_email_key.py`. "Loại giấy phép" ghi đúng thành phần trong tên của nhà phân phối. Thuật ngữ mới thì thêm vào `THUAT_NGU`.
- **Mã nhà cung cấp:** sửa `app/ma_ncc.default.json` (mẫu ban đầu). Khi chạy, chương trình dùng `data/ma_ncc.json`.
- **Mẫu email** chỉ dùng bảng và style nội tuyến, không JS, không `<style>` cho bố cục. Gmail bỏ những phần này khi dán.
- Không kiểm tra "bộ ký tự hợp lệ" của key Microsoft. Key thật có cả N và Z, từng gây báo nhầm.
- Key **không được ghép qua xuống dòng** (regex dùng `[ \t]`, không dùng `\s`). Nếu không, key bị che sẽ thành key giả.
- Trả lời người dùng và viết chú thích bằng **tiếng Việt**.
