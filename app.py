import streamlit as st
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
from io import BytesIO
import os
import base64

st.set_page_config(
    page_title="VietQR BIDV",
    page_icon="assets/bidvfa.png",  # hoặc emoji như "🏦"
    layout="centered"
)
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "logo.png")
FONT_PATH = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
BG_PATH = os.path.join(ASSETS_DIR, "background.png")
BG_THAI_PATH = os.path.join(ASSETS_DIR, "backgroundthantai.png")

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
def round_corners(image, radius):
    """Trả về ảnh được bo góc với bán kính radius"""
    rounded = Image.new("RGBA", image.size, (0, 0, 0, 0))
    mask = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, image.size[0], image.size[1]], radius=radius, fill=255)
    rounded.paste(image, (0, 0), mask=mask)
    return rounded

def build_vietqr_payload(merchant_id, bank_bin, add_info, amount=""):
    payload = ""
    payload += format_tlv("00", "01")
    payload += format_tlv("01", "12")  # Dynamic QR
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
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=21,
        border=3
    )
    qr.add_data(data)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")

    # Dán logo vào giữa QR
    logo = Image.open(LOGO_PATH).convert("RGBA")
    logo = logo.resize((int(img_qr.width * 0.45), int(img_qr.height * 0.15)))
    pos = ((img_qr.width - logo.width) // 2, (img_qr.height - logo.height) // 2)
    img_qr.paste(logo, pos, mask=logo)

    # 4 dòng text hiển thị
    lines = [
        ("Tên tài khoản:", 48, "black"),
        (acc_name.upper(), 60, "#007C71"),
        ("Tài khoản định danh:", 48, "black"),
        (merchant_id, 60, "#007C71")
    ]
    spacing = 20
    total_text_height = sum([size for _, size, _ in lines]) + spacing * (len(lines) - 1)

    # Tạo canvas để chứa QR + text
    canvas = Image.new("RGBA", (img_qr.width, img_qr.height + total_text_height + 65), "white")
    canvas.paste(img_qr, (0, 0))

    # Vẽ text
    draw = ImageDraw.Draw(canvas)
    y = img_qr.height + 16
    for text, size, color in lines:
        font = ImageFont.truetype(FONT_PATH, size)
        text_width = draw.textbbox((0, 0), text, font=font)[2]
        x = (canvas.width - text_width) // 2  # Căn giữa ngang
        draw.text((x, y), text, fill=color, font=font)
        y += size + spacing

    # Trả về ảnh dạng BytesIO để hiển thị trên Streamlit
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
    font1 = ImageFont.truetype(FONT_PATH, 45)
    font2 = ImageFont.truetype(FONT_PATH, 60)

    # Căn giữa toàn ảnh theo chiều ngang
    
def create_qr_with_background_thantai(data, acc_name, merchant_id):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA").resize((540, 540))
    qr_img = round_corners(qr_img, radius=40)
    logo = Image.open(LOGO_PATH).convert("RGBA").resize((240, 80))
    qr_img.paste(logo, ((qr_img.width - logo.width) // 2, (qr_img.height - logo.height) // 2), mask=logo)

    base = Image.open(BG_THAI_PATH).convert("RGBA")
    base.paste(qr_img, (460, 936), mask=qr_img)

    draw = ImageDraw.Draw(base)
    font1 = ImageFont.truetype(FONT_PATH, 45)
    font2 = ImageFont.truetype(FONT_PATH, 60)

    def center_x(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        return (base.width - (bbox[2] - bbox[0])) // 2

    value_1 = acc_name.upper()
    value_2 = merchant_id

    draw.text((center_x(value_1, font2), 1665), value_1, fill=(0, 102, 102), font=font2)
    draw.text((center_x(value_2, font2), 1815), value_2, fill=(0, 102, 102), font=font2)

    buf = BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf
def center_x(text, font):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        return (base.width - text_width) // 2

    # Nội dung
   # label_1 = "Tên tài khoản:"
    value_1 = acc_name.upper()
  #  label_2 = "Tài khoản định danh:"
    value_2 = merchant_id

    # Vẽ nền trắng đủ rộng phía dưới
   # draw.rectangle([(460, 1600), (1000, 2000)], fill="white")

    # Vẽ các dòng text, căn giữa toàn ảnh
   # draw.text((center_x(label_1, font1), 1650), label_1, fill=(0, 102, 102), font=font1)
    draw.text((center_x(value_1, font2), 1665), value_1, fill=(0, 102, 102), font=font2)
 #   draw.text((center_x(label_2, font1), 1800), label_2, fill=(0, 102, 102), font=font1)
    draw.text((center_x(value_2, font2), 1815), value_2, fill=(0, 102, 102), font=font2)

    buf = BytesIO()
    base.save(buf, format="PNG")
    buf.seek(0)
    return buf



def local_font_to_css(path, font_name):
    with open(path, "rb") as f:
        font_data = f.read()
        encoded = base64.b64encode(font_data).decode()
        return f"""
        <style>
        @font-face {{
            font-family: '{font_name}';
            src: url(data:font/ttf;base64,{encoded}) format('truetype');
        }}
        </style>
        """

font_css = local_font_to_css("assets/Roboto-Bold.ttf", "RobotoCustom")
st.markdown(font_css, unsafe_allow_html=True)

st.title("🇻🇳 Tạo ảnh VietQR đẹp chuẩn NAPAS ")

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

merchant_id = st.text_input("🔢 Số tài khoản định danh:")
acc_name = st.text_input("👤 Tên tài khoản (tuỳ chọn):")
add_info = st.text_input("📝 Nội dung chuyển khoản (tuỳ chọn):")
amount = st.text_input("💵 Số tiền (tuỳ chọn):", "")
bank_bin = st.text_input("🏦 Mã ngân hàng (mặc định BIDV 970418):", "970418")

if st.button("🎉 Tạo mã QR"):
    if not merchant_id:
        st.warning("❗ Vui lòng nhập đầy đủ thông tin số tài khoản.")
    else:
        qr_data = build_vietqr_payload(merchant_id.strip(), bank_bin.strip(), add_info.strip(), amount.strip())
        qr1 = generate_qr_with_logo(qr_data)
        qr2 = create_qr_with_text(qr_data, acc_name, merchant_id)
        qr3 = create_qr_with_background(qr_data, acc_name, merchant_id)

        st.subheader("📌 Mẫu 1: QR Rút gọn")
        st.image(qr1, caption="QR VietQR chuẩn")

        st.subheader("🧾 Mẫu 2: QR CÓ THÔNG TIN")
        st.image(qr2, caption="QR kèm tên và định danh")

        st.subheader("🌅 Mẫu 3: QR MÈO THẦN TÀI")
        st.image(qr3, caption="QR nền tùy chỉnh")
        qr4 = create_qr_with_background_thantai(qr_data, acc_name, merchant_id)
        st.subheader("🐯 Mẫu 4: QR MÈO THẦN TÀI - PHIÊN BẢN KHÁC")
        st.image(qr4, caption="QR nền mèo thần tài khác")

