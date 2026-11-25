"""Tạo email gửi KEY bản quyền (Office / Windows) cho khách – chuẩn HTML email doanh nghiệp (25/11/2026).

    python3 app/tao_email_key.py --ds                                   # danh sách sản phẩm có sẵn
    python3 app/tao_email_key.py --sp EP2-36890 --key "<key>" --mo   # dùng mã sản phẩm có sẵn
    Loại: office (Office 2024) · m365 (Microsoft 365) · windows (Windows 11) · kaspersky. Sản phẩm mới chưa có trong SAN_PHAM:
    python3 app/tao_email_key.py --loai office [--khach "Anh/Chị Nguyễn Văn A"] \
        --ten "Office Home & Business 2024" --ma "EP2-06604" --key "XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" \
        [--ngay 28/09/2026] [--key KEY2 …] [--mo]

Sinh ra trong data/email_out/ (KHÔNG đưa lên git vì chứa key):
  <mã SP>-<giờ>.html  – nội dung email. Mở trong Chrome → Cmd+A, Cmd+C → dán vào khung soạn Gmail.
  <mã SP>-<giờ>.txt   – Tiêu đề (Subject) + bản chữ thuần (dán khi khách dùng ứng dụng không hiện HTML / gửi Zalo).

Trình bày theo phong cách email giao dịch của các hãng lớn (Apple, Microsoft, Stripe, Adobe):
  logo căn giữa · tiêu đề lớn căn giữa · MỘT điểm nhấn chính (key) + MỘT nút chính · nhiều khoảng trắng ·
  nhãn xám / giá trị đậm, đường kẻ mảnh · màu thương hiệu chỉ dùng cho nút và biểu tượng · khối "Cần hỗ trợ?" ·
  chân thư chữ nhỏ xám nằm ngoài thẻ.
Chuẩn email: bảng lồng, style nội tuyến (giữ nguyên khi dán vào Gmail), co giãn PC / điện thoại không cần CSS riêng,
font hệ thống, không JS; có preheader, khối điều kiện cho Outlook (MSO), thuộc tính bgcolor dự phòng.
"""
import argparse, html, re, subprocess
from datetime import date
from pathlib import Path

import os
OUT = Path(os.environ.get('DATA_DIR', Path(__file__).resolve().parents[1] / 'data')) / 'email_out'   # file email tạo bằng dòng lệnh (chứa key – không đưa lên git)
LOGO = 'https://laptopaz.vn/media/lib/05-11-2026/laptopaz-logo-pc86-1x.png'

# Màu: chữ đen–xám trung tính, xanh thương hiệu (laptopaz.vn) chỉ cho nút / biểu tượng / liên kết
XANH = '#1f6fc4'        # thương hiệu
XANH_NHAT = '#eaf2fc'   # nền biểu tượng
CHU = '#1d1d1f'         # chữ chính
PHU = '#6e6e73'         # chữ phụ
MO = '#86868b'          # chữ rất phụ (chân thư)
KE = '#e5e5ea'          # đường kẻ
NEN = '#f5f5f7'         # nền ngoài thẻ / khối key
# Font: Segoe UI (anh chốt 25/11/2026 – font hệ thống, không tải webfont). Máy không có Segoe UI (Mac / iPhone / Android)
# tự dùng font hệ thống tương đương: -apple-system (SF Pro), Roboto, Helvetica Neue, Arial. Key: SF Mono → Consolas → Roboto Mono.
FONT = "font-family:'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,'Helvetica Neue',Arial,sans-serif;"
MONO = "font-family:'SF Mono',ui-monospace,Consolas,'Roboto Mono',Menlo,'Liberation Mono',monospace;"

CONG_TY = 'CÔNG TY TNHH LAPTOPAZ VIỆT NAM'
HOTLINE, HOTLINE_TEL = '0825.233.233', '0825233233'
EMAIL = 'laptopaz2025@gmail.com'
WEB = 'laptopaz.vn'
NGUOI_GUI = 'Bộ phận Chăm sóc khách hàng'  # người gửi cố định (anh chốt 25/11/2026)

