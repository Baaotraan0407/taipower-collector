"""Chuyen du lieu tho Taipower (dataset 8931) thanh bang sach.

Xu ly 3 diem:
  1. Bo cac dong tong phu (小計) de khong cong trung.
  2. Tach luu tru pin: phat (storageGen) va sac (storageLoad, gia tri am = phu tai).
  3. Quy doi nhom nguon tieng Trung sang ma cua bo Zenodo (coal, lng, ippLng...).

Cach dung (Colab hoac may tinh):
    python process_genary.py <thu_muc_raw> <thu_muc_ket_qua>

Ket qua:
    units_10min.parquet : tung to may, moi 10 phut (de tach CC/GT khi tinh CI)
    wide_10min.parquet  : tong theo nhom nguon, cot giong bo Zenodo
    unmapped_types.csv  : nhom nguon chua co trong bang quy doi (neu co)
"""
import gzip
import json
import re
import sys
from pathlib import Path

import pandas as pd

# Bang quy doi: ten nhom cua Taipower -> ma cot cua bo Zenodo.
# Cac ma moi (storageGen, storageLoad, pumpLoad, otherRenew) khong co trong Zenodo.
TYPE_MAP = {
    "燃煤": "coal",
    "民營電廠-燃煤": "ippCoal",
    "燃氣": "lng",
    "民營電廠-燃氣": "ippLng",
    "汽電共生": "coGen",
    "燃油": "oil",
    "燃料油": "oil",
    "輕油": "diesel",
    "柴油": "diesel",
    "核能": "nuclear",
    "水力": "hydro",
    "抽蓄發電": "pumpGen",
    "抽蓄負載": "pumpLoad",
    "太陽能": "solar",
    "風力": "wind",
    "地熱": "otherRenew",
    "其它再生能源": "otherRenew",
    "儲能": "storageGen",
    "儲能負載": "storageLoad",
}

# Thu tu cot dau ra: cac cot cua Zenodo truoc, cot moi sau.
ZENODO_COLUMNS = [
    "hydro", "solar", "diesel", "coal", "nuclear", "pumpGen",
    "ippLng", "ippCoal", "coGen", "lng", "oil", "wind",
]
NEW_COLUMNS = ["pumpLoad", "storageGen", "storageLoad", "otherRenew"]


def clean_type(raw: str) -> str:
    """Bo the HTML va phan chu tieng Anh trong ngoac, vd '儲能負載(Energy ...)</b>'."""
    text = re.sub(r"<[^>]+>", "", str(raw))
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()


DIESEL_HINTS = ("GAS", "澎湖", "金門", "馬祖", "離島", "蘭嶼", "綠島")


def split_oil(category: str, unit: str) -> str:
    """Nhom 燃料油 gop ca dau nang va dau nhe. Tuabin chay dau (ten co 'Gas')
    va may phat diesel o dao duoc xep vao 'diesel' cho giong bo Zenodo."""
    if category == "oil" and any(hint in unit.upper() for hint in DIESEL_HINTS):
        return "diesel"
    return category


def gas_subtype(category: str, unit: str) -> str:
    """Tach loai to may khi: chu trinh hon hop (cc), tuabin khi don (gt),
    hoac loai khac (other, vd to may hoi dot khi kieu cu nhu 大林#5, #6).
    Cac nha may khi IPP deu la chu trinh hon hop."""
    if category == "ippLng":
        return "cc"
    if category != "lng":
        return ""
    name = unit.upper()
    if "CC" in name:
        return "cc"
    if "GT" in name:
        return "gt"
    return "other"


def time_from_path(path: Path) -> str:
    """Suy thoi diem tu duong dan .../YYYY-MM-DD/HHMM.json.gz."""
    hhmm = path.name.split(".")[0]
    return f"{path.parent.name} {hhmm[:2]}:{hhmm[2:4]}"


