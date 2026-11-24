import contextlib,io,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'Worker'))
import performance
from core import Context,Failure,atomic
class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.lib=self.root/'library';self.lib.mkdir();self.game=dict(id='040074A01BF12000',name='Synthetic game',packages=[])
        self.c=Context(dict(operation='launch',privateRoot=str(self.root/'private'),library=str(self.lib),gameId=self.game['id'],performanceHUD=True,recordPerformance=True))
        self.c.save_catalog(dict(games=[self.game]));self.runtime=self.lib/'games'/self.game['id']/'current';self.runtime.mkdir(parents=True)
        atomic(self.runtime/'manifest.json',dict(assetCompression=True,graphics='nvn',engine='fixture',version='1',chain='abc'))
    def tearDown(self):self.tmp.cleanup()
    def quiet(self,fn,*args):
        with contextlib.redirect_stdout(io.StringIO()):return fn(*args)
    def begin(self):
        self.env={};return self.quiet(performance.begin,self.c,self.game,self.runtime,self.env)
    def test_hud_per_launch_and_recording_opt_in(self):
        env={'MTL_HUD_ENABLED':'1'};self.c.r.update(performanceHUD=False,recordPerformance=False)
        self.assertIsNone(self.quiet(performance.begin,self.c,self.game,self.runtime,env));self.assertEqual(env['MTL_HUD_ENABLED'],'0');self.assertFalse((self.lib/'benchmarks').exists())
        self.c.r.update(performanceHUD=True,recordPerformance=True);s=self.begin()
        self.assertEqual(self.env['DM_METAL_HUD'],'1');self.assertEqual(self.env['DM_NVN_TSV_CALLS'],'0');self.assertTrue(s.exists())
    def write_rows(self,s):
        text='frame\tname\tvalue\n'
        for n,p in enumerate([10,20,40,60,-1],1):
            text+=f'{n}\t@frame_ms\t12\n{n}\t@presented_ms\t{p}\n{n}\t@gpu_ms\t5\n'
            if p>0:text+=f'{n}\t@pres_at_ms\t{n*1000}\n'
        (s/'engine-timing.tsv').write_text(text+'bad\t@frame_ms\tnan\n9\t@frame_ms\tinf\n')
    def test_display_metrics_percentiles_hitches_discarded_and_manual_sections(self):
        s=self.begin();self.write_rows(s)
        (s/'markers.jsonl').write_text('\n'.join(json.dumps(v) for v in [dict(action='start',label='Gameplay',elapsedSeconds=1.5),dict(action='hitch',label='Gameplay',elapsedSeconds=2.5),dict(action='end',label='Gameplay',elapsedSeconds=3.5)])+'\n')
        report=performance.summarize(s)
        self.assertEqual(report['overall']['samples'],4);self.assertAlmostEqual(report['overall']['fpsFromMeanInterval'],1000/32.5);self.assertAlmostEqual(report['overall']['p95Ms'],57);self.assertEqual(report['overall']['framesOver50Ms'],1)
        self.assertEqual(report['discardedPresentations'],1);self.assertEqual(report['sections'][0]['displayedFrames']['samples'],2);self.assertEqual(len(report['manualHitches']),1);self.assertEqual(report['sections'][0]['durationSeconds'],2)
        self.assertTrue((s/'frames.csv').exists());self.assertTrue((s/'report.html').exists())
    def test_native_focus_loss_marks_run_as_not_comparable(self):
        s=self.begin();(s/'engine.log').write_text('[dm] oe focus state → 1\n')
        self.assertTrue(performance.summarize(s)['visibilityWarning'])
    def test_no_data_and_fallback_not_fake_display_fps(self):
        s=self.begin();self.assertEqual(performance.summarize(s)['timingSource'],'unavailable');(s/'engine-timing.tsv').write_text('1\t@frame_ms\t25\n')
        self.assertIn('not display FPS',performance.summarize(s)['timingSource'])
    def test_late_present_rows_survive_reordering(self):
        s=self.begin();lines=[]
        for frame in range(100):
            lines.append(f'{frame}\t@frame_ms\t16')
            if frame>=8:lines.extend([f'{frame-8}\t@presented_ms\t16.667',f'{frame-8}\t@pres_at_ms\t{(frame-8)*16.667}'])
        (s/'engine-timing.tsv').write_text('\n'.join(lines));self.assertEqual(performance.summarize(s)['overall']['samples'],92)
    def test_active_markers_duplicate_start_and_finish(self):
        s=self.begin();self.c.r.update(markerAction='start',markerLabel='Loading',markerMonotonic=time.monotonic());self.quiet(performance.marker,self.c)
        with self.assertRaises(Failure):self.quiet(performance.marker,self.c)
        self.assertTrue(json.loads((s/'phase.json').read_text())['active']);self.c.r.update(markerAction='end',markerMonotonic=time.monotonic());self.quiet(performance.marker,self.c)
        self.assertFalse(json.loads((s/'phase.json').read_text())['active']);self.quiet(performance.finish,self.c,self.game,s)
        with self.assertRaises(Failure):self.quiet(performance.marker,self.c)
    def test_cancellation_still_finalizes(self):
        s=self.begin();self.c.cancelled=True;self.quiet(performance.finish,self.c,self.game,s)
        self.assertFalse((self.lib/('.benchmark-'+self.game['id']+'.json')).exists());self.assertTrue((s/'summary.json').exists())
    def test_wrapper_preserves_game_failure_and_captures_only_current_log(self):
        (self.runtime/'dmhost').write_bytes(b'host');log=self.root/'engine.log';log.write_text('old session\n')
        def run(args,log=None,env=None,**kwargs):
            self.assertEqual(env['DM_METAL_HUD'],'1');Path(env['DM_NVN_TSV']).write_text('1\t@frame_ms\t20\n')
            with Path(log).open('a') as stream:stream.write('new session\n')
            raise Failure('original game failure')
        self.c.run=run
        with patch('build.launch',side_effect=lambda c:c.run([self.runtime/'dmhost'],log,{})):
            with self.assertRaisesRegex(Failure,'original game failure'):self.quiet(performance.launch,self.c)
        report=next((self.lib/'benchmarks').glob('**/summary.json'));self.assertEqual((report.parent/'engine.log').read_text(),'new session\n');self.assertEqual(json.loads((report.parent/'session.json').read_text())['gameOutcome'],'failed')
    def test_hud_only_does_not_create_reports(self):
        self.c.r['recordPerformance']=False;self.assertIsNone(self.begin());self.assertEqual(self.env['MTL_HUD_ENABLED'],'1')
    def test_invalid_marker_clock_label_and_pointer_are_rejected(self):
        self.begin()
        for values in [dict(markerAction='start',markerLabel='bad'),dict(markerAction='start',markerLabel='Loading',markerMonotonic=float('nan')),dict(markerAction='start',markerLabel='Loading',markerMonotonic=0)]:
            self.c.r.update(values)
            with self.assertRaises(Failure):self.quiet(performance.marker,self.c)
        atomic(self.lib/('.benchmark-'+self.game['id']+'.json'),dict(id='../../outside'))
        with self.assertRaises(Failure):self.quiet(performance.marker,self.c)
