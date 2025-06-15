import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io, os, base64, cv2, numpy as np

st.set_page_config(page_title="VietQR BIDV", page_icon="assets/bidvfa.png", layout="centered")

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
FONT_PATH = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
BG_PATH = os.path.join(ASSETS_DIR, "background.png")

# ======== QR Logic Functions ========
def format_tlv(tag, value): return f"{tag}{len(value):02d}{value}"

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

def create_qr_with_background(data, acc_name, merchant_id):
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
    cx = lambda t: (base.width - draw.textbbox((0, 0), t, font=font)[2]) // 2
    draw.text((cx(acc_name.upper()), 1665), acc_name.upper(), fill=(0, 102, 102), font=font)
    draw.text((cx(merchant_id), 1815), merchant_id, fill=(0, 102, 102), font=font)
    buf = io.BytesIO(); base.save(buf, format="PNG"); buf.seek(0)
    return buf
