// Exact RGB565 codec shared by the browser worker and Node tests.
export const MAX_PIXELS = 16777216;
export const SCHEMA = 'pixel-number/v1';
const HEX = Array.from({length: 65536}, (_, i) => i.toString(16).padStart(4, '0'));

export function capacity(width, height) {
  if (!Number.isSafeInteger(width) || !Number.isSafeInteger(height) || width < 1 || height < 1 || width * height > MAX_PIXELS)
    throw new Error('宽高需为正整数，总像素不能超过 16,777,216。');
  return width * height * 16;
}
export function validate(n, width, height, order = 'msb') {
  const bits = capacity(width, height);
  if (!['msb', 'lsb'].includes(order)) throw new Error('无效的像素顺序。');
  if (typeof n !== 'bigint' || n < 0n || n >> BigInt(bits)) throw new Error('编号超出当前尺寸的范围；请增大尺寸或减小编号。');
  return bits;
}
export function parseNumber(text, base, bits) {
  if (![10, 16].includes(base)) throw new Error('请选择十进制或十六进制。');
  let s = String(text).replace(/[\s_]/g, '').replace(/^\+/, '');
  if (base === 16) s = s.replace(/^0x/i, '');
  if (!(base === 16 ? /^[0-9a-f]+$/i : /^[0-9]+$/).test(s)) throw new Error('请输入有效的非负整数。');
  s = s.replace(/^0+/, '') || '0';
  const limit = base === 16 ? Math.ceil(bits / 4) : Math.floor(bits * Math.LOG10E * Math.LN2) + 1;
  if (s.length > limit) throw new Error('编号超过当前尺寸的容量。');
  const n = BigInt(base === 16 ? '0x' + s : s);
  if (n >> BigInt(bits)) throw new Error('编号超过当前尺寸的容量。');
  return n;
}
export function parseStep(text, bits) {
  const s = String(text).replace(/\s/g, '');
  const match = /^(2|65536)\^(\d{1,10})$/.exec(s);
  let n;
  if (match) {
    const exponent = Number(match[2]) * (match[1] === '65536' ? 16 : 1);
    if (exponent >= bits) throw new Error('步长已超过整张图的容量。');
    n = 1n << BigInt(exponent);
  } else n = parseNumber(s, /^0x/i.test(s) ? 16 : 10, bits);
  if (n < 1n) throw new Error('步长必须大于零。');
  return n;
}
export function numberToRGBA(number, width, height, order = 'msb') {
  validate(number, width, height, order);
  const count = width * height;
  // Convert only once; repeatedly shifting a multi-million-bit integer is quadratic.
  const hex = number.toString(16).padStart(count * 4, '0');
  const rgba = new Uint8ClampedArray(count * 4);
  for (let i = 0; i < count; i++) {
    const code = parseInt(hex.slice(i * 4, i * 4 + 4), 16);
    const j = (order === 'msb' ? i : count - 1 - i) * 4;
    const r = code >> 11, g = (code >> 5) & 63, b = code & 31;
    rgba[j] = r << 3 | r >> 2;
    rgba[j + 1] = g << 2 | g >> 4;
    rgba[j + 2] = b << 3 | b >> 2;
    rgba[j + 3] = 255;
  }
  return rgba;
}
export function rgbaToNumber(rgba, width, height, order = 'msb') {
  capacity(width, height);
  if (!['msb', 'lsb'].includes(order) || rgba.length !== width * height * 4) throw new Error('像素数据或顺序无效。');
  const codes = new Array(width * height);
  for (let i = 0; i < codes.length; i++) {
    const j = i * 4, a = rgba[j + 3] / 255;
    const code = (Math.round(rgba[j] * a) >> 3) << 11 |
      (Math.round(rgba[j + 1] * a) >> 2) << 5 | Math.round(rgba[j + 2] * a) >> 3;
    codes[order === 'msb' ? i : codes.length - 1 - i] = HEX[code];
  }
  return BigInt('0x' + codes.join(''));
}
export function bounds(anchor, step, bits) {
  if (anchor < 0n || anchor >> BigInt(bits) || step <= 0n) throw new Error('滑条参数无效。');
  const left = anchor / step, right = ((1n << BigInt(bits)) - 1n - anchor) / step;
  return {min: left === 0n ? 0 : -Number(left > 1000n ? 1000n : left), max: Number(right > 1000n ? 1000n : right)};
}
export function summary(n, base = 10) {
  const hex = n.toString(16);
  const bits = n === 0n ? 0 : (hex.length - 1) * 4 + (32 - Math.clz32(parseInt(hex[0], 16)));
  const compact = hex.length > 120;
  return {hex, bits, compact, display: compact ? `0x${hex.slice(0, 16)}…${hex.slice(-16)}` : (base === 16 ? '0x' : '') + n.toString(base)};
}
export function session(n, width, height, order, step) {
  validate(n, width, height, order);
  validate(step, width, height, order);
  if (!step) throw new Error('步长必须大于零。');
  return {schema: SCHEMA, width, height, order, number_hex: n.toString(16), step_hex: step.toString(16)};
}
export function readSession(data) {
  if (!data || data.schema !== SCHEMA) throw new Error('这不是 Pixel Number 的编号文件。');
  const {width, height, order} = data, bits = capacity(width, height);
  const number = parseNumber(data.number_hex, 16, bits);
  const step = parseNumber(data.step_hex || '1', 16, bits);
  validate(number, width, height, order);
  if (!step) throw new Error('编号文件中的步长无效。');
  return {number, width, height, order, step};
}

