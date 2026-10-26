"""GNS3-oriented behaviour: mixed collectors, labelled simulations and safe lab tools."""
import asyncio
from contextlib import asynccontextmanager,redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,Mock,patch

import monitor_ssh as m
from device_monitor.collectors.hybrid import HybridCollector
from device_monitor.collectors.snmp import SNMPCollector,IF_NAME,IF_OPER_STATUS
from device_monitor.probe import read_temperature,collect_local
from lab.linux import labctl,configure_network,install_agent
from tools.create_gns3_project import project


def config(**kw):
    return m.Config(host="192.168.10.129",ssh_user="fixture",iface="gns3test",snmp_profile="linux-extend",**kw)


class GNS3Tests(unittest.TestCase):
    def test_profile_has_real_gns3_management_target_and_separate_test_interface(self):
        from dotenv import dotenv_values
        values=dict(dotenv_values("examples/gns3.env",interpolate=False))
        values.update(SSH_PASSWORD="fixture-only",TELEGRAM_TOKEN="123:fake_fixture",TELEGRAM_CHAT_ID="1000")
        c=m.Config.from_env(values)
        self.assertEqual((c.host,c.iface,c.interval),("192.168.10.129","gns3test",5))
        values["MONITOR_PROTOCOL"]="hybrid"
        values["SNMP_COMMUNITY"]="local-readonly"
        self.assertEqual(m.Config.from_env(values).protocol,"hybrid")

    def test_hybrid_selects_ssh_resources_and_snmp_interface(self):
        c=config(protocol="hybrid")
        ssh=Mock()
        snmp=Mock()
        ssh.collect.return_value=m.Sample({"cpu":81,"ram":70,"temp":None,"iface":"up"},{"temp":"missing"},{"cpu":"SSH"})
        snmp.collect.return_value=m.Sample({"cpu":80,"ram":69,"temp":75,"iface":"down"},{},{"temp":"SNMP / DEMO","iface":"SNMP / IF-MIB"})
        result=HybridCollector(c,ssh,snmp).collect()
        self.assertEqual(result.values["cpu"],81)
        self.assertEqual(result.values["iface"],"down")
        self.assertEqual(result.values["temp"],75)
        self.assertIn("DEMO",result.sources["temp"])
        self.assertEqual(result.values["ssh"],"up")
        self.assertEqual(result.values["snmp"],"up")

    def test_partial_transport_failure_is_visible_and_other_collector_survives(self):
        ssh,snmp=Mock(),Mock()
        ssh.collect.side_effect=m.DeviceUnavailable("SSH unavailable")
        snmp.collect.return_value=m.Sample({"cpu":40,"ram":50,"temp":45,"iface":"up"})
        result=HybridCollector(config(protocol="hybrid"),ssh,snmp).collect()
        self.assertEqual(result.values["cpu"],40)
        self.assertEqual(result.values["ssh"],"down")
        self.assertIn("ssh",result.errors)
        with tempfile.TemporaryDirectory() as d:
            store=m.Store(Path(d)/"state.db")
            messages=store.observe(config(protocol="hybrid"),result,["tg"])
            self.assertTrue(any("Kết nối SSH" in x for x in messages))

    def test_both_transports_unavailable_is_device_unreachable(self):
        ssh,snmp=Mock(),Mock()
        ssh.collect.side_effect=m.DeviceUnavailable("failed")
        snmp.collect.side_effect=m.DeviceUnavailable("failed")
        with self.assertRaises(m.DeviceUnavailable):
            HybridCollector(config(protocol="hybrid"),ssh,snmp).collect()

    def test_demo_temperature_expires_to_explicit_demo_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/"temperature.json"
            with patch("time.time",return_value=1000):
                labctl.demo_temperature(75,60,file)
                self.assertEqual(read_temperature("demo",file),75)
            with patch("time.time",return_value=1061):
                self.assertEqual(read_temperature("demo",file),40)
            file.write_text("[]")
            with self.assertRaises(m.DataError):
                read_temperature("demo",file)

    def test_absent_hardware_never_generates_temperature_zero(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(m.DataError):
                read_temperature("auto",sysroot=Path(d))

    def test_simulated_alert_and_recovery_always_labelled(self):
        c=config(temp_source="demo")
        with tempfile.TemporaryDirectory() as d:
            store=m.Store(Path(d)/"state.db")
            sample=m.Sample({"temp":75},{},{"temp":"SSH / DEMO"})
            messages=store.observe(c,sample,["tg"])
            self.assertIn("MÔ PHỎNG",messages[0])
            messages=store.observe(c,m.Sample({"temp":40},{},{"temp":"SSH / DEMO"}),["tg"])
            self.assertIn("MÔ PHỎNG",messages[0])
            self.assertIn("bình thường",messages[0])

    def test_agent_configuration_limits_source_and_does_not_allow_snmp_set(self):
        text=install_agent.configuration("192.168.10.129","192.168.10.1","gns3test","local-readonly")
        self.assertIn("192.168.10.1/32",text)
        self.assertIn("rocommunity",text)
        self.assertNotIn("rwcommunity",text)
        self.assertIn("extend qtmnc",text)
        for bad in ("x;id","space unsafe","short"):
            with self.assertRaises(ValueError):
                install_agent.configuration("192.168.10.129","192.168.10.1","gns3test",bad)

    def test_netplan_does_not_replace_nat_or_add_default_route(self):
        text=configure_network.netplan_text("00:50:56:11:22:33","00:50:56:44:55:66")
        self.assertIn("gns3mgmt",text)
        self.assertIn("gns3test",text)
        self.assertIn("192.168.10.129",text)
        self.assertNotIn("gateway4:",text)
        self.assertNotIn("ens33:",text)
        with self.assertRaises(ValueError):
            configure_network.netplan_text("00:50:56:11:22:33","00:50:56:11:22:33")

    def test_interface_stimulus_refuses_management_and_default_nics(self):
        for iface in ("gns3mgmt","ens33"):
            replies=['[{"dev":"gns3mgmt"}]','[{"dev":"ens33"}]']
            with patch("lab.linux.labctl.subprocess.check_output",side_effect=replies),patch("lab.linux.labctl.subprocess.run") as run:
                with self.assertRaises(ValueError):
                    labctl.interface_test(iface,"192.168.10.1",30)
                run.assert_not_called()

    def test_ram_stimulus_is_bounded_by_available_memory(self):
        self.assertEqual(labctl.ram_bytes(1000,550,70),250)
        self.assertEqual(labctl.ram_bytes(1000,100,70),0)
        self.assertLessEqual(labctl.ram_bytes(1000,1000,80),750)

    def test_gns3_project_uses_local_compute_and_distinct_cloud_networks(self):
        data=project()
        nodes=data["topology"]["nodes"]
        self.assertEqual(sum(n["node_type"]=="cloud" for n in nodes),3)
        self.assertEqual(sum(n["node_type"]=="ethernet_switch" for n in nodes),2)
        self.assertEqual(sum(n["node_type"]=="vpcs" for n in nodes),1)
        self.assertTrue(all(n["compute_id"]=="local" for n in nodes))
        ids={n["node_id"] for n in nodes}
        self.assertEqual(len(ids),6)
        for link in data["topology"]["links"]:
            self.assertTrue(all(p["node_id"] in ids for p in link["nodes"]))

    def test_linux_snmp_payload_and_if_mib_independent(self):
        c=config(protocol="snmp")
        collector=SNMPCollector(c)
        payload=json.dumps({"version":1,"values":{"cpu":80,"ram":70,"temp":75},"sources":{"temp":"DEMO"}})
        @asynccontextmanager
        async def session():
            yield None
        collector.session=session
        collector.get=AsyncMock(return_value=[payload])
        collector.linux_interface=AsyncMock(return_value="down")
        sample=asyncio.run(collector._fetch_linux())
        self.assertEqual(sample.values["iface"],"down")
        self.assertEqual(sample.values["ram"],70)
        self.assertIn("DEMO",sample.sources["temp"])
        collector.get=AsyncMock(return_value=["not-json"])
        sample=asyncio.run(collector._fetch_linux())
        self.assertIsNone(sample.values["ram"])
        self.assertEqual(sample.values["iface"],"down")

    def test_changed_ifindex_is_verified_then_rediscovered(self):
        collector=SNMPCollector(config(protocol="snmp"))
        collector.ifindex=2
        collector.get=AsyncMock(side_effect=[["different","1"],["gns3test","2"]])
        collector.discover_interface=AsyncMock(return_value=7)
        self.assertEqual(asyncio.run(collector.linux_interface(None)),"down")
        collector.discover_interface.assert_awaited_once()

    def test_notification_check_does_not_require_a_live_ssh_collector(self):
        with tempfile.TemporaryDirectory() as d:
            env={"MONITOR_HOST":"192.168.10.129","SSH_USER":"fixture",
                 "TELEGRAM_TOKEN":"123:fake_fixture","TELEGRAM_CHAT_ID":"1000",
                 "MONITOR_STATE_FILE":str(Path(d)/"state.sqlite3")}
            channel=Mock(key="tg",kind="telegram")
            channel.send.return_value=m.Delivery(True)
            with patch.dict(os.environ,env,clear=True),patch.object(m,"Channel",return_value=channel),patch.object(m,"make_collector") as factory:
                self.assertEqual(m.main(["--test-notifications"]),0)
            factory.assert_not_called()
            channel.send.assert_called_once()
            self.assertIn("KIỂM THỬ",channel.send.call_args.args[0])


if __name__=="__main__":
    unittest.main()