LOAI = {
    'office': dict(
        nhom='Microsoft Office', giay_phep='Vĩnh viễn – Retail Online (ESD)',
        link='https://setup.office.com/', nut='Kích hoạt tại setup.office.com',
        buoc=[('Truy cập trang kích hoạt', 'Mở <a href="https://setup.office.com/" style="color:%s;text-decoration:none">setup.office.com</a> trên trình duyệt.' % XANH),
              ('Đăng nhập tài khoản Microsoft', 'Đăng nhập hoặc tạo mới tài khoản Microsoft. Bản quyền sẽ được gắn vĩnh viễn vào tài khoản này.'),
              ('Nhập mã key', 'Nhập mã key ở trên, chọn quốc gia / ngôn ngữ và bấm <b>Tiếp theo</b>.'),
              ('Tải và cài đặt', 'Vào <a href="https://account.microsoft.com/services" style="color:%s;text-decoration:none">account.microsoft.com/services</a>, chọn <b>Cài đặt</b> để tải bộ cài Office.' % XANH),
              ('Hoàn tất', 'Mở Word hoặc Excel, đăng nhập đúng tài khoản Microsoft ở bước 2; Office sẽ tự động kích hoạt.')],
        kiem=[('Gỡ bản Office dùng thử', 'Gỡ các bản Office / Microsoft 365 dùng thử đang có trên máy (Cài đặt → Ứng dụng) trước khi cài, tránh xung đột bản quyền.'),
              ('Dùng tài khoản Microsoft cá nhân', 'Outlook, Hotmail hoặc email đã đăng ký Microsoft. Không dùng tài khoản công ty / trường học.'),
              ('Chỉ nhập key tại setup.office.com', 'Không nhập key trong Word / Excel.'),
              ('Mỗi key chỉ nhập một lần', 'Sau khi key đã gắn vào tài khoản, khi cài lại máy Quý khách chỉ cần đăng nhập tài khoản đó, không nhập lại key.'),
              ('Sao chép và dán key', 'Dùng Ctrl+C, Ctrl+V thay vì gõ tay để tránh nhầm ký tự.')]),
    'windows': dict(
        nhom='Microsoft Windows', giay_phep='Vĩnh viễn – Retail (ESD)',
        link='https://support.microsoft.com/vi-vn/windows/activation/activate-windows', nut='Xem hướng dẫn của Microsoft',
        buoc=[('Mở mục Kích hoạt', 'Vào <b>Cài đặt (Settings)</b> → <b>Hệ thống (System)</b> → <b>Kích hoạt (Activation)</b>.'),
              ('Đổi khóa sản phẩm', 'Bấm <b>Thay đổi khóa sản phẩm (Change product key)</b>.'),
              ('Nhập mã key', 'Nhập mã key ở trên, bấm <b>Tiếp theo</b> rồi <b>Kích hoạt</b>.'),
              ('Hoàn tất', 'Máy cần kết nối Internet. Trạng thái hiển thị <b>“Windows is activated”</b> là đã kích hoạt thành công.')],
        kiem=[('Kiểm tra phiên bản Windows', 'Xem tại Cài đặt → Hệ thống → Giới thiệu (About): key bản Pro dùng cho Windows Pro. Nếu máy đang chạy bản Home, khi nhập key Pro Windows sẽ tự nâng cấp lên Pro – vui lòng lưu công việc trước vì máy sẽ khởi động lại.'),
              ('Kết nối Internet ổn định', 'Giữ kết nối Internet trong suốt quá trình kích hoạt.'),
              ('Sao chép và dán key', 'Dùng Ctrl+C, Ctrl+V thay vì gõ tay để tránh nhầm ký tự.'),
              ('Mỗi key kích hoạt cho một máy', 'Không dùng một key cho nhiều máy.')]),
    'm365': dict(
        nhom='Microsoft 365', giay_phep='Thuê bao 12 tháng – Retail (ESD)',
        link='https://setup.office.com/', nut='Kích hoạt tại setup.office.com',
        buoc=[('Truy cập trang kích hoạt', 'Mở <a href="https://setup.office.com/" style="color:%s;text-decoration:none">setup.office.com</a> trên trình duyệt.' % XANH),
              ('Đăng nhập tài khoản Microsoft', 'Đăng nhập hoặc tạo mới tài khoản Microsoft. Gói Microsoft 365 sẽ được gắn vào tài khoản này.'),
              ('Nhập mã key', 'Nhập mã key ở trên, chọn quốc gia / ngôn ngữ và bấm <b>Tiếp theo</b>.'),
              ('Tải và cài đặt', 'Vào <a href="https://account.microsoft.com/services" style="color:%s;text-decoration:none">account.microsoft.com/services</a>, chọn <b>Cài đặt</b> để tải Microsoft 365 cho máy tính; trên điện thoại, tải ứng dụng Word / Excel / Outlook từ App Store hoặc Google Play.' % XANH),
              ('Hoàn tất', 'Mở ứng dụng, đăng nhập đúng tài khoản Microsoft ở bước 2; gói sẽ tự động kích hoạt.')],
        kiem=[('Dùng tài khoản Microsoft cá nhân', 'Outlook, Hotmail hoặc email đã đăng ký Microsoft. Không dùng tài khoản công ty / trường học.'),
              ('Chỉ nhập key tại setup.office.com', 'Không nhập key trong Word / Excel.'),
              ('Đang dùng Microsoft 365?', 'Nếu tài khoản đang dùng đúng gói này (Personal hoặc Family), Quý khách vẫn nhập key bình thường – thời hạn mới được cộng dồn vào gói hiện tại.'),
              ('Mỗi key chỉ nhập một lần', 'Sau khi key đã gắn vào tài khoản, khi cài thêm máy Quý khách chỉ cần đăng nhập tài khoản đó, không nhập lại key.'),
              ('Sao chép và dán key', 'Dùng Ctrl+C, Ctrl+V thay vì gõ tay để tránh nhầm ký tự.')],
        tm='Microsoft và Microsoft 365 là thương hiệu của Microsoft Corporation.'),
    'kaspersky': dict(
        nhom='Kaspersky', giay_phep='Thuê bao 1 năm',
        link='https://www.kaspersky.com.vn/downloads', nut='Tải Kaspersky chính hãng',
        buoc=[('Tải phần mềm', 'Tải đúng phiên bản đã mua tại <a href="https://www.kaspersky.com.vn/downloads" style="color:%s;text-decoration:none">kaspersky.com.vn/downloads</a>.' % XANH),
              ('Cài đặt', 'Chạy bộ cài và làm theo hướng dẫn trên màn hình.'),
              ('Nhập mã kích hoạt', 'Khi ứng dụng yêu cầu, nhập mã kích hoạt ở trên và bấm <b>Kích hoạt</b>.'),
              ('Kết nối My Kaspersky (khuyên dùng)', 'Đăng nhập hoặc tạo tài khoản tại <a href="https://my.kaspersky.com/" style="color:%s;text-decoration:none">my.kaspersky.com</a> để quản lý thiết bị và bản quyền.' % XANH),
              ('Hoàn tất', 'Ứng dụng hiển thị trạng thái được bảo vệ và số ngày bản quyền còn lại.')],
        kiem=[('Gỡ phần mềm diệt virus khác', 'Gỡ các phần mềm diệt virus đang có trên máy trước khi cài, tránh xung đột.'),
              ('Tải đúng phiên bản', 'Phiên bản tải về phải trùng với bản đã mua (Standard / Plus / Premium / Small Office Security).'),
              ('Kết nối Internet ổn định', 'Giữ kết nối Internet trong suốt quá trình kích hoạt.'),
              ('Sao chép và dán mã', 'Dùng Ctrl+C, Ctrl+V thay vì gõ tay để tránh nhầm ký tự.')],
        tm='Kaspersky là thương hiệu của AO Kaspersky Lab.'),
}
LOAI['office']['tm'] = 'Microsoft và Office là thương hiệu của Microsoft Corporation.'
LOAI['windows']['tm'] = 'Microsoft và Windows là thương hiệu của Microsoft Corporation.'

