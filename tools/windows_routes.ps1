param([switch]$Apply, [switch]$Remove)
$ErrorActionPreference = 'Stop'
if ($Apply -and $Remove) { throw 'Chọn -Apply hoặc -Remove.' }
$qtmncGateway = '192.168.73.10'
$qtmncAlias = 'VMware Network Adapter VMnet8'
$qtmncNetworks = @('10.10.10.0/24', '10.20.20.0/24')
$qtmncAdapter = Get-NetAdapter -Name $qtmncAlias
if ($qtmncAdapter.Status -ne 'Up') { throw 'VMnet8 chưa Up; kiểm tra VMware Virtual Network Editor.' }
$qtmncAddress = @(Get-NetIPAddress -InterfaceIndex $qtmncAdapter.ifIndex -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -like '192.168.73.*' -and $_.PrefixLength -eq 24 })
if ($qtmncAddress.Count -ne 1 -or $qtmncAddress[0].IPAddress -ne '192.168.73.1') {
    throw 'Thiết kế này cần VMnet8=192.168.73.1/24. Xem docs/01_GNS3.md; không tự đổi mạng đang dùng.'
}
if ($Apply -or $Remove) {
    $qtmncIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $qtmncPrincipal = New-Object Security.Principal.WindowsPrincipal($qtmncIdentity)
    if (-not $qtmncPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Mở PowerShell bằng Run as administrator.' }
}
foreach ($qtmncNetwork in $qtmncNetworks) {
    $qtmncRoutes = @(Get-NetRoute -DestinationPrefix $qtmncNetwork -AddressFamily IPv4 -PolicyStore ActiveStore -ErrorAction SilentlyContinue)
    $qtmncOwn = @($qtmncRoutes | Where-Object { $_.InterfaceIndex -eq $qtmncAdapter.ifIndex -and $_.NextHop -eq $qtmncGateway })
    if ($Remove) {
        $qtmncOwn | Remove-NetRoute -Confirm:$false
        Write-Host "Đã gỡ tuyến lab nếu tồn tại: $qtmncNetwork qua $qtmncGateway"
    } elseif ($Apply) {
        if (@($qtmncRoutes | Where-Object { $_.InterfaceIndex -ne $qtmncAdapter.ifIndex -or $_.NextHop -ne $qtmncGateway }).Count -gt 0) {
            throw "Có tuyến khác tới $qtmncNetwork; xem Get-NetRoute trước khi đổi. Không xóa tuyến khác tự động."
        }
        if ($qtmncOwn.Count -eq 0) {
            New-NetRoute -DestinationPrefix $qtmncNetwork -InterfaceIndex $qtmncAdapter.ifIndex -NextHop $qtmncGateway -RouteMetric 10 -PolicyStore ActiveStore | Out-Null
        }
        Write-Host "Đã có tuyến lab: $qtmncNetwork qua $qtmncGateway trên VMnet8"
    } else {
        Write-Host "Kế hoạch: $qtmncNetwork qua $qtmncGateway trên VMnet8; chỉ lưu tới khi Windows khởi động lại."
    }
}
if (-not $Apply -and -not $Remove) { Write-Host 'Thêm -Apply để áp dụng; -Remove để gỡ đúng hai tuyến trên.' }