def read_file(path: Path) -> pd.DataFrame:
    with gzip.open(path, "rb") as file:
        data = json.loads(file.read().decode("utf-8-sig"))
    df = pd.DataFrame(data["aaData"])
    # Link service: 6 cot (loai, ten, cong suat, san luong, ty le, ghi chu).
    # Link www (genary.json cu, repo kiang): 7 cot, cot thu 2 de trong.
    if df.shape[1] >= 7:
        blank_second = (df.iloc[:, 1].astype(str).str.strip() == "").mean() > 0.5
        df = df.iloc[:, [0, 2, 3, 4, 5, 6]] if blank_second else df.iloc[:, :6]
    else:
        df = df.iloc[:, :6]
    df.columns = ["type_raw", "unit", "capacity_mw", "net_mw", "ratio", "note"]
    # Dinh dang moi dung khoa "DateTime"; ban genary cu dung khoa rong "".
    stamp = data.get("DateTime") or data.get("") or time_from_path(path)
    df["datetime"] = pd.to_datetime(stamp)
    df["source_file"] = path.name
    return df


def process(raw_dir: Path, out_dir: Path) -> None:
    files = sorted(raw_dir.rglob("*.json.gz"))
    if not files:
        raise SystemExit(f"Khong tim thay file .json.gz trong {raw_dir}")

    frames, failed = [], []
    for path in files:
        try:
            frames.append(read_file(path))
        except Exception as error:  # noqa: BLE001
            failed.append((str(path), str(error)))
    df = pd.concat(frames, ignore_index=True)

    # Diem 1: bo dong tong phu.
    df["unit"] = df["unit"].astype(str).str.strip()
    df = df[~df["unit"].str.contains("小計|合計|總計")]

    df["type"] = df["type_raw"].map(clean_type)
    df["category"] = df["type"].map(TYPE_MAP)
    df["category"] = [split_oil(c, u) for c, u in zip(df["category"], df["unit"])]
    df["net_mw"] = pd.to_numeric(df["net_mw"], errors="coerce")
    df["capacity_mw"] = pd.to_numeric(df["capacity_mw"], errors="coerce")

    # Kiem tra lech cot: san luong khong the bang dung cong suat o hau het dong.
    has_cap = df["capacity_mw"] > 0
    same = (df.loc[has_cap, "net_mw"] == df.loc[has_cap, "capacity_mw"]).mean()
    if has_cap.any() and same > 0.5:
        print(f"CANH BAO lech cot: {same:.0%} dong co san luong = cong suat. Kiem tra dinh dang file.")

    # Diem 2: phan sac pin la phu tai, giu dau am de phan biet.
    is_load = df["category"].isin(["storageLoad", "pumpLoad"])
    df.loc[is_load, "net_mw"] = -df.loc[is_load, "net_mw"].abs()

    df["gas_type"] = [gas_subtype(c, u) for c, u in zip(df["category"], df["unit"])]

    # Mot thoi diem co the bi tai 2 lan neu lich chay bi tre: giu ban dau tien.
    df = df.drop_duplicates(["datetime", "type", "unit"])

    out_dir.mkdir(parents=True, exist_ok=True)

    unmapped = df[df["category"].isna()]
    if not unmapped.empty:
        unmapped[["type"]].value_counts().to_csv(out_dir / "unmapped_types.csv")

    units = df[[
        "datetime", "type", "category", "gas_type", "unit",
        "capacity_mw", "net_mw", "note",
    ]].sort_values(["datetime", "category", "unit"])
    units.to_parquet(out_dir / "units_10min.parquet", index=False)

    # Diem 3: bang rong theo ma Zenodo.
    wide = (
        df.dropna(subset=["category"])
        .pivot_table(index="datetime", columns="category", values="net_mw", aggfunc="sum")
        .reindex(columns=ZENODO_COLUMNS + NEW_COLUMNS)
        .fillna(0.0)
        .sort_index()
    )
    wide.to_parquet(out_dir / "wide_10min.parquet")

    print(f"So file doc duoc: {len(frames)} / {len(files)}")
    for path, error in failed[:5]:
        print("  Loi:", path, error)
    print(f"So thoi diem: {wide.shape[0]} | tu {wide.index.min()} den {wide.index.max()}")
    if unmapped.empty:
        print("Tat ca nhom nguon deu da quy doi.")
    else:
        print("CANH BAO, nhom nguon chua quy doi:", sorted(unmapped["type"].unique()))
    print("\nTong theo nhom (MW), thoi diem moi nhat:")
    print(wide.iloc[-1].round(1).to_string())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Cach dung: python process_genary.py <thu_muc_raw> <thu_muc_ket_qua>")
    process(Path(sys.argv[1]), Path(sys.argv[2]))