# Danh mục sản phẩm phần mềm LaptopAZ đang bán (theo bài trên ADMIN, output/_moi/<mã>) → dùng: --sp <mã>
SAN_PHAM = {
    'EP2-06604': dict(loai='office', ten='Office Home & Business 2024', giay_phep='Vĩnh viễn – All Languages APAC EM Retail Online (ESD)',
                      pham_vi='1 người dùng, 1 máy tính Windows hoặc Mac.'),
    'EP2-06796': dict(loai='office', ten='Microsoft Office Home 2024', giay_phep='Vĩnh viễn – All Languages APAC EM Retail Online (ESD)',
                      pham_vi='1 người dùng, 1 máy tính Windows hoặc Mac.'),
    'EP2-06811': dict(loai='office', ten='Microsoft Office Home 2024', giay_phep='Vĩnh viễn – English APAC EM FPP Medialess',
                      pham_vi='1 người dùng, 1 máy tính Windows hoặc Mac.'),
    'EP2-32313': dict(loai='m365', ten='Microsoft 365 Personal', giay_phep='Thuê bao 12 tháng – APAC EM Online (ESD)',
                      pham_vi='1 người dùng, cài trên tối đa 5 thiết bị cùng lúc (máy tính, Mac, máy tính bảng, điện thoại).'),
    'EP2-32409': dict(loai='m365', ten='Microsoft 365 Personal', giay_phep='Thuê bao 12 tháng – English APAC Medialess',
                      pham_vi='1 người dùng, cài trên tối đa 5 thiết bị cùng lúc (máy tính, Mac, máy tính bảng, điện thoại).'),
    'EP2-36890': dict(loai='m365', ten='Microsoft 365 Family', giay_phep='Thuê bao 12 tháng – APAC EM Online (ESD)',
                      pham_vi='Tối đa 6 người dùng (chủ gói + mời thêm 5 người), mỗi người cài trên tối đa 5 thiết bị cùng lúc. Chủ gói mời thành viên tại account.microsoft.com/services → Chia sẻ.'),
    'EP2-36878': dict(loai='m365', ten='Microsoft 365 Family', giay_phep='Thuê bao 12 tháng – English APAC Medialess',
                      pham_vi='Tối đa 6 người dùng (chủ gói + mời thêm 5 người), mỗi người cài trên tối đa 5 thiết bị cùng lúc. Chủ gói mời thành viên tại account.microsoft.com/services → Chia sẻ.'),
    'KW9-00664': dict(loai='windows', ten='Windows 11 Home', giay_phep='Vĩnh viễn – All Languages Online (ESD)', pham_vi='1 máy tính.'),
    'FQC-10572': dict(loai='windows', ten='Windows 11 Pro', giay_phep='Vĩnh viễn – All Languages Online (ESD)', pham_vi='1 máy tính, máy mới hoặc đã qua sử dụng.'),
    'HAV-00163': dict(loai='windows', ten='Windows 11 Pro', giay_phep='Vĩnh viễn – English International FPP (USB)', pham_vi='1 máy tính, máy mới hoặc đã qua sử dụng.'),
    'FQC-10528': dict(loai='windows', ten='Windows 11 Pro', giay_phep='Vĩnh viễn – English International OEM DSP OEI (DVD)', pham_vi='1 máy tính, gắn với máy được cài đặt lần đầu.'),
    'KL1042WUAFS': dict(loai='kaspersky', ten='Kaspersky Plus', giay_phep='Thuê bao 1 năm', pham_vi='1 thiết bị (Windows, Mac, Android hoặc iOS).'),
    'KL10424UCFS': dict(loai='kaspersky', ten='Kaspersky Plus', giay_phep='Thuê bao 1 năm', pham_vi='3 thiết bị (Windows, Mac, Android hoặc iOS).'),
    'KL10424UEFS': dict(loai='kaspersky', ten='Kaspersky Plus', giay_phep='Thuê bao 1 năm', pham_vi='5 thiết bị (Windows, Mac, Android hoặc iOS).'),
    'KL1041WDEFS': dict(loai='kaspersky', ten='Kaspersky Standard', giay_phep='Thuê bao 1 năm', pham_vi='5 thiết bị (Windows, Mac, Android hoặc iOS).'),
    'KAV-STANDARD-3DVC': dict(loai='kaspersky', ten='Kaspersky Standard', giay_phep='Thuê bao 1 năm', pham_vi='3 thiết bị (Windows, Mac, Android hoặc iOS).'),
    'KAV-PREMIUM-1DVC': dict(loai='kaspersky', ten='Kaspersky Premium', giay_phep='Thuê bao 1 năm', pham_vi='1 thiết bị (Windows, Mac, Android hoặc iOS).'),
    'KSOS-1S5PC': dict(loai='kaspersky', ten='Kaspersky Small Office Security', giay_phep='Thuê bao 1 năm – Hộp (Box)', pham_vi='1 máy chủ + 5 máy tính.'),
    'KSOS-1S10PC': dict(loai='kaspersky', ten='Kaspersky Small Office Security', giay_phep='Thuê bao 1 năm – Hộp (Box)', pham_vi='1 máy chủ + 10 máy tính.'),
}

