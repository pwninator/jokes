
import fs from 'node:fs/promises';
import vm from 'node:vm';

const filePath = process.argv[2];
try {
  const code = await fs.readFile(filePath, 'utf8');
  new vm.SourceTextModule(code, { identifier: filePath });
  process.exit(0);
} catch (err) {
  console.error(String(err));
  process.exit(1);
}
