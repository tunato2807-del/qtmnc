#!/usr/bin/env python3
"""Tạo tải có thời hạn trên VM lab để kiểm tra cảnh báo; không cần sudo."""
import argparse
import multiprocessing
import time
from pathlib import Path


def memory():
    data = {line.split(":")[0]: int(line.split()[1]) * 1024 for line in Path("/proc/meminfo").read_text().splitlines() if ":" in line}
    return data["MemTotal"], data["MemAvailable"]


def burn(seconds):
    until = time.monotonic() + seconds
    value = 1
    while time.monotonic() < until:
        for _ in range(10000):
            value = (value * 17 + 31) % 1000000007


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("cpu", "ram"))
    parser.add_argument("--seconds", type=int, default=45, choices=range(5, 121), metavar="5..120")
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 5))
    parser.add_argument("--target", type=int, default=75, choices=range(50, 81))
    args = parser.parse_args()
    if args.kind == "cpu":
        processes = [multiprocessing.Process(target=burn, args=(args.seconds,)) for _ in range(args.workers)]
        try:
            for process in processes:
                process.start()
            print(f"Đang tạo tải CPU {args.seconds}s; tự dừng, Ctrl+C để dừng sớm.", flush=True)
            for process in processes:
                process.join()
        finally:
            for process in processes:
                if process.is_alive():
                    process.terminate()
                process.join()
    else:
        total, available = memory()
        budget = min(768 * 1024**2, max(0, available - 200 * 1024**2), int(available * .7))
        blocks, allocated = [], 0
        try:
            while allocated < budget:
                total, available = memory()
                if 100 * (total - available) / total >= args.target or available < 220 * 1024**2:
                    break
                size = min(16 * 1024**2, budget - allocated)
                block = bytearray(size)
                for position in range(0, size, 4096):
                    block[position] = 1
                blocks.append(block)
                allocated += size
            print(f"Đã giữ {allocated // 1024**2} MiB trong {args.seconds}s; giới hạn 768 MiB và giữ dự phòng RAM.", flush=True)
            print("Nếu chưa đạt ngưỡng: giảm tải nền hoặc giảm ngưỡng thử nghiệm trong inventory, không tăng vô hạn.", flush=True)
            time.sleep(args.seconds)
        finally:
            blocks.clear()
    print("Đã kết thúc tải thử.")


if __name__ == "__main__":
    main()
