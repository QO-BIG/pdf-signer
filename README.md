# Sign a PDF

A small Streamlit app: upload a PDF and an image of your signature, click on
the page preview to position it, then download the signed PDF. Everything
runs locally in your own browser session — nothing is uploaded anywhere
unless you deploy it publicly.

## How it works

1. Upload your PDF and a signature image (PNG with a transparent background
   works best; JPGs/plain PNGs are also accepted and can have their white
   background stripped automatically with the "Remove white background"
   checkbox).
2. Pick the page number, and adjust the signature's size (% of page width)
   and rotation with the sliders.
3. Click anywhere on the page preview — the signature jumps there. Click
   again to nudge it, as many times as you like.
4. Click "Generate signed PDF", then "Download signed PDF" to save the
   result.

## Run it locally

You need Python 3.10+ installed.

```bash
# 1. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

Streamlit will open the app in your browser automatically (usually at
http://localhost:8501). Press Ctrl+C in the terminal to stop it.

## Deploying to Streamlit Community Cloud (free, public link)

Once you've tried it locally and are happy with it, you can publish it for
free:

1. Create a free GitHub account (if you don't have one) and a new repository,
   e.g. `pdf-signer`.
2. Push these two files (`app.py` and `requirements.txt`) to that repository.
3. Go to https://share.streamlit.io and sign in with GitHub.
4. Click "New app," pick your repository/branch, and set the main file path
   to `app.py`.
5. Click "Deploy." Streamlit Cloud installs `requirements.txt` automatically
   and gives you a public URL like `https://your-app-name.streamlit.app`.

Keep in mind that a publicly deployed app is reachable by anyone with the
link, and Streamlit Cloud's free tier runs on shared infrastructure — avoid
using it for sensitive documents unless you add your own access control
(Streamlit Cloud supports simple viewer-restriction settings under the app's
"Settings" menu).

## Notes / possible tweaks

- The app only places one signature on one selected page per "Generate"
  click. If you need it on multiple pages, generate once per page and merge
  the PDFs afterward, or ask to have multi-page placement added.
- The "Remove white background" option uses a simple brightness threshold
  (any pixel with R, G, and B all above the threshold becomes transparent).
  It works well for a signature photographed or scanned on plain white
  paper; busier backgrounds may need a proper background-removal tool
  first.
- Position and size are stored as fractions of the page, so they stay
  correct regardless of the PDF's actual page size (Letter, A4, etc.).
