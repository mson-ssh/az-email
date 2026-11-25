# AZ Email

Trang nội bộ LaptopAZ để soạn **email gửi key bản quyền phần mềm** (Office, Microsoft 365, Windows, Kaspersky) cho khách.

Nhân viên bấm **Paste ở đây!**, dán email hoặc ảnh của nhà cung cấp. Trang tự nhận sản phẩm và key, nhân viên xem trước, bấm **Sao chép email** rồi dán vào Gmail.

## Chạy nhanh

```bash
cp .env.example .env          # đặt EMAIL_KEY_USER / EMAIL_KEY_PASS
docker compose up -d --build  # → http://127.0.0.1:8889
```

Cần **HTTPS** (reverse proxy hoặc Cloudflare Tunnel) để dùng nút Paste và Sao chép email.

Cài đặt chi tiết, phần mềm cần có và cách kiểm tra: xem [REQUIREMENTS.md](REQUIREMENTS.md).

## Thư mục

- `app/web.py`: trang web, phân tích chữ / ảnh, OCR, đăng nhập
- `app/tao_email_key.py`: mẫu email, danh mục sản phẩm
- `app/ma_ncc.default.json`: mã hàng nhà cung cấp → sản phẩm
- `data/`: dữ liệu khi chạy (không đưa lên git)

## Nguyên tắc

- Không lưu key.
- Không commit `.env`.
- OCR chạy ngay trên máy chủ, ảnh không gửi ra ngoài.
