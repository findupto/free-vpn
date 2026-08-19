from __future__
import base64,csv,gzip,html,io,json,os,re,shutil,ssl,subprocess,tempfile,threading,time,urllib.request,zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=Path(os.environ.get('LOCALAPPDATA',tempfile.gettempdir()))/'FinduptoVPN'
LOG=ROOT/'diagnostic.log'; PROFILE_LOGS=ROOT/'openvpn-logs'; CACHE=ROOT/'servers.json'
UA='FinduptoVPN/9.0.0'
GATE_URLS=('https://www.vpngate.net/api/iphone/','https://download.vpngate.jp/api/iphone/')
VPNBOOK_PAGE='https://www.vpnbook.com/freevpn/openvpn'
VPNBOOK={'us16':('United States','US16'),'us178':('United States','US178'),'ca149':('Canada','CA149'),'ca196':('Canada','CA196'),'uk205':('United Kingdom','UK205'),'uk68':('United Kingdom','UK68'),'de20':('Germany','DE20'),'de220':('Germany','DE220'),'fr200':('France','FR200'),'fr2311':('France','FR231')}
_lock=threading.Lock()
def log(msg:str)->None:
 ROOT.mkdir(parents=True,exist_ok=True)
 with _lock:
  with LOG.open('a',encoding='utf-8') as f:f.write(f'[{time.strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
def _curl()->str|None:
 for name in ('curl.exe','curl'):
  p=shutil.which(name)
  if p:return p
 return None
def http_get(url:str,timeout:float=12,limit:int=10000000)->bytes:
 started=time.monotonic();log(f'HTTP START {url} timeout={timeout:.1f}s limit={limit}')
 curl=_curl()
 if curl:
  cmd=[curl,'--fail','--silent','--show-error','--location','--compressed','--connect-timeout',str(max(2,int(timeout*.4))),'--max-time',str(max(3,int(timeout))),'-A',UA,url]
  try:
   cp=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout+2,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
   if cp.returncode:raise RuntimeError(f'curl exit {cp.returncode}: {cp.stderr.decode("utf-8","replace")[-500:]}')
   data=cp.stdout
   if len(data)>limit:raise RuntimeError('response too large')
   log(f'HTTP OK {url} bytes={len(data)} elapsed={time.monotonic()-started:.2f}s method=curl');return data
  except Exception as e:log(f'HTTP CURL FAIL {url} error={type(e).__name__}: {e}')
 req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Connection':'close'})
 try:
  with urllib.request.urlopen(req,timeout=min(timeout,12),context=ssl.create_default_context()) as r:
   data=r.read(limit+1)
   if len(data)>limit:raise RuntimeError('response too large')
   enc=(r.headers.get('Content-Encoding') or '').lower()
   if 'gzip' in enc:data=gzip.decompress(data)
   log(f'HTTP OK {url} bytes={len(data)} elapsed={time.monotonic()-started:.2f}s method=urllib');return data
 except Exception as e:log(f'HTTP FAIL {url} elapsed={time.monotonic()-started:.2f}s error={type(e).__name__}: {e}');raise
def parse_gate(raw:bytes)->list[dict]:
 text=raw.decode('utf-8-sig','replace').replace('\r','');lines=text.split('\n');header=next((x for x in lines if x.startswith('#HostName,')),None)
 if not header:raise RuntimeError('VPN Gate CSV header missing')
 fields=next(csv.reader([header[1:]]));out=[]
 for line in lines:
  if not line or line.startswith('#'):continue
  try:row=next(csv.reader([line]))
  except Exception:continue
  if len(row)<len(fields):continue
  d=dict(zip(fields,row));ip=(d.get('IP') or '').strip();host=(d.get('HostName') or '').strip();cfg=(d.get('OpenVPN_ConfigData_Base64') or '').strip()
  if not ip or not host or not cfg:continue
  try:ping=float(d.get('Ping') or 9999)
  except Exception:ping=9999
  try:speed=float(d.get('Speed') or 0)/1000000
  except Exception:speed=0
  try:uptime=float(d.get('Uptime') or 0)/86400
  except Exception:uptime=0
  try:score=float(d.get('Score') or 0)
  except Exception:score=0
  out.append({'id':f'gate:{ip}:{host}','ip':ip,'host':host,'country':d.get('CountryLong') or d.get('CountryShort') or 'Unknown','city':d.get('City') or 'Unknown','ping':ping,'speed':speed,'rank':speed*5+min(uptime,100)*.12+score*.01-min(ping,2000)*.28,'config':cfg,'source':'VPN Gate','kind':'gate'})
 return sorted(out,key=lambda s:s['rank'],reverse=True)
def vpnbook_servers()->list[dict]:
 return [{'id':f'book:{sid}','sid':sid,'ip':f'{sid}.vpnbook.com','host':f'{sid}.vpnbook.com','country':c,'city':city,'ping':9999,'speed':0,'rank':-50,'source':'VPNBook','kind':'book','bundle':f'https://www.vpnbook.com/free-openvpn-account/vpnbook-openvpn-{sid}.zip'} for sid,(c,city) in VPNBOOK.items()]
def _cache_load()->list[dict]:
 try:
  d=json.loads(CACHE.read_text(encoding='utf-8'));return d.get('servers',[]) if time.time()-float(d.get('time',0))<86400 else []
 except Exception:return []
def _cache_save(servers:list[dict])->None:
 try:
  ROOT.mkdir(parents=True,exist_ok=True);tmp=CACHE.with_suffix('.tmp');tmp.write_text(json.dumps({'time':time.time(),'servers':servers},separators=(',',':')),encoding='utf-8');tmp.replace(CACHE)
 except Exception as e:log(f'CACHE SAVE FAIL {type(e).__name__}: {e}')
def discover(deadline:float=12)->list[dict]:
 start=time.monotonic();merged={s['id']:s for s in vpnbook_servers()}
 for s in _cache_load():merged[s.get('id',f"cache:{s.get('ip','')}")]=s
 log(f'DISCOVERY START cache={len(merged)}')
 with ThreadPoolExecutor(max_workers=2) as ex:
  futures=[ex.submit(http_get,u,min(deadline,10),8000000) for u in GATE_URLS]
  for fut in as_completed(futures,timeout=deadline+1):
   try:
    for s in parse_gate(fut.result()):merged[s['id']]=s
    log('DISCOVERY GATE OK')
   except Exception as e:log(f'DISCOVERY GATE FAIL {type(e).__name__}: {e}')
 data=sorted(merged.values(),key=lambda s:(s.get('rank',-999),-s.get('ping',9999)),reverse=True)[:180];_cache_save(data);log(f'DISCOVERY READY candidates={len(data)} elapsed={time.monotonic()-start:.2f}s');return data
def openvpn_exe()->str|None:
 for p in (shutil.which('openvpn.exe'),shutil.which('openvpn'),r'C:\Program Files\OpenVPN\bin\openvpn.exe'):
  if p and os.path.isfile(p) and p.lower().endswith('openvpn.exe'):return p
 return None
def _vpnbook_profiles(server:dict)->list[str]:
 raw=http_get(server['bundle'],15,5000000)
 if not raw.startswith(b'PK'):raise RuntimeError(f'VPNBook returned invalid bundle ({len(raw)} bytes)')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  names=[n for n in z.namelist() if n.lower().endswith('.ovpn')]
  if not names:raise RuntimeError('VPNBook bundle contains no .ovpn profiles')
  order=('tcp443','tcp80','udp53','udp25000');names=sorted(names,key=lambda n:next((i for i,k in enumerate(order) if k in n.lower()),99));log(f'VPNBOOK PROFILES server={server["host"]} profiles={len(names)} order={names}');return [z.read(n).decode('utf-8-sig','replace') for n in names]
def _vpnbook_password()->str:
 raw=http_get(VPNBOOK_PAGE,12,10000000).decode('utf-8','replace');text=re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>','\n',raw)));m=re.search(r'(?:VPN\s+)?Password\s*[:\-]?\s*([A-Za-z0-9]{6,24})',text,re.I)
 if not m:raise RuntimeError('VPNBook current password not found')
 value=m.group(1)
 if value.lower() in {'password','vpnbook','credentials','updated'}:raise RuntimeError('VPNBook password parser rejected invalid value')
 log(f'VPNBOOK AUTH username=vpnbook length={len(value)} fingerprint={value[:2]}***{value[-2:]}');return value
def _profiles(server:dict)->tuple[list[str],str,str]:
 if server['kind']=='gate':return [base64.b64decode(server['config']+'===').decode('utf-8-sig','replace')],'vpn','vpn'
 return _vpnbook_profiles(server),'vpnbook',_vpnbook_password()
def _prepare(profile:str,username:str,password:str,path:Path)->None:
 auth=path/'auth.txt';auth.write_text(username+'\n'+password+'\n',encoding='utf-8');lines=[line for line in profile.splitlines() if not line.strip().lower().startswith('auth-user-pass')];lines += [f'auth-user-pass "{auth}"','auth-nocache','resolv-retry infinite','connect-retry 2 3','connect-timeout 10','verb 4'];(path/'client.ovpn').write_text('\n'.join(lines)+'\n',encoding='utf-8')
def _classify(text:str,code:int|None)->str:
 low=text.lower()
 for key,msg in (('auth_failed','authentication failed'),('options error','OpenVPN configuration error'),('tls error','TLS handshake failed'),('connection refused','connection refused'),('network is unreachable','network unreachable'),('cannot open tun','TUN/TAP adapter unavailable'),('all tap-windows adapters','TUN/TAP adapter unavailable'),('access is denied','administrator permission required')):
  if key in low:return msg
 return f'OpenVPN exited with code {code}' if code is not None else 'connection timeout'
def connect(server:dict,total_deadline:float=50):
 exe=openvpn_exe()
 if not exe:raise RuntimeError('OpenVPN Community is not installed. Install OpenVPN Community and retry.')
 started=time.monotonic();profiles,user,pwd=_profiles(server);PROFILE_LOGS.mkdir(parents=True,exist_ok=True);last=''
 for idx,profile in enumerate(profiles,1):
  if time.monotonic()-started>=total_deadline:break
  work=Path(tempfile.mkdtemp(prefix='findupto-vpn-'));conf=work/'client.ovpn';_prepare(profile,user,pwd,work);logfile=PROFILE_LOGS/f'{server["host"].replace(":","_")}-{int(time.time())}-v{idx}.log';p=None
  try:
   p=subprocess.Popen([exe,'--config',str(conf),'--log',str(logfile),'--log-append','--route-delay','2'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));log(f'OPENVPN START server={server["host"]} variant={idx}/{len(profiles)} pid={p.pid} log={logfile}');deadline=min(started+total_deadline,time.monotonic()+14)
   while time.monotonic()<deadline:
    text=logfile.read_text(encoding='utf-8',errors='replace') if logfile.exists() else ''
    if 'Initialization Sequence Completed' in text:log(f'OPENVPN INITIALIZED server={server["host"]} variant={idx} pid={p.pid}');return p,work,logfile
    if p.poll() is not None:last=_classify(text,p.returncode);break
    time.sleep(.25)
   if p and p.poll() is None:last='connection timeout';p.terminate()
   if p:
    try:p.wait(timeout=3)
    except Exception:
     try:p.kill()
     except Exception:pass
   text=logfile.read_text(encoding='utf-8',errors='replace') if logfile.exists() else ''
   if text:last=_classify(text,p.returncode if p else None)
   log(f'OPENVPN ATTEMPT FAIL server={server["host"]} variant={idx} reason={last}')
  except Exception as e:last=f'{type(e).__name__}: {e}';log(f'OPENVPN ATTEMPT EXCEPTION server={server["host"]} variant={idx} error={last}')
  finally:
   if p and p.poll() is None:
    try:p.kill()
    except Exception:pass
   shutil.rmtree(work,ignore_errors=True)
 log(f'CONNECT FAIL server={server["host"]} reason={last or "all OpenVPN profiles failed"}');raise RuntimeError(last or 'all OpenVPN profiles failed; see OpenVPN logs')
def verify_tunnel(timeout:float=8)->str:
 before=None
 try:before=http_get('https://api.ipify.org',timeout,256).decode('ascii','ignore').strip()
 except Exception:pass
 for url in ('https://api.ipify.org','https://ifconfig.me/ip','https://icanhazip.com'):
  try:
   ip=http_get(url,timeout,256).decode('ascii','ignore').strip()
   if re.fullmatch(r'(?:\d{1,3}\.){3}\d{1,3}',ip) or ':' in ip:log(f'TUNNEL VERIFIED public_ip={ip} previous_ip={before or "unknown"}');return ip
  except Exception as e:log(f'TUNNEL VERIFY FAIL {url}: {type(e).__name__}: {e}')
 raise RuntimeError('OpenVPN initialized but public-IP verification failed; tunnel is not trusted')
