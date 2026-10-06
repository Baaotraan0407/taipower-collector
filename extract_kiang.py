"""Trich toan bo lich su file docs/genary.json tu repo kiang/taipower_data.

Repo ghi de docs/genary.json moi 10 phut tu 22/10/2024; moi commit la mot anh chup.
Script lay noi dung file o tung commit va luu thanh:
    <out_dir>/raw/YYYY-MM/YYYY-MM-DD/HHMM.json.gz   (gio Dai Loan)
giong cau truc cua collect.py, de dung chung process_genary.py.

Cach dung tren Colab:
    !git clone --bare https://github.com/kiang/taipower_data.git kiang.git
    !python extract_kiang.py kiang.git kiang_out
"""
import datetime as dt
import gzip
import subprocess
import sys
from pathlib import Path

FILE_PATH = "docs/genary.json"
TZ_TAIWAN = dt.timezone(dt.timedelta(hours=8))


def list_commits(repo: str) -> list[tuple[str, dt.datetime]]:
    """Tra ve (sha, thoi diem commit theo gio Dai Loan), tu cu den moi."""
    output = subprocess.run(
        ["git", "-C", repo, "log", "--reverse", "--format=%H %cI", "--", FILE_PATH],
        capture_output=True, text=True, check=True,
    ).stdout
    commits = []
    for line in output.splitlines():
        sha, stamp = line.split(" ", 1)
        commits.append((sha, dt.datetime.fromisoformat(stamp).astimezone(TZ_TAIWAN)))
    return commits


def iter_blobs(repo: str, commits):
    """Doc noi dung file o tung commit bang mot tien trinh git cat-file duy nhat (nhanh)."""
    proc = subprocess.Popen(
        ["git", "-C", repo, "cat-file", "--batch"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    )
    for sha, when in commits:
        proc.stdin.write(f"{sha}:{FILE_PATH}\n".encode())
        proc.stdin.flush()
        header = proc.stdout.readline().decode().split()
        if len(header) < 3 or header[1] != "blob":
            yield sha, when, None, None
            continue
        size = int(header[2])
        content = proc.stdout.read(size)
        proc.stdout.read(1)  # ky tu xuong dong sau noi dung
        yield sha, when, header[0], content
    proc.stdin.close()
    proc.wait()


def main(repo: str, out_dir: str) -> None:
    commits = list_commits(repo)
    print(f"So commit sua {FILE_PATH}: {len(commits)}")
    if commits:
        print(f"Tu {commits[0][1]} den {commits[-1][1]}")

    out = Path(out_dir) / "raw"
    saved, skipped_same, missing = 0, 0, 0
    last_oid = None
    for i, (sha, when, oid, content) in enumerate(iter_blobs(repo, commits), start=1):
        if content is None:
            missing += 1
            continue
        if oid == last_oid:  # noi dung khong doi so voi lan truoc
            skipped_same += 1
            continue
        last_oid = oid
        folder = out / f"{when:%Y-%m}" / f"{when:%Y-%m-%d}"
        folder.mkdir(parents=True, exist_ok=True)
        with gzip.open(folder / f"{when:%H%M}.json.gz", "wb") as file:
            file.write(content)
        saved += 1
        if i % 10000 == 0:
            print(f"  da xu ly {i:,}/{len(commits):,} commit")

    print(f"Da luu {saved:,} file | bo qua {skipped_same:,} ban trung | thieu {missing:,}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Cach dung: python extract_kiang.py <repo_bare> <thu_muc_ket_qua>")
    main(sys.argv[1], sys.argv[2])