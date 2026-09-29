const automator = require('/tmp/xinyu-manual-automation/node_modules/miniprogram-automator');
const [action, ...args] = process.argv.slice(2);
const pause = ms => new Promise(resolve => setTimeout(resolve,ms));
const timer = setTimeout(()=>{console.error('Automation action timed out');process.exit(1)},25000);
(async()=>{
 const m=await automator.connect({wsEndpoint:'ws://127.0.0.1:9420'});
 let p=await m.currentPage();
 if(action==='relogin') {
   await m.mockWxMethod('login',{code:'local-screenshot'});
   p=await m.reLaunch('/pages/onboarding/index');
   await p.waitFor('.option'); await (await p.$('.option')).tap(); await p.callMethod('begin');
   for(let i=0;i<60;i++){ await pause(100);p=await m.currentPage();if(p.path==='pages/identity-verification/index'||p.path==='pages/today/index')break; }
   if(p.path==='pages/identity-verification/index') {
     await (await p.$('input[placeholder="请输入姓名"]')).input('演示同学');
     await (await p.$('input[placeholder="请输入学号"]')).input('DEMO20260916');
     await p.callMethod('submit');
   }
 } else if(action==='onboard') {
   await m.mockWxMethod('login',{code:'local-screenshot'});
   if(p.path!=='pages/onboarding/index') p=await m.reLaunch('/pages/onboarding/index');
   if(!(await p.data('agreed'))) await (await p.$('.option')).tap();
   await p.callMethod('begin');
 } else if(action==='identity') {
   await (await p.$('input[placeholder="请输入姓名"]')).input('演示同学');
   await (await p.$('input[placeholder="请输入学号"]')).input('DEMO20260916');
 } else if(action==='method') {
   await p.callMethod(args[0],...(args[1]?JSON.parse(args[1]):[]));
 } else if(action==='tap') {
   const elements=await p.$$(args[0]);
   if(!elements[Number(args[1]||0)]) throw new Error('Element not found: '+args[0]);
   await elements[Number(args[1]||0)].tap();
 } else if(action==='input') {
   const element=await p.$(args[0]); if(!element) throw new Error('Input not found');
   await element.input(args[1]);
 } else if(action==='tab') {
   await m.switchTab('/pages/'+args[0]+'/index');
 } else if(action==='module') {
   p=await m.switchTab('/pages/assessment-center/index');
   await p.waitFor(`.assessment-row[data-key="${args[0]}"]`);
   await (await p.$(`.assessment-row[data-key="${args[0]}"]`)).tap();
 } else if(action==='navigate') {
   await m.navigateTo('/pages/'+args[0]+'/index'+(args[1]||''));
 } else if(action==='back') {
   await m.navigateBack();
 } else if(action==='scroll') {
   await m.pageScrollTo(Number(args[0]));
 } else if(action==='answer') {
   const target=Number(args[0]); const option=Number(args[1]||0);
   for(let i=0;i<target;i++) {
     p=await m.currentPage();
     if(p.path!=='pages/assessment-answer/index') break;
     const current=await p.data('currentIndex');
     await (await p.$(`.option[data-value="${option}"]`)).tap();
     await pause(100);
     if(current===(await p.data('questions')).length-1) break;
   }
 } else if(action==='shot') {
   await m.screenshot({path:args[0]});
 }
 await pause(250);
 p=await m.currentPage();
 const data=await p.data();
 const record={time:new Date().toISOString(),action,args,page:p.path,data};
 require('node:fs').appendFileSync(require('node:path').join(__dirname,'ui-flow.jsonl'),JSON.stringify(record)+'\n');
 console.log(JSON.stringify({page:p.path,error:data.error,loading:data.loading,title:data.title,currentIndex:data.currentIndex,questionCount:data.questions?.length,mood:data.mood,selectedMood:data.selectedMood,result:data.result,profile:data.profile,communityConsent:data.communityConsent,post:data.post,items:data.items?.length,posts:data.posts?.length},null,2));
 m.disconnect();clearTimeout(timer);
})().catch(error=>{console.error(error);process.exit(1)});
