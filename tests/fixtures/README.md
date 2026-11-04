`gns3-project-schema.json`: GNS3 project revision 9 schema, từ GNS3/gns3-server commit `9c6a0c7be42629fd0c72fab1e3376c34f7dd1681`, `docs/gns3_file.json`.

`gns3-vmware-properties.json`: các trường thuộc `VMWARE_OBJECT_SCHEMA` trong `gns3server/schemas/vmware.py`, tag v2.2.61; dùng kiểm tra properties đã sinh, không bao gồm custom_adapters vì generator không dùng trường đó.

Nguồn GNS3 GPL-3.0: https://github.com/GNS3/gns3-server. Các schema chỉ phục vụ xác thực định dạng; không chứng minh VM đã chạy trên VMware.
