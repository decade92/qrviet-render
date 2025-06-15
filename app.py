
import streamlit as st
import time
st.set_page_config(
    page_title="VietQR BIDV",
    page_icon="assets/bidvfa.png",
    layout="centered"
)

# ... Giữ lại phần đầu và các hàm từ bản chuẩn ...

# === Hiển thị form nhập liệu dùng value=... để tránh lỗi ===
account = st.text_input("🔢 Số tài khoản", value=st.session_state.get("account", ""))
bank_bin = st.text_input("🏦 Mã ngân hàng", value=st.session_state.get("bank_bin", ""))
name = st.text_input("👤 Tên tài khoản (nếu có)", value=st.session_state.get("name", ""))
note = st.text_input("📝 Nội dung (nếu có)", value=st.session_state.get("note", ""))
amount = st.text_input("💵 Số tiền (nếu có)", value=st.session_state.get("amount", ""))

# === Nút tạo QR ===
if st.button("🎉 Tạo mã QR"):
    if not all([account.strip(), bank_bin.strip()]):
        st.warning("⚠️ Vui lòng nhập số tài khoản và mã ngân hàng.")
    else:
        qr_data = build_vietqr_payload(account.strip(), bank_bin.strip(), note.strip(), amount.strip())
        qr1 = generate_qr_with_logo(qr_data)
        qr2 = create_qr_with_text(qr_data, name.strip(), account.strip())
        qr3 = create_qr_with_background(qr_data, name.strip(), account.strip())

        st.session_state["qr1"] = qr1
        st.session_state["qr2"] = qr2
        st.session_state["qr3"] = qr3
        st.success("✅ Mã QR đã được tạo thành công.")

        for key in ['account', 'bank_bin', 'name', 'note', 'amount', 'uploaded_file']:
            if key in st.session_state:
                del st.session_state[key]

# === Hiển thị lại QR nếu có ===
if "qr1" in st.session_state:
    st.markdown("### 🏷️ Mẫu 1: QR có logo BIDV")
    st.image(st.session_state["qr1"], caption="Mẫu QR có logo", use_container_width=True)

if "qr2" in st.session_state:
    st.markdown("### 🧾 Mẫu 2: QR có chữ (tên và số tài khoản)")
    st.image(st.session_state["qr2"], caption="Mẫu QR có chữ", use_container_width=True)

if "qr3" in st.session_state:
    st.markdown("### 🐈‍⬛ Mẫu 3: QR nền mèo thần tài (may mắn)")
    st.image(st.session_state["qr3"], caption="Mẫu QR nền đẹp", use_container_width=True)
