import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io, os, base64, cv2, numpy as np
import requests
from bs4 import BeautifulSoup
from pyzbar.pyzbar import decode as pyzbar_decode

st.set_page_config(page_title="VietQR BIDV", page_icon="assets/bidvfa.png", layout="centered")
st.markdown(
    """
    <style>
    /* Xoá khoảng trắng trên cùng */
    .block-container {
        padding-top: 0rem;
    }
    header[data-testid="stHeader"] {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True
)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
FONT_PATH = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
FONT_LABELPATH = os.path.join(ASSETS_DIR, "RobotoCondensed-Regular.ttf")
BG_PATHFIX = os.path.join(ASSETS_DIR, "backgroundfix.png")
BG_PATH = os.path.join(ASSETS_DIR, "background.png")
BG_THAI_PATH = os.path.join(ASSETS_DIR, "backgroundthantai.png")
BG_LOA_PATH = os.path.join(ASSETS_DIR, "backgroundloa.png")
BG_TINGBOX_PATH = os.path.join(ASSETS_DIR, "tingbox.png")

# ======== QR Logic Functions ========
def clean_amount_input(raw_input):
    if not raw_input:
        return ""
    try:
        # Xử lý định dạng: "1.000.000,50" => "1000000.50"
        cleaned = raw_input.replace(".", "").replace(",", ".")
        value = float(cleaned)
        return str(int(value))  # Lấy phần nguyên
    except ValueError:
        return None
        
def format_tlv(tag, value): return f"{tag}{len(value):02d}{value}"
def sanitize_input(text):
    return ''.join(text.split())

def crc16_ccitt(data):
    crc = 0xFFFF
    for b in data.encode():
        crc ^= b << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"

def parse_tlv(payload):
    i = 0
    tlv_data = {}
    while i + 4 <= len(payload):
        tag = payload[i:i+2]
        length_str = payload[i+2:i+4]
        try:
            length = int(length_str)
        except ValueError:
            raise ValueError(f"Lỗi TLV: không thể chuyển '{length_str}' thành số nguyên tại vị trí {i}")
        
        value_start = i + 4
        value_end = value_start + length
        if value_end > len(payload):
            raise ValueError(f"Lỗi TLV: độ dài value vượt quá payload tại tag {tag}")
        
        value = payload[value_start:value_end]
        tlv_data[tag] = value
        i = value_end
    return tlv_data


def extract_vietqr_info(payload):
    parsed = parse_tlv(payload)
    info = {"account": "", "bank_bin": "", "name": "", "note": "", "amount": ""}
    if "38" in parsed:
        nested_38 = parse_tlv(parsed["38"])
        if "01" in nested_38:
            acc_info = parse_tlv(nested_38["01"])
            info["bank_bin"] = acc_info.get("00", "")
            info["account"] = acc_info.get("01", "")
    if "62" in parsed:
        add = parse_tlv(parsed["62"])
        info["note"] = add.get("08", "")
    if "54" in parsed:
        info["amount"] = parsed["54"]
    return info

def decode_qr_auto(uploaded_image):
    """
    Thử đọc QR theo thứ tự:
    1️⃣ OpenCV
    2️⃣ ZXing web
    3️⃣ pyzbar (offline)
    Trả về: data (string) và phương pháp đọc
    """
    uploaded_image.seek(0)
    file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
    img_cv2 = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    # ===== 1️⃣ OpenCV =====
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img_cv2)
    if data:
        try:
            if data.startswith("00"):
                _ = parse_tlv(data)  # xác thực TLV
                return data.strip(), "✅ Đọc bằng OpenCV"
        except Exception as e:
            st.info(f"⚠️ OpenCV phát hiện QR nhưng sai chuẩn TLV: {e}")

    # ===== 2️⃣ ZXing Web =====
    try:
        uploaded_image.seek(0)
        img = Image.open(uploaded_image).convert("RGB")
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        img_bytes = buffered.getvalue()
        files = {'f': ('qr.jpg', img_bytes, 'image/jpeg')}
        response = requests.post("https://zxing.org/w/decode", files=files)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            result_tag = soup.find("pre")
            if result_tag:
                zxing_data = result_tag.text.strip()
                try:
                    if zxing_data.startswith("00"):
                        _ = parse_tlv(zxing_data)
                        return zxing_data, "✅ Đọc bằng ZXing"
                except Exception as e:
                    st.info(f"⚠️ ZXing đọc QR nhưng sai chuẩn TLV: {e}")
    except Exception as e:
        st.warning(f"❌ ZXing lỗi: {e}")

    # ===== 3️⃣ pyzbar =====
    try:
        uploaded_image.seek(0)
        img_pil = Image.open(uploaded_image).convert("L")  # grayscale
        results = pyzbar_decode(img_pil)
        if results:
            pyzbar_data = results[0].data.decode("utf-8")
            try:
                if pyzbar_data.startswith("00"):
                    _ = parse_tlv(pyzbar_data)
                    return pyzbar_data, "✅ Đọc bằng pyzbar"
            except Exception as e:
                st.info(f"⚠️ pyzbar đọc QR nhưng sai chuẩn TLV: {e}")
        else:
            st.warning("❌ pyzbar không đọc được QR")
    except Exception as e:
        st.warning(f"❌ pyzbar lỗi: {e}")

    return None, "❌ Không thể đọc QR bằng OpenCV, ZXing hoặc pyzbar. QR được giải mã nhưng không đúng chuẩn VietQR"
    
def round_corners(image, radius):
    rounded = Image.new("RGBA", image.size, (0, 0, 0, 0))
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, image.size[0], image.size[1]], radius=radius, fill=255)
    rounded.paste(image, (0, 0), mask=mask)
    return rounded

def build_vietqr_payload(merchant_id, bank_bin, add_info, amount=""):
    p = format_tlv
    payload = p("00", "01") + p("01", "12")
    acc_info = p("00", bank_bin) + p("01", merchant_id)
    nested_38 = p("00", "A000000727") + p("01", acc_info) + p("02", "QRIBFTTA")
    payload += p("38", nested_38) + p("52", "0000") + p("53", "704")
    if amount: payload += p("54", amount)
    payload += p("58", "VN") + p("62", p("08", add_info)) + "6304"
    return payload + crc16_ccitt(payload)

def generate_qr_with_logo(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((int(img.width*0.15), int(img.height*0.15)))
    img.paste(logo, ((img.width - logo.width) // 2, (img.height - logo.height) // 2), logo)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return buf
def create_qr_with_text(data, acc_name, merchant_id, border=100, usage_ratio=0.85,
                        qr_tip_font_size=60, qr_tip_gap=100):
    # ===== Tạo QR gốc =====
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=0)
    qr.add_data(data)
    qr.make(fit=True)

    # ===== Mở nền =====
    base = Image.open(BG_PATHFIX).convert("RGBA")
    base_w, base_h = base.size

    # ===== Thêm border =====
    new_w, new_h = base_w + border*2, base_h + border*2
    bordered_base = Image.new("RGBA", (new_w, new_h), (255,255,255,255))
    bordered_base.paste(base, (border, border))
    base = bordered_base
    base_w, base_h = base.size
    draw = ImageDraw.Draw(base)

    # ===== Tính block width cho mỗi QR =====
    half_w = (base_w - 2*border)//2
    qr_target_w = int(half_w * usage_ratio)
    qr_target_h = qr_target_w  # QR vuông

    # ===== Hàm giảm font tự động =====
    def get_font(text, max_width, base_size):
        font_size = base_size
        font = ImageFont.truetype(FONT_PATH, font_size)
        text_width = draw.textbbox((0,0), text, font=font)[2]
        while text_width > max_width and font_size > 20:
            font_size -= 2
            font = ImageFont.truetype(FONT_PATH, font_size)
            text_width = draw.textbbox((0,0), text, font=font)[2]
        return font, font_size

    label_font_size = 46
    font_label = ImageFont.truetype(FONT_LABELPATH, label_font_size)
    font_qr_tip = ImageFont.truetype(FONT_PATH, qr_tip_font_size)

    # ===== Vẽ 2 QR + text =====
    for i in range(2):
        # QR resize
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((qr_target_w, qr_target_h))
        # Logo resize và paste vào QR
        logo_resized = Image.open(LOGO_PATH).convert("RGBA")
        logo_w = int(qr_target_w * 0.2)
        logo_h = int(logo_resized.height / logo_resized.width * logo_w)
        logo_resized = logo_resized.resize((logo_w, logo_h))
        qr_img.paste(logo_resized, ((qr_target_w - logo_w)//2, (qr_target_h - logo_h)//2), logo_resized)

        # ===== Tính tổng chiều cao block (QR + text) =====
        total_text_h = 0
        if acc_name and acc_name.strip():
            _, acc_h = get_font(acc_name.upper(), qr_target_w, 40)
            total_text_h += label_font_size + 20 + acc_h
        if merchant_id and merchant_id.strip():
            _, merchant_h = get_font(merchant_id, qr_target_w, 40)
            total_text_h += label_font_size + 20 + merchant_h

        total_block_h = qr_target_h + total_text_h + qr_tip_gap  # khoảng cách tip tùy chỉnh

        # ===== Căn giữa theo chiều dọc =====
        qr_x = border + i*half_w + (half_w - qr_target_w)//2
        qr_y = (base_h - total_block_h)//2 + qr_tip_gap

        # ===== Vẽ QR =====
        base.paste(qr_img, (qr_x, qr_y), qr_img)

        # ===== Vẽ dòng Quét mã QR trên QR, căn giữa QR =====
        qr_tip_text = "Quét mã QR để thanh toán"
        x_tip = qr_x + (qr_target_w - draw.textbbox((0,0), qr_tip_text, font=font_qr_tip)[2]) // 2
        y_tip = qr_y - qr_tip_gap  # khoảng cách từ QR, mặc định 100px
        draw.text((x_tip, y_tip), qr_tip_text, fill=(0,102,102), font=font_qr_tip)

        # ===== Vẽ text dưới QR với nhãn =====
        y_offset = qr_y + qr_target_h + 20  # 20 px dưới QR
        max_text_width = qr_target_w

        if acc_name and acc_name.strip():
            label_acc = "Tên tài khoản:"
            x_label_acc = qr_x + (qr_target_w - draw.textbbox((0,0), label_acc, font=font_label)[2])//2
            draw.text((x_label_acc, y_offset), label_acc, fill="black", font=font_label)
            y_offset += label_font_size + 15
            font_acc, acc_font_size = get_font(acc_name.upper(), max_text_width, 40)
            x_acc = qr_x + (qr_target_w - draw.textbbox((0,0), acc_name.upper(), font=font_acc)[2])//2
            draw.text((x_acc, y_offset), acc_name.upper(), fill=(0,102,102), font=font_acc)
            y_offset += acc_font_size + 35

        if merchant_id and merchant_id.strip():
            label_merchant = "Số tài khoản:"
            x_label_merchant = qr_x + (qr_target_w - draw.textbbox((0,0), label_merchant, font=font_label)[2])//2
            draw.text((x_label_merchant, y_offset), label_merchant, fill="black", font=font_label)
            y_offset += label_font_size + 15
            font_merchant, merchant_font_size = get_font(merchant_id, max_text_width, 40)
            x_merchant = qr_x + (qr_target_w - draw.textbbox((0,0), merchant_id, font=font_merchant)[2])//2
            draw.text((x_merchant, y_offset), merchant_id, fill=(0,102,102), font=font_merchant)

    # ===== Quay 90 độ sang landscape =====
    base = base.rotate(-90, expand=True)

    # ===== Lưu buffer =====
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf

def create_qr_with_background(data, acc_name, merchant_id, store_name, support_name="", support_phone=""):
    # ===== Tạo QR =====
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((540, 540))
    qr_img = round_corners(qr_img, 40)

    # Logo trên QR
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((100, 100))
    qr_img.paste(logo, ((qr_img.width - logo.width)//2, (qr_img.height - logo.height)//2), logo)

    # Nền
    base = Image.open(BG_PATH).convert("RGBA")
    base_w, base_h = base.size
    qr_x, qr_y = 460, 936
    base.paste(qr_img, (qr_x, qr_y), qr_img)

    draw = ImageDraw.Draw(base)

    # Font label
    font_label = ImageFont.truetype(FONT_LABELPATH, 46)

    # Hàm giảm font nếu chữ dài
    def get_font(text, max_width, base_size):
        font_size = base_size
        font = ImageFont.truetype(FONT_PATH, font_size)
        text_width = draw.textbbox((0,0), text, font=font)[2]
        while text_width > max_width and font_size > 12:
            font_size -= 1
            font = ImageFont.truetype(FONT_PATH, font_size)
            text_width = draw.textbbox((0,0), text, font=font)[2]
        return font, font_size

    # ===== Vẽ Tên tài khoản & Số tài khoản giống loa =====
    max_text_width = int(base_w * 0.7)
    y_offset = qr_y + qr_img.height + 130

    if acc_name and acc_name.strip():
        label_acc = "Tên tài khoản:"
        x_label = (base_w - draw.textbbox((0,0), label_acc, font=font_label)[2]) // 2
        draw.text((x_label, y_offset), label_acc, fill="black", font=font_label)
        y_offset += 28 + 30

        font_acc, acc_font_size = get_font(acc_name.upper(), max_text_width, 48)
        x_acc = (base_w - draw.textbbox((0,0), acc_name.upper(), font=font_acc)[2]) // 2
        draw.text((x_acc, y_offset), acc_name.upper(), fill=(0,102,102), font=font_acc)
        y_offset += acc_font_size + 45

    if merchant_id and merchant_id.strip():
        label_merchant = "Số tài khoản:"
        x_label = (base_w - draw.textbbox((0,0), label_merchant, font=font_label)[2]) // 2
        draw.text((x_label, y_offset), label_merchant, fill="black", font=font_label)
        y_offset += 28 + 30

        font_merchant, merchant_font_size = get_font(merchant_id, max_text_width, 46)
        x_merchant = (base_w - draw.textbbox((0,0), merchant_id, font=font_merchant)[2]) // 2
        draw.text((x_merchant, y_offset), merchant_id, fill=(0,102,102), font=font_merchant)
        y_offset += merchant_font_size + 55
    # ===== Hiển thị Cán bộ hỗ trợ 1 dòng, căn trái =====
    padding_left = 70
    padding_bottom = 60
    
    if (support_name and support_name.strip()) or (support_phone and support_phone.strip()):
        # Font chữ
        font_support = ImageFont.truetype(FONT_LABELPATH, 34)
    
        # Nội dung từng phần
        label_text = "Cán bộ hỗ trợ: "
        contact_text = f"{support_name}" if support_name else ""
        label2_text = " - Liên hệ: "
        phone_text = f"{support_phone}" if support_phone else ""
    
        # Tọa độ căn trái, căn dưới
        support_x = padding_left
        support_y = base_h - 32 - padding_bottom  # 32 là font size ước lượng
    
        # Vẽ từng phần
        draw.text((support_x, support_y), label_text, fill=(0,102,102), font=font_support)
        offset_x = support_x + draw.textbbox((0,0), label_text, font=font_support)[2]
    
        draw.text((offset_x, support_y), contact_text, fill=(255,0,0), font=font_support)
        offset_x += draw.textbbox((0,0), contact_text, font=font_support)[2]
    
        draw.text((offset_x, support_y), label2_text, fill=(0,102,102), font=font_support)
        offset_x += draw.textbbox((0,0), label2_text, font=font_support)[2]
    
        draw.text((offset_x, support_y), phone_text, fill=(255,0,0), font=font_support)
        # Store name
        store_font = ImageFont.truetype(FONT_PATH, 70)
        if store_name and store_name.strip():
            cx = lambda t, f: (base.width - draw.textbbox((0,0), t, font=f)[2]) // 2
            draw.text((cx(store_name.upper(), store_font), 265), store_name.upper(), fill="#007C71", font=store_font)

    # Lưu buffer
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf
def create_qr_with_background_thantai(data, acc_name, merchant_id, store_name, support_name="", support_phone=""):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((480, 520))

    # Thêm logo lên QR
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((100, 100))
    qr_img.paste(logo, ((qr_img.width - logo.width)//2, (qr_img.height - logo.height)//2), logo)

    # Mở nền
    base = Image.open(BG_THAI_PATH).convert("RGBA")
    base_w, base_h = base.size
    qr_x, qr_y = 793, 725
    base.paste(qr_img, (qr_x, qr_y), qr_img)

    draw = ImageDraw.Draw(base)

    # Font label
    font_label = ImageFont.truetype(FONT_LABELPATH, 46)

    # Hàm giảm font nếu chữ dài, giới hạn max_width
    def get_font(text, max_width, base_size):
        font_size = base_size
        font = ImageFont.truetype(FONT_PATH, font_size)
        text_width = draw.textbbox((0, 0), text, font=font)[2]
        while text_width > max_width and font_size > 12:
            font_size -= 1
            font = ImageFont.truetype(FONT_PATH, font_size)
            text_width = draw.textbbox((0, 0), text, font=font)[2]
        return font, font_size

    # Tối đa 70% chiều rộng nền
    max_text_width = int(base_w * 0.7)

    # Vẽ Tên tài khoản và Số tài khoản căn giữa nền
    y_offset = qr_y + qr_img.height + 360

    if acc_name and acc_name.strip():
        label_acc = "Tên tài khoản:"
        text_width = draw.textbbox((0,0), label_acc, font=font_label)[2]
        x_label = (base_w - text_width) // 2  # căn giữa nền
        draw.text((x_label, y_offset), label_acc, fill="black", font=font_label)
        y_offset += 28 + 30

        font_acc, acc_font_size = get_font(acc_name.upper(), max_text_width, 48)
        text_width = draw.textbbox((0,0), acc_name.upper(), font=font_acc)[2]
        x_acc = (base_w - text_width) // 2  # căn giữa nền
        draw.text((x_acc, y_offset), acc_name.upper(), fill=(0,102,102), font=font_acc)
        y_offset += acc_font_size + 45

    if merchant_id and merchant_id.strip():
        label_merchant = "Số tài khoản:"
        text_width = draw.textbbox((0,0), label_merchant, font=font_label)[2]
        x_label = (base_w - text_width) // 2  # căn giữa nền
        draw.text((x_label, y_offset), label_merchant, fill="black", font=font_label)
        y_offset += 28 + 30

        font_merchant, merchant_font_size = get_font(merchant_id, max_text_width, 46)
        text_width = draw.textbbox((0,0), merchant_id, font=font_merchant)[2]
        x_merchant = (base_w - text_width) // 2  # căn giữa nền
        draw.text((x_merchant, y_offset), merchant_id, fill=(0,102,102), font=font_merchant)
        y_offset += merchant_font_size + 35
    # ===== Hiển thị Cán bộ hỗ trợ 1 dòng, căn trái =====
    padding_left = 70
    padding_bottom = 60
    
    if (support_name and support_name.strip()) or (support_phone and support_phone.strip()):
        # Font chữ
        font_support = ImageFont.truetype(FONT_LABELPATH, 34)
    
        # Nội dung từng phần
        label_text = "Cán bộ hỗ trợ: "
        contact_text = f"{support_name}" if support_name else ""
        label2_text = " - Liên hệ: "
        phone_text = f"{support_phone}" if support_phone else ""
    
        # Tọa độ căn trái, căn dưới
        support_x = padding_left
        support_y = base_h - 32 - padding_bottom  # 32 là font size ước lượng
    
        # Vẽ từng phần
        draw.text((support_x, support_y), label_text, fill=(0,102,102), font=font_support)
        offset_x = support_x + draw.textbbox((0,0), label_text, font=font_support)[2]
    
        draw.text((offset_x, support_y), contact_text, fill=(255,0,0), font=font_support)
        offset_x += draw.textbbox((0,0), contact_text, font=font_support)[2]
    
        draw.text((offset_x, support_y), label2_text, fill=(0,102,102), font=font_support)
        offset_x += draw.textbbox((0,0), label2_text, font=font_support)[2]
    
        draw.text((offset_x, support_y), phone_text, fill=(255,0,0), font=font_support)
    # Store name
    store_font = ImageFont.truetype(FONT_PATH, 70)
    cx = lambda t, f: (base.width - draw.textbbox((0, 0), t, font=f)[2]) // 2
    draw.text((cx(store_name.upper(), store_font), 265), store_name.upper(), fill="#007C71", font=store_font)

    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf
def create_qr_with_background_loa(data, acc_name, merchant_id, store_name="", support_name="", support_phone=""):
    # ===== Tạo QR =====
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((560, 560))

    # Thêm logo lên QR
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((100, 100))
    qr_img.paste(
        logo,
        ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2),
        logo
    )

    # ===== Mở nền và paste QR =====
    base = Image.open(BG_LOA_PATH).convert("RGBA")
    qr_x, qr_y = 175, 285
    base.paste(qr_img, (qr_x, qr_y), qr_img)

    draw = ImageDraw.Draw(base)

    # ===== Hàm tự động giảm font nếu chữ dài =====
    def get_font(text, max_width, base_size):
        font_size = base_size
        font = ImageFont.truetype(FONT_PATH, font_size)
        text_width = draw.textbbox((0, 0), text, font=font)[2]
        while text_width > max_width and font_size > 20:
            font_size -= 2
            font = ImageFont.truetype(FONT_PATH, font_size)
            text_width = draw.textbbox((0, 0), text, font=font)[2]
        return font, font_size

    # ===== Vẽ Tên tài khoản =====
    max_text_width = qr_img.width
    y_offset = qr_y + qr_img.height + 20
    label_font_size = 28
    font_label = ImageFont.truetype(FONT_LABELPATH, label_font_size)

    if acc_name and acc_name.strip():
        label_acc = "Tên tài khoản:"
        draw.text(
            (qr_x + (qr_img.width - draw.textbbox((0,0), label_acc, font=font_label)[2]) // 2, y_offset),
            label_acc, fill="black", font=font_label
        )
        y_offset += label_font_size + 8

        font_acc, acc_font_size = get_font(acc_name.upper(), max_text_width, 32)
        x_acc = qr_x + (qr_img.width - draw.textbbox((0,0), acc_name.upper(), font=font_acc)[2]) // 2
        draw.text((x_acc, y_offset), acc_name.upper(), fill=(0,102,102), font=font_acc)
        y_offset += acc_font_size + 15

    # ===== Vẽ Số tài khoản =====
    if merchant_id and merchant_id.strip():
        label_merchant = "Số tài khoản:"
        draw.text(
            (qr_x + (qr_img.width - draw.textbbox((0,0), label_merchant, font=font_label)[2]) // 2, y_offset),
            label_merchant, fill="black", font=font_label
        )
        y_offset += label_font_size + 8

        font_merchant, merchant_font_size = get_font(merchant_id, max_text_width, 32)
        x_merchant = qr_x + (qr_img.width - draw.textbbox((0,0), merchant_id, font=font_merchant)[2]) // 2
        draw.text((x_merchant, y_offset), merchant_id, fill=(0,102,102), font=font_merchant)
        y_offset += merchant_font_size + 20

    # ===== Vẽ thông tin cán bộ hỗ trợ (giữ nguyên tọa độ) =====
    support_name_x, support_name_y = 500, 1138
    support_phone_x, support_phone_y = 570, 1175

    if support_name.strip():  # an toàn với string rỗng
        font_support_name = ImageFont.truetype(FONT_LABELPATH, 32)
        draw.text((support_name_x, support_name_y), support_name, fill=(0,102,102), font=font_support_name)

    if support_phone.strip():
        font_support_phone = ImageFont.truetype(FONT_LABELPATH, 32)
        draw.text((support_phone_x, support_phone_y), support_phone, fill=(0,102,102), font=font_support_phone)

    # ===== Luôn return buffer =====
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf

def create_qr_tingbox(data, merchant_id):
    # Tạo QR
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=0
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((460, 460))
    # Thêm logo lên QR
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((100, 100))
    qr_img.paste(
        logo,
        ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2),
        logo
    )
    # Mở nền ảnh có sẵn
    base = Image.open(BG_TINGBOX_PATH).convert("RGBA")

    # Paste QR vào nền, căn giữa theo X và vị trí Y tùy chỉnh
    qr_x = 202
    qr_y = 395  # điều chỉnh tùy ý
    base.paste(qr_img, (qr_x, qr_y), qr_img)

    draw = ImageDraw.Draw(base)

    # Hàm tính font giảm nếu tên quá dài
    def get_font(text, max_width, base_size):
        font_size = base_size
        font = ImageFont.truetype(FONT_PATH, font_size)
        text_width = draw.textbbox((0,0), text, font=font)[2]
        while text_width > max_width and font_size > 12:
            font_size -= 1
            font = ImageFont.truetype(FONT_PATH, font_size)
            text_width = draw.textbbox((0,0), text, font=font)[2]
        return font

    # Vẽ merchant_id dưới QR, căn giữa
    if merchant_id and merchant_id.strip():
        max_text_width = qr_img.width
        font_merchant = get_font(merchant_id, max_text_width, 32)
        text_width = draw.textbbox((0,0), merchant_id, font=font_merchant)[2]
        x_merchant = qr_x + (qr_img.width - text_width) // 2
        y_merchant = qr_y + qr_img.height + 20
        draw.text((x_merchant, y_merchant), merchant_id, fill=(0,102,102), font=font_merchant)

    # Lưu buffer
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf
    
# ==== Giao diện người dùng ====
if os.path.exists(FONT_PATH):
    font_css = f"""
    <style>
    @font-face {{
        font-family: 'RobotoCustom';
        src: url(data:font/ttf;base64,{base64.b64encode(open(FONT_PATH, "rb").read()).decode()}) format('truetype');
    }}
    * {{ font-family: 'RobotoCustom'; }}
    </style>
    """
    st.markdown(font_css, unsafe_allow_html=True)

# Tiêu đề 1: Tên ứng dụng
st.markdown(
    """
    <div style="display: flex; align-items: center; justify-content: left; margin-bottom: 10px;">
        <span style="font-family: Roboto, sans-serif; font-weight: bold; font-size: 22px; color: white;">
            🇻🇳 Tạo ảnh VietQR đẹp chuẩn NAPAS
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# Tiêu đề 2: BIDV Thái Bình + logo
st.markdown(
    """
    <div style="display: flex; align-items: center;">
        <img src="data:image/png;base64,{logo_data}" style="max-height:20px; height:20px; width:auto; margin-right:10px;">
        <span style="font-family: Roboto, sans-serif; font-weight: bold; font-size:20px; color:#007C71;">
            Dành riêng cho BIDV Thái Bình
        </span>
    </div>
    """.format(
        logo_data=base64.b64encode(open("assets/logo_bidv.png", "rb").read()).decode()
    ),
    unsafe_allow_html=True
)


uploaded_result = st.file_uploader("📤 Tải ảnh QR VietQR", type=["png", "jpg", "jpeg"], key="uploaded_file")
if uploaded_result and uploaded_result != st.session_state.get("last_file_uploaded"):
    st.session_state["last_file_uploaded"] = uploaded_result
    qr_text, method = decode_qr_auto(uploaded_result)
    st.write(method)
    if qr_text:
        try:
            info = extract_vietqr_info(qr_text)
            bank_bin = info.get("bank_bin", "")
            bank_map = {
                            "970418": "BIDV",
                            "970436": "Vietcombank",
                            "970415": "VietinBank",
                            "970405": "Agribank",
                            "970422": "MB Bank",
                            "970407": "Techcombank",
                            "970423": "TPBank",
                            "970424": "Shinhan Bank",
                            "970441": "VIB",
                            "970432": "VPBank",
                            "970443": "SHB",
                            "970431": "Eximbank",
                            "970438": "BaoVietBank",
                            "970454": "VietCapitalBank",
                            "970429": "SCB",
                            "970421": "VRB",
                            "970425": "ABBank",
                            "970412": "PVcomBank",
                            "970414": "OceanBank",
                            "970428": "NamABank",
                            "970437": "HDBank",
                            "970433": "VietBank",
                            "970459": "ABBANK",
                            "970448": "OCB",
                            "970409": "BacABank",
                            "970442": "Hong Leong Bank VN",
                            "970430": "PG Bank",
                            "970446": "Co-op Bank",
                            "422589": "CIMB VN",
                            "970434": "Indovina Bank",
                            "970457": "Woori VN",
                            "970458": "UOB VN",
                            "970466": "KEB Hana HCM",
                            "970467": "KEB Hana HN",
                            # Tiếp tục bổ sung nếu cần...
                        }

            if bank_bin != "970418":
                bank_name = bank_map.get(bank_bin, f"Mã BIN {bank_bin}")
                st.error(f"""
                ⚠️ Mã QR này thuộc về: {bank_name}  
                Ứng dụng chỉ hỗ trợ QR từ BIDV (Mã BIN: 970418)
                """)
            else:
                st.session_state["account"] = info.get("account", "")
                st.session_state["bank_bin"] = bank_bin
                st.session_state["note"] = info.get("note", "")
                st.session_state["amount"] = info.get("amount", "")
                st.session_state["name"] = info.get("name", "")
                st.session_state["store"] = info.get("store", "")
                st.success("✅ Đã trích xuất dữ liệu từ ảnh QR.")
        except Exception as e:
            st.warning(f"⚠️ QR được giải mã nhưng không đúng chuẩn VietQR: {e}")



# Nhập số tài khoản (giữ nguyên key để Streamlit nhớ giá trị)
account = st.text_input("🔢 Số tài khoản", value=st.session_state.get("account", ""), key="account")

# Làm sạch dữ liệu: bỏ khoảng trắng dư thừa
account = ''.join(account.split())
name = st.text_input("👤 Tên tài khoản (nếu có)", value=st.session_state.get("name", ""), key="name")
store = st.text_input("🏪 Tên cửa hàng (nếu có)", value=st.session_state.get("store", ""), key="store")
note = st.text_input("📝 Nội dung (nếu có)", value=st.session_state.get("note", ""), key="note")
bank_bin = ''.join(st.session_state.get("bank_bin", "970418").split())
amount = ''.join(str(st.session_state.get("amount", "")).split())
merchant_id = ''.join(account.split())  # nếu bạn dùng account làm merchant_id

# === Danh sách cán bộ hỗ trợ ===
staff_list = {
    "": ("", ""),
    "Vũ Hoàng Phát - PGD Tiền Hải": ("Vũ Hoàng Phát", "0986.155.838"),
    "Lê Thị Liên - PGD Tiền Hải": ("Lê Thị Liên", "0976.239.278"),
    "Chu Thị Thu Hiền - BIDV Tiền Hải": ("Chu Thị Thu Hiền", "0989.557.699"),
}

selected_staff = st.selectbox("👨‍💼 Cán bộ hỗ trợ", list(staff_list.keys()), key="staff_selected")
staff_name, staff_phone = staff_list[selected_staff]
# Xử lý đầu vào số tiền
amount_input_raw = st.text_input("💰 Số tiền (nếu có)", value=st.session_state.get("amount", ""), key="amount_input")
amount_cleaned = clean_amount_input(amount_input_raw)

if amount_input_raw and amount_cleaned is None:
    st.error("❌ Số tiền không hợp lệ. Vui lòng chỉ nhập số (dùng dấu . hoặc , nếu có).")
else:
    st.session_state["amount"] = amount_cleaned or ""


if st.button("🎉 Tạo mã QR"):
    if not account.strip():
        st.warning("⚠️ Vui lòng nhập số tài khoản.")
    else:
        qr_data = build_vietqr_payload(account.strip(), bank_bin.strip(), note.strip(), amount.strip())
        st.session_state["qr1"] = generate_qr_with_logo(qr_data)
        st.session_state["qr2"] = create_qr_with_text(qr_data, name.strip(), account.strip())
        st.session_state["qr3"] = create_qr_with_background(qr_data, name.strip(), account.strip(), store.strip(), staff_name.strip(), staff_phone.strip())
        st.session_state["qr4"] = create_qr_with_background_thantai(qr_data, name.strip(), account.strip(), store.strip(), staff_name.strip(), staff_phone.strip())
        st.session_state["qr5"] = create_qr_with_background_loa(qr_data, name.strip(), account.strip(), store.strip(), staff_name.strip(), staff_phone.strip())
        st.session_state["qr6"] = create_qr_tingbox(qr_data, account.strip())
        st.success("✅ Mã QR đã được tạo thành công.")

# ==== Hiển thị ảnh QR nếu có ====
if "qr1" in st.session_state:
    with st.expander("🏷️ Mẫu 1: QR có logo"):
        st.image(st.session_state["qr1"], caption="Mẫu QR có logo", use_container_width=True)
if "qr2" in st.session_state:
    with st.expander("📄 Mẫu 2: QR có chữ"):
        st.image(st.session_state["qr2"], caption="Mẫu QR có chữ", use_container_width=True)
if "qr3" in st.session_state:
    with st.expander("🐱 Mẫu 3: QR mèo thần tài"):
        st.image(st.session_state["qr3"], caption="Mẫu QR mèo thần tài", use_container_width=True)
if "qr4" in st.session_state:
    with st.expander("🐯 Mẫu 4: QR thần tài"):
        st.image(st.session_state["qr4"], caption="Mẫu QR nền thần tài", use_container_width=True)
if "qr5" in st.session_state:
    with st.expander("🔊 Mẫu 5: QR nền loa thanh toán"):
        st.image(st.session_state["qr5"], caption="Mẫu QR loa thanh toán", use_container_width=True)
if "qr6" in st.session_state:
    with st.expander("📱 Mẫu 6: QR Tingbox"):
        st.image(st.session_state["qr6"], caption="Mẫu QR Tingbox", use_container_width=True)
