import test from 'node:test';
import assert from 'node:assert/strict';
import worker from '../dist/worker.mjs';

test('public assets, correct MIME types, exact ETags and HEAD', async () => {
  const home = await worker.fetch(new Request('https://pixels.mcgeelee.com/'));
  assert.equal(home.status,200);
  assert.match(home.headers.get('content-type'),/text\/html/);
  assert.match(await home.text(),/数字像素实验室/);
  const js = await worker.fetch(new Request('https://pixels.mcgeelee.com/engine.js'));
  assert.match(js.headers.get('content-type'),/javascript/);
  assert.match(js.headers.get('content-security-policy'),/connect-src 'none'/);
  const cached = await worker.fetch(new Request('https://pixels.mcgeelee.com/engine.js',{headers:{'If-None-Match':js.headers.get('etag')}}));
  assert.equal(cached.status,304);
  const head = await worker.fetch(new Request('https://pixels.mcgeelee.com/',{method:'HEAD'}));
  assert.equal(await head.text(),'');
});
test('unpublished workspace files and write methods are unavailable', async () => {
  for (const name of ['/.venv/pyvenv.cfg','/README.md','/requirements.txt','/../pixel_number/codec.py','/.git/config']) {
    assert.equal((await worker.fetch(new Request('https://pixels.mcgeelee.com'+name))).status,404);
  }
  assert.equal((await worker.fetch(new Request('https://pixels.mcgeelee.com/',{method:'POST',body:'private photo'}))).status,405);
});
