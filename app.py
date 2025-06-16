import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io, os, base64, cv2, numpy as np

st.set_page_config(page_title="VietQR BIDV", page_icon="assets/bidvfa.png", layout="centered")

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
FONT_PATH = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
BG_PATH = os.path.join(ASSETS_DIR, "background.png")
BG_THAI_PATH = os.path.join(ASSETS_DIR, "backgroundthantai.png")

# ======== QR Logic Functions ========
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
    i, result = 0, {}
    while i < len(payload) - 4:
        tag, length = payload[i:i+2], int(payload[i+2:i+4])
        value = payload[i+4:i+4+length]
        result[tag], i = value, i + 4 + length
    return result

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

def decode_qr_image_cv(uploaded_image_bytes):
    file_bytes = np.asarray(bytearray(uploaded_image_bytes.read()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(image)
    return data if data else None

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
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((int(img.width*0.45), int(img.height*0.15)))
    img.paste(logo, ((img.width - logo.width) // 2, (img.height - logo.height) // 2), logo)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return buf

def create_qr_with_text(data, acc_name, merchant_id):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=21, border=3)
    qr.add_data(data); qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((int(img.width*0.45), int(img.height*0.15)))
    img.paste(logo, ((img.width - logo.width) // 2, (img.height - logo.height) // 2), logo)
    lines = [("Tên tài khoản:", 48, "black"), (acc_name.upper(), 60, "#007C71"), ("Tài khoản định danh:", 48, "black"), (merchant_id, 60, "#007C71")]
    spacing = 20
    total_text_height = sum([size for _, size, _ in lines]) + spacing * (len(lines) - 1)
    canvas = Image.new("RGBA", (img.width, img.height + total_text_height + 65), "white")
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    y = img.height + 16
    for text, size, color in lines:
        font = ImageFont.truetype(FONT_PATH, size)
        x = (canvas.width - draw.textbbox((0, 0), text, font=font)[2]) // 2
        draw.text((x, y), text, fill=color, font=font)
        y += size + spacing
    buf = io.BytesIO(); canvas.save(buf, format="PNG"); buf.seek(0)
    return buf

def create_qr_with_background(data, acc_name, merchant_id, store_name):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data); qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((540, 540))
    qr_img = round_corners(qr_img, 40)
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((240, 80))
    qr_img.paste(logo, ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2), logo)
    base = Image.open(BG_PATH).convert("RGBA")
    base.paste(qr_img, (460, 936), qr_img)
    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype(FONT_PATH, 60)
    cx = lambda t, f: (base.width - draw.textbbox((0, 0), t, font=f)[2]) // 2
    draw.text((cx(acc_name.upper(), font), 1665), acc_name.upper(), fill=(0, 102, 102), font=font)
    draw.text((cx(merchant_id, font), 1815), merchant_id, fill=(0, 102, 102), font=font)
    store_font = ImageFont.truetype(FONT_PATH, 70)
    draw.text((cx(store_name.upper(), store_font), 265), store_name.upper(), fill="#007C71", font=store_font)
    buf = io.BytesIO(); base.save(buf, format="PNG"); buf.seek(0)
    return buf

def create_qr_with_background_thantai(data, acc_name, merchant_id, store_name):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=0)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((480, 520))
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((240, 80))
    qr_img.paste(logo, ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2), logo)
    base = Image.open(BG_THAI_PATH).convert("RGBA")
    base.paste(qr_img, (793, 725), qr_img)
    draw = ImageDraw.Draw(base)
    font = ImageFont.truetype(FONT_PATH, 60)
    cx = lambda t, f: (base.width - draw.textbbox((0, 0), t, font=f)[2]) // 2
    draw.text((cx(acc_name.upper(), font), 1665), acc_name.upper(), fill=(0, 102, 102), font=font)
    draw.text((cx(merchant_id, font), 1815), merchant_id, fill=(0, 102, 102), font=font)
    store_font = ImageFont.truetype(FONT_PATH, 70)
    draw.text((cx(store_name.upper(), store_font), 265), store_name.upper(), fill="#007C71", font=store_font)
    buf = io.BytesIO(); base.save(buf, format="PNG"); buf.seek(0)
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

st.title("🇻🇳 Tạo ảnh VietQR đẹp chuẩn NAPAS")
st.markdown(
    """
    <div style="display: flex; align-items: center;">
        <img src="data:image/png;base64,{logo_data}" style="max-height:25px; height:25px; width:auto; margin-right:10px;">
        <span style="font-family: Roboto, sans-serif; font-weight: bold; font-size:25px; color:#007C71;">
            Dành riêng cho BIDV Thái Bình - PGD Tiền Hải
        </span>
    </div>
    """.format(
        logo_data=base64.b64encode(open("assets/logo_bidv.png", "rb").read()).decode()
    ),
    unsafe_allow_html=True
)

st.markdown("**📥 Nhập thông tin chuyển khoản**")

uploaded_result = st.file_uploader("📤 Tải ảnh QR VietQR", type=["png", "jpg", "jpeg"], key="uploaded_file")
if uploaded_result and uploaded_result != st.session_state.get("last_file_uploaded"):
    st.session_state["last_file_uploaded"] = uploaded_result
    qr_text = decode_qr_image_cv(uploaded_result)
    if qr_text:
        info = extract_vietqr_info(qr_text)
        if info.get("bank_bin") != "970418":
            st.error("⚠️ Ứng dụng chỉ hỗ trợ QR từ BIDV (Mã BIN: 970418).")
        else:
            # 🚨 Ghi đè toàn bộ các trường bằng dữ liệu trích xuất từ ảnh QR
            st.session_state["account"] = info.get("account", "")
            st.session_state["bank_bin"] = info.get("bank_bin", "970418")
            st.session_state["note"] = info.get("note", "")
            st.session_state["amount"] = info.get("amount", "")
            st.session_state["name"] = info.get("name", "")
            st.session_state["store"] = info.get("store", "")
            st.success("✅ Đã trích xuất dữ liệu từ ảnh QR.")
    else:
        st.warning("⚠️ Không thể nhận diện được mã QR từ ảnh đã tải lên.")


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
# Nhập số tiền
amount_input = st.text_input("💰 Số tiền (VND)", value=st.session_state.get("amount", ""), key="amount")

# Làm sạch khoảng trắng
amount_input = ''.join(amount_input.split())

# Kiểm tra hợp lệ
if amount_input and not amount_input.isdigit():
    st.warning("⚠️ Số tiền chỉ được nhập bằng chữ số (không dấu, không ký tự đặc biệt).")
else:
    st.session_state["amount"] = amount_input  # Gán lại nếu hợp lệ
if st.button("🎉 Tạo mã QR"):
    if not account.strip():
        st.warning("⚠️ Vui lòng nhập số tài khoản.")
    else:
        qr_data = build_vietqr_payload(account.strip(), bank_bin.strip(), note.strip(), amount.strip())
        st.session_state["qr1"] = generate_qr_with_logo(qr_data)
        st.session_state["qr2"] = create_qr_with_text(qr_data, name.strip(), account.strip())
        st.session_state["qr3"] = create_qr_with_background(qr_data, name.strip(), account.strip(), store.strip())
        st.session_state["qr4"] = create_qr_with_background_thantai(qr_data, name.strip(), account.strip(), store.strip())
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
