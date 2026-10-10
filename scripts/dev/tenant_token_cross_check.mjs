#!/usr/bin/env node
/**
 * 混沌海租户令牌跨语言契约测试：Node（Chaos 网关逻辑）签发/验签 ↔ Python（混沌海）验签/签发。
 * 用法：仓库根目录 `node scripts/dev/tenant_token_cross_check.mjs`（自动调 uv run python 验证反向）。
 */
import crypto from 'node:crypto';
import { execSync } from 'node:child_process';

const SECRET = 'cross-language-contract-test-secret';
const productId = 'pilot-gmoney';
const userId = 'u1001';
const role = 'user';

const b64url = (input) => Buffer.from(input).toString('base64url');
function signNode(payloadObj) {
  const header = b64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const now = Math.floor(Date.now() / 1000);
  const payload = b64url(JSON.stringify({ ...payloadObj, iat: now, exp: now + 300 }));
  const signature = b64url(crypto.createHmac('sha256', SECRET).update(`${header}.${payload}`).digest());
  return { token: `${header}.${payload}.${signature}`, payload: { ...payloadObj, iat: now, exp: now + 300 } };
}
function verifyNode(token) {
  const [header, payload, signature] = token.split('.');
  const expected = b64url(crypto.createHmac('sha256', SECRET).update(`${header}.${payload}`).digest());
  if (signature !== expected) throw new Error('bad signature');
  const claims = JSON.parse(Buffer.from(payload, 'base64url').toString());
  if (claims.exp < Math.floor(Date.now() / 1000)) throw new Error('expired');
  return claims;
}

// 1. Node 签 → 落盘给 Python 验
const issued = signNode({ productId, userId, role });
process.env.KB_TEST_SECRET = SECRET;
process.env.KB_TEST_TOKEN = issued.token;
const py = execSync(
  `uv run python scripts/dev/tenant_token_cross_check.py --verify "${issued.token}"`,
  { env: { ...process.env }, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
);
const pyResult = JSON.parse(py.trim().split('\n').pop());
if (!pyResult.ok || pyResult.productId !== productId || pyResult.userId !== userId || pyResult.role !== role) {
  console.error('FAIL node→python:', JSON.stringify(pyResult));
  process.exit(1);
}
console.log('PASS node→python 验签:', JSON.stringify(pyResult));

// 2. 篡改令牌 → Python 必须拒绝（脚本恒 exit 0，按输出 ok 字段判定）
const tampered = issued.token.slice(0, -2) + (issued.token.endsWith('AA') ? 'BB' : 'AA');
let tamperResult = { ok: true };
try {
  const out = execSync(`uv run python scripts/dev/tenant_token_cross_check.py --verify "${tampered}"`, {
    env: { ...process.env }, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'],
  });
  tamperResult = JSON.parse(out.trim().split('\n').pop());
} catch {
  tamperResult = { ok: false };
}
if (tamperResult.ok !== false) {
  console.error('FAIL 篡改令牌未被拒绝:', JSON.stringify(tamperResult));
  process.exit(1);
}
console.log('PASS node→python 篡改拒绝');

// 3. Python 签 → Node 验
const pyIssued = execSync(
  `uv run python scripts/dev/tenant_token_cross_check.py --issue "${productId}" "${userId}" "${role}"`,
  { env: { ...process.env, KB_TEST_SECRET: SECRET }, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] },
).trim().split('\n').pop();
const claims = verifyNode(pyIssued);
if (claims.productId !== productId || claims.userId !== userId || claims.role !== role) {
  console.error('FAIL python→node:', JSON.stringify(claims));
  process.exit(1);
}
console.log('PASS python→node 验签:', JSON.stringify({ productId: claims.productId, userId: claims.userId, role: claims.role }));
console.log('\n==== 跨语言契约 3/3 PASS ====');
