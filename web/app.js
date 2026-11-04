'use strict';
const $ = id => document.getElementById(id);
const clock = epoch => new Date(epoch * 1000).toLocaleTimeString('vi-VN', {hour12: false});
const number = (n, unit = '%') => typeof n === 'number' ? n.toFixed(1) + unit : '—';
const node = (tag, text, cls) => {const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e;};
let selected = '', inventoryReady = false, pending = false;
function badge(text, state) {return node('span', text, 'badge ' + state);}
function deviceCard(d, all, cfg) {
  const s = d.sample, fresh = d.freshness === 'fresh', connected = fresh && s && s.kind !== 'offline';
  const card = node('article', undefined, 'device'), head = node('div', undefined, 'device-head'), title = node('div');
  title.append(node('h3', d.name), node('div', d.host + ' · ' + d.protocol.toUpperCase(), 'address'));
  const state = !s ? 'Chờ mẫu đầu' : !fresh ? 'Dữ liệu đã cũ' : s.kind === 'offline' ? 'Mất kết nối' : s.kind === 'unknown' ? 'Lỗi đọc chỉ số' : 'Đã kết nối';
  head.append(title, badge(state, connected ? (s.kind === 'unknown' ? 'UNKNOWN' : 'OK') : s ? 'ALERT' : 'UNKNOWN')); card.append(head);
  const metrics = node('div', undefined, 'metric-grid');
  [['CPU','cpu_pct','%'],['RAM','ram_pct','%'],['Nhiệt độ','temperature_c','°C']].forEach(([label, key, unit]) => {
    const value = connected ? s[key] : null, level = connected ? s.states[key] || 'UNKNOWN' : 'UNKNOWN';
    const metric = node('div', undefined, 'metric ' + level);
    metric.append(node('p', label), node('strong', number(value, unit)), node('small', key === 'temperature_c' && !cfg.monitor_temperature ? 'Không bật cảnh báo' : 'Ngưỡng > ' + cfg.thresholds[key] + unit)); metrics.append(metric);
  }); card.append(metrics);
  d.interfaces.forEach(name => {
    const i = connected ? s.interfaces[name] || {} : {}, state = i.state || 'unknown';
    const row = node('div', undefined, 'interface');
    row.append(node('b', name), badge(state === 'unknown' ? 'N/A' : state.toUpperCase(), state === 'up' ? 'OK' : state === 'down' ? 'ALERT' : 'UNKNOWN'), node('span', '↓ ' + number(i.rx_mbps, '') + '  ↑ ' + number(i.tx_mbps, '') + ' Mbps', 'speed')); card.append(row);
  });
  if (s && (s.error || !fresh)) card.append(node('p', !fresh ? 'Mẫu cuối: ' + clock(s.at) + ' · kiểm tra tiến trình giám sát.' : s.error, 'device-note'));
  if (d.parent) {
    const parent = all.find(x => x.id === d.parent);
    if (!connected && parent && parent.sample && (parent.sample.kind === 'offline' || parent.freshness !== 'fresh')) card.append(node('p', 'R1 cũng đang mất dữ liệu; cần kiểm tra đường đi qua router.', 'device-note'));
  }
  return card;
}
const NS = 'http://www.w3.org/2000/svg';
function svg(tag, attrs, text) {const el = document.createElementNS(NS, tag); Object.entries(attrs).forEach(([k,v]) => el.setAttribute(k,v)); if(text !== undefined) el.textContent = text; return el;}
function drawChart(rows) {
  const chart = $('chart'); chart.replaceChildren();
  [0,25,50,75,100].forEach(v => {const y = 215 - v * 2; chart.append(svg('line',{x1:35,y1:y,x2:990,y2:y,stroke:'#e4ebf4'}),svg('text',{x:3,y:y+4,fill:'#7a889c','font-size':11},v));});
  if (!rows.length) {chart.append(svg('text',{x:400,y:120,fill:'#78889c','font-size':15},'Đang chờ mẫu dữ liệu')); return;}
  const first = rows[0].at, last = rows[rows.length-1].at;
  [['cpu_pct','#2864dc'],['ram_pct','#078963']].forEach(([key,color]) => {
    let path = '', pen = false;
    rows.forEach(r => {if (typeof r[key] !== 'number') {pen = false;return;} const x=35+((r.at-first)/Math.max(1,last-first))*950,y=215-r[key]*2;path+=(pen?' L':' M')+x.toFixed(2)+' '+y.toFixed(2);pen=true;});
    chart.append(svg('path',{d:path,fill:'none',stroke:color,'stroke-width':2.7,'stroke-linecap':'round'}));
    if (rows.length === 1) chart.append(svg('circle',{cx:35,cy:215-rows[0][key]*2,r:3,fill:color}));
  });
  $('chart-start').textContent=clock(first);$('chart-end').textContent=clock(last);
}
async function json(url) {const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error('HTTP '+response.status);return response.json();}
async function refresh() {
  if(pending)return;pending=true;
  try {
    const [cfg,events]=await Promise.all([json('/api/state'),json('/api/events')]);
    $('mode').textContent=cfg.demo?'MÔ PHỎNG':'LAB THẬT';$('mode').className='badge '+(cfg.demo?'UNKNOWN':'OK');
    $('notice').hidden=!cfg.demo;$('notice').textContent='CHẾ ĐỘ MÔ PHỎNG · Dữ liệu minh họa giao diện; không kết nối thiết bị và không gửi tin nhắn.';
    $('updated').textContent='Cập nhật '+clock(cfg.at);
    $('online').textContent=cfg.devices.filter(d=>d.freshness==='fresh'&&d.sample&&d.sample.kind!=='offline').length+' / '+cfg.devices.length;
    $('alerts').textContent=cfg.devices.reduce((n,d)=>n+(d.freshness==='fresh'&&d.sample?Object.values(d.sample.states).filter(x=>x==='ALERT').length:0),0);
    $('queue').textContent=cfg.queue.pending;$('channels').textContent=cfg.channels.length?cfg.channels.join(' + ')+(cfg.queue.retrying?' · đang thử lại':''):'Chưa cấu hình kênh';$('interval').textContent=cfg.interval+' giây';
    $('devices').replaceChildren(...cfg.devices.map(d=>deviceCard(d,cfg.devices,cfg)));
    if(!inventoryReady){cfg.devices.forEach(d=>{const option=node('option',d.name);option.value=d.id;$('device-select').append(option);});selected=cfg.devices[0].id;inventoryReady=true;}
    $('export').href='/api/export?device='+encodeURIComponent(selected);
    const rows=events.map(e=>{const tr=node('tr');const td=node('td');td.append(badge(e.state,e.state));tr.append(node('td',clock(e.at)),node('td',e.device.toUpperCase()),td,node('td',e.message));return tr;});
    if(!rows.length){const tr=node('tr'),td=node('td','Chưa có sự kiện thay đổi trạng thái.','empty');td.colSpan=4;tr.append(td);rows.push(tr);}$('event-rows').replaceChildren(...rows);
    drawChart(await json('/api/history?device='+encodeURIComponent(selected)));
  } catch(error) {$('notice').hidden=false;$('notice').textContent='Không tải được dashboard. Kiểm tra cửa sổ chạy NetWatch; dữ liệu đang hiển thị có thể đã cũ.';$('mode').textContent='MẤT KẾT NỐI DASHBOARD';$('mode').className='badge ALERT';}
  finally {pending=false;}
}
$('device-select').addEventListener('change',event=>{selected=event.target.value;refresh();});
refresh();setInterval(refresh,3000);
