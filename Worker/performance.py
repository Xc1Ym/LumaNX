"""Opt-in existing-engine HUD/telemetry and manually timed benchmark sections."""
import array,csv,datetime,fcntl,html,json,math,os,platform,re,shutil,statistics,subprocess,time,uuid
from pathlib import Path
from core import Failure,atomic,read,contained
METRICS={'@frame_ms','@presented_ms','@pres_at_ms','@gpu_ms','@t_s'}

def percentile(values,fraction):
    if not values:return None
    values=sorted(values);index=(len(values)-1)*fraction;low=int(index);high=min(low+1,len(values)-1)
    return values[low]+(values[high]-values[low])*(index-low)

def statistics_for(values):
    values=[v for v in values if math.isfinite(v) and v>0]
    if not values:return dict(samples=0)
    mean=statistics.fmean(values)
    return dict(samples=len(values),meanFrameMs=mean,fpsFromMeanInterval=1000/mean,p50Ms=percentile(values,.5),p95Ms=percentile(values,.95),p99Ms=percentile(values,.99),maxMs=max(values),framesOver33_3Ms=sum(v>100/3 for v in values),framesOver50Ms=sum(v>50 for v in values),framesOver100Ms=sum(v>100 for v in values),framesOver250Ms=sum(v>250 for v in values))

def rows(path):
    # GPU/present data arrives eight frames late. Keep a bounded reordering window.
    pending={};highest=0
    try:stream=Path(path).open(newline='')
    except FileNotFoundError:return
    with stream:
        for line in stream:
            if len(line)>4096:continue
            fields=line.rstrip('\n').split('\t')
            if len(fields)!=3 or fields[1] not in METRICS:continue
            try:frame=int(fields[0]);value=float(fields[2])
            except ValueError:continue
            if frame<0 or not math.isfinite(value):continue
            highest=max(highest,frame);pending.setdefault(frame,{})[fields[1]]=value
            for old in sorted(k for k in pending if k<highest-64):yield old,pending.pop(old)
        yield from sorted(pending.items())

def sections(events):
    result=[];active=None
    for event in events:
        if event.get('action')=='start':active=event
        elif event.get('action')=='end' and active:
            result.append(dict(label=active['label'],startSeconds=active['elapsedSeconds'],endSeconds=event['elapsedSeconds'],durationSeconds=max(0,event['elapsedSeconds']-active['elapsedSeconds'])));active=None
    if active:result.append(dict(label=active['label'],startSeconds=active['elapsedSeconds'],incomplete=True))
    return result

