# PDF Logo Corner App

This app lets you:

- Upload one or multiple PDF files
- Add a logo on every page
- Prefer the lower-right corner first
- Try the other three corners if the lower-right corner is busy
- Shrink the logo if needed so it can fit in a corner
- Add the same institute image as a full page at the beginning and end

## Run

```powershell
streamlit run app.py
```

If `streamlit` is not on your PATH:

```powershell
python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8502
```

## Notes

- The app uses local processing only.
- Output is downloadable as a single PDF or a ZIP when you upload multiple PDFs.
- You can adjust preferred logo width, minimum logo width, and page margin from the sidebar.


