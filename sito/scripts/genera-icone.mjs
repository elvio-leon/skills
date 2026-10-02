// Genera favicon.ico (32x32) e apple-touch-icon.png (180x180) da favicon.svg.
// Si lancia a mano solo se cambia la favicon: node scripts/genera-icone.mjs
import { readFileSync, writeFileSync } from 'node:fs';
import { Resvg } from '@resvg/resvg-js';

const svg = readFileSync('public/favicon.svg', 'utf8');
const png = (size, background) =>
  new Resvg(svg, { fitTo: { mode: 'width', value: size }, background }).render().asPng();

// apple-touch-icon: fondo Paper pieno (iOS non gestisce la trasparenza)
writeFileSync('public/apple-touch-icon.png', png(180, '#F4F4EF'));

// favicon.ico: contenitore ICO con un'immagine PNG 32x32
const p32 = png(32);
const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0);
header.writeUInt16LE(1, 2);
header.writeUInt16LE(1, 4);
const entry = Buffer.alloc(16);
entry.writeUInt8(32, 0);
entry.writeUInt8(32, 1);
entry.writeUInt8(0, 2);
entry.writeUInt8(0, 3);
entry.writeUInt16LE(1, 4);
entry.writeUInt16LE(32, 6);
entry.writeUInt32LE(p32.length, 8);
entry.writeUInt32LE(22, 12);
writeFileSync('public/favicon.ico', Buffer.concat([header, entry, p32]));
console.log('Icone generate.');