# Mô tả giấy phép: chỉ giải thích các thành phần CÓ trong chuỗi "Loại giấy phép", theo đúng thứ tự xuất hiện.
# (mẫu regex, nhãn hiển thị, mô tả chung, mô tả riêng theo loại)
THUAT_NGU = [
    (r'vĩnh viễn|perpetual', 'Vĩnh viễn', 'Mua một lần, sử dụng lâu dài, không phải gia hạn theo tháng / năm.', {}),
    (r'thuê bao\s*\d+\s*(tháng|năm)', None, 'Sử dụng trong {n} kể từ ngày kích hoạt. Khi hết hạn, Quý khách gia hạn bằng key mới để tiếp tục sử dụng.',
     {'kaspersky': 'Sử dụng trong {n} kể từ ngày kích hoạt. Khi hết hạn, Quý khách gia hạn bằng mã kích hoạt mới để tiếp tục được bảo vệ.',
      'm365': 'Sử dụng trong {n} kể từ ngày kích hoạt. Nhập key gia hạn khi gói còn hạn thì thời gian được cộng dồn, không mất ngày còn lại.'}),
    (r'all\s*(languages|lng)', 'All Languages', 'Hỗ trợ cài đặt mọi ngôn ngữ, gồm tiếng Việt và tiếng Anh.', {}),
    (r'english\s*(international|intl)|eng\s*intl', 'English International', 'Bộ cài và giao diện tiếng Anh (bản quốc tế).', {}),
    (r'\benglish\b(?!\s*(international|intl))', 'English', 'Phiên bản đóng gói tiếng Anh.', {}),
    (r'apac\s*em', 'APAC EM', 'Bản phát hành cho khu vực Châu Á – Thái Bình Dương, nhóm thị trường mới nổi (Emerging Markets), kích hoạt và sử dụng hợp lệ tại Việt Nam.', {}),
    (r'(?<!em)\s?apac(?!\s*em)', 'APAC', 'Bản phát hành cho khu vực Châu Á – Thái Bình Dương, kích hoạt và sử dụng hợp lệ tại Việt Nam.', {}),
    (r'\bretail\b', 'Retail (bản lẻ)', 'Bản quyền chính hãng Microsoft.',
     {'office': 'Bản quyền chính hãng Microsoft, gắn vào tài khoản Microsoft của Quý khách, sử dụng trên 1 máy tính (Windows hoặc Mac) tại một thời điểm.',
      'windows': 'Bản quyền chính hãng Microsoft, kích hoạt cho 1 máy tính tại một thời điểm.',
      'm365': 'Bản quyền chính hãng Microsoft, gắn vào tài khoản Microsoft của Quý khách.'}),
    (r'\boem\b', 'OEM', 'Bản quyền đi kèm máy, gắn với phần cứng của máy đã kích hoạt.', {}),
    (r'dsp\s*oei', 'DSP OEI', 'Bản OEM dành cho cài đặt mới trên máy tính lắp ráp hoặc máy chưa có Windows bản quyền.', {}),
    (r'\bfpp\b', 'FPP', 'Bản hộp (Full Packaged Product), có hộp và thẻ key chính hãng.', {}),
    (r'medialess', 'Medialess', 'Key vật lý không kèm đĩa cài hay USB; bộ cài tải trực tiếp từ Microsoft.', {}),
    (r'\(usb\)|\busb\b', 'USB', 'Kèm USB cài đặt Windows chính hãng.', {}),
    (r'\(dvd\)|\bdvd\b', 'DVD', 'Kèm đĩa DVD cài đặt Windows.', {}),
    (r'hộp\s*\(box\)|\bbox\b', 'Hộp (Box)', 'Hộp chứa key bản quyền chính hãng.', {}),
    (r'online\s*\(?\s*esd\s*\)?', 'Online (ESD)', 'Giao bản quyền điện tử qua email (Electronic Software Delivery), không kèm hộp hay đĩa cài; bộ cài tải trực tiếp từ Microsoft.', {}),
    (r'(?<!online \()\besd\b', 'ESD', 'Giao bản quyền điện tử qua email (Electronic Software Delivery), không kèm hộp hay đĩa cài; bộ cài tải trực tiếp từ hãng.', {}),
]


def mo_ta_giay_phep(chuoi, loai, pham_vi=''):
    """[(nhãn, mô tả)] chỉ cho các thuật ngữ có trong chuỗi Loại giấy phép, theo thứ tự xuất hiện."""
    thay, da = [], []
    for mau, nhan, chung, rieng in THUAT_NGU:
        for m in re.finditer(mau, chuoi, re.I):
            a, b = m.span()
            if any(a < y and x < b for x, y in da):
                continue
            da.append((a, b))
            d = rieng.get(loai, chung)
            if nhan is None:  # thuê bao N tháng / năm
                n = re.search(r'\d+\s*(tháng|năm)', m.group(0), re.I).group(0)
                nhan, d = f'Thuê bao {n}', d.format(n=n)
            thay.append((a, nhan, d))
            break
    # Anh chốt 25/11/2026: chỉ giải thích đúng các từ có trong "Loại giấy phép" (không thêm Phạm vi / Chuyển máy).
    return [(n, d) for _, n, d in sorted(thay)]


CHUYEN = {
    'office': 'Gỡ cài đặt Office và đăng xuất tài khoản Microsoft trên máy cũ, sau đó trên máy mới vào account.microsoft.com/services, đăng nhập đúng tài khoản đã kích hoạt và chọn <b>Cài đặt</b>. Không cần nhập lại key.',
    'windows': 'Gỡ key khỏi máy cũ (hoặc cài lại Windows trên máy cũ), sau đó nhập key trên máy mới tại Cài đặt → Hệ thống → Kích hoạt.',
    'm365': 'Đăng xuất thiết bị không dùng nữa tại account.microsoft.com/devices, sau đó cài và đăng nhập trên thiết bị mới. Không cần nhập lại key.',
    'kaspersky': 'Gỡ Kaspersky trên thiết bị cũ (hoặc xoá thiết bị khỏi My Kaspersky), sau đó cài và nhập mã kích hoạt trên thiết bị mới. Thời hạn bản quyền tính từ lần kích hoạt đầu tiên, không thay đổi khi chuyển máy.',
}


