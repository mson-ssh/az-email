"""AZ Email – trang soạn email gửi KEY bản quyền cho khách (LaptopAZ).

    python3 app/web.py                  → http://127.0.0.1:8889   (cấu hình qua biến môi trường / file .env)

Chọn / Paste (chữ hoặc ảnh) → tự nhận sản phẩm + key → xem trước → "Sao chép email" → dán vào Gmail.
- KHÔNG lưu key: không ghi file, không DB, không log nội dung yêu cầu. Ảnh chỉ ghi tạm để OCR rồi xoá ngay.
- Đăng nhập Basic Auth (EMAIL_KEY_USER / EMAIL_KEY_PASS) cho mọi truy cập (trừ khi AUTH_BYPASS_LOCAL=1 và mở từ 127.0.0.1).
- OCR: PaddleOCR trên server (Docker, mặc định) · Apple Vision trên macOS · Tesseract dự phòng (OCR_ENGINE=auto|paddle|vision|tesseract).
- Chỉ dùng thư viện chuẩn Python 3.10+, không cần pip.
"""
import base64, hmac, json, os, platform, re, shutil, subprocess, sys, tempfile
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parent
GOC = APP.parent


def _nap_env(f=GOC / '.env'):
    """Nạp .env (KEY=VALUE) vào biến môi trường nếu chưa đặt."""
    if f.exists():
        for l in f.read_text(encoding='utf-8').splitlines():
            l = l.strip()
            if l and not l.startswith('#') and '=' in l:
                k, v = l.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_nap_env()
sys.path.insert(0, str(APP))
import tao_email_key as M  # noqa: E402

HOST = os.environ.get('HOST', '127.0.0.1')
PORT = int(os.environ.get('PORT', '8889'))
NGUOI_DUNG = os.environ.get('EMAIL_KEY_USER', 'admin')
MAT_KHAU = os.environ.get('EMAIL_KEY_PASS', '')
BO_QUA_LOCAL = os.environ.get('AUTH_BYPASS_LOCAL', '0') == '1'
DATA = Path(os.environ.get('DATA_DIR', GOC / 'data'))
OCR_ENGINE = os.environ.get('OCR_ENGINE', 'auto').lower()     # auto | paddle | vision | tesseract
OCR_LANG = os.environ.get('OCR_LANG', 'vie+eng')              # chỉ cho tesseract
OCR_GPU = os.environ.get('OCR_GPU', '0') == '1'               # PaddleOCR dùng GPU NVIDIA (cần image paddlepaddle-gpu)


def tao(d):
    sp = M.SAN_PHAM.get(d.get('sp') or '', {})
    keys = [k.strip() for k in (d.get('keys') or '').replace(',', '\n').splitlines() if k.strip()]
    a = SimpleNamespace(
        khach=(d.get('khach') or '').strip() or 'Quý khách',
        loai=d.get('loai') or sp.get('loai') or 'office',
        ten=(d.get('ten') or '').strip() or sp.get('ten', ''),
        ma=(d.get('ma') or '').strip() or sp.get('ma', '' if (d.get('sp') or '').startswith(('KAV-', 'KSOS-')) else (d.get('sp') or '')),
        giay_phep=(d.get('giay_phep') or '').strip() or sp.get('giay_phep', ''),
        pham_vi=sp.get('pham_vi', ''),
        key=keys or ['XXXXX-XXXXX-XXXXX-XXXXX-XXXXX'],
        ngay=(d.get('ngay') or '').strip() or date.today().strftime('%d/%m/%Y'),
        nguoi_gui=M.NGUOI_GUI, chuc_vu='', dia_chi='')
    if a.loai not in M.LOAI:
        a.loai = 'office'
    a.ten = a.ten or 'Tên phần mềm'
    return {'subject': M.tieu_de(a), 'html': M.tao_html(a), 'txt': M.tao_txt(a).split('\n', 2)[2],
            'du': bool(keys) and bool(d.get('chon'))}


# ---------- Phân tích email nhà cung cấp (dạng chữ) ----------
RE_KEY = re.compile(r'\b(?:[A-Z0-9]{5}-){3,4}[A-Z0-9]{5}\b')
RE_PART = re.compile(r'\b([A-Z0-9]{3}-\d{5}|KL\d{4}[A-Z0-9]{4,6})\b')


def _sach_ten(t):
    t = re.sub(r'^\s*(phần mềm|bản quyền)\s+', '', t, flags=re.I)
    t = re.sub(r'[_\s]*\(?\s*[A-Z0-9]{3}-\d{5}\s*\)?', '', t)                 # bỏ part number
    t = re.sub(r'([A-Za-z])(20\d\d)\b', r'\1 \2', t)                           # Business2024 → Business 2024
    goc = re.split(r'\b(all\s*(lng|languages)|apac|retail|oem|fpp|online|esd|medialess|\d+\s*(tháng|năm|months?|years?))\b', t, flags=re.I)[0]
    return re.sub(r'\s+', ' ', goc).strip(' -_–|,')


def _giay_phep(t):
    """Dựng chuỗi Loại giấy phép từ tên hàng hoá của nhà cung cấp."""
    g = []
    m = re.search(r'(\d+)\s*(tháng|năm|months?|years?)', t, re.I)
    if m:
        dv = {'month': 'tháng', 'months': 'tháng', 'year': 'năm', 'years': 'năm'}.get(m.group(2).lower(), m.group(2).lower())
        g.append(f'Thuê bao {m.group(1)} {dv}')
    elif re.search(r'office|windows', t, re.I) and not re.search(r'365', t):
        g.append('Vĩnh viễn')
    phan = []
    if re.search(r'all\s*(lng|languages)', t, re.I): phan.append('All Languages')
    if re.search(r'apac\s*em', t, re.I): phan.append('APAC EM')
    elif re.search(r'\bapac\b', t, re.I): phan.append('APAC')
    for w, nhan in (('retail', 'Retail'), ('oem', 'OEM'), ('fpp', 'FPP'), ('medialess', 'Medialess')):
        if re.search(rf'\b{w}\b', t, re.I): phan.append(nhan)
    if re.search(r'\besd\b', t, re.I):
        phan.append('Online (ESD)' if re.search(r'\bonline\b', t, re.I) else '(ESD)')
    if phan:
        g.append(' '.join(phan).replace(' (ESD)', ' (ESD)'))
    return ' – '.join(g)


