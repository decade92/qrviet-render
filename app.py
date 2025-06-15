
import streamlit as st
import time
st.set_page_config(
    page_title="VietQR BIDV",
    page_icon="assets/bidvfa.png",
    layout="centered"
    if st.session_state.get("do_rerun", False):
    st.session_state["do_rerun"] = False
    st.experimental_rerun()

)

import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
from io import BytesIO
import os
import base64
import cv2
import numpy as np

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
FONT_PATH = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
BG_PATH = os.path.join(ASSETS_DIR, "background.png")

def format_tlv(tag, value):
    return f"{tag}{len(value):02d}{value}"

def crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for b in data.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = (crc << 1) ^ 0x1021 if (crc & 0x8000) else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"

def parse_tlv(payload):
    i = 0
    result = {}
    while i < len(payload) - 4:
        tag = payload[i:i+2]
        length = int(payload[i+2:i+4])
        value = payload[i+4:i+4+length]
        result[tag] = value
        i += 4 + length
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
    payload = ""
    payload += format_tlv("00", "01")
    payload += format_tlv("01", "12")
    guid = format_tlv("00", "A000000727")
    acc_info = format_tlv("00", bank_bin) + format_tlv("01", merchant_id)
    nested_38 = guid + format_tlv("01", acc_info) + format_tlv("02", "QRIBFTTA")
    payload += format_tlv("38", nested_38)
    payload += format_tlv("52", "0000")
    payload += format_tlv("53", "704")
    if amount:
        payload += format_tlv("54", amount)
    payload += format_tlv("58", "VN")
    payload += format_tlv("62", format_tlv("08", add_info))
    payload += "6304"
    payload += crc16_ccitt(payload)
    return payload