// PNG tEXt preserves pixel order without storing the huge integer a second time.
const CRC_TABLE = new Uint32Array(256);
for (let i = 0; i < 256; i++) {
  let c = i;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ c >>> 1 : c >>> 1;
  CRC_TABLE[i] = c >>> 0;
}
export function crc32(data) {
  let c = 0xffffffff;
  for (const byte of data) c = CRC_TABLE[(c ^ byte) & 255] ^ c >>> 8;
  return (c ^ 0xffffffff) >>> 0;
}
export function withOrder(png, order) {
  const body = new TextEncoder().encode('tEXtpixel_number.order\0' + order);
  const chunk = new Uint8Array(body.length + 8);
  const view = new DataView(chunk.buffer);
  view.setUint32(0, body.length - 4);
  chunk.set(body, 4);
  view.setUint32(chunk.length - 4, crc32(body));
  return new Blob([png.slice(0, -12), chunk, png.slice(-12)], {type: 'image/png'});
}
export function pngOrder(data) {
  if (data.length < 20 || data[0] !== 137 || data[1] !== 80 || data[2] !== 78 || data[3] !== 71) return null;
  const v = new DataView(data.buffer, data.byteOffset, data.byteLength);
  for (let i = 8; i + 12 <= data.length;) {
    const length = v.getUint32(i), end = i + 12 + length;
    if (end > data.length) break;
    if (String.fromCharCode(...data.subarray(i + 4, i + 8)) === 'tEXt' && length < 256) {
      const s = new TextDecoder().decode(data.subarray(i + 8, end - 4));
      if (s === 'pixel_number.order\0msb') return 'msb';
      if (s === 'pixel_number.order\0lsb') return 'lsb';
    }
    i = end;
  }
  return null;
}

// ZIP store mode: PNG is already compressed, so no third-party bundle is needed.
export async function zipFiles(files) {
  const parts = [], central = [];
  let offset = 0, centralSize = 0;
  for (const file of files) {
    const name = new TextEncoder().encode(file.name);
    const bytes = new Uint8Array(await file.blob.arrayBuffer());
    const crc = crc32(bytes);
    const header = new Uint8Array(30 + name.length), hv = new DataView(header.buffer);
    hv.setUint32(0, 0x04034b50, true); hv.setUint16(4, 20, true); hv.setUint16(6, 0x800, true);
    hv.setUint32(14, crc, true); hv.setUint32(18, bytes.length, true); hv.setUint32(22, bytes.length, true);
    hv.setUint16(26, name.length, true); header.set(name, 30);
    const entry = new Uint8Array(46 + name.length), ev = new DataView(entry.buffer);
    ev.setUint32(0, 0x02014b50, true); ev.setUint16(4, 20, true); ev.setUint16(6, 20, true); ev.setUint16(8, 0x800, true);
    ev.setUint32(16, crc, true); ev.setUint32(20, bytes.length, true); ev.setUint32(24, bytes.length, true);
    ev.setUint16(28, name.length, true); ev.setUint32(42, offset, true); entry.set(name, 46);
    parts.push(header, bytes); central.push(entry);
    offset += header.length + bytes.length; centralSize += entry.length;
  }
  const end = new Uint8Array(22), v = new DataView(end.buffer);
  v.setUint32(0, 0x06054b50, true); v.setUint16(8, files.length, true); v.setUint16(10, files.length, true);
  v.setUint32(12, centralSize, true); v.setUint32(16, offset, true);
  return new Blob([...parts, ...central, end], {type: 'application/zip'});
}
