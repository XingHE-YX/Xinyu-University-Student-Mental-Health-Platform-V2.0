import assert from 'node:assert/strict';
import '../../../../../miniprogram/tests/register-ts.mjs';
const app = { globalData: { apiBaseUrl: 'http://127.0.0.1:9000/api/v1', environmentKind: 'demo' } };
globalThis.getApp = () => app;
globalThis.wx = {
  login: ({success}) => success({code:'manual-smoke'}),
  request: async ({url, method, data, header, success, fail}) => {
    try {
      if (method === 'GET' && data) url += '?' + new URLSearchParams(Object.entries(data).map(([k,v])=>[k,String(v)]));
      const response = await fetch(url, { method, headers: {...header,'Content-Type':'application/json'}, body: method === 'GET' ? undefined : JSON.stringify(data) });
      success({data:await response.json(),statusCode:response.status});
    } catch (error) { fail(error); }
  },
};
const auth = await import('../../../../../miniprogram/services/auth.ts');
const assessment = await import('../../../../../miniprogram/services/assessment.ts');
const today = await import('../../../../../miniprogram/services/today.ts');
const treehole = await import('../../../../../miniprogram/services/treehole.ts');
const me = await import('../../../../../miniprogram/services/me.ts');
const initialSession = await auth.loginWithWechat();
if (!initialSession.basicConsent) await auth.recordBasicConsent();
if (!initialSession.identityVerified) await auth.verifyIdentity('演示同学','DEMO20260916');
assert.equal((await auth.fetchUser()).identityVerified,true);
await today.saveMood('calm');
assert.equal((await today.fetchToday()).mood.mood,'平静');
assert.equal((await assessment.fetchModules()).length,3);
for (const module of ['gad7','phq9','sleep']) {
  const session = await assessment.startAssessment(module);
  const answers = session.questions.map(()=>0);
  const result = await assessment.submitAssessment(session.id,module,answers);
  assert.ok(result.interpretation);
  assert.ok(result.completedAt);
  if (module==='sleep') { assert.equal(result.score,null); assert.equal(result.sleepDimensions.length,3); }
  else assert.equal(result.score,0);
  console.log('completed',module,result.kind);
}
const safety = await assessment.startAssessment('phq9');
const safetyAnswers = safety.questions.map(()=>0); safetyAnswers[8] = 1;
await assessment.confirmSafety(safety.id,'uncertain',safetyAnswers.slice(0,9));
assert.equal((await assessment.fetchResources('safety')).length,3);
await assessment.acknowledgeSupportResources(safety.id);
const restricted = await assessment.submitAssessment(safety.id,'phq9',safetyAnswers);
assert.equal(restricted.kind,'safety_support'); assert.equal(restricted.score,null);
console.log('safety_support',restricted.kind);
assert.equal((await auth.updateCommunityConsent(true)).communityConsent,true);
assert.equal((await auth.fetchUser()).communityConsent,true);
const posts = await treehole.fetchPosts(); assert.ok(posts.length>=2);
const post = await treehole.publishPost('这是一条本地流程核对使用的合成内容。');
assert.ok(post.id); assert.notEqual(post.status,'published');
assert.ok((await treehole.fetchMyPosts()).some(p=>p.id===post.id));
const history = await me.fetchHistory(); assert.ok(history.length>=4);
await auth.stopAccount(); assert.equal((await auth.fetchUser()).accountStatus,'recovery');
await auth.recoverAccount(); assert.equal((await auth.fetchUser()).accountStatus,'active');
await auth.updateCommunityConsent(false);
assert.equal((await auth.fetchUser()).communityConsent,false);
await assert.rejects(()=>treehole.publishPost('撤回同意后不可发布的合成验证内容。'));
console.log('PASS: local HTTP flow with real frontend adapters and backend domain services');