def summarize(session):
    meta=read(session/'session.json');events=[]
    for line in (session/'markers.jsonl').read_text().splitlines() if (session/'markers.jsonl').exists() else []:
        try:events.append(json.loads(line))
        except ValueError:continue
    phases=sections(events);present=array.array('d');fallback=array.array('d');gpu=array.array('d');discarded=0;first=None;samples=[array.array('d') for _ in phases]
    with (session/'frames.csv').open('w',newline='') as out:
        writer=csv.writer(out);writer.writerow(['frame','engine_seconds','presented_interval_ms','present_call_interval_ms','gpu_ms'])
        for frame,data in rows(session/'engine-timing.tsv'):
            p=data.get('@presented_ms');f=data.get('@frame_ms');g=data.get('@gpu_ms');stamp=data.get('@pres_at_ms')
            stamp=stamp/1000 if stamp is not None and stamp>=0 else data.get('@t_s')
            writer.writerow([frame,stamp,p,f,g])
            if f is not None and f>0:fallback.append(f)
            if g is not None and g>=0:gpu.append(g)
            if p is not None and p<0:discarded+=1
            if p is not None and p>0:
                present.append(p)
                for phase,values in zip(phases,samples):
                    if stamp is not None and phase.get('endSeconds') is not None and phase['startSeconds']<=stamp<=phase['endSeconds']:values.append(p)
            if data.get('@pres_at_ms',0)>0:first=stamp if first is None else min(first,stamp)
    for phase,values in zip(phases,samples):phase['displayedFrames']=statistics_for(values)
    log=(session/'engine.log').read_text(errors='replace') if (session/'engine.log').exists() else ''
    prewarm=[float(v) for v in re.findall(r'pipeline prepare:.*? in ([0-9.]+) s',log)]
    result=dict(schema=1,gameId=meta['gameId'],label=meta.get('label',''),storage=meta['storage'],gameOutcome=meta.get('gameOutcome','unknown'),timingSource='on-screen presentation intervals' if present else 'present-call intervals (not display FPS)' if fallback else 'unavailable',overall=statistics_for(present or fallback),discardedPresentations=discarded,gpu=dict(samples=len(gpu),p50Ms=percentile(gpu,.5),p95Ms=percentile(gpu,.95)),firstRecordedPresentationEngineSeconds=first,pipelinePrewarmSeconds=prewarm,sections=phases,manualHitches=[e for e in events if e.get('action')=='hitch'],visibilityWarning=('window covered' in log or 'focus lost' in log or bool(re.search(r'oe focus state[^\n]*[→>]\s*1\b',log))),notes=['Manual durations use the monotonic clock and include user reaction time.','Section/frame alignment uses process launch as the approximate engine clock origin.','First recorded presentation is not proof the title screen or game world is ready.','Overall metrics include menus, startup and loading; compare matching gameplay sections.','HUD and recording add overhead; compare runs with identical instrumentation.','Keep the game visible and focused; covered/background timing is not comparable gameplay data.','Caches are left intact. Restarting a game does not establish a cold disk cache.','Threshold counts are raw frame intervals, not proof storage caused a hitch.'])
    atomic(session/'summary.json',result)
    def table(data):return '<table>'+''.join('<tr><th>'+html.escape(k)+'</th><td>'+html.escape(f'{v:.3f}' if isinstance(v,float) else str(v))+'</td></tr>' for k,v in data.items())+'</table>'
    content='<h1>Performance session</h1><p>'+html.escape(meta.get('label',''))+'</p><p>'+html.escape(meta.get('gameName',''))+' — '+html.escape(meta['storage'])+'</p><p>'+html.escape(result['timingSource'])+'</p><h2>Overall</h2>'+table(result['overall'])
    if result['visibilityWarning']:content+='<p><strong>Focus/visibility changed: this run is not a controlled gameplay comparison.</strong></p>'
    content+='<h2>GPU timing</h2>'+table(result['gpu'])+'<h2>Presentation and startup diagnostics</h2>'+table(dict(discardedPresentations=discarded,firstRecordedPresentationEngineSeconds=first,pipelinePrewarmSeconds=prewarm))
    for phase in phases:content+='<h2>'+html.escape(phase['label'])+'</h2>'+table({k:v for k,v in phase.items() if k!='displayedFrames'})+table(phase['displayedFrames'])
    content+='<h2>Manual hitch markers</h2><p>'+str(len(result['manualHitches']))+' marked; times are in summary.json and markers.jsonl.</p><h2>Interpretation</h2><ul>'+''.join('<li>'+html.escape(n)+'</li>' for n in result['notes'])+'</ul>'
    (session/'report.html').write_text('<!doctype html><meta charset="utf-8"><title>Performance session</title><style>body{font:16px system-ui;max-width:960px;margin:40px auto;padding:0 20px}table{border-collapse:collapse}th,td{text-align:left;padding:6px 16px;border-bottom:1px solid #ddd}th{font-weight:500}</style>'+content)
    meta.update(ended=time.time(),state='completed');atomic(session/'session.json',meta)
    return result

def process_token(pid):
    try:return subprocess.check_output(['/bin/ps','-p',str(pid),'-o','lstart='],text=True,stderr=subprocess.DEVNULL,timeout=2).strip()
    except (OSError,subprocess.SubprocessError):return ''

def begin(c,game,runtime,env):
    # Override inherited switches for this child process only, never global defaults.
    hud=c.r.get('performanceHUD') is True;env.update(DM_METAL_HUD='1' if hud else '0',MTL_HUD_ENABLED='1' if hud else '0')
    if c.r.get('recordPerformance') is not True:return None
    identifier=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    session=contained(c.library,c.library/'benchmarks'/game['id']/identifier);session.mkdir(parents=True,mode=0o700)
    manifest=read(runtime/'manifest.json',{});hardware=[]
    label=c.r.get('benchmarkLabel','')
    label=''.join(ch for ch in label[:80] if ch.isprintable()) if isinstance(label,str) else ''
    try:hardware=subprocess.check_output(['/usr/sbin/sysctl','-n','hw.model','machdep.cpu.brand_string','hw.memsize'],text=True,stderr=subprocess.DEVNULL,timeout=2).splitlines()
    except (OSError,subprocess.SubprocessError):pass
    meta=dict(schema=1,id=identifier,gameId=game['id'],gameName=game.get('name',''),label=label,assetLocation=env.get('DM_ROMFS',''),started=time.time(),launchMonotonic=time.monotonic(),state='running',workerPID=os.getpid(),workerToken=process_token(os.getpid()),purpose='validation' if c.r.get('benchmarkValidation') is True else 'user',storage='compressed' if manifest.get('assetCompression') else 'uncompressed',engine=manifest.get('engine'),chain=manifest.get('chain'),gameVersion=manifest.get('version'),OS=platform.mac_ver()[0],machine=platform.machine(),hardware=hardware,launcher=read(c.resource/'product.json',{}),HUD=hud,graphics=manifest.get('graphics','nvn'))
    atomic(session/'session.json',meta);atomic(c.library/('.benchmark-'+game['id']+'.json'),dict(id=identifier))
    if meta['graphics']=='nvn':env.update(DM_NVN_TSV=str(session/'engine-timing.tsv'),DM_NVN_TSV_CALLS='0')
    c.emit('message','Recording performance session: '+str(session));return session

