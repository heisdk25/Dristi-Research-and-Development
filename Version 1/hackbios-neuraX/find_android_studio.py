import urllib.request
import re

url = "https://developer.android.com/studio"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8")

filename = "android-studio-rabbit1-windows.zip"
pos = html.find(filename)
print("Position:", pos)
if pos != -1:
    snippet = html[max(0, pos-200):min(len(html), pos+600)]
    print("Snippet:")
    print(snippet)
    # Search for 64-char hex
    hashes = re.findall(r'[a-fA-F0-9]{64}', snippet)
    print("Hashes found:", hashes)
else:
    # Look for all hashes in page
    hashes = re.findall(r'[a-fA-F0-9]{64}', html)
    print("All 64-hex hashes in page:", len(hashes), hashes[:5])
