import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile, readdir} from 'node:fs/promises';

const output = new URL('../dist-pages/', import.meta.url);
const assets = ['app.js', 'core.js', 'engine.js', 'icon.svg', 'index.html', 'style.css'];

test('Pages output preserves every application byte and excludes backend/workspace files', async () => {
  assert.deepEqual((await readdir(output)).sort(), [...assets, '_headers', '404.html'].sort());
  for (const name of assets) {
    assert.deepEqual(await readFile(new URL(name, output)), await readFile(new URL('../public/' + name, import.meta.url)));
  }
});

test('Pages retains local-only policy and an explicit 404 instead of SPA fallback', async () => {
  const headers = await readFile(new URL('_headers', output), 'utf8');
  assert.match(headers, /^\/\*\n/);
  for (const expected of [
    'Cache-Control: public, max-age=0, must-revalidate',
    'X-Content-Type-Options: nosniff',
    'Referrer-Policy: no-referrer',
    'Permissions-Policy: camera=(), microphone=(), geolocation=()',
    "worker-src 'self'; connect-src 'none'",
    "frame-ancestors 'none'; form-action 'none'",
  ]) assert.ok(headers.includes(expected), expected);
  assert.match(await readFile(new URL('404.html', output), 'utf8'), /404/);
});
