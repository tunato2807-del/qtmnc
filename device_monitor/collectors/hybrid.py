"""Combine SSH and SNMP while making partial transport failures visible."""
from ..errors import DeviceUnavailable
from ..models import Sample


class HybridCollector:
    def __init__(self, config, ssh=None, snmp=None):
        from .ssh import SSHCollector
        from .snmp import SNMPCollector
        self.c=config
        self.ssh=ssh if ssh is not None else SSHCollector(config)
        self.snmp=snmp if snmp is not None else SNMPCollector(config)

    def close(self):
        self.ssh.close()

    def collect(self):
        samples, failures={},{}
        for name,collector in (("ssh",self.ssh),("snmp",self.snmp)):
            try:
                samples[name]=collector.collect()
            except DeviceUnavailable as exc:
                failures[name]=str(exc)
        if not samples:
            raise DeviceUnavailable("Cả SSH và SNMP đều không thu thập được; kiểm tra đường quản trị GNS3")
        values,errors,sources={},{},{}
        metrics=["cpu","ram","iface"]+(["temp"] if self.c.temp_enabled else [])
        for metric in metrics:
            order=("snmp","ssh") if metric=="iface" else ("ssh","snmp")
            choices=[(name,samples[name]) for name in order if name in samples]
            chosen=next(((name,sample) for name,sample in choices if sample.values.get(metric) is not None), choices[0])
            name,sample=chosen
            values[metric]=sample.values.get(metric)
            sources[metric]=sample.sources.get(metric,name.upper())
            if metric in sample.errors:
                errors[metric]=sample.errors[metric]
        for name in ("ssh","snmp"):
            values[name]="down" if name in failures else "up"
            sources[name]="Transport"
            if name in failures:
                errors[name]=failures[name]
        return Sample(values,errors,sources)