def generate_qr_with_logo(data):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo = logo.resize((int(img_qr.width * 0.45), int(img_qr.height * 0.15)))
    pos = ((img_qr.width - logo.width) // 2, (img_qr.height - logo.height) // 2)
    img_qr.paste(logo, pos, mask=logo)
    buf = BytesIO()
    img_qr.save(buf, format="PNG")
    buf.seek(0)
    return buf

def create_qr_with_text(data, acc_name, merchant_id):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=21, border=3)
    qr.add_data(data)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo = logo.resize((int(img_qr.width * 0.45), int(img_qr.height * 0.15)))
    pos = ((img_qr.width - logo.width) // 2, (img_qr.height - logo.height) // 2)
    img_qr.paste(logo, pos, mask=logo)
    lines = [("Tên tài khoản:", 48, "black"), (acc_name.upper(), 60, "#007C71"),
             ("Tài khoản định danh:", 48, "black"), (merchant_id, 60, "#007C71")]
    spacing = 20
    total_text_height = sum([size for _, size, _ in lines]) + spacing * (len(lines) - 1)
    canvas = Image.new("RGBA", (img_qr.width, img_qr.height + total_text_height + 65), "white")
    canvas.paste(img_qr, (0, 0))
    draw = ImageDraw.Draw(canvas)
    y = img_qr.height + 16
    for text, size, color in lines:
        font = ImageFont.truetype(FONT_PATH, size)
        text_width = draw.textbbox((0, 0), text, font=font)[2]
        x = (canvas.width - text_width) // 2
        draw.text((x, y), text, fill=color, font=font)
        y += size + spacing
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    buf.seek(0)
    return buf

def create_qr_with_background(data, acc_name, merchant_id):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((540, 540))
    qr_img = round_corners(qr_img, radius=40)
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((240, 80))
    qr_img.paste(logo, ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2), mask=logo)
    base = Image.open(BG_PATH).convert("RGBA")
    base.paste(qr_img, (460, 936), mask=qr_img)
    draw = ImageDraw.Draw(base)
    font2 = ImageFont.truetype(FONT_PATH, 60)
    def center_x(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return (base.width - (bbox[2] - bbox[0])) // 2
    draw.text((center_x(acc_name.upper(), font2), 1665), acc_name.upper(), fill=(0, 102, 102), font=font2)
    draw.text((center_x(merchant_id, font2), 1815), merchant_id, fill=(0, 102, 102), font=font2)
    buf = BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf


# ==== Giao diện và xử lý người dùng ====
font_css = f"""
<style>
@font-face {{
    font-family: 'RobotoCustom';
    src: url(data:font/ttf;base64,{base64.b64encode(open(FONT_PATH, "rb").read()).decode()}) format('truetype');
}}
</style>
"""
st.markdown(font_css, unsafe_allow_html=True)

st.title("🇻🇳 Tạo ảnh VietQR đẹp chuẩn NAPAS ")

with open("assets/logo_bidv.png", "rb") as f:
    logo_data = base64.b64encode(f.read()).decode()

st.markdown(
    f"""
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
        <img src="data:image/png;base64,{logo_data}" style="height:30px; width:auto;">
        <span style="font-family: Roboto, sans-serif; font-weight: bold; font-size:24px; color:#007C71;">
            Dành riêng cho BIDV Thái Bình - PGD Tiền Hải
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

st.header("📥 Nhập tay hoặc phân tích từ ảnh QR")

for field in ["account", "bank_bin", "name", "note", "amount", "uploaded_file"]:
    if field not in st.session_state:
        st.session_state[field] = ""

# 👉 Khởi tạo duy nhất
uploaded_file = st.empty()
uploaded_result = uploaded_file.file_uploader("📤 Tải ảnh QR VietQR", type=["png", "jpg", "jpeg"])

# 👉 Xử lý nếu có file upload
if uploaded_result is not None:
    if "last_file_uploaded" not in st.session_state or st.session_state["last_file_uploaded"] != uploaded_result:
        st.session_state["last_file_uploaded"] = uploaded_result
        qr_text = decode_qr_image_cv(uploaded_result)
        if qr_text:
            info = extract_vietqr_info(qr_text)
            st.session_state["account"] = info.get("account", "")
            st.session_state["bank_bin"] = info.get("bank_bin", "970418")
            st.session_state["note"] = info.get("note", "")
            st.session_state["amount"] = info.get("amount", "")
            st.success("✅ Đã trích xuất dữ liệu từ ảnh QR.")
        else:
            st.warning("⚠️ Không thể nhận diện được mã QR từ ảnh đã tải lên.")


account = st.text_input("🔢 Số tài khoản", value=st.session_state.get("account", ""))
bank_bin = st.text_input("🏦 Mã ngân hàng", value=st.session_state.get("bank_bin", ""))
name = st.text_input("👤 Tên tài khoản (nếu có)", value=st.session_state.get("name", ""))
note = st.text_input("📝 Nội dung (nếu có)", value=st.session_state.get("note", ""))
amount = st.text_input("💵 Số tiền (nếu có)", value=st.session_state.get("amount", ""))

if st.button("🎉 Tạo mã QR"):
    if not all([account.strip(), bank_bin.strip()]):
        st.warning("⚠️ Vui lòng nhập số tài khoản và mã ngân hàng.")
    else:
        qr_data = build_vietqr_payload(account.strip(), bank_bin.strip(), note.strip(), amount.strip())
        qr1 = generate_qr_with_logo(qr_data)
        qr2 = create_qr_with_text(qr_data, name.strip(), account.strip())
        qr3 = create_qr_with_background(qr_data, name.strip(), account.strip())

        # Lưu ảnh QR vào session để hiển thị sau rerun
        st.session_state["qr1"] = qr1
        st.session_state["qr2"] = qr2
        st.session_state["qr3"] = qr3

# Xoá các trường form (nhưng giữ lại qr1, qr2, qr3)
        for key in ['account', 'bank_bin', 'name', 'note', 'amount', 'uploaded_file', 'last_file_uploaded']:
            st.session_state.pop(key, None)
        
        # Đặt cờ để rerun
        st.session_state["do_rerun"] = True



if "qr1" in st.session_state:
    st.markdown("### 🏷️ Mẫu 1: QR có logo BIDV")
    st.image(st.session_state["qr1"], caption="Mẫu QR có logo", use_container_width=True)

if "qr2" in st.session_state:
    st.markdown("### 🧾 Mẫu 2: QR có chữ (tên và số tài khoản)")
    st.image(st.session_state["qr2"], caption="Mẫu QR có chữ", use_container_width=True)

if "qr3" in st.session_state:
    st.markdown("### 🐈‍⬛ Mẫu 3: QR nền mèo thần tài (may mắn)")
    st.image(st.session_state["qr3"], caption="Mẫu QR nền đẹp", use_container_width=True)

