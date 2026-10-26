from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
from ..errors import DataError, DeviceUnavailable
from ..validation import number
from ..models import Sample

IF_NAME="1.3.6.1.2.1.31.1.1.1.1"
IF_OPER_STATUS="1.3.6.1.2.1.2.2.1.8"

def interface_state(raw):
    code=number(raw,1,7)
    if code!=int(code):
        raise DataError("ifOperStatus không hợp lệ")
    return {1:"up",2:"down",3:"testing",4:"unknown",5:"dormant",6:"notpresent",7:"lowerlayerdown"}[int(code)]

class SNMPCollector:
    """Numeric OIDs must be selected from the monitored device's MIB documentation."""
    def __init__(self, config):
        from pysnmp.hlapi.v3arch import asyncio as api
        self.api, self.c = api, config
        self.ifindex=None

    @asynccontextmanager
    async def session(self):
        a,c=self.api,self.c
        engine=a.SnmpEngine()
        try:
            auth=(a.UsmUserData(c.snmp_user,c.snmp_auth_key,c.snmp_priv_key,authProtocol=a.usmHMACSHAAuthProtocol,privProtocol=a.usmAesCfb128Protocol) if c.snmp_version=="3" else a.CommunityData(c.snmp_community,mpModel=1))
            target=await a.UdpTransportTarget.create((c.host,c.snmp_port),timeout=c.timeout,retries=1)
            yield a,engine,auth,target
        except (DeviceUnavailable,DataError):
            raise
        except Exception as exc:
            raise DeviceUnavailable(f"Không thu thập được SNMP ({type(exc).__name__})") from None
        finally:
            engine.close_dispatcher()

    async def get(self,session,oids):
        a,engine,auth,target=session
        indication,status,index,bindings=await a.get_cmd(engine,auth,target,a.ContextData(),*(a.ObjectType(a.ObjectIdentity(oid)) for oid in oids),lookupMib=False)
        if indication:
            raise DeviceUnavailable("SNMP không phản hồi hoặc xác thực thất bại")
        if status or len(bindings)!=len(oids):
            raise DataError("SNMP agent trả lỗi hoặc thiếu dữ liệu; kiểm tra quyền đọc/OID")
        return [binding[1].prettyPrint() for binding in bindings]

    async def discover_interface(self,session):
        a,engine,auth,target=session
        count=0
        async for indication,status,index,bindings in a.walk_cmd(engine,auth,target,a.ContextData(),a.ObjectType(a.ObjectIdentity(IF_NAME)),lexicographicMode=False,lookupMib=False,maxRows=256):
            if indication:
                raise DeviceUnavailable("SNMP không phản hồi khi tìm interface")
            if status:
                raise DataError("Không có quyền đọc IF-MIB")
            for oid,value in bindings:
                count+=1
                nums=tuple(int(x) for x in oid)
                if nums[:-1]!=tuple(map(int,IF_NAME.split('.'))):
                    break
                if value.prettyPrint()==self.c.iface:
                    self.ifindex=nums[-1]
                    return self.ifindex
            if count>=256:
                break
        raise DataError("Không tìm thấy MONITOR_IFACE trong IF-MIB::ifName")

    async def linux_interface(self,session):
        if self.c.oids.get("iface"):
            return interface_state((await self.get(session,[self.c.oids["iface"]]))[0])
        if self.ifindex is not None:
            name,status=await self.get(session,[f"{IF_NAME}.{self.ifindex}",f"{IF_OPER_STATUS}.{self.ifindex}"])
            if name==self.c.iface:
                return interface_state(status)
            self.ifindex=None
        index=await self.discover_interface(session)
        name,status=await self.get(session,[f"{IF_NAME}.{index}",f"{IF_OPER_STATUS}.{index}"])
        if name!=self.c.iface:
            raise DataError("ifIndex thay đổi trong khi lấy mẫu; thử lại chu kỳ sau")
        return interface_state(status)

    async def _fetch_linux(self):
        values,errors,sources={},{},{}
        async with self.session() as session:
            payload=(await self.get(session,[self.c.snmp_extend_oid]))[0]
            try:
                data=json.loads(payload)
                if not isinstance(data,dict) or data.get("version")!=1 or not isinstance(data.get("values"),dict):
                    raise ValueError
                raw=data["values"]
                metadata=data.get("sources",{})
                if not isinstance(metadata,dict):
                    metadata={}
            except (ValueError,TypeError):
                raw,metadata={},{}
            for metric in ["cpu","ram"]+(["temp"] if self.c.temp_enabled else []):
                try:
                    values[metric]=number(raw.get(metric),-50 if metric=="temp" else 0,200 if metric=="temp" else 100)
                except DataError:
                    values[metric]=None
                    errors[metric]="Thiếu dữ liệu từ extend qtmnc; kiểm tra Linux probe/cảm biến"
                sources[metric]="SNMP / DEMO" if metric=="temp" and "DEMO" in str(metadata.get(metric,"")).upper() else "SNMP"
            try:
                values["iface"]=await self.linux_interface(session)
            except DataError as exc:
                values["iface"],errors["iface"]=None,str(exc)
            sources["iface"]="SNMP / IF-MIB"
        return Sample(values,errors,sources)

    async def _fetch(self):
        a, c = self.api, self.c
        engine = a.SnmpEngine()
        try:
            auth = (a.UsmUserData(c.snmp_user, c.snmp_auth_key, c.snmp_priv_key,
                                authProtocol=a.usmHMACSHAAuthProtocol,
                                privProtocol=a.usmAesCfb128Protocol)
                    if c.snmp_version == "3" else a.CommunityData(c.snmp_community, mpModel=1))
            target = await a.UdpTransportTarget.create((c.host, c.snmp_port), timeout=c.timeout, retries=1)
            requested = {k: v for k, v in c.oids.items() if c.temp_enabled or k != "temp"}
            # Numeric OIDs avoid runtime MIB downloads.
            indication, status, index, bindings = await a.get_cmd(
                engine, auth, target, a.ContextData(),
                *(a.ObjectType(a.ObjectIdentity(oid)) for oid in requested.values()), lookupMib=False)
            if indication:
                raise DeviceUnavailable("SNMP không phản hồi hoặc xác thực thất bại")
            if status:
                raise DataError("SNMP agent trả về lỗi truy vấn; kiểm tra quyền đọc và OID")
            if len(bindings) != len(requested):
                raise DeviceUnavailable("SNMP trả về thiếu varbind")
            return {name: binding[1].prettyPrint() for name, binding in zip(requested, bindings)}
        except (DeviceUnavailable, DataError):
            raise
        except Exception as exc:
            raise DeviceUnavailable(f"Không thu thập được SNMP ({type(exc).__name__})") from None
        finally:
            engine.close_dispatcher()

    def collect(self):
        metrics = ["cpu", "ram", "iface"] + (["temp"] if self.c.temp_enabled else [])
        try:
            if self.c.snmp_profile=="linux-extend":
                return asyncio.run(self._fetch_linux())
            raw = asyncio.run(self._fetch())
        except DataError as exc:
            # A responding agent rejecting a query is not a disconnected device.
            return Sample({metric: None for metric in metrics}, {metric: str(exc) for metric in metrics})
        values, errors = {}, {}
        for metric in metrics:
            try:
                if metric == "ram" and "ram" not in raw:
                    used, total = number(raw.get("ram_used"), 0), number(raw.get("ram_total"), 0)
                    if total <= 0:
                        raise DataError("Tổng RAM không hợp lệ")
                    value = number(100 * used / total, 0, 100)
                elif metric == "iface":
                    code = number(raw.get(metric), 1, 7)
                    if code != int(code):
                        raise DataError("ifOperStatus không hợp lệ")
                    value = {1: "up", 2: "down", 3: "testing", 4: "unknown", 5: "dormant", 6: "notpresent", 7: "lowerlayerdown"}[int(code)]
                elif metric == "temp":
                    value = number(number(raw.get(metric)) * self.c.temp_scale, -50, 200)
                else:
                    value = number(raw.get(metric), 0, 100)
                values[metric] = value
            except DataError as exc:
                values[metric], errors[metric] = None, str(exc)
        return Sample(values, errors, {metric:"SNMP" for metric in metrics})