def chuyen_may(chuoi, loai):
    """Đặc điểm chuyển máy: OEM = không; Retail / FPP / Microsoft 365 / Kaspersky = được."""
    xanh, do = '#1e8e3e', '#c5221f'
    if re.search(r'\boem\b', chuoi, re.I):
        return ('Chuyển sang máy khác', f'<b style="color:{do}">Không.</b> Bản quyền OEM gắn với máy đã kích hoạt, không chuyển sang máy khác.')
    if loai in ('m365', 'kaspersky') or re.search(r'\bretail\b|\bfpp\b', chuoi, re.I):
        pham = {'m365': 'trong số thiết bị của gói', 'kaspersky': 'trong số thiết bị của gói'}.get(loai, 'mỗi lúc dùng trên 1 máy')
        return ('Chuyển sang máy khác', f'<b style="color:{xanh}">Được</b> ({pham}). {CHUYEN[loai]} LaptopAZ hỗ trợ chuyển máy qua UltraViewer khi Quý khách cần.')
    return None


KSOS_LINK = 'https://www.kaspersky.com/small-business-security/downloads/small-office-security'


def cau_hinh(a):
    """Bản sao cấu hình LOAI chỉnh theo đúng sản phẩm: Windows Home / USB / DVD, Microsoft 365 Family, Kaspersky Small Office."""
    L = dict(LOAI[a.loai]); L['buoc'] = list(L['buoc']); L['kiem'] = list(L['kiem'])
    gp = a.giay_phep or L['giay_phep']
    if a.loai == 'windows':
        if re.search(r'\bhome\b', a.ten, re.I):
            L['kiem'][0] = ('Kiểm tra phiên bản Windows', 'Xem tại Cài đặt → Hệ thống → Giới thiệu (About): key bản Home chỉ kích hoạt được Windows Home. Nếu máy đang cài bản Pro, Quý khách liên hệ LaptopAZ để được hướng dẫn trước khi nhập key.')
        if re.search(r'\b(usb|dvd)\b', gp, re.I):
            vat = 'USB' if re.search(r'usb', gp, re.I) else 'DVD'
            L['kiem'].insert(1, (f'Cài mới bằng {vat} đi kèm', f'Khi cài Windows từ {vat}, nhập key lúc trình cài đặt yêu cầu; hoặc chọn <b>I don\'t have a product key</b> rồi kích hoạt sau theo hướng dẫn bên dưới.'))
    if a.loai == 'm365' and re.search(r'family', a.ten, re.I):
        L['buoc'].insert(4, ('Chia sẻ cho gia đình', 'Vào <a href="https://account.microsoft.com/services" style="color:%s;text-decoration:none">account.microsoft.com/services</a> → <b>Chia sẻ</b> để mời tối đa 5 người dùng chung gói.' % XANH))
    if a.loai == 'kaspersky' and re.search(r'small\s*office', a.ten, re.I):
        L['link'] = KSOS_LINK
        L['buoc'][0] = ('Tải phần mềm', 'Tải Kaspersky Small Office Security tại <a href="%s" style="color:%s;text-decoration:none">trang tải chính thức của Kaspersky</a>.' % (KSOS_LINK, XANH))
        L['kiem'][1] = ('Tải đúng phiên bản', 'Dùng bộ cài Kaspersky Small Office Security (không dùng bộ cài Standard / Plus / Premium).')
    return L


# Lưu ý (anh chốt 25/11/2026): phần mềm bản quyền KHÔNG bảo hành, không đổi trả theo chính sách nhà phát hành; hỗ trợ kỹ thuật do hãng.
HO_TRO_HANG = {
    'kaspersky': ('Kaspersky', 'https://support.kaspersky.com/', 'support.kaspersky.com'),
}
HO_TRO_MS = ('Microsoft', 'https://support.microsoft.com/vi-vn/contactus', 'support.microsoft.com/vi-vn/contactus')


def luu_y_ds(loai, html_=True):
    hang, link, chu = HO_TRO_HANG.get(loai, HO_TRO_MS)
    b = (lambda x: f'<b style="color:#1d1d1f;font-weight:600">{x}</b>') if html_ else (lambda x: x)
    lk = f'<a href="{link}" style="color:{XANH};text-decoration:none">{chu}</a>' if html_ else link
    return [
        f'Theo chính sách của nhà phát hành {hang}, sản phẩm phần mềm bản quyền {b("không áp dụng bảo hành và đổi trả")} sau khi mã kích hoạt đã được cung cấp.',
        f'Các vấn đề kỹ thuật trong quá trình sử dụng được {hang} hỗ trợ trực tiếp tại {lk}. LaptopAZ luôn sẵn sàng hỗ trợ Quý khách cài đặt và kích hoạt ban đầu.',
        'Quý khách vui lòng lưu lại email này để tiện tra cứu khi cài đặt lại máy hoặc cần hỗ trợ.',
        'Mã kích hoạt là thông tin bảo mật, chỉ dành riêng cho Quý khách – vui lòng không chia sẻ cho người khác.',
    ]


def e(s):
    return html.escape(str(s))


def T(size, lh, color=CHU, weight='normal', extra=''):
    """Kiểu chữ nội tuyến."""
    return f'{FONT}font-size:{size}px;line-height:{lh}px;font-weight:{weight};color:{color};{extra}'


def hang(noi_dung, pad='0 24px'):
    return f'<tr><td style="padding:{pad}">{noi_dung}</td></tr>'


def ke(pad='24px 24px'):
    """Đường kẻ mảnh ngăn các phần."""
    return f'''<tr><td style="padding:{pad}"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      <tr><td height="1" style="height:1px;line-height:1px;font-size:0;background-color:{KE}" bgcolor="{KE}">&nbsp;</td></tr></table></td></tr>'''


def tieu_de_muc(ten, phu=''):
    p = f'<div style="{T(13, 20, PHU)}padding-top:4px">{phu}</div>' if phu else ''
    return hang(f'<div style="{T(17, 24, CHU, 600)}">{ten}</div>{p}', '0 24px 18px 24px')