def finish(c,game,session):
    if session is None:return
    # Context.lock checks cancellation; finalization must also run after Cancel.
    with (c.library/'.benchmark-markers.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        active=c.library/('.benchmark-'+game['id']+'.json')
        if read(active,{}).get('id')==session.name:active.unlink(missing_ok=True)
        summarize(session)

def marker(c):
    game=c.game();identifier=read(c.library/('.benchmark-'+game['id']+'.json'),{}).get('id','')
    if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{8}',identifier):raise Failure('Launch the game with performance recording enabled first.')
    session=contained(c.library,c.library/'benchmarks'/game['id']/identifier);action=c.r.get('markerAction');label=c.r.get('markerLabel','Gameplay')
    if action not in ('start','end','hitch') or label not in ('Loading','Transition','Gameplay'):raise Failure('Invalid benchmark marker.')
    value=c.r.get('markerMonotonic',time.monotonic())
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or abs(value-time.monotonic())>30:raise Failure('Timing marker expired. Please retry.')
    with c.lock('benchmark-markers'):
        if read(c.library/('.benchmark-'+game['id']+'.json'),{}).get('id')!=identifier:raise Failure('Performance session has ended.')
        meta=read(session/'session.json')
        if not meta.get('workerToken') or process_token(meta.get('workerPID'))!=meta['workerToken']:raise Failure('Performance session is no longer running.')
        path=session/'markers.jsonl';events=[json.loads(line) for line in path.read_text().splitlines()] if path.exists() else [];active=None
        for e in events:
            if e['action']=='start':active=e
            elif e['action']=='end':active=None
        if action=='start' and active:raise Failure('Stop the current timed section first.')
        if action=='end' and not active:raise Failure('Start a timed section first.')
        event=dict(action=action,label=active['label'] if action=='end' else label,elapsedSeconds=max(0,value-meta['launchMonotonic']))
        with path.open('a') as stream:stream.write(json.dumps(event)+'\n');stream.flush();os.fsync(stream.fileno())
        if action=='start':atomic(session/'phase.json',dict(active=True,label=label,startMonotonic=value))
        elif action=='end':atomic(session/'phase.json',dict(active=False))
    return dict(event=event)

def launch(c):
    # Dispatch wrapper avoids touching build.py: telemetry cannot invalidate builds.
    import build
    original=c.run;session=None
    def run(args,log=None,env=None,**kwargs):
        nonlocal session
        if not args or Path(args[0]).name!='dmhost':return original(args,log,env,**kwargs)
        runtime=Path(args[0]).parent;game=c.game();env=dict(env or {});session=begin(c,game,runtime,env)
        offset=Path(log).stat().st_size if log and Path(log).exists() else 0
        try:value=original(args,log,env,**kwargs);outcome='exited';return value
        except BaseException as error:outcome='cancelled' if type(error).__name__=='Cancelled' else 'failed';raise
        finally:
            if session:
                try:
                    meta=read(session/'session.json');meta['gameOutcome']=outcome;atomic(session/'session.json',meta)
                    if log and Path(log).exists():
                        with Path(log).open('rb') as source,(session/'engine.log').open('wb') as destination:source.seek(offset);shutil.copyfileobj(source,destination)
                    finish(c,game,session);c.emit('message','Performance report saved: '+str(session/'report.html'))
                except Exception as error:c.emit('message','Performance report could not be finalized: '+str(error))
    c.run=run
    try:
        result=build.launch(c)
        if session:result['performanceSession']=str(session)
        return result
    finally:c.run=original
