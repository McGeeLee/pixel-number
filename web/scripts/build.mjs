import {copyFile, mkdir, readdir, rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const output = path.join(root, 'dist-pages');
// Publish only the application assets and Pages metadata, never workspace files.
const assets = ['app.js', 'core.js', 'engine.js', 'icon.svg', 'index.html', 'style.css'];
const actual = (await readdir(path.join(root, 'public'))).sort();
if (JSON.stringify(actual) !== JSON.stringify([...assets].sort())) {
  throw new Error('Review the public asset allowlist before adding files to the deployment.');
}
await rm(output, {recursive: true, force: true});
await mkdir(output, {recursive: true});
for (const name of assets) await copyFile(path.join(root, 'public', name), path.join(output, name));
for (const name of ['_headers', '404.html']) await copyFile(path.join(root, 'pages', name), path.join(output, name));
console.log(`Built ${assets.length} application assets and 2 Pages files in dist-pages; no Functions or Worker script.`);
