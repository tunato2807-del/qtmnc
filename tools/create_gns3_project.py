#!/usr/bin/env python3
"""Generate an editable GNS3 2.2+ local-server lab; no VM or router images required."""
import argparse
import json
from pathlib import Path
import urllib.parse
import urllib.request
import uuid

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
    p.add_argument("--server",default="http://127.0.0.1:3080")
    a=p.parse_args()
    if a.output is None:
        name="QTMNC_TAP" if a.tap else "QTMNC_SIMPLE" if a.simple else "QTMNC_GNS3_MONITOR"
        a.output=ROOT/"lab/generated"/name/(name+".gns3")
    if a.output.exists():
        p.error("File đã tồn tại; chọn --output mới để giữ công việc GNS3 đã chỉnh")
    indices = (2,) if a.tap else (1,2) if a.simple else (1,2,3)
    names=local_interfaces(a.server, indices) if a.check_local_api else None
    value=(tap_project if a.tap else simple_project if a.simple else project)(names)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    print(a.output)
    if a.tap:
        print("Cloud-WINDOWS dùng UDP 30010 -> 127.0.0.1:30011; chạy run_tap_windows.cmd.")
    else:
        print("Mở file này trong GNS3 local server; kiểm tra Cloud đúng VMnet1/2" + ("." if a.simple else "/3."))
    print("Linux VM chạy riêng trong VMware, không được tự tạo hay tự bật bởi file lab.")
    print("Đọc docs/GNS3_LAB.md trước khi đổi card mạng hoặc nối link.")


if __name__=="__main__":
    main()