def bieu_tuong(noi_dung, nen=XANH_NHAT, mau=XANH):
    """Ô tròn nhỏ (Outlook Windows hiện ô vuông – vẫn gọn)."""
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr><td width="28" height="28" align="center" valign="middle" '
            f'bgcolor="{nen}" style="width:28px;height:28px;background-color:{nen};border-radius:14px;{T(13, 28, mau, 700)}">{noi_dung}</td></tr></table>')


def danh_sach(items, icon):
    """Danh sách có biểu tượng bên trái: [(tiêu đề, mô tả)]."""
    rows = ''.join(f'''<tr>
        <td width="44" valign="top" style="padding:0 0 18px 0">{bieu_tuong(icon(i))}</td>
        <td valign="top" style="padding:3px 0 18px 0;{T(14, 21)}"><b style="font-weight:600">{t}</b><br><span style="{T(13, 20, PHU)}">{d}</span></td></tr>'''
                   for i, (t, d) in enumerate(items, 1))
    return f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>'


def dong_tt(nhan, gt, cuoi=False):
    """Dòng thông tin kiểu hoá đơn: nhãn xám trái – giá trị phải."""
    bd = '' if cuoi else f'border-bottom:1px solid {KE};'
    return f'''<tr>
        <td valign="top" style="padding:12px 0;{bd}{T(14, 20, PHU)}white-space:nowrap">{nhan}</td>
        <td valign="top" align="right" style="padding:12px 0 12px 16px;{bd}{T(14, 20, CHU, 600)}text-align:right">{gt}</td></tr>'''


def khoi_key(keys, ten_key='Product Key'):
    out = []
    for i, k in enumerate(keys, 1):
        nhan = f'{ten_key} {i} / {len(keys)}' if len(keys) > 1 else ten_key
        out.append(f'''<tr><td style="padding:0 0 12px 0">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{NEN}" style="background-color:{NEN};border-radius:12px">
          <tr><td align="center" style="padding:22px 16px 6px 16px;{T(12, 16, PHU, 600, 'letter-spacing:1.5px;text-transform:uppercase;')}">{nhan}</td></tr>
          <tr><td align="center" style="padding:0 16px 22px 16px;{MONO}font-size:20px;line-height:28px;font-weight:600;color:{CHU};letter-spacing:1px;-webkit-user-select:all;-moz-user-select:all;user-select:all;cursor:text">{e(k)}</td></tr>
        </table></td></tr>''')
    return ''.join(out)


def nut(link, chu, chinh=True):
    nen, mau, vien = (XANH, '#ffffff', XANH) if chinh else ('#ffffff', XANH, XANH)
    return f'''<!--[if mso]><v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" href="{link}" style="height:48px;v-text-anchor:middle;width:320px" arcsize="50%" strokecolor="{vien}" fillcolor="{nen}"><center style="color:{mau};font-family:'Segoe UI',Arial,sans-serif;font-size:15px;font-weight:bold">{e(chu)}</center></v:roundrect><![endif]-->
    <!--[if !mso]><!--><table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center"><tr><td bgcolor="{nen}" style="background-color:{nen};border:1px solid {vien};border-radius:24px">
      <a href="{link}" style="display:inline-block;padding:13px 22px;{T(14, 18, mau, 600)}text-decoration:none;border-radius:24px;white-space:nowrap;text-align:center">{e(chu)}</a>
    </td></tr></table><!--<![endif]-->'''


def tieu_de(a):
    return f'[LaptopAZ] Thông tin bản quyền {a.ten}'