def _loai(t):
    if re.search(r'kaspersky', t, re.I): return 'kaspersky'
    if re.search(r'365', t): return 'm365'
    if re.search(r'windows', t, re.I): return 'windows'
    return 'office'


OCR_SRC = APP / 'ocr.swift'
OCR_BIN = DATA / '.ocr-vision'


def _co_paddle():
    try:
        import importlib.util
        return importlib.util.find_spec('paddleocr') is not None
    except Exception:
        return False


def _bo_doc():
    if OCR_ENGINE in ('paddle', 'vision', 'tesseract'):
        return OCR_ENGINE
    if _co_paddle():
        return 'paddle'
    if platform.system() == 'Darwin' and shutil.which('swiftc'):
        return 'vision'
    return 'tesseract'


_PADDLE = None
_PADDLE_KHOA = __import__('threading').Lock()


def _paddle(duong_dan):
    """PaddleOCR (Apache-2.0) – mô hình 'en' tải sẵn lúc build, chạy offline trên CPU (hoặc GPU nếu OCR_GPU=1).
    Đo 100 ảnh key: 86% đúng tuyệt đối (Tesseract 81%, Apple Vision 90%). Không an toàn đa luồng → khoá."""
    global _PADDLE
    with _PADDLE_KHOA:
        if _PADDLE is None:
            from paddleocr import PaddleOCR
            _PADDLE = PaddleOCR(use_angle_cls=False, lang='en', show_log=False, use_gpu=OCR_GPU)
        kq = _PADDLE.ocr(duong_dan, cls=False)
    return '\n'.join(x[1][0] for x in ((kq or [None])[0] or []))


def ocr(du_lieu: bytes) -> str:
    """Ảnh → chữ. Server: PaddleOCR; macOS: Apple Vision; dự phòng: Tesseract. Ảnh ghi tạm rồi xoá ngay."""
    bo = _bo_doc()
    with tempfile.NamedTemporaryFile(suffix='.png') as f:
        f.write(du_lieu); f.flush()
        if bo == 'paddle':
            return _paddle(f.name)
        if bo == 'vision':
            if not OCR_BIN.exists() or OCR_BIN.stat().st_mtime < OCR_SRC.stat().st_mtime:
                DATA.mkdir(parents=True, exist_ok=True)
                subprocess.run(['swiftc', '-O', str(OCR_SRC), '-o', str(OCR_BIN)], check=True, capture_output=True)
            r = subprocess.run([str(OCR_BIN), f.name], capture_output=True, text=True, timeout=60)
        else:
            if not shutil.which('tesseract'):
                raise RuntimeError('máy chủ chưa cài tesseract-ocr (xem README)')
            return _tesseract(f.name)
    if r.returncode:
        raise RuntimeError((r.stderr or '').strip()[:200] or 'OCR lỗi')
    return r.stdout


def _tesseract(duong_dan):
    """Tesseract đọc chữ nhỏ (bảng phần mềm, ảnh 1x) kém → trắng đen + phóng to 2x + tăng tương phản, đọc 2 lượt
    (psm 3: cả trang; psm 11: chữ rời rạc kiểu bảng) rồi gộp dòng."""
    from PIL import Image, ImageOps
    im = Image.open(duong_dan).convert('L')
    if im.width < 2400:
        im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    im = ImageOps.autocontrast(im)
    def chay(*thamso):
        r = subprocess.run(['tesseract', g.name, 'stdout', *thamso], capture_output=True, text=True, timeout=90)
        if r.returncode:
            raise RuntimeError((r.stderr or '').strip()[:200] or 'OCR lỗi')
        return r.stdout

    KEY = re.compile(r'(?:[A-Z0-9]{5}[ \t]*-[ \t]*){3,4}[A-Z0-9]{5}', re.I)   # không nối qua xuống dòng
    with tempfile.NamedTemporaryFile(suffix='.png') as g:
        im.save(g.name)
        trang = chay('-l', OCR_LANG, '--psm', '3')            # cả trang (thứ tự dòng → gán key theo sản phẩm)
        bang = chay('-l', OCR_LANG, '--psm', '11')            # chữ rời rạc kiểu bảng (mã hàng, tên hàng)
        # Lượt riêng cho KEY: chỉ cho phép A–Z, 0–9, "-" → đo thử 100 ảnh: 57% → 83% key đúng tuyệt đối
        wl = chay('-l', 'eng', '--psm', '6', '-c', 'tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')
    key_wl = [re.sub(r'\s+', '', k).upper() for k in KEY.findall(wl)]
    dong_tr = [l for l in trang.splitlines() if l.strip()]
    vt = [i for i, l in enumerate(dong_tr) if KEY.search(l)]   # các dòng có key trong lượt cả trang
    if key_wl and len(key_wl) == len(vt):                       # thay CẢ DÒNG bằng key lượt whitelist, giữ vị trí
        for i, k in zip(vt, key_wl):
            dong_tr[i] = k
    elif key_wl:                                               # số key lệch → bỏ dòng key cũ, thêm key whitelist vào cuối
        dong_tr = [l for i, l in enumerate(dong_tr) if i not in vt] + key_wl
    dong = dong_tr + [KEY.sub(' ', l) for l in bang.splitlines() if l.strip()]
    return '\n'.join(dict.fromkeys(dong))


# (25/11/2026) Bỏ kiểm bộ ký tự key Microsoft: key thật nhà cung cấp cấp có cả N, Z → báo nhầm. Key đọc từ ảnh chỉ kèm ghi chú đối chiếu.


