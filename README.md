# Flypaper

## Download and remove the PREVIEW watermark

Run the downloader with the requested image width, height, and two-character
alphanumeric airline code. The output is saved as `<CODE>.png` in the current directory:

```powershell
python downloader.py 1200 800 TB
```

Both dimensions must be between 1 and 2048 pixels. The downloaded image is
processed in memory; no intermediate input image is created. The airline code
is case-insensitive and the output filename uses uppercase letters.
`remove_preview.py` and `preview_template.png` must remain alongside
`downloader.py`.

## Live aircraft display

Run `server.py` and open `http://127.0.0.1:8765`. The page shows a Boeing 737-800
with the livery of the currently selected airline. Airline images are downloaded
on first use, have the PREVIEW watermark removed, and are composited onto the
aircraft template. Source and rendered images are cached in `tail-cache/`.
If FlightRadar24 responds with HTTP 429, polling waits for its `Retry-After`
value when provided, or backs off exponentially before retrying.
The upper-right panel shows model, registration, and aircraft details from the
FlightRadar24 flight-details response. Year of manufacture and serial number
are shown only when present in that response; otherwise the panel says the API
did not provide them. The Boeing 737-800 SVG is a temporary illustration.
Numeric registration-country IDs are translated to names where known; common
aircraft registration prefixes are used as a fallback.