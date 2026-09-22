"""Self-contained premium HTML research reader.

The module is deliberately browser-library free.  Report data is escaped before it
enters the template and all interaction code is embedded so exported reports remain
portable and work without a network connection.
"""

from html import escape
from urllib.parse import urlsplit

from fathomark_reporting.model import ReportModel


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _valid_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlsplit(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _icon(name: str) -> str:
    return f'<svg class="icon" aria-hidden="true"><use href="#icon-{name}"></use></svg>'


_ICONS = """
<svg class="icon-sprite" aria-hidden="true">
  <symbol id="icon-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></symbol>
  <symbol id="icon-theme" viewBox="0 0 24 24"><path d="M20 15.4A8 8 0 0 1 8.6 4a8 8 0 1 0 11.4 11.4Z"/></symbol>
  <symbol id="icon-more" viewBox="0 0 24 24"><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></symbol>
  <symbol id="icon-print" viewBox="0 0 24 24"><path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><path d="M7 14h10v7H7z"/></symbol>
  <symbol id="icon-pdf" viewBox="0 0 24 24"><path d="M6 2h8l4 4v16H6z"/><path d="M14 2v5h5M8.5 16h7M8.5 12h7"/></symbol>
  <symbol id="icon-up" viewBox="0 0 24 24"><path d="m5 15 7-7 7 7"/></symbol>
  <symbol id="icon-close" viewBox="0 0 24 24"><path d="m5 5 14 14M19 5 5 19"/></symbol>
  <symbol id="icon-chevron" viewBox="0 0 24 24"><path d="m9 5 7 7-7 7"/></symbol>
  <symbol id="icon-book" viewBox="0 0 24 24"><path d="M4 4.5A3.5 3.5 0 0 1 7.5 1H20v18H7.5A3.5 3.5 0 0 0 4 22.5z"/><path d="M4 4.5v18M8 6h8M8 10h8"/></symbol>
  <symbol id="icon-menu" viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16"/></symbol>
  <symbol id="icon-arrow" viewBox="0 0 24 24"><path d="m9 5 7 7-7 7"/></symbol>
  <symbol id="icon-target" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="M12 3v3M21 12h-3"/></symbol>
</svg>
"""


_MARK = """
<svg class="brand-mark" viewBox="0 0 48 48" role="img" aria-label="Fathomark 渊衡">
  <defs><linearGradient id="fmk-gold" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#f1d08a"/><stop offset="1" stop-color="#c9973e"/></linearGradient></defs>
  <circle cx="24" cy="24" r="23" fill="#102a43"/><circle cx="24" cy="24" r="19" fill="none" stroke="#31556f"/>
  <path d="M9 27c5-9 13-13 23-13 3 0 6 .5 8 1.5M11 32c4-5 10-8 17-8 5 0 9 1 12 4M15 37c3-3 7-4 11-4 3 0 6 .5 8 2" fill="none" stroke="url(#fmk-gold)" stroke-width="2.4" stroke-linecap="round"/>
</svg>
"""


_CSS = r"""
:root{color-scheme:light;--report-background:#fff;--report-foreground:#17212b;--report-table-header:#e8eef2;--paper:#f4f1e9;--surface:#fffdf8;--ink:#18252d;--muted:#66726f;--line:#d9d8cf;--teal:#0e6f68;--teal-deep:#094d49;--navy:#102a43;--clay:#a9533f;--gold:#c9973e;--shadow:0 20px 48px rgba(35,45,42,.08);--toolbar-h:64px;font-family:"Avenir Next","Noto Sans CJK SC","Noto Sans",system-ui,sans-serif;line-height:1.7}
html{scroll-behavior:smooth;scroll-padding-top:92px;background:var(--paper)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-size:17px}button,input,summary{font:inherit}button,a,summary{-webkit-tap-highlight-color:transparent}button:active,a:active{transform:translateY(1px)}a{color:var(--teal-deep)}.icon-sprite{position:absolute;width:0;height:0;overflow:hidden}.icon{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:none}
.skip-link{position:fixed;left:16px;top:-60px;z-index:20;background:var(--navy);color:#fff;padding:10px 14px;border-radius:8px}.skip-link:focus{top:12px}.reading-progress{position:fixed;inset:0 0 auto;height:3px;z-index:12;background:transparent}.reading-progress i{display:block;width:0;height:100%;background:linear-gradient(90deg,var(--teal),var(--gold))}
.appbar{height:var(--toolbar-h);position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between;padding:0 clamp(18px,4vw,64px);background:rgba(244,241,233,.92);border-bottom:1px solid rgba(16,42,67,.1);backdrop-filter:blur(18px);box-shadow:inset 0 1px rgba(255,255,255,.6)}.brand{display:flex;align-items:center;gap:10px;color:var(--navy);text-decoration:none}.brand-mark{width:34px;height:34px}.brand span{display:grid;line-height:1.15}.brand b{font-size:12px;letter-spacing:.12em}.brand small{font-size:10px;color:var(--muted)}.toolbar{display:flex;align-items:center;gap:8px}.tool,.mode-switch button,.more-menu summary{border:1px solid rgba(16,42,67,.14);background:rgba(255,253,248,.86);color:var(--navy);height:38px;padding:0 12px;border-radius:10px;display:inline-flex;align-items:center;gap:7px;cursor:pointer;transition:transform .18s ease,border-color .18s ease,background .18s ease}.tool:hover,.more-menu summary:hover,.mode-switch button:hover{border-color:rgba(14,111,104,.55);background:#fff}.mode-switch{display:flex;padding:3px;border:1px solid rgba(16,42,67,.14);border-radius:12px}.mode-switch button{border:0;height:30px;background:transparent;color:var(--muted);white-space:nowrap}.mode-switch button.active{background:var(--navy);color:#fff}.more-menu{position:relative}.more-menu summary{list-style:none}.more-menu summary::-webkit-details-marker{display:none}.more-pop{position:absolute;right:0;top:46px;min-width:190px;padding:7px;background:var(--surface);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow)}.more-pop a,.more-pop button{width:100%;border:0;background:transparent;color:var(--ink);display:flex;align-items:center;gap:10px;text-decoration:none;padding:10px;border-radius:8px;text-align:left;cursor:pointer}.more-pop a:hover,.more-pop button:hover{background:rgba(14,111,104,.08)}
.search-dialog{position:fixed;z-index:30;left:50%;top:82px;transform:translateX(-50%);width:min(680px,calc(100% - 28px));padding:12px;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:0 28px 80px rgba(16,42,67,.2)}.search-dialog[hidden]{display:none}.search-field{display:flex;align-items:center;gap:10px}.search-field input{width:100%;border:0;background:transparent;padding:10px 4px;font-size:18px;color:var(--ink);outline:0}.search-field button{border:0;background:transparent;color:var(--muted);padding:8px;cursor:pointer}.search-meta{display:flex;justify-content:space-between;align-items:center;border-top:1px solid var(--line);padding:9px 4px 0;color:var(--muted);font-size:13px}.search-nav{display:flex;gap:5px}.search-nav button{border:1px solid var(--line);background:transparent;color:var(--ink);border-radius:7px;cursor:pointer}
.cover{min-height:540px;position:relative;overflow:hidden;display:grid;grid-template-columns:minmax(0,1fr) minmax(220px,340px);gap:clamp(30px,7vw,110px);align-items:end;padding:76px clamp(24px,8vw,120px) 70px;background:var(--surface);border-bottom:1px solid var(--line)}.cover::after{content:attr(data-symbol);position:absolute;right:-.03em;top:-.28em;font-size:clamp(170px,28vw,430px);font-weight:800;letter-spacing:-.08em;color:rgba(16,42,67,.035);pointer-events:none}.cover-copy{position:relative;z-index:1;max-width:790px}.eyebrow{margin:0 0 18px;color:var(--clay);font-size:12px;font-weight:750;letter-spacing:.16em}.cover h1{font-size:clamp(44px,7vw,96px);line-height:.96;letter-spacing:-.055em;margin:0;color:var(--navy)}.cover h1 span{display:block;color:var(--teal);font-size:.42em;letter-spacing:-.025em;margin-top:18px}.cover-meta{display:flex;flex-wrap:wrap;gap:10px 18px;margin-top:30px;color:var(--muted);font-size:14px}.cover-meta span{display:inline-flex;gap:6px}.rating-panel{position:relative;z-index:1;padding:28px 0 6px;border-top:2px solid var(--gold)}.rating-panel small{display:block;color:var(--muted);font-size:12px;letter-spacing:.12em}.rating-panel strong{display:block;color:var(--navy);font-size:clamp(46px,6vw,82px);line-height:1;margin:13px 0}.rating-panel p{margin:0;color:var(--muted)}.freshness{display:inline-flex!important;margin-top:18px;padding:6px 9px;border:1px solid var(--line);border-radius:999px;letter-spacing:.06em!important}.freshness[data-state="fresh"]{color:var(--teal);border-color:rgba(14,111,104,.35)}.freshness[data-state="review"]{color:#9a6820;border-color:rgba(201,151,62,.5)}.freshness[data-state="stale"]{color:var(--clay);border-color:rgba(169,83,63,.45)}
.reader-shell{display:grid;grid-template-columns:260px minmax(0,880px);gap:clamp(34px,5vw,76px);justify-content:center;align-items:start;padding:58px clamp(20px,5vw,70px) 110px}.toc{position:sticky;top:90px;max-height:calc(100dvh - 118px);overflow:auto;padding-right:12px}.toc-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;color:var(--navy)}.toc-head strong{font-size:12px;letter-spacing:.12em}.current-readout{font-size:12px;color:var(--teal);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:120px}.toc-group{border-top:1px solid var(--line);padding:9px 0}.toc-group summary{display:flex;align-items:center;justify-content:space-between;cursor:pointer;color:var(--navy);font-size:13px;font-weight:750;list-style:none}.toc-group summary::-webkit-details-marker{display:none}.toc-group summary .icon{transition:transform .2s ease}.toc-group[open] summary .icon{transform:rotate(90deg)}.toc-links{display:grid;padding:7px 0 3px}.toc-links a{padding:6px 8px;border-left:2px solid transparent;color:var(--muted);font-size:13px;line-height:1.35;text-decoration:none}.toc-links a:hover,.toc-links a.active{color:var(--teal-deep);border-left-color:var(--gold);background:rgba(14,111,104,.05)}
.report{min-width:0}.report-section{padding:16px 0 64px;border-top:1px solid var(--line);scroll-margin-top:90px}.report-section:first-child{border-top:0}.section-kicker{margin:0 0 8px;color:var(--clay);font-size:11px;font-weight:750;letter-spacing:.14em}.report h2{margin:0 0 24px;color:var(--navy);font-size:clamp(28px,3.4vw,43px);line-height:1.08;letter-spacing:-.035em}.report h3{color:var(--teal-deep);font-size:21px}.report p,.report li{line-height:1.9}.report a{overflow-wrap:anywhere}.overview-lede{font-size:clamp(21px,2.4vw,30px);line-height:1.45!important;letter-spacing:-.02em;color:var(--navy);max-width:34em}.metric-rail{display:grid;grid-template-columns:repeat(3,1fr);margin:34px 0 10px;border-block:1px solid var(--line)}.metric-link{display:block;min-width:0;padding:20px 18px;text-decoration:none;border-right:1px solid var(--line);transition:background .18s ease}.metric-link:nth-child(3n){border-right:0}.metric-link:nth-child(n+4){border-top:1px solid var(--line)}.metric-link:hover{background:rgba(14,111,104,.055)}.metric-link small{display:block;color:var(--muted);font-size:12px}.metric-link strong{display:block;color:var(--navy);font-size:24px;line-height:1.2;margin:6px 0}.metric-link em{font-style:normal;color:var(--teal);font-size:12px}.metric-link[data-missing="true"] strong{color:#8c928e}.status-note{padding:14px 16px;border-left:3px solid var(--gold);background:rgba(201,151,62,.09);font-weight:650}.hash{font-family:"SFMono-Regular",Consolas,monospace;font-size:12px;overflow-wrap:anywhere;color:var(--muted)}
.table-wrap{max-width:100%;overflow-x:auto;margin:22px 0 30px;border-block:1px solid var(--line)}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:13px 12px;text-align:left;vertical-align:top;border-bottom:1px solid var(--line);overflow-wrap:anywhere}th{background:var(--report-table-header);color:var(--navy);font-size:11px;letter-spacing:.04em}tbody tr:last-child td{border-bottom:0}.factor-name{font-weight:720;color:var(--navy)}.score{font-family:"SFMono-Regular",Consolas,monospace;color:var(--teal-deep);font-weight:750}.valuation-focus{display:grid;grid-template-columns:minmax(160px,240px) 1fr;gap:30px;align-items:start}.valuation-number{padding-top:6px;border-top:2px solid var(--gold)}.valuation-number strong{display:block;font-size:54px;line-height:1;color:var(--navy)}.valuation-number span{color:var(--muted);font-size:13px}.risk-list,.evidence-list{padding:0;list-style:none}.risk-list li,.evidence-list li{padding:17px 0;border-bottom:1px solid var(--line)}.risk-list strong,.evidence-list strong{color:var(--navy)}mark.search-hit{background:rgba(201,151,62,.35);color:inherit;border-radius:2px}mark.search-hit.current{background:#f1c35a;outline:2px solid rgba(169,83,63,.35)}
.artifact-footer{padding:34px clamp(20px,6vw,84px);display:flex;justify-content:space-between;gap:30px;background:var(--navy);color:#eaf0ef}.artifact-footer .brand{color:#fff}.artifact-footer code{max-width:48%;font-size:10px;color:#aebfc8;overflow-wrap:anywhere}.mobile-nav{display:none}.mobile-catalog-close{display:none}
body.quick-mode .report-section[data-quick="false"]{display:none}body.quick-mode .toc-link[data-quick="false"]{display:none}
body.dark{--report-background:#17212b;--report-foreground:#f4f7f9;--report-table-header:#253b4c;--paper:#111d26;--surface:#172731;--ink:#e8eeec;--muted:#a9b7b3;--line:#344853;--teal:#62b8ad;--teal-deep:#85c9c0;--navy:#e9f0f3;--clay:#e08b73;--gold:#deb76a;--shadow:0 20px 48px rgba(0,0,0,.24)}body.dark .appbar{background:rgba(17,29,38,.91)}body.dark .tool,body.dark .mode-switch button,body.dark .more-menu summary{background:rgba(23,39,49,.86)}body.dark .mode-switch button.active{background:#dce7e8;color:#17212b}body.dark .cover::after{color:rgba(255,255,255,.025)}body.dark .metric-link:hover{background:rgba(98,184,173,.08)}
@media(max-width:900px){.reader-shell{grid-template-columns:1fr;padding-inline:clamp(18px,5vw,46px)}.toc{position:fixed;inset:0 auto 0 0;z-index:24;width:min(88vw,340px);max-height:none;padding:24px;background:var(--surface);box-shadow:var(--shadow);transform:translateX(-105%);transition:transform .24s cubic-bezier(.16,1,.3,1)}.toc.mobile-open{transform:none}.mobile-catalog-close{display:inline-flex;border:0;background:transparent;color:var(--ink);cursor:pointer}.cover{grid-template-columns:1fr;min-height:auto;padding-top:68px}.rating-panel{max-width:300px}.toolbar .tool span,.more-menu summary span{display:none}.brand small{display:none}}
@media(max-width:720px){body{font-size:16px}.appbar{padding-inline:12px}.brand span{display:none}.brand-mark{width:30px;height:30px}.mode-switch button{padding-inline:8px;font-size:12px}.cover{padding:56px 20px 46px}.cover h1{font-size:48px}.cover::after{font-size:180px;top:-35px}.reader-shell{padding:34px 18px 100px}.report-section{padding-bottom:48px}.metric-rail{grid-template-columns:1fr}.metric-link,.metric-link:nth-child(3n){border-right:0}.metric-link:nth-child(n+2){border-top:1px solid var(--line)}.table-wrap{overflow:visible;border:0}.table-wrap table,.table-wrap thead,.table-wrap tbody,.table-wrap tr,.table-wrap td{display:block;width:100%}.table-wrap thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}.table-wrap tr{margin:0 0 14px;padding:10px 14px;border:1px solid var(--line);border-radius:12px;background:rgba(255,253,248,.35)}body.dark .table-wrap tr{background:rgba(255,255,255,.025)}.table-wrap td{display:grid;grid-template-columns:minmax(105px,34%) 1fr;gap:10px;padding:8px 0;border-bottom:1px solid var(--line)}.table-wrap td:last-child{border-bottom:0}.table-wrap td::before{content:attr(data-label);color:var(--muted);font-size:11px;font-weight:720;letter-spacing:.03em}.valuation-focus{grid-template-columns:1fr}.artifact-footer{display:grid}.artifact-footer code{max-width:100%}.mobile-nav{position:fixed;z-index:11;left:0;right:0;bottom:0;display:grid;grid-template-columns:1fr 1fr 1fr;background:rgba(244,241,233,.95);border-top:1px solid var(--line);backdrop-filter:blur(16px);padding:8px max(8px,env(safe-area-inset-right)) calc(8px + env(safe-area-inset-bottom)) max(8px,env(safe-area-inset-left))}.mobile-nav button{border:0;background:transparent;color:var(--navy);display:grid;place-items:center;gap:1px;font-size:11px;cursor:pointer}.mobile-nav button:disabled{opacity:.3}.search-dialog{top:70px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important}}
@media print{@page{size:A4;margin:16mm 15mm 18mm}.no-print,.appbar,.reading-progress,.toc,.mobile-nav,.search-dialog,.artifact-footer{display:none!important}:root{--report-background:#fff;--report-foreground:#000;--report-table-header:#eef1ef;--paper:#fff;--surface:#fff;--ink:#17212b;--muted:#5d6663;--line:#cdd2cf;--navy:#102a43;--teal:#0e6f68}html,body{background:#fff;color:#17212b;font-size:9.2pt}.cover{min-height:252mm;display:grid;break-after:page;padding:25mm 12mm 18mm;border:0}.reader-shell{display:block;padding:0}.report-section{display:block!important;padding:0 0 9mm;border-top:0;break-inside:auto}.report-section h2{font-size:20pt;break-after:avoid}.metric-rail{break-inside:avoid}.table-wrap{overflow:visible;break-inside:auto}table{font-size:7.8pt}thead{display:table-header-group}tr{break-inside:avoid}.evidence-list li,.risk-list li{break-inside:avoid}.hash{font-size:7pt}}
"""


_JS = r"""
(()=>{
  const $=(selector,root=document)=>root.querySelector(selector);
  const $$=(selector,root=document)=>Array.from(root.querySelectorAll(selector));
  const body=document.body;
  const reportKey=`fathomark-reader:${body.dataset.reportHash}`;
  const sections=$$('.report-section');
  const tocLinks=$$('.toc-link');
  const searchDialog=$('#search-dialog');
  const searchInput=$('#search-input');
  const searchStatus=$('#search-status');
  let activeIndex=0;
  let searchHits=[];
  let searchIndex=-1;

  $$('.table-wrap table').forEach(table=>{
    const labels=$$('th',table).map(cell=>cell.textContent.trim());
    $$('tbody tr',table).forEach(row=>$$('td',row).forEach((cell,index)=>cell.setAttribute('data-label',labels[index]||'')));
  });

  function setMode(mode,persist=true){
    const quick=mode==='quick';
    body.classList.toggle('quick-mode',quick);
    $$('[data-reading-mode]').forEach(button=>{
      const active=button.dataset.readingMode===mode;
      button.classList.toggle('active',active);
      button.setAttribute('aria-pressed',String(active));
    });
    if(persist)localStorage.setItem(`${reportKey}:mode`,mode);
    updateNavigation();
  }
  $$('[data-reading-mode]').forEach(button=>button.addEventListener('click',()=>setMode(button.dataset.readingMode)));

  function setTheme(theme,persist=true){
    body.classList.toggle('dark',theme==='dark');
    if(persist)localStorage.setItem(`${reportKey}:theme`,theme);
  }
  $('[data-action="theme"]').addEventListener('click',()=>setTheme(body.classList.contains('dark')?'light':'dark'));

  function openSearch(){searchDialog.hidden=false;searchInput.focus();searchInput.select()}
  function closeSearch(){searchDialog.hidden=true;clearSearch()}
  $('[data-action="search"]').addEventListener('click',openSearch);
  $('[data-action="search-close"]').addEventListener('click',closeSearch);
  document.addEventListener('keydown',event=>{
    if((event.metaKey || event.ctrlKey) && event.key.toLowerCase()==='k'){event.preventDefault();openSearch()}
    if(event.key === 'Escape' && !searchDialog.hidden){closeSearch()}
  });

  function clearSearch(){
    $$('mark.search-hit').forEach(mark=>mark.replaceWith(document.createTextNode(mark.textContent)));
    $('#report-content').normalize();searchHits=[];searchIndex=-1;
    searchStatus.textContent='输入关键词搜索全文';
  }
  function showSearchHit(){
    searchHits.forEach((hit,index)=>hit.classList.toggle('current',index===searchIndex));
    if(searchIndex<0){searchStatus.textContent='未找到结果';return}
    const hit=searchHits[searchIndex];
    const section=hit.closest('.report-section');
    const sectionName=section?.querySelector('h2')?.textContent.trim()||'报告正文';
    searchStatus.textContent=`${searchIndex+1} / ${searchHits.length} · ${sectionName}`;
    hit.scrollIntoView({block:'center',behavior:'smooth'});
  }
  function runSearch(){
    clearSearch();const query=searchInput.value.trim();if(!query)return;
    const nodes=[];const walker=document.createTreeWalker($('#report-content'),NodeFilter.SHOW_TEXT,{acceptNode:node=>node.parentElement.closest('script,style,mark')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
    while(walker.nextNode())nodes.push(walker.currentNode);
    const needle=query.toLocaleLowerCase();
    nodes.forEach(node=>{const text=node.data;const lower=text.toLocaleLowerCase();let start=0;let index;let found=false;const fragment=document.createDocumentFragment();while((index=lower.indexOf(needle,start))!==-1){found=true;fragment.append(text.slice(start,index));const mark=document.createElement('mark');mark.className='search-hit';mark.textContent=text.slice(index,index+query.length);fragment.append(mark);start=index+query.length}if(found){fragment.append(text.slice(start));node.replaceWith(fragment)}});
    searchHits=$$('mark.search-hit');searchIndex=searchHits.length?0:-1;showSearchHit();
  }
  searchInput.addEventListener('input',runSearch);
  $('[data-action="search-next"]').addEventListener('click',()=>{if(searchHits.length){searchIndex=(searchIndex+1)%searchHits.length;showSearchHit()}});
  $('[data-action="search-prev"]').addEventListener('click',()=>{if(searchHits.length){searchIndex=(searchIndex-1+searchHits.length)%searchHits.length;showSearchHit()}});

  function visibleSections(){return sections.filter(section=>getComputedStyle(section).display!=='none')}
  function updateNavigation(){
    const visible=visibleSections();const current=sections[activeIndex];const index=Math.max(0,visible.indexOf(current));
    $('#mobile-prev').disabled=index<=0;$('#mobile-next').disabled=index>=visible.length-1;
  }
  function goRelative(offset){const visible=visibleSections();const current=sections[activeIndex];let index=visible.indexOf(current);if(index<0)index=0;visible[Math.max(0,Math.min(visible.length-1,index+offset))]?.scrollIntoView({behavior:'smooth'})}
  $('#mobile-prev').addEventListener('click',()=>goRelative(-1));
  $('#mobile-next').addEventListener('click',()=>goRelative(1));

  const toc=$('#report-toc');
  function openCatalog(){toc.classList.add('mobile-open')}
  function closeCatalog(){toc.classList.remove('mobile-open')}
  $('#mobile-catalog').addEventListener('click',openCatalog);
  $('[data-action="catalog-close"]').addEventListener('click',closeCatalog);
  tocLinks.forEach(link=>link.addEventListener('click',closeCatalog));

  function setActive(section){
    activeIndex=Math.max(0,sections.indexOf(section));
    tocLinks.forEach(link=>link.classList.toggle('active',link.hash===`#${section.id}`));
    $('#current-section').textContent=section.querySelector('h2')?.textContent.trim()||'';
    const activeLink=tocLinks.find(link=>link.hash===`#${section.id}`);
    if(activeLink){const group=activeLink.closest('.toc-group');$$('.toc-group').forEach(item=>item.open=item===group)}
    localStorage.setItem(`${reportKey}:section`,section.id);updateNavigation();
  }
  const observer=new IntersectionObserver(entries=>{entries.forEach(entry=>{if(entry.isIntersecting)setActive(entry.target)})},{rootMargin:'-18% 0px -70%'});
  sections.forEach(section=>observer.observe(section));

  let saveTimer;
  function updateProgress(){const max=document.documentElement.scrollHeight-innerHeight;$('#reading-progress').style.width=`${max?Math.min(100,scrollY/max*100):0}%`;clearTimeout(saveTimer);saveTimer=setTimeout(()=>localStorage.setItem(`${reportKey}:scroll`,String(scrollY)),120)}
  addEventListener('scroll',updateProgress,{passive:true});updateProgress();

  const reportDate=new Date(`${body.dataset.reportDate}T00:00:00`);const days=Math.max(0,Math.floor((Date.now()-reportDate.getTime())/86400000));const freshness=$('#freshness');
  if(days<=30){freshness.dataset.state='fresh';freshness.textContent=`Fresh · ${days}d`}else if(days<=90){freshness.dataset.state='review';freshness.textContent=`Review · ${days}d`}else{freshness.dataset.state='stale';freshness.textContent=`Stale · ${days}d`}

  $('[data-action="print"]').addEventListener('click',()=>window.print());
  $('[data-action="top"]').addEventListener('click',()=>scrollTo({top:0,behavior:'smooth'}));
  $$('[data-close-more]').forEach(item=>item.addEventListener('click',()=>$('#more-menu').open=false));

  const savedTheme=localStorage.getItem(`${reportKey}:theme`);if(savedTheme)setTheme(savedTheme,false);else if(document.documentElement.dataset.theme==='auto')setTheme(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light',false);
  setMode(localStorage.getItem(`${reportKey}:mode`)||'full',false);
  const savedSection=localStorage.getItem(`${reportKey}:section`);const savedScroll=Number(localStorage.getItem(`${reportKey}:scroll`));
  requestAnimationFrame(()=>{if(Number.isFinite(savedScroll)&&savedScroll>0){scrollTo(0,savedScroll)}else if(savedSection&&document.getElementById(savedSection)){document.getElementById(savedSection).scrollIntoView()}});
})();
"""


def _preferred_lens(report: ReportModel):
    return next(
        (lens for lens in report.lenses if lens.lens == report.scope.research_role),
        report.lenses[0] if report.lenses else None,
    )


def _factor(report: ReportModel, name: str):
    return next((factor for factor in report.factors if factor.factor == name), None)


def _toc_group(name: str, sections: list[tuple[str, str, bool]], *, open_: bool) -> str:
    links = "".join(
        f'<a class="toc-link" data-quick="{str(quick).lower()}" href="#{_e(section_id)}">{_e(title)}</a>'
        for section_id, title, quick in sections
    )
    return (
        f'<details class="toc-group" data-toc-group="{_e(name)}"'
        f"{' open' if open_ else ''}><summary>{_e(name)}{_icon('chevron')}</summary>"
        f'<div class="toc-links">{links}</div></details>'
    )


def render_premium_html(report: ReportModel, *, theme: str) -> str:
    """Render a grouped, searchable and responsive research reader."""
    preferred = _preferred_lens(report)
    score = (
        "NR"
        if preferred is None or preferred.total is None
        else f"{preferred.total:.2f}"
    )
    rating = "NR" if preferred is None else preferred.rating
    status_label = "DRAFT — NOT APPROVED" if report.status == "draft" else "APPROVED"
    valuation = _factor(report, "valuation")
    valuation_score = (
        "NR" if valuation is None else f"{valuation.proposed_score:.1f} / 10"
    )
    risk_count = sum(1 for lens in report.lenses if lens.flagged or lens.vetoed) + sum(
        1 for issue in report.review_issues if issue.blocking
    )

    groups = [
        (
            "结论",
            [
                ("executive-overview", "Executive Overview", True),
                ("lens-results", "评分与评级", True),
            ],
        ),
        (
            "公司",
            [
                ("research-scope", "研究范围", False),
                ("factor-proposals", "因子与研究依据", False),
            ],
        ),
        ("估值", [("valuation-analysis", "估值判断", True)]),
        (
            "风险与监控",
            [
                ("risk-monitoring", "风险与监控", True),
                ("evidence-ledger", "证据账本", False),
                ("review-issues", "复核事项", True),
            ],
        ),
    ]
    toc = "".join(
        _toc_group(name, sections, open_=index == 0)
        for index, (name, sections) in enumerate(groups)
    )

    lens_rows = "".join(
        '<tr><td>{}</td><td class="score">{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            _e(lens.lens),
            _e(lens.total if lens.total is not None else "NR"),
            _e(lens.rating),
            _e(lens.tactical_state or "—"),
            "yes" if lens.flagged else "no",
            "yes" if lens.vetoed else "no",
            _e("; ".join(lens.veto_reasons) or "—"),
        )
        for lens in report.lenses
    )
    factor_rows = "".join(
        '<tr><td class="factor-name">{}</td><td class="score">{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
            _e(factor.factor),
            _e(factor.proposed_score),
            _e(factor.confidence),
            ", ".join(
                f'<a href="#{_e(item)}">{_e(item)}</a>' for item in factor.evidence_ids
            )
            or "—",
            ", ".join(
                f'<a href="#{_e(item)}">{_e(item)}</a>'
                for item in factor.counter_evidence_ids
            )
            or "—",
            _e("; ".join(factor.missing_data) or "—"),
            _e(factor.rationale),
        )
        for factor in report.factors
    )
    evidence_items = "".join(
        f'<li id="{_e(item.id)}"><strong>{_e(item.id)} · {_e(item.source_name)}</strong><p>{_e(item.published_date)} · grade {_e(item.grade)}'
        f"{f' · {_e(item.excerpt)}' if item.excerpt else ''}</p>"
        f"{f'<a href="{_e(item.url)}" rel="noreferrer">Source URL</a>' if _valid_url(item.url) else (f'<span>{_e(item.url)}</span>' if item.url else '')}</li>"
        for item in report.evidence
    )
    issue_items = (
        "".join(
            f"<li><strong>{_e(issue.category)} · {'blocking' if issue.blocking else 'non-blocking'}</strong><p>{_e(issue.rationale)}</p><span>{', '.join(f'<a href="#{_e(item)}">{_e(item)}</a>' for item in issue.evidence_ids) or '—'}</span></li>"
            for issue in report.review_issues
        )
        or "<li><strong>No open review issue</strong><p>当前报告模型没有待复核事项。</p></li>"
    )
    flagged = [lens for lens in report.lenses if lens.flagged or lens.vetoed]
    risk_items = (
        "".join(
            f"<li><strong>{_e(lens.lens)} · {_e(lens.rating)}</strong><p>Flagged: {'yes' if lens.flagged else 'no'}; Vetoed: {'yes' if lens.vetoed else 'no'}; Veto reasons: {_e('; '.join(lens.veto_reasons) or '—')}</p></li>"
            for lens in flagged
        )
        or "<li><strong>未触发评分镜头风险门</strong><p>Flagged: no; Vetoed: no; Veto reasons: —</p></li>"
    )

    initial_dark = theme == "dark"
    palette = {
        "light": ("#fff", "#17212b", "#e8eef2"),
        "dark": ("#17212b", "#f4f7f9", "#33414d"),
        "print": ("#fff", "#000", "#fff"),
        "auto": ("#fff", "#17212b", "#e8eef2"),
    }
    try:
        background, foreground, table_header = palette[theme]
    except KeyError as exc:
        raise ValueError(f"unknown HTML theme: {theme}") from exc
    theme_tokens = f":root{{--report-background:{background};--report-foreground:{foreground};--report-table-header:{table_header}}}"

    metrics = [
        ("评分", score, "lens-results", False, "查看评分镜头"),
        ("评级", rating, "lens-results", False, "查看评级依据"),
        (
            "研究角色",
            report.scope.research_role,
            "research-scope",
            False,
            "查看研究边界",
        ),
        (
            "估值因子",
            valuation_score,
            "valuation-analysis",
            valuation is None,
            "查看估值判断",
        ),
        ("价格区间", "NR", "valuation-analysis", True, "模型未提供"),
        ("情景 CAGR", "NR", "valuation-analysis", True, "模型未提供"),
        ("风险门", str(risk_count), "risk-monitoring", False, "查看风险与监控"),
    ]
    metric_html = "".join(
        f'<a class="metric-link" href="#{target}" data-missing="{str(missing).lower()}"><small>{_e(label)}</small><strong>{_e(value)}</strong><em>{_e(note)}</em></a>'
        for label, value, target, missing, note in metrics
    )

    return f"""<!doctype html>
<html lang="en" data-theme="{_e(theme)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="fathomark-template" content="premium-reader-2">
<title>{_e(report.scope.symbol)} Research Report</title>
<style>{theme_tokens}{_CSS}</style>
</head>
<body class="{"dark" if initial_dark else ""}" data-report-hash="{_e(report.model_hash)}" data-report-date="{_e(report.scope.research_date)}">
{_ICONS}
<a class="skip-link" href="#executive-overview">跳到研报正文</a>
<div class="reading-progress no-print"><i id="reading-progress"></i></div>
<header class="appbar no-print">
  <a class="brand" href="#top">{_MARK}<span><b>FATHOMARK · RESEARCH DESK</b><small>深研有据，权衡有度</small></span></a>
  <div class="toolbar">
    <div class="mode-switch" aria-label="阅读模式"><button type="button" data-reading-mode="quick">速读</button><button type="button" data-reading-mode="full" class="active">完整研报</button></div>
    <button class="tool" type="button" data-action="search">{_icon("search")}<span>搜索</span></button>
    <button class="tool" type="button" data-action="theme">{_icon("theme")}<span>主题</span></button>
    <details class="more-menu" id="more-menu"><summary data-action="more">{_icon("more")}<span>更多</span></summary><div class="more-pop">
      <a href="report.pdf" data-close-more>{_icon("pdf")} PDF</a>
      <button type="button" data-action="print" data-close-more>{_icon("print")} 打印</button>
      <button type="button" data-action="top" data-close-more>{_icon("up")} 返回顶部</button>
    </div></details>
  </div>
</header>
<section class="search-dialog no-print" id="search-dialog" role="dialog" aria-label="搜索报告" hidden>
  <div class="search-field">{_icon("search")}<input id="search-input" type="search" placeholder="搜索正文，Cmd / Ctrl + K" aria-label="搜索报告全文"><button type="button" data-action="search-close" aria-label="关闭搜索">{_icon("close")}</button></div>
  <div class="search-meta"><span id="search-status">输入关键词搜索全文</span><div class="search-nav"><button type="button" data-action="search-prev" aria-label="上一个结果">↑</button><button type="button" data-action="search-next" aria-label="下一个结果">↓</button></div></div>
</section>
<section class="cover" id="top" data-symbol="{_e(report.scope.symbol)}">
  <div class="cover-copy"><p class="eyebrow">FATHOMARK · EVIDENCE-LED EQUITY RESEARCH</p><h1>{_e(report.scope.symbol)}<span>Research Report</span></h1><div class="cover-meta"><span>{_e(report.scope.exchange)}</span><span>{_e(report.scope.horizon)}</span><span>{_e(report.scope.research_date)}</span><span>{_e(report.scope.framework_ref)}</span></div></div>
  <aside class="rating-panel"><small>STRATEGIC RATING</small><strong>{_e(rating)}</strong><p>{_e(status_label)}</p><small class="freshness" id="freshness" data-state="fresh">Freshness</small></aside>
</section>
<main class="reader-shell">
  <aside class="toc no-print" id="report-toc"><div class="toc-head"><strong>{_icon("book")} 目录</strong><span class="current-readout" id="current-section">Executive Overview</span><button class="mobile-catalog-close" type="button" data-action="catalog-close" aria-label="关闭目录">{_icon("close")}</button></div>{toc}</aside>
  <article class="report" id="report-content">
    <section class="report-section" id="executive-overview" data-group="结论" data-quick="true"><p class="section-kicker">EXECUTIVE OVERVIEW</p><h2>研究结论</h2><p class="overview-lede">{_e(report.scope.symbol)} 的正式评分结果、研究边界和证据状态集中呈现在这里；点击核心数据可直接进入对应正文。</p><p class="status-note">{_e(status_label)} · Overall confidence: {_e(report.overall_confidence)}</p><div class="metric-rail">{metric_html}</div><p class="hash">Report model: {_e(report.model_hash)}<br>Snapshot: {_e(report.snapshot_hash)}</p></section>
    <section class="report-section" id="lens-results" data-group="结论" data-quick="true"><p class="section-kicker">SCORE &amp; RATING</p><h2>评分与评级</h2><div class="table-wrap"><table><thead><tr><th scope="col">Lens</th><th scope="col">Total</th><th scope="col">Rating</th><th scope="col">Tactical state</th><th scope="col">Flagged</th><th scope="col">Vetoed</th><th scope="col">Veto reasons</th></tr></thead><tbody>{lens_rows}</tbody></table></div></section>
    <section class="report-section" id="research-scope" data-group="公司" data-quick="false"><p class="section-kicker">COMPANY &amp; SCOPE</p><h2>研究范围</h2><p>Exchange: <strong>{_e(report.scope.exchange)}</strong>; Research role: <strong>{_e(report.scope.research_role)}</strong>; Horizon: <strong>{_e(report.scope.horizon)}</strong>; Research date: <strong>{_e(report.scope.research_date)}</strong>; Data cutoff: <strong>{_e(report.scope.data_cutoff)}</strong>.</p><p>Framework: <strong>{_e(report.scope.framework_ref)}</strong>.</p></section>
    <section class="report-section" id="factor-proposals" data-group="公司" data-quick="false"><p class="section-kicker">FACTOR RESEARCH</p><h2>因子与研究依据</h2><div class="table-wrap"><table><thead><tr><th scope="col">Factor</th><th scope="col">Score</th><th scope="col">Confidence</th><th scope="col">Supporting evidence</th><th scope="col">Counter evidence</th><th scope="col">Missing data</th><th scope="col">Rationale</th></tr></thead><tbody>{factor_rows}</tbody></table></div></section>
    <section class="report-section" id="valuation-analysis" data-group="估值" data-quick="true"><p class="section-kicker">VALUATION</p><h2>估值判断</h2><div class="valuation-focus"><div class="valuation-number"><strong>{_e(valuation_score)}</strong><span>估值因子评分</span></div><div><h3>{_e(valuation.rationale if valuation else "当前模型没有提供估值因子。")}</h3><p>价格区间与情景 CAGR 仅在结构化模型明确提供时展示；本报告未提供的字段保持 NR。</p></div></div></section>
    <section class="report-section" id="risk-monitoring" data-group="风险与监控" data-quick="true"><p class="section-kicker">RISK &amp; MONITORING</p><h2>风险与监控</h2><ul class="risk-list">{risk_items}</ul></section>
    <section class="report-section" id="evidence-ledger" data-group="风险与监控" data-quick="false"><p class="section-kicker">EVIDENCE LEDGER</p><h2>证据账本</h2><ol class="evidence-list">{evidence_items}</ol></section>
    <section class="report-section" id="review-issues" data-group="风险与监控" data-quick="true"><p class="section-kicker">REVIEW ISSUES</p><h2>复核事项</h2><ul class="risk-list">{issue_items}</ul></section>
  </article>
</main>
<nav class="mobile-nav no-print" aria-label="章节导航"><button type="button" id="mobile-prev">‹<span>上一节</span></button><button type="button" id="mobile-catalog">{_icon("menu")}<span>目录</span></button><button type="button" id="mobile-next">›<span>下一节</span></button></nav>
<footer class="artifact-footer no-print"><div class="brand">{_MARK}<span><b>Fathomark · 渊衡</b><small>深研有据，权衡有度</small></span></div><span>静态 · 离线 · 自包含</span><code>{_e(report.model_hash)}<br>{_e(report.snapshot_hash)}</code></footer>
<script>{_JS}</script>
</body>
</html>
"""
