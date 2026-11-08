import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

/** Bind rendering to the exact presentation bytes approved by the inspector. */
export async function verifyInput(root = process.cwd()) {
  let provenance, bytes;
  try {
    const text = await readFile(path.join(root, 'research-provenance.json'), 'utf8');
    try { provenance = JSON.parse(text); }
    catch { throw new Error('invalid-provenance-json'); }
  } catch {
    throw new Error('Reviewed-input check failed: research-provenance.json is missing or invalid. Create a fresh presentation from inspector-approved inputs.');
  }
  if (provenance?.status !== 'inspector-approved' || !/^[a-f0-9]{64}$/.test(provenance.presentationSha256 || '')) {
    throw new Error('Reviewed-input check failed: no valid inspector-approved presentation seal. Revalidate the research and create a fresh presentation directory.');
  }
  try { bytes = await readFile(path.join(root, 'src/data.json')); }
  catch { throw new Error('Reviewed-input check failed: src/data.json is unavailable.'); }
  const sha256 = createHash('sha256').update(bytes).digest('hex');
  if (sha256 !== provenance.presentationSha256) {
    throw new Error('Reviewed-input check failed: src/data.json changed after inspection. Reinspect and reseal the analysis, then scaffold a fresh output directory. UI and artwork edits may retain the approved data unchanged.');
  }
  return { presentationSha256: sha256 };
}

if (path.resolve(process.argv[1] || '') === fileURLToPath(import.meta.url)) {
  try { await verifyInput(); console.log('Inspector-approved presentation bytes verified.'); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
