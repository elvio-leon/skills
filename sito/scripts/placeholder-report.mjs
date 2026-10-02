// Elenca i segnaposto [DA SCRIVERE: ...] rimasti nelle pagine pubblicate.
// Non blocca il build: serve a sapere cosa manca prima di condividere il sito.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const RE = /\[DA SCRIVERE:[^\]]*\]/g;

function walk(dir, out = []) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(html|txt|xml)$/.test(f)) out.push(p);
  }
  return out;
}

const trovati = new Map();
for (const file of walk('dist')) {
  // Solo testo visibile o metadati: niente duplicati da JSON-LD e attributi.
  const html = readFileSync(file, 'utf8').replace(/<script[\s\S]*?<\/script>/g, '').replace(/<head>[\s\S]*?<\/head>/, '');
  const set = new Set(html.match(RE) ?? []);
  if (set.size) trovati.set(file.replace(/^dist/, '').replace(/index\.html$/, ''), set);
}

if (trovati.size === 0) {
  console.log('\n✓ Nessun segnaposto [DA SCRIVERE] nelle pagine pubblicate.\n');
} else {
  console.log('\n⚠ Segnaposto [DA SCRIVERE] ancora presenti nelle pagine pubblicate:');
  for (const [pagina, set] of trovati) {
    console.log(`\n  ${pagina}`);
    for (const s of set) console.log(`    · ${s}`);
  }
  console.log('');
}
