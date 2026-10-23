import test from 'node:test';
import assert from 'node:assert/strict';
import {capacity, parseNumber, parseStep, numberToRGBA, rgbaToNumber, bounds, summary, session, readSession, crc32, pngOrder, withOrder, zipFiles} from '../public/core.js';

test('explicit RGB565 colors, scan order and carry', () => {
  const n = 0xf80007e0001fffffn;
  assert.deepEqual(Array.from(numberToRGBA(n, 2, 2)), [255,0,0,255,0,255,0,255,0,0,255,255,255,255,255,255]);
  assert.deepEqual(Array.from(numberToRGBA(1n, 2, 1)), [0,0,0,255,0,0,8,255]);
  assert.deepEqual(Array.from(numberToRGBA(65536n, 2, 1)), [0,0,8,255,0,0,0,255]);
  assert.equal(rgbaToNumber(numberToRGBA(n, 2, 2, 'lsb'), 2, 2, 'lsb'), n);
});
test('all 65536 colors, independent expansion and exact round trip', () => {
  const n = BigInt('0x' + Array.from({length:65536},(_,i)=>i.toString(16).padStart(4,'0')).join(''));
  const rgba = numberToRGBA(n, 256, 256);
  for (let i=0;i<65536;i++) {
    const r=i>>11,g=i>>5&63,b=i&31;
    assert.equal(rgba[i*4],r*8+Math.floor(r/4));
    assert.equal(rgba[i*4+1],g*4+Math.floor(g/16));
    assert.equal(rgba[i*4+2],b*8+Math.floor(b/4));
  }
  assert.equal(rgbaToNumber(rgba,256,256),n);
});
test('1080p boundary and random frame retain every bit', () => {
  const raw = new Uint8ClampedArray(1920*1080*4);
  for(let i=0;i<raw.length;i++) raw[i]=(i*37+41)&255;
  for(let i=3;i<raw.length;i+=4)raw[i]=255;
  for(const order of ['msb','lsb']) {
    const n=rgbaToNumber(raw,1920,1080,order);
    assert.equal(rgbaToNumber(numberToRGBA(n,1920,1080,order),1920,1080,order),n);
  }
  const max=(1n<<33177600n)-1n;
  assert.equal(numberToRGBA(max,1920,1080)[0],255);
  assert.throws(()=>numberToRGBA(max+1n,1920,1080));
});
test('input, precision, dimensions and arithmetic bounds', () => {
  assert.equal(parseNumber('0x F800_07E0',16,32),0xf80007e0n);
  assert.equal(parseNumber('1234567890'.repeat(1000),10,40000).toString(),'1234567890'.repeat(1000));
  for(const value of ['-1','1.2','1e3','NaN','65536'])assert.throws(()=>parseNumber(value,10,16));
  assert.equal(parseStep('65536^1000',20000),1n<<16000n);
  assert.throws(()=>parseStep('2^16',16));
  assert.throws(()=>parseStep('0',16));
  assert.throws(()=>capacity(0,10));
  assert.throws(()=>capacity(1.5,10));
  assert.deepEqual(bounds(0n,1n,16),{min:0,max:1000});
  assert.deepEqual(bounds(65535n,1n,16),{min:-1000,max:0});
  assert.equal(summary(1n<<33177599n).compact,true);
});
test('desktop-compatible session and alpha quantization', () => {
  const state=session(0xf80007e0001fffffn,2,2,'lsb',65536n);
  assert.deepEqual(readSession(JSON.parse(JSON.stringify(state))),{number:0xf80007e0001fffffn,width:2,height:2,order:'lsb',step:65536n});
  assert.equal(rgbaToNumber(new Uint8ClampedArray([255,255,255,0]),1,1),0n);
  assert.throws(()=>readSession({...state,step_hex:'0'}));
});
test('PNG order metadata and CRC32 known vector', async () => {
  assert.equal(crc32(new TextEncoder().encode('123456789')),0xcbf43926);
  // A minimal PNG container sufficient for testing independent chunk boundaries.
  const png=Uint8Array.from([137,80,78,71,13,10,26,10,0,0,0,0,73,69,78,68,174,66,96,130]);
  for(const order of ['msb','lsb']) {
    const blob=withOrder(png,order), data=new Uint8Array(await blob.arrayBuffer());
    assert.equal(pngOrder(data),order);
    const v=new DataView(data.buffer), len=v.getUint32(8);
    assert.equal(v.getUint32(8+8+len),crc32(data.subarray(12,8+8+len)));
  }
  assert.equal(pngOrder(new Uint8Array([1,2,3])),null);
});
test('ZIP stored entries are structurally valid', async()=>{
  const blob=await zipFiles([{name:'000000.png',blob:new Blob(['hello'])},{name:'plan.json',blob:new Blob(['{}'])}]);
  const data=new Uint8Array(await blob.arrayBuffer()),view=new DataView(data.buffer);
  assert.equal(view.getUint32(0,true),0x04034b50);
  const end=data.length-22;
  assert.equal(view.getUint32(end,true),0x06054b50);
  assert.equal(view.getUint16(end+10,true),2);
  assert.equal(view.getUint32(view.getUint32(end+16,true),true),0x02014b50);
});
