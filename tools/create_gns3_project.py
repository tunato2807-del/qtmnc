#!/usr/bin/env python3
"""Generate an editable GNS3 2.2+ local-server lab; no VM or router images required."""
import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request
import uuid
from xml.sax.saxutils import escape

ROOT=Path(__file__).resolve().parents[1]
NS=uuid.UUID("efb81918-060c-49aa-b21a-9b1a14d80f22")


def uid(name):
    return str(uuid.uuid5(NS,name))


def project(names=None):
    names={**{n:f"VMware Network Adapter VMnet{n}" for n in (1,2,3)}, **(names or {})}
    nodes=[]
    def node(name,kind,x,y,properties,symbol):
        value={"name":name,"node_id":uid(name),"node_type":kind,"compute_id":"local",
               "console_type":"telnet" if kind=="vpcs" else "none",
               "x":x,"y":y,"z":1,"symbol":symbol,"properties":properties,
               "label":{"text":name,"x":0,"y":-28,"rotation":0}}
        nodes.append(value)
        return value["node_id"]
    def cloud(label,index,x,y):
        return node(label,"cloud",x,y,{"ports_mapping":[{"name":f"VMnet{index}","port_number":0,"type":"ethernet","interface":names[index]}]},":/symbols/cloud.svg")
    def switch(label,x,y):
        return node(label,"ethernet_switch",x,y,{"ports_mapping":[{"name":f"Ethernet{i}","port_number":i,"type":"access","vlan":1} for i in range(4)]},":/symbols/ethernet_switch.svg")
    win=cloud("WINDOWS-VMNET1",1,-500,-120)
    mgmt=switch("SW-MANAGEMENT",-150,-120)
    linux=cloud("LINUX-MGMT-VMNET2",2,220,-120)
    data=cloud("LINUX-DATA-VMNET3",3,-500,150)
    lab=switch("SW-TEST",-150,150)
    vpc=node("VPCS-TEST","vpcs",220,150,{},":/symbols/vpcs_guest.svg")
    links=[]
    def connect(a,ap,b,bp):
        links.append({"link_id":uid(a+str(ap)+b+str(bp)),"nodes":[{"node_id":a,"adapter_number":0,"port_number":ap},{"node_id":b,"adapter_number":0,"port_number":bp}]})
    connect(win,0,mgmt,0)
    connect(mgmt,1,linux,0)
    connect(data,0,lab,0)
    connect(lab,1,vpc,0)
    return {"name":"QTMNC_GNS3_MONITOR","project_id":uid("project"),"type":"topology","revision":9,
            "version":"2.2.54","auto_start":False,"auto_close":True,"auto_open":False,
            "scene_width":1800,"scene_height":1000,"zoom":100,"show_interface_labels":True,
            "topology":{"computes":[{"compute_id":"local","name":"Local","protocol":"http","host":"127.0.0.1","port":3080}],
                        "nodes":nodes,"links":links,"drawings":[]}}


def simple_project(names=None):
    """The SSH lab needs only the management path: two Clouds and one switch."""
    value = project(names)
    keep = {"WINDOWS-VMNET1", "SW-MANAGEMENT", "LINUX-MGMT-VMNET2"}
    nodes = [node for node in value["topology"]["nodes"] if node["name"] in keep]
    ids = {node["node_id"] for node in nodes}
    value["name"] = "QTMNC_SIMPLE"
    value["project_id"] = uid("simple-project")
    value["topology"]["nodes"] = nodes
    value["topology"]["links"] = [
        link for link in value["topology"]["links"]
        if all(end["node_id"] in ids for end in link["nodes"])
    ]
    return value


def tap_project(names=None, cloud_port=30010, bridge_port=30011):
    """Windows receives Ethernet through TAP WriteFile, connected to a UDP Cloud."""
    if not all(1 <= port <= 65535 for port in (cloud_port, bridge_port)) or cloud_port == bridge_port:
        raise ValueError("Hai cổng UDP phải hợp lệ và khác nhau")
    value = simple_project(names)
    value["name"] = "QTMNC_TAP"
    value["project_id"] = uid("tap-project")
    for node in value["topology"]["nodes"]:
        if node["name"] == "WINDOWS-VMNET1":
            node["name"] = "Cloud-WINDOWS"
            node["properties"]["ports_mapping"] = [{
                "name": "TAP-UDP", "port_number": 0, "type": "udp",
                "lport": cloud_port, "rhost": "127.0.0.1", "rport": bridge_port,
            }]
        elif node["node_type"] == "ethernet_switch":
            node["name"] = "Switch1"
        else:
            node["name"] = "Cloud-LINUX"
        node["label"]["text"] = node["name"]
    return value


