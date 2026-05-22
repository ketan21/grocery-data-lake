// Post-build: remove crossorigin attributes from the built index.html
// Our app is same-origin — crossorigin causes the browser to do unnecessary CORS
// checks which can fail with certain CDN/proxy setups and trigger React error #299.

import { readFileSync, writeFileSync } from 'fs';
import { join } from 'path';

const htmlPath = join(import.meta.dirname, '../dashboard/index.html');
let html = readFileSync(htmlPath, 'utf8');

const before = html.length;
html = html.replace(/ crossorigin(?:="[^"]*")?/g, '');
const after = html.length;

writeFileSync(htmlPath, html);

const stripped = before - after;
if (stripped > 0) {
  console.log(`✅ Stripped ${stripped} chars of crossorigin attributes`);
} else {
  console.log('ℹ️  No crossorigin attributes found');
}