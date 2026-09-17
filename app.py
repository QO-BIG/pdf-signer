import io

import pymupdf as fitz  # PyMuPDF
import streamlit as st
from PIL import Image
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="Sign a PDF", page_icon="✍️", layout="centered")

PREVIEW_WIDTH = 650


def load_pdf(file_bytes):
    return fitz.open(stream=file_bytes, filetype="pdf")


def render_page(doc, page_index, target_width=PREVIEW_WIDTH):
    page = doc[page_index]
    zoom = target_width / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
    return page, img


def make_transparent(img, threshold):
    """Turn near-white pixels transparent (simple background removal)."""
    img = img.convert("RGBA")
    pixels = img.getdata()
    new_pixels = [
        (r, g, b, 0) if (r >= threshold and g >= threshold and b >= threshold) else (r, g, b, a)
        for (r, g, b, a) in pixels
    ]
    img.putdata(new_pixels)
    return img


def rotate_signature(sig_img, angle):
    if angle == 0:
        return sig_img
    return sig_img.rotate(angle, expand=True, resample=Image.BICUBIC)


def composite_preview(page_img, sig_img, center_frac, width_frac):
    base = page_img.convert("RGBA").copy()
    target_w = max(1, round(width_frac * base.width))
    scale = target_w / sig_img.width
    target_h = max(1, round(sig_img.height * scale))
    resized = sig_img.resize((target_w, target_h))
    cx = center_frac[0] * base.width
    cy = center_frac[1] * base.height
    top_left = (round(cx - target_w / 2), round(cy - target_h / 2))
    base.alpha_composite(resized, dest=top_left)
    return base.convert("RGB")


def build_signed_pdf(pdf_bytes, page_index, sig_img, center_frac, width_frac):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_index]
    pw, ph = page.rect.width, page.rect.height
    w_pt = width_frac * pw
    h_pt = w_pt * (sig_img.height / sig_img.width)
    cx_pt = center_frac[0] * pw
    cy_pt = center_frac[1] * ph
    rect = fitz.Rect(cx_pt - w_pt / 2, cy_pt - h_pt / 2, cx_pt + w_pt / 2, cy_pt + h_pt / 2)
    buf = io.BytesIO()
    sig_img.save(buf, format="PNG")
    page.insert_image(rect, stream=buf.getvalue(), keep_proportion=True)
    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


st.title("✍️ Sign a PDF")
st.caption(
    "Upload a PDF and a signature image, click on the page preview to place it, "
    "then download the signed file. Nothing leaves your machine."
)

pdf_file = st.file_uploader("PDF document", type=["pdf"])
sig_file = st.file_uploader("Signature image", type=["png", "jpg", "jpeg"])

if pdf_file and sig_file:
    pdf_bytes = pdf_file.getvalue()
    doc = load_pdf(pdf_bytes)
    num_pages = len(doc)

    col1, col2 = st.columns(2)
    with col1:
        page_number = st.number_input(
            "Page", min_value=1, max_value=num_pages, value=1, step=1
        )
    with col2:
        width_pct = st.slider("Signature width (% of page width)", 5, 60, 20)

    rotation = st.slider("Rotation (degrees)", -45, 45, 0)

    sig_raw = Image.open(io.BytesIO(sig_file.getvalue()))
    default_remove_white = sig_raw.mode != "RGBA"
    remove_white = st.checkbox(
        "Remove white background from signature", value=default_remove_white
    )
    threshold = 235
    if remove_white:
        threshold = st.slider("White removal sensitivity", 200, 254, 235)

    sig_processed = sig_raw.convert("RGBA")
    if remove_white:
        sig_processed = make_transparent(sig_processed, threshold)
    sig_rotated = rotate_signature(sig_processed, rotation)

    page_index = page_number - 1
    page, page_img = render_page(doc, page_index)

    center_key = f"center_{page_index}"
    if center_key not in st.session_state:
        st.session_state[center_key] = (0.5, 0.5)

    preview = composite_preview(
        page_img, sig_rotated, st.session_state[center_key], width_pct / 100
    )

    st.write("Click anywhere on the page below to move the signature there:")
    click = streamlit_image_coordinates(preview, key=f"coords_{page_index}")

    if click is not None:
        fx = min(max(click["x"] / preview.width, 0.0), 1.0)
        fy = min(max(click["y"] / preview.height, 0.0), 1.0)
        if (fx, fy) != st.session_state[center_key]:
            st.session_state[center_key] = (fx, fy)
            st.rerun()

    if st.button("Reset position to center"):
        st.session_state[center_key] = (0.5, 0.5)
        st.rerun()

    if st.button("Generate signed PDF", type="primary"):
        signed_bytes = build_signed_pdf(
            pdf_bytes,
            page_index,
            sig_rotated,
            st.session_state[center_key],
            width_pct / 100,
        )
        st.success("Signed PDF ready.")
        st.download_button(
            "Download signed PDF",
            data=signed_bytes,
            file_name=f"signed_{pdf_file.name}",
            mime="application/pdf",
        )
else:
    st.info("Upload both a PDF and a signature image to get started.")