def course_project(names=None):
    """Seven lightweight nodes, distinct management/test L2 segments, no router image."""
    value=project(names)
    value["name"]="QTMNC_COURSE"
    value["project_id"]=uid("course-project")
    value["scene_height"]=1400
    nodes=value["topology"]["nodes"]
    for item in nodes:
        if item["name"]=="WINDOWS-VMNET1":
            item["name"]="Cloud-WINDOWS"
            item["properties"]["ports_mapping"]=[{"name":"TAP-UDP","port_number":0,"type":"udp",
                                                   "lport":30010,"rhost":"127.0.0.1","rport":30011}]
        elif item["name"]=="LINUX-MGMT-VMNET2":
            item["name"]="Cloud-LINUX-MGMT"
        elif item["name"]=="LINUX-DATA-VMNET3":
            item["name"]="Cloud-LINUX-LAB"
        elif item["name"]=="SW-TEST":
            item["name"]="SW-LAB"
        elif item["name"]=="VPCS-TEST":
            item["name"]="PC01"
        if item["node_type"]=="ethernet_switch":
            vlan=10 if item["name"]=="SW-MANAGEMENT" else 30
            for port in item["properties"]["ports_mapping"]:
                port["vlan"]=vlan
        item["label"]["text"]=item["name"]
    pc={"name":"PC02","node_id":uid("course-pc02"),"node_type":"vpcs","compute_id":"local",
        "console_type":"telnet","x":220,"y":330,"z":1,"symbol":":/symbols/vpcs_guest.svg",
        "properties":{},"label":{"text":"PC02","x":0,"y":-28,"rotation":0}}
    nodes.append(pc)
    switch=next(n for n in nodes if n["name"]=="SW-LAB")
    value["topology"]["links"].append({"link_id":uid("course-link-pc02"),"nodes":[
        {"node_id":switch["node_id"],"adapter_number":0,"port_number":2},
        {"node_id":pc["node_id"],"adapter_number":0,"port_number":0}]})
    def drawing(name,x,y,width,height,fill,stroke,lines):
        text="".join(f'<text x="20" y="{34+i*27}" font-family="DejaVu Sans" font-size="18" fill="#19354a">{escape(line)}</text>'
                     for i,line in enumerate(lines))
        return {"drawing_id":uid("course-drawing-"+name),"x":x,"y":y,"z":-1,"rotation":0,
                "svg":f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect x="1" y="1" width="{width-2}" height="{height-2}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="2"/>{text}</svg>'}
    value["topology"]["drawings"]=[
        drawing("management",-620,-235,1200,220,"#edf6fb","#7fadc1",["QUẢN TRỊ · ACCESS VLAN 10 · 192.168.10.0/24"]),
        drawing("lab",-620,40,1200,450,"#f0f2fc","#a19bce",["THỬ NGHIỆM · ACCESS VLAN 30 · 192.168.30.0/24"]),
        drawing("notes",-620,520,1200,115,"#f8fafc","#c6d3df",[
            "Một Ubuntu VMware: ens37 .10.129 | gns3test .30.129 | ens33 NAT / DHCP",
            "PC01 .30.10 | PC02 .30.20 · Hai Cloud Linux là hai card của cùng một VM",
            "Windows: TAP .10.1 · Dashboard http://127.0.0.1:8765 · Không có routing liên VLAN"]),
    ]
    return value


def local_interfaces(url, indices=(1,2,3)):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http","https"} or parsed.hostname not in {"localhost","127.0.0.1","::1"} or parsed.username or parsed.password:
        raise ValueError("Chỉ đọc API GNS3 local server, không đưa credential vào URL")
    request=urllib.request.Request(url.rstrip("/")+"/v2/compute/network/interfaces")
    with urllib.request.urlopen(request,timeout=5) as response:
        items=json.load(response)
    names={}
    for index in indices:
        matches=[item["name"] for item in items if str(item.get("name","")).lower().endswith(f"vmnet{index}")]
        if len(matches)!=1:
            raise ValueError(f"Chưa tìm thấy duy nhất VMnet{index}; tạo adapter trong VMware trước")
        names[index]=matches[0]
    return names


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path)
    p.add_argument("--check-local-api",action="store_true",help="Kiểm tra tên VMnet qua API GNS3 đang mở")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--simple", action="store_true", help="Chỉ hai Cloud và một switch")
    mode.add_argument("--tap", action="store_true", help="Windows TAP/UDP -> switch -> Cloud VMnet2")
    mode.add_argument("--course", action="store_true", help="Đồ án: TAP, hai vùng quản trị/thử nghiệm, hai VPCS")
    p.add_argument("--server",default="http://127.0.0.1:3080")
    a=p.parse_args()
    if a.output is None:
        name="QTMNC_COURSE" if a.course else "QTMNC_TAP" if a.tap else "QTMNC_SIMPLE" if a.simple else "QTMNC_GNS3_MONITOR"
        a.output=ROOT/"lab/generated"/name/(name+".gns3")
    if a.output.exists():
        p.error("File đã tồn tại; chọn --output mới để giữ công việc GNS3 đã chỉnh")
    indices = (2,3) if a.course else (2,) if a.tap else (1,2) if a.simple else (1,2,3)
    names=local_interfaces(a.server, indices) if a.check_local_api else None
    value=(course_project if a.course else tap_project if a.tap else simple_project if a.simple else project)(names)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(a.output)
    if a.tap or a.course:
        print("Cloud-WINDOWS dùng UDP 30010 -> 127.0.0.1:30011; chạy run_tap_windows.cmd.")
    else:
        print("Mở file này trong GNS3 local server; kiểm tra Cloud đúng VMnet1/2" + ("." if a.simple else "/3."))
    print("Linux VM chạy riêng trong VMware, không được tự tạo hay tự bật bởi file lab.")
    print("Đọc docs/GNS3_LAB.md trước khi đổi card mạng hoặc nối link.")


if __name__=="__main__":
    main()
