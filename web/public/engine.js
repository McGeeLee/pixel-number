import {capacity, validate, parseNumber, parseStep, numberToRGBA, rgbaToNumber, bounds, summary, session, readSession, withOrder, zipFiles} from './core.js';

const makePNG = async (n, width, height, order) => {
  const canvas = new OffscreenCanvas(width, height);
  canvas.getContext('2d').putImageData(new ImageData(numberToRGBA(n, width, height, order), width, height), 0, 0);
  const blob = await canvas.convertToBlob({type: 'image/png'});
  return withOrder(new Uint8Array(await blob.arrayBuffer()), order);
};

self.onmessage = async ({data: {id, kind, p}}) => {
  const started = performance.now();
  try {
    let width = p.width, height = p.height, order = p.order || 'msb', bits;
    let n, step;
    if (kind === 'session') {
      ({number: n, width, height, order, step} = readSession(JSON.parse(p.text)));
      bits = capacity(width, height);
    } else {
      bits = capacity(width, height);
      step = parseStep(p.step || '1', bits);
      if (kind === 'preset') {
        if (p.preset === 'black') n = 0n;
        else if (p.preset === 'white') n = (1n << BigInt(bits)) - 1n;
        else if (p.preset === 'palette') {
          const rgba = new Uint8ClampedArray(width * height * 4);
          for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
            const i = (y * width + x) * 4;
            rgba[i] = Math.round(x / Math.max(1, width - 1) * 255);
            rgba[i + 1] = Math.round(y / Math.max(1, height - 1) * 255);
            rgba[i + 2] = Math.round((1 - x / Math.max(1, width - 1)) * 255);
            rgba[i + 3] = 255;
          }
          n = rgbaToNumber(rgba, width, height, order);
        } else {
          const rgba = new Uint8ClampedArray(width * height * 4);
          for (let i = 0; i < rgba.length; i += 65536) crypto.getRandomValues(rgba.subarray(i, i + 65536));
          for (let i = 3; i < rgba.length; i += 4) rgba[i] = 255;
          n = rgbaToNumber(rgba, width, height, order);
        }
      } else if (kind === 'image') n = rgbaToNumber(new Uint8ClampedArray(p.rgba), width, height, order);
      else n = parseNumber(p.text ?? p.hex, p.text !== undefined ? p.base : 16, bits);
    }
    if (kind === 'offset') n += BigInt(p.offset) * step;
    validate(n, width, height, order);
    if (kind === 'png') {
      self.postMessage({id, ok: true, kind, blob: await makePNG(n, width, height, order), extension: 'png'});
    } else if (kind === 'json' || kind === 'txt') {
      const value = kind === 'json' ? JSON.stringify(session(n, width, height, order, step), null, 2) : (p.base === 16 ? '0x' : '') + n.toString(p.base);
      self.postMessage({id, ok: true, kind, blob: new Blob([value + '\n'], {type: kind === 'json' ? 'application/json' : 'text/plain'}), extension: kind});
    } else if (kind === 'batch') {
      if (!Number.isSafeInteger(p.count) || p.count < 1 || p.count > 100) throw new Error('网页版每批支持 1–100 张。');
      if (width * height * 4 * p.count > 256 * 1024 * 1024) throw new Error('本批原始像素超过 256 MiB，请减少张数或分辨率。');
      validate(n + BigInt(p.count - 1) * step, width, height, order);
      const files = [];
      const plan = {...session(n, width, height, order, step), count: p.count, formula: 'number + index * step'};
      files.push({name: 'plan.json', blob: new Blob([JSON.stringify(plan, null, 2)])});
      for (let i = 0; i < p.count; i++) {
        files.push({name: String(i).padStart(6, '0') + '.png', blob: await makePNG(n + BigInt(i) * step, width, height, order)});
        self.postMessage({id, kind: 'progress', done: i + 1, total: p.count});
      }
      self.postMessage({id, ok: true, kind, blob: await zipFiles(files), extension: 'zip'});
    } else {
      const rgba = numberToRGBA(n, width, height, order);
      const info = summary(n, p.base || 10);
      self.postMessage({id, ok: true, kind, ...info, width, height, order, stepHex: step.toString(16),
        bounds: bounds(n, step, bits), rgba: rgba.buffer, elapsed: performance.now() - started}, [rgba.buffer]);
    }
  } catch (error) { self.postMessage({id, ok: false, kind, error: error.message || String(error)}); }
};