def tao_html(a):
    L = cau_hinh(a)
    n = len(a.key)
    ten_sp = e(a.ten) + (f'<br><span style="{T(13, 19, PHU)}">{e(a.ma)}</span>' if a.ma else '')
    ky = f'<b style="{T(14, 20, CHU, 600)}">{e(a.nguoi_gui)}</b>' + (f'<br><span style="{T(13, 20, PHU)}">{e(a.chuc_vu)}</span>' if a.chuc_vu else '')
    dia_chi = f'<br>{e(a.dia_chi)}' if a.dia_chi else ''
    gp = ''.join(f'<tr><td style="padding:4px 20px 6px 20px;{T(13, 20, PHU)}"><b style="color:{CHU};font-weight:600">{t}:</b> {d}</td></tr>' for t, d in mo_ta_giay_phep(a.giay_phep or L['giay_phep'], a.loai, a.pham_vi))
    luu_y = ''.join(f'<tr><td width="18" valign="top" style="{T(14, 22, PHU)}">&#8226;</td><td style="padding-bottom:6px;{T(14, 22, PHU)}">{x}</td></tr>' for x in luu_y_ds(a.loai))
    tick = lambda i: '&#10003;'
    so = lambda i: str(i)
    return f'''<!DOCTYPE html>
<html lang="vi" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="x-apple-disable-message-reformatting"><meta name="format-detection" content="telephone=no,address=no,email=no,date=no">
<title>{e(tieu_de(a))}</title>
<!--[if mso]><style>td,a,span,b,div{{font-family:'Segoe UI',Arial,sans-serif !important}}</style><![endif]-->
<!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->
</head>
<body style="margin:0;padding:0;background-color:{NEN};-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%">
<div style="display:none;font-size:1px;line-height:1px;max-height:0;max-width:0;opacity:0;overflow:hidden;mso-hide:all">Mã kích hoạt {e(a.ten)} của Quý khách đã sẵn sàng, kèm hướng dẫn kích hoạt.&#8199;&#65279;&#847;&#8199;&#65279;&#847;</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{NEN}" style="background-color:{NEN}">
<tr><td align="center" style="padding:24px 10px">
<!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->

<!-- Logo ngoài thẻ -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px">
  <tr><td align="center" style="padding:0 0 24px 0"><a href="https://{WEB}" style="text-decoration:none"><img src="{LOGO}" alt="LaptopAZ" width="120" style="display:block;width:120px;max-width:120px;height:auto;border:0;outline:none"></a></td></tr>
</table>

<!-- Thẻ nội dung -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="max-width:600px;background-color:#ffffff;border-radius:16px">

  <!-- Tiêu đề chính -->
  <tr><td align="center" style="padding:36px 24px 0 24px;{T(12, 16, XANH, 700, 'letter-spacing:1.5px;text-transform:uppercase;')}">Bản quyền phần mềm</td></tr>
  <tr><td align="center" style="padding:10px 24px 0 24px;{T(24, 31, CHU, 600)}">Mã kích hoạt của Quý khách đã sẵn sàng</td></tr>
  <tr><td align="center" style="padding:12px 24px 0 24px;{T(14, 20, PHU)}">{e(a.ten)}</td></tr>

  <!-- Lời chào -->
  <tr><td style="padding:24px 24px 0 24px;{T(14, 22)}">
    Kính gửi {e(a.khach)},<br><br>
    Trân trọng cảm ơn Quý khách đã lựa chọn sản phẩm bản quyền tại LaptopAZ. Đơn hàng của Quý khách đã được xử lý thành công.
    Dưới đây là mã kích hoạt <b style="font-weight:600">{e(L['nhom'])}</b> và hướng dẫn chi tiết.
  </td></tr>

  <!-- Key + nút chính -->
  <tr><td style="padding:28px 24px 0 24px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{khoi_key(a.key, 'Activation Code' if a.loai == 'kaspersky' else 'Product Key')}</table>
    <div style="{T(13, 19, PHU)}text-align:center;padding:2px 0 0 0">Chạm (hoặc nhấp) vào key để chọn toàn bộ, sau đó sao chép.</div>
  </td></tr>
  <tr><td align="center" style="padding:24px 24px 0 24px">{nut(L['link'], L['nut'])}</td></tr>

  {ke('24px 24px 24px 24px')}

  <!-- Thông tin đơn hàng -->
  {tieu_de_muc('Thông tin đơn hàng')}
  <tr><td style="padding:0 24px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
      {dong_tt('Sản phẩm', ten_sp)}
      {dong_tt('Loại giấy phép', e(a.giay_phep or L['giay_phep']))}
      {dong_tt('Số lượng', f'{n:02d} bản quyền')}
      {dong_tt('Ngày cấp', e(a.ngay), cuoi=True)}
    </table>
  </td></tr>
  <tr><td style="padding:16px 24px 0 24px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{NEN}" style="background-color:{NEN};border-radius:12px">
      <tr><td style="padding:18px 20px 6px 20px;{T(14, 20, CHU, 600)}">Mô tả giấy phép</td></tr>
      {gp}
      <tr><td style="padding:0 0 12px 0;font-size:0;line-height:0">&nbsp;</td></tr>
    </table>
  </td></tr>

  {ke()}

  <!-- Trước khi kích hoạt -->
  {tieu_de_muc('Trước khi kích hoạt', 'Vui lòng kiểm tra các điểm sau để kích hoạt thành công ngay lần đầu.')}
  {hang(danh_sach(L['kiem'], tick))}

  {ke('14px 24px 24px 24px')}

  <!-- Hướng dẫn -->
  {tieu_de_muc('Hướng dẫn kích hoạt')}
  {hang(danh_sach(L['buoc'], so))}

  <!-- Cần hỗ trợ -->
  <tr><td style="padding:14px 24px 0 24px">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{NEN}" style="background-color:{NEN};border-radius:12px">
      <tr><td align="center" style="padding:28px 24px 6px 24px;{T(16, 23, CHU, 600)}">Cần hỗ trợ?</td></tr>
      <tr><td align="center" style="padding:0 24px 18px 24px;{T(14, 22, PHU)}">Nếu chưa quen thao tác, Quý khách liên hệ <b style="color:{CHU};font-weight:600">trước khi nhập key</b>.<br>
        Kỹ thuật viên LaptopAZ sẽ hỗ trợ cài đặt và kích hoạt từ xa qua <b style="color:{CHU};font-weight:600">UltraViewer</b>.</td></tr>
      <tr><td align="center" style="padding:0 24px 28px 24px">{nut('tel:' + HOTLINE_TEL, 'Gọi hotline ' + HOTLINE, chinh=False)}</td></tr>
    </table>
  </td></tr>

  <!-- Lưu ý -->
  <tr><td style="padding:28px 24px 0 24px">
    <div style="{T(14, 22, CHU, 600)}padding-bottom:8px">Lưu ý</div>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{luu_y}</table>
  </td></tr>

  <!-- Kết thư + chữ ký -->
  <tr><td style="padding:28px 24px 0 24px;{T(14, 22)}">LaptopAZ cảm ơn Quý khách đã tin tưởng và lựa chọn.<br><br>Trân trọng,</td></tr>
  <tr><td style="padding:16px 24px 36px 24px">
    <table role="presentation" cellpadding="0" cellspacing="0" border="0"><tr>
      <td valign="middle" style="padding-right:16px;border-right:2px solid {XANH}"><img src="{LOGO}" alt="LaptopAZ" width="72" style="display:block;width:72px;height:auto;border:0"></td>
      <td valign="middle" style="padding-left:16px;{T(13, 20, PHU)}">{ky}<br>{CONG_TY}<br>Hotline <a href="tel:{HOTLINE_TEL}" style="color:{XANH};text-decoration:none">{HOTLINE}</a> &nbsp;·&nbsp; <a href="https://{WEB}" style="color:{XANH};text-decoration:none">{WEB}</a></td>
    </tr></table>
  </td></tr>
</table>

<!-- Chân thư ngoài thẻ -->
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px">
  <tr><td align="center" style="padding:28px 24px 8px 24px;{T(12, 18, MO, 600)}">{CONG_TY}</td></tr>
  <tr><td align="center" style="padding:0 24px 8px 24px;{T(12, 18, MO)}">
    Hotline <a href="tel:{HOTLINE_TEL}" style="color:{MO};text-decoration:underline">{HOTLINE}</a> &nbsp;·&nbsp;
    <a href="mailto:{EMAIL}" style="color:{MO};text-decoration:underline">{EMAIL}</a> &nbsp;·&nbsp;
    <a href="https://{WEB}" style="color:{MO};text-decoration:underline">{WEB}</a>{dia_chi}</td></tr>
  <tr><td align="center" style="padding:8px 24px 0 24px;{T(11, 17, MO)}">
    Email này chứa thông tin bản quyền dành riêng cho khách hàng của LaptopAZ. Nếu nhận nhầm, vui lòng thông báo cho chúng tôi và xoá email.<br>
    {L['tm']}</td></tr>
</table>

<!--[if mso]></td></tr></table><![endif]-->
</td></tr>
</table>
</body>
</html>
'''


