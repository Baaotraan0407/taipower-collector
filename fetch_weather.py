"""Tai thoi tiet theo gio (Open-Meteo, du lieu tai phan tich ERA5) cho 5 diem dai dien o Dai Loan.

Dung cho: bien dau vao du bao CI (RQ3) va bien kiem soat thoi tiet trong hoi quy MEF.
Open-Meteo mien phi, khong can khoa API; du lieu tre khoang 5 ngay so voi hien tai.

Cach dung tren Colab:
    !python fetch_weather.py 2019-07-01 2022-06-30 weather_coal.parquet
    !python fetch_weather.py 2024-10-01 2026-10-01 weather_gas.parquet
Luu ket qua vao taipower_data/weather/.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

import pandas as pd

# Diem dai dien: 3 trung tam phu tai, 1 vung dien mat troi, 1 vung dien gio ven bien.
POINTS = {
    "taipei": (25.03, 121.56),
    "taichung": (24.15, 120.67),
    "kaohsiung": (22.63, 120.30),
    "tainan_solar": (23.10, 120.20),
    "changhua_wind": (24.08, 120.40),
}
VARIABLES = [
    "temperature_2m",          # nhiet do (C): dieu hoa -> phu tai
    "relative_humidity_2m",    # do am (%)
    "shortwave_radiation",     # buc xa mat troi (W/m2): dien mat troi
    "cloud_cover",             # do che phu may (%)
    "wind_speed_100m",         # gio o do cao tuabin (km/h): dien gio
]
URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_point(lat: float, lon: float, start: str, end: str) -> pd.DataFrame:
    query = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon,
        "start_date": start, "end_date": end,
        "hourly": ",".join(VARIABLES),
        "timezone": "Asia/Taipei",
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"{URL}?{query}", timeout=120) as response:
                data = json.load(response)["hourly"]
            break
        except Exception as error:  # noqa: BLE001
            print("  loi, thu lai:", error)
            time.sleep(10)
    else:
        raise SystemExit("Tai that bai")
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    return df.set_index("time")


def main(start: str, end: str, out_path: str) -> None:
    frames = []
    for name, (lat, lon) in POINTS.items():
        print(f"Dang tai {name} ({start} -> {end})")
        frames.append(fetch_point(lat, lon, start, end).add_prefix(f"{name}__"))
        time.sleep(2)  # tranh vuot gioi han goi API
    wide = pd.concat(frames, axis=1)
    # Bien tom tat cho mo hinh: trung binh 3 trung tam phu tai, buc xa vung nang, gio ven bien.
    load_centres = ["taipei", "taichung", "kaohsiung"]
    wide["temp_load_mean"] = wide[[f"{c}__temperature_2m" for c in load_centres]].mean(axis=1)
    wide["radiation_solar"] = wide["tainan_solar__shortwave_radiation"]
    wide["wind_coast"] = wide["changhua_wind__wind_speed_100m"]
    wide.to_parquet(out_path)
    print(f"Da luu {out_path}: {wide.shape[0]:,} gio, {wide.shape[1]} cot")
    print("Thieu du lieu (%):", round(wide.isna().mean().max() * 100, 2))


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Cach dung: python fetch_weather.py <tu_ngay> <den_ngay> <file_ra.parquet>")
    main(*sys.argv[1:])