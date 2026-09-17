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


def composite_signature(base, sig_img, center_frac, width_frac):
    """Alpha-composite sig_img onto base (both RGBA) in place."""
    target_w = max(1, round(width_frac * base.width))
    scale = target_w / sig_img.width
    target_h = max(1, round(sig_img.height * scale))
    resized = sig_img.resize((target_w, target_h))
    cx = center_frac[0] * base.width
    cy = center_frac[1] * base.height
    top_left = (round(cx - target_w / 2), round(cy - target_h / 2))
    base.alpha_composite(resized, dest=top_left)


def build_signed_pdf(pdf_bytes, placements):
    """placements: list of dicts with page_index, sig_img, center_frac, width_frac."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for placement in placements:
        page = doc[placement["page_index"]]
        pw, ph = page.rect.width, page.rect.height
        sig_img = placement["sig_img"]
        w_pt = placement["width_frac"] * pw
        h_pt = w_pt * (sig_img.height / sig_img.width)
        cx_pt = placement["center_frac"][0] * pw
        cy_pt = placement["center_frac"][1] * ph
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
    "Upload a PDF and one or more signature images, place each one where you "
    "like (any page, size, rotation), then download the signed file. "
    "Nothing leaves your machine."
)

pdf_file = st.file_uploader("PDF document", type=["pdf"])
sig_files = st.file_uploader(
    "Signature image(s)",
    type=["png", "jpg", "jpeg"],
    accept_multiple_files=True,
)

if pdf_file and sig_files:
    pdf_bytes = pdf_file.getvalue()
    doc = load_pdf(pdf_bytes)
    num_pages = len(doc)

    # Stable per-signature key based on upload order + filename.
    sig_keys = [f"sig_{i}_{f.name}" for i, f in enumerate(sig_files)]

    for key in sig_keys:
        if key not in st.session_state:
            st.session_state[key] = {
                "page": 1,
                "center": (0.5, 0.5),
                "width_pct": 20,
                "rotation": 0,
                "remove_white": True,
                "threshold": 235,
            }

    active_idx = st.selectbox(
        "Editing signature",
        options=range(len(sig_files)),
        format_func=lambda i: sig_files[i].name,
    )
    active_key = sig_keys[active_idx]
    active_file = sig_files[active_idx]
    state = st.session_state[active_key]

    col1, col2 = st.columns(2)
    with col1:
        state["page"] = st.number_input(
            "Page",
            min_value=1,
            max_value=num_pages,
            value=state["page"],
            step=1,
            key=f"{active_key}_page",
        )
    with col2:
        state["width_pct"] = st.slider(
            "Signature width (% of page width)",
            5,
            60,
            state["width_pct"],
            key=f"{active_key}_width",
        )

    state["rotation"] = st.slider(
        "Rotation (degrees)", -45, 45, state["rotation"], key=f"{active_key}_rotation"
    )
    state["remove_white"] = st.checkbox(
        "Remove white background from signature",
        value=state["remove_white"],
        key=f"{active_key}_removewhite",
    )
    if state["remove_white"]:
        state["threshold"] = st.slider(
            "White removal sensitivity",
            200,
            254,
            state["threshold"],
            key=f"{active_key}_threshold",
        )

    # Process every signature (needed to render all of them onto the preview page).
    processed_imgs = {}
    for key, f in zip(sig_keys, sig_files):
        s = st.session_state[key]
        raw = Image.open(io.BytesIO(f.getvalue())).convert("RGBA")
        if s["remove_white"]:
            raw = make_transparent(raw, s["threshold"])
        processed_imgs[key] = rotate_signature(raw, s["rotation"])

    preview_page_index = state["page"] - 1
    page, page_img = render_page(doc, preview_page_index)
    preview = page_img.convert("RGBA").copy()

    for key, f in zip(sig_keys, sig_files):
        s = st.session_state[key]
        if s["page"] - 1 != preview_page_index:
            continue
        composite_signature(preview, processed_imgs[key], s["center"], s["width_pct"] / 100)

    st.write(f"Click anywhere on page {state['page']} to move **{active_file.name}** there:")
    click = streamlit_image_coordinates(
        preview.convert("RGB"), key=f"coords_{active_key}_{preview_page_index}"
    )

    if click is not None:
        fx = min(max(click["x"] / preview.width, 0.0), 1.0)
        fy = min(max(click["y"] / preview.height, 0.0), 1.0)
        if (fx, fy) != state["center"]:
            state["center"] = (fx, fy)
            st.rerun()

    if st.button("Reset this signature's position to center"):
        state["center"] = (0.5, 0.5)
        st.rerun()

    with st.expander("All placed signatures"):
        for key, f in zip(sig_keys, sig_files):
            s = st.session_state[key]
            marker = "→ " if key == active_key else ""
            st.write(
                f"{marker}**{f.name}** — page {s['page']}, "
                f"{s['width_pct']}% width, rotated {s['rotation']}°"
            )

    if st.button("Generate signed PDF", type="primary"):
        placements = [
            {
                "page_index": st.session_state[key]["page"] - 1,
                "sig_img": processed_imgs[key],
                "center_frac": st.session_state[key]["center"],
                "width_frac": st.session_state[key]["width_pct"] / 100,
            }
            for key in sig_keys
        ]
        signed_bytes = build_signed_pdf(pdf_bytes, placements)
        st.success("Signed PDF ready.")
        st.download_button(
            "Download signed PDF",
            data=signed_bytes,
            file_name=f"signed_{pdf_file.name}",
            mime="application/pdf",
        )
else:
    st.info("Upload a PDF and at least one signature image to get started.")