def tao_txt(a):
    L = cau_hinh(a)
    sach = lambda x: re.sub('<[^>]+>', '', x)
    keys = '\n'.join(f'  {"Key " + str(i) + ": " if len(a.key) > 1 else ""}{k}' for i, k in enumerate(a.key, 1))
    kiem = '\n'.join(f'  [v] {t}: {sach(d)}' for t, d in L['kiem'])
    buoc = '\n'.join(f'  {i}. {t}: {sach(m)}' for i, (t, m) in enumerate(L['buoc'], 1))
    return f'''TIÊU ĐỀ (Subject): {tieu_de(a)}

Kính gửi {a.khach},

Trân trọng cảm ơn Quý khách đã lựa chọn sản phẩm bản quyền tại LaptopAZ. Đơn hàng của Quý khách đã được xử lý thành công.

MÃ KÍCH HOẠT ({'ACTIVATION CODE' if a.loai == 'kaspersky' else 'PRODUCT KEY'})
{keys}

THÔNG TIN ĐƠN HÀNG
  Sản phẩm: {a.ten}{f" ({a.ma})" if a.ma else ""}
  Loại giấy phép: {a.giay_phep or L["giay_phep"]}
  Số lượng: {len(a.key):02d} bản quyền
  Ngày cấp: {a.ngay}
  Mô tả giấy phép:
{chr(10).join(f'    - {t}: {re.sub("<[^>]+>", "", d)}' for t, d in mo_ta_giay_phep(a.giay_phep or L["giay_phep"], a.loai, a.pham_vi))}

TRƯỚC KHI KÍCH HOẠT (để kích hoạt thành công ngay lần đầu)
{kiem}

HƯỚNG DẪN KÍCH HOẠT
{buoc}
  {L["nut"]}: {L["link"]}

CẦN HỖ TRỢ?
  Nếu chưa quen thao tác, liên hệ hotline {HOTLINE} trước khi nhập key – kỹ thuật viên LaptopAZ sẽ hỗ trợ cài đặt và kích hoạt từ xa qua UltraViewer.

LƯU Ý
{chr(10).join("  - " + x for x in luu_y_ds(a.loai, False))}

LaptopAZ cảm ơn Quý khách đã tin tưởng và lựa chọn.

Trân trọng,
{a.nguoi_gui}{chr(10) + a.chuc_vu if a.chuc_vu else ""}
{CONG_TY}
Hotline: {HOTLINE} | Email: {EMAIL} | Website: {WEB}{chr(10) + a.dia_chi if a.dia_chi else ""}
'''


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--khach', default='Quý khách', help='Bỏ trống = "Quý khách" (mặc định). Có tên: "Anh/Chị Nguyễn Văn A"')
    p.add_argument('--sp', choices=SAN_PHAM, metavar='MÃ', help='Mã sản phẩm có sẵn (xem --ds) – tự điền loại, tên, mã, loại giấy phép, phạm vi')
    p.add_argument('--ds', action='store_true', help='Liệt kê các sản phẩm có sẵn rồi thoát')
    p.add_argument('--loai', choices=LOAI, default=None)
    p.add_argument('--ten', default='', help='Tên phần mềm')
    p.add_argument('--pham-vi', dest='pham_vi', default='', help='Phạm vi sử dụng, VD "1 người dùng, 5 thiết bị"')
    p.add_argument('--ma', default='', help='Mã sản phẩm hãng, VD EP2-06604')
    p.add_argument('--key', action='append', default=[], help='Mã key (lặp lại --key nếu nhiều key)')
    p.add_argument('--ra', default='', help='Tên file ra (mặc định: <mã sản phẩm>-<giờ tạo>)')
    p.add_argument('--ngay', default=date.today().strftime('%d/%m/%Y'))
    p.add_argument('--giay-phep', dest='giay_phep', default='')
    p.add_argument('--dia-chi', dest='dia_chi', default='')
    p.add_argument('--mo', action='store_true', help='Mở file HTML trong trình duyệt (tab nền) sau khi tạo')
    a = p.parse_args()
    a.nguoi_gui, a.chuc_vu = NGUOI_GUI, ''
    if a.ds:
        for k, v in SAN_PHAM.items():
            print(f'{k:20} {v["loai"]:10} {v["ten"]} | {v["giay_phep"]}')
        raise SystemExit
    if a.sp:
        sp = SAN_PHAM[a.sp]
        a.loai = a.loai or sp['loai']; a.ten = a.ten or sp['ten']; a.giay_phep = a.giay_phep or sp['giay_phep']
        a.pham_vi = a.pham_vi or sp.get('pham_vi', '')
        a.ma = a.ma or sp.get('ma', '' if a.sp.startswith(('KAV-', 'KSOS-')) else a.sp)
    a.loai = a.loai or 'office'
    if not (a.ten and a.key):
        p.error('cần --ten (hoặc --sp) và --key')
    OUT.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    ten_file = a.ra or f"{(a.sp or a.loai)}-{datetime.now():%Y%m%d-%H%M%S}"
    h, t = OUT / f'{ten_file}.html', OUT / f'{ten_file}.txt'
    h.write_text(tao_html(a), encoding='utf-8'); t.write_text(tao_txt(a), encoding='utf-8')
    print('Subject:', tieu_de(a)); print(h); print(t)
    if a.mo:
        subprocess.run(['open', '-g', str(h)])
