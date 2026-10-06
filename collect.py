"""Tai du lieu phat dien thoi gian thuc cua Taipower (dataset 8931) va luu dang nen.

Moi lan chay luu 1 file: data/raw/YYYY-MM/YYYY-MM-DD/HHMM.json.gz (gio Dai Loan).
Luu nguyen du lieu goc; viec doc va xu ly lam sau tren Colab.
"""
import datetime as dt
import gzip
import json
import os
import time
import urllib.request

URL = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genary.json"
TZ_TAIWAN = dt.timezone(dt.timedelta(hours=8))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def fetch(retries: int = 3, wait_seconds: int = 10) -> bytes:
    """Tai file JSON, thu lai neu loi. Kiem tra noi dung dung la JSON."""
    request = urllib.request.Request(URL, headers=HEADERS)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
            json.loads(body.decode("utf-8-sig"))
            return body
        except Exception as error:  # noqa: BLE001
            print(f"Lan thu {attempt} loi: {error}")
            if attempt < retries:
                time.sleep(wait_seconds)
    raise SystemExit("Tai that bai sau tat ca cac lan thu")


def main() -> None:
    now = dt.datetime.now(TZ_TAIWAN)
    body = fetch()
    folder = os.path.join("data", "raw", f"{now:%Y-%m}", f"{now:%Y-%m-%d}")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{now:%H%M}.json.gz")
    with gzip.open(path, "wb") as file:
        file.write(body)
    print(f"Da luu {path} ({len(body):,} bytes)")


if __name__ == "__main__":
    main()