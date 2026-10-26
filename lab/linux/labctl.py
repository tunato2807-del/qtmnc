#!/usr/bin/env python3
"""Bounded lab stimuli. Run on the Linux VM, not on the monitoring Windows host."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

DEMO=Path("/var/lib/qtmnc-lab/temperature.json")


def ram_bytes(total,available,target=70):
    requested=max(0,round(available-total*(1-target/100)))
    return min(requested,int(available*.75))


def stop(signum,frame):
    raise KeyboardInterrupt


def demo_temperature(value,seconds,path=DEMO):
    if not -20<=value<=120 or not 5<=seconds<=600:
        raise ValueError("Nhiệt độ demo -20..120°C; thời gian 5..600s")
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
    fd,tmp=tempfile.mkstemp(prefix=".temperature-",dir=path.parent)
    try:
        with os.fdopen(fd,"w") as f:
            json.dump({"celsius":value,"baseline":40,"expires_at":time.time()+seconds},f)
        os.chmod(tmp,0o644)
        os.replace(tmp,path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def interface_test(iface,management_host,seconds):
    if not re.fullmatch(r"[A-Za-z0-9_.:@-]{1,64}",iface) or iface=="lo":
        raise ValueError("Chỉ được chọn interface lab hợp lệ")
    ipaddress.IPv4Address(management_host)
    routes=json.loads(subprocess.check_output(["ip","-j","route","get",management_host],text=True))
    defaults=json.loads(subprocess.check_output(["ip","-j","route","show","default"],text=True))
    protected={r.get("dev") for r in routes+defaults}
    if iface in protected:
        raise ValueError("Từ chối hạ interface đang dùng để quản trị hoặc làm default route")
    flags=int((Path("/sys/class/net")/iface/"flags").read_text().strip(),16)
    if not flags&1:
        raise ValueError("Interface đã administratively down; không tự đổi trạng thái của nó")
    try:
        subprocess.run(["ip","link","set","dev",iface,"down"],check=True)
        print(f"{iface} DOWN; sẽ khôi phục sau {seconds}s hoặc Ctrl+C.",flush=True)
        time.sleep(seconds)
    finally:
        subprocess.run(["ip","link","set","dev",iface,"up"],check=True)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    cpu=sub.add_parser("cpu")
    cpu.add_argument("--cores",type=int,default=min(os.cpu_count() or 1,4))
    cpu.add_argument("--seconds",type=int,default=60)
    ram=sub.add_parser("ram")
    ram.add_argument("--target",type=float,default=70)
    ram.add_argument("--seconds",type=int,default=90)
    temp=sub.add_parser("temperature")
    temp.add_argument("--celsius",type=float,default=75)
    temp.add_argument("--seconds",type=int,default=90)
    iface=sub.add_parser("interface")
    iface.add_argument("--iface",required=True)
    iface.add_argument("--management-host",default="192.168.10.1")
    iface.add_argument("--seconds",type=int,default=45)
    a=p.parse_args(argv)
    if sys.platform!="linux":
        p.error("Chạy bài thử trên máy ảo Linux")
    if not 5<=a.seconds<=600:
        p.error("Thời gian phải trong 5..600 giây")
    signal.signal(signal.SIGTERM,stop)
    children=[]
    try:
        if a.action=="temperature":
            demo_temperature(a.celsius,a.seconds)
            print(f"MÔ PHỎNG nhiệt độ {a.celsius}°C trong {a.seconds}s; sau đó về baseline demo 40°C.")
            print("Chỉ có tác dụng khi cấu hình TEMP_SOURCE=demo; không phải nhiệt độ phần cứng.")
        elif a.action=="interface":
            interface_test(a.iface,a.management_host,a.seconds)
        elif a.action=="ram":
            if not 40<=a.target<=80:
                p.error("Mục tiêu RAM phải trong 40..80%")
            info={line.split()[0].rstrip(":"):int(line.split()[1])*1024 for line in Path("/proc/meminfo").read_text().splitlines()}
            size=ram_bytes(info["MemTotal"],info["MemAvailable"],a.target)
            print(f"Cấp phát có giới hạn khoảng {size/1024**2:.0f} MiB, giữ {a.seconds}s.",flush=True)
            data=bytearray(size)
            for i in range(0,size,4096):
                data[i]=1
            time.sleep(a.seconds)
            del data
        else:
            if not 1<=a.cores<=min(os.cpu_count() or 1,64):
                p.error("Số core phải phù hợp số vCPU của máy ảo")
            program="import time,sys\\ndeadline=time.monotonic()+float(sys.argv[1])\\nwhile time.monotonic()<deadline:\\n sum(i*i for i in range(10000))".replace("\\n","\n")
            for _ in range(a.cores):
                children.append(subprocess.Popen([sys.executable,"-c",program,str(a.seconds)]))
            print(f"Tạo tải {a.cores} vCPU trong {a.seconds}s; Ctrl+C để dừng sớm.",flush=True)
            for child in children:
                child.wait()
    except KeyboardInterrupt:
        print("Đã dừng bài thử.")
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
            child.wait()


if __name__=="__main__":
    try:
        main()
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        print(f"Bài thử chưa thực hiện được ({type(exc).__name__}): {exc}",file=sys.stderr)
        raise SystemExit(2)