import unicodedata
MA_NCC_FILE = DATA / 'ma_ncc.json'   # mã hàng nội bộ nhà cung cấp → mã sản phẩm (không chứa key)
RE_KEY5 = re.compile(r'(?<![A-Z0-9-])(?:[A-Z0-9]{5}-){4}[A-Z0-9]{5}(?![A-Z0-9-])')
RE_KEY4 = re.compile(r'(?<![A-Z0-9-])(?:[A-Z0-9]{5}-){3}[A-Z0-9]{5}(?![A-Z0-9])')
RE_KEY_CUT = re.compile(r'(?<![A-Z0-9-])(?:[A-Z0-9]{5}-){2,4}(?=\s|$|[^A-Z0-9])')   # key bị cắt / che (kết thúc bằng "-")
RE_MA_NCC = re.compile(r'\b(PM[A-Z]{2}\d{3,5}|[A-Z]{2,4}\d{4,6})\b')  # chạy trên chữ đã VIẾT HOA (An Phát có mã viết thường, VD pmkp0316)


def _gieo_ma_ncc():
    if not MA_NCC_FILE.exists():
        DATA.mkdir(parents=True, exist_ok=True)
        shutil.copy(APP / 'ma_ncc.default.json', MA_NCC_FILE)


def _doc_tho():
    try:
        return json.loads(MA_NCC_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def doc_ma_ncc():
    """{mã hàng NCC (viết hoa): mã sản phẩm}. File: {mã: {sp, ncc, ten_ncc, link, cap_nhat}} (bản cũ: {mã: sp})."""
    return {k.upper(): (v['sp'] if isinstance(v, dict) else v) for k, v in _doc_tho().items()}


def nho_ma_ncc(ma, sp, ncc=''):
    ma = (ma or '').upper()
    if ma and sp in M.SAN_PHAM and doc_ma_ncc().get(ma) != sp:
        d = _doc_tho(); cu = d.get(ma) if isinstance(d.get(ma), dict) else {}
        from datetime import date as _d
        d[ma] = {**cu, 'sp': sp, 'ncc': ncc or cu.get('ncc', ''), 'cap_nhat': _d.today().strftime('%d/%m/%Y'), 'ghi_boi': 'nhân viên (sao chép email)'}
        MA_NCC_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')


def _fold(t):
    t = unicodedata.normalize('NFD', t.lower()).replace('đ', 'd')
    return ''.join(c for c in t if unicodedata.category(c) != 'Mn')


# Nhận sản phẩm theo TÊN khi không có part number (VD An Phát: "Phần mềm Microsoft Office Home 202…", mã hàng PMOF0051)
def _dieu_kien(sp):
    ten = _fold(sp['ten'])
    if sp['loai'] == 'office':
        return ['office', 'home'] + (['business'] if 'business' in ten else ['!business'])
    if sp['loai'] == 'm365':
        return ['365', 'family' if 'family' in ten else 'personal']
    if sp['loai'] == 'windows':
        return ['windows', 'home' if 'home' in ten else 'pro']
    phien = next(w for w in ('small office', 'premium', 'plus', 'standard') if w in ten)
    so = re.search(r'(\d+)\s*(thiet bi|may tinh)', _fold(sp.get('pham_vi', '')))
    return ['kaspersky', phien] + ([f'#{so.group(1)}'] if so else [])


def _khop(dk, f):
    for d in dk:
        if d.startswith('!'):
            if re.search(rf'\b{d[1:]}\b', f): return False
        elif d.startswith('#'):
            if not re.search(rf'\b{d[1:]}\s*(thiet bi|may|devices?|dvc|pc|user)', f): return False
        elif not re.search(rf'\b{re.escape(d)}', f):
            return False
    return True


def nhan_theo_ten(t):
    """→ (mã sản phẩm, cảnh báo). Nhiều phiên bản cùng tên → chọn theo gợi ý ESD / FPP / Medialess / OEM / USB, mặc định key điện tử (ESD)."""
    f = _fold(t)
    ung = [k for k, v in M.SAN_PHAM.items() if _khop(_dieu_kien(v), f)]
    if not ung:
        return '', ''
    if len(ung) == 1:
        return ung[0], ''
    goi_y = [(r'\b(oem|dsp|dvd)\b', 'OEM'), (r'\busb\b', 'USB'), (r'\b(fpp|box)\b|hop', 'FPP'), (r'medialess', 'Medialess'),
             (r'\b(esd|online|dwnld|download)\b|key dien tu', 'ESD')]
    for mau, tu in goi_y:
        if re.search(mau, f):
            hop = [k for k in ung if tu.lower() in M.SAN_PHAM[k]['giay_phep'].lower()]
            if hop:
                return hop[0], ''
    esd = [k for k in ung if 'esd' in M.SAN_PHAM[k]['giay_phep'].lower()] or ung
    cac = ', '.join(f"{k} ({M.SAN_PHAM[k]['giay_phep']})" for k in ung)
    return esd[0], f'Tên hàng khớp nhiều phiên bản: {cac}. Em chọn bản key điện tử – nếu là bản hộp / Medialess / OEM anh chọn lại.'


def phan_tich(text):
    """Lấy key, mã sản phẩm, tên hàng, số lượng từ email / ảnh nhà cung cấp. Không lưu key."""
    t = text.replace(' ', ' ')
    t = re.sub(r'(?<=[A-Za-z0-9])[ \t]*[–—−‐-][ \t]*(?=[A-Za-z0-9]{5}\b)', '-', t)   # chỉ nối TRÊN CÙNG MỘT DÒNG (không ghép key qua dòng)   # OCR: gạch dài / khoảng trắng giữa các nhóm key
    T = t.upper()
    keys5 = list(dict.fromkeys(RE_KEY5.findall(T)))
    keys4 = [k for k in dict.fromkeys(RE_KEY4.findall(T)) if not any(k in x for x in keys5)]
    cut = [k for k in dict.fromkeys(RE_KEY_CUT.findall(T)) if not any(k.rstrip('-') in x for x in keys5 + keys4)]
    m_ten = re.search(r'(t[êe]n\s*h[àa]ng(\s*h[óoò][áa]?)?|s[ảa]n\s*ph[ẩa]m|product)\s*:\s*(.+)', t, re.I)
    ten_ncc = m_ten.group(m_ten.lastindex).strip() if m_ten else ''
    m_sl = re.search(r'(s[ốôo]\s*l[ưu][ợơo]ng|qty|quantity)\s*:?\s*(\d+)', t, re.I)
    sl = int(m_sl.group(2)) if m_sl else None
    parts = [p for p in RE_PART.findall(ten_ncc or t) if not any(p in k for k in keys5 + keys4)]
    part = parts[0] if parts else ''
    ma_ncc = next((m for m in RE_MA_NCC.findall(T) if m in doc_ma_ncc()), '') or next((m for m in RE_MA_NCC.findall(T) if m.startswith('PM')), '')
    kq = {'sl': sl, 'ten_ncc': ten_ncc, 'part': part, 'sp': '', 'ma_ncc': ma_ncc, 'canh_bao': []}
    if part in M.SAN_PHAM:
        kq['sp'] = part
    elif ma_ncc in doc_ma_ncc():
        kq['sp'] = doc_ma_ncc()[ma_ncc]; kq['theo'] = f'mã hàng nhà cung cấp {ma_ncc} (đã ghi nhớ)'
    else:
        sp, cb = nhan_theo_ten(ten_ncc or t)
        if sp and not part:
            kq['sp'] = sp; kq['theo'] = 'tên hàng'
            if cb: kq['canh_bao'].append(cb)
        else:
            nguon = ten_ncc or t
            kq.update(loai=_loai(nguon), ten=_sach_ten(ten_ncc) if ten_ncc else '', ma=part, giay_phep=_giay_phep(nguon))
            if part or kq.get('ten'):
                kq['canh_bao'].append(f'Sản phẩm {part or kq["ten"]} chưa có trong danh mục – đã điền tự động, anh kiểm lại tên và loại giấy phép.')
            else:
                kq['canh_bao'].append('Không nhận ra sản phẩm – anh chọn sản phẩm ở danh sách bên dưới.')
    loai = M.SAN_PHAM.get(kq['sp'], {}).get('loai') or kq.get('loai')
    # Microsoft: key 5 nhóm; Kaspersky: 4 nhóm
    keys = keys5 if loai != 'kaspersky' else (keys4 or keys5)
    if loai != 'kaspersky':
        cut += [k + '-' for k in keys4]
    kq['keys'] = keys
    if cut:
        kq['canh_bao'].append('Key chưa đủ nhóm (bị cắt hoặc che): ' + ', '.join(c.rstrip('-') + '-…' for c in cut) + ' – anh lấy key đầy đủ từ email gốc.')
    if not keys and not cut:
        kq['canh_bao'].append('Không tìm thấy key nào trong nội dung đã dán.')
    elif keys and sl is not None and sl != len(keys):
        kq['canh_bao'].append(f'Số lượng ghi {sl} nhưng tìm thấy {len(keys)} key – anh kiểm lại.')
    return kq


# ---------- Tách dữ liệu: nhiều nhà cung cấp, nhiều sản phẩm trong một lần dán ----------
NCC = [(r'anphat', 'An Phát'), (r'ankhang', 'An Khang'), (r'phongvu', 'Phong Vũ'), (r'digiworld|dgw', 'Digiworld'),
       (r'synnex|fpt', 'Synnex FPT'), (r'tinhvan', 'Tinh Vân'), (r'nhattin', 'Nhất Tín')]


def nha_cung_cap(t):
    f = _fold(t)
    for mau, ten in NCC:
        if re.search(mau, f):
            return ten
    m = [d for d in re.findall(r'@([a-z0-9-]+)\.(?:com|vn|net)', f) if d not in ('gmail', 'yahoo', 'outlook', 'hotmail', 'laptopaz', 'laptopaz2025')]
    return m[0] if m else ''


TU_SP = re.compile(r'office|365|windows|kaspersky|m365', re.I)


def _moc(dong, map_ncc):
    """Dòng này có nhắc tới sản phẩm nào không → khoá nhận diện (mã SP / part / mã NCC) hoặc None."""
    U = dong.upper()
    if RE_KEY5.search(U) or RE_KEY4.search(U):
        U = RE_KEY4.sub(' ', RE_KEY5.sub(' ', U))           # bỏ phần key trước khi dò mã
    for m in RE_MA_NCC.findall(U):
        if m in map_ncc:
            return map_ncc[m]
    for p in RE_PART.findall(U):
        return p
    if TU_SP.search(dong):
        sp, _ = nhan_theo_ten(dong)
        return sp or None
    return None


def tach(text, nguon='văn bản'):
    """Tách một lần dán (email / ảnh) thành danh sách mục [{sp, keys, sl, …}] – mỗi sản phẩm một mục, key gán theo sản phẩm đứng trước gần nhất."""
    t = text.replace(' ', ' ')
    t = re.sub(r'(?<=[A-Za-z0-9])[ \t]*[–—−‐-][ \t]*(?=[A-Za-z0-9]{5}\b)', '-', t)   # chỉ nối TRÊN CÙNG MỘT DÒNG (không ghép key qua dòng)
    t = re.sub(r'\b(PM[A-Za-z]{2})([0-9Oo]{4})\b', lambda m: m[1] + m[2].replace('O', '0').replace('o', '0'), t)   # OCR: PMOFO051 → PMOF0051
    map_ncc = doc_ma_ncc()
    nhom, thu_tu, truoc, hien = {}, [], [], None
    for dong in t.splitlines():
        k = _moc(dong, map_ncc)
        if k:
            if k not in nhom:
                nhom[k] = []; thu_tu.append(k)
            hien = k
        (nhom[hien] if hien else truoc).append(dong)
    ncc = nha_cung_cap(t)
    if len(thu_tu) <= 1:                                   # một sản phẩm (hoặc không nhận ra) → phân tích cả khối
        muc = [phan_tich(t)]
    else:
        muc = []
        for k in thu_tu:
            m = phan_tich('\n'.join(nhom[k]))
            if not m.get('sp') and k in M.SAN_PHAM:
                m['sp'] = k
            muc.append(m)
        # key nằm trước mọi sản phẩm (VD An Phát: key ở đầu email, bảng hàng ở dưới)
        con = phan_tich('\n'.join(truoc))
        roi = con['keys']
        if roi:
            trong = [m for m in muc if not m['keys']]
            if len(trong) == 1:
                trong[0]['keys'] = roi; trong[0]['canh_bao'] = [c for c in trong[0]['canh_bao'] if 'Không tìm thấy key' not in c]
            else:
                for m in muc:
                    m['canh_bao'].append('Có key nằm ngoài phần sản phẩm, chưa rõ thuộc mục nào: ' + ', '.join(roi))
    for m in muc:
        m['ncc'] = ncc
        m['ghi_chu'] = ['Key đọc từ ảnh – nhân viên đối chiếu nhanh với ảnh gốc trước khi gửi.'] if (nguon == 'ảnh' and m.get('keys')) else []
    return {'ncc': ncc, 'nguon': nguon, 'muc': muc}


def danh_muc():
    return [{'ma': k, 'loai': v['loai'], 'ten': v['ten'], 'gp': v['giay_phep'], 'pv': v.get('pham_vi', '')} for k, v in M.SAN_PHAM.items()]


TRANG = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Gửi key bản quyền – LaptopAZ</title>
<style>
:root{--xanh:#1f6fc4;--chu:#1d1d1f;--phu:#6e6e73;--ke:#e5e5ea;--nen:#f5f5f7;--the:#fff;--ok:#1e8e3e}
*{box-sizing:border-box}
body{margin:0;background:var(--nen);color:var(--chu);font:14px/1.5 'Segoe UI',-apple-system,BlinkMacSystemFont,Roboto,Arial,sans-serif}
header{background:var(--the);border-bottom:1px solid var(--ke);padding:12px 20px;display:flex;align-items:center;gap:12px}
header b{font-size:16px} header span{color:var(--phu)}
main{display:grid;grid-template-columns:380px 1fr;gap:16px;padding:16px;height:calc(100vh - 53px)}
@media (max-width:900px){main{grid-template-columns:1fr;height:auto}}
.cot{background:var(--the);border:1px solid var(--ke);border-radius:12px;padding:16px;overflow:auto}
label{display:block;font-weight:600;margin:12px 0 4px} label small{font-weight:400;color:var(--phu)}
input,select,textarea{width:100%;min-height:38px;padding:8px 10px;border:1px solid #d2d2d7;border-radius:8px;font:inherit;background:#fff;color:var(--chu)}
input[type=date]{cursor:pointer}
input[type=date]::-webkit-calendar-picker-indicator{cursor:pointer;opacity:.75;padding:2px}
textarea{font-family:'SF Mono',Consolas,Menlo,monospace;min-height:84px;resize:vertical}
.dan{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:9px 12px;border:1.5px dashed #c7c7cc;border-radius:10px;background:#fbfbfd;color:var(--chu);font:600 14px/1.2 inherit;font-family:inherit;cursor:pointer;transition:.15s}
.dan:hover,.dan:focus,.dan.keo{border-color:var(--xanh);background:#f2f7fd;outline:none}
.dan.dang{opacity:.6;pointer-events:none}
.dan-icon{flex:none;color:var(--xanh)}
hr{border:0;border-top:1px solid var(--ke);margin:16px 0 4px}
.ptkq{margin-top:10px;border:1px solid var(--ke);border-left-width:4px;border-radius:10px;background:#fff;font-size:13px;overflow:hidden}
.ptkq.ok{border-color:#b7dfc3;border-left-color:#1e8e3e}
.ptkq.canh{border-color:#f3d999;border-left-color:#f0a500}
.ptkq.loi{border-color:#f5c2bf;border-left-color:#c5221f}
.ptkq.dang{border-left-color:var(--xanh)}
.kq-dau{display:flex;gap:10px;align-items:center;padding:10px 12px}
.ok .kq-dau{background:#e6f4ea}.canh .kq-dau{background:#fef7e0}.loi .kq-dau{background:#fce8e6}.dang .kq-dau{background:#eaf2fc}
.kq-icon{flex:none;width:24px;height:24px;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#fff;font:700 13px/1 inherit;font-family:inherit}
.ok .kq-icon{background:#1e8e3e}.canh .kq-icon{background:#f0a500}.loi .kq-icon{background:#c5221f}.dang .kq-icon{background:var(--xanh)}
.kq-dau b{display:block;font-size:14px}.ok .kq-dau b{color:#137333}.canh .kq-dau b{color:#7a5200}.loi .kq-dau b{color:#a50e0e}.dang .kq-dau b{color:var(--xanh)}
.kq-dau small{color:var(--phu);font-size:12px}
.kq-bang{display:grid;grid-template-columns:86px 1fr;gap:6px 10px;margin:0;padding:10px 12px}
.kq-bang dt{color:var(--phu)}.kq-bang dd{margin:0;font-weight:600;color:var(--chu)}
.kq-bang dd span{display:block;font-weight:400;color:var(--phu);font-size:12px}
.kq-bang dd span.tag{display:inline-block;font-weight:600;font-size:11px}
.tag{display:inline-block;margin-left:6px;padding:1px 8px;border-radius:10px;font-size:11px;font-weight:600;vertical-align:1px}
.kq-bang dd span.tag.ok{background:#e6f4ea;color:#137333}.kq-bang dd span.tag.canh{background:#fef7e0;color:#7a5200}
.kq-cb{margin:0;padding:0 12px 10px 30px;color:#7a5200}.kq-cb li+li{margin-top:4px}
.loi .kq-cb{color:#a50e0e}
.kq-gc{padding:0 12px 10px;color:var(--phu);font-size:12px}
.muc{display:flex;flex-direction:column;gap:6px;padding:0 12px 10px}
.muc button{text-align:left;background:#fff;color:var(--chu);border:1px solid #d2d2d7;border-radius:8px;padding:7px 10px;font-weight:500;font-size:13px}
.muc button.on{border-color:var(--xanh);box-shadow:0 0 0 2px #cfe2f8}
.muc button.xong{color:#137333}
.gp{background:var(--nen);border-radius:8px;padding:8px 10px;color:var(--phu);font-size:13px;margin-top:6px}
.hai{display:grid;grid-template-columns:1fr 1fr;gap:8px}
details{margin-top:12px} summary{cursor:pointer;color:var(--xanh);font-weight:600}
.nut{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
button{border:1px solid var(--xanh);background:var(--xanh);color:#fff;border-radius:20px;padding:9px 16px;font:600 14px inherit;font-family:inherit;cursor:pointer}
button.phu{background:#fff;color:var(--xanh)}
button:disabled{opacity:.45;cursor:not-allowed}
#tb{margin-top:10px;min-height:20px;color:var(--ok);font-weight:600}
#tb.loi{color:#c5221f}
.xem{display:flex;flex-direction:column;padding:0}
.xem .thanh{padding:10px 16px;border-bottom:1px solid var(--ke);display:flex;gap:12px;align-items:center;flex-wrap:wrap}
.xem .thanh .tieude{flex:1;min-width:200px;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.seg button{background:#fff;color:var(--chu);border-color:#d2d2d7;padding:5px 12px;font-weight:500}
.seg button.on{background:var(--chu);color:#fff;border-color:var(--chu)}
.khung{flex:1;display:flex;justify-content:center;background:var(--nen);overflow:auto}
iframe{border:0;width:100%;height:100%;min-height:600px;background:var(--nen);transition:width .2s}
iframe.dt{width:390px;border-left:1px solid var(--ke);border-right:1px solid var(--ke)}
</style></head>
<body>
<header><b>Gửi key bản quyền</b><span>Soạn email chuẩn → sao chép → dán vào Gmail. Key không được lưu lại.</span></header>
<main>
 <section class="cot">
  <button type="button" id="dan" class="dan" title="Dán email hoặc ảnh nhà cung cấp từ clipboard (hoặc Cmd+V, kéo thả ảnh)"><svg class="dan-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1"/><path d="M9 14l2 2 4-4"/></svg>Paste ở đây!</button>
  <div id="ptkq" class="ptkq" hidden></div>
  <hr>
  <label>Sản phẩm</label>
  <select id="sp"></select>
  <div class="gp" id="gp"></div>

  <div id="tudo" hidden>
   <div class="hai"><div><label>Loại</label><select id="loai"><option value="office">Office</option><option value="m365">Microsoft 365</option><option value="windows">Windows</option><option value="kaspersky">Kaspersky</option></select></div>
   <div><label>Mã hãng</label><input id="ma" placeholder="EP2-06604"></div></div>
   <label>Tên phần mềm</label><input id="ten" placeholder="Office Home & Business 2024">
   <label>Loại giấy phép</label><input id="giay_phep" placeholder="Vĩnh viễn – Retail (ESD)">
  </div>

  <label>Key <small>(mỗi key một dòng)</small></label>
  <textarea id="keys" placeholder="XXXXX-XXXXX-XXXXX-XXXXX-XXXXX" spellcheck="false" autocomplete="off"></textarea>
  <label>Ngày cấp</label><input id="ngay" type="date" required>
  <label>Tên khách <small>(bỏ trống = Quý khách)</small></label><input id="khach" placeholder="Anh/Chị Nguyễn Văn A">


  <div class="nut">
   <button id="bEmail">Sao chép email</button>
   <button id="bMoi" class="phu">Đơn mới</button>
  </div>
  <div id="tb"></div>
 </section>

 <section class="cot xem">
  <div class="thanh"><span class="tieude" id="tieude"></span>
   <span class="seg"><button id="vPC" class="on">Máy tính</button> <button id="vDT">Điện thoại</button></span></div>
  <div class="khung"><iframe id="xem" title="Xem trước email"></iframe></div>
 </section>
</main>
<script>
const $ = id => document.getElementById(id);
const DM = __DM__;
let kq = null, hen = null, maNCC = '';
// ô ngày dạng lịch (yyyy-mm-dd) – mặc định hôm nay; gửi đi dạng dd/mm/yyyy
const homNay = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
const ddmmyyyy = v => v ? v.split('-').reverse().join('/') : '';
const tenLoai = {office: 'Office 2024', m365: 'Microsoft 365', windows: 'Windows 11', kaspersky: 'Kaspersky'};
// danh sách sản phẩm theo nhóm
for (const l of Object.keys(tenLoai)) {
  const g = document.createElement('optgroup'); g.label = tenLoai[l];
  DM.filter(x => x.loai === l).forEach(x => { const o = document.createElement('option'); o.value = x.ma; o.textContent = `${x.ten} – ${x.gp} (${x.ma})`; g.appendChild(o); });
  $('sp').appendChild(g);
}
const k = document.createElement('option'); k.value = 'khac'; k.textContent = 'Sản phẩm khác (tự nhập)…'; $('sp').appendChild(k);
const o0 = document.createElement('option'); o0.value = ''; o0.textContent = '— Lựa chọn sản phẩm —'; $('sp').prepend(o0); $('sp').value = '';
$('ngay').value = homNay();

function hienGP() {
  const v = $('sp').value, x = DM.find(d => d.ma === v);
  $('tudo').hidden = v !== 'khac';
  $('gp').hidden = !v;
  $('gp').innerHTML = x ? `<b>${x.gp}</b>${x.pv ? '<br>' + x.pv : ''}` : 'Nhập loại, tên, mã hãng và loại giấy phép bên dưới.';
}
function duLieu() {
  const d = {}; for (const id of ['sp', 'loai', 'ma', 'ten', 'giay_phep', 'keys', 'ngay', 'khach']) d[id] = $(id).value;
  d.ngay = ddmmyyyy(d.ngay);
  d.chon = !!$('sp').value;
  if ($('sp').value !== 'khac') { d.loai = ''; d.ma = ''; d.ten = ''; d.giay_phep = ''; }
  if ($('sp').value === 'khac') d.sp = '';
  return d;
}
async function capNhat() {
  const r = await fetch('/tao', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(duLieu())});
  kq = await r.json();
  $('xem').srcdoc = kq.html; $('tieude').textContent = kq.subject;
  $('bEmail').disabled = !kq.du;
  $('bEmail').title = kq.du ? '' : 'Cần chọn sản phẩm và nhập key';
}
const doi = () => { clearTimeout(hen); hen = setTimeout(capNhat, 250); };
document.querySelectorAll('input,select,textarea').forEach(el => el.addEventListener('input', () => { if (el.id === 'sp') hienGP(); doi(); }));

function bao(t, loi) { $('tb').textContent = t; $('tb').className = loi ? 'loi' : ''; clearTimeout(bao.h); bao.h = setTimeout(() => $('tb').textContent = '', 4000); }
async function chepHTML(html, txt) {
  // lấy phần <body> để dán vào Gmail giữ nguyên định dạng
  const body = (html.match(/<body[^>]*>([\s\S]*)<\/body>/i) || [, html])[1];
  await navigator.clipboard.write([new ClipboardItem({'text/html': new Blob([body], {type: 'text/html'}), 'text/plain': new Blob([txt], {type: 'text/plain'})})]);
}
$('bEmail').onclick = async () => { try { await capNhat(); await chepHTML(kq.html, kq.txt);
    if (maNCC && $('sp').value && $('sp').value !== 'khac') fetch('/nho', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ma_ncc: maNCC, sp: $('sp').value, ncc})});
    if (ds.length > 1) { ds[chon].xong = true; const t = chon; chonMuc(t); }
    bao('Đã sao chép email' + (ds.length > 1 ? ` mục ${chon + 1}/${ds.length}` : '') + ' – dán vào khung soạn Gmail (Cmd+V).'); } catch (e) { bao('Không sao chép được: ' + e.message, 1); } };
$('bMoi').onclick = () => { for (const id of ['keys', 'khach']) $(id).value = ''; $('sp').value = ''; hienGP(); $('ptkq').hidden = true; ds = []; $('ngay').value = homNay(); capNhat(); $('keys').focus(); bao('Đã xoá key của đơn trước.'); };
$('vPC').onclick = () => { $('xem').classList.remove('dt'); $('vPC').classList.add('on'); $('vDT').classList.remove('on'); };
$('vDT').onclick = () => { $('xem').classList.add('dt'); $('vDT').classList.add('on'); $('vPC').classList.remove('on'); };
let ds = [], chon = 0, ncc = '', nguonDoc = '';
function apDung(k) {
  if (k.loi) { $('ptkq').innerHTML = `<div class="kq-dau"><div class="kq-icon">×</div><div><b>Không đọc được</b><small>${k.loi}</small></div></div>`; $('ptkq').className = 'ptkq loi'; $('ptkq').hidden = false; return; }
  ds = k.muc || [k]; ncc = k.ncc || ''; nguonDoc = k.nguon || 'văn bản';
  chonMuc(0);
}
function tenMuc(m) { const x = DM.find(v => v.ma === m.sp); return x ? `${x.ten} (${x.ma})` : (m.ten || 'chưa nhận ra') + (m.ma ? ` (${m.ma})` : ''); }
function chonMuc(i) {
  chon = i; const k = ds[i];
  if (k.sp) { $('sp').value = k.sp; }
  else if (k.ten || k.ma) { $('sp').value = 'khac'; $('loai').value = k.loai || 'office'; $('ten').value = k.ten || ''; $('ma').value = k.ma || ''; $('giay_phep').value = k.giay_phep || ''; }
  $('keys').value = (k.keys || []).join('\n');
  maNCC = k.ma_ncc || '';
  hienGP();
  const x = DM.find(v => v.ma === k.sp);
  const coSP = !!(x || k.ten), soKey = k.keys.length, khopSL = k.sl == null || k.sl === soKey;
  const trangThai = !coSP || !soKey ? 'loi' : (k.canh_bao.length || !khopSL ? 'canh' : 'ok');
  const tieuDe = {ok: 'Dữ liệu hợp lệ', canh: 'Cần kiểm tra lại', loi: 'Chưa đủ dữ liệu'}[trangThai];
  const icon = {ok: '✓', canh: '!', loi: '×'}[trangThai];
  const phu = [`Đọc từ ${nguonDoc}`, ncc && `Nhà cung cấp: ${ncc}`, ds.length > 1 && `Mục ${i + 1}/${ds.length}`].filter(Boolean).join(' · ');
  const sp = x ? `${x.ten}<span>${x.ma} · ${x.gp}</span>` : (k.ten ? `${k.ten}<span>${k.ma || 'chưa có mã'} · sản phẩm ngoài danh mục</span>` : 'Chưa nhận ra');
  const tagKey = !soKey ? '' : (k.sl == null ? '' : `<span class="tag ${khopSL ? 'ok' : 'canh'}">${khopSL ? 'Khớp số lượng' : 'Lệch số lượng ' + k.sl}</span>`);
  let h = `<div class="kq-dau"><div class="kq-icon">${icon}</div><div><b>${tieuDe}</b><small>${phu}</small></div></div>`;
  if (ds.length > 1) h += '<div class="muc">' + ds.map((m, j) => `<button type="button" class="${j === i ? 'on' : ''}${m.xong ? ' xong' : ''}" data-i="${j}">${m.xong ? '✓ ' : ''}${j + 1}. ${tenMuc(m)} – ${m.keys.length} key</button>`).join('') + '</div>';
  h += `<dl class="kq-bang"><dt>Sản phẩm</dt><dd>${sp}</dd><dt>Key</dt><dd>${soKey} key${tagKey}</dd>${k.theo ? `<dt>Nhận theo</dt><dd style="font-weight:400">${k.theo}</dd>` : ''}</dl>`;
  if (k.canh_bao.length) h += '<ul class="kq-cb">' + k.canh_bao.map(c => `<li>${c}</li>`).join('') + '</ul>';
  if ((k.ghi_chu || []).length) h += '<div class="kq-gc">' + k.ghi_chu.join('<br>') + '</div>';
  $('ptkq').innerHTML = h; $('ptkq').className = 'ptkq ' + trangThai; $('ptkq').hidden = false;
  $('ptkq').querySelectorAll('.muc button').forEach(b => b.onclick = () => chonMuc(+b.dataset.i));
  capNhat();
}
async function guiChu(text) {
  const r = await fetch('/phan_tich', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
  apDung(await r.json());
}
async function guiAnh(file) {
  $('dan').classList.add('dang'); $('ptkq').innerHTML = '<div class="kq-dau"><div class="kq-icon">…</div><div><b>Đang đọc chữ trong ảnh</b><small>Nhận dạng bằng Apple Vision trên máy</small></div></div>'; $('ptkq').className = 'ptkq dang'; $('ptkq').hidden = false;
  try { const r = await fetch('/ocr', {method: 'POST', headers: {'Content-Type': file.type || 'image/png'}, body: file}); apDung(await r.json()); }
  finally { $('dan').classList.remove('dang'); }
}
async function xuLy(dt) {
  const anh = [...(dt.items || [])].find(i => i.kind === 'file' && i.type.startsWith('image/'));
  const f = anh ? anh.getAsFile() : [...(dt.files || [])].find(f => f.type.startsWith('image/'));
  if (f) return guiAnh(f);
  const text = dt.getData('text/plain');
  if (text && text.trim()) return guiChu(text);
  apDung({loi: 'Không có chữ hoặc ảnh trong nội dung vừa dán.'});
}
$('dan').addEventListener('click', async () => {
  // bấm = dán thẳng từ clipboard (ảnh hoặc chữ)
  try {
    for (const it of await navigator.clipboard.read()) {
      const anh = it.types.find(t => t.startsWith('image/'));
      if (anh) return guiAnh(await it.getType(anh));
      if (it.types.includes('text/plain')) { const t = await (await it.getType('text/plain')).text(); if (t.trim()) return guiChu(t); }
    }
    apDung({loi: 'Clipboard đang trống – hãy sao chép email hoặc ảnh trước.'});
  } catch (e) {
    apDung({loi: 'Trình duyệt chưa cho đọc clipboard – bấm "Cho phép" hoặc nhấn Cmd+V.'});
  }
});
document.addEventListener('paste', e => {
  // dán ở bất kỳ đâu ngoài các ô nhập → coi như dán vào vùng Paste
  if (e.target !== $('dan') && e.target.closest && e.target.closest('input,textarea,select')) return;
  e.preventDefault(); xuLy(e.clipboardData);
});
['dragenter', 'dragover'].forEach(ev => $('dan').addEventListener(ev, e => { e.preventDefault(); $('dan').classList.add('keo'); }));
['dragleave', 'drop'].forEach(ev => $('dan').addEventListener(ev, e => { e.preventDefault(); $('dan').classList.remove('keo'); }));
$('dan').addEventListener('drop', e => xuLy(e.dataTransfer));
hienGP(); capNhat();
</script>
</body></html>'''


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # không ghi log (tránh lộ key)
        pass

    def gui(self, ma, kieu, body):
        b = body.encode('utf-8')
        self.send_response(ma)
        self.send_header('Content-Type', kieu + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def dung_mk(self):
        if BO_QUA_LOCAL and self.client_address[0] in ('127.0.0.1', '::1') and not self.headers.get('X-Forwarded-For') \
                and not self.headers.get('Cf-Connecting-Ip'):
            return True
        h = self.headers.get('Authorization') or ''
        if h.startswith('Basic '):
            try:
                u, _, p = base64.b64decode(h[6:]).decode('utf-8').partition(':')
                if u == NGUOI_DUNG and hmac.compare_digest(p, MAT_KHAU):
                    return True
            except Exception:
                pass
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="LaptopAZ - Gui key", charset="UTF-8"')
        self.send_header('Content-Length', '0'); self.end_headers()
        return False

    def do_GET(self):
        if self.path == '/healthz':
            return self.gui(200, 'text/plain', 'ok')
        if not self.dung_mk():
            return
        if self.path in ('/', '/index.html'):
            return self.gui(200, 'text/html', TRANG.replace('__DM__', json.dumps(danh_muc(), ensure_ascii=False)))
        self.gui(404, 'text/plain', 'Không có')

    def do_POST(self):
        if not self.dung_mk():
            return
        if self.path == '/ocr':
            n = int(self.headers.get('Content-Length') or 0)
            if not n or n > 20_000_000:
                return self.gui(413, 'text/plain', 'Ảnh quá lớn')
            try:
                kq = tach(ocr(self.rfile.read(n)), 'ảnh')
                return self.gui(200, 'application/json', json.dumps(kq, ensure_ascii=False))
            except Exception as ex:
                return self.gui(500, 'application/json', json.dumps({'loi': f'Không đọc được ảnh: {ex}'}, ensure_ascii=False))
        if self.path == '/nho':
            n = int(self.headers.get('Content-Length') or 0)
            d = json.loads(self.rfile.read(min(n, 10_000)) or b'{}')
            nho_ma_ncc((d.get('ma_ncc') or '')[:20], d.get('sp') or '', (d.get('ncc') or '')[:40])
            return self.gui(200, 'application/json', '{"ok":true}')
        if self.path == '/phan_tich':
            n = int(self.headers.get('Content-Length') or 0)
            if n > 100_000:
                return self.gui(413, 'text/plain', 'Quá lớn')
            d = json.loads(self.rfile.read(n) or b'{}')
            return self.gui(200, 'application/json', json.dumps(tach(d.get('text') or ''), ensure_ascii=False))
        if self.path != '/tao':
            return self.gui(404, 'text/plain', 'Không có')
        n = int(self.headers.get('Content-Length') or 0)
        if n > 100_000:
            return self.gui(413, 'text/plain', 'Quá lớn')
        try:
            d = json.loads(self.rfile.read(n) or b'{}')
            self.gui(200, 'application/json', json.dumps(tao(d), ensure_ascii=False))
        except Exception as ex:
            self.gui(400, 'application/json', json.dumps({'loi': str(ex)}, ensure_ascii=False))


if __name__ == '__main__':
    if not MAT_KHAU:
        sys.exit('Thiếu EMAIL_KEY_PASS (đặt trong .env hoặc biến môi trường) – không chạy khi chưa có mật khẩu.')
    _gieo_ma_ncc()
    print(f'AZ Email: http://{HOST}:{PORT}  · OCR: {_bo_doc()}  · dữ liệu: {DATA}  (Ctrl+C để dừng)', flush=True)
    ThreadingHTTPServer((HOST, PORT), H).serve_forever()
