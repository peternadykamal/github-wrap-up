import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, readFile, writeFile, copyFile, rm, stat } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import os from 'node:os';
import { verifyInput } from './verify-input.mjs';

const template = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
async function fixture(fn) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'year-review-seal-'));
  try {
    await mkdir(path.join(root, 'src'));
    await mkdir(path.join(root, 'scripts'));
    const bytes = Buffer.from('{"fixture":"approved synthetic data"}\n');
    await writeFile(path.join(root, 'src/data.json'), bytes);
    await writeFile(path.join(root, 'research-provenance.json'), JSON.stringify({ status:'inspector-approved', presentationSha256:createHash('sha256').update(bytes).digest('hex') }));
    for (const name of ['verify-input.mjs','export.mjs']) await copyFile(path.join(template,'scripts',name),path.join(root,'scripts',name));
    await copyFile(path.join(template,'package.json'),path.join(root,'package.json'));
    await fn(root);
  } finally { await rm(root, { recursive:true, force:true }); }
}

test('exact approved bytes pass; UI-only edits preserve the approval',async()=>fixture(async root=>{
  const result=await verifyInput(root);assert.match(result.presentationSha256,/^[a-f0-9]{64}$/);
  await writeFile(path.join(root,'src/styles.css'),'body { color: teal }');
  await writeFile(path.join(root,'src/Artwork.tsx'),'export const Artwork = () => null;');
  assert.deepEqual(await verifyInput(root),result);
}));

test('post-scaffold data mutation blocks check/dev/build/export before creating output',async()=>fixture(async root=>{
  const sensitive='synthetic-private-marker-never-publish';
  await writeFile(path.join(root,'src/data.json'),JSON.stringify({fixture:sensitive}));
  for (const command of [['npm','run','check'],['npm','run','dev'],['npm','run','build'],['node','scripts/export.mjs']]) {
    const result=spawnSync(command[0],command.slice(1),{cwd:root,encoding:'utf8',timeout:15000});
    assert.notEqual(result.status,0,command.join(' '));
    assert.match(result.stdout+result.stderr,/Reviewed-input check failed/);
    assert.equal((result.stdout+result.stderr).includes(sensitive),false);
    assert.equal(await stat(path.join(root,'dist')).then(()=>true,()=>false),false);
    assert.equal(await stat(path.join(root,'year-in-review.html')).then(()=>true,()=>false),false);
  }
}));

test('missing or nonapproved provenance is rejected without echoing input',async()=>fixture(async root=>{
  await writeFile(path.join(root,'research-provenance.json'),'{invalid synthetic-private-provenance');
  await assert.rejects(verifyInput(root),/missing or invalid/);
  await writeFile(path.join(root,'research-provenance.json'),JSON.stringify({status:'pending',presentationSha256:'0'.repeat(64)}));
  await assert.rejects(verifyInput(root),/no valid inspector-approved/);
  await rm(path.join(root,'research-provenance.json'));
  await assert.rejects(verifyInput(root),/missing or invalid/);
}));
