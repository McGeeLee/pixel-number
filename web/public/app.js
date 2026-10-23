import {capacity, pngOrder} from './core.js';

const $ = id => document.getElementById(id);
const fmt = n => n.toLocaleString('zh-CN');
const canvas = $('canvas'), ctx = canvas.getContext('2d', {willReadFrequently: true});
const loupeCtx = $('loupe').getContext('2d');
let worker, frame = null, anchor = null, rgba = null, compact = false;
let serial = 0, latest = 0, active = null, pending = null, timer;
let dirty = true, source = 'input', locked = false, pixel = [1919, 1079];
const exportKinds = new Set(['png', 'json', 'txt', 'batch']);

function status(text, error = false) {
  $('status').textContent = text;
  $('status').classList.toggle('error', error);
}
function buttons() {
  for (const control of document.querySelectorAll('.input-card button,.input-card input,.input-card select,.settings-row input,.settings-row button,.settings-row select,.actions-row button')) control.disabled = locked;
  const ready = frame && !dirty && !locked;
  for (const id of ['savePNG', 'saveSession', 'saveText', 'batch', 'previous', 'next']) $(id).disabled = !ready;
  if (ready) {
    $('previous').disabled = frame.bounds.min >= 0;
    $('next').disabled = frame.bounds.max <= 0;
  }
  $('slider').disabled = !frame || locked || (dirty && source !== 'slider');
  $('cancel').hidden = !active;
}
function setDirty(reason = 'input') {
  dirty = true; source = reason;
  $('renderState').textContent = '待更新';
  $('renderState').classList.add('busy');
  buttons();
}
function invalidate(reason) {
  clearTimeout(timer); latest = ++serial; pending = null;
  setDirty(reason);
}
function params() {
  const width = Number($('width').value), height = Number($('height').value);
  capacity(width, height);
  return {width, height, order: $('order').value, base: Number($('base').value), step: $('step').value};
}
function currentParams() {
  return {width: frame.width, height: frame.height, order: frame.order, hex: frame.hex,
    base: Number($('base').value), step: '0x' + frame.stepHex};
}
function startWorker() {
  worker = new Worker(new URL('./engine.js', import.meta.url), {type: 'module'});
  worker.onmessage = ({data}) => {
    if (!active || data.id !== active.id) return;
    if (data.kind === 'progress') {
      status(`正在打包 ${data.done} / ${data.total} 张图片…`);
      return;
    }
    const task = active; active = null;
    if (data.id === latest) {
      locked = false;
      if (!data.ok) {
        dirty = !exportKinds.has(task.kind);
        status(data.error, true);
        $('renderState').textContent = '未更新';
      } else if (data.blob) {
        download(data.blob, data.extension);
        status(`已准备好 ${data.extension.toUpperCase()} 下载。图片和编号始终留在你的设备上。`);
      } else acceptFrame(data, task.reanchor);
    }
    if (pending) { const next = pending; pending = null; dispatch(next); }
    buttons();
  };
  worker.onerror = event => {
    event.preventDefault(); worker.terminate(); active = pending = null; locked = false;
    dirty = true; status('图片引擎遇到错误，已重启。请重新生成预览。', true);
    startWorker(); buttons();
  };
}
function dispatch(task) {
  active = task;
  worker.postMessage(task, task.p.rgba ? [task.p.rgba] : []);
  $('renderState').textContent = exportKinds.has(task.kind) ? '保存中' : '计算中';
  $('renderState').classList.add('busy');
  buttons();
}
function request(kind, p, reanchor = true, reason = 'input') {
  clearTimeout(timer);
  latest = ++serial;
  if (exportKinds.has(kind)) locked = true;
  else setDirty(reason);
  const task = {id: latest, kind, p, reanchor};
  if (active) pending = task;
  else dispatch(task);
  status(exportKinds.has(kind) ? '正在准备下载…' : '正在生成画面…');
  buttons();
}
function generate() {
  if (locked) return;
  try {
    const p = params();
    if (compact && frame) p.hex = frame.hex;
    else p.text = $('number').value;
    request('render', p);
  } catch (error) { status(error.message, true); setDirty(); }
}
function writeNumber() {
  compact = frame.compact;
  $('number').value = frame.display;
  $('number').classList.toggle('compact', compact);
  $('number').title = compact ? '超大编号以十六进制摘要显示；保存编号或导出 TXT 可取得完整数字。' : '';
  $('numberHint').textContent = compact ? `${fmt(frame.bits)} bit · 完整编号可导出` : '每个整数，都对应一幅确定的画面';
}
function acceptFrame(data, reanchor) {
  frame = data; rgba = new Uint8ClampedArray(data.rgba);
  $('width').value = data.width; $('height').value = data.height; $('order').value = data.order;
  if (data.kind === 'session') {
    const value = BigInt('0x' + data.stepHex);
    $('step').value = data.stepHex.length < 100 ? value.toString() : '0x' + data.stepHex;
  }
  canvas.width = data.width; canvas.height = data.height;
  ctx.putImageData(new ImageData(rgba, data.width, data.height), 0, 0);
  writeNumber();
  if (reanchor || !anchor) {
    anchor = {hex: data.hex, width: data.width, height: data.height, order: data.order, step: '0x' + data.stepHex};
    $('slider').min = data.bounds.min; $('slider').max = data.bounds.max; $('slider').value = 0;
    $('offset').textContent = '偏移 +0';
  }
  dirty = false;
  $('dimensions').textContent = `${fmt(data.width)} × ${fmt(data.height)}  /  ${fmt(data.width * data.height)} px`;
  $('timing').textContent = `${Math.round(data.elapsed)} ms · RGB565`;
  $('renderState').textContent = '已就绪'; $('renderState').classList.remove('busy');
  status(data.kind === 'image' ? '图片已量化为 RGB565；透明区域合成到黑色。可保存 PNG 或完整编号。' :
    '画面已更新。输入数字可跳转，滑条浏览附近；保存时使用完整分辨率。');
  zoom(); inspect(); buttons();
}
function zoom() {
  if (!frame) return;
  const actual = $('zoom').value !== 'fit';
  $('viewport').classList.toggle('actual', actual);
  canvas.classList.toggle('actual', actual);
  canvas.style.width = actual ? `${frame.width * Number($('zoom').value)}px` : '100%';
  canvas.style.height = actual ? `${frame.height * Number($('zoom').value)}px` : 'auto';
}
function inspect() {
  if (!frame) return;
  const mode = $('inspectMode').value;
  if (mode === 'last') pixel = [frame.width - 1, frame.height - 1];
  if (mode === 'first') pixel = [0, 0];
  const x = Math.min(frame.width - 1, Math.max(0, pixel[0])), y = Math.min(frame.height - 1, Math.max(0, pixel[1]));
  const left = Math.max(0, Math.min(x - 5, frame.width - 11)), top = Math.max(0, Math.min(y - 5, frame.height - 11));
  const w = Math.min(11, frame.width), h = Math.min(11, frame.height);
  loupeCtx.imageSmoothingEnabled = false;
  loupeCtx.drawImage(canvas, left, top, w, h, 0, 0, 176, 176);
  loupeCtx.strokeStyle = '#a2c887'; loupeCtx.lineWidth = 1;
  loupeCtx.strokeRect((x - left) * 176 / w + .5, (y - top) * 176 / h + .5, 176 / w - 1, 176 / h - 1);
  const i = (y * frame.width + x) * 4, r = rgba[i], g = rgba[i + 1], b = rgba[i + 2];
  const code = (r >> 3) << 11 | (g >> 2) << 5 | b >> 3;
  const hex = '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('').toUpperCase();
  $('pixelHex').textContent = hex; $('swatch').style.backgroundColor = hex;
  $('coordinates').textContent = `${x}, ${y}`;
  $('pixelRGB').textContent = `${r} / ${g} / ${b}`;
  $('pixelCode').textContent = `${code} · 0x${code.toString(16).padStart(4, '0').toUpperCase()}`;
}
function download(blob, extension) {
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  a.href = url; a.download = `pixel-${stamp}.${extension}`;
  document.body.append(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  $('renderState').textContent = '已就绪'; $('renderState').classList.remove('busy');
}
function exportFile(kind) {
  if (locked || dirty || !frame) return;
  request(kind, currentParams());
}
function offset(delta, reanchor) {
  if (!frame || locked) return;
  const p = reanchor ? currentParams() : {...anchor, base: Number($('base').value)};
  p.offset = delta;
  request('offset', p, reanchor, 'slider');
}

$('numberForm').addEventListener('submit', event => { event.preventDefault(); generate(); });
$('number').addEventListener('input', () => {
  compact = false; $('number').classList.remove('compact'); invalidate('input');
  timer = setTimeout(generate, 350);
});
$('number').addEventListener('focus', () => { if (compact) $('number').select(); });
$('base').addEventListener('change', () => {
  if (frame) request('render', {...currentParams(), base: Number($('base').value)});
  else generate();
});
$('slider').addEventListener('input', () => {
  const value = Number($('slider').value);
  $('offset').textContent = '偏移 ' + (value >= 0 ? '+' : '') + value;
  invalidate('slider'); timer = setTimeout(() => offset(value, false), 40);
});
$('previous').addEventListener('click', () => offset(-1, true));
$('next').addEventListener('click', () => offset(1, true));
$('applyStep').addEventListener('click', generate);
$('step').addEventListener('input', () => invalidate('step'));
$('step').addEventListener('keydown', event => { if (event.key === 'Enter') generate(); });
for (const id of ['width', 'height', 'order']) $(id).addEventListener('change', () => { invalidate('input'); generate(); });
for (const id of ['width', 'height']) $(id).addEventListener('input', () => invalidate('input'));
$('fullHD').addEventListener('click', () => { $('width').value = 1920; $('height').value = 1080; invalidate('input'); generate(); });
for (const button of document.querySelectorAll('[data-preset]')) button.addEventListener('click', () => {
  try { request('preset', {...params(), preset: button.dataset.preset}); }
  catch (error) { status(error.message, true); }
});
$('zoom').addEventListener('change', zoom);
$('inspectMode').addEventListener('change', inspect);
canvas.addEventListener('pointermove', event => {
  if (!frame || $('inspectMode').value !== 'hover') return;
  const rect = canvas.getBoundingClientRect();
  pixel = [Math.floor((event.clientX - rect.left) * frame.width / rect.width), Math.floor((event.clientY - rect.top) * frame.height / rect.height)];
  inspect();
});
$('savePNG').addEventListener('click', () => exportFile('png'));
$('saveSession').addEventListener('click', () => exportFile('json'));
$('saveText').addEventListener('click', () => exportFile('txt'));
$('importImage').addEventListener('click', () => $('imageFile').click());
$('openNumber').addEventListener('click', () => $('numberFile').click());
$('imageFile').addEventListener('change', async event => {
  const file = event.target.files[0]; event.target.value = ''; if (!file) return;
  invalidate('file'); const ticket = latest;
  try {
    if (file.size > 128 * 1024 * 1024) throw new Error('图片文件不能超过 128 MiB。');
    status('正在本地读取图片…');
    const bitmap = await createImageBitmap(file, {imageOrientation: 'from-image'});
    try {
      capacity(bitmap.width, bitmap.height);
      const local = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = local.getContext('2d'); context.drawImage(bitmap, 0, 0);
      const pixels = context.getImageData(0, 0, bitmap.width, bitmap.height).data;
      const order = pngOrder(new Uint8Array(await file.arrayBuffer())) || $('order').value;
      if (ticket !== latest) return;
      $('step').value = '1';
      request('image', {width: bitmap.width, height: bitmap.height, order, step: '1', base: Number($('base').value), rgba: pixels.buffer});
    } finally { bitmap.close(); }
  } catch (error) { if (ticket === latest) status(error.message, true); }
});
$('numberFile').addEventListener('change', async event => {
  const file = event.target.files[0]; event.target.value = ''; if (!file) return;
  invalidate('file'); const ticket = latest;
  try {
    if (file.size > 128 * 1024 * 1024) throw new Error('编号文件不能超过 128 MiB。');
    const text = await file.text(); if (ticket !== latest) return;
    if (/\.json$/i.test(file.name)) request('session', {text, base: Number($('base').value)});
    else request('render', {...params(), text});
  } catch (error) { if (ticket === latest) status(error.message, true); }
});
$('batch').addEventListener('click', () => {
  const max = Math.min(100, Math.floor(256 * 1024 * 1024 / (frame.width * frame.height * 4)));
  $('count').max = max; $('count').value = Math.min(10, max);
  $('batchHint').textContent = `当前尺寸每批最多 ${max} 张。输出 N、N + 步长、N + 2 × 步长…，包含恢复参数的 plan.json。`;
  $('batchDialog').showModal();
});
$('closeDialog').addEventListener('click', () => $('batchDialog').close());
$('batchForm').addEventListener('submit', event => {
  event.preventDefault(); $('batchDialog').close();
  if (!dirty && !locked && frame) request('batch', {...currentParams(), count: Number($('count').value)});
});
$('cancel').addEventListener('click', () => {
  clearTimeout(timer); worker.terminate(); active = pending = null; latest = ++serial; locked = false;
  startWorker();
  if (frame) {
    dirty = false; $('width').value = frame.width; $('height').value = frame.height; $('order').value = frame.order;
    $('step').value = frame.stepHex.length < 100 ? BigInt('0x' + frame.stepHex).toString() : '0x' + frame.stepHex;
    writeNumber();
  }
  $('renderState').textContent = frame ? '已就绪' : '已取消'; $('renderState').classList.remove('busy');
  status('任务已取消，保留最近成功的画面。本次未完成的下载不会保存。'); buttons();
});
document.addEventListener('keydown', event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 's') { event.preventDefault(); exportFile('png'); }
});

if (!globalThis.Worker || !globalThis.OffscreenCanvas || !globalThis.createImageBitmap) {
  status('请使用支持 Web Worker 和 OffscreenCanvas 的新版浏览器。', true);
} else { startWorker(); generate(); }
