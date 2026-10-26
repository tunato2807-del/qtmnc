"""Real SNMP GET/GETNEXT integration for the Linux JSON + IF-MIB collector."""
import asyncio
import json
import socket
import unittest
import monitor_ssh as m
import test_integration as fixture
from device_monitor.collectors.snmp import IF_NAME,IF_OPER_STATUS


@unittest.skipIf(fixture.snmp_api is None,"Install pysnmp")
class LinuxSNMPProtocolTests(unittest.TestCase):
    def exercise(self,version):
        async def run():
            a=fixture.snmp_api
            agent=fixture.engine.SnmpEngine()
            sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
            sock.bind(("127.0.0.1",0))
            port=sock.getsockname()[1]
            sock.setblocking(False)
            transport=fixture.udp.UdpTransport().open_server_mode(sock=sock)
            fixture.snmp_config.add_transport(agent,fixture.udp.DOMAIN_NAME,transport)
            fixture.snmp_config.add_v1_system(agent,"fixture","local-community")
            fixture.snmp_config.add_v3_user(agent,"fixture",a.usmHMACSHAAuthProtocol,"local-auth-key",a.usmAesCfb128Protocol,"local-priv-key")
            fixture.snmp_config.add_vacm_user(agent,2,"fixture","noAuthNoPriv",(1,3,6))
            fixture.snmp_config.add_vacm_user(agent,3,"fixture","authPriv",(1,3,6))
            c=m.Config(host="127.0.0.1",protocol="snmp",snmp_profile="linux-extend",
                       snmp_port=port,snmp_version=version,snmp_community="local-community",
                       snmp_user="fixture",snmp_auth_key="local-auth-key",snmp_priv_key="local-priv-key",
                       iface="gns3test",timeout=1)
            oid=lambda s:tuple(map(int,s.split(".")))
            payload=json.dumps({"version":1,"values":{"cpu":81.5,"ram":70,"temp":75},"sources":{"temp":"DEMO"}})
            values={
                oid(c.snmp_extend_oid):fixture.rfc1902.OctetString(payload),
                oid(IF_NAME+".1"):fixture.rfc1902.OctetString("lo"),
                oid(IF_NAME+".4"):fixture.rfc1902.OctetString("gns3test"),
                oid(IF_OPER_STATUS+".1"):fixture.rfc1902.Integer32(4),
                oid(IF_OPER_STATUS+".4"):fixture.rfc1902.Integer32(2),
            }
            class Instrumentation:
                def read_variables(self,*bindings,**kwargs):
                    return [(name,values.get(tuple(name),fixture.rfc1905.noSuchInstance)) for name,_ in bindings]
                def read_next_variables(self,*bindings,**kwargs):
                    result=[]
                    for name,_ in bindings:
                        nxt=next((key for key in sorted(values) if key>tuple(name)),None)
                        result.append((fixture.rfc1902.ObjectName(nxt),values[nxt]) if nxt else (name,fixture.rfc1905.endOfMibView))
                    return result
            ctx=fixture.context.SnmpContext(agent)
            ctx.unregister_context_name(b"")
            ctx.register_context_name(b"",Instrumentation())
            get=fixture.cmdrsp.GetCommandResponder(agent,ctx)
            getnext=fixture.cmdrsp.NextCommandResponder(agent,ctx)
            try:
                await transport._lport
                collector=m.SNMPCollector(c)
                sample=await collector._fetch_linux()
                self.assertEqual(sample.errors,{})
                self.assertEqual(sample.values,{"cpu":81.5,"ram":70.,"temp":75.,"iface":"down"})
                self.assertEqual(collector.ifindex,4)
                self.assertIn("DEMO",sample.sources["temp"])
                values[oid(IF_OPER_STATUS+".4")]=fixture.rfc1902.Integer32(1)
                recovered=await collector._fetch_linux()
                self.assertEqual(recovered.values["iface"],"up")
            finally:
                get.close(agent)
                getnext.close(agent)
                agent.close_dispatcher()
                await asyncio.sleep(0)
        asyncio.run(run())

    def test_v2c_linux_extend_and_interface_discovery(self):
        self.exercise("2c")

    def test_v3_linux_extend_and_interface_discovery(self):
        self.exercise("3")


if __name__=="__main__":
    unittest.main()
