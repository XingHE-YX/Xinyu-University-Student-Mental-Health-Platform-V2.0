import { createServer } from '../../admin/node_modules/vite/dist/node/index.js';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../../admin', import.meta.url));
const server = await createServer({
  root,
  server: { host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:9000', changeOrigin: false } } },
});
await server.listen();
server.printUrls();
