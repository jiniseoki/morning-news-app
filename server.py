from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.parse import quote, urlparse
import xml.etree.ElementTree as ET
import json, re, datetime, email.utils, collections
from pathlib import Path
ROOT=Path(__file__).parent
QUERIES={'경제':['경제 금융 증시 금리','global economy markets inflation'],'사회':['사회 사건 교육 노동','world society health climate'],'정책':['정부 정책 법안 국회','international government policy regulation']}
STOP={'대한','한국','국내','관련','정부','오늘','최근','발표','올해','대한민국','뉴스','속보','the','and','for','with','from','after','over','into','says','said','new','will','that','this','국제'}
def tokens(s):
    return set(w.lower() for w in re.findall(r'[가-힣]{2,}|[a-zA-Z]{3,}|\d{2,}',s) if w.lower() not in STOP)
def fetch(q,lang):
    if lang=='ko': params='&hl=ko&gl=KR&ceid=KR:ko'
    else: params='&hl=en-US&gl=US&ceid=US:en'
    url='https://news.google.com/rss/search?q='+quote(q+' when:1d')+params
    req=Request(url,headers={'User-Agent':'Mozilla/5.0 MorningNewsBrief/1.0'})
    with urlopen(req,timeout=12) as res: root=ET.fromstring(res.read())
    out=[]
    for it in root.findall('./channel/item')[:30]:
        title=(it.findtext('title') or '').strip()
        source=it.find('source'); publisher=(source.text or '').strip() if source is not None else ''
        if publisher and title.endswith(' - '+publisher): title=title[:-(len(publisher)+3)]
        dt=it.findtext('pubDate') or ''
        try: published=email.utils.parsedate_to_datetime(dt).isoformat()
        except Exception: published=''
        out.append({'title':title,'url':it.findtext('link') or '', 'publisher':publisher or '출처 미상','published':published})
    return out

def news():
    all_items=[]; errors=[]
    for category,queries in QUERIES.items():
        for region,q in zip(('국내','해외'),queries):
            try:
                for item in fetch(q,'ko' if region=='국내' else 'en'):
                    item.update(category=category,region=region)
                    all_items.append(item)
            except Exception as e: errors.append(category+' '+region+': '+str(e))
    clusters=[]; seen_urls=set()
    for item in all_items:
        if not item['title'] or item['url'] in seen_urls: continue
        seen_urls.add(item['url']); tt=tokens(item['title'])
        best=None; score=0
        for cl in clusters:
            inter=len(tt & cl['tokens']); sim=inter/max(1,min(len(tt),len(cl['tokens'])))
            if inter>=2 and sim>=0.55 and sim>score: best=cl; score=sim
        if best:
            best['articles'].append(item)
            best['tokens'] |= tt
        else: clusters.append({'tokens':tt,'articles':[item]})
    result=[]
    for cl in clusters:
        articles=cl['articles']; publishers=len(set(a['publisher'] for a in articles)); first=articles[0]
        result.append({'title':first['title'],'category':first['category'],'region':first['region'],'coverage':len(articles),'publishers':publishers,'articles':articles[:8]})
    result.sort(key=lambda x:(x['publishers'],x['coverage']),reverse=True)
    return {'updated':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(),'items':result[:30],'sample_size':len(all_items),'errors':errors,'note':'Google 뉴스 검색 RSS의 제한된 기사 표본에서 매체 수와 중복 이슈 보도 수를 기준으로 산정한 참고 순위이며, 전체 언론사의 실제 보도량 순위가 아닙니다.'}
class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT),**kwargs)
    def do_GET(self):
        if urlparse(self.path).path=='/api/news':
            try: body=json.dumps(news(),ensure_ascii=False).encode(); status=200
            except Exception as e: body=json.dumps({'error':str(e)},ensure_ascii=False).encode(); status=503
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        else: super().do_GET()
if __name__=='__main__':
    print('Open http://localhost:8787')
    ThreadingHTTPServer(('0.0.0.0',8787),Handler).serve_forever()
