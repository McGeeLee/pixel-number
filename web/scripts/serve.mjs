import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root = fileURLToPath(new URL('../public/', import.meta.url));
const types = {'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'};
createServer(async (req, res) => {
  const route = new URL(req.url, 'http://localhost').pathname;
  const name = route === '/' ? 'index.html' : route.slice(1);
  if (name.includes('/') || !/^[\w.-]+$/.test(name)) {res.writeHead(404);res.end();return;}
  try {
    const data = await readFile(path.join(root, name));
    res.writeHead(200, {'Content-Type': types[path.extname(name)] || 'text/plain', 'Cache-Control': 'no-store'});
    res.end(data);
  } catch {res.writeHead(404);res.end();}
}).listen(8788, '127.0.0.1', () => console.log('Pixel Number local: http://127.0.0.1:8788'));
