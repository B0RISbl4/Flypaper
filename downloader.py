from curl_cffi import requests
URL = "https://content.airhex.com/content/logos/airlines_TB_600_600_t.png"
r = requests.get(
    URL,
    impersonate="chrome"
)
print(r.status_code, r.headers.get("content-type"))
if r.headers.get("content-type", "").startswith("image/"):
    open("input.png", "wb").write(r.content)