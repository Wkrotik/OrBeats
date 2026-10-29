// Offline browser regression: app + headless Chromium/CDP must already be running.
// node development/scripts/test_companion_browser.mjs [app URL] [CDP URL] [output dir]
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const app = process.argv[2] || 'http://127.0.0.1:18765';
const cdp = process.argv[3] || 'http://127.0.0.1:19222';
const output = process.argv[4] || 'temp/orbeats-browser-evidence';
await mkdir(output, { recursive: true });
const page = await (await fetch(cdp + '/json/new?about:blank', { method: 'PUT' })).json();
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let next = 0;
const pending = new Map(), errors = [], covers = new Map();
const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=';
const wav = Buffer.alloc(44 + 44100 * 4);
wav.write('RIFF'); wav.writeUInt32LE(wav.length - 8, 4); wav.write('WAVEfmt ', 8);
wav.writeUInt32LE(16, 16); wav.writeUInt16LE(1, 20); wav.writeUInt16LE(2, 22);
wav.writeUInt32LE(44100, 24); wav.writeUInt32LE(44100 * 4, 28);
wav.writeUInt16LE(4, 32); wav.writeUInt16LE(16, 34); wav.write('data', 36); wav.writeUInt32LE(wav.length - 44, 40);
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++next; pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
socket.onmessage = ({ data }) => {
  const m = JSON.parse(data);
  if (m.id) {
    const p = pending.get(m.id); if (!p) return;
    pending.delete(m.id); m.error ? p.reject(Error(JSON.stringify(m.error))) : p.resolve(m.result);
  }
  if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text);
  if (m.method === 'Fetch.requestPaused') {
    const { requestId, request } = m.params;
    const url = new URL(request.url);
    let status = 200, type = 'image/png', body = png;
    if (url.pathname.endsWith('/cover')) {
      const count = (covers.get(url.pathname) || 0) + 1; covers.set(url.pathname, count);
      if (url.pathname.includes('000001') && count === 1) { status = 503; body = ''; }
    }
    if (url.pathname.endsWith('/preview') || url.pathname.endsWith('.mp3')) { type = 'audio/wav'; body = wav.toString('base64'); }
    send('Fetch.fulfillRequest', { requestId, responseCode: status, responseHeaders: [{ name: 'Content-Type', value: type }], body })
      .catch(e => errors.push(e.message));
  }
};
async function evaluate(expression) {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, userGesture: true });
  assert(!r.exceptionDetails, JSON.stringify(r.exceptionDetails)); return r.result.value;
}
async function until(expression) {
  for (let i = 0; i < 100; i++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  throw Error('Timed out: ' + expression + '\n' + JSON.stringify(await evaluate("({deletes:window.testDeletes,removing:state.removing,loading:state.libraryLoading,ready:state.libraryReady,queue:state.queue,songs:state.songs.length,feedback:document.getElementById('library-feedback').textContent,notice:document.getElementById('notice').textContent,confirm:document.getElementById('confirm-action').open})")));
}
async function checkDownloadsModal() {
  await evaluate(`(()=>{const spacer=document.createElement('div');spacer.id='scroll-fixture';spacer.style.height='3000px';document.querySelector('main').append(spacer);scrollTo(0,200);document.getElementById('open-downloads').click();const content=document.createElement('div');content.id='modal-scroll-fixture';content.style.height='2000px';document.getElementById('downloads').append(content)})()`);
  const originalScroll = await evaluate('scrollY');
  const mainScroll = await evaluate("document.querySelector('main').scrollTop");
  const rect = await evaluate("(()=>{const d=document.getElementById('downloads'),r=d.getBoundingClientRect();d.scrollTop=d.scrollHeight;return {x:r.x+r.width/2,y:r.y+r.height/2,left:r.left,top:r.top}})()");
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: rect.x, y: rect.y, deltaX: 0, deltaY: 600 });
  await new Promise(resolve => setTimeout(resolve, 150));
  assert.equal(await evaluate('scrollY'), originalScroll, 'Modal bottom scrolled background');
  await evaluate("document.getElementById('downloads').scrollTop=0");
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: rect.x, y: rect.y, deltaX: 0, deltaY: -600 });
  await new Promise(resolve => setTimeout(resolve, 150));
  assert.equal(await evaluate('scrollY'), originalScroll, 'Modal top scrolled background');
  // Inert background/backdrop must not move either.
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: 2, y: 2, deltaX: 0, deltaY: 600 });
  await new Promise(resolve => setTimeout(resolve, 150));
  assert.equal(await evaluate('scrollY'), originalScroll, 'Backdrop wheel scrolled background');
  assert.equal(await evaluate("getComputedStyle(document.documentElement).overflow"), 'hidden');
  // Padding is inside the bounding box; clicking it must leave the panel open.
  const inside = {x:rect.left+4,y:rect.top+4};
  for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', {type,...inside,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('downloads').open"), true);
  // A drag which started inside must not become an outside-click dismissal.
  await send('Input.dispatchMouseEvent', {type:'mousePressed',...inside,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent', {type:'mouseMoved',x:2,y:2,buttons:1});
  await send('Input.dispatchMouseEvent', {type:'mouseReleased',x:2,y:2,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('downloads').open"), true);
  for (const type of ['mousePressed', 'mouseReleased']) await send('Input.dispatchMouseEvent', {type,x:2,y:2,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('downloads').open"), false, 'Backdrop click did not dismiss');
  assert.equal(await evaluate("document.querySelector('main').scrollTop"), mainScroll, 'Modal scrolled desktop content');
  if (await evaluate('innerWidth>720')) {
    assert.equal(await evaluate("getComputedStyle(document.documentElement).overflow"), 'hidden');
    assert.equal(await evaluate("getComputedStyle(document.querySelector('main')).overflowY"), 'auto');
  } else assert.notEqual(await evaluate("getComputedStyle(document.documentElement).overflow"), 'hidden');
  await evaluate("document.getElementById('modal-scroll-fixture').remove();document.getElementById('scroll-fixture').remove();scrollTo(0,0)");
}
async function checkDetailsBackdrop() {
  const rect=await evaluate("(()=>{const r=document.getElementById('details').getBoundingClientRect();return {left:r.left,top:r.top}})()");
  const inside={x:rect.left+4,y:rect.top+4};
  for(const type of ['mousePressed','mouseReleased'])await send('Input.dispatchMouseEvent',{type,...inside,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('details').open"),true,'Detail padding dismissed dialog');
  await send('Input.dispatchMouseEvent',{type:'mousePressed',...inside,button:'left',clickCount:1});
  await send('Input.dispatchMouseEvent',{type:'mouseMoved',x:2,y:2,buttons:1});
  await send('Input.dispatchMouseEvent',{type:'mouseReleased',x:2,y:2,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('details').open"),true,'Detail drag dismissed dialog');
  await evaluate("(()=>{const d=document.getElementById('details');d.dispatchEvent(new PointerEvent('pointerdown',{clientX:2,clientY:2,isPrimary:true,button:0}));d.dispatchEvent(new PointerEvent('pointercancel'));d.dispatchEvent(new MouseEvent('click',{clientX:2,clientY:2}))})()");
  assert.equal(await evaluate("document.getElementById('details').open"),true,'Cancelled gesture dismissed dialog');
  for(const type of ['mousePressed','mouseReleased'])await send('Input.dispatchMouseEvent',{type,x:2,y:2,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('details').open"),false,'Detail outside click did not dismiss');
}
async function checkInstallationLog() {
  await evaluate(`(()=>{
    window.savedLogHistory=structuredClone(window.testQueue.history);
    window.testQueue.history=Array.from({length:80},(_,i)=>({id:'log-history-'+i,map_id:'abc',title:'History song '+i,status:'complete'}));
    document.getElementById('open-downloads').click();document.getElementById('downloads').scrollTop=0;
  })()`);
  await until("document.querySelectorAll('#queue-history li').length===80");
  assert.equal(await evaluate("document.getElementById('diagnostics').hidden"),true);
  assert.equal(await evaluate("document.getElementById('toggle-log').getAttribute('aria-expanded')"),'false');
  assert.equal(await evaluate("Boolean(document.getElementById('installation-log').compareDocumentPosition(document.getElementById('queue-list'))&Node.DOCUMENT_POSITION_FOLLOWING)"),true);
  assert.equal(await evaluate("(()=>{const r=document.getElementById('toggle-log').getBoundingClientRect(),d=document.getElementById('downloads').getBoundingClientRect();return r.top>=d.top&&r.bottom<=d.bottom})()"),true,'Log toggle buried below long history');
  await evaluate("document.getElementById('toggle-log').click();window.testProgress.lines.push(...Array.from({length:300},(_,i)=>'log-line-'+i));window.testProgress.index=window.testProgress.lines.length");
  await until("document.getElementById('log').textContent.includes('log-line-299')");
  await until("(()=>{const l=document.getElementById('log');return l.scrollHeight-l.clientHeight-l.scrollTop<=4})()");
  assert.equal(await evaluate("document.getElementById('log-title').textContent"),'Installation log');
  assert.equal(await evaluate("document.getElementById('toggle-log').textContent"),'Hide log');
  assert.equal(await evaluate("(()=>{const l=document.getElementById('log');return l.clientHeight<=281&&l.scrollHeight>l.clientHeight})()"),true);
  await evaluate("document.getElementById('log').focus();document.getElementById('log').scrollTop=0");
  await until("!state.logFollowing&&!document.getElementById('log-latest').hidden");
  const before=await evaluate("({page:scrollY,dialog:document.getElementById('downloads').scrollTop,log:document.getElementById('log').scrollTop})");
  await evaluate("window.testProgress.lines.push('new output while reading earlier');window.testProgress.index++");
  await until("state.rawLog.includes('new output while reading earlier')");
  assert.deepEqual(await evaluate("({page:scrollY,dialog:document.getElementById('downloads').scrollTop,log:document.getElementById('log').scrollTop})"),before,'Polling stole reader scroll');
  assert.equal(await evaluate("document.activeElement.id"),'log');
  await evaluate("document.getElementById('toggle-log').click()");
  assert.equal(await evaluate('state.logFollowing'),false);
  await evaluate("document.getElementById('toggle-log').click()");
  assert.equal(await evaluate('state.logFollowing'),false);
  await evaluate("document.getElementById('log-latest').click()");
  await until("state.logFollowing&&document.getElementById('log-latest').hidden&&(()=>{const l=document.getElementById('log');return l.scrollHeight-l.clientHeight-l.scrollTop<=4})()");
  await evaluate("document.getElementById('close-downloads').click();window.testProgress.lines.push('closed-dialog-output');window.testProgress.index++");
  await until("state.rawLog.includes('closed-dialog-output')");
  assert.equal(await evaluate("document.getElementById('downloads').open"),false,'New output auto-opened dialog');
  await evaluate("document.getElementById('open-downloads').click()");
  await until("(()=>{const l=document.getElementById('log');return l.scrollHeight-l.clientHeight-l.scrollTop<=4})()");
  const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile(output+'/downloads-long-history.png',Buffer.from(shot.data,'base64'));
  await evaluate("document.getElementById('toggle-log').click();document.getElementById('close-downloads').click();window.testQueue.history=window.savedLogHistory");
}
const fixture = {
  id: '4cb11', metadata: { songName: 'Browser fixture <img src=x onerror=alert(1)>', songAuthorName: 'Artist', levelAuthorName: 'Mapper', duration: 209, bpm: 132 },
  uploaded: new Date().toISOString(), stats: { score: .95, upvotes: 50, downvotes: 2, downloads: 1000, plays: 2000 }, tags: ['dance'],
  description: '<script>window.pwned=true</script>', versions: [{ diffs: [{ characteristic: 'Standard', difficulty: 'Expert', ne: false, me: false, chroma: false, cinema: false, notes: 1024, bombs: 16, obstacles: 94, nps: 4.9, njs: 14 }], coverURL: 'https://cdn.beatsaver.com/fixture.png', previewURL: 'https://cdn.beatsaver.com/fixture.mp3' }]
};
const song = { id: 'bsd_additive_000000000000000000000001', title: 'Installed fixture', author: 'Artist', duration: 209, bpm: 132, bytes: 1000, mask: 8, stats: [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [1024, 16, 94, 14, 0], [0, 0, 0, 0, 0]] };
const hooks = `(()=>{const original=window.fetch.bind(window),map=${JSON.stringify(fixture)},song=${JSON.stringify(song)};window.testOriginalSongs=[{...song,info:map},{...song,id:song.id.replace(/1$/,'2'),title:'Compression [Vorbis test]'}];window.testSongs=structuredClone(window.testOriginalSongs);window.testPluginWrites=[];window.testUpdateOffline=false;window.testDeletes=[];window.testDeleteError='';window.testDeleteDelay=false;window.testQueue={pending:[],active:null,history:[],paused:true,message:''};window.testProgress={job:null,running:false,index:0,lines:[]};window.confirm=()=>{throw Error('Native browser confirmation used')};window.fetch=async(url,options={})=>{const path=String(url);let value;
if(path==='/api/orbis/settings')value={ip:'192.168.1.67',port:2121,user:'anonymous',template:'',updates:{state:'not_checked',message:'Official GitHub release has not been checked.'}};
else if(path==='/api/orbis/plugin'&&(!options.method||options.method==='GET'))value={installed:true,installed_version:'0.8068',available_version:'0.8071',capability_matches:true,declared_version_matches:true,max_songs:8,registration:'registered_once',runtime_verified:false};
else if(path==='/api/orbis/extras'){if(options.method==='POST'){window.testPluginWrites.push('bundled-extras');value={ok:true,message:'Extras installed (offline fixture)'}}else value={installed:true,installed_version:'0.0008',available_version:'0.0009',registration:'enabled'}}
else if(path==='/api/orbis/updates')value=window.testUpdateOffline?{state:'unavailable',message:'Update check unavailable. This does not mean up to date.'}:{state:'checked',message:'Official GitHub release checked.',versions:{app:{current:'0.1.13',latest:'0.1.14',update_available:true},main:{current:'0.8079',latest:'0.8079',update_available:false},extras:{current:'0.0009',latest:'0.0010',update_available:true}}};
else if(path.startsWith('/api/orbis/updates/')&&options.method==='POST'){window.testPluginWrites.push(path.split('/').at(-1));value={ok:true,message:'Release installed (offline fixture)'}}
else if(path==='/api/ping')value={webapp_version:'0.7.15',pipeline_version:'0.5383',plugin_version:'v0.8071'};
else if(path.startsWith('/api/orbis/search?'))value={docs:window.testSearchPages?.[new URL(path,location.href).searchParams.get('page')]||[map]};
else if(path.startsWith('/api/jobs/lines?')){const p=window.testProgress,q=new URL(path,location.href).searchParams;value={...p,lines:p.lines.slice(q.get('job_id')===p.job?.id?Number(q.get('after')):0)}}
else if(path==='/api/install-queue'){if(options.method==='POST'){const b=JSON.parse(options.body);window.testQueue.pending.push({id:'entry-'+b.map_id,map_id:b.map_id,title:b.title,status:'queued'});value={ok:true}}else value=window.testQueue}
else if(path==='/api/install-queue/clear'){window.testQueue.pending=[];window.testQueue.paused=true;value=window.testQueue}
else if(path==='/api/install-queue/pause'){window.testQueue.paused=true;value=window.testQueue}
else if(path==='/api/install-queue/start'){window.testQueue.paused=false;value=window.testQueue}
else if(path.startsWith('/api/install-queue/')&&options.method==='DELETE'){window.testQueue.pending=window.testQueue.pending.filter(e=>e.id!==path.split('/').at(-1));value=window.testQueue}
else if(path==='/api/jobs/status')value={running:false};
else if(path==='/api/orbis/library')value={songs:window.testSongs};
else if(path.startsWith('/api/orbis/library/')&&options.method==='DELETE'){const id=decodeURIComponent(path.split('/').at(-1));window.testDeletes.push(id);if(window.testDeleteDelay)await new Promise(resolve=>{window.testResolveDelete=resolve});if(window.testDeleteError===id)return new Response(JSON.stringify({detail:'fixture removal failed'}),{status:503,headers:{'Content-Type':'application/json'}});window.testSongs=window.testSongs.filter(s=>s.id!==id);value={cleanup_pending:[],count:window.testSongs.length}}
else if(path.startsWith('/api/'))throw Error('Unexpected API during offline test: '+path);
else return original(url,options);return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});};})();`;
function luminance(rgb) {
  return rgb.match(/[\d.]+/g).slice(0, 3).map(n => { const c = Number(n) / 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; })
    .reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
}
const contrast = [];
try {
  await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });
  await send('Fetch.enable', { patterns: [{ urlPattern: '*://cdn.beatsaver.com/fixture*' }, { urlPattern: '*/api/orbis/library/*/cover*' }, { urlPattern: '*/api/orbis/library/*/preview' }] });
  await send('Page.addScriptToEvaluateOnNewDocument', { source: hooks });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false });
  await send('Page.bringToFront'); await send('Page.navigate', { url: app });
  await until("document.querySelectorAll('#results .card').length===1");
  // All20 songs remain in the grid; horizontal pagination stays below it at any column count.
  await evaluate(`window.savedPagination=document.getElementById('pagination');window.testSearchPages=[Array.from({length:20},(_,i)=>({...state.maps[0],id:(4096+i).toString(16),metadata:{...state.maps[0].metadata,songName:'Result '+(i+1)}})),Array.from({length:3},(_,i)=>({...state.maps[0],id:(8192+i).toString(16)}))];search()`);
  await until("document.querySelectorAll('#results .card').length===20");
  assert.deepEqual(await evaluate("[...document.querySelectorAll('#results .card h3')].map(e=>e.textContent)"),Array.from({length:20},(_,i)=>'Result '+(i+1)));
  assert.equal(await evaluate("document.getElementById('results').nextElementSibling===window.savedPagination&&!document.querySelector('#results #pagination')"),true);
  assert.equal(await evaluate("document.getElementById('previous').disabled&&!document.getElementById('next').disabled"),true);
  assert.equal(await evaluate("(()=>{const p=document.getElementById('pagination').getBoundingClientRect(),r=document.getElementById('results').getBoundingClientRect(),a=document.getElementById('previous').getBoundingClientRect(),b=document.getElementById('next').getBoundingClientRect();return r.width>0&&p.top>=r.bottom&&Math.abs(a.top-b.top)<1&&a.right<b.left})()"),true);
  await evaluate("document.getElementById('next').click()");
  await until("document.getElementById('page-number').textContent==='Page 2'&&document.querySelectorAll('#results .card').length===3");
  assert.equal(await evaluate("!document.getElementById('previous').disabled&&document.getElementById('next').disabled&&document.getElementById('pagination')===window.savedPagination"),true);
  // A partial page still keeps pagination separate and horizontal.
  assert.equal(await evaluate("(()=>{const p=document.getElementById('pagination').getBoundingClientRect(),r=document.getElementById('results').getBoundingClientRect(),a=document.getElementById('previous').getBoundingClientRect(),b=document.getElementById('next').getBoundingClientRect();return r.width>0&&p.top>=r.bottom&&Math.abs(a.top-b.top)<1&&a.right<b.left})()"),true);
  await evaluate("document.getElementById('previous').click()");
  await until("document.getElementById('page-number').textContent==='Page 1'&&document.querySelectorAll('#results .card').length===20");
  // Fullscreen: five song columns, no sixth pagination tile/extra grid row.
  await send('Emulation.setDeviceMetricsOverride', {width:1920,height:1080,deviceScaleFactor:1,mobile:false});
  assert.equal(await evaluate("getComputedStyle(document.getElementById('results')).gridTemplateColumns.split(' ').length"),5);
  assert.equal(await evaluate("document.getElementById('results').children.length===20&&document.getElementById('results').nextElementSibling===window.savedPagination"),true);
  await evaluate("document.querySelector('main').scrollTop=document.querySelector('main').scrollHeight");
  const paginationShot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile(output+'/pagination-horizontal-fullscreen.png',Buffer.from(paginationShot.data,'base64'));
  await send('Emulation.setDeviceMetricsOverride', {width:1440,height:1100,deviceScaleFactor:1,mobile:false});
  await evaluate("window.testSearchPages=[[]];search()");
  await until("document.querySelector('#results .empty')?.textContent.includes('No maps found')");
  assert.equal(await evaluate("document.getElementById('results').nextElementSibling===window.savedPagination&&document.getElementById('previous').disabled&&document.getElementById('next').disabled"),true);
  await evaluate("delete window.testSearchPages;search();document.querySelector('main').scrollTop=0");
  await until("document.querySelectorAll('#results .card').length===1");
  assert.equal(await evaluate('document.title'), 'OrBeats');
  assert.equal(await evaluate("document.getElementById('sort').value"), 'Relevance');
  assert.deepEqual(await evaluate("[...document.getElementById('sort').options].map(o=>o.value)"), ['Relevance', 'Latest', 'Rating', 'Curated']);
  assert.deepEqual(await evaluate("[...document.getElementById('period').options].map(o=>o.value)"), ['all', 'week', 'month']);
  assert.equal(await evaluate("[...document.querySelectorAll('link[href*=companion],script[src*=companion]')].every(e=>/\\?v=[0-9a-f]{20}/.test(e.href||e.src))"), true);
  assert.equal(await evaluate("(()=>{const r=document.querySelector('#open-downloads svg').getBoundingClientRect(),b=document.getElementById('open-downloads').getBoundingClientRect();return r.width===22&&r.height===22&&b.height<=56})()"), true);

  assert.equal(await evaluate("Boolean(document.querySelector('main header, .brand small'))"), false);
  assert.equal(await evaluate("document.querySelector('#results h3').textContent"), fixture.metadata.songName);
  assert.equal(await evaluate("document.querySelectorAll('#results h3 img').length"), 0);
  assert.equal(await evaluate("document.querySelector('#results .rating').textContent.includes('52 votes')"), true);
  assert.equal(await evaluate("(()=>{const r=document.querySelector('#results .meta .rating'),b=r?.previousElementSibling;return Boolean(r&&b&&b.textContent.includes('BPM')&&getComputedStyle(r).fontSize===getComputedStyle(b).fontSize&&getComputedStyle(r).fontFamily===getComputedStyle(b).fontFamily&&getComputedStyle(r).color===getComputedStyle(b).color&&!r.querySelector('small')&&!r.textContent.includes('Few'))})()"), true);

  assert.equal(await evaluate("document.querySelector('#results .compatibility').textContent.includes('No known blockers')"), true);
  assert.equal(await evaluate("document.querySelector('#results').textContent.includes('plays')"), false);
  await evaluate("state.maps.push({...state.maps[0],id:'badd',versions:[{diffs:[{characteristic:'Standard',difficulty:'Expert',ne:true}]}]});document.getElementById('results').innerHTML=state.maps.map(card).join('');updateQueueButtons()");
  assert.equal(await evaluate("document.querySelector('[data-install=badd]').disabled"), true);
  assert.equal(await evaluate("document.querySelectorAll('#results .compatibility')[1].textContent.includes('Not compatible')"), true);
  await evaluate("state.maps.pop();document.getElementById('results').innerHTML=state.maps.map(card).join('');updateQueueButtons()");

  assert.equal(await evaluate("mediaURL('https://beatsaver.com.evil.test/track.mp3')"), null);
  await evaluate("document.querySelector('#results [data-preview]').click()");
  await until("document.querySelector('#results [data-preview]').getAttribute('aria-pressed')==='true'");
  assert.equal(await evaluate("document.getElementById('details').open"), false);
  await evaluate("document.querySelector('#results [data-preview]').click()");
  assert.equal(await evaluate('previewAudio.paused'), true);
  await evaluate("document.querySelector('#results [data-install]').click()");
  await until("document.getElementById('download-count').textContent==='1'");
  assert.equal(await evaluate("document.getElementById('downloads').open"), false);
  assert.equal(await evaluate("document.getElementById('notice').hidden"), true);
  assert.equal(await evaluate("document.querySelector('main #job')"), null);
  // Bottom toast never reflows content or steals focus, and is dismissible.
  const beforeToast=await evaluate("({top:document.querySelector('.hero').getBoundingClientRect().top,scroll:scrollY})");
  await evaluate("document.getElementById('query').focus();notify('<img src=x onerror=alert(1)> Preview unavailable')");
  assert.equal(await evaluate("document.getElementById('notice-message').textContent.includes('<img')"),true);
  assert.equal(await evaluate("document.querySelectorAll('#notice-message img').length"),0);
  assert.equal(await evaluate("document.querySelector('main #notice')"),null);
  assert.deepEqual(await evaluate("({top:document.querySelector('.hero').getBoundingClientRect().top,scroll:scrollY})"),beforeToast);
  assert.equal(await evaluate("document.activeElement.id"),'query');
  assert.equal(await evaluate("(()=>{const r=document.getElementById('notice').getBoundingClientRect(),s=getComputedStyle(document.getElementById('notice'));return r.bottom<=innerHeight&&r.bottom>=innerHeight-50&&s.position==='fixed'&&!s.backgroundColor.includes('rgba')})()"),true);
  await evaluate("document.getElementById('open-downloads').click();notify('Notification above Downloads')");
  assert.equal(await evaluate("document.getElementById('notice').matches(':popover-open')"),true);
  const closeBox=await evaluate("(()=>{const r=document.getElementById('dismiss-notice').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()");
  for(const type of ['mousePressed','mouseReleased'])await send('Input.dispatchMouseEvent',{type,...closeBox,button:'left',clickCount:1});
  assert.equal(await evaluate("document.getElementById('notice').hidden"),true);
  assert.equal(await evaluate("document.getElementById('downloads').open"),true);
  await evaluate("document.getElementById('close-downloads').click()");
  await checkDownloadsModal();
  await evaluate("document.getElementById('open-downloads').click();document.getElementById('queue-start').click()");
  await until("document.getElementById('confirm-action').open");
  await evaluate("document.querySelector('#confirm-action [value=cancel]').click()");
  await evaluate("document.getElementById('queue-clear').click()");
  await until("document.getElementById('queue-total').textContent==='0'");
  await evaluate("document.getElementById('close-downloads').click()");
  assert.equal(await evaluate("document.getElementById('confirm-action').open"), false);
  assert.equal(await evaluate('state.busy'), false);
  await until("!state.confirming");
  await evaluate("void(window.testConfirmation=confirmAction('Regression', 'No action is executed.', 'Confirm'))");
  assert.equal(await evaluate("document.getElementById('confirm-accept').click();window.testConfirmation"), true);
  await evaluate("void(window.testConfirmation=confirmAction('Regression', 'Escape must cancel even after a prior confirmation.', 'Confirm'))");
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  assert.equal(await evaluate('window.testConfirmation'), false);
  await evaluate("document.querySelector('[data-detail]').click()");
  assert.equal(await evaluate("document.getElementById('details').open"), true);
  assert.equal(await evaluate("document.getElementById('detail-content').textContent.includes('1024')"), true);
  assert.equal(await evaluate("document.getElementById('detail-content').textContent.includes('DOWNLOADS')||document.getElementById('detail-content').textContent.includes('PLAYS')"), false);

  assert.equal(await evaluate('Boolean(window.pwned)'), false);
  await checkDetailsBackdrop();
  await evaluate("document.querySelector('[data-tab=library]').click()");
  await until("document.querySelectorAll('#installed .card').length===2");
  await until("[...document.querySelectorAll('#installed img')].every(i=>i.complete&&i.naturalWidth===1&&i.src.includes('/api/orbis/library/'))");
  assert(covers.get('/api/orbis/library/' + song.id + '/cover') >= 2, 'Transient cover failure was not retried');
  assert.equal(await evaluate("document.querySelectorAll('#installed [data-preview]').length"), 0);
  await evaluate("document.querySelectorAll('[data-installed-info]')[0].click()");
  assert.equal(await evaluate("document.querySelectorAll('#detail-content [data-preview]').length"), 0);
  assert.equal(await evaluate("document.querySelector('#detail-content [data-remove]')!==null"), true);
  await evaluate("document.getElementById('close-details').click();document.querySelectorAll('[data-installed-info]')[1].click()");
  assert.equal(await evaluate("document.getElementById('detail-content').textContent.includes('1024')"), true);
  assert.equal(await evaluate("document.getElementById('details').open"), true);
  await evaluate("document.getElementById('close-details').click()");
  // Selection is opt-in; whole card/image/text toggles only during edit mode.
  assert.equal(await evaluate("document.getElementById('library-selection').hidden"), true);
  assert.equal(await evaluate("document.querySelectorAll('#installed input[type=checkbox]').length"), 0);
  await evaluate("document.querySelector('#installed .art').click()");
  assert.equal(await evaluate('state.selectedSongs.size'), 0);
  await evaluate("document.getElementById('edit-selection').click();document.querySelector('#installed .art').click()");
  assert.equal(await evaluate('state.selectedSongs.size'), 1);
  assert.equal(await evaluate("document.querySelector('[data-song-tile]').getAttribute('aria-checked')"), 'true');
  await evaluate("document.querySelector('[data-song-tile]').dispatchEvent(new KeyboardEvent('keydown',{key:' ',bubbles:true}))");
  assert.equal(await evaluate('state.selectedSongs.size'), 0);
  await evaluate("document.querySelector('#installed h3').click()");
  assert.equal(await evaluate('state.selectedSongs.size'), 1);
  assert.equal(await evaluate("document.querySelectorAll('#installed .song-select').length"), 0);
  // The real paused-queue case used to silently stash the reason in Downloads.
  await evaluate("window.testQueue.pending=[{id:'pending',map_id:'55528',title:'Brainrot Giga Choir',status:'queued'}];window.testQueue.paused=true");
  await until("!document.getElementById('library-guard').hidden");
  assert.equal(await evaluate("document.getElementById('library-guard-message').textContent.includes('queue paused')"), true);
  assert.equal(await evaluate("[...document.querySelectorAll('#installed [data-remove]')].every(b=>b.disabled)"), true);
  await evaluate("document.getElementById('select-all-songs').click()");
  assert.equal(await evaluate("document.getElementById('selection-count').textContent"), '2 selected');
  assert.equal(await evaluate("document.getElementById('remove-selected').disabled"), true);
  assert.deepEqual(await evaluate('window.testDeletes'), []);
  assert.equal(await evaluate("document.getElementById('log-title').textContent"),'Last installation log');
  for (const mode of ['light', 'dark']) {
    await evaluate(`document.documentElement.dataset.theme='${mode}'`);
    const capture = await send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false});
    await writeFile(output + '/library-' + mode + '.png', Buffer.from(capture.data,'base64'));
  }
  await evaluate("document.getElementById('library-downloads').click()");
  assert.equal(await evaluate("document.getElementById('downloads').open"), true);
  await evaluate("document.getElementById('queue-clear').click()");
  await until("document.getElementById('library-guard').hidden");
  assert.equal(await evaluate("document.getElementById('remove-selected').disabled"), false);
  await evaluate("document.getElementById('close-downloads').click();document.getElementById('clear-selection').click();document.getElementById('edit-selection').click()");
  // Compression-test IDs behave exactly like ordinary IDs; no destructive call
  // is made before confirmation (including Escape and cancel).
  await evaluate("document.querySelectorAll('#installed [data-remove]')[1].click()");
  await until("document.getElementById('confirm-action').open");
  assert.equal(await evaluate("document.getElementById('confirm-message').textContent.includes('[Vorbis test]')"), true);
  await evaluate("document.querySelector('#confirm-action [value=cancel]').click();document.querySelectorAll('#installed [data-remove]')[1].click();document.getElementById('confirm-accept').click()");
  await until("!document.getElementById('confirm-action').open&&!state.confirming");
  assert.deepEqual(await evaluate('window.testDeletes'), []);
  await evaluate("document.querySelectorAll('#installed [data-remove]')[1].click()");
  await until("document.getElementById('confirm-action').open");
  await evaluate("document.getElementById('confirm-accept').click()");
  await until("window.testDeletes.length===1&&!state.removing&&state.songs.length===1");
  assert.deepEqual(await evaluate('window.testDeletes'), [song.id.replace(/1$/, '2')]);
  // Bulk work is serial, selected-only, and retains all unselected maps.
  await evaluate("window.testSongs=[...structuredClone(window.testOriginalSongs),{...window.testOriginalSongs[0],id:'bsd_additive_000000000000000000000003',title:'Unselected song'}];window.testDeletes=[];loadLibrary()");
  await until("document.querySelectorAll('#installed .card').length===3&&!state.libraryLoading");
  await evaluate("if(!state.editingSelection)document.getElementById('edit-selection').click();document.querySelectorAll('[data-song-tile]')[0].click();document.querySelectorAll('[data-song-tile]')[1].click();document.getElementById('remove-selected').click()");
  await until("document.getElementById('confirm-action').open");
  assert.equal(await evaluate("document.getElementById('confirm-title').textContent"), 'Remove 2 maps?');
  assert.equal(await evaluate("document.getElementById('confirm-message').textContent.includes('Unselected song')"), false);
  assert.equal(await evaluate("document.querySelectorAll('#confirm-message img').length"), 0);
  await evaluate("window.testDeleteDelay=true;document.getElementById('confirm-accept').click()");
  await until("window.testDeletes.length===1&&state.removing");
  assert.equal(await evaluate("document.getElementById('refresh-library').disabled&&document.getElementById('remove-selected').disabled"), true);
  await evaluate("window.testDeleteDelay=false;window.testResolveDelete()");
  await until("!state.removing&&state.songs.length===1");
  assert.deepEqual(await evaluate('window.testDeletes'), [song.id, song.id.replace(/1$/, '2')]);
  assert.equal(await evaluate('state.songs[0].title'), 'Unselected song');
  assert.equal(await evaluate('state.selectedSongs.size'), 0);
  // Stop on the first error; retained selections identify the remaining work.
  await evaluate("window.testSongs=[...structuredClone(window.testOriginalSongs),{...window.testOriginalSongs[0],id:'bsd_additive_000000000000000000000003',title:'Last song'}];window.testDeletes=[];window.testDeleteError=window.testOriginalSongs[1].id;loadLibrary()");
  await until("document.querySelectorAll('#installed .card').length===3&&!state.libraryLoading");
  await evaluate("document.getElementById('select-all-songs').click();document.getElementById('remove-selected').click()");
  await until("document.getElementById('confirm-action').open");
  await evaluate("document.getElementById('confirm-accept').click()");
  await until("!state.removing&&window.testDeletes.length===2");
  assert.equal(await evaluate('state.songs.length'), 2);
  assert.equal(await evaluate('state.selectedSongs.size'), 2);
  assert.equal(await evaluate("document.getElementById('notice-message').textContent.includes('1 of 3 removed')"), true);
  assert.equal(await evaluate("document.getElementById('notice-message').textContent.includes('fixture removal failed')"), true);
  // Selection is pruned against fresh manifests, never silently retargeted.
  await evaluate("window.testDeleteError='';window.testSongs=window.testSongs.slice(1);loadLibrary()");
  await until("!state.libraryLoading&&state.songs.length===1");
  assert.equal(await evaluate('state.selectedSongs.size'), 1);
  await evaluate("document.querySelector('[data-tab=settings]').click()");
  async function checkSettingsLayout(mobile) {
    const boxes = await evaluate(`(()=>{
      const box = element => {const r=element.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
      return {connection:box(document.getElementById('connection')),updates:box(document.getElementById('release-settings')),plugins:box(document.getElementById('plugin-settings')),viewport:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth};
    })()`);
    assert(Math.abs(boxes.connection.left-boxes.updates.left)<1);
    assert(Math.abs(boxes.connection.width-boxes.updates.width)<1);
    assert(Math.abs(boxes.updates.top-boxes.connection.bottom-20)<1, 'Updates immediately below connection, not beneath the plugin column');
    assert(boxes.connection.height<500, 'Connection card must remain content-sized');
    assert.equal(boxes.overflow,false);
    if (mobile) assert(boxes.plugins.top>=boxes.updates.bottom, 'Mobile columns stack without overlap');
    else {
      assert(boxes.plugins.left>boxes.connection.right);
      assert(Math.abs(boxes.plugins.top-boxes.connection.top)<1);
    }
    for (const box of [boxes.connection,boxes.updates,boxes.plugins]) assert(box.left>=0&&box.right<=boxes.viewport);
    await evaluate("document.querySelector('main').scrollTop=0;scrollTo(0,0)");
    const screenshot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
    await writeFile(output+'/settings-'+(mobile?'mobile':'desktop')+'.png',Buffer.from(screenshot.data,'base64'));
  }
  await checkSettingsLayout(false);
  await evaluate("document.getElementById('check-plugin-version').click()");
  await until("document.getElementById('plugin-version').textContent.includes('Installed: 0.8068')");
  assert.equal(await evaluate("document.getElementById('plugin-version').textContent.includes('8-song profile')"),true);
  assert.equal(await evaluate("document.getElementById('plugin-version').textContent.includes('Available: 0.8071')"),true);

  assert.equal(await evaluate("document.querySelector('aside #theme')"), null);
  assert.equal(await evaluate("document.querySelector('aside').textContent.includes('Local companion')"),false);
  await evaluate("document.getElementById('check-extras-version').click()");
  await until("document.getElementById('extras-version').textContent.includes('Installed: 0.0008')");
  await evaluate("document.getElementById('deploy-extras').click()");
  await until("document.getElementById('confirm-action').open");
  await evaluate("document.querySelector('#confirm-action [value=cancel]').click()");
  // The close event is queued: wait for the real confirmation guard to clear
  // before asking to reopen, rather than racing the browser's dialog lifecycle.
  await until("!state.confirming&&!document.getElementById('confirm-action').open");
  assert.deepEqual(await evaluate('window.testPluginWrites'),[]);
  await evaluate("document.getElementById('deploy-extras').click()");
  await until("document.getElementById('confirm-action').open");
  await evaluate("document.getElementById('confirm-accept').click()");
  await until("window.testPluginWrites.length===1");
  assert.deepEqual(await evaluate('window.testPluginWrites'),['bundled-extras']);
  await evaluate("document.getElementById('check-updates').click()");
  await until("document.getElementById('updates').textContent.includes('latest 0.1.14 (update available)')");
  await evaluate("window.testUpdateOffline=true;document.getElementById('check-updates').click()");
  await until("document.getElementById('updates').textContent.includes('does not mean up to date')");
  await evaluate("document.getElementById('release-extras').click()");
  await until("document.getElementById('confirm-action').open");
  await evaluate("document.getElementById('confirm-accept').click()");
  await until("window.testPluginWrites.length===2");
  assert.deepEqual(await evaluate('window.testPluginWrites'),['bundled-extras','extras']);
  // Wheel repeatedly into both scroll limits; sidebar geometry must not follow.
  const asideTop=await evaluate("document.querySelector('aside').getBoundingClientRect().top");
  await evaluate("document.getElementById('theme-settings').scrollIntoView({block:'center'})");
  for(const deltaY of [2000,2000,-4000,-4000]) {
    await send('Input.dispatchMouseEvent',{type:'mouseWheel',x:1000,y:400,deltaX:0,deltaY});
    await new Promise(resolve=>setTimeout(resolve,80));
    assert.equal(await evaluate("document.querySelector('aside').getBoundingClientRect().top"),asideTop);
    assert.equal(await evaluate('scrollY'),0);
  }
  assert.equal(await evaluate("document.getElementById('ip').value"), '192.168.1.67');
  await evaluate(`window.testProgress={job:{id:'1793030351128670239',exit_code:null,cancelled:false},running:true,index:4,lines:['   Project: /private/project','[additive] Retaining 3 library entries; unrelated map files are not audited.','[additive] Validating and converting map/audio...','[additive] Import refused: fixture error']}`);
  await until("state.jobId==='1793030351128670239'");
  assert.equal(await evaluate("document.getElementById('log').textContent.includes('Project:')||document.getElementById('log').textContent.includes('[additive]')||document.getElementById('log').textContent.includes('Retaining 3')"), false);
  assert.equal(await evaluate("state.rawLog.includes('/private/project')"), true);
  assert.equal(await evaluate("document.querySelectorAll('#diagnostics pre').length"), 1);
  assert.equal(await evaluate("document.querySelector('#raw-log')"), null);
  await checkInstallationLog();
  assert.equal(await evaluate("document.getElementById('downloads').open"), false);
  await evaluate("window.testQueue.error=true;window.testQueue.message='Queue could not start: fixture error'");
  await until("document.getElementById('download-activity').classList.contains('failed')");
  assert.equal(await evaluate("document.getElementById('downloads').open"), false);
  assert.equal(await evaluate("document.getElementById('open-downloads').getAttribute('aria-label').includes('attention needed')"), true);
  await evaluate("window.testQueue.error=false;window.testQueue.history=[{id:'retry-failed',map_id:'a123',title:'Failed <img src=x>',status:'failed',error:'Import refused: fixture'}]");
  await until("document.querySelector('[data-queue-retry]')!==null");
  assert.equal(await evaluate("document.querySelectorAll('#queue-history img').length"),0);
  await evaluate("document.getElementById('open-downloads').click();document.querySelector('[data-queue-retry]').click()");
  await until("window.testQueue.pending.some(e=>e.map_id==='a123')");
  assert.equal(await evaluate("window.testQueue.pending.find(e=>e.map_id==='a123').title"),'Failed <img src=x>');
  assert.equal(await evaluate("document.querySelector('[data-queue-retry]').disabled"),true);
  assert.equal(await evaluate("window.testQueue.paused"),true);
  await evaluate("document.getElementById('queue-clear').click();document.getElementById('close-downloads').click()");
  await evaluate("window.testProgress={job:{id:'1793030351128670240',exit_code:0,cancelled:false},running:false,index:1,lines:['[additive] Complete']};window.testQueue.message='Queue finished.'");
  await until("state.jobId==='1793030351128670240'&&document.getElementById('log').textContent==='Complete\\n'");
  assert.equal(await evaluate("document.getElementById('log-title').textContent"),'Last installation log');
  for (const mode of ['light', 'dark']) {
    await evaluate(`document.documentElement.dataset.theme='${mode}';document.getElementById('deploy-plugin').scrollIntoView({block:'center'})`);
    const box = await evaluate("(()=>{const r=document.getElementById('deploy-plugin').getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()");
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...box });
    await new Promise(resolve => setTimeout(resolve, 250));
    const style = await evaluate("(()=>{const s=getComputedStyle(document.getElementById('deploy-plugin'));return {fg:s.color,bg:s.backgroundColor}})()");
    const a = luminance(style.fg), b = luminance(style.bg), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    assert(ratio >= 4.5, `${mode} primary hover contrast ${ratio}`); contrast.push({ theme: mode, ratio, ...style });
    await evaluate("document.querySelector('[data-tab=discover]').click();scrollTo(0,0)");
    await evaluate("notify('Preview unavailable. Check your connection and try again.')");
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(output + '/desktop-' + mode + '.png', Buffer.from(shot.data, 'base64'));
    await evaluate("document.getElementById('open-downloads').click()");
    const downloadShot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    await writeFile(output + '/downloads-' + mode + '.png', Buffer.from(downloadShot.data, 'base64'));
    await evaluate("document.getElementById('close-downloads').click();document.querySelector('[data-tab=settings]').click()");
  }
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await evaluate("document.querySelector('[data-tab=discover]').click();scrollTo(0,0)");
  await until('document.documentElement.scrollWidth<=innerWidth');
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(output + '/mobile-dark.png', Buffer.from(shot.data, 'base64'));
  await evaluate("document.getElementById('open-downloads').click()");
  assert.equal(await evaluate("document.getElementById('downloads').getBoundingClientRect().width<=innerWidth"), true);
  await evaluate("window.testQueue.history=Array.from({length:80},(_,i)=>({id:'mobile-history-'+i,map_id:'abc',title:'History '+i,status:'complete'}));document.getElementById('toggle-log').click();document.getElementById('downloads').scrollTop=0");
  await until("document.querySelectorAll('#queue-history li').length===80");
  assert.equal(await evaluate("(()=>{const r=document.getElementById('toggle-log').getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&document.getElementById('log').clientHeight<=281})()"),true);
  const mobileDialog = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(output + '/downloads-mobile.png', Buffer.from(mobileDialog.data, 'base64'));
  await evaluate("document.getElementById('close-downloads').click()");
  await checkDownloadsModal();
  await evaluate("showDetails(0)");
  await checkDetailsBackdrop();
  await evaluate("document.querySelector('[data-tab=settings]').click();scrollTo(0,0)");
  await checkSettingsLayout(true);
  await evaluate("document.querySelector('[data-tab=library]').click();scrollTo(0,0)");
  assert.equal(await evaluate('document.documentElement.scrollWidth<=innerWidth'), true);
  await evaluate("notify('Removal stopped: one map needs attention. Review Downloads and retry when ready.')");
  const libraryMobile = await send('Page.captureScreenshot', {format:'png',captureBeyondViewport:false});
  await writeFile(output + '/library-mobile.png', Buffer.from(libraryMobile.data,'base64'));
  assert.deepEqual(errors, []);
  await evaluate("setTab('discover')");
  assert.equal(await evaluate("document.getElementById('discover').hidden"),false);
  assert.equal(await evaluate("document.getElementById('results').nextElementSibling===document.getElementById('pagination')"),true);
  assert.equal(await evaluate("(()=>{const p=document.getElementById('pagination').getBoundingClientRect(),r=document.getElementById('results').getBoundingClientRect(),a=document.getElementById('previous').getBoundingClientRect(),b=document.getElementById('next').getBoundingClientRect();return r.width>0&&p.top>=r.bottom&&Math.abs(a.top-b.top)<1&&a.right<b.left})()"),true);
  console.log(JSON.stringify({ ok: true, viewport: '1440x1100 + 390x844', checks: ['minimal header/brand', 'escaped metadata', 'cover click preview start/stop', 'library cover retry without search cache', 'new and legacy map information without library playback controls', 'visible paused-queue removal guard', 'compression-test removal and selected-only serial bulk removal', 'bulk failure stops and selection refresh', 'opt-in whole-card/keyboard library selection', 'metadata compatibility hints, vote counts and relative dates', 'quiet sidebar queue, failed-map Retry and popup', 'active/last log before80history entries, bounded desktop/mobile scroll, follow/pause/jump with no focus or page-scroll theft', 'solid dismissible bottom toast without reflow/focus theft', 'Downloads/details outside-click dismissal, padding/drag/cancel guards desktop/mobile', 'in-page confirmation/accept/cancel/Escape', 'primary button hover contrast', 'read-only binary plugin version and registration check', 'Extras/version and explicit confirmed bundled/release installation (mock writes only)', 'official updates/offline state', 'sidebar stable under repeated wheel scrolling', 'compact connection + Updates columns on desktop and mobile', 'settings', 'no horizontal overflow', 'no JS exceptions'], contrast, consoleWrites: false, api: 'offline fixtures', screenshots: output }, null, 2));
} finally {
  socket.close(); await fetch(cdp + '/json/close/' + page.id);
}
