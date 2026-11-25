# AZ Email

Web app nội bộ (Python stdlib + PaddleOCR) để soạn email gửi key bản quyền phần mềm cho khách. Đầu vào là chữ hoặc ảnh email của nhà cung cấp. Ứng dụng tách ra nhà cung cấp, sản phẩm và key, rồi sinh email HTML chuẩn.

- Chạy: `cp .env.example .env && docker compose up -d --build` → `127.0.0.1:8889`, cần HTTPS phía trước.
- Code: `app/web.py` (server, phân tích, OCR, auth) · `app/tao_email_key.py` (mẫu email, `SAN_PHAM`, `THUAT_NGU`) · `app/ma_ncc.default.json` (mã nhà cung cấp → sản phẩm).
- Triển khai: là **một tính năng trong CRM https://azcrm.store**, chạy dưới đường dẫn `https://azcrm.store/email` (`BASE_PATH=/email`), mục menu đề xuất *Đơn hàng → Gửi key bản quyền*. Admin lo HTTPS / reverse proxy.
- Cài đặt, cấu hình, tích hợp CRM, kiểm tra, quy tắc: [REQUIREMENTS.md](REQUIREMENTS.md).
