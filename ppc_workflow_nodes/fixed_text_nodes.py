"""Explicit fixed functions for the remaining pure text/JSON runners.

Each function is the original business body, compiled as normal Python.
Nothing here reads a code string from the graph or calls exec/eval/compile.
"""
from __future__ import annotations

import json
import math
import re

from .serialize import pack_error, pack_success

_UNBOUND_LOCAL = re.compile(
    r"(?:cannot access local variable '([^']+)' where it is not associated with a value"
    r"|local variable '([^']+)' referenced before assignment)"
)


def _pack_unbound(exc: UnboundLocalError):
    """A function-local read before assignment is a NameError in the runner's flat namespace."""
    frame = exc.__traceback__
    while frame is not None and frame.tb_next is not None:
        frame = frame.tb_next
    code_name = "" if frame is None else frame.tb_frame.f_code.co_name
    matched = _UNBOUND_LOCAL.fullmatch(str(exc))
    if code_name.startswith("_fixed_") and matched:
        name = matched.group(1) or matched.group(2)
        return pack_error(NameError(f"name '{name}' is not defined"))
    return pack_error(exc)

RUNNER_RETURN = ("STRING", "STRING", "BOOLEAN")
RUNNER_NAMES = ("result_text", "result_json", "has_error")

def _fixed_500007(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);e=json.loads(input_json)
        s=p['prompt']
        notes='Declared uploaded references, with their original user roles: '+', '.join('<Picture '+str(i)+'>' for i in e['inventory']['images'])+'.'
        s=s.replace('detailed_description:',notes+'\ndetailed_description:',1)
        result=dict(prompt=s,**e['inventory'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500007:
    """Fixed function formerly embedded in node 500007."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500007."
    def run(self, input_text, input_json):
        return _fixed_500007(input_text, input_json)

def _fixed_400510(input_text, input_json=""):
    result = ""
    try:
        # Metadata only. A successful primary never reads or traverses fallback data.
        try:
            p=json.loads(input_text);result=p
            marker='参考音频准备失败：未找到两端都有自然停顿的3至15秒参考片段。请提供一句完整、说完后稍作停顿的单人录音，或调整所选参考区间；不会强行截断字音。'
            if p['primary'].get('start')==marker and p['primary'].get('duration')==marker:
                q=p['quality']['original'];data=p['fallback']
                total,head,tail=[float(q[k]) for k in ['duration_seconds','leading_silence_seconds','trailing_silence_seconds']]
                if not math.isfinite(total) or not 0<=head<total or not 0<=tail<total-head:raise ValueError('参考录音首尾检测无效。')
                regions=data['regions'];count=data.get('total_regions')
                if data.get('export_format')!='json' or not str(count).isdigit() or count!=len(regions) or count>1024:raise ValueError('参考停顿报告无效或过密，请提供较短清晰录音。')
                raw=[];last=quiet=0
                for r in regions:
                    a,b=[float(r[k]) for k in ['start_time','end_time']];meta=r.get('metadata',{})
                    if not 0<=last<=a<min(b,total) or b>total+.002 or b-a<.009999:raise ValueError('参考停顿范围无效。')
                    if r.get('label')!='silence' or meta.get('type')!='silence' or not abs(float(meta.get('threshold',-1))-.015)<=1e-12:raise ValueError('参考停顿来源无效。')
                    b=min(b,total);raw.append([a,b,quiet]);quiet+=b-a;last=b
                p['legacy']=[[a,b] for a,b,q in raw if b-a>=.199]
                groups=[]
                for i,(a,b,q) in enumerate(raw):
                    if groups and a-groups[-1][1]<=.021000001:
                        c=groups[-1];c[1]=b;c[2]+=b-a
                        if b-a>raw[c[3]][1]-raw[c[3]][0]:c[3]=i
                    else:groups.append([a,b,b-a,i])
                ids={i for a,b,q,i in groups if b-a>=.199999 and round(q/(b-a),9)>=.85 and raw[i][1]-raw[i][0]>=.079999}
                if raw and head>=.03 and raw[0][0]==0:ids.add(0)
                if raw and tail>=.03 and raw[-1][1]==total:ids.add(len(raw)-1)
                p['grouped']=[raw[i] for i in sorted(ids)]
                # Last fallback: continuous quiet only; no joins or waveform change.
                p['short_pauses']=[r for r in raw if r[1]-r[0]>=.119999]
        except Exception as e:
            message='参考音频准备失败：'+str(e)[:160]
            result={'ok':False,'reason':message,'quality':p.get('quality',{}),'row':p.get('row',{}),'primary':{'start':message,'duration':message}}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400510:
    """Fixed function formerly embedded in node 400510."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400510."
    def run(self, input_text):
        return _fixed_400510(input_text, "")

def _fixed_414017(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json)
        assert 0<p['count']==len(p['segments'])==len(state['paths'])==len(state['records']), 'S42_MERGE_COUNT'
        assert len(set(state['paths']))==p['count'], 'S42_MERGE_DUPLICATES'
        assert all(re.match(r'^output/selflift_auto_segment_[A-Za-z0-9_-]+\.mp4$',x) for x in state['paths']), 'S42_MERGE_PATH'
        frames=0;words=''
        for i,r in enumerate(state['records']):
         s=p['segments'][i]
         assert r['segment_index']==i and r['output_start']==frames, 'S42_MERGE_ORDER'
         proof=r.get('reference_scope',{})
         scoped=proof.get('reason') in ['explicit_empty_scene','explicit_authored_shot'] and proof.get('available_slots')==s['original_slots'] and proof.get('selected_slots')==r['original_slots'] and set(r['original_slots'])<=set(s['original_slots'])
         scoped=scoped or (proof.get('previous_slots')==s['original_slots'] and state['ds_guard_verdicts_v1'][i] is True)
         assert r['text']==s['text'] and r['source_blocks']==s['source_blocks'] and (r['original_slots']==s['original_slots'] or scoped), 'S42_MERGE_PROVENANCE'
         assert r['retained_count']==r['decoded_count']==r['keep_count']>0 and r['keep_start']==0, 'S42_MERGE_NATIVE_FRAMES'
         frames+=r['retained_count'];words+=r['text']
        assert (96 if p['mode']=='without_voice' else 1)<=frames<=p['max_seconds']*24 and words==''.join(s['text'] for s in p['segments']), 'S42_MERGE_LENGTH'
        result=dict(ok=True,output_frames=frames,duration_seconds=frames/24,records=state['records'],paths=state['paths'],text=words,native_audio=True)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed414017:
    """Fixed function formerly embedded in node 414017."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 414017."
    def run(self, input_text, input_json):
        return _fixed_414017(input_text, input_json)

def _fixed_414015(input_text, input_json=""):
    result = ""
    try:
        item=json.loads(input_text);state=json.loads(input_json)
        from .fragment_path import normalize_fragment_path
        path=normalize_fragment_path(item['path']);r=item['record']
        assert path not in state['paths'] and len(state['paths'])==len(state['records']), 'VIP_DUPLICATE_FRAGMENT'
        assert r['segment_index']==len(state['records']), 'VIP_FRAGMENT_ORDER'
        assert r['retained_count']==r['keep_count']==r['decoded_count']>0 and r['keep_start']==0, 'S42_FULL_NATIVE_FRAMES'
        r['output_start']=sum(v['retained_count'] for v in state['records'])
        state['paths'].append(path);state['records'].append(r)
        state['ambience_previous']=r['ambience_context_plan']['current']
        result=state
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed414015:
    """Fixed function formerly embedded in node 414015."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 414015."
    def run(self, input_text, input_json):
        return _fixed_414015(input_text, input_json)

def _fixed_414013(input_text, input_json=""):
    result = ""
    try:
        n,seconds,sr=json.loads(input_text);s=json.loads(input_json)
        n=int(n);seconds=float(seconds);sr=int(sr)
        assert s.get('native_audio') and 0<=int(s['segment_index']), 'S42_NATIVE_SOURCE'
        assert n>0 and int(s.get('delivered_frames',s['model_frames']))-8<=n<=int(s.get('delivered_frames',s['model_frames']))+1, 'S42_DECODED_FRAME_COUNT'
        assert math.isfinite(seconds) and seconds>0 and sr==32000, 'S42_NATIVE_AUDIO'
        assert abs(seconds-n/24)<=1/24+1e-8, 'S42_NATIVE_AV_DURATION'
        result=dict(segment_index=int(s['segment_index']),retained_count=n,keep_count=n,keep_start=0,decoded_count=n,model_frames=int(s['model_frames']),native_audio_seconds=seconds,sample_rate=sr,source_blocks=s['source_blocks'],original_slots=s['original_slots'],text=s['text'],planned_output_start=s['output_start'])
        if s.get('reference_scope'):result['reference_scope']=s['reference_scope']
        if s.get('audio_context'):result['audio_context']=s['audio_context']
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed414013:
    """Fixed function formerly embedded in node 414013."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 414013."
    def run(self, input_text, input_json):
        return _fixed_414013(input_text, input_json)

def _fixed_500116(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text)
        assert sorted(p)==['crop_none','env','segment'], 'invalid_crop_envelope'
        flag=str(p['crop_none'])
        assert flag in ['True','False'], 'invalid_crop_flag'
        s=p['segment'];env=p['env'];has_crop=flag=='False'
        slots=s['original_slots'];prompt=s['prompt']
        proof=s.get('reference_scope',{})
        scoped=proof.get('reason') in ['explicit_empty_scene','explicit_authored_shot'] and proof.get('selected_slots')==s['original_slots'] and sorted(proof.get('available_slots',[]))==sorted(env['inventory']['images']) and set(s['original_slots'])<=set(proof['available_slots'])
        scoped=scoped or s.get('ds_guard_verdict_v1') is True
        assert len(slots)==len(set(slots)) and (sorted(slots)==sorted(env['inventory']['images']) or scoped), 'original_reference_dropped'
        flags=[False]*9
        if has_crop:
         assert len(slots)<9 and s['crop_source'] in slots and len(s['identity_subjects'])==1, 'invalid_identity_crop'
         slot=len(slots)+1;flags[slot-1]=True
         instruction='Additional <Picture '+str(slot)+'> is a literal face-detail crop of the same <Subject '+s['identity_subjects'][0]+'>. Compare it with the original identity images only to preserve facial features. It is not a shot, keyframe, scene, costume or camera target. Never display the reference still or face card in the video.'
         prompt=prompt.replace('detailed_description:',instruction+'\ndetailed_description:',1)
        if env['caption_policy'] and not s.get('raw_passthrough'):
         policy=env['caption_policy']
         if 'NO subtitles' in policy and '<d>' in prompt:
          h3='Spoken dialogue is audio only. Do not add subtitles, captions, dialogue text, or graphic text overlays. Preserve existing text on physical objects in the references.'
          delivery='Clean live-action footage with audible speech only: the spoken words are heard, never written in the image. No added writing appears anywhere in the frame; retain lettering physically present on scene objects.'
          head,visual=prompt.split('detailed_description:',1)
          visual,tail=visual.split('overall_soundscape:',1)
          parts=re.split(r'(<d>.*?</d>)',visual,flags=re.S)
          visual=''.join(part if i%2 else part.replace(h3,'') for i,part in enumerate(parts))
          style=policy.split(' The video frames remain entirely clean,',1)[0]
          prompt=head+'detailed_description:\n'+h3+'\n'+delivery+'\n'+style+' No watermarks.\n'+visual+'overall_soundscape:\nAll dialogue blocks specify audible speech only, without on-screen transcription.\n'+tail
         else:
          prompt=prompt.replace('overall_soundscape:',policy+'\noverall_soundscape:',1)
        result=dict(prompt=prompt,crop_used=has_crop)
        for i,flag in enumerate(flags,1):result['crop_'+str(i)]=flag
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500116:
    """Fixed function formerly embedded in node 500116."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500116."
    def run(self, input_text):
        return _fixed_500116(input_text, "")

def _fixed_764000(input_text, input_json=""):
    result = ""
    try:
        p = json.loads(input_text)
        memo = {}

        def may_time(text):
            plain = ' '.join(text.lower().split())
            return any((w in plain for w in ['second', '秒', 'duration', '时长', '前说完', '前讲完'])) or any(('at ' + n in plain for n in '0123456789'))

        def adapt(text):
            if text in memo:
                return memo[text]
            if not may_time(text):
                return text
            pieces = re.split('(<d>.*?</d>)', text, flags=re.S)
            for i in range(0, len(pieces), 2):
                clauses = re.split('([;；\\n。]|\\.(?!\\d))', pieces[i])
                for j in range(0, len(clauses), 2):
                    clause = clauses[j]
                    if not may_time(clause):
                        continue
                    if not re.search('\\d', clause):
                        continue
                    lower = clause.lower()

                    def at_time(m):
                        context = clause[:m.start()].lower().split()[-5:]
                        return m[0] if any((w in context for w in ['aspect', 'ratio', 'format'])) else ''
                    if 'at' in lower:
                        clause = re.sub('\\bAt\\s+\\d+(?:[:：]\\d+)?(?:\\.\\d+)?(?:\\s*(?:seconds?\\b|s\\b|秒)|(?=\\s*[,;，；]))[,]?', at_time, clause, flags=re.I)
                    if ' by ' in lower or ' within ' in lower or '前说完' in clause or ('前讲完' in clause):
                        clause = re.sub('(finish|speak|say) (by|within) [\\d.]+ seconds?|[\\d:]+前[说讲]完', 'Natural measured dialogue timing', clause, flags=re.I)
                    if any((w in clause.lower() for w in ['silent', 'silence', 'pause', 'hold', '静默', '停顿', '无对白', '无台词'])):
                        clauses[j] = clause
                        continue
                    clauses[j] = clause
                pieces[i] = ''.join(clauses)
            memo[text] = ''.join(pieces)
            return memo[text]
        if p['mode']=='with_voice':
            p['source_metadata']=dict(header=p['header'],tail=p['tail'])
            for key in ['header','tail']:p[key]=adapt(p[key])
            for s in p['shots']:
                for key in ['tail','global_action']:s[key]=adapt(s[key])
                if s['visual_only']:s['body']=adapt(s['body'])
                for r in s['parts']:
                    r['source_action']=r['action']
                    r['action']=adapt(r['action'])
        result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed764000:
    """Fixed function formerly embedded in node 764000."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 764000."
    def run(self, input_text):
        return _fixed_764000(input_text, "")

def _fixed_400501(input_text, input_json=""):
    result = ""
    try:
        # Main timbre always uses the full source or an explicit user window.
        p=json.loads(input_text)
        try:
            if p.get('ok') is False:raise ValueError(p.get('reason','参考音频准备未通过。'))
            q=p['quality']['original'];row=p['row']
            total=float(q['duration_seconds']);silence=float(q['silence_ratio'])
            if not math.isfinite(total) or not 0<total<=120 or not math.isfinite(silence) or not 0<=silence<1:
                raise ValueError('主音色录音为空或没有可用声音。')
            low,high=row.get('reference_windows',{}).get(str(row.get('voice')),[0,total])
            low=float(low);high=float(high)
            if not math.isfinite(low) or not math.isfinite(high) or not 0<=low<high<=total:
                raise ValueError('主音色参考区间无效。')
        except Exception as exc:
            reason='MULTIREF_AUDIO_PREP|node=400501|主音色录音准备失败：'+str(exc)
            result={'ok':False,'reason':reason,'start':reason,'duration':reason}
        else:
            result={'ok':True,'start':low,'duration':high-low,'source':'primary_timbre'}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400501:
    """Fixed function formerly embedded in node 400501."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400501."
    def run(self, input_text):
        return _fixed_400501(input_text, "")

def _fixed_764001(input_text, input_json=""):
    result = ""
    try:
        p = json.loads(input_text)
        memo = {}

        def may_time(text):
            plain = ' '.join(text.lower().split())
            return any((w in plain for w in ['second', '秒', 'duration', '时长', '前说完', '前讲完'])) or any(('at ' + n in plain for n in '0123456789'))

        def adapt(text):
            if text in memo:
                return memo[text]
            if not may_time(text):
                return text
            pieces = re.split('(<d>.*?</d>)', text, flags=re.S)
            for i in range(0, len(pieces), 2):
                clauses = re.split('([;；\\n。]|\\.(?!\\d))', pieces[i])
                for j in range(0, len(clauses), 2):
                    clause = clauses[j]
                    if not may_time(clause):
                        continue
                    if not re.search('\\d', clause):
                        continue
                    lower = clause.lower()

                    def at_time(m):
                        context = clause[:m.start()].lower().split()[-5:]
                        return m[0] if any((w in context for w in ['aspect', 'ratio', 'format'])) else ''
                    if any((w in clause.lower() for w in ['silent', 'silence', 'pause', 'hold', '静默', '停顿', '无对白', '无台词'])):
                        clauses[j] = clause
                        continue
                    if 'from' in lower or 'between' in lower or '秒' in clause:
                        clause = re.sub('(From|Between) [\\d.]+ (to|and) [\\d.]+ seconds?\\b|[\\d.]+[-到至][\\d.]+秒', 'During the corresponding action', clause, flags=re.I)
                    if 'duration' in lower or '时长' in clause:
                        clause = re.sub('(duration(_seconds)?|时长)\\s*[:：=]\\s*[\\d.]+\\s*(seconds?|s|秒)?', 'Natural measured dialogue timing', clause, flags=re.I)
                    clauses[j] = clause
                pieces[i] = ''.join(clauses)
            memo[text] = ''.join(pieces)
            return memo[text]
        if p['mode']=='with_voice':
            for key in ['header','tail']:p[key]=adapt(p[key])
            for s in p['shots']:
                for key in ['tail','global_action']:s[key]=adapt(s[key])
                if s['visual_only']:s['body']=adapt(s['body'])
                for r in s['parts']:
                    r['action']=adapt(r['action'])
        result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed764001:
    """Fixed function formerly embedded in node 764001."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 764001."
    def run(self, input_text):
        return _fixed_764001(input_text, "")

def _fixed_765200(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        prompt=s.get('prompt','');source=env.get('source','')
        raw=source.partition('overall_soundscape:')[2].partition('non_diegetic_music:')[0].strip()
        body=source.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
        ids=re.findall(r'(?im)^\s*\[\s*(?:Shot|镜头)\s+(\d+)\s*\]',body)
        index=s.get('shot',-1)
        meta=dict(applied=False,outer_clock_removed=False,reason='unstructured_or_no_explicit_shot_audio')
        if not s.get('raw_passthrough') and index>=0 and index<len(ids):
            target=ids[index]
            chunks=re.split(r'[;；\n]+',raw)
            kept=[];removed=[];saw=False
            for chunk in chunks:
                refs=re.findall(r'(?i)\[\s*(?:Shot|镜头)\s+(\d+)\s*\]',chunk)
                if refs:
                    saw=True
                    if target not in refs:
                        removed.append(chunk.strip());continue
                    chunk=re.sub(r'(?i)\[\s*(?:Shot|镜头)\s+\d+\s*\]','this shot',chunk)
                if chunk.strip():kept.append(chunk.strip())
            if saw and removed and raw and raw in prompt:
                replacement='; '.join(kept) if kept else 'N/A.'
                prompt=prompt.replace(raw,replacement,1)
                meta.update(applied=True,reason='explicit_authored_soundscape_shot_scope',authored_shot=target,removed_clause_count=len(removed),retained=replacement)
            if env.get('inventory',{}).get('audios') and not s.get('visual_only'):
                parts=re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
                opening=re.search(r'(?im)^\s*\[\s*Shot\s+1\s*\]\s*(From\s+\d{1,2}:\d{2}(?:\.\d+)?\s+to\s+\d{1,2}:\d{2}(?:\.\d+)?\s*,\s*)',prompt)
                if opening:
                    clock=opening.group(1)
                    for i in range(0,len(parts),2):parts[i]=parts[i].replace(clock,'')
                    prompt=''.join(parts);meta['outer_clock_removed']=True
                    meta['removed_outer_clock']=clock
        s['prompt']=prompt;s['shot_audio_scope']=meta
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed765200:
    """Fixed function formerly embedded in node 765200."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 765200."
    def run(self, input_text, input_json):
        return _fixed_765200(input_text, input_json)

def _fixed_1801(input_text, input_json=""):
    result = ""
    try:
        mode = (input_json or '').strip()
        if mode not in ['无字幕', '仅按提示词指定']:
            raise ValueError('caption_mode_invalid')
        source = input_text or ''
        if not source.strip() or len(source) > 24000:
            raise ValueError('prompt_empty_or_over_24000_characters')

        families = [
            ['Picture', 9, ['@参考图片', '@参考图', '@图片', '@图', '@image_', '@image']],
            ['Audio', 3, ['@参考音频', '@参考音色', '@音频', '@音色']],
            ['Video', 3, ['@参考视频', '@视频']]
        ]

        def starts_reference(value, token):
            return value.startswith(token) and (len(value) == len(token) or not value[len(token)].isdigit())

        def ref_value(text):
            value = text.strip()
            for family, count, forms in families:
                for slot in range(count, 0, -1):
                    native = '<%s %s>' % (family, slot)
                    if value.startswith(native):
                        return native
                    for form in forms:
                        if starts_reference(value, form + str(slot)):
                            return native
            return ''

        def add_alias(aliases, name, value):
            old = aliases.get(name, '')
            if old and old != value:
                raise ValueError('reference_alias_conflict')
            aliases[name] = value

        def label_from(rest):
            stop = len(rest)
            for marker in ['主参考', '参考', '，', ',', '。', '；', ';', ' ', '\t']:
                pos = rest.find(marker)
                if pos >= 0 and pos < stop:
                    stop = pos
            return rest[:stop].strip()

        aliases = {}
        declared = []
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line.startswith('@'):
                continue
            cut = -1
            width = 0
            for marker in ['=', '：', ':', '对应']:
                pos = line.find(marker)
                if pos > 1 and (cut < 0 or pos < cut):
                    cut = pos
                    width = len(marker)
            if cut > 1:
                name = line[1:cut].strip()
                value = ref_value(line[cut + width:])
                if name and value:
                    add_alias(aliases, name, value)
                    declared.append(line)
            for family, count, forms in families:
                for slot in range(count, 0, -1):
                    native = '<%s %s>' % (family, slot)
                    for form in forms:
                        token = form + str(slot)
                        if starts_reference(line, token):
                            rest = line[len(token):].lstrip('：: \t')
                            label = label_from(rest)
                            if family == 'Audio' and label and not label.endswith('音色'):
                                label += '音色'
                            if family == 'Video' and label and not label.endswith('动作'):
                                label += '动作'
                            if label and len(label) <= 80:
                                add_alias(aliases, label, native)

        names = sorted(aliases, key=len, reverse=True)

        def map_normal(text):
            kept = []
            for raw_line in text.splitlines(True):
                if raw_line.strip() not in declared:
                    kept.append(raw_line)
            value = ''.join(kept)
            for name in names:
                value = value.replace('@' + name, aliases[name])
            for family, count, forms in families:
                for slot in range(count, 0, -1):
                    native = '<%s %s>' % (family, slot)
                    value = value.replace(native, native)
                    for form in forms:
                        value = re.sub(re.escape(form + str(slot)) + r'(?!\d)', native, value)
            return value

        parts = source.split('<d>')
        result = map_normal(parts[0])
        for part in parts[1:]:
            if part.count('</d>') != 1:
                raise ValueError('dialogue_tag_boundaries')
            spoken, tail = part.split('</d>', 1)
            result += '<d>' + spoken + '</d>' + map_normal(tail)
        result = result.strip()

        policy = 'detailed_description: The target video is in a realistic smartphone photography style, with natural skin texture and soft available light. The video frames remain entirely clean, with NO subtitles, captions, dialogue transcription, translated text, title cards, lower thirds, speech bubbles, overlay text, or watermarks at any time.'
        if mode == '仅按提示词指定':
            policy = ('Render visible text only when the user explicitly requests it. Never turn dialogue into captions. '
                      'Physical text already in supplied reference scenes may remain.')
        if result.startswith('{'):
            try:
                data = json.loads(result)
            except Exception:
                raise ValueError('bad_json')
            exclusions = data.get('exclusions', [])
            if json.dumps(exclusions)[:1] != '[':
                exclusions = [exclusions]
            kept = []
            for item in exclusions:
                if item not in ['subtitles', 'text overlays', 'captions', 'caption', policy]:
                    kept.append(item)
            data['exclusions'] = kept + [policy]
            result = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        else:
            result += '\n' + policy
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed1801:
    """Fixed function formerly embedded in node 1801."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 1801."
    def run(self, input_text, input_json):
        return _fixed_1801(input_text, input_json)

def _fixed_400443(input_text, input_json=""):
    result = ""
    try:
        # Unwrap declared structures only; never author or shorten speech.
        def adapt(raw):
            if not raw.strip() or len(raw)>24000:raise ValueError('请输入1至24000字符；不会截断口播。')
            text=raw.strip()
            if text.startswith('```') and text.endswith('```'):
                text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
            keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            if not text.startswith('{'):return {'raw':raw,'source':text if raw.strip().startswith('```') else raw}
            p=json.loads(text)
            if all(k in p for k in keys):
                if not all(p[k]==str(p[k]) for k in keys):raise ValueError('六段式JSON每段须为文本；不会猜测对白。')
                return {'raw':raw,'source':'\n\n'.join(k+':\n'+p[k] for k in keys)}
            if p.get('schema')!='h3-director-json-v1' or not p.get('storyboard'):
                raise ValueError('JSON请使用六段式文本字段或含明确dialogue的h3-director-json-v1。')
            def metadata(value):
                text=json.dumps(value,ensure_ascii=False)
                if re.search(r'<\s*/?\s*d\s*>',text):raise ValueError('JSON非dialogue说明含口播保留标签，请明确实际对白边界。')
                return text
            header=[];subjects=[]
            for ref in p.get('references',[]):
                name=ref['label'];m=re.fullmatch(r'<Subject ([1-3])>',name)
                if not m:raise ValueError('JSON reference label须明确Subject 1至3。')
                subjects.append(m.group(1))
                header.append(name+': '+metadata({k:v for k,v in ref.items() if k!='label'}))
            out=[];end=0
            for i,shot in enumerate(p['storyboard'],1):
                start=float(shot['start_seconds']);finish=float(shot['end_seconds'])
                if start!=end or finish<=start:raise ValueError('JSON分镜时间段须从0连续，不重叠。')
                if shot.get('shot',i)!=i:raise ValueError('JSON分镜编号不连续。')
                end=finish
                out.append('[Shot '+str(i)+']\nAt '+str(int(start//60))+':'+('%06.3f'%(start%60)))
                out.append(metadata({k:v for k,v in shot.items() if k not in ['dialogue','shot','start_seconds','end_seconds']}))
                for line in shot.get('dialogue',[]):
                    m=re.fullmatch(r'\(?S([1-3])\)?',line.get('speaker',''))
                    if not m or m.group(1) not in subjects:raise ValueError('JSON dialogue speaker须对应已声明的Subject。')
                    words=line.get('line')
                    if words!=str(words) or not words.strip():raise ValueError('JSON dialogue line须为完整台词。')
                    spoken=re.sub(r'^<d>(?:\[(?:Chinese|中文)\])?(.*?)</d>$',r'\1',words,flags=re.S)
                    if re.fullmatch(r'[.。…—，；！？、：!?\s]+',spoken):continue
                    if not words.startswith('<d>'):words='<d>[Chinese]'+words+'</d>'
                    sid=m.group(1)
                    delivery=line.get('delivery','natural')
                    metadata(delivery)
                    out.append('<Subject '+sid+'> (S'+sid+') says '+delivery+': '+words+'\n\n')
            total=p.get('format',{}).get('duration_seconds',end)
            if float(total)!=end or not 4<=end<=120:raise ValueError('JSON总长与切点须一致且为4至120秒。')
            other={k:v for k,v in p.items() if k not in ['references','storyboard','audio']}
            source='subject_definitions:\n'+'\n'.join(header)+'\n\nsummary:\nDuration: '+str(end)+'.\n'+metadata(other)+'\n\nretention_analysis:\nPreserve declared references.\n\ndetailed_description:\n'+'\n'.join(out)+'\noverall_soundscape:\n'+metadata(p.get('audio',{}))+'\n\nnon_diegetic_music:\n'
            return {'raw':raw,'source':source}
        result=adapt(input_text)
        if 'detailed_description:' not in result['source']:
            source=result['source'].replace('\r\n','\n');prefix='\ue000'
            for attempt in range(len(source)+1):
                if prefix not in source:break
                prefix+='\ue000'
            result['audios']=[i-8 for i,v in enumerate(input_json.split(',')) if 9<=i<18 and v.strip().lower() not in ['true','1']]
            quoted={};qp=re.escape(prefix)+r'\d+\ue001'
            def restore(m):return quoted[m.group(0)]
            def mask(m):
                key=prefix+str(len(quoted))+'\ue001'
                quoted[key]=re.sub(qp,restore,m.group(0))
                return key
            pattern=r'“[^“”]*”|「[^「」]*」|『[^『』]*』|"[^"\n]*(?:\n[^"\n]*)*"'
            for depth in range(len(source)+1):
                if not re.search(r'[“”「」『』"]',source):break
                masked=re.sub(pattern,mask,source)
                if source==masked:raise ValueError('口播引号没有闭合，请明确完整台词。')
                source=masked
            result['definitions']={}
            for m in (re.finditer(r'^(?:人物|角色)[:：][ \t]*([^，,；;：: \n]+)([^\n]*(?:\n[ \t]*(?:形象|参考图|主音色|主声音|音色|声音|声线|自然|开心|高兴|喜悦|兴奋|激昂|不开心|难过|悲伤|伤心|低落|低沉|平静|冷静|惊讶|生气|愤怒)[:：][^\n]*)*)$',source,re.M) if '人物' in source or '角色' in source else []):result['definitions'][m.group(1)]=m.group(2)
            result.update(source=source,quotes=quoted,quote_prefix=prefix)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400443:
    """Fixed function formerly embedded in node 400443."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400443."
    def run(self, input_text, input_json):
        return _fixed_400443(input_text, input_json)

def _fixed_400442(input_text, input_json=""):
    result = ""
    try:
        if not input_text.startswith('{'):
            result=input_text
        else:
            def assemble(p):
                if "prompt" in p:return p
                rows=p["rows"];out=p["out"];definitions=p["definitions"]
                audios=p['audios']
                if not audios:raise ValueError('请至少上传一段主音色录音，用于克隆人物声音。')
                def refs(s):
                    def ref(m):
                        kind='Picture' if m.group(1).lower() in '图片|图|参考图|参考图片|image'.split('|') else 'Audio'
                        return f'<{kind} {m.group(2)}>'
                    return re.sub(r'@(?:参考)?(图片|图|参考图|参考图片|image|音频|音色|audio)_?\s*(\d+)',ref,s,flags=re.I)
                names=list(definitions)
                pronouns='|他|她|它|人物|主角|这个人|这位人物'.split('|')
                for row in rows:
                    actor=row['actor']
                    picture=re.search(r'@?(?:图片|图|image)\s*(\d+)|<Picture (\d+)>',actor,re.I) if actor not in definitions else None
                    row['actor']=f"image:{int(picture.group(1) or picture.group(2))}" if picture else actor
                    name=row['actor']
                    if name not in pronouns and not name.startswith('image:') and name not in names:names.append(name)
                if not names:names=['presenter']
                image_actors={r['actor'] for r in rows if r['actor'].startswith('image:')}
                if not definitions and len(image_actors)>1:
                    metadata='\n'.join(out).split('[Shot ',1)[0]
                    same=any(x in metadata for x in '同一人|同一个人|同一女性|同一男性|同一位|都是本人'.split('|'))
                    different=any(x in metadata for x in '两个人|不同的人|不同人物|三个人|不是同|并非同|非同一'.split('|'))
                    if not same or different:raise ValueError('多张图片分别说话，人物对应尚不明确；请说明是同一人还是不同人物。')
                if len(names)>3:raise ValueError('当前最多支持3位说话人物。')
                single=len(names)==1
                speakers={};rendered=[]
                for row in rows:
                    name=row['actor']
                    if name.startswith('image:'):
                        n=name.split(':')[1]
                        choices=[a for a in names if n in definitions.get(a,{}).get('images',[])]
                        if len(choices)==1:name=choices[0]
                        elif single:name=names[0]
                        else:raise ValueError('这张图片对应哪个说话人物尚不明确，不能按图片编号猜人物。')
                    elif name in pronouns:
                        if len(names)!=1:raise ValueError('多人场景中“他/她”指向不明，请注明这句是谁说的。')
                        name=names[0]
                    sid=names.index(name)+1
                    if name not in speakers:speakers[name]=len(speakers)+1
                    info=dict(definitions.get(name,{}))
                    declared=info.get('voice');local=row['audio_roles'].get('voice')
                    if declared is not None and local is not None and declared!=local:raise ValueError('VIP_ROLE_VOICE_CONFLICT：同一角色不能覆盖已绑定的主音色，请检查角色与音频1至3的对应。')
                    info.update(row['audio_roles'])
                    voice=info.get('voice',p.get('global_voice') if single else None);emotion=info.get('emotion',p.get('global_emotion') if single else None)
                    if voice is None and single and emotion!=1 and 1 in audios:voice=1
                    if voice is None and emotion:raise ValueError('只指定了情绪参考，尚未明确克隆音色。')
                    if voice is None and len(audios)==1 and 1<=audios[0]<=3 and sid==1:voice=audios[0]
                    if voice is None and not any(1<=a<=3 for a in audios):raise ValueError('VIP_MAIN_SLOT_REQUIRED：请在音频1至3上传角色主音色长录音；情绪槽不能代替主音色。')
                    if voice is None:raise ValueError('本句人物未指定主音色，请说明使用哪段已上传的录音。')
                    for audio in [voice,emotion]:
                        if audio is not None and audio not in audios:raise ValueError('音频'+str(audio)+('超出1至9范围。' if not 1<=audio<=9 else '未上传，请补充对应录音。'))
                    prefix=f'<Subject {sid}> (S{speakers[name]}) says'+(' in an off-screen voiceover' if row['voiceover'] else ' naturally')+f', voice from <Audio {voice}>;'
                    if emotion is not None:prefix+=f' emotion from <Audio {emotion}>;'
                    if row.get('named_emotion_state'):prefix+=' emotion: '+row['named_emotion_state']+';'
                    rendered.append(f"{prefix} <d>[Chinese]{row['text']}</d>\n\n")
                body='\n'.join(out)
                if re.search(r'<\s*/?\s*d\s*>',body):raise ValueError('非台词说明含d保留标签，请明确实际口播边界。')
                body=refs(body)
                def speech(m):return rendered[int(m.group(1))]
                body=re.sub(r'<<VIP_LINE_(\d+)>>',speech,body)
                if not p['shots']:body='[Shot 1]\n'+body
                headers=[]
                for i,name in enumerate(names,1):
                    imgs=definitions.get(name,{}).get('images',[])
                    desc='; identity references '+', '.join(f'<Picture {x}>' for x in imgs) if imgs else '; preserve the user-specified identity and its reference images'
                    headers.append(f'<Subject {i}>: {name}{desc}.')
                header='\n'.join(headers);total=p.get('total','auto')
                prompt=f'subject_definitions:\n{header}\n\nsummary:\nDuration: {total}.\n\nretention_analysis:\nPreserve the user-specified people, scenes and material associations.\n\ndetailed_description:\n{body}\noverall_soundscape:\n\nnon_diegetic_music:\n'
                result={'raw':p['raw'],'natural':True,'prompt':prompt}
                if p.get('named_roles_active'):result['named_roles_active']=True
                return result
            result=assemble(json.loads(input_text))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400442:
    """Fixed function formerly embedded in node 400442."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400442."
    def run(self, input_text):
        return _fixed_400442(input_text, "")

def _fixed_400441(input_text, input_json=""):
    result = ""
    try:
        # Extract authored dialogue; opaque quoted text cannot become a metadata field.
        def extract(p):
            raw=p['source']
            if 'detailed_description:' in raw:return {'raw':p['raw'],'prompt':raw}
            qp=re.escape(p['quote_prefix'])+r'\d+\ue001'
            def restore(m):return p['quotes'][m.group(0)]
            def full(s):return re.sub(qp,restore,s) if p['quote_prefix'] in s else s
            definitions=p['definitions']
            rows=[];out=[];active=None;pending=None;context='';shots=0
            fields='口播文案|口播内容|配音文案|旁白内容|对白内容|解说词|文案|口播|台词|对白|旁白|请原样朗读以下内容'.split('|')
            boundaries='画面|画面描述|动作|镜头描述|音效|背景音乐|背景声音|情绪|语气|语速|素材说明|人物|角色|要求|声音|运镜|环境音|BGM|字幕|字幕要求|Negative|整体要求|备注|参考音频|镜头语言|旁白说明|subject_definitions|summary|retention_analysis|detailed_description|overall_soundscape|non_diegetic_music'.split('|')
            stop=tuple('不要|禁止|不能|别|请勿|错误示例|反例|例子|例如|假如|如果|字幕|标题|招牌|标牌|旁边标牌'.split('|'))
            for line in raw.splitlines():
                if active is None and pending is None and (line.isalpha() or not re.search(r'[:：\ue000\d]',line)):out.append(full(line));context+='\n'+line;continue
                label=line.strip()
                shot=re.fullmatch(r'(?:镜头|分镜|场景)\s*(\d+)\s*(?:[:：](.*))?',label) if label.startswith(('镜头','分镜','场景')) else None
                if shot:
                    active=None;pending=None;context='';shots+=1
                    if int(shot.group(1))!=shots:raise ValueError('分镜编号不连续，请确认镜头顺序。')
                    out.append(f'[Shot {shots}]')
                    if shot.group(2):out.append(full(shot.group(2)))
                    continue
                parts=re.split('[:：]',label,1)
                if len(parts)==1:
                    pair=re.match(r'(.+?)('+qp+r'.*)',label)
                    if pair:parts=pair.groups()
                key=parts[0];meta='';actor='';recognized=False
                if label.startswith(stop):active=None;pending=None;out.append(full(line));context+='\n'+line;continue
                pair=re.fullmatch(r'(.*?)[（(](.*)[）)]',key) if key.endswith(('）',')')) else None
                if pair:key=pair.group(1).strip();meta=pair.group(2)
                key=key.removesuffix('如下').removesuffix('是').strip()
                verb=re.fullmatch(r'(.*?)(?:说道|讲道|念道|说出这句话|说的内容|说|讲|念|says|say)',key,re.I) if len(parts)==2 and key not in fields and key not in boundaries and key not in definitions else None
                if len(parts)==2:
                    if key in fields:recognized=True
                    elif key in definitions:actor=key;recognized=True
                    elif verb:actor=re.sub(r'^(?:请让|让|Please\s*)','',verb.group(1),flags=re.I).strip();recognized=True
                if recognized:
                    text=parts[1].lstrip();active=None
                    if not text:pending=(actor,meta,key);continue
                    pending=None
                elif key in boundaries:
                    active=None;pending=None;out.append(full(line));context+='\n'+line if key not in ['人物','角色'] else '';continue
                elif pending:actor,meta,key=pending;text=line;pending=None
                elif active is not None:
                    if len(parts)>1:raise ValueError('未识别的字段紧随未加引号台词，请明确台词结束位置。')
                    rows[active]['text']+='\n'+full(line);continue
                else:out.append(full(line));context+='\n'+line;continue
                # All consecutive quoted utterances are retained; only explicit continuation links count.
                segments=[];quoted=False
                for part in text:
                    if not text.startswith(p['quote_prefix']):break
                    q=re.match(qp,text);segments.append(p['quotes'][q.group(0)][1:-1]);text=text[q.end():].lstrip();quoted=True
                    text=re.sub(r'^[，,；;]?\s*(?:(?:然后)?(?:接着)?(?:说道|讲道|念道|说|讲|念)\s*[:：]?\s*)?(?='+qp+')','',text)
                if quoted and re.search(qp,text) and re.search(r'说|讲|念|口播|台词|say|speak',text):raise ValueError('后续台词的连接方式不明确，请为下一句单独标注口播文案。')
                suffix=full(text) if quoted else ''
                if not quoted:segments=[full(text)]
                for words in segments:
                    tagged=re.fullmatch(r'<\s*d\s*>(?:\[(?:Chinese|中文)\])?(.*?)<\s*/\s*d\s*>',words,re.S) if words.startswith('<') else None
                    if tagged:words=tagged.group(1);quoted=True
                    if ('<' in words or '＞' in words or '&lt;' in words) and re.search(r'<\s*/?\s*d\s*>|＜/?d＞|&lt;/?d&gt;',words):raise ValueError('口播标签没有闭合、嵌套或编码不明确；请使用ASCII d标签。')
                    if not words.strip():raise ValueError('口播正文为空。')
                    if not words.strip('.。…—-，,；;！!？?、：: \t\r\n'):out.append('Silent pause; no speech.');continue
                    rows.append({'actor':actor,'text':words,'audio_context':context+'\n'+meta,'voiceover':key.startswith('旁白'),'literal_quoted':quoted})
                    out.append(f'<<VIP_LINE_{len(rows)-1}>>')
                    active=None if quoted else len(rows)-1
                if suffix:out.append(suffix)
                context=''
            if not rows and p.get('audios'):raise ValueError('VIP_MISSING_DIALOGUE：请给出明确口播正文，例如“口播文案：原话”或“图片1讲：原话”；画面说明和参考录音不会自动变成台词。')
            for row in rows:row['text']=row['text'].rstrip('\r\n')
            p.update(rows=rows,out=out,inventory=input_json,shots=shots)
            return p
        result=extract(json.loads(input_text)) if input_text.startswith('{') else input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400441:
    """Fixed function formerly embedded in node 400441."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400441."
    def run(self, input_text, input_json):
        return _fixed_400441(input_text, input_json)

def _fixed_500049(input_text, input_json=""):
    result = ""
    try:
        plan=json.loads(input_text)
        result=input_text
        if plan['mode']=='with_voice' and plan['count']>1:
            p=json.loads(input_json)
            for s in plan['segments']:
                prompt=s['prompt'];head,sep,body=prompt.partition('detailed_description:\n')
                assert sep, 'missing_visual_section'
                defs,sep,rest=head.partition('summary:\n')
                summary,sep,retention=rest.partition('retention_analysis:\n')
                assert sep, 'missing_retention_section'
                source=p['shots'][s['shot']]['body']
                identity=[];kept=[]
                for line in defs.splitlines():
                    m=re.match(r'\s*<Picture (\d+)>:',line)
                    matches=[b for b in s['bindings'] if m and b['local_picture']==int(m[1])]
                    binding=matches[0] if matches else None
                    purely_identity=binding and binding['roles']==['speaker_identity'] and len(binding['subject_ids'])==1
                    original=binding['original_slot'] if binding else 0
                    anchor=False
                    if purely_identity:
                        token='<Picture '+str(original)+'>'
                        for clause in re.split(r'\n|(?<=[.!?])\s+',p['header']+source):
                            if token in clause and re.search(r'first frame|last frame|keyframe|composition anchor|starts? from|ends? on',clause,re.I):anchor=True
                    if purely_identity and not anchor:
                        sid=binding['subject_ids'][0]
                        identity.append((m[1],sid))
                        kept.append('Identity source for <Subject '+sid+'>: '+line[m.end():].strip()+' Use only the identity attributes explicitly assigned to <Picture '+m[1]+'>, not the source photograph as a displayed frame.')
                    else:kept.append(line)
                for picture,sid in identity:
                    retention=retention.replace('<Picture '+picture+'>: fully_preserved', '<Subject '+sid+'> (identity and clothing from <Picture '+picture+'>): fully_preserved')
                shot_pattern=r'\bShot\s+\d+(?:\s*(?:,|and|&)\s*(?:Shot\s+)?\d+)*'
                retention=re.sub(shot_pattern,'this shot',retention)
                summary=re.sub(r'\n\s*<Subject \d+>\s*\(S\d+\):\s*$', '\n',summary)
                summary_lines=summary.splitlines(True)
                for line_index in range(len(summary_lines)-1,-1,-1):
                    line=summary_lines[line_index]
                    if re.fullmatch(r'[ \t]*<Subject (\d+)>[ \t]*\(S\1\):[ \t]*\r?\n?',line):
                        trailer=' '.join(''.join(summary_lines[line_index+1:]).split())
                        if trailer in ['[reference generation] + [audio reference]','[audio reference] + [reference generation]','[reference generation]','[audio reference]']:
                            summary_lines[line_index]=''
                summary=''.join(summary_lines)
                out='\n'.join(kept)+'\nsummary:\n'+summary+'retention_analysis:\n'+retention+'detailed_description:\n'+body
                assert re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S), 'reference_scope_dialogue_changed'
                s['prompt']=out
            result=plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500049:
    """Fixed function formerly embedded in node 500049."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500049."
    def run(self, input_text, input_json):
        return _fixed_500049(input_text, input_json)

def _fixed_500050(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text)
        assert p['schema']=='rh-native-source-v1', 'invalid_source_schema'
        memo=p.pop('regex_memo_v1',{})
        def staged(site,text,live):
            table=memo.get(site,{})
            if text in table:return table[text]
            return live(text)
        def clock(token):
            parts=token.replace('：',':').split(':')
            assert len(parts)<=2, 'invalid_authored_clock'
            seconds=float(parts[-1])
            if len(parts)==2:
                assert seconds<60, 'invalid_authored_clock'
                seconds+=60*float(parts[0])
            return seconds
        number=r'\d+(?:[:：]\d+)?(?:\.\d+)?'
        span=r'^(?:(?:From|Between)\s+)?('+number+r')\s*(?:seconds?\b|s\b|秒)?\s*(?:to|and|[-–—到至])\s*('+number+r')\s*(?:seconds?\b|s\b|秒)?'
        def temporal(m,text):
            return m and (m[0].rstrip().endswith(('second','seconds','s','秒')) or text[m[3]:].lstrip()[:1] in ',;:.，；!?')
        def parser_view(raw):
            body=re.sub(r'<d>.*?</d>','',raw,flags=re.S)
            body=re.sub(r'^\s*\[Shot\s+\d+\]\s*','',body,flags=re.I)
            # Normalize only the parser view, never submitted source or spoken text.
            beat=re.match(r'^(?:At\s+\d+(?::\d+)?(?:\.\d+)?\s*,\s*)?Beat\s+\d+\s*[—–:-]\s*(\d+(?::\d+)?(?:\.\d+)?)\s*[–—-]\s*(\d+(?::\d+)?(?:\.\d+)?)\s*:',body,re.I)
            if beat:
                leading=re.match(r'^At\s+(\d+(?::\d+)?(?:\.\d+)?)',body,re.I)
                if leading:assert clock(leading[1])==clock(beat[1]), 'conflicting_beat_start'
                body=beat[1]+' to '+beat[2]+', '+body[beat.end():]
            return body
        def span_view(body):
            m=re.match(span,body,re.I)
            return [m[0],m[1],m[2],m.end()] if m else None
        for shot in p['shots']:
            body=staged('view',shot['body'],parser_view)
            found=staged('span',body,span_view)
            start=None;end=None
            if temporal(found,body):
                start=clock(found[1]);end=clock(found[2])
                assert 0<=start<end<=120, 'invalid_authored_clock'
            else:
                found=re.match(r'^At\s+('+number+r')\s*(?:seconds?\b|s\b|秒)?',body,re.I)
                found=[found[0],found[1],None,found.end()] if found else None
                if temporal(found,body):start=clock(found[1])
            if start is not None:assert 0<=start<=120, 'invalid_authored_clock'
            shot['authored_start']=start;shot['authored_end']=end
        # These clips are generated separately, one authored shot per call. An edge
        # <scenetrans> belongs to the cross-shot protocol, never to spoken timing text.
        # Keep the submitted source verbatim for audit; project only edge markers out.
        def project(row):
            text=row['text']
            clean=re.sub(r'^(?:\s*<scenetrans>)+|(?:<scenetrans>\s*)$','',text)
            if clean==text:return
            assert clean.strip(), 'empty_spoken_dialogue'
            row['original_raw_dialogue']=row.get('original_raw_dialogue',row['raw_dialogue'])
            row['original_text']=row.get('original_text',text)
            row['text']=clean
            row['raw_dialogue']='<d>['+row['language']+']'+clean+'</d>'
            row['separate_clip_transition']=True
        for row in p['rows']:project(row)
        for shot in p['shots']:
            for row in shot['parts']:
                old=row['raw_dialogue'];project(row)
                shot['body']=shot['body'].replace(old,row['raw_dialogue'])
            shot['text']=''.join(row['text'] for row in shot['parts'])

        result=p
        def duration_view(summary):
            return re.sub(r'\b((?:total\s+)?duration)\s+of\s+(\d+(?::\d+)?(?:\.\d+)?)\s*(seconds?\b|s\b)?',r'\1 is \2 \3',summary,flags=re.I)

        # Canonicalize numeric global duration wording only in the parsed summary view.
        # The raw source and all <d> blocks remain verbatim.
        if p.get('mode')=='without_voice' and 'summary:' in p['header']:
            head,sep,rest=p['header'].partition('summary:')
            summary,sep2,retention=rest.partition('retention_analysis:')
            summary=staged('duration',summary,duration_view)
            p['header']=head+sep+summary+sep2+retention
        result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500050:
    """Fixed function formerly embedded in node 500050."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500050."
    def run(self, input_text):
        return _fixed_500050(input_text, "")

def _fixed_762018(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_text);p=json.loads(input_json)
        p['current']['seconds']=r['native_audio_seconds']
        r['ambience_context_plan']=p
        result=r
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed762018:
    """Fixed function formerly embedded in node 762018."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 762018."
    def run(self, input_text, input_json):
        return _fixed_762018(input_text, input_json)

def _fixed_1701(input_text, input_json=""):
    result = ""
    try:
        raw = input_text.strip().upper().replace(' ', '')
        values = {'': '0.59', '480': '0.59', '480P': '0.59', '720': '0.9', '720P': '0.9', '1080': '2.0', '1080P': '2.0'}
        if raw not in values:
            raise ValueError('清晰度请填写480P、720P或1080P')
        result = values[raw]
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed1701:
    """Fixed function formerly embedded in node 1701."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 1701."
    def run(self, input_text):
        return _fixed_1701(input_text, "")

def _fixed_500044(input_text, input_json=""):
    result = ""
    try:
        plan=json.loads(input_text);p=json.loads(input_json)
        assert plan['schema']=='rh-native-plan-v1' and p['schema']=='rh-native-source-v1', 'invalid_schema'
        picture_rows=[]
        for line in p['header'].splitlines():
            if re.match(r'\s*<Picture\s+\d+>',line):picture_rows.append((line,[int(n) for n in re.findall(r'<Picture\s+(\d+)>',line)]))
        reference_tokens=re.compile(r'<(Picture|Audio|Video)\s+(\d+)>')
        shot_tokens=re.compile(r'\[Shot\s+\d+\]')
        dialogue_tokens=re.compile(r'<d>.*?</d>',re.S)
        all_words=[]
        if plan['mode']=='with_voice':assert p.get('temporal_view'), 'missing_temporal_policy'
        for s in plan['segments']:
            assert s['segment_index']==len(all_words) and s['native_audio'] and s['model_frames']%17==5 and s['keep_start']==0, 'invalid_native_plan'
            shot=p['shots'][s['shot']];mapping=dict(zip(s['original_slots'],range(1,10)))
            maps={'Picture':mapping,'Audio':dict(zip(p['inventory']['audios'],[1,2,3])),'Video':dict(zip(p['inventory']['videos'],[1,2,3]))}
            def refs(text):
                def token(m):
                    n=int(m[2])
                    assert n in maps[m[1]], 'missing_reference'
                    return '<'+m[1]+' '+str(maps[m[1]][n])+'>'
                return reference_tokens.sub(token,text)
            definitions=[]
            for sid in s['declared_subjects']:
                definitions.extend(refs(line) for line in p['subject_defs'].get(sid,[]))
            for line,used in picture_rows:
                if used and all(n in mapping for n in used):definitions.append('Declared visual reference: '+refs(line))
            if not definitions:definitions=['Use the supplied images only as their explicitly described subject or scene references.']
            chosen=set(s['source_blocks']);actions=[];provenance=[]
            for row in shot['parts']:
                if row['source_block'] not in chosen:continue
                original=row.get('source_action',row['action']);action=row['action']
                action=shot_tokens.sub('[Shot 1]',action)
                action=refs(action)
                actions.append(action+row['raw_dialogue'])
                provenance.append(dict(source_block=row['source_block'],original_action=original,reference_mapped_action=action,raw_dialogue=row['raw_dialogue'],numeric_speech_times_advisory=plan['mode']=='with_voice'))
            if s['visual_only']:actions=[refs(shot_tokens.sub('[Shot 1]',s.get('duration_action_override',shot['body'])))]
            elif shot['source_blocks'][-1] in chosen:actions.append(refs(shot['tail']))
            if shot['global_action'].strip():actions.insert(0,refs(shot['global_action']))
            continuity='Do not insert reference stills or detail cards as shots. Maintain consistent framing and action direction at authored scene boundaries where compatible with the camera instructions.'
            if s['identity_subjects']:continuity+=' Preserve the same person, facial proportions, age, hair, clothing and accessories. Compare all references assigned to each identity together. Scene references supply scenery only. Maintain continuous motion within each authored take.'
            pacing='Perform each described action with its adjacent exact spoken line, preserving authored silent holds and emotional pauses. The complete natural dialogue determines timing; numeric speaking deadlines are advisory.' if plan['mode']=='with_voice' else 'Follow the chosen total duration, the authored actions, their exact lines and the intentional pauses.'
            sound='Generate synchronized native voice and mouth motion using the same speaker identity and natural delivery as the uploaded voice reference. The reference supplies vocal identity, never source words to repeat. Treat every supplied dialogue block above as a verbatim script. Speak every word once, in order; preserve short words and particles. After each scripted line ends, continue its described physical action with natural breathing or the requested ambience until the next scripted line. Do not fill a pause with speech. Do not invent a sign-off, greeting, filler, repetition, or extra line. Background music must not introduce unscripted vocals or intelligible words.' if plan['mode']=='with_voice' else 'Generate the requested native audio and only the exact specified dialogue. Treat every supplied dialogue block above as a verbatim script. Speak every word once, in order; preserve short words and particles. After the final scripted word, finish with natural silent breathing or the requested ambience. Do not invent a sign-off, greeting, filler, repetition, or extra line.'
            if s['visual_only']:sound='This authored visual interval has no dialogue. Preserve requested ambience without inventing speech.'
            summary=p['header'].split('summary:',1)[1].split('retention_analysis:',1)[0] if 'summary:' in p['header'] else ''
            retention=p['header'].split('retention_analysis:',1)[1] if 'retention_analysis:' in p['header'] else ''
            s['source_metadata']=p.get('source_metadata',dict(header=p['header'],tail=p['tail']))
            ambience,music=p['tail'].split('non_diegetic_music:',1) if 'non_diegetic_music:' in p['tail'] else (p['tail'],'N/A')
            s['prompt']='subject_definitions:\n'+'\n'.join(definitions)+'\nsummary:\n'+refs(summary)+'\nretention_analysis:\n'+refs(retention)+'\n'+continuity+'\ndetailed_description:\n'+'\n'.join(actions)+'\n'+pacing+'\noverall_soundscape:\n'+sound+'\n'+refs(ambience)+'\nnon_diegetic_music:\n'+refs(music)
            expected=[p['rows'][i]['raw_dialogue'] for i in s['source_blocks']]
            assert s['prompt'].count('<d>')==s['prompt'].count('</d>')==len(expected), 'dialogue_tag_boundaries'
            assert dialogue_tokens.findall(s['prompt'])==expected, 'dialogue_changed'
            assert s['text']==''.join(p['rows'][i]['text'] for i in s['source_blocks']), 'dialogue_changed'
            s['action_provenance']=provenance
            all_words.append(s['text'])
        assert ''.join(all_words)==''.join(r['text'] for r in p['rows']), 'dialogue_changed'
        assert plan['output_frames']==sum(s['model_frames'] for s in plan['segments']) and plan['output_frames']<=plan['max_seconds']*24, 'total_frame_budget'
        result=plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500044:
    """Fixed function formerly embedded in node 500044."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500044."
    def run(self, input_text, input_json):
        return _fixed_500044(input_text, input_json)

def _fixed_500043(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text)
        def spoken_cadence(text, voice, subject):
            if voice not in [1,2,3]:return text
            reference=' consistent with <Audio '+str(voice)+'>'
            natural='at a natural, articulate pace'+reference
            replacements=[
                ('at a brisk conversational pace','at a natural, articulate conversational pace'+reference),
                ('at a moderately brisk pace',natural),
                ('at a brisk, steady pace','at a natural, articulate, steady pace'+reference),
                ('at a brisk, energetic pace',natural+', retaining energetic delivery'),
                ('at a punchy, brisk pace',natural+', retaining punchy emphasis'),
                ('at a slightly accelerated brisk pace',natural),
                ('at a brisk, energetic e-commerce pace',natural+', retaining energetic e-commerce delivery'),
                ('at a crisp, brisk conversational tempo','at a natural, articulate conversational tempo'+reference+', retaining crisp articulation'),
                ('at a brisk, articulate pace',natural),
                ('at a brisk, engaging pace',natural+', retaining engaging delivery'),
                ('at a brisk pace',natural),
                ('in a brisk, decisive, highly persuasive tone',natural+', in a decisive, highly persuasive tone')]
            prefixes=['','on camera','on camera in connected, clearly articulated mandarin','on camera in clearly articulated mandarin','on camera from a slight profile-over-the-shoulder angle']
            def speech(m):
                value=m[2]
                for old,new in replacements:
                    pos=value.lower().find(old)
                    if pos>=0 and ' '.join(value[:pos].lower().split()) in prefixes:
                        value=value[:pos]+new+value[pos+len(old):]
                        break
                return m[1]+value
            owner=re.escape(str(subject))
            speaker=r'(\b(?:S|Subject\s+)'+owner+r'>?\s+(?:speaks|delivers|narrates|says)\b)([^.;\n]*)'
            pieces=re.split(r'(<d>.*?</d>)',text,flags=re.S)
            for i in range(0,len(pieces),2):pieces[i]=re.sub(speaker,speech,pieces[i],flags=re.I)
            return ''.join(pieces)

        if p['mode']=='with_voice':
            for s in p['shots']:
                for r in s['parts']:r['action']=spoken_cadence(r['action'],r['voice'],r['subject'])
            p['temporal_view']=True
        result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500043:
    """Fixed function formerly embedded in node 500043."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500043."
    def run(self, input_text):
        return _fixed_500043(input_text, "")

def _fixed_762020(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        if env.get('normalize') and not env['inventory']['audios'] and s.get('visual_only') and not s.get('text') and not s.get('speaker_units') and not s.get('raw_passthrough') and not s.get('continuation') and '<d>' not in s.get('prompt',''):
            source=env['source']
            if not source.lstrip().startswith('{'):
                heads=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
                prompt=s['prompt'];fields={}
                for i,key in enumerate(heads):fields[key]=prompt.partition(key+':')[2].partition(heads[i+1]+':' if i<5 else '\x00')[0].strip()
                marks=list(re.finditer(r'(?m)^\s*(?:\[Shot\s+\d+\]|(?:镜头|分镜|场景)\s*\d+\s*[:：])',source))
                shot=int(s['shot']);local=source
                if marks and shot<len(marks):
                    local=source[:marks[0].start()]+'\n'+source[marks[shot].start():marks[shot+1].start() if shot+1<len(marks) else len(source)]
                no_music=False;has_music=False
                for clause in re.split(r'[。！？;；\n,，]|(?<=[.!?])\s+',local):
                    for hit in re.finditer(r'背景音乐|配乐|音乐|\bbgm\b|\b(?:background\s+)?music\b',clause,re.I):
                        before=clause[:hit.start()].lower().strip();after=clause[hit.end():].lower().strip(' :：.')
                        negative=before.endswith(('no','without','do not add',"don't add",'no any','without any','无','不要','不加','没有','不需要','禁止','关闭','不要任何','不加任何','禁止添加','不添加')) or after in ['none','n/a','absent','off','无','不要','不加','关闭']
                        exception=any(word in clause.lower() for word in ['except','但是','但'])
                        if negative and not exception:no_music=True
                        else:has_music=True
                generic_music='Use only the music requested by the user; do not add sung lyrics.'
                if fields['non_diegetic_music'].strip()==generic_music and no_music and not has_music:fields['non_diegetic_music']='N/A.'
                sound=[]
                physical_words=set('wind breeze rain rainfall waves surf crickets footstep footsteps contact impact tap knock rustling'.split())
                physical_phrases=['room tone','air conditioning','风声','雨声','海浪','流水','虫鸣','环境底噪','室内底噪','空调','脚步声','敲击','碰撞声','落盘']
                for clause in re.split(r'[。！？;；\n,，]|(?<=[.!?])\s+',fields['detailed_description']):
                    clause=clause.strip()
                    low=clause.lower();words=set(re.findall('[a-z]+',low))
                    physical=bool(words.intersection(physical_words)) or any(term in low for term in physical_phrases)
                    if physical:
                        clause=re.sub(r'^(?:环境音|环境声|背景声|音效|声音|Soundscape|Ambience)\s*[:：]\s*','',clause,flags=re.I)
                        clause=re.sub(r'^(?:延续相同的|保持相同的|维持相同的|继续相同的|持续稳定的)','持续的',clause)
                        if clause not in sound:sound.append(clause)
                placeholder='Follow the physical sound requests written alongside the current shot.'
                if sound and placeholder in fields['overall_soundscape']:fields['overall_soundscape']=fields['overall_soundscape'].replace(placeholder,';\n'.join(sound)+'.\n')
                s['prompt']='\n'.join(key+':\n'+fields[key] for key in heads)
                s['native_sound_fields']=dict(version='plain_current_shot_v1',explicit_no_music=no_music and not has_music,sound_clauses=len(sound))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed762020:
    """Fixed function formerly embedded in node 762020."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 762020."
    def run(self, input_text, input_json):
        return _fixed_762020(input_text, input_json)

def _fixed_500042(input_text, input_json=""):
    result = ""
    try:
        plan=json.loads(input_text);p=json.loads(input_json)
        assert plan['schema']=='rh-native-plan-v1' and p['schema']=='rh-native-source-v1', 'invalid_schema'
        present=p['inventory']['images']
        roles={}
        speakers={r['subject'] for r in p['rows']}
        for sid,lines in p['subject_defs'].items():
            description=' '.join(lines)
            person=re.search(r'\b(?:person|woman|man|girl|boy|character|face|identity|speaker|actor)\b|人物|女性|男性|女人|男人|角色|人脸|面部|五官',description,re.I)
            scene=re.search(r'\b(?:scene|scenery|landscape|environment|background|location)\b|场景|环境|背景|风景|地点',description,re.I)
            roles[sid]='person' if sid in speakers or person else ('scene' if scene else 'reference')
        for s in plan['segments']:
            shot=p['shots'][s['shot']]
            outside=re.sub(r'<d>.*?</d>','',shot['body'],flags=re.S)
            subjects=list(dict.fromkeys(re.findall(r'(?:<Subject\s+|\bS)(\d+)>?',outside)))
            if not subjects and len(p['subject_defs'])==1:subjects=list(p['subject_defs'])
            own=[];owners={}
            for sid in subjects:
                for slot in p['identity_banks'].get(sid,[]):
                    if slot not in own:own.append(slot)
                    owners.setdefault(str(slot),[]).append(sid)
            notes=p['header'].split('summary:',1)[-1] if 'summary:' in p['header'] else ''
            selected=list(dict.fromkeys(own+[int(x) for x in re.findall(r'<Picture\s+(\d+)>',outside+'\n'+notes)]))
            if not selected:selected=present[:]
            assert len(selected)<=9 and all(x in present for x in selected), 'missing_reference'
            s['original_slots']=selected;s['bindings']=[]
            for i,slot in enumerate(selected,1):
                ids=list(dict.fromkeys(owners.get(str(slot),[])))
                bound=list(dict.fromkeys(roles[sid] for sid in ids))
                role='speaker_identity' if 'person' in bound else ('scene' if 'scene' in bound else 'declared_reference')
                s['bindings'].append(dict(original_slot=slot,local_picture=i,subject_ids=ids,subject_roles=bound,roles=[role],role=role))
            people=[sid for sid in subjects if roles.get(sid)=='person']
            identity=[b['original_slot'] for b in s['bindings'] if b['role']=='speaker_identity']
            s['crop_source']=identity[0] if len(people)==1 and identity and len(selected)<9 else 0
            s['crop_is_suggestion_only']=True
            s['slot_indices']=selected+[0]*(9-len(selected))
            for i,value in enumerate(s['slot_indices'],1):s['slot_'+str(i)]=value
            s['identity_subjects']=people;s['declared_subjects']=subjects
            s['subject_roles']={sid:roles.get(sid,'reference') for sid in subjects}
            s['speaker_units']=[dict(source_block=i,subject=p['rows'][i]['subject'],voice=p['rows'][i]['voice']) for i in s['source_blocks']]
        result=plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500042:
    """Fixed function formerly embedded in node 500042."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500042."
    def run(self, input_text, input_json):
        return _fixed_500042(input_text, input_json)

def _fixed_500048(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text)
        if p['mode']=='with_voice' and len(p['shots'])>1:
            # Shared source embedded into the two existing code nodes; no added node or model call.
            def opening_boundary(text):
                stripped=text.lstrip()
                if not stripped.lower().startswith('[shot '):return text
                label,sep,body=stripped.partition(']')
                if not sep:return text
                body=body.lstrip();clock=''
                for mark in [',',';', '，','：']:
                    head,split,rest=body.partition(mark)
                    if split:
                        words=head.lower().split()
                        allowed='to and s sec secs second seconds - – —'.split()
                        valid=len(words)>1 and words[0] in ['at','from','between'] and all(w in allowed or w.replace(':','').replace('.','').isdigit() for w in words[1:])
                        if valid and (words[0]!='at' or ':' in head or words[-1] in allowed):
                            clock=body[:len(head)+1]+' ';body=rest.lstrip();break
                if body.startswith('During the corresponding action'):
                    body=body[len('During the corresponding action'):].lstrip(' ,;:，：')
                if body.lower().startswith('matching <picture '):
                    head,sep,rest=body.partition(',')
                    if sep and head.rstrip().endswith('>'):clock+=head+', ';body=rest.lstrip()
                words=body.split(None,12);lower=[w.lower() for w in words];used=0
                for word in lower:
                    if word not in 'the camera scene shot video we smooth smoothly hard direct directly'.split():break
                    used+=1
                if len(lower)<=used or lower[used] not in ['cut','cuts','cutting','transition','transitions','transitioning']:return text
                used+=1
                if len(lower)>used and lower[used]=='back':used+=1
                if len(lower)<=used+1 or lower[used]!='to':return text
                used+=1
                target=body.split(None,used)[used]
                first=target.split('.',1)[0].split(';',1)[0].lower()
                # Explicit later timing is an intra-shot instruction, not an opening edit cue.
                if any(word in ' '+first+' ' for word in [' after ',' before ',' once ',' when ',' until ',' then ',' later ',' over ',' during ',' at ',' if ',' unless ']):return text
                return label+'] '+clock+'From the first frame, show '+target
            for shot in p['shots']:
                for row in shot['parts']:row['action']=opening_boundary(row['action'])
                if shot['visual_only']:shot['body']=opening_boundary(shot['body'])
            head,sep,rest=p['header'].partition('summary:')
            overview,end,retention=rest.partition('retention_analysis:')
            rows=re.split(r'(?<=[.!?。])\s+|\n+',overview)
            overview=' '.join(clause for clause in rows if not re.search(r'\b(?:\d+|two|three|four|five|six|seven|eight|nine|ten|multiple|multi)[ -]*(?:shot|scene)s?\b|\d+:\d+',clause,re.I))
            if sep and end:p['header']=head+sep+'\n'+overview+'\n'+end+retention
        result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500048:
    """Fixed function formerly embedded in node 500048."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500048."
    def run(self, input_text):
        return _fixed_500048(input_text, "")

def _fixed_500047(input_text, input_json=""):
    result = ""
    try:
        compiled_pattern_0 = re.compile('(?<=[.!?。])\\s+|\\n+', 0)
        compiled_pattern_1 = re.compile('-scene| scenes|scene cut|transition|cut to', re.I)
        compiled_pattern_2 = re.compile('<Picture\\s+(\\d+)>', 0)
        compiled_pattern_3 = re.compile('\\[Shot\\s+(\\d+)\\]', 0)
        compiled_pattern_4 = re.compile('\\[Shot\\s+\\d+\\]', 0)
        compiled_pattern_5 = re.compile('<d>.*?</d>', re.S)
        compiled_pattern_6 = re.compile('<(Picture|Audio|Video)\\s+(\\d+)>', 0)
        compiled_pattern_7 = re.compile('^(\\s*\\[Shot\\s+\\d+\\]\\s*)(?:Smooth cut to|Cut to)\\s+', 0)
        compiled_pattern_8 = re.compile('\\s*<Picture\\s+\\d+>', 0)
        compiled_pattern_9 = re.compile('\\n\\s*\\n', 0)
        compiled_pattern_10 = re.compile('^\\s*\\[Shot\\s+\\d+\\]\\s*', 0)
        plan = json.loads(input_text)
        result = input_text
        if plan['mode'] == 'with_voice' and plan['count'] > 1:
            p = json.loads(input_json)
            assert p['schema'] == 'rh-native-source-v1' and p.get('temporal_view'), 'invalid_scope_source'
            keys = ['subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music']
            header, separator, tail = p['header'].partition('summary:')
            summary, separator, retention = tail.partition('retention_analysis:')
            header = header.split('retention_analysis:', 1)[0]
            lines = header.splitlines()
            cache = {}

            def context(text):
                if text not in cache:
                    rows = []
                    for clause in compiled_pattern_0.split(text):
                        if compiled_pattern_1.search(clause):
                            continue
                        pictures = {int(n) for n in compiled_pattern_2.findall(clause)}
                        shots = {int(n) for n in compiled_pattern_3.findall(clause)}
                        rows.append((pictures, shots, compiled_pattern_4.sub('this shot', clause)))
                    cache[text] = rows
                return ' '.join((row[2] for row in cache[text] if not row[0] - active and (not row[1] - {s['shot'] + 1})))
            for s in plan['segments']:
                shot = p['shots'][s['shot']]
                active = set()
                for sid in s['declared_subjects']:
                    active.update(p['identity_banks'].get(sid, []))
                active.update((int(n) for n in compiled_pattern_2.findall(compiled_pattern_5.sub('', shot['body']))))
                maps = {'Picture': dict(zip(s['original_slots'], range(1, 10))), 'Audio': dict(zip(p['inventory']['audios'], [1, 2, 3])), 'Video': dict(zip(p['inventory']['videos'], [1, 2, 3]))}

                def refs(text):

                    def token(m):
                        return '<' + m[1] + ' ' + str(maps[m[1]][int(m[2])]) + '>'
                    return compiled_pattern_6.sub(token, text)

                def boundary(text):
                    return compiled_pattern_7.sub('\\1From the first frame, the scene is ', text, count=1)
                prompt = s['prompt']
                fields = s.pop('scope_fields')
                defs = [refs(line) for sid in s['declared_subjects'] for line in p['subject_defs'].get(sid, []) if line in lines]
                for line in lines:
                    used = {int(n) for n in compiled_pattern_2.findall(line)}
                    if compiled_pattern_8.match(line) and used and (used <= active):
                        defs.append(refs(line))
                fields['subject_definitions'] = '\n'.join(defs) or 'Use supplied references only for their declared identity and current scene roles.'
                for row in s['action_provenance']:
                    old = row['reference_mapped_action']
                    new = boundary(old)
                    if new != old:
                        needle = old + row['raw_dialogue']
                        assert fields['detailed_description'].count(needle) == 1, 'scope_action_not_unique'
                        fields['detailed_description'] = fields['detailed_description'].replace(needle, new + row['raw_dialogue'], 1)
                        row['reference_mapped_action'] = new
                        row['boundary_projection'] = dict(before=row['original_action'], after=boundary(row['original_action']))
                if s['visual_only']:
                    old = refs(compiled_pattern_4.sub('[Shot 1]', shot['body']))
                    fields['detailed_description'] = fields['detailed_description'].replace(old, boundary(old), 1)
                if shot['global_action'].strip():
                    old = refs(shot['global_action'])
                    assert old in fields['detailed_description'], 'scope_global_not_found'
                    fields['detailed_description'] = fields['detailed_description'].replace(old, refs(context(shot['global_action'])), 1)
                opening = shot['parts'][0]['action'] if shot['parts'] else shot['body']
                if s['source_blocks'] and p['rows'][s['source_blocks'][0]].get('measured_sentence_window'):
                    opening = p['rows'][s['source_blocks'][0]]['action']
                opening = compiled_pattern_9.split(opening.strip(), maxsplit=1)[0]
                opening = compiled_pattern_10.sub('', boundary(opening))
                fields['summary'] = 'One continuous shot, already established from the first frame. ' + refs(opening) + '\n' + refs(context(summary))
                fields['retention_analysis'] = refs(context(retention)) + '\nDo not insert reference stills or detail cards as shots. The first frame already shows the current described location and physical state.'
                if s['identity_subjects']:
                    fields['retention_analysis'] += ' Preserve the same person, facial proportions, age, hair, clothing and accessories. Compare all references assigned to each identity together. Scene references supply scenery only. Maintain continuous motion within each authored take.'
                out = '\n'.join((k + ':\n' + fields[k] for k in keys))
                assert compiled_pattern_5.findall(out) == compiled_pattern_5.findall(prompt), 'scope_dialogue_changed'
                s['prompt'] = out
            result = plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500047:
    """Fixed function formerly embedded in node 500047."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500047."
    def run(self, input_text, input_json):
        return _fixed_500047(input_text, input_json)

def _fixed_500045(input_text, input_json=""):
    result = ""
    try:
        env=json.loads(input_text);seconds=float(env['selected_seconds'])
        assert env['raw_route'] and math.isfinite(seconds) and 4<=seconds<=30, 'selected_outside4_30'
        n=max(107,5+17*int((seconds*24-5)//17))
        assert 96<=n<=720, 'fixed_frame_budget'
        slots=env['inventory']['images'];s=dict(segment_index=0,shot=0,source_blocks=[],text='',prompt=env['raw'],original_slots=slots,bindings=[],native_audio=True,model_frames=n,keep_count=n,keep_start=0,output_start=0,measured_seconds=n/24,visual_only=False,continuation=False,guide_enabled=False,crop_source=0,identity_subjects=[],declared_subjects=[],speaker_units=[],slot_indices=slots+[0]*(9-len(slots)),raw_passthrough=True)
        for i,value in enumerate(s['slot_indices'],1):s['slot_'+str(i)]=value
        result=dict(schema='rh-native-plan-v1',mode='without_voice',count=1,requested_seconds=seconds,actual_seconds=n/24,output_frames=n,max_seconds=30,segments=[s])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500045:
    """Fixed function formerly embedded in node 500045."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500045."
    def run(self, input_text):
        return _fixed_500045(input_text, "")

def _fixed_500161(input_text, input_json=""):
    result = ""
    try:
        plan=json.loads(input_text)
        if plan['mode']=='with_voice' and plan['count']>1:
            keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            def blank_dialogue(m):return ' '*len(m[0])
            for s in plan['segments']:
                prompt=s['prompt'];masked=re.sub(r'<d>.*?</d>',blank_dialogue,prompt,flags=re.S)
                anchored='\n'+masked;marks=[anchored.find('\n'+k+':\n') for k in keys]
                assert marks==sorted(marks) and all(anchored.count('\n'+k+':\n')==1 for k in keys), 'invalid_h3_scope_fields'
                fields={k:prompt[marks[i]+len(k)+2:marks[i+1] if i<5 else len(prompt)] for i,k in enumerate(keys)}
                s['scope_fields']=fields
        result=plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500161:
    """Fixed function formerly embedded in node 500161."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500161."
    def run(self, input_text):
        return _fixed_500161(input_text, "")

def _fixed_762009(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);p=json.loads(input_json);result=s
        if p['enabled']:
            assert not s.get('text') and not s.get('speaker_units') and '<d>' not in s['prompt'], 'R18Q_SPEECH_BYPASS'
            def shift(m):
                ms=int(round((int(m[1])*60+float(m[2])+p['context_seconds'])*1000))
                return '%02d:%06.3f'%(ms//60000,ms%60000/1000)
            prompt=re.sub(r'(?<!\d)(\d{2}):(\d{2}\.\d{3})(?!\d)',shift,s['prompt'])
            setup='From 00:00.000 to 00:01.000, establish only the current shot composition and its initial physical state while continuing the supplied environmental sound. The authored action begins at 00:01.000; its physical sound events follow that action.\n'
            continuity='The shared environment remains audibly continuous across this camera change. Continue its existing sound texture and strength naturally from the supplied starting audio. This background is already present; it does not stop or restart at the camera change. New physical sound events still follow only the current authored action.\n'
            prompt=prompt.replace('detailed_description:\n','detailed_description:\n'+setup,1)
            prompt=prompt.replace('overall_soundscape:\n','overall_soundscape:\n'+continuity,1)
            result=dict(s,prompt=prompt,model_frames=p['render_frames'],delivered_frames=p['delivered_frames'],audio_context=p)

        # ---- Independent reference preroll branch; never enters R18Q_SPEECH_BYPASS ----
        htplan=p.get('head_trim',{})
        if htplan.get('enabled'):
            assert not p['enabled'] and not s.get('audio_context'),'HEAD_TRIM_DOUBLE_PREFIX'
            assert htplan['prefix_frames']==24 and htplan['prefix_seconds']==1.0 and htplan['delivered_frames']==s['model_frames'],'HEAD_TRIM_PLAN_MISMATCH'
            before=s['prompt'];parts=re.split(r'(<d>.*?</d>)',before,flags=re.S)
            assert before.count('<d>')==before.count('</d>')==len(re.findall(r'<d>.*?</d>',before,re.S)),'HEAD_TRIM_DIALOGUE_ENVELOPE'
            def ht_shift(m):
                ms=int(round((int(m[1])*60+float(m[2])+1.0)*1000))
                return '%02d:%06.3f'%(ms//60000,ms%60000/1000)
            prompt=''.join(part if i%2 else re.sub(r'(?<!\d)(\d{2}):(\d{2}\.\d{3})(?!\d)',ht_shift,part) for i,part in enumerate(parts))
            assert prompt.count('detailed_description:\n')==1 and prompt.count('overall_soundscape:\n')==1,'HEAD_TRIM_SECTION_ENVELOPE'
            end=1.0+htplan['delivered_seconds'];render_end=htplan['render_frames']/24
            def ht_time(x):
                ms=int(round(x*1000));return '%02d:%06.3f'%(ms//60000,ms%60000/1000)
            setup=('Generation-only preroll window 00:00.000–00:01.000: hold the current described opening composition and initial physical state; no authored action or speech occurs in this preroll. All authored action, dialogue and physical sound events run in the retained window 00:01.000–'+ht_time(end)+'. The timestamps outside dialogue have been translated to this render clock. After '+ht_time(end)+' until '+ht_time(render_end)+', hold the final physical state without adding words or events; this model-grid tail is not delivered.\n')
            sound=('Generation-only preroll timing: from 00:00.000 to 00:01.000 there is no speech, singing or authored sound event. Begin the exact assigned dialogue and requested soundtrack at or after 00:01.000, within the retained window ending '+ht_time(end)+'. Preserve every assigned word in that window; never say a word in the discarded preroll or repeat it in the grid tail.\n')
            prompt=prompt.replace('detailed_description:\n','detailed_description:\n'+setup,1).replace('overall_soundscape:\n','overall_soundscape:\n'+sound,1)
            assert re.findall(r'<d>.*?</d>',prompt,re.S)==re.findall(r'<d>.*?</d>',before,re.S),'HEAD_TRIM_SCRIPT_CHANGED'
            assert re.findall(r'<Audio\s+\d+>',prompt)==re.findall(r'<Audio\s+\d+>',before),'HEAD_TRIM_AUDIO_BINDING_CHANGED'
            result=dict(s,prompt=prompt,model_frames=htplan['render_frames'],delivered_frames=htplan['delivered_frames'],head_trim=dict(htplan,render_setup=setup,audio_setup=sound))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed762009:
    """Fixed function formerly embedded in node 762009."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 762009."
    def run(self, input_text, input_json):
        return _fixed_762009(input_text, input_json)

def _fixed_1601(input_text, input_json=""):
    result = ""
    try:
        values = {'1:1': '1:1 (Square)', '2:3': '2:3 (Portrait Photo)', '3:4': '3:4 (Portrait Standard)', '9:16': '9:16 (Portrait Widescreen)', '3:2': '3:2 (Photo)', '4:3': '4:3 (Standard)', '16:9': '16:9 (Widescreen)', '21:9': '21:9 (Ultrawide)'}
        aliases = {'横屏': '16:9', '竖屏': '9:16', '方形': '1:1', '正方形': '1:1'}
        raw = input_text.strip().replace("：", ":").replace(" ", "")
        raw = aliases.get(raw, raw)
        if raw not in values:
            raise ValueError("画面比例请填写16:9、9:16、1:1、2:3、3:2、3:4、4:3或21:9")
        result = values[raw]
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed1601:
    """Fixed function formerly embedded in node 1601."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 1601."
    def run(self, input_text):
        return _fixed_1601(input_text, "")

def _fixed_762001(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);state=json.loads(input_json);prev=state.get('ambience_previous',{})
        prompt=s.get('prompt','');scope=s.get('audio_intent_scope',{})
        sound=prompt.partition('overall_soundscape:')[2].partition('non_diegetic_music:')[0].lower()
        local=prompt.partition('detailed_description:')[2].partition('overall_soundscape:')[0].lower()
        bed=[]
        steady=set('breeze wind rainfall rain river waterfall surf waves crickets cicadas traffic'.split())
        excluded=set('no without absent stop silence fade whoosh impact contact crash footstep music'.split())
        for clause in re.split(r'[;；\n]',sound):
            clause=re.sub(r'\s+',' ',clause).strip(' ,.:');words=set(re.findall('[a-z]+',clause))
            present=bool(words.intersection(steady)) or any(x in clause for x in ['room tone','air conditioning','风声','雨声','海浪','流水','环境底噪','室内底噪','空调低鸣','虫鸣','交通底噪'])
            banned=bool(words.intersection(excluded)) or any(x in clause for x in ['静音','无声','停止','渐弱','撞击','落盘','脚步','音乐'])
            if present and not banned:bed.append(clause)
        intent=local+' '+sound
        pause=any(x in intent for x in ['absolute silence','complete silence','silent pause','silence for','pause in sound','pause in all sound','sound stops','sound cuts out','fade out','fade to silence','ambience stops','完全静音','全部静音','所有声音停止','环境声停止','静音1','静音一','静音 1'])
        scene_break=any(x in intent for x in ['move indoors','moves indoors','enter a room','enters a room','enter the room','enter a building','enters a building','enter the car','enters the car','go underwater','goes underwater','ambience changes','different acoustic space','a different location','a new location','进入室内','进入房间','进入车内','沉入水中','声场切换','环境声切换','换一个地点'])
        nonverbal=(scope.get('speech') is False and scope.get('music')=='absent' and not s.get('text') and not s.get('speaker_units') and '<d>' not in prompt and not s.get('raw_passthrough') and not s.get('continuation') and not s.get('guide_enabled'))
        body=sound.partition('absent throughout this shot.')[2] or sound
        discrete=set('contact impact crash bang footstep footsteps knock clap bell chime gunshot scream laughter crying singing humming tap taps tapping clink clinks click clicks scrape'.split())
        donor_event=bool(set(re.findall('[a-z]+',body)).intersection(discrete)) or any(x in body for x in ['落盘','撞击','触碰声','碰撞声','金属轻响','脚步','敲击','拍手','铃声','枪声','尖叫','笑声','哼唱'])
        frames=int(s['model_frames'])
        c1_cut=s.get('c1_authored_cut_v1') is True
        current=dict(index=int(s['segment_index']),seconds=frames/24,bed=bed,nonverbal=nonverbal,silence=pause,donor_safe=nonverbal and not pause and not donor_event)
        shared=[x for x in bed if x in prev.get('bed',[])]
        enabled=bool(not c1_cut and shared and nonverbal and not pause and not scene_break and prev.get('donor_safe') and prev.get('index')==current['index']-1 and frames>=60 and (frames-5)%17==0 and prev.get('seconds',0)>=2.5)
        prefix=24 if enabled else 0
        render=5+17*math.ceil((frames+prefix-5)/17) if enabled else frames
        result=dict(version='native_audio_context_r18q',enabled=enabled,reason='same_authored_nonverbal_bed' if enabled else 'preserve_original_route',shared_bed=shared,context_seconds=prefix/24,context_frames=prefix,render_frames=render,delivered_frames=frames,delivered_seconds=frames/24,donor_start=max(0.0,prev.get('seconds',0)-prefix/24),current=current)

        # ---- shared_reference_head_trim_v1: independent from the old nonverbal donor gate ----
        ht_prov=s.get('action_provenance') or []
        ht_bits=[]
        try:
            for x in ht_prov:
                try:
                    ht_bits.append(x.get('original_action') or '')
                except Exception:
                    pass
        except Exception:
            ht_bits=[]
        ht_source='\n'.join(ht_bits)
        ht_refs=bool(s.get('original_slots'))
        ht_gate=not c1_cut and not any(s.get(k) for k in ['raw_passthrough','continuation','guide_enabled','internal_split_origin','first_frame_enabled','boundary_image_inherit'])
        ht_literal=bool(re.search(r'(?i)\b(?:exact\s+(?:first\s+)?(?:frame|still)|first[- ]frame|last[- ]frame|keyframe)\b|首帧|尾帧|关键帧',re.sub(r'<d>.*?</d>','',ht_source,flags=re.S)))
        ht_render=5+17*math.ceil((frames+24-5)/17)
        ht_ok=bool(ht_refs and ht_gate and not ht_literal and frames>=60 and (frames-5)%17==0 and ht_render<=362 and not enabled)
        ht_reason=('existing_audio_context_single_crop' if enabled else 'no_reference_images' if not ht_refs else 'protected_guide_or_raw_route' if not ht_gate else 'explicit_keyframe_request' if ht_literal else 'unsupported_render_window' if frames<60 or (frames-5)%17 or ht_render>362 else 'reference_preroll')
        result['head_trim']=dict(version='shared_reference_head_trim_v1',enabled=ht_ok,reason=ht_reason,prefix_frames=24 if ht_ok else 0,prefix_seconds=1.0 if ht_ok else 0.0,render_frames=ht_render if ht_ok else frames,delivered_frames=frames,delivered_seconds=frames/24,frame_rate=24)
        # These fields feed only the video/audio crop switches, never the audio donor/guide gate.
        result['crop_enabled']=bool(enabled or ht_ok)
        result['crop_start_frames']=prefix if enabled else 24 if ht_ok else 0
        result['crop_start_seconds']=prefix/24 if enabled else 1.0 if ht_ok else 0.0
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed762001:
    """Fixed function formerly embedded in node 762001."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 762001."
    def run(self, input_text, input_json):
        return _fixed_762001(input_text, input_json)

def _fixed_762000(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        prompt=s.get('prompt','');scope=s.get('audio_intent_scope',{})
        eligible=(scope.get('speech') is False and scope.get('music')=='absent' and not s.get('text') and not s.get('speaker_units') and '<d>' not in prompt and not s.get('raw_passthrough') and not s.get('continuation') and not s.get('guide_enabled'))
        if eligible:
            head,_,tail=prompt.partition('overall_soundscape:');raw_sound,_,music=tail.partition('non_diegetic_music:')
            scoped=[];changed=False
            for clause in re.split(r'(?<=[;；\n])',raw_sound):
                low=clause.lower();markers=[x for x in ['only in ','only during ','仅在','只在'] if x in low]
                if len(markers)==1 and low.count(markers[0])==1:
                    marker=markers[0];start=low.find(marker)
                    assert start>=0,'substring not found'
                    prefix=low[:start].rstrip();rest=low[start+len(marker):]
                    targets=[];end=0
                    if marker.startswith('only'):
                        part=rest.lstrip();cursor=len(rest)-len(part)
                        for scope_index in range(60):
                            if not part.startswith('[shot') or ']' not in part:break
                            close=part.find(']')
                            assert close>=0,'substring not found'
                            number=part[5:close].strip()
                            if not number.isdigit():break
                            targets.append(int(number));end=cursor+close+1
                            remain=rest[end:].lstrip();separator=''
                            for sep in [',','and ','&']:
                                if remain.startswith(sep):separator=sep;break
                            if not separator:break
                            following=remain[len(separator):].lstrip()
                            if not following.startswith('[shot'):break
                            cursor=len(rest)-len(following);part=following
                    else:
                        match=re.match(r'(?:第\s*)?(\d+)\s*(?:个)?镜头|镜头\s*(\d+)',rest)
                        if match:targets=[int(match.group(1) or match.group(2))];end=match.end()
                    remainder=rest[end:].lstrip()
                    unclear=prefix.endswith(('not','不','不是','不仅','不只','并非')) or any(remainder.startswith(x) for x in ['-','–','—','to ','through ','至','到'])
                    steady=any(x in low for x in ['wind','rain','river','waves','surf','crickets','traffic','breeze','room tone','air conditioning','风声','雨声','环境底噪','流水'])
                    if targets and not unclear and not steady:
                        changed=True
                        if int(s.get('shot',-1))+1 not in targets:continue
                        replacement='in this shot' if marker.startswith('only') else '在本镜头'
                        clause=clause[:start]+replacement+clause[start+len(marker)+end:]
                scoped.append(clause)
            if changed:
                result=dict(s,prompt=head+'overall_soundscape:'+''.join(scoped)+'non_diegetic_music:'+music)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed762000:
    """Fixed function formerly embedded in node 762000."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 762000."
    def run(self, input_text):
        return _fixed_762000(input_text, "")

def _fixed_409612(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_json)
        memo={}
        if input_text.lstrip().startswith('{'):
            staged_input=json.loads(input_text);memo=staged_input['regex_memo_v1'];input_text=staged_input['input_text']
        i=int(input_text)
        def staged(site,text,live):
            table=memo.get(site,{})
            if text in table:return table[text]
            return live(text)
        assert 0<=i<p['count'], 'VIP_LOOP_INDEX'
        s=dict(p['segments'][i]);origin=s.get('internal_split_origin')
        s['guide_enabled']=bool(origin and i>0 and p['segments'][i-1].get('internal_split_origin')==origin)
        s['carry_image']=bool(origin and i+1<p['count'] and p['segments'][i+1].get('internal_split_origin')==origin)
        s['continuation']=s['guide_enabled']
        if s['guide_enabled']:
            instruction='Continue the same uninterrupted take from the supplied initial-frame guide: preserve the exact camera framing, person position, wardrobe, props and ongoing physical state at the boundary. Proceed naturally with only the current dialogue and its corresponding action; do not restart the introduction or add a cut.'
            s['prompt']=s['prompt'].replace('retention_analysis:', 'retention_analysis:\n'+instruction,1)
        result=s


        # Boundary-image inheritance is distinct from uninterrupted internal continuation.
        # Read only compiler-provenance action text, never global summary/dialogue.
        def boundary_request(previous,current):
            if previous.get('raw_passthrough') or current.get('raw_passthrough'):
                return False,'raw_passthrough'
            if current.get('internal_split_origin') or previous.get('internal_split_origin'):
                return False,'internal_split_owned'
            def people(segment):
                return sorted(segment.get('identity_subjects') or set(str(u['subject']) for u in segment.get('speaker_units',[]) if u.get('subject')))
            if not people(current) or people(current)!=people(previous):
                return False,'identity_scope_changed_or_unknown'
            if sorted(current.get('original_slots',[]))!=sorted(previous.get('original_slots',[])):
                return False,'reference_scope_changed'
            if '<Video ' in current.get('prompt','') or '<Video ' in previous.get('prompt',''):
                return False,'reference_video_owned'
            provenance=current.get('action_provenance',[])
            if not provenance:
                return False,'no_compiler_action_provenance'
            action=provenance[0].get('original_action','')
            action=re.sub(r'<d>.*?</d>','',action,flags=re.S)
            # Explicit authored camera conflict wins over a continuity phrase.
            if staged('anchor',action,anchor_live):
                return False,'explicit_current_reference_anchor'
            if staged('conflict',action,conflict_live):
                return False,'explicit_camera_or_scene_change'
            clauses=re.split(r'[;。\n]|(?<!\d)\.(?!\d)',action)
            positive=False
            for clause in clauses:
                if staged('neg',clause,neg_live):
                    continue
                english=staged('english',clause,english_live)
                chinese=staged('chinese',clause,chinese_live)
                if english or chinese:positive=True
            return positive,'explicit_previous_boundary_geometry' if positive else 'no_explicit_geometry_inheritance'
        def anchor_live(action):return bool(re.search(r'(?:current shot begins from|first[- ]frame|keyframe|composition anchor).{0,40}<Picture\s+\d+>',action,re.I))
        def conflict_live(action):return bool(re.search(r'\b(?:cut|switch|reset|change|pull\s+back|zoom\s+out)\s+(?:\w+\s+){0,3}(?:to\s+)?(?:a\s+)?(?:wide|close[- ]?up|medium|full[- ]body|long\s+shot|different\s+(?:framing|scene|room)|new\s+(?:scene|room))\b|(?:切换|切到|改为|拉回|拉远|换成).{0,10}(?:全景|远景|全身|近景|中景|新场景|另一场景)|(?:different|new)\s+(?:location|room|scene)\b|换场|换装',action,re.I))
        def neg_live(clause):return bool(re.search(r"""\b(?:not|never|avoid|without)\b|don't|do not|不要|不继承|不沿用|不承接|不保持""",clause,re.I))
        def english_live(clause):
            previous_end=r'(?:previous|preceding)\s+(?:shot|take)(?:[’\x27]s)?'
            dimension=r'(?:framing|distance|shot\s+size|camera\s+distance)'
            english=bool(re.search(r'\binherit(?:ed|s|ing)?\b',clause,re.I) and re.search(previous_end,clause,re.I) and re.search(dimension,clause,re.I))
            return english or bool(re.search(r'\b(?:match|maintain|preserve|keep)\b.{0,90}'+previous_end+r'.{0,35}(?:final|ending|end).{0,35}'+dimension,clause,re.I))
        def chinese_live(clause):return bool(re.search(r'(?:继承|承接|沿用|保持).{0,20}(?:上一镜|前一镜|前镜).{0,15}(?:结束|末尾|结尾|最终).{0,12}(?:景别|距离|构图)',clause))
        segments=p['segments']
        new_request,reason=boundary_request(segments[i-1],segments[i]) if i>0 else (False,'first_segment')
        next_request,next_reason=boundary_request(segments[i],segments[i+1]) if i+1<p['count'] else (False,'last_segment')
        s['boundary_image_inherit']=bool(new_request)
        s['first_frame_enabled']=bool(s['guide_enabled'] or new_request)
        s['carry_image']=bool(s['carry_image'] or next_request)
        s['boundary_image_policy_v1']={'reason':reason,'next_reason':next_reason,'audio_policy_unchanged':True,'continuation_policy_unchanged':True}
        if new_request:
            instruction='Use the supplied previous-shot ending image only as the opening visual boundary for the explicitly inherited camera distance/framing and current character state. This is a new authored shot, not an uninterrupted take. Follow its own camera angle, motion, actions and exact dialogue; do not restart a reference-photo opening. Do not inherit previous audio or dialogue.'
            s['prompt']=s['prompt'].replace('retention_analysis:', 'retention_analysis:\n'+instruction,1)
        result=s

        # C1: compiled authored-shot entry, after existing explicit boundary/guide policy.
        c1_domain=p.get('schema')=='rh-native-plan-v1' and p['count']==len(p['segments']) and all(x.get('shot')!=None and (x.get('source_blocks') or x.get('internal_split_origin') or x.get('visual_only')) and (not x.get('internal_split_origin') or x['internal_split_origin'][0]==x['shot']) for x in p['segments']) and any(x['shot']!=s['shot'] for x in p['segments'])
        if c1_domain and (i==0 or p['segments'][i-1]['shot']!=s['shot']) and not any(s.get(k) or p['segments'][i].get(k) for k in ['raw_passthrough','one_take_ctx','one_take_mode','guide_enabled','first_frame_enabled','boundary_image_inherit']) and not re.search(r'(?i)\b(?:exact\s+(?:first\s+)?(?:frame|still)|first[- ]frame|last[- ]frame|keyframe)\b|首帧|尾帧|关键帧',re.sub(r'<d>.*?</d>','',' '.join(x.get('original_action','') for x in s.get('action_provenance',[])),flags=re.S)):
            s['c1_authored_cut_v1']=True
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409612:
    """Fixed function formerly embedded in node 409612."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409612."
    def run(self, input_text, input_json):
        return _fixed_409612(input_text, input_json)

def _fixed_500099(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text)
        result={k:s[k] for k in ['prompt','original_slots','crop_source','identity_subjects']}
        result['raw_passthrough']=s.get('raw_passthrough',False)
        result['speaker_units']=s.get('speaker_units',[])
        if s.get('reference_scope'):result['reference_scope']=s['reference_scope']
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500099:
    """Fixed function formerly embedded in node 500099."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500099."
    def run(self, input_text):
        return _fixed_500099(input_text, "")

def _fixed_400475(input_text, input_json=""):
    result = ""
    try:
        row=json.loads(input_json)
        try:
            row['reference_pause_report']=json.loads(input_text)
        except Exception:
            row['reference_pause_report']={'error':'参考音频停顿检测未返回有效结果。'}
        result=row
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400475:
    """Fixed function formerly embedded in node 400475."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400475."
    def run(self, input_text, input_json):
        return _fixed_400475(input_text, input_json)

def _fixed_409040(input_text, input_json=""):
    result = ""
    try:
        def inline_speech(p):
            if 'quote_prefix' not in p or p.get('audios') or 'detailed_description:' in p['source']:return p
            out=[]
            pattern=r'[。；;，,]\s*(旁白|画外音|解说词|解说|Voiceover|voiceover|Narration|narration|口播|台词|对镜头说|对着镜头说|对镜头说道)\s*[:：]'
            for line in p['source'].splitlines():
                if line.lstrip().startswith(('不要','禁止','不能','别','请勿','错误示例','反例','例子','例如','假如','如果','招牌','标牌','字幕','标题')):out.append(line);continue
                heading=re.match(r'^(?:镜头|分镜|场景)\s*(\d+)\s*[:：]\s*(.+)$',line)
                if heading:out.append('镜头'+heading[1]);line=heading[2]
                matches=list(re.finditer(pattern,line)) if any(x in line for x in ['旁白','画外音','解说','voiceover','Voiceover','Narration','narration','口播','台词','镜头说']) else []
                if matches:
                    out.append('画面描述：'+line[:matches[0].start()])
                    for i,m in enumerate(matches):
                        key='旁白' if m[1].lower() in ['旁白','画外音','解说词','解说','voiceover','narration'] else '口播'
                        out.append(key+'：'+line[m.end():matches[i+1].start() if i+1<len(matches) else len(line)])
                else:out.append(re.sub(r'^(?:画外音|解说词|解说|voice[ -]?over|narration)\s*[:：]','旁白：',line,flags=re.I))
            p['source']='\n'.join(out);return p
        def normalize(p):
            if 'quote_prefix' not in p:return p
            if not re.search(r'(?m)^\s*[（(][^\n]*[）)].+',p['source']):return p
            lines=[];speaker=None;pending=None;shots=0
            qp=re.escape(p['quote_prefix'])+r'\d+\ue001'
            def restore(m):return p['quotes'][m[0]]
            for line in p['source'].splitlines():
                label=re.fullmatch(r'\s*((?:@?图片\s*[1-9]|[^：:\n]{1,30}?)(?:说|讲|说道|讲道)|口播文案|口播|台词|旁白)[:：]\s*',line)
                if label:
                    if pending is not None:lines.append(pending)
                    picture=re.fullmatch(r'@?图片\s*([1-9])(?:说|讲|说道|讲道)',label[1])
                    if picture:
                        if not re.search(r'(?m)^\s*(?:镜头|分镜|场景)\s*\d+',p['source']):
                            shots+=1;lines.append('镜头'+str(shots))
                        lines.append('画面参考：<Picture '+picture[1]+'>')
                    speaker=label[1];pending=line;continue
                direction=re.match(r'^\s*[（(]([^（）()]*)[）)](.+)$',line) if speaker else None
                if direction and re.search(r'挑眉|神情|手势|眼神|停顿|微笑|身体|前倾|语速|配合|单手',direction[1]):
                    words=re.sub(qp,restore,direction[2]);token=p['quote_prefix']+str(len(p['quotes']))+'\ue001'
                    p['quotes'][token]='“'+words+'”'
                    lines.extend(['人物表现：'+direction[1],speaker+'：'+token]);pending=None
                    continue
                if pending is not None:lines.append(pending);pending=None
                if line.strip():speaker=None
                lines.append(line)
            if pending is not None:lines.append(pending)
            p['source']='\n'.join(lines);return p

        result=normalize(inline_speech(json.loads(input_text))) if input_text.startswith('{') else input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409040:
    """Fixed function formerly embedded in node 409040."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409040."
    def run(self, input_text):
        return _fixed_409040(input_text, "")

def _fixed_409711(input_text, input_json=""):
    result = ""
    try:
        result='\n'.join(json.loads(input_text)['paths'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409711:
    """Fixed function formerly embedded in node 409711."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409711."
    def run(self, input_text):
        return _fixed_409711(input_text, "")

def _fixed_409033(input_text, input_json=""):
    result = ""
    try:
        # Validate reference-audio use without changing the input envelope.
        result=input_text
        if input_text.startswith('{'):
            p=json.loads(input_text)
            if 'prompt' in p:
                directions=re.sub(r'<d>.*?</d>','',p['prompt'],flags=re.S)
            else:
                def refs(s):
                    def ref(m):
                        kind='Picture' if m.group(1).lower() in '图片|图|参考图|参考图片|image'.split('|') else 'Audio'
                        return f'<{kind} {m.group(2)}>'
                    return re.sub(r'@(?:参考)?(图片|图|参考图|参考图片|image|音频|音色|audio)_?\s*(\d+)',ref,s,flags=re.I)
                directions=refs('\n'.join(p['out']))
            if any(w in directions.lower() for w in ['music','bgm','背景音乐','配乐','sound effect','sfx','音效']) and re.search(r'(?:background\s*music|bgm|背景音乐|配乐|sound\s*effects?|sfx|音效)[^\n.;。；<>]{0,40}(?:<Audio \d+>|@(?:音频|音色|audio)_?\d+)|(?:<Audio \d+>|@(?:音频|音色|audio)_?\d+)[^\n.;。；<>]{0,25}(?:as background music|作为背景音乐|用作配乐|as sound effects?|作为音效|用作音效)',directions,re.I):raise ValueError('音频被指定为背景音乐或音效；本应用音频入口用于音色或情绪参考，请修改用途或移除这段关联。')
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409033:
    """Fixed function formerly embedded in node 409033."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409033."
    def run(self, input_text):
        return _fixed_409033(input_text, "")

def _fixed_409031(input_text, input_json=""):
    result = ""
    try:
        if not input_text.startswith('{'):
            result=input_text
        else:
            # Resolve explicit identities before delivery states; do not infer new people.
            p=json.loads(input_text)
            if p.get('named_roles_active'):
                banks=p['role_emotion_banks'];aliases=p['role_emotion_aliases']
                explicit=r'(?:emotion|情绪|语气)\s*(?:from|reference|参考|使用|用|为)?\s*[:：=]?\s*(?:<Audio\s+\d+>|@?(?:音频|音色|audio)_?\s*\d+)'
                def disabled(context):
                    return any(w in context.lower() for w in '不使用情绪参考|不用情绪参考|不要情绪参考|关闭情绪参考|禁用情绪参考|do not use emotion reference|no emotion reference|without emotion reference'.split('|'))
                def mood(context):
                    found=re.findall(r'(?:emotion|情绪|语气)\s*[:：=]\s*([^\W\d_]+)',context,re.I)
                    values={aliases[x.lower()] for x in found if x.lower() in aliases}
                    if len(values)>1:raise ValueError('同一句出现不同情绪，请明确一个状态或直接指定参考音频。')
                    return sorted(values)[0] if values else None
                def suffix_info(s):
                    s=s.strip().lower()
                    if not s:return True,None
                    s=s.removesuffix('地')
                    for ending in '的语气|的情绪|的状态|的口吻|的声音'.split('|'):s=s.removesuffix(ending)
                    for beginning in '有点|稍微|很|非常|比较|有些|略显|用|带着|以'.split('|'):
                        if s.startswith(beginning):s=s[len(beginning):].strip();break
                    valid=s in aliases or s in '温柔|轻松|认真|激动|坚定|平和|沉稳|耐心|温暖|自信|害羞|无奈|感慨|疑惑|愉快|沮丧|哽咽|微笑着|苦笑着|大笑着|笑着|哭着|哽咽着'.split('|')
                    return valid,aliases.get(s)
                if 'prompt' not in p:
                    for index,row in enumerate(p['rows']):
                        actor=row['actor'];state=None;delivery=''
                        if actor not in p['definitions']:
                            for name in sorted(p['definitions'],key=len,reverse=True):
                                if not actor.startswith(name):continue
                                suffix=actor[len(name):].strip();valid,state=suffix_info(suffix)
                                direct=re.fullmatch(r'(?:用|使用)\s*(?:<Audio \d+>|@音频\d+)',suffix)
                                if direct:row['audio_context']+='\n音色参考 '+suffix.removeprefix('使用').removeprefix('用')
                                if valid or direct:actor=name;delivery='' if direct else suffix;break
                        if actor not in p['definitions']:
                            pic=re.fullmatch(r'(?:@?(?:图片|图|picture)\s*|<Picture\s+)([1-9])>?\s*(.*)',actor,re.I)
                            valid,state=suffix_info(pic[2]) if pic else (False,None)
                            if pic and valid:
                                owners=[name for name,desc in p['definitions'].items() if pic[1] in re.findall(r'(?:@?(?:图片|图|picture)\s*|<Picture\s+)(\d+)>?',desc,re.I)]
                                if not owners:raise ValueError('图片'+pic[1]+'未关联人物，请先说明这张图属于哪个角色。')
                                if len(owners)>1:raise ValueError('图片'+pic[1]+'关联了多个角色，请用角色名称说明谁在说话。')
                                actor=owners[0];delivery=pic[2]
                                token='<<VIP_LINE_'+str(index)+'>>'
                                p['out']=[line.replace(token,'画面参考<Picture '+pic[1]+'>。\n'+token) for line in p['out']]
                        if actor in '|他|她|它|人物|主角|这个人|这位人物'.split('|'):
                            if len(p['definitions'])!=1:raise ValueError('多人场景中“他/她”指向不明，请注明这句是谁说的。')
                            actor=list(p['definitions'])[0]
                        if actor not in p['definitions']:raise ValueError('人物“'+actor+'”未明确关联，请使用已声明的角色名称。')
                        row['actor']=actor
                        context=row['audio_context'];specified=mood(context)
                        if state and specified and state!=specified:raise ValueError('同一句出现不同情绪，请明确一个状态或直接指定参考音频。')
                        state=state or specified
                        if state:row['named_emotion_state']=state
                        if delivery:
                            token='<<VIP_LINE_'+str(index)+'>>'
                            p['out']=[line.replace(token,'人物表现：'+delivery+'。\n'+token) for line in p['out']]
                        chosen=banks.get(actor,{}).get(state)
                        if chosen and not disabled(context) and not re.search(explicit,context,re.I):row['audio_context']+='\n情绪参考 <Audio '+str(chosen)+'>。'
                else:
                    text=p['prompt'];start=text.find('detailed_description:')
                    if start<0:raise ValueError('substring not found')
                    cursor=start;parts=[text[:start]]
                    for m in re.finditer(r'<d>.*?</d>',text[start:],re.S):
                        a=start+m.start();b=start+m.end();context=text[cursor:a]
                        ids=re.findall(r'<Subject (\d+)>\s*\(S\d+[^)]*\)',context)
                        state=mood(context)
                        role=ids[-1] if ids else None
                        chosen=banks.get(role,{}).get(state)
                        if chosen and not disabled(context) and not re.search(explicit,context,re.I):context+=' emotion from <Audio '+str(chosen)+'>; '
                        parts.extend([context,text[a:b]]);cursor=b
                    parts.append(text[cursor:]);p['prompt']=''.join(parts)
                p.pop('role_emotion_aliases',None)
            result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409031:
    """Fixed function formerly embedded in node 409031."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409031."
    def run(self, input_text):
        return _fixed_409031(input_text, "")

def _fixed_409030(input_text, input_json=""):
    result = ""
    try:
        if not input_text.startswith('{'):
            result=input_text
        else:
            # Explicit role declarations are independent from optional emotion samples.
            p=json.loads(input_text)
            aliases={'自然':'natural','开心':'happy','高兴':'happy','喜悦':'happy','兴奋':'excited','激昂':'excited','不开心':'sad','难过':'sad','悲伤':'sad','伤心':'sad','低落':'low','低沉':'low','平静':'calm','冷静':'calm','惊讶':'surprised','生气':'angry','愤怒':'angry'}
            for name in 'natural happy excited sad low calm surprised angry'.split():aliases[name]=name
            pattern=r'(?<!\w)([^\W\d_]+?)\s*(?:的)?\s*(?:情绪|语气)?\s*(?:(?:参考|使用|用|来自|reference|ref|from)\s*[:：=]?|[:：=])\s*(?:<Audio\s+(\d+)>|@?(?:音频|音色|audio)_?\s*(\d+))'
            def clear_mood(m):return '' if m[1].lower() in aliases else m[0]
            formal='prompt' in p
            if formal:
                header=p['prompt'].split('detailed_description:',1)[0]
                entries=[]
                for line in header.splitlines():
                    ids=set(re.findall(r'<Subject (\d+)>',line))
                    if len(ids)==1:entries.append((sorted(ids)[0],line))
            else:
                entries=list(p['definitions'].items())
                for line in p['out']:
                    m=re.match(r'^\s*([^，,；;：:\s]+?)的((?:主音色|主声音|音色|声音|声线).*)$',line)
                    if m:
                        if m[1] in p['definitions']:raise ValueError('人物'+m[1]+'有重复声音声明，请合并。')
                        entries.append((m[1],line))
            banks={};rewrites={};cleaned={}
            uploaded=[i-8 for i,v in enumerate(input_json.split(',')) if 9<=i<18 and v.strip().lower() not in ['true','1']]
            for role,line in entries:
                bank=banks.setdefault(role,{})
                for m in re.finditer(pattern,line,re.I):
                    if m[1].lower() not in aliases:continue
                    mood=aliases[m[1].lower()];audio=int(m[2] or m[3])
                    if not 4<=audio<=9:raise ValueError('VIP_EMOTION_SLOT_REQUIRED：人物'+role+'的情绪参考必须使用音频4至9，音频1至3只用于主音色。')
                    if audio not in uploaded:raise ValueError('人物'+role+'的'+m[1]+'参考音频'+str(audio)+'未上传，请补充对应录音。')
                    if mood in bank and bank[mood]!=audio:raise ValueError('人物'+role+'的'+m[1]+'有多个参考，请保留一个对应录音。')
                    bank[mood]=audio
                clean=re.sub(pattern,clear_mood,line,flags=re.I)
                rewrites[line]=clean;cleaned[role]=clean
            if entries:
                p['role_emotion_banks']=banks;p['named_roles_active']=True
                p['role_emotion_aliases']=aliases
                if formal:
                    for line,clean in rewrites.items():header=header.replace(line,clean)
                    p['prompt']=header+'detailed_description:'+p['prompt'].split('detailed_description:',1)[1]
                else:
                    for role,clean in cleaned.items():
                        if role not in p['definitions']:clean=re.sub(r'^\s*'+re.escape(role)+r'的','',clean)
                        p['definitions'][role]=clean
                    def clean_meta(text):
                        for line,clean in rewrites.items():text=text.replace(line,clean)
                        return re.sub(pattern,clear_mood,text,flags=re.I)
                    p['out']=[clean_meta(line) for line in p['out']]
                    declarations={part.strip() for line in rewrites for part in line.splitlines()}
                    for row in p['rows']:
                        row['audio_context']='\n'.join(line for line in row['audio_context'].splitlines() if line.strip() not in declarations)
            result=p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409030:
    """Fixed function formerly embedded in node 409030."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409030."
    def run(self, input_text, input_json):
        return _fixed_409030(input_text, input_json)

def _fixed_400457(input_text, input_json=""):
    result = ""
    try:
        try:
            q=json.loads(input_text)['original']
            duration=float(q['duration_seconds']);silence=float(q['silence_ratio'])
            if not math.isfinite(duration) or duration<=0 or not math.isfinite(silence) or not 0<=silence<1:
                raise ValueError('录音为空或没有可用声音。')
        except Exception as exc:
            raise ValueError('主音色参考录音校验失败：'+str(exc))
        result={'ok':True,'duration':duration}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400457:
    """Fixed function formerly embedded in node 400457."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400457."
    def run(self, input_text):
        return _fixed_400457(input_text, "")

def _fixed_409702(input_text, input_json=""):
    result = ""
    try:
        result=dict(path=input_text,record=json.loads(input_json))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed409702:
    """Fixed function formerly embedded in node 409702."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 409702."
    def run(self, input_text, input_json):
        return _fixed_409702(input_text, input_json)

def _fixed_760014(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        if not env['inventory']['audios'] and not s.get('raw_passthrough') and env.get('structured') and s.get('reference_scope',{}).get('reason')=='explicit_authored_shot':
            keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            prompt=s['prompt'];before=re.findall(r'<d>.*?</d>',prompt,re.S);fields={}
            for i,k in enumerate(keys):
                fields[k]=prompt.split(k+':',1)[1].split(keys[i+1]+':',1)[0].strip() if i<5 else prompt.split(k+':',1)[1].strip()
            source=env['source'].partition('detailed_description:')[2].partition('overall_soundscape:')[0]
            blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',source)[1:]
            stop=set('the and from with into through along while under above around over this that those these every all only current shot camera scene picture subject second seconds natural clear smooth gently closely softly slowly rapidly warm golden each their them then before after until of as on at to in by a an is are its it be or for no not once keep preserve'.split())
            def words(text):
                out=set()
                for w in re.findall('[a-z]+',text.lower()):
                    if len(w)<4 or w in stop:continue
                    if w.endswith('ing') and len(w)>6:w=w[:-3]
                    elif w.endswith('ed') and len(w)>5:w=w[:-2]
                    elif w.endswith(('sses','shes','ches','xes','zes')) and len(w)>5:w=w[:-2]
                    elif w.endswith('s') and len(w)>4:w=w[:-1]
                    out.add(w)
                return out
            banks=[words(b) for b in blocks];own=s['shot'];proof=[]
            if len(banks)>1 and own<len(banks):
                frequency={}
                for bank in banks:
                    for w in bank:frequency[w]=frequency.get(w,0)+1
                for key in ['overall_soundscape','non_diegetic_music']:
                    raw=env['source'].partition(key+':')[2]
                    if key=='overall_soundscape':raw=raw.partition('non_diegetic_music:')[0]
                    raw=raw.strip();prefix,found,suffix=fields[key].partition(raw) if raw else ('','','')
                    if not found:continue
                    kept=[]
                    parts=[]
                    for part in re.split(r'[.!?。！？;；,，]',raw):
                        if parts and parts[-1].split() and parts[-1].split()[-1].lower() in ['sweeping','crisp','quiet','elegant','subtle','gentle','warm','bright','soft','low','clear']:parts[-1]+=', '+part
                        else:parts.append(part)
                    for clause in parts:
                        if not clause.strip():continue
                        tokens=words(clause)
                        scores=[sum(1/frequency[w] for w in tokens.intersection(bank) if frequency[w]<len(banks)) for bank in banks]
                        top=max(scores);owners=[i for i,x in enumerate(scores) if x==top]
                        conditional=bool(set(clause.lower().split()).intersection(['as','when','while','during','after','before','once','accompanying']))
                        explicit_offscreen=any(w in clause.lower() for w in ['off-screen','offscreen','画外'])
                        if conditional and not explicit_offscreen and top>=1 and len(owners)==1 and own not in owners and scores[own]<top/2:
                            proof.append(dict(section=key,cue=clause,source_shots=[i+1 for i in owners]))
                        else:kept.append(clause)
                    fields[key]=prefix+'; '.join(kept).strip()+suffix
                fields['overall_soundscape']+='\nSound events apply only to actions actually occurring in this shot. Ambience and music cannot introduce another visual event, location, object, or cut. Preserve the exact assigned spoken words.'
                fields['non_diegetic_music']+='\nThis section controls the instrumental score only, never the visual events.'
                fields['detailed_description']=fields['detailed_description'].replace('Summary and soundtrack clocks describe the complete film timeline.','The visual action and its sound events remain local to this shot.')
                s['prompt']='\n'.join(k+':\n'+fields[k] for k in keys)
                s['sound_scope']=dict(version='authored_stage_cues_v1',removed_other_shot_cues=proof,source_shot=own+1)
                assert re.findall(r'<d>.*?</d>',s['prompt'],re.S)==before,'sound_scope_dialogue_changed'
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760014:
    """Fixed function formerly embedded in node 760014."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760014."
    def run(self, input_text, input_json):
        return _fixed_760014(input_text, input_json)

def _fixed_760015(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        if not env['inventory']['audios'] and not s.get('raw_passthrough') and env.get('structured') and (s.get('reference_scope',{}).get('reason')=='explicit_authored_shot' or s.get('shot_scope',{}).get('version')=='no_voice_current_shot_v1'):
            keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            prompt=s['prompt'];before=re.findall(r'<d>.*?</d>',prompt,re.S);fields={}
            for i,k in enumerate(keys):
                fields[k]=prompt.split(k+':',1)[1].split(keys[i+1]+':',1)[0].strip() if i<5 else prompt.split(k+':',1)[1].strip()
            retention=env['source'].partition('retention_analysis:')[2].partition('detailed_description:')[0]
            assignments={}
            for line in retention.splitlines():
                m=re.match(r'\s*<Subject\s+(\d+)>\s*\(appears\s+in\s+([^)]*)\)',line,re.I)
                if m:
                    shots={int(x) for x in re.findall(r'\bShot\s+(\d+)\b',m[2],re.I)}
                    if shots:assignments[m[1]]=shots
            own=s['shot']+1
            active=fields['summary']+'\n'+fields['detailed_description']+'\n'+fields['overall_soundscape']
            active_ids=set(re.findall(r'<Subject\s+(\d+)>',active)+re.findall(r'\bS(\d+)\b',active))
            parts=re.split(r'(?m)(?=^\s*<(?:Subject|Picture|Audio)\s+\d+>)',fields['subject_definitions'])
            definition_refs=re.findall(r'<Subject\s+(\d+)>',fields['subject_definitions'])
            kept=[];removed=[]
            for part in parts:
                m=re.match(r'\s*<Subject\s+(\d+)>',part)
                if m and m[1] in assignments and own not in assignments[m[1]]:
                    sid=m[1]
                    used=sid in active_ids or definition_refs.count(sid)>re.findall(r'<Subject\s+(\d+)>',part).count(sid)
                    if not used:
                        removed.append(dict(subject=sid,declared_shots=sorted(assignments[sid])));continue
                kept.append(part)
            if removed:
                fields['subject_definitions']=''.join(kept).strip()
                s['prompt']='\n'.join(k+':\n'+fields[k] for k in keys)
            s['subject_scope']=dict(version='explicit_subject_appearance_v1',source_shot=own,removed_inactive_definitions=removed)
            assert re.findall(r'<d>.*?</d>',s['prompt'],re.S)==before,'subject_scope_dialogue_changed'
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760015:
    """Fixed function formerly embedded in node 760015."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760015."
    def run(self, input_text, input_json):
        return _fixed_760015(input_text, input_json)

def _fixed_400451(input_text, input_json=""):
    result = ""
    try:
        # Coordinates only. Downstream TrimAudioDuration slices the original AUDIO.
        try:
            report=json.loads(input_text);row=json.loads(input_json)
            original=report['original'];total=float(original['duration_seconds'])
            if not math.isfinite(total) or total<=0 or float(original['silence_ratio'])>=1:
                raise ValueError('参考音频为空或没有可用声音，请换用清晰的单人录音。')
            interval=row.get('reference_windows',{}).get(str(row.get('voice')))
            safe_short=False
            if interval is None and total<=15:
                try:
                    head=float(original.get('leading_silence_seconds',-1))
                    tail=float(original.get('trailing_silence_seconds',-1))
                except Exception:
                    head=-1;tail=-1
                valid_edges=(math.isfinite(head) and math.isfinite(tail) and 0<=head<total and 0<=tail<total and head+tail<total)
                if valid_edges and .03<=head and .03<=tail:
                    safe_short=True
                else:
                    # Already within the model limit: preserve the complete recording.
                    # Never cut a word just to manufacture a pause.
                    head=0.0;tail=0.0;safe_short=True
            if safe_short:
                start=max(0,round(head-.15,3));excess=max(0,round(tail-.15,3))
                duration=round(total-start-excess,3)
                result={'start':start,'duration':duration}
            else:
                low=0;high=total
                if interval is not None:
                    low=float(interval[0]);high=float(interval[1])
                    if not math.isfinite(low) or not math.isfinite(high) or not 0<=low<high<=total:
                        raise ValueError('参考音频范围超出录音长度，或起止时间不正确。')
                data=row.get('reference_pause_report',{})
                if json.dumps(data)[:1]!='{' or data.get('export_format')!='json' or json.dumps(data.get('regions'))[:1]!='[':
                    raise ValueError('参考音频停顿检测无效，请重新上传清晰的单人录音。')
                regions=data['regions'];pauses=[];prefix=[0];last=0
                if data.get('total_regions')!=len(regions):raise ValueError('参考音频停顿数量无效。')
                for r in regions:
                    a=float(r['start_time']);b=float(r['end_time']);meta=r.get('metadata',{})
                    if not math.isfinite(a) or not math.isfinite(b) or not 0<=a<b<=total+.002 or a<last or b-a<.299:
                        raise ValueError('参考音频停顿范围无效。')
                    if r.get('label')!='silence' or meta.get('type')!='silence' or not abs(float(meta.get('threshold',-1))-.015)<=1e-12:
                        raise ValueError('参考音频停顿来源无效。')
                    pauses.append([a,b]);prefix.append(prefix[-1]+b-a);last=b
                best=None;best_score=None;limit=0
                for i,left in enumerate(pauses):
                    start=max(low,left[1]-.15)
                    if start>=high:break
                    if not left[0]+.04<=start<=left[1]-.04:continue
                    for k in range(limit,len(pauses)):
                        if pauses[k][0]>high or min(high,pauses[k][0]+.15)>start+15:break
                        limit=k+1
                    for j in range(limit-1,i,-1):
                        right=pauses[j]
                        end=min(high,right[0]+.15)
                        duration=end-start
                        if duration<3:break
                        if not right[0]+.04<=end<=right[1]-.04:continue
                        quiet=left[1]-start+end-right[0]+prefix[j]-prefix[i+1]
                        voiced=duration-quiet
                        if voiced<1.5:break
                        if voiced/duration<.5:continue
                        score=[int(duration>=10),round(voiced,3),-round(start,3)]
                        if best_score is None or score>best_score:
                            best_score=score;best={'start':round(start,3),'duration':round(duration,3)}
                        break
                if best is None:
                    raise ValueError('未找到两端都有自然停顿的3至15秒参考片段。请提供一句完整、说完后稍作停顿的单人录音，或调整所选参考区间；不会强行截断字音。')
                result=best
        except Exception as e:
            message='参考音频准备失败：'+str(e)
            result={'start':message,'duration':message}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400451:
    """Fixed function formerly embedded in node 400451."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400451."
    def run(self, input_text, input_json):
        return _fixed_400451(input_text, input_json)

def _fixed_760013(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s

        if not s.get('raw_passthrough') and env.get('structured'):
            source=env['source'];retention=source.partition('retention_analysis:')[2].partition('detailed_description:')[0]
            defs=source.partition('subject_definitions:')[2].partition('summary:')[0]
            assignments={}
            role_lines=retention+'\n'+defs if env['inventory']['audios'] else retention
            for line in role_lines.splitlines():
                if env['inventory']['audios'] and re.search(r'\b(?:not|never|except|excluding)\b',line,re.I):continue
                pic=re.match(r'\s*<Picture\s+(\d+)>',line)
                ids={int(n) for n in re.findall(r'\bShot\s+(\d+)\b',line,re.I)}
                if pic and ids:assignments[int(pic[1])]=ids
            voice_explicit=bool(assignments)
            detail=source.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
            openings={}
            for match in re.finditer(r'\[Shot\s+(\d+)\]([^\n]*)',detail):
                line=match[2];mark=line.lower().find('matching ')
                if mark<0:continue
                prefix=line[mark+9:].split('.',1)[0]
                for value in re.findall(r'<Picture\s+(\d+)>',prefix):
                    n=int(value);openings.setdefault(n,set()).add(int(match[1]))
            for n,shots in openings.items():
                if n not in assignments:assignments[n]=shots
            # Only explicit temporal picture roles trigger this path, never guessed identity ownership.
            own=s['shot']+1;slots=s['original_slots'];identity={b['original_slot'] for b in s.get('bindings',[]) if 'speaker_identity' in b['roles']}
            excluded=set(s.get('voice_visual_scope',{}).get('excluded_identity_slots',[]))
            direct=set()
            if env['inventory']['audios']:
                if not voice_explicit:assignments={}
            action=s['prompt'].partition('detailed_description:')[2].partition('overall_soundscape:')[0]
            used={int(n) for n in re.findall(r'<Picture\s+(\d+)>',re.sub(r'<d>.*?</d>','',action,flags=re.S))}
            direct={b['original_slot'] for b in s.get('bindings',[]) if b['local_picture'] in used}
            selected=[n for n in slots if n not in excluded and (n not in assignments or own in assignments[n] or n in identity or n in direct)]
            if assignments and selected and len(selected)<len(slots):
                old_to_new={i+1:selected.index(n)+1 for i,n in enumerate(slots) if n in selected}
                keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
                prompt=s['prompt'];before=re.findall(r'<d>.*?</d>',prompt,re.S);fields={}
                for i,k in enumerate(keys):
                    fields[k]=prompt.split(k+':',1)[1].split(keys[i+1]+':',1)[0].strip() if i<5 else prompt.split(k+':',1)[1].strip()
                for k in ['subject_definitions','retention_analysis']:
                    kept=[]
                    for line in fields[k].splitlines():
                        used={int(n) for n in re.findall(r'<Picture\s+(\d+)>',line)}
                        if used and not used<=set(old_to_new):continue
                        kept.append(line)
                    fields[k]='\n'.join(kept)
                fields['retention_analysis']+='\nOnly the current authored shot is generated here. Other shots and their reference scenes are not active in this clip. Preserve all active subject identities and the adjacent action-dialogue relationship.'
                prompt='\n'.join(k+':\n'+fields[k] for k in keys)
                def remap(m):
                    n=int(m[1]);assert n in old_to_new,'inactive_picture_in_current_action'
                    return '<Picture '+str(old_to_new[n])+'>'
                s['prompt']=re.sub(r'<Picture\s+(\d+)>',remap,prompt)
                s['reference_scope']=dict(reason='explicit_authored_shot',source_shot=own,available_slots=slots,selected_slots=selected,excluded_slots=[n for n in slots if n not in selected],label_mapping={str(k):v for k,v in old_to_new.items()})
                if s.get('crop_source') in excluded:s['crop_source']=selected[0]
                s['original_slots']=selected;s['slot_indices']=selected+[0]*(9-len(selected))
                for i,v in enumerate(s['slot_indices'],1):s['slot_'+str(i)]=v
                s['bindings']=[dict(b,local_picture=selected.index(b['original_slot'])+1) for b in s['bindings'] if b['original_slot'] in selected]
                assert re.findall(r'<d>.*?</d>',s['prompt'],re.S)==before,'scoped_dialogue_changed'
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760013:
    """Fixed function formerly embedded in node 760013."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760013."
    def run(self, input_text, input_json):
        return _fixed_760013(input_text, input_json)

def _fixed_760018(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        # A speaker heard off screen is not automatically a visible image subject.
        if not env['inventory']['audios'] and env.get('structured') and not s.get('raw_passthrough') and not s.get('guide_enabled'):
            voiced={v['source_block'] for v in s.get('native_voice_entry',{}).get('events',[])}
            units=s.get('speaker_units',[]);own=s['shot']+1;assignments={}
            source=env['source'];retention=source.partition('retention_analysis:')[2].partition('detailed_description:')[0]
            for line in retention.splitlines():
                m=re.match(r'\s*<Subject\s+(\d+)>\s*\(appears\s+in\s+([^)]*)\)',line,re.I)
                if m:assignments[m[1]]={int(n) for n in re.findall(r'\bShot\s+(\d+)\b',m[2],re.I)}
            origins={a['source_block']:a['original_action'] for a in s.get('action_provenance',[])}
            speaker_map={speaker:subject for subject,speaker in re.findall(r'<Subject\s+(\d+)>\s*\(S(\d+)\)',source.partition('summary:')[0])}
            routed=[]
            for u in units:
                tags=re.findall(r'<Subject\s+(\d+)>\s*\(S\d+\)',origins.get(u['source_block'],''))
                sid=tags[-1] if tags else speaker_map.get(u.get('subject'),u.get('subject'))
                routed.append(dict(u,subject=sid))
            units=routed
            candidates=set()
            for u in units:
                sid=u.get('subject')
                relevant=[v for v in units if v.get('subject')==sid]
                if sid in assignments and assignments[sid] and own not in assignments[sid] and all(v['source_block'] in voiced for v in relevant):candidates.add(sid)
            actions='\n'.join(a['original_action'] for a in s.get('action_provenance',[]))
            direct={int(n) for n in re.findall(r'<Picture\s+(\d+)>',actions)}
            for speaker,sid in speaker_map.items():
                if sid not in candidates:continue
                visual=actions.rsplit('<Subject '+sid+'>',1)[0]
                pieces=visual.split('S'+speaker+' ')
                if '<Subject '+sid+'>' in visual or len(pieces)>2 or (len(pieces)==2 and not pieces[1].lower().startswith(('speaks ','says ','delivers ','narrates '))):candidates.discard(sid)
            excluded=[];detached=set()
            for b in s.get('bindings',[]):
                ids=set(b.get('subject_ids',[]));slot=b['original_slot']
                if ids and ids<=candidates and b.get('roles')==['speaker_identity'] and slot not in direct:
                    excluded.append(slot);detached.update(ids)
            if excluded and any(b['original_slot'] not in excluded for b in s.get('bindings',[])):
                keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
                prompt=s['prompt'];before=re.findall(r'<d>.*?</d>',prompt,re.S);fields={}
                for i,k in enumerate(keys):fields[k]=prompt.split(k+':',1)[1].split(keys[i+1]+':',1)[0].strip() if i<5 else prompt.split(k+':',1)[1].strip()
                voices=[]
                for k in ['subject_definitions','retention_analysis']:
                    kept=[]
                    for line in fields[k].splitlines():
                        m=re.match(r'\s*<Subject\s+(\d+)>',line)
                        if m and m[1] in detached:
                            speaker=re.search(r'\(S(\d+)\)',line)
                            if k=='subject_definitions' and speaker:
                                voice='The established off-screen speaker (S'+speaker[1]+'), heard only in this shot.'
                                for sentence in re.split(r'[.;]',line):
                                    if re.search(r'\b(?:voice|vocal|timbre|pitch|accent|speaking)\b',sentence,re.I) and '<Picture' not in sentence:voice+=' '+re.sub(r'<Subject\s+\d+>','the speaker',sentence).strip()+'.'
                                voices.append(voice)
                            continue
                        kept.append(line)
                    fields[k]='\n'.join(kept)
                fields['subject_definitions']+='\n'+'\n'.join(voices)
                prompt='\n'.join(k+':\n'+fields[k] for k in keys)
                parts=re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
                def voice_tag(m):return 'the off-screen speaker' if m[1] in detached else m[0]
                s['prompt']=''.join(part if part.startswith('<d>') else re.sub(r'<Subject\s+(\d+)>',voice_tag,part) for part in parts)
                s['voice_visual_scope']=dict(version='declared_offscreen_visual_v1',excluded_identity_slots=excluded,voice_only_subjects=sorted(detached),source_shot=own)
                for key in ['identity_subjects','declared_subjects']:s[key]=[sid for sid in s.get(key,[]) if sid not in detached]
                assert re.findall(r'<d>.*?</d>',s['prompt'],re.S)==before,'voice_visual_dialogue_changed'
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760018:
    """Fixed function formerly embedded in node 760018."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760018."
    def run(self, input_text, input_json):
        return _fixed_760018(input_text, input_json)

def _fixed_760019(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        if not env['inventory']['audios'] and s.get('visual_only') and not s.get('raw_passthrough') and not s.get('speaker_units') and '<d>' not in s['prompt']:
            source=env['source']
            pieces=re.split(r'(?m)^\s*\[Shot\s+\d+\]',source.partition('detailed_description:')[2].partition('overall_soundscape:')[0])
            local=pieces[s['shot']+1] if len(pieces)>s['shot']+1 else source
            global_text=pieces[0] if len(pieces)>1 else ''
            tail=source.partition('overall_soundscape:')[2]
            intent=global_text+'\n'+local+'\n'+tail
            intent=intent.replace('Spoken dialogue is audio only.','')
            lower=intent.lower()
            no_voice=['no spoken dialogue','no dialogue','no speech','no narration','no human voice','no one speaks','characters do not speak','without dialogue','without speech','without voices','无口播','无对白','无旁白','无人声','不要人声','不要口播','不要对白','不要旁白','禁止说话','禁止人声','没有说话','只有环境音','仅保留音效']
            explicit=any(w in lower for w in no_voice) or bool(re.search(r'\b(?:no|without|exclude|excluding|never)\s+(?:(?:any|audible|intelligible|human|spoken)\s+)*(?:speech|dialogue|narration|voices?|voiceover|vocals?)\b',lower))
            vocal_words=set('sing sings singing humming hum hums chant chants chanting choir vocal vocals vocalization vocalizations narrator narration voiceover whisper whispers whispering dialogue speech speaking says laughter laugh laughs breathing scream screams cheer cheers applause'.split())
            chinese=['哼唱','唱歌','合唱','吟唱','口播','旁白','人声','说话','对白','笑声','呼吸声','尖叫','欢呼']
            negatives=set('no not without never absent exclude excluding'.split())
            requested=False
            for clause in re.split(r'[.!?。！？;；\n]',lower):
                hits=set(re.findall(r'[a-z]+',clause)).intersection(vocal_words)
                hits.update(w for w in chinese if w in clause)
                for word in hits:
                    prefix=clause[:clause.find(word)]
                    for cut in [' but ',' except ',' however ','但是','但']:
                        prefix=prefix.rsplit(cut,1)[-1]
                    tail_prefix=prefix.rsplit('，',1)[-1].rsplit(',',1)[-1]
                    affirmative=any(w in tail_prefix for w in ['保留','允许','加入','需要','要有','听到','keep ','allow ','include '])
                    tail_negated=bool(set(tail_prefix.split()).intersection(negatives)) or any(w in tail_prefix for w in ['无','不要','禁止','没有','不加','不需要'])
                    if affirmative and not tail_negated:prefix=tail_prefix
                    no=bool(set(prefix.split()).intersection(negatives)) or any(w in prefix for w in ['无','不要','禁止','没有','不加','不需要'])
                    suffix=clause[clause.find(word)+len(word):].strip()
                    if not no and suffix not in ['none','absent','is absent','are absent',': none',': n/a',': 无','：无']:
                        requested=True
            if explicit and not requested:
                keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
                prompt=s['prompt'];fields={}
                for i,k in enumerate(keys):
                    fields[k]=prompt.partition(k+':')[2].partition(keys[i+1]+':' if i<5 else '\x00')[0].strip()
                aliases=re.findall(r'<Subject\s+(\d+)>\s*\(S(\d+)\)',fields['subject_definitions'])
                # S identifiers are for actual vocal sources; these aliases only name visible objects.
                for key in ['subject_definitions','summary','retention_analysis','detailed_description']:
                    text=fields[key]
                    for subject,speaker in aliases:
                        text=text.replace('<Subject '+subject+'> (S'+speaker+')','<Subject '+subject+'>')
                        text=re.sub(r'\bS'+speaker+r'\b','<Subject '+subject+'>',text)
                    text=text.replace('Spoken dialogue is audio only.','')
                    text=text.replace('Complete the authored silent ending actions and music without adding speech.','Complete the authored physical ending actions.')
                    text=text.replace('Follow the chosen total duration, the authored actions, their exact lines and the intentional pauses.','Follow the chosen duration, authored actions and intentional pauses.')
                    fields[key]=text
                sound=fields['overall_soundscape']
                sound=sound.replace('This authored visual interval has no dialogue. Preserve requested ambience without inventing speech.','')
                sound=sound.replace('Sound events apply only to actions actually occurring in this shot. Ambience and music cannot introduce another visual event, location, object, or cut. Preserve the exact assigned spoken words.','Sound effects follow only the visible actions in this shot.')
                music=fields['non_diegetic_music'].replace('This section controls the instrumental score only, never the visual events.','').strip().rstrip('.').strip()
                absent=music.lower() in ['n/a','na','none','无','无音乐','无配乐','no music','no background music']
                if absent:fields['non_diegetic_music']='No background music.'
                else:fields['non_diegetic_music']=music+'. Instrumental arrangement only, with no singers, choir or vocal samples.'
                policy='Only the described environmental ambience and physical sound effects are audible.' if absent else 'Only the described ambience, physical effects and requested instrumental music are audible.'
                fields['overall_soundscape']=policy+' Human voices, dialogue, narration, singing and vocalizations are absent throughout this shot.\n'+sound.strip()
                fields['detailed_description']+='\nThis entire shot has no human vocal sound; its audible events are the physical sounds specified in overall_soundscape.'
                s['prompt']='\n'.join(k+':\n'+fields[k] for k in keys)
                s['audio_intent_scope']=dict(version='explicit_nonverbal_v1',speech=False,music='absent' if absent else 'authored',vocal_aliases_removed=len(aliases),physical_sound_preserved=True)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760019:
    """Fixed function formerly embedded in node 760019."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760019."
    def run(self, input_text, input_json):
        return _fixed_760019(input_text, input_json)

def _fixed_760016(input_text, input_json=""):
    result = ""
    try:
        # Compile only the no-reference-audio envelope. Existing voice normalization is passed through.
        p=json.loads(input_text);result=p
        if 'prompt' not in p and not p.get('audios'):
            def refs(text):
                def ref(m):return '<Picture '+m[2]+'>'
                return re.sub(r'@(?:参考)?(图片|图|参考图|参考图片|image)_?\s*(\d+)',ref,text,flags=re.I)
            def silent(row):return not row.get('literal_quoted') and row['text'].strip(' 。.!！').lower() in ['无','无口播','无台词','无对白','无旁白','不说话','无人声','none','n/a']
            names=list(p['definitions']);pronouns=['','他','她','它','人物','主角','这个人','这位人物']
            for row in p['rows']:
                if silent(row):continue
                actor=row['actor'];picture=re.fullmatch(r'@?(?:图片|图|image)\s*(\d+)|<Picture (\d+)>',actor,re.I)
                if picture:row['actor']='image:'+str(int(picture[1] or picture[2]))
                elif actor not in names and actor not in pronouns:names.append(actor)
            if not names and any(not silent(r) for r in p['rows']):names=['presenter']
            image_actors={r['actor'] for r in p['rows'] if r['actor'].startswith('image:')}
            if not p['definitions'] and len(image_actors)>1:
                metadata='\n'.join(p['out']).split('[Shot ',1)[0]
                same=any(x in metadata for x in ['同一人','同一个人','同一女性','同一男性','同一位','都是本人'])
                different=any(x in metadata for x in ['两个人','不同的人','不同人物','三个人','不是同','并非同','非同一'])
                assert same and not different,'multiple_image_speakers_need_roles'
            rendered=[]
            for row in p['rows']:
                if silent(row):rendered.append('No spoken dialogue. Preserve requested physical sounds and music.');continue
                name=row['actor']
                if name.startswith('image:'):
                    number=name.split(':')[1]
                    choices=[a for a in names if number in p['definitions'].get(a,{}).get('images',[])]
                    if len(choices)==1:name=choices[0]
                    elif len(names)==1:name=names[0]
                    else:raise ValueError('image_speaker_needs_declared_role')
                elif name in pronouns:
                    assert len(names)==1,'speaker_pronoun_ambiguous'
                    name=names[0]
                sid=names.index(name)+1
                prefix='<Subject '+str(sid)+'> (S'+str(sid)+') says'+(' in an off-screen voiceover' if row['voiceover'] else ' naturally')
                if row.get('named_emotion_state'):prefix+='; emotion: '+row['named_emotion_state']
                rendered.append(prefix+': <d>[Chinese]'+row['text']+'</d>\n\n')
            body=refs('\n'.join(p['out']))
            assert not re.search(r'<\s*/?\s*d\s*>',body),'reserved_dialogue_tag_in_directions'
            def speech(m):return rendered[int(m[1])]
            body=re.sub(r'<<VIP_LINE_(\d+)>>',speech,body)
            existing=list(re.finditer(r'(?m)^[ \t]*\[Shot[ \t]+\d+\]',body))
            if not p['shots'] and (not existing or '<d>' in body[:existing[0].start()]):body='[Shot 1]\n'+body
            headers=[]
            for i,name in enumerate(names,1):
                pictures=p['definitions'].get(name,{}).get('images',[])
                suffix='; identity references '+', '.join('<Picture '+str(x)+'>' for x in pictures) if pictures else '; keep the user-specified identity and reference roles'
                headers.append('<Subject '+str(i)+'>: '+name+suffix+'.')
            p['prompt']='subject_definitions:\n'+'\n'.join(headers)+'\nsummary:\nDuration: '+str(p.get('total','auto'))+'.\nretention_analysis:\nPreserve the user-specified people, scenes and material associations.\ndetailed_description:\n'+body+'\noverall_soundscape:\nFollow the physical sound requests written alongside the current shot. No unscripted speech.\nnon_diegetic_music:\nUse only the music requested by the user; do not add sung lyrics.'
            p['native_freeform_compiled']=True
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760016:
    """Fixed function formerly embedded in node 760016."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760016."
    def run(self, input_text):
        return _fixed_760016(input_text, "")

def _fixed_760017(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);result=p
        if 'prompt' in p and not p.get('native_freeform_compiled') and not any(v.strip().lower() in ['false','0'] for v in input_json.split(',')[9:12]):
            matches=re.findall(r'summary:\s*Duration:\s*([0-9.]+)',p['prompt'])
            if matches and '\nAt ' in p['prompt']:
                p['native_freeform_compiled']=True;p['source']='';p['total']=float(matches[0].rstrip('.'))
        if p.get('native_freeform_compiled'):
            source=p['source'];prompt=p['prompt'];total=p.get('total','auto')
            # Only explicit film-duration language is a global clock. Speech quotes are still opaque.
            if total=='auto':
                choices=[]
                patterns=[r'(?:总时长|总长度|视频时长|成片时长|视频长度|时长)\s*[:：为约是]?\s*(\d+(?:\.\d+)?)\s*(?:秒|s\b)',r'(\d+(?:\.\d+)?)\s*秒(?:钟)?\s*(?:的)?\s*(?:视频|短片|成片)',r'\b(\d+(?:\.\d+)?)[ -]seconds?\s+(?:video|clip|film)\b',r'\b(?:total duration|video duration|duration)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:seconds?|s)\b']
                for index,pattern in enumerate(patterns):
                    active=('时长' in source or '长度' in source) if index==0 else (('秒' in source and any(w in source for w in ['视频','短片','成片'])) if index==1 else (any(w in source.lower() for w in ['second','duration']) if index>=2 else False))
                    if active:choices.extend(float(m[1]) for m in re.finditer(pattern,source,re.I))
                if choices:total=choices[-1]
            if p.get('total','auto')=='auto':
                before,sep,body=prompt.partition('detailed_description:\n');body,sep,tail=body.partition('\noverall_soundscape:\n')
                marks=list(re.finditer(r'(?m)^\[Shot (\d+)\]',body));parts=[];weights=[]
                global_context=body[:marks[0].start()].strip() if marks else ''
                for i,m in enumerate(marks):
                    chunk=body[m.end():marks[i+1].start() if i+1<len(marks) else len(body)].strip()
                    spoken=re.findall(r'<d>\[[^\]]+\](.*?)</d>',chunk,re.S)
                    if spoken:
                        text=''.join(spoken);cjk=sum('\u3400'<=c<='\u9fff' or c.isdigit() for c in text);latin=sum(any('a'<=c.lower()<='z' for c in word) for word in text.split());weight=max(0.5,cjk/5+latin/2.5)
                    else:weight=15.0 if len(marks)==1 else 5.0
                    parts.append(chunk);weights.append(weight)
                if total=='auto':total=max(4.0,min(sum(weights),60.0-len(parts)*17.0/24))
                assert 0<float(total)<=120,'native_freeform_source_clock_outside120'
                clock=0.0;rendered=[]
                for i,(chunk,weight) in enumerate(zip(parts,weights)):
                    end=clock+float(total)*weight/sum(weights)
                    rendered.append('[Shot '+str(i+1)+'] From '+str(round(clock,4))+' to '+str(round(end,4))+' seconds,\n'+chunk)
                    clock=end
                before=re.sub(r'(?m)^Duration: auto\.$','Duration: '+str(total)+'.',before)
                p['prompt']=before+'detailed_description:\n'+(global_context+'\n' if global_context else '')+'\n\n'.join(rendered)+'\noverall_soundscape:\n'+tail
            p['native_freeform_clock']=dict(source='explicit_prompt_or_coarse_native_estimate',seconds=total,voice_reference=False)

        if p.get('native_freeform_compiled') and p.get('total','auto')!='auto':
            prompt=p['prompt'];marks=list(re.finditer(r'(?m)^\[Shot (\d+)\]\nAt (\d+):([\d.]+)\n',prompt))
            starts=[float(m[2])*60+float(m[3]) for m in marks]+[float(p['total'])]
            for j in range(len(marks)-1,-1,-1):
                m=marks[j];replacement='[Shot '+m[1]+'] From '+str(starts[j])+' to '+str(starts[j+1])+' seconds,\n'
                prompt=prompt[:m.start()]+replacement+prompt[m.end():]
            p['prompt']=prompt
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760017:
    """Fixed function formerly embedded in node 760017."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760017."
    def run(self, input_text, input_json):
        return _fixed_760017(input_text, input_json)

def _fixed_400447(input_text, input_json=""):
    result = ""
    try:
        if not input_text.startswith('{'):
            result=input_text
        else:
            def bind(p):
                if 'prompt' in p:
                    outside=re.sub(r'<d>.*?</d>','',p['prompt'],flags=re.S)
                    return p
                definitions=p['definitions']
                def refs(s):
                    def ref(m):
                        kind='Picture' if m.group(1).lower() in '图片|图|参考图|参考图片|image'.split('|') else 'Audio'
                        return f'<{kind} {m.group(2)}>'
                    return re.sub(r'@(?:参考)?(图片|图|参考图|参考图片|image|音频|音色|audio)_?\s*(\d+)',ref,s,flags=re.I)
                def roles(s):
                    s=refs(s);found={}
                    for m in re.finditer(r'(?:(音色|声音|声线|voice|情绪|语气|emotion)\s*(?:参考|来自|使用|用|为|from|reference)?\s*[:：=]?\s*)?<Audio (\d+)>',s,re.I):
                        lead=s[:m.start()].replace('，',',').replace('；',';').replace('。',';')
                        lead=re.split(r'[,;\n]',lead)[-1]
                        if lead and re.search(r'禁止|不要|不能|请勿|别|不使用|not|never|avoid',lead,re.I):raise ValueError('音频关联处含否定要求，请明确实际使用哪一段音频。')
                        kind='emotion' if (m[1] or '').lower() in '情绪|语气|emotion'.split('|') else 'voice'
                        if re.match(r'(?:但)?(?:不允许|不[要能准可]?|禁止|别|勿|请勿)(?:再)?(?:使用|采用|用)',s[m.end():].lstrip(' ，,；;（( ')):raise ValueError('音频关联后含否定要求，请明确实际音频。')
                        number=int(m.group(2))
                        if kind in found and found[kind]!=number:raise ValueError('同一处声音关联冲突，请明确音频用途。')
                        found[kind]=number
                    return found
                for name,desc in definitions.items():
                    info=roles(desc)
                    info['images']=re.findall(r'<Picture (\d+)>',refs(desc));definitions[name]=info
                global_voice=None;global_emotion=None;global_lines=[]
                directions=refs('\n'.join(p['out']))
                p['emotion_disabled']=p.get('named_roles_active') or any(w in directions.lower() for w in ['不使用情绪参考','不用情绪参考','不要情绪参考','关闭情绪参考','禁用情绪参考','do not use emotion reference','no emotion reference','without emotion reference'])
                header='\n'.join(p['out']).split('[Shot ',1)[0].split('<<VIP_LINE_',1)[0]
                candidates=header.splitlines() if any(x in header for x in ['全片','全程','整个视频','所有镜头','所有分镜']) else []
                for line in candidates:
                    if not any(x in line for x in ['全片','全程','整个视频','所有镜头','所有分镜']):continue
                    if not any(x in line for x in ['口播','声音','音色','声线','配音','情绪','语气']):continue
                    if not any(x in line for x in ['参考','使用','采用','关联','来自','用']):continue
                    info=roles(line)
                    if not info:continue
                    if 'voice' in info:
                        voice=info['voice']
                        if global_voice is not None and global_voice!=voice:raise ValueError('全片音色关联冲突，请明确一段音频。')
                        global_voice=voice
                    if 'emotion' in info:
                        emotion=info['emotion']
                        if global_emotion is not None and global_emotion!=emotion:raise ValueError('全片情绪关联冲突，请明确一段音频。')
                        global_emotion=emotion
                    global_lines.append(line)
                p['global_voice']=global_voice;p['global_emotion']=global_emotion
                for row in p['rows']:
                    context=row['audio_context']
                    if global_lines or '素材' in context:
                        context='\n'.join(line for line in context.splitlines() if line not in global_lines and not line.strip().startswith(('素材：','素材:','素材说明：','素材说明:')))
                    row['audio_roles']=roles(context)
                    for name in sorted(definitions,key=len,reverse=True):
                        if not row['actor'].startswith(name):continue
                        suffix=refs(row['actor'][len(name):].strip())
                        if re.fullmatch(r'(?:用|使用)\s*<Audio [1-9]>',suffix):
                            row['actor']=name;row['audio_roles'].update(roles(suffix));break
                return p
            result=bind(json.loads(input_text))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400447:
    """Fixed function formerly embedded in node 400447."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400447."
    def run(self, input_text):
        return _fixed_400447(input_text, "")

def _fixed_760021(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        # Scope only a proved, exclusive global identity-attribute block. Never edit the authored shot.
        scope=s.get('voice_visual_scope',{});excluded=scope.get('excluded_identity_slots',[])
        if env.get('structured') and not env['inventory']['audios'] and not s.get('raw_passthrough') and len(excluded)==1 and scope.get('source_shot')==s['shot']+1:
            identity=[b for b in s.get('bindings',[]) if 'speaker_identity' in b['roles']]
            if identity and all(b['original_slot']==excluded[0] and b['roles']==['speaker_identity'] and set(b['subject_ids'])<=set(scope['voice_only_subjects']) for b in identity):
                source=env['source'];detail=source.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
                boundary=re.search(r'(?m)^\s*\[Shot\s+\d+\]',detail)
                original=detail[:boundary.start()].strip() if boundary else ''
                refs={int(n) for n in re.findall(r'<Picture\s+(\d+)>',original)}
                speakers={speaker for subject,speaker in re.findall(r'<Subject\s+(\d+)>\s*\(S(\d+)\)',source.partition('summary:')[0]) if subject in scope['voice_only_subjects']}
                if original and refs==set(excluded) and set(re.findall(r'\bS(\d+)\b',original))<=speakers and not any(q in original for q in ['"',"'",'“','”','‘','’','<d>']):
                    allowed=set('keep preserve maintain the a an same person consistent identity throughout all shots shot beats beat and continuous movement established facial features proportions age appearance skin tone body hairstyle hair color colour glasses clothing clothes wardrobe accessories with supplied reference matching of unchanged'.split())
                    spans=list(re.finditer(r'[^.!?\n]+(?:[.!?]|$)',original))
                    def pure(m):
                        text=re.sub(r'<Picture\s+\d+>','',m[0]).strip()
                        text=re.sub(r'\bS\d+\b','',text)
                        if re.search(r'[^A-Za-z\s,.;:!?()\-]',text):return False
                        words=re.findall(r'[a-z]+',text.lower())
                        return bool(words and words[0] in ['keep','preserve','maintain'] and set(words)<=allowed and set(words).intersection({'person','identity','facial','hairstyle','hair','clothing','wardrobe','accessories'}))
                    anchors=[i for i,m in enumerate(spans) if '<Picture' in m[0] and pure(m)]
                    if len(anchors)==1:
                        last=anchors[0];first=last
                        for index in range(last-1,-1,-1):
                            if not pure(spans[index]):break
                            first=index
                        cuts=spans[first:last+1];a=cuts[0].start();b=cuts[-1].end()
                        projected=original[:a]+original[b:]
                        mapping={n:i+1 for i,n in enumerate(s['original_slots'])}
                        def label(m):return '<Picture '+str(mapping[int(m[1])])+'>'
                        def mapped(text):return re.sub(r'<Picture\s+(\d+)>',label,text)
                        old=mapped(original);new=mapped(projected)
                        head,sep,body=s['prompt'].partition('detailed_description:')
                        current,sep2,tail=body.partition('overall_soundscape:')
                        start=re.search(r'(?m)^\s*\[Shot\s+\d+\]',current)
                        if start and current[:start.start()].count(old)==1:
                            current=current[:start.start()].replace(old,new,1)+current[start.start():]
                            out=head+sep+current+sep2+tail
                            assert re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',s['prompt'],re.S),'global_identity_dialogue_changed'
                            s['prompt']=out
                            s['global_identity_scope']=dict(version='exclusive_offscreen_global_attributes_v1',source_shot=scope['source_shot'],excluded_identity_slots=excluded,source_clauses=[m[0].strip() for m in cuts],source_global=original,source_span=[a,b])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed760021:
    """Fixed function formerly embedded in node 760021."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 760021."
    def run(self, input_text, input_json):
        return _fixed_760021(input_text, input_json)

def _fixed_400444(input_text, input_json=""):
    result = ""
    try:
        # Work on metadata only: quoted strings are opaque tokens from443.
        def adapt(p):
            source=p['source']
            if '<d>' not in source:source=re.sub(r'(?m)^\s*\[Shot\s+(\d+)\]\s*$',r'镜头\1',source)
            p['source']=source
            if '<<VIP_LINE_' in p['raw']:raise ValueError('原提示包含工作流保留控制标记，请移除该标记；不会当作口播执行。')
            if 'detailed_description:' in source:return p
            out=[];total=0;shots=0;fixed=False
            fields='口播文案|口播内容|配音文案|旁白内容|对白内容|解说词|文案|口播|台词|对白|旁白'.split('|')
            names=re.findall(r'^(?:人物|角色)[:：]\s*([^，, \n]+)',source,re.M) if '人物' in source or '角色' in source else []
            names=sorted(names,key=len,reverse=True)
            for original in source.splitlines():
                if original.isalpha() or not re.search(r'[:：\d#*【]',original):out.append(original);continue
                line=original.lstrip('#-* ')
                if '**' in original:line=re.sub(r'\*\*([^*]+)\*\*',r'\1',original).lstrip('#-* ')
                if line.startswith('【'):line=re.sub(r'^【([^】]+)】\s*[:：]?',r'\1：',line)
                if line.startswith(('不要','禁止','不能','别','请勿','错误示例','反例','例子','例如','假如','如果','招牌','标牌','字幕','标题')):out.append(line);continue
                clock=re.match(r'^\s*\[?([\d:.]+)[ s秒]*[-–—~～至]\s*([\d:.]+) *(s|秒)?\]?[ |｜:：]*(.*)$',line) if line[:1] in '0123456789[' and line else None
                if clock:
                    a,b,unit,line=clock.groups()
                    if not unit and ':' not in a:raise ValueError('时间范围缺少单位，请明确秒或分:秒；不会猜测时长。')
                    def seconds(v):
                        t=v.split(':');return float(t[-1])+(60*int(t[0]) if len(t)>1 else 0)
                    start=seconds(a);end=seconds(b)
                    if start!=total or end<=start:raise ValueError('分镜时间段须从0连续，不重叠；不能猜测空白时段。')
                    if end>120:raise ValueError('分镜总时长不能超过120秒。')
                    total=end;fixed=True;shots+=1
                    out.extend(['镜头'+str(shots),'At '+str(int(start//60))+':'+('%06.3f'%(start%60))])
                direct=re.split('[:：]',line,1)[0].strip().removesuffix('如下') in fields
                matches=[] if direct else [m for m in re.finditer(r'[,，;；|｜]\s*(\w+)\s*[:：]',line) if m.group(1) in fields]
                m=matches[0] if matches else None
                if not m:out.append(line);continue
                prefix=line[:m.start()];value=line[m.end():].lstrip()
                if any(x in prefix for x in ['不要说','不能说','别说','禁止说','错误示例','反例']):raise ValueError('口播字段位于否定或示例说明中，请明确实际台词。')
                heading=re.match(r'^\s*(?:镜头|分镜|场景)\s*(\d+)\s*[:：]\s*(.*)$',prefix) if prefix.startswith(('镜头','分镜','场景')) else None
                if heading:out.append('镜头'+heading.group(1));prefix=heading.group(2)
                actor=''
                for name in names:
                    if prefix.startswith(name):actor=name;break
                if actor and re.match(r'\s*(?:和|与|及|跟|、)',prefix[len(actor):]):raise ValueError('同一镜头有多个说话候选，请明确这句由谁说。')
                if actor and prefix!=actor and not prefix[len(actor):].startswith(tuple('@| |，|,|：|:|把|坐|站|看|说|讲|念|低头|抬|微笑|笑|端|指|拿|从|面|转|伸|点|走|挥|靠|手|双|撕|掰|打开|开心|侧|蹲|喝|轻|一|慢|正|对|向|在|放|盯|咬'.split('|'))):raise ValueError('人物名边界不明确，请用完整姓名单独标注谁说这句。')
                if not actor:
                    pic=re.match(r'@?(?:图片|图)\s*(\d+)',prefix)
                    if pic:actor='图片'+pic.group(1)
                out.append('画面描述：'+prefix)
                suffix=None if value.startswith(p['quote_prefix']) or not (':' in value or '：' in value) else re.search(r'([,，;；|｜])\s*(?:运镜|画面|动作|音效|环境气氛|演员表情)[^:：]*[:：]',value)
                if suffix and suffix.group(1) not in '|｜':raise ValueError('同排台词和画面说明边界不明确，请换行或给台词加引号。')
                out.append((actor+'说' if actor else m.group(1))+'：'+(value[:suffix.start()].rstrip() if suffix else value))
                if suffix:out.append('画面描述：'+value[suffix.start():])
            p['source']='\n'.join(out);p['total']=total if fixed else 'auto'
            return p
        result=adapt(json.loads(input_text)) if input_text.startswith('{') else input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400444:
    """Fixed function formerly embedded in node 400444."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400444."
    def run(self, input_text):
        return _fixed_400444(input_text, "")

def _fixed_400289(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_json);d,state=input_text.split('\n',1)
        duration=float(d);q=json.loads(state)
        assert math.isfinite(duration) and duration>0, 'invalid_measured_clock'
        assert q['queue'] and q['queue'][0]['text']==r['text'], 'clock_queue_mismatch'
        head=float(r['edge_head']);tail=float(r['edge_tail'])
        assert 0<=head<=duration and 0<=tail<=duration, 'invalid_speech_edges'
        before=float(r.get('pause_before',0));after=float(r.get('pause_after',0))
        assert all(math.isfinite(x) and x>=0 for x in [before,after]), 'invalid_silent_hold'
        seconds=duration+before+after
        q['attempts']+=1
        assert q['attempts']<=256, 'clock_queue_progress_limit'
        if seconds>719/24:
            assert max(before,after)<719/24, 'authored_single_pause_requires_separate_visual_window'
            text=r['text'];tokens=re.findall(r'''[A-Za-z0-9]+|\s+|[。！？!?][”’"')）]*|[\s\S]''',text)
            positions=[];punct=[];sentences=[];cursor=0
            for token in tokens[:-1]:
                cursor+=len(token)
                if text[:cursor].strip() and text[cursor:].strip():
                    positions.append(cursor)
                    if token in '。！？；.!?;,，':punct.append(cursor)
                    if token[:1] in '。！？!?':sentences.append(cursor)
                    if token=='.' and text[cursor:cursor+1].isspace() and not (cursor>1 and text[cursor-2].isdigit()):sentences.append(cursor)
            assert positions, 'unsplittable_spoken_token_over30'
            middle=len(text)/2
            candidates=[i for i in punct if len(text)*0.25<=i<=len(text)*0.75] or positions
            def distance(i):return abs(i-middle)
            cut=min(candidates,key=distance)
            bounds=[0]+sentences+[len(text)] if sentences else [0,cut,len(text)]
            chunks=[text[x:y] for x,y in zip(bounds,bounds[1:])]
            parts=[]
            for j,chunk in enumerate(chunks):
                row=dict(q['queue'][0]);row['text']=chunk
                row['raw_dialogue']='<d>['+row['language']+']'+chunk+'</d>'
                row['original_source_block']=row.get('original_source_block',row['source_block'])
                row['original_full_text']=row.get('original_full_text',text)
                row['pause_before']=before if j==0 else 0.0
                row['pause_after']=after if j==len(chunks)-1 else 0.0
                row['measured_sentence_window']=True
                if j:
                    row['source_action']=row.get('source_action',row['action'])
                    row['action']='Continue the same scene and ongoing physical action from the preceding interval without repeating the introduction. The same <Subject '+row['subject']+'> (S'+row['subject']+') continues speaking at the same natural reference-voice pace: '
                parts.append(row)
            assert ''.join(x['text'] for x in parts)==text, 'dialogue_split_changed_words'
            q['queue']=parts+q['queue'][1:];q['splits']+=len(parts)-1
        else:
            index=len(q['timeline']);accepted=q['queue'].pop(0)
            q['accepted'].append(accepted)
            q['timeline'].append(dict(source_block=index,shot=r['shot'],subject=r['subject'],voice=r['voice'],text=r['text'],audio_seconds=duration,edge_head=head,edge_tail=tail,pause_before=before,pause_after=after,gap=0.0,seconds=seconds))
            assert sum(x['seconds'] for x in q['timeline'])<=120, 'total_over120'
        result=dict(clock_queue=json.dumps(q,ensure_ascii=False),pending=bool(q['queue']))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed400289:
    """Fixed function formerly embedded in node 400289."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 400289."
    def run(self, input_text, input_json):
        return _fixed_400289(input_text, input_json)

def _fixed_1410(input_text, input_json=""):
    result = ""
    try:
        parts = input_json.split('|')
        if len(parts) != 4:
            raise ValueError('reference_inventory_shape')
        sizes = [9, 3, 3]
        families = ['Picture', 'Audio', 'Video']
        names = {'Picture': '图片', 'Audio': '音频/音色', 'Video': '视频'}
        maps = {}
        for family, size, raw in zip(families, sizes, parts[:3]):
            flags = raw.split(',')
            if len(flags) != size or any(flag not in ['True', 'False'] for flag in flags):
                raise ValueError('reference_inventory_values')
            present = [index + 1 for index, flag in enumerate(flags) if flag == 'False']
            maps[family] = {slot: index + 1 for index, slot in enumerate(present)}

        duration = float(parts[3])
        if not math.isfinite(duration) or not 4 <= duration <= 15:
            raise ValueError('duration_must_be_4_to_15_seconds')
        source = input_text
        if not source.strip() or len(source) > 24000:
            raise ValueError('prompt_empty_or_over_24000_characters')

        # This is a reference mapper, not a prompt planner. It only rewrites explicit
        # material tokens outside <d> exact-dialogue blocks; it never adds prose.
        aliases = {
            'Picture': ['<Picture {n}>', '@图片{n}', '@图片 {n}', '@参考图片{n}', '@参考图{n}', '@图{n}'],
            'Audio': ['<Audio {n}>', '@音频{n}', '@音频 {n}', '@音色{n}', '@音色 {n}', '@参考音频{n}', '@参考音色{n}'],
            'Video': ['<Video {n}>', '@视频{n}', '@视频 {n}', '@参考视频{n}']
        }
        markers = {
            'Picture': ['@图片', '@参考图片', '@参考图', '@图'],
            'Audio': ['@音频', '@音色', '@参考音频', '@参考音色'],
            'Video': ['@视频', '@参考视频']
        }

        def remap(text):
            for family, size in zip(families, sizes):
                for marker in markers[family] + ['<%s ' % family]:
                    for fragment in text.split(marker)[1:]:
                        digits = ''
                        for character in fragment:
                            if character in '0123456789':
                                digits += character
                            else:
                                break
                        if digits and (int(digits) < 1 or int(digits) > size):
                            raise ValueError('reference_number_out_of_range')
            for family, size in zip(families, sizes):
                for slot in range(1, size + 1):
                    found = False
                    for template in aliases[family]:
                        token = template.format(n=slot)
                        if token in text:
                            found = True
                    if not found:
                        continue
                    native = maps[family].get(slot)
                    if native is None:
                        raise ValueError('引用的%s%s未上传' % (names[family], slot))
                    for template in aliases[family]:
                        text = text.replace(template.format(n=slot), '<%s %s>' % (family, native))
            return text

        # Preserve structured dialogue blocks exactly. A literal tag-shaped word in
        # policy prose is ordinary text, so it cannot invalidate reference mapping.
        segments = source.split('<d>')
        result = remap(segments[0])
        for segment in segments[1:]:
            if not segment.lstrip().startswith('['):
                result += remap('<d>' + segment)
                continue
            if segment.count('</d>') != 1:
                raise ValueError('dialogue_tag_boundaries')
            spoken, tail = segment.split('</d>', 1)
            result += '<d>' + spoken + '</d>' + remap(tail)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed1410:
    """Fixed function formerly embedded in node 1410."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 1410."
    def run(self, input_text, input_json):
        return _fixed_1410(input_text, input_json)

def _fixed_730023(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text)
        assert s['decoded_count']>0
        result=dict(last_index=s['decoded_count']-1)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed730023:
    """Fixed function formerly embedded in node 730023."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 730023."
    def run(self, input_text):
        return _fixed_730023(input_text, "")

def _fixed_500104(input_text, input_json=""):
    result = ""
    try:
        e=json.loads(input_text)
        result=dict(inventory=dict(images=e['inventory']['images']),caption_policy=e['caption_policy'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500104:
    """Fixed function formerly embedded in node 500104."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500104."
    def run(self, input_text):
        return _fixed_500104(input_text, "")

def _fixed_500108(input_text, input_json=""):
    result = ""
    try:
        boxes=json.loads(input_text)
        assert boxes==list(boxes) and len(boxes)==1 and boxes[0]==list(boxes[0]), 'invalid_face_detection'
        for box in boxes[0]:
            assert box==list(box) and len(box)==4, 'invalid_face_detection'
            x1,y1,x2,y2=[float(v) for v in box]
            assert all(math.isfinite(v) for v in [x1,y1,x2,y2]) and 0<=x1<x2 and 0<=y1<y2, 'invalid_face_detection'
        result=dict(single=len(boxes[0])==1,count=len(boxes[0]))

        policy=json.loads(input_json)
        areas=sorted([(v[2]-v[0])*(v[3]-v[1]) for v in boxes[0]],reverse=True)
        ratio=areas[0]/areas[1] if len(areas)>1 and areas[1]>0 else 0
        allowed=bool(policy.get('request') and policy.get('dominant_allowed') and len(areas)>1 and ratio>=16)
        result['single']=bool(len(areas)==1 or allowed)
        result['dominant_used']=allowed
        result['dominance_ratio']=ratio
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500108:
    """Fixed function formerly embedded in node 500108."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500108."
    def run(self, input_text, input_json):
        return _fixed_500108(input_text, input_json)

def _fixed_500100(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json)
        proof=s.get('reference_scope',{})
        scoped=proof.get('reason') in ['explicit_empty_scene','explicit_authored_shot'] and proof.get('selected_slots')==s['original_slots'] and sorted(proof.get('available_slots',[]))==e['inventory']['images'] and set(s['original_slots'])<=set(proof['available_slots'])
        scoped=scoped or s.get('ds_guard_verdict_v1') is True
        assert sorted(s['original_slots'])==e['inventory']['images'] or scoped, 'original_reference_dropped'
        request=bool(s.get('crop_source') and len(e['inventory']['images'])<9 and len(s.get('identity_subjects',[]))==1)
        result=dict(request=request,source=s['crop_source'] if request else 0)
        header=s.get('source_metadata',{}).get('header','').partition('summary:')[0]
        source_label='<Picture '+str(s.get('crop_source',0))+'>'
        source_lines=[line for line in header.splitlines() if line.strip().startswith(source_label+':')]
        identity_lines=[line for line in header.splitlines() if line.strip().startswith('<Subject '+str(s.get('identity_subjects',[''])[0] if s.get('identity_subjects') else '')+'>')]
        explicit=any(re.search(r'(?i)\b(?:sole|only|primary)\s+(?:identity|facial|face)\b|唯一.{0,4}(?:身份|人脸)|主要.{0,3}身份',line) for line in source_lines)
        spatial=any(re.search(r'(?i)\b(?:background person|leftmost|rightmost|smaller person|second person|rear person)\b|后排|第二个人|背景人物',line) for line in identity_lines)
        result['dominant_allowed']=bool(request and explicit and not spatial and len(s.get('declared_subjects',[]))==1)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed500100:
    """Fixed function formerly embedded in node 500100."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 500100."
    def run(self, input_text, input_json):
        return _fixed_500100(input_text, input_json)

def _fixed_799281(input_text, input_json=""):
    result = ""
    try:
        segment = json.loads(input_text)
        parts = input_json.split('|', 3)
        assert len(parts) == 4, 'invalid_seed_policy_context'
        width = int(parts[0])
        height = int(parts[1])
        voice = parts[2].strip().lower()
        assert voice in ('true', 'false', '1', '0'), 'invalid_voice_mode'
        with_voice = voice in ('true', '1')
        no_captions = parts[3].strip() == '无字幕'
        frames = segment.get('model_frames', 0)
        encoded_frames = json.dumps(frames)
        known_window = encoded_frames.isdigit() and 0 < int(encoded_frames) <= 360
        known_shape = width == 736 and height == 1280
        # The release builder pins the complete model, LoRA, sampler and 24 fps profile.
        # These are observed candidates, never a universal no-subtitle guarantee.
        matched = no_captions and known_shape and known_window and not segment.get('raw_passthrough', False)
        result = {
            'apply_observed_policy': matched,
            'selected_value': 1774 if with_voice else 999,
            'basis': 'observed_native_timbre' if with_voice else 'observed_native_no_timbre',
            'matched_conditions': matched,
            'guaranteed_subtitle_free': False,
        }
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed799281:
    """Fixed function formerly embedded in node 799281."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 799281."
    def run(self, input_text, input_json):
        return _fixed_799281(input_text, input_json)

def _fixed_798201(input_text, input_json=""):
    result = ""
    try:
        def stage(prompt, segment):

            def unchanged(reason):
                return (prompt, {'applied': False, 'reason': reason})
            if segment.get('raw_passthrough') or segment.get('visual_only'):
                return unchanged('raw_or_visual_only')
            ids = segment.get('identity_subjects', [])
            if len(ids) != 1 or segment.get('declared_subjects') != ids:
                return unchanged('not_one_declared_identity')
            sid = str(ids[0])
            if segment.get('subject_roles', {}).get(sid) != 'person':
                return unchanged('not_person')
            units = segment.get('speaker_units', [])
            if not units or any((str(u.get('subject')) != sid for u in units)):
                return unchanged('speaker_not_same_identity')
            voices = {u.get('voice') for u in units}
            if len(voices) != 1 or not all((re.fullmatch('[1-9][0-9]*', json.dumps(v)) for v in voices)):
                return unchanged('ambiguous_speaker_id')
            voice = list(voices)[0]
            alias = 'S' + str(voice)
            provenance = segment.get('action_provenance', [])
            if len(provenance) != 1 or len(segment.get('source_blocks', [])) != 1:
                return unchanged('not_one_action_interval')
            action = provenance[0]['reference_mapped_action']
            masked = re.sub('<d>.*?</d>', '', action, flags=re.S)
            if not re.search('\\boff[- ]screen\\s+voice[- ]?over\\b', masked, re.I):
                return unchanged('no_explicit_offscreen_voiceover')
            visible_person = '\\b(?:face|facial|head|torso|shoulders?|lips|portrait|selfie|glasses|medium shot|wide shot|full[- ]body|over[- ]the[- ]shoulder|eye contact|on[- ]camera|mirror|reflection)\\b'
            if re.search(visible_person, masked, re.I):
                return unchanged('visible_person_or_ambiguous_composition')
            return ([sid, voice, alias, masked], {'applied': True})
        plan = json.loads(input_text)
        result = input_text
        if plan['mode'] == 'with_voice' and plan['count'] > 1:
            for s in plan['segments']:
                if '_hand_visibility_pending_v2' in s:
                    raise ValueError('VISIBILITY_INTERNAL_FIELD_COLLISION')
                context, audit = stage(s['prompt'], s)
                if audit['applied']:
                    s['_hand_visibility_pending_v2'] = context
            result = plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed798201:
    """Fixed function formerly embedded in node 798201."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 798201."
    def run(self, input_text):
        return _fixed_798201(input_text, "")

def _fixed_798204(input_text, input_json=""):
    result = ""
    try:
        def stage(prompt, context):
            H3_FIELDS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music')
            IDENTITY_CONTINUITY = ' Preserve the same person, facial proportions, age, hair, clothing and accessories. Compare all references assigned to each identity together. Scene references supply scenery only. Maintain continuous motion within each authored take.'
            GLOBAL_IDENTITY = 'Maintain the same person and a consistent identity throughout all shots, beats, and continuous movement.'
            MOUTH_INSTRUCTION = 'Generate synchronized native voice and mouth motion using the same speaker identity and natural delivery as the uploaded voice reference.'

            def unchanged(reason):
                return (prompt, {'applied': False, 'reason': reason})
            sid, voice, alias, picture, subject, picture_token, fields, definitions, person_lines, identity_lines, audios, part, composition, last_section_start, profile, prefix = context
            definitions[person_lines[0]] = prefix + subject + ' (' + alias + '): The owner of the ' + part + ' visible in this close-up. ' + picture_token + ' supplies the visible hand characteristics and skin tone. ' + audios[0] + " supplies the same speaker's vocal timbre."
            if identity_lines:
                definitions[identity_lines[0]] = 'Identity source for ' + subject + ': ' + picture_token + ' contributes the visible hand characteristics in this authored composition.'
            fields['subject_definitions'] = '\n'.join(definitions) + '\n'
            retention = fields['retention_analysis']
            entry = re.compile('<Subject (\\d+)>\\s*\\(identity and clothing from <Picture (\\d+)>\\):\\s*fully_preserved\\s*-\\s*[^\\n]*?(?=\\s+<(?:Audio|Subject|Picture|Video) \\d+>(?:\\s*\\([^)]*\\))?\\s*:|\\n|$)')
            replacement = subject + ' (visible ' + part + ' in this shot): partially_preserved - The hand details and skin tone follow ' + picture_token + ' within the authored close-up.'

            entries = [m for m in entry.finditer(retention) if m[1] == sid and m[2] == picture]
            count = len(entries)
            if count == 1:
                entry_match = entries[0]
                retention = retention[:entry_match.start()] + replacement + retention[entry_match.end():]
            if count != (1 if profile == 'canonical' else 0) or IDENTITY_CONTINUITY not in retention:
                return unchanged('unrecognized_retention_template')
            fields['retention_analysis'] = retention.replace(IDENTITY_CONTINUITY, ' Keep the visible hand characteristics and the authored close-up composition consistent through the complete shot.', 1)
            detail = fields['detailed_description']
            before, shot_marker, after = detail.partition('[Shot 1]')
            if not shot_marker or detail.count('[Shot 1]') != 1:
                return unchanged('not_one_local_shot')
            identity_sentence = 'Preserve the established facial features, facial proportions, age appearance, skin tone, body proportions, hairstyle, hair color, glasses, clothing, and accessories matching ' + picture_token + '.'
            if profile == 'canonical':
                count = before.count(identity_sentence)
                before = before.replace(identity_sentence, '')
                if count != 1 or before.count(GLOBAL_IDENTITY) != 1:
                    return unchanged('unrecognized_global_appearance_template')
                before = before.replace(GLOBAL_IDENTITY, '', 1)
            else:
                authored_identity = 'The character maintains consistent facial features, skin texture, and attire according to ' + picture_token + '.'
                if before.count(authored_identity) != 1 or identity_sentence in before or GLOBAL_IDENTITY in before:
                    return unchanged('unrecognized_authored_appearance_template')
                before = before.replace(authored_identity, '', 1)
            composition_rule = 'The complete shot stays within the authored ' + composition.rstrip() + '. The ' + part + ' and the objects described in this close-up occupy the frame throughout.'
            fields['detailed_description'] = before + composition_rule + '\n[Shot 1]' + after
            sound = fields['overall_soundscape']
            if sound.count(MOUTH_INSTRUCTION) != 1:
                return unchanged('unrecognized_native_voice_template')
            fields['overall_soundscape'] = sound.replace(MOUTH_INSTRUCTION, 'Generate the specified off-screen voiceover using the same speaker identity and natural delivery as the uploaded voice reference.', 1)
            output = ''.join((k + ':\n' + fields[k] for k in H3_FIELDS))
            assert fields['detailed_description'].partition('[Shot 1]')[2] == after, 'VISIBILITY_AUTHORED_ACTION_CHANGED'
            assert re.findall('<d>.*?</d>', output, re.S) == re.findall('<d>.*?</d>', prompt, re.S), 'VISIBILITY_DIALOGUE_CHANGED'

            def refs(text):
                return set(re.findall('<(?:Picture|Audio|Video) \\d+>', text))
            assert refs(output) == refs(prompt), 'VISIBILITY_REFERENCE_LABEL_CHANGED'
            assert fields['non_diegetic_music'] == prompt[last_section_start:], 'VISIBILITY_MUSIC_CHANGED'
            return (output, {'applied': True, 'version': 'HAND_VISIBILITY_SCOPE_CANDIDATE_V1', 'subject': sid, 'speaker': voice, 'visiblePart': part, 'identityPicture': int(picture), 'referencesDropped': False, 'sourceActionChanged': False, 'userAcceptance': False, 'cloudVerified': False})
        plan = json.loads(input_text)
        result = input_text
        if plan['mode'] == 'with_voice' and plan['count'] > 1:
            for s in plan['segments']:
                if '_hand_visibility_pending_v2' in s:
                    context = s.pop('_hand_visibility_pending_v2')
                    prompt, audit = stage(s['prompt'], context)
                    if audit['applied']:
                        s['prompt'] = prompt
                        s['hand_visibility_scope'] = audit
            result = plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed798204:
    """Fixed function formerly embedded in node 798204."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 798204."
    def run(self, input_text):
        return _fixed_798204(input_text, "")

def _fixed_798203(input_text, input_json=""):
    result = ""
    try:
        def stage(prompt, segment, context):

            def unchanged(reason):
                return (prompt, {'applied': False, 'reason': reason})
            H3_FIELDS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music')
            sid, voice, alias, part, composition = context
            bindings = [b for b in segment.get('bindings', []) if b.get('subject_ids') == [sid] and b.get('roles') == ['speaker_identity']]
            if len(bindings) != 1:
                return unchanged('not_one_pure_identity_binding')
            picture = str(bindings[0]['local_picture'])
            subject = '<Subject ' + sid + '>'
            picture_token = '<Picture ' + picture + '>'
            marker = re.compile('(?m)^(' + '|'.join(H3_FIELDS) + '):\\s*\\n')
            marks = list(marker.finditer(prompt))
            if tuple((m[1] for m in marks)) != H3_FIELDS:
                return unchanged('unsupported_h3_sections')
            fields = {m[1]: prompt[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(prompt)] for i, m in enumerate(marks)}
            definitions = fields['subject_definitions'].splitlines()
            normalized = []
            prefixes = []
            for line in definitions:
                stripped = line.lstrip()
                prefix = '- ' if stripped.startswith('- ') else ''
                normalized.append(stripped[2:] if prefix else stripped)
                prefixes.append(prefix)
            person_lines = [i for i, line in enumerate(normalized) if line.startswith(subject + ' ') or line.startswith(subject + ':')]
            identity_lines = [i for i, line in enumerate(normalized) if line.startswith('Identity source for ' + subject + ':')]
            if len(person_lines) != 1 or len(identity_lines) > 1:
                return unchanged('unrecognized_identity_definition')
            profile = 'canonical' if identity_lines else 'authored_line'
            prefix = prefixes[person_lines[0]]
            old_definition = definitions[person_lines[0]]
            if profile == 'authored_line' and re.findall('<Picture [0-9]+>', old_definition) != [picture_token]:
                return unchanged('ambiguous_authored_identity_reference')
            audios = re.findall('<Audio \\d+>', old_definition)
            if len(set(audios)) != 1:
                return unchanged('no_unique_voice_reference')
            return ([sid, voice, alias, picture, subject, picture_token, fields, definitions, person_lines, identity_lines, audios, part, composition, marks[-1].end(), profile, prefix], {'applied': True})
        plan = json.loads(input_text)
        result = input_text
        if plan['mode'] == 'with_voice' and plan['count'] > 1:
            for s in plan['segments']:
                if '_hand_visibility_pending_v2' in s:
                    context = s.pop('_hand_visibility_pending_v2')
                    context, audit = stage(s['prompt'], s, context)
                    if audit['applied']:
                        s['_hand_visibility_pending_v2'] = context
            result = plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed798203:
    """Fixed function formerly embedded in node 798203."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 798203."
    def run(self, input_text):
        return _fixed_798203(input_text, "")

def _fixed_798241(input_text, input_json=""):
    result = ""
    try:
        FIELDS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music')
        PREFIX = 'Generate synchronized native voice and mouth motion using the same speaker identity and natural delivery as the uploaded voice reference.'
        OFFSCREEN_PREFIX = 'Generate the specified off-screen voiceover using the same speaker identity and natural delivery as the uploaded voice reference.'
        SUFFIX = ' The reference supplies vocal identity, never source words to repeat. Treat every supplied dialogue block above as a verbatim script. Speak every word once, in order; preserve short words and particles. After each scripted line ends, continue its described physical action with natural breathing or the requested ambience until the next scripted line. Do not fill a pause with speech. Do not invent a sign-off, greeting, filler, repetition, or extra line. Background music must not introduce unscripted vocals or intelligible words.'
        TIMBRE_CONTRACT = "Use the uploaded audio only for the assigned speaker's vocal timbre. Follow the delivery specified beside each dialogue block. Speak only the written dialogue, once, in order, with clear articulation through its final syllable. After the last written syllable in this shot, the speaker remains vocally silent through the remaining authored action; retain only the user-specified non-speech sounds."

        def source_scope(source):
            raw = source.get('source', '') + source.get('header', '') + source.get('tail', '')
            lower = raw.lower()
            if any((x in lower for x in ('fully_copy', 'partially_copy', 'original audio track', 'reuse', '原音轨', '复用原录音'))):
                return 'authored_recording_reuse_preserved'
            words = set(re.findall('[a-z]+', lower))
            vocals = 'laugh laughs laughed laughing laughter chuckle chuckles chuckled chuckling hum hums humming hummed sing sings singing sung cry cries crying cried scream screams screamed screaming giggle giggles giggled giggling gasp gasps gasped gasping sigh sighs sighed sighing'.split()
            if words.intersection(vocals):
                return 'authored_vocal_event_requires_specific_scope'
            if any((x in raw for x in ('笑声', '哼唱', '尖叫', '哭声', '叹气'))):
                return 'authored_vocal_event_requires_specific_scope'
            if PREFIX + SUFFIX in raw or OFFSCREEN_PREFIX + SUFFIX in raw:
                return 'guard_is_authored_content'
            audio_lines = dict(re.findall('(?m)^\\s*[-*]?\\s*<Audio (\\d+)>:\\s*([^\\n]+)', source.get('header', '')))
            for number in source['inventory']['audios']:
                line = audio_lines.get(str(number), '').lower()
                if not any((x in line for x in ('voice', 'vocal timbre'))) or any((x in line for x in ('music', 'rhythm', 'beat', 'sound effect', 'recording', 'cadence', 'delivery'))):
                    return 'audio_role_not_exclusively_voice_reference'
            return ''

        def optimize_segment(segment, source, scope_reason=None):
            before = segment['prompt']

            def unchanged(reason):
                return (before, {'applied': False, 'reason': reason})
            if segment.get('raw_passthrough') or segment.get('visual_only') or (not segment.get('native_audio')):
                return unchanged('outside_structured_native_spoken_scope')
            if segment.get('guide_enabled') or segment.get('continuation'):
                return unchanged('continuation_not_in_this_candidate_scope')
            blocks = re.findall('<d>.*?</d>', before, re.S)
            expected = [source['rows'][i]['raw_dialogue'] for i in segment['source_blocks']]
            if not blocks or blocks != expected or any(t in before for t in ('<scenetrans>', '<|scenetrans|>', '<cutoff>', '<|cutoff|>')):
                return unchanged('dialogue_or_transition_outside_contract')
            if segment.get('source_metadata', {}).get('explicit_nonverbal_vocals'):
                return unchanged('authored_nonverbal_vocals')
            if scope_reason is None:
                scope_reason = source_scope(source)
            if scope_reason:
                return unchanged(scope_reason)
            matches = list(re.finditer('(?m)^(' + '|'.join(FIELDS) + '):\\s*\\n', before))
            if [m[1] for m in matches] != list(FIELDS):
                return unchanged('unrecognized_six_section_structure')
            fields = {m[1]: before[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(before)] for i, m in enumerate(matches)}
            options = [(PREFIX + SUFFIX, "Generate synchronized native voice and mouth motion using the assigned speaker's vocal timbre. "), (OFFSCREEN_PREFIX + SUFFIX, 'Generate the specified off-screen voiceover. ')]
            matching = [(old, start) for old, start in options if fields['overall_soundscape'].count(old) == 1]
            if len(matching) != 1:
                return unchanged('unrecognized_compiler_audio_guard')
            old, start = matching[0]
            fields['overall_soundscape'] = fields['overall_soundscape'].replace(old, start + TIMBRE_CONTRACT, 1)
            audio_map = dict(zip(source['inventory']['audios'], (1, 2, 3)))
            definitions = source['header'].partition('summary:')[0]
            existing = set(re.findall('(?m)^\\s*<Audio (\\d+)>:', fields['subject_definitions']))
            used = set(re.findall('<Audio (\\d+)>', before))
            added = []
            for line in definitions.splitlines():
                match = re.match('\\s*<Audio (\\d+)>:\\s*(.+)', line)
                if not match or int(match[1]) not in audio_map:
                    continue
                number = str(audio_map[int(match[1])])
                if number in used and number not in existing:
                    if re.search('<(?:Picture|Video|Audio)\\s+\\d+>', match[2]):
                        return unchanged('complex_audio_definition_requires_mapper')
                    added.append('<Audio ' + number + '>: ' + match[2])
                    existing.add(number)
            if added:
                fields['subject_definitions'] = fields['subject_definitions'].rstrip() + '\n' + '\n'.join(added) + '\n'
            detail_before = fields['detailed_description']
            fields['detailed_description'] = re.sub('</d>[ \\t]*(?:\\r?\\n[ \\t]*)*', '</d>\n\n', detail_before)
            after = ''.join((k + ':\n' + fields[k] for k in FIELDS))
            assert re.findall('<d>.*?</d>', after, re.S) == blocks
            assert set(re.findall('<(?:Picture|Audio|Video) \\d+>', after)) == set(re.findall('<(?:Picture|Audio|Video) \\d+>', before))
            assert ' '.join(fields['detailed_description'].split()) == ' '.join(detail_before.split())
            return (after, {'applied': True, 'audioDefinitionsRestored': added, 'offscreenGuardPreserved': old.startswith(OFFSCREEN_PREFIX), 'scriptChanged': False, 'authoredActionChanged': False, 'voiceReferenceChanged': False, 'renderVerified': False})

        envelope=json.loads(input_json)
        segment=json.loads(input_text)
        result=segment
        if envelope['plan']['mode']=='with_voice':
            prompt,audit=optimize_segment(segment,envelope['source'])
            result=dict(segment,prompt=prompt)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed798241:
    """Fixed function formerly embedded in node 798241."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 798241."
    def run(self, input_text, input_json):
        return _fixed_798241(input_text, input_json)

def _fixed_799251(input_text, input_json=""):
    result = ""
    try:
        FIELDS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music')
        TIMBRE = "Use the uploaded audio only for the assigned speaker's vocal timbre. Follow the delivery specified beside each dialogue block. Speak only the written dialogue, once, in order, with clear articulation through its final syllable. After the last written syllable in this shot, the speaker remains vocally silent through the remaining authored action; retain only the user-specified non-speech sounds."
        STARTS = ("Generate synchronized native voice and mouth motion using the assigned speaker's vocal timbre. ", 'Generate the specified off-screen voiceover. ')
        CAPTION_HINT = 'All dialogue blocks specify audible speech only, without on-screen transcription.'
        QUIET_BACKGROUND = 'The background is quiet throughout the shot.'

        def scope_native_speech(payload, envelope):
            out = dict(payload)
            before = payload['prompt']
            segment, env = (envelope['segment'], envelope['env'])

            def unchanged(reason):
                return (out, dict(applied=False, reason=reason))
            if not segment.get('native_audio') or any((segment.get(k) for k in ('raw_passthrough', 'visual_only', 'guide_enabled', 'continuation', 'internal_split_origin'))):
                return unchanged('different_native_or_continuation_route')
            units, blocks = (segment.get('speaker_units', []), segment.get('source_blocks', []))
            if len(units) != 1 or len(blocks) != 1:
                return unchanged('multi_utterance_not_changed')
            unit = units[0]
            assert unit['source_block'] == blocks[0], 'speech_layout_source_binding'
            audios = env.get('inventory', {}).get('audios', [])
            if unit['voice'] not in audios:
                return unchanged('no_reference_voice')
            if segment.get('source_metadata', {}).get('explicit_nonverbal_vocals'):
                return unchanged('authored_vocal_event')
            if any((t in before for t in ('<scenetrans>', '<|scenetrans|>', '<cutoff>', '<|cutoff|>', '<singing>', '<lyrics>'))):
                return unchanged('authored_continuation_or_singing')
            matches = list(re.finditer('(?m)^(' + '|'.join(FIELDS) + '):[ \\t]*\\r?\\n', before))
            if [m[1] for m in matches] != list(FIELDS):
                return unchanged('noncanonical_sections')
            fields = {m[1]: before[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(before)] for i, m in enumerate(matches)}
            guards = [s + TIMBRE for s in STARTS if fields['overall_soundscape'].count(s + TIMBRE) == 1]
            if len(guards) != 1 or any((g in fields['detailed_description'] for g in guards)):
                return unchanged('no_recognized_compiler_voice_guard')
            dialogue = re.findall('<d>.*?</d>', before, re.S)
            if len(dialogue) != 1 or dialogue != re.findall('<d>.*?</d>', segment['prompt'], re.S):
                return unchanged('dialogue_scope_not_exact')
            body = fields['detailed_description']
            utterance = re.search('(?m)^[ \\t]*(<Subject[ \\t]+(\\d+)>[ \\t]*\\(S(\\d+)\\):[ \\t]*)' + re.escape(dialogue[0]), body)
            if not utterance or utterance[2] != str(unit['subject']):
                return unchanged('speaker_binding_not_canonical')
            audio = str(audios.index(unit['voice']) + 1)
            subject, speaker = (utterance[2], utterance[3])
            definition_pattern = '(?m)^([ \\t]*<Audio ' + audio + '>:[^\\n]*)(\\n|$)'
            definitions = list(re.finditer(definition_pattern, fields['subject_definitions']))
            if len(definitions) != 1:
                return unchanged('audio_definition_not_unique')
            guard = guards[0]
            remaining = fields['overall_soundscape'].replace(guard, '', 1)
            hint_count = remaining.count(CAPTION_HINT)
            if hint_count > 1:
                return unchanged('ambiguous_caption_guard')
            if hint_count:
                remaining = remaining.replace(CAPTION_HINT, '', 1)
            quiet = remaining.strip().lower() in ('', 'n/a', 'n/a.')
            fields['overall_soundscape'] = QUIET_BACKGROUND + '\n\n' if quiet else remaining
            moved = '\n' + guard + ('\n' + CAPTION_HINT if hint_count else '') + '\n'
            end = utterance.end()
            body = body[:end] + moved + body[end:]
            cue = 'For this utterance, <Audio ' + audio + '> supplies the vocal timbre of <Subject ' + subject + '> (S' + speaker + ').\n'
            body = body[:utterance.start()] + cue + body[utterance.start():]
            fields['detailed_description'] = body
            definition = definitions[0]
            binding = ' This voice reference belongs to <Subject ' + subject + '> (S' + speaker + ').'
            defs = fields['subject_definitions']
            fields['subject_definitions'] = defs[:definition.end(1)] + binding + defs[definition.end(1):]
            after = ''.join((k + ':\n' + fields[k] for k in FIELDS))
            assert re.findall('<d>.*?</d>', after, re.S) == dialogue, 'speech_layout_words_changed'
            assert after.count(guard) == before.count(guard), 'speech_layout_guard_duplicated'
            assert set(re.findall('<(?:Picture|Audio|Video|Subject) \\d+>', before)) == set(re.findall('<(?:Picture|Audio|Video|Subject) \\d+>', after)), 'speech_layout_reference_changed'
            out['prompt'] = after
            return (out, dict(applied=True, reason='native_speech_scoped_to_current_shot', subject=subject, speaker=speaker, audio=audio, compilerGuardMoved=True, captionHintMoved=bool(hint_count), quietBackgroundClarified=quiet, dialogueChanged=False, originalDeliveryUnchanged=True, originalActionsUnchanged=True, actualAudioUnchanged=True, movedGuard=guard, insertedCue=cue, insertedBinding=binding))
        result, audit = scope_native_speech(json.loads(input_text), json.loads(input_json))

        # The preceding layout scope already guarantees one native utterance.
        if audit.get('applied', False):
            ending_match = re.search(r'<d>(\[Chinese\].*?)(\s*)</d>', result['prompt'], re.S)
            if ending_match and ending_match[1][9:].strip() and ending_match[1][-1] not in '.,?!;:，。？！；：…':
                ending_at = ending_match.end(1)
                result['prompt'] = result['prompt'][:ending_at] + '.' + result['prompt'][ending_at:]
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed799251:
    """Fixed function formerly embedded in node 799251."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 799251."
    def run(self, input_text, input_json):
        return _fixed_799251(input_text, input_json)

def _fixed_798202(input_text, input_json=""):
    result = ""
    try:
        def stage(prompt, segment, context):

            def unchanged(reason):
                return (prompt, {'applied': False, 'reason': reason})
            sid, voice, alias, masked = context
            composition = re.search('\\b(?:close[- ]up(?:\\s+shot)?|macro\\s+shot)\\b[^.!?\\n]*', masked, re.I)
            hands = [m for m in re.finditer("\\b(S\\d+)['’]s\\s+((?:(?:right|left|bare|gloved|index)\\s+){0,3}(?:hands?|fingers?|fingertips?))\\b", masked, re.I) if m[1].lower() == alias.lower()]
            hand = hands[0] if hands else None
            if not composition or not hand:
                return unchanged('no_explicit_hand_closeup')
            anchor_text = masked
            generated_head = 'From the first frame, show a '
            original_action = segment['action_provenance'][0].get('original_action', '')
            if generated_head in masked and original_action:
                original_masked = re.sub('<d>.*?</d>', '', original_action, flags=re.S)
                neutral = '<Picture [0-9]+>|\\[Shot [0-9]+\\]'
                old = re.sub(neutral, '<REF>', original_masked)
                mapped = re.sub(neutral, '<REF>', masked)
                if old.startswith('<REF> Hard cut to a ') and old.replace('Hard cut to a ', generated_head, 1) == mapped:
                    anchor_text = masked.replace(generated_head, 'Hard cut to a ', 1)
            if re.search('\\b(?:first frame|last frame|keyframe|composition anchor|storyboard)\\b', anchor_text, re.I):
                return unchanged('explicit_frame_anchor')
            return ([sid, voice, alias, hand[2].lower(), composition[0]], {'applied': True})
        plan = json.loads(input_text)
        result = input_text
        if plan['mode'] == 'with_voice' and plan['count'] > 1:
            for s in plan['segments']:
                if '_hand_visibility_pending_v2' in s:
                    context = s.pop('_hand_visibility_pending_v2')
                    context, audit = stage(s['prompt'], s, context)
                    if audit['applied']:
                        s['_hand_visibility_pending_v2'] = context
            result = plan
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed798202:
    """Fixed function formerly embedded in node 798202."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 798202."
    def run(self, input_text):
        return _fixed_798202(input_text, "")

def _fixed_799253(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        context = json.loads(input_json)
        segment = context['segment']
        before = result['prompt']
        excluded = any(segment.get(k, False) for k in ('raw_passthrough', 'visual_only', 'guide_enabled', 'continuation'))
        excluded = excluded or bool(segment.get('source_metadata', {}).get('explicit_nonverbal_vocals'))
        excluded = excluded or any(t in before for t in ('<scenetrans>', '<|scenetrans|>', '<cutoff>', '<|cutoff|>'))
        excluded = excluded or any(t in before.lower() for t in ('fully_copy', 'partially_copy', 'original audio track', 'reuse', '原音轨', '复用原录音'))
        units = segment.get('speaker_units', [])
        bound_voice = units[0].get('voice') if len(units) == 1 else None
        available_audio = context.get('env', {}).get('inventory', {}).get('audios', [])
        bound_reference_voice = bool(bound_voice) and bound_voice in available_audio
        excluded = excluded or not bound_reference_voice
        blocks = re.findall(r'<d>.*?</d>', before, re.S)
        authored = segment.get('text', '').strip()
        if segment.get('native_audio') and not excluded and len(units) == 1 and len(segment.get('source_blocks', [])) == 1 and len(blocks) == 1 and authored:
            match = re.search(r'<d>\[Chinese\]([^<]*?)(\s*)</d>', before, re.S)
            if match:
                words = match[1].rstrip()
                if words == authored and words and words[-1] not in '.,?!;:，。？！；：…':
                    end = match.end(1)
                    result = dict(result, prompt=before[:end] + '.' + before[end:])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed799253:
    """Fixed function formerly embedded in node 799253."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 799253."
    def run(self, input_text, input_json):
        return _fixed_799253(input_text, input_json)

def _fixed_970010(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_text);state=json.loads(input_json)
        n=int(r['decoded_count']);sr=int(r['sample_rate']);i=int(r['segment_index'])
        assert sr==32000 and n>0 and i==len(state['records']), 'PCM_CLOCK_INPUT'
        start=sum(int(x['retained_count']) for x in state['records'])
        a=(2*start*sr+24)//48;b=(2*(start+n)*sr+24)//48
        samples=int(round(float(r['native_audio_seconds'])*sr));target=b-a
        assert samples>0 and abs(samples-target)<=sr/24+2, 'PCM_AV_CLOCK_MISMATCH'
        kept=min(samples,target)
        result=dict(segment_index=i,output_start=start,target_samples=target,native_samples=samples,pad_samples=target-kept,trim_seconds=(kept+0.25)/sr,fade_in_seconds=0.002 if i>0 else 0.0,fade_out_seconds=0.002,retained_count=n,clock='cumulative_video_24fps_32000hz',audio_origin='native_vae_before_aac')
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed970010:
    """Fixed function formerly embedded in node 970010."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 970010."
    def run(self, input_text, input_json):
        return _fixed_970010(input_text, input_json)

def _fixed_978001(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        context = json.loads(input_json)
        segment = context['segment']
        source = context['env']['source']
        prompt = result['prompt']
        FIELDS = ('subject_definitions', 'summary', 'retention_analysis', 'detailed_description', 'overall_soundscape', 'non_diegetic_music')
        marks = list(re.finditer(r'(?m)^(\w+):[ \t]*\n', prompt))
        if not segment.get('raw_passthrough') and tuple(m[1] for m in marks) == FIELDS:
            fields = {m[1]: prompt[m.end():marks[i+1].start() if i+1<len(marks) else len(prompt)] for i,m in enumerate(marks)}
            header = source.split('summary:', 1)[0]
            declarations = {}
            for match in re.finditer(r'(?m)^\s*<Picture\s+(\d+)>\s*[:：]\s*([^\n]+)', header):
                declarations[int(match[1])] = match[2].strip()
            patterns = [('facial identity', ['face','facial'], ['人脸','面部','五官','脸型']), ('wardrobe', ['wardrobe','attire','clothing','costume','outfit'], ['服装','衣着','衣服','穿着']), ('hairstyle', ['hairstyle','hair'], ['发型','头发']), ('environment', ['environment','interior','setting','background'], ['场景','环境','背景']), ('props', ['props','desk','computer'], ['道具','桌','电脑'])]
            prefix = source.partition('detailed_description:')
            clauses = re.split(r'[.\n]',prefix[0]+prefix[2].split('[Shot ',1)[0])
            assignments = {}
            for clause in clauses:
                slots = set(re.findall(r'<Picture (\d+)>',clause))
                if len(slots)==1:
                    slot = int(list(slots)[0])
                    assignments.setdefault(slot,[]).append(re.split(r'\bnot\b|\bexcluding\b|\bexclude\b|不含|不要|不参考',clause,maxsplit=1,flags=re.I)[0])
            groups = {}
            for binding in segment.get('bindings', []):
                if len(binding.get('subject_ids', [])) != 1 or 'speaker_identity' not in binding.get('roles', []):
                    continue
                slot = binding['original_slot']
                descriptor = declarations.get(slot, '')
                # Explicit exclusions do not become requested attributes.
                positive = re.split(r'\bnot\b|\bexcluding\b|\bexclude\b|不含|不要|不参考', descriptor, maxsplit=1, flags=re.I)[0]
                if positive.strip():
                    positive += ' '+ ' '.join(assignments.get(slot,[]))
                words = set(re.findall(r'[a-z]+',positive.lower()))
                roles = [name for name, english, chinese in patterns if words.intersection(english) or any(word in positive for word in chinese)]
                anchor = any(word in positive.lower() for word in ['first frame','last frame','keyframe','composition anchor','首帧','尾帧','关键帧'])
                if not roles or anchor:
                    continue
                sid = binding['subject_ids'][0]
                groups.setdefault(sid, []).append({'original_slot':slot, 'local_picture':binding['local_picture'], 'roles':roles, 'declaration':descriptor})
            scoped = {}
            audit = []
            for sid, bindings in groups.items():
                faces = [b for b in bindings if 'facial identity' in b['roles'] and 'wardrobe' not in b['roles'] and 'environment' not in b['roles']]
                clothes = [b for b in bindings if 'wardrobe' in b['roles'] and 'facial identity' not in b['roles']]
                if len(faces) != 1 or len(clothes) != 1 or faces[0]['original_slot'] == clothes[0]['original_slot']:
                    continue
                for binding in bindings:
                    scoped[binding['local_picture']] = (sid, binding)
                audit.append({'subject':sid, 'faceSlot':faces[0]['original_slot'], 'wardrobeSlot':clothes[0]['original_slot'], 'bindings':bindings})
            if audit:
                result["_attribute_pending_v1"] = {"scoped":scoped,"audit":audit,"fields":fields}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed978001:
    """Fixed function formerly embedded in node 978001."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 978001."
    def run(self, input_text, input_json):
        return _fixed_978001(input_text, input_json)

def _fixed_978003(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        context = json.loads(input_json)
        segment = context['segment']
        source = context['env']['source']
        prompt = result['prompt']
        FIELDS = ('subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music')
        marks = [prompt.find(k+':\n') for k in FIELDS]
        excluded = any(segment.get(k,False) for k in ('raw_passthrough','continuation','guide_enabled'))
        if not excluded and min(marks)>=0 and marks==sorted(marks):
            fields = {k:prompt[marks[i]+len(k)+2:marks[i+1] if i<5 else len(prompt)] for i,k in enumerate(FIELDS)}
            original_detail = fields['detailed_description']
            overview = source.partition('summary:')[2].partition('retention_analysis:')[0].lower()
            sequential = ('first ' in overview and 'then ' in overview) or ('initially ' in overview and any(w in overview for w in ['later ','subsequently ','finally '])) or ('先' in overview and any(w in overview for w in ['再','然后']))
            multiple = source.partition('detailed_description:')[2].partition('overall_soundscape:')[0].count('[Shot ') > 1
            action = '\n'.join(row.get('reference_mapped_action',row.get('original_action','')) for row in segment.get('action_provenance',[]))
            detail_head, separator, local = original_detail.partition('[Shot 1]')
            audit = {}
            if sequential and multiple and separator and action:
                current = local.partition('<d>')[0].strip()
                if current.endswith(':') and '<Subject ' in current.rsplit('\n',1)[-1]:
                    current = current.rsplit('\n',1)[0].strip()
                fields['summary'] = 'One continuous authored shot. '+current+'\n'
                audit['crossShotOverviewRemoved'] = True
            lower = action.lower()
            opening = []
            for state,phrases in [('seated',['seated medium','seated close','seated wide','opens with','begins with','starts with','坐姿中景','坐姿近景']),('standing',['standing medium','standing close','standing wide','站姿中景']),('lying',['lying medium','lying close','卧姿近景'])]:
                if any(phrase in lower for phrase in phrases[:3]) or any(phrase in lower for phrase in phrases if not phrase.endswith('with')):
                    opening.append(state)
            if 'seated' not in opening and any(word in lower for word in ['opens with','begins with','starts with']):
                first_sentence = lower.partition('.')[0]
                if 'seated' in first_sentence or 'sitting' in first_sentence:
                    opening.append('seated')
            transitions = ['stand up','stands up','standing up','rises','rising','rise ','get up','gets up','getting up','sit down','sits down','sitting down','walk','run ','runs ','running','lie down','lies down','起身','站起','坐下','走动','走向','躺下']
            transition = any(word in lower for word in transitions)
            additions = []
            if sequential and multiple and len(opening)==1 and not transition and len(segment.get('declared_subjects',[]))==1:
                sid = str(segment['declared_subjects'][0])
                additions.append('Throughout this entire authored shot, <Subject '+sid+'> remains '+opening[0]+', performing the described gestures within that posture. A change of posture or locomotion described only in another shot belongs to that later shot.')
                audit['openingStateHold'] = opening[0]
            spoken = ''.join(re.findall(r'<d>(.*?)</d>',prompt,re.S))
            cues = []
            cue_positions = []
            for marker in ['immediately after,','immediately after;','after that,','afterwards,','afterward,','说完后，','说完后,']:
                position = lower.find(marker)
                if position>=0:
                    cue_positions.append((position,marker))
            for position,marker in cue_positions:
                prior = action[:position]
                quoted = re.findall(r'["“]([^"”\n]+)["”]',prior)
                if not quoted:
                    continue
                cue = quoted[-1].strip()
                cue_normalized = re.sub(r'[\s,，。.!！?？;；:：]','',cue)
                spoken_normalized = re.sub(r'[\s,，。.!！?？;；:：]','',spoken)
                if not cue or cue_normalized not in spoken_normalized:
                    continue
                event = action[position+len(marker):].strip().split('\n')[0]
                stops = [event.find(mark) for mark in ['. ','! ','? ','。'] if mark in event]
                if stops:
                    event = event[:min(stops)+1]
                if not event or '<d>' in event or '<Subject' in event:
                    continue
                additions.append('Action timing: finish the existing scripted speech cue "'+cue+'" before the subsequent authored action: '+event+' Keep the preceding state until this cue is complete. The cue is part of the single existing dialogue, not an additional line.')
                cues.append({'cue':cue,'event':event})
            if cues:
                audit['afterSpeechCues'] = cues
            if additions:
                fields['detailed_description'] = original_detail.rstrip()+'\n\n'+'\n'.join(additions)+'\n'
            if audit:
                after = ''.join(k+':\n'+fields[k] for k in FIELDS)
                assert re.findall(r'<d>.*?</d>',after,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S),'TIMING_DIALOGUE_CHANGED'
                assert fields['detailed_description'].startswith(original_detail.rstrip()),'AUTHORED_ACTION_CHANGED'
                result['prompt'] = after
                result['shot_event_scope_v1'] = audit
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed978003:
    """Fixed function formerly embedded in node 978003."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 978003."
    def run(self, input_text, input_json):
        return _fixed_978003(input_text, input_json)

def _fixed_978005(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        prompt = result['prompt']
        FIELDS = ('subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music')
        if '_attribute_pending_v1' in result:
            pending = result.pop('_attribute_pending_v1')
            scoped = {int(k):v for k,v in pending['scoped'].items()}
            audit = pending['audit']
            fields = pending['fields']
            rows = []
            for line in fields['subject_definitions'].splitlines():
                tokens = [int(n) for n in re.findall(r'<Picture (\d+)>', line)]
                if line.lstrip().startswith('Identity source for <Subject ') and len(set(tokens)) == 1 and tokens[0] in scoped:
                    sid, binding = scoped[tokens[0]]
                    line = '<Subject ' + sid + '> attributes from <Picture ' + str(tokens[0]) + '>: ' + ', '.join(binding['roles']) + ' only. Apply the originally declared attributes; this photograph is not a displayed frame.'
                    if line in rows:
                        continue
                rows.append(line)
            fields['subject_definitions'] = '\n'.join(rows) + '\n'
            for picture, pair in scoped.items():
                sid, binding = pair
                old = '<Subject '+sid+'> (identity and clothing from <Picture '+str(picture)+'>)'
                new = '<Subject '+sid+'> ('+', '.join(binding['roles'])+' from <Picture '+str(picture)+'>)'
                fields['retention_analysis'] = fields['retention_analysis'].replace(old,new)
            fields['retention_analysis'] = fields['retention_analysis'].replace('Compare all references assigned to each identity together.', 'Resolve each explicitly assigned attribute from its own declared reference, keeping the reference roles separate.')
            contracts = []
            for item in audit:
                for binding in item['bindings']:
                    contracts.append('<Subject '+item['subject']+'> uses <Picture '+str(binding['local_picture'])+'> only for '+', '.join(binding['roles'])+'.')
            contract = 'Reference attribute contract for the complete current shot: '+' '.join(contracts)+' Preserve each assignment throughout the shot; an identity-only photograph does not supply wardrobe or scenery.\n'
            fields['retention_analysis'] += contract
            fields['detailed_description'] = contract + fields['detailed_description']
            after = ''.join(k+':\n'+fields[k] for k in FIELDS)
            assert re.findall(r'<d>.*?</d>', after, re.S) == re.findall(r'<d>.*?</d>', prompt, re.S), 'ATTRIBUTE_DIALOGUE_CHANGED'
            assert set(re.findall(r'<(?:Picture|Video|Audio) \d+>',after)) == set(re.findall(r'<(?:Picture|Video|Audio) \d+>',prompt)), 'ATTRIBUTE_REFERENCE_CHANGED'
            result['prompt'] = after
            result['reference_attribute_scope_v1'] = audit
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed978005:
    """Fixed function formerly embedded in node 978005."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 978005."
    def run(self, input_text):
        return _fixed_978005(input_text, "")

def _fixed_979001(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        context = json.loads(input_json)
        segment = context['segment']
        for index in range(1,10):
            result['route_slot_'+str(index)] = segment.get('slot_'+str(index),0)
        audit = result.get('reference_attribute_scope_v1',[])
        excluded = any(segment.get(k,False) for k in ['raw_passthrough','continuation','guide_enabled'])
        if not excluded and len(audit)==1 and len(segment.get('declared_subjects',[]))==1:
            assigned = audit[0]['bindings']
            faces = [b for b in assigned if b['roles']==['facial identity']]
            scenes = [b for b in assigned if 'environment' in b['roles'] and 'facial identity' not in b['roles']]
            if len(faces)==1 and len(scenes)==1 and faces[0]['original_slot']!=scenes[0]['original_slot']:
                face = faces[0]
                scene = scenes[0]
                slots = segment['original_slots']
                eligible = bool(result.get('crop_used') and segment.get('crop_source')==face['original_slot'] and len(slots)<9)
                result['reference_content_isolation_v2'] = {'applied':False,'reason':'face_crop_unavailable_or_source_mismatch','faceSlot':face['original_slot'],'sceneSlot':scene['original_slot']}
                if eligible:
                    old = result['prompt']
                    extra = len(slots)+1
                    instruction = 'Additional <Picture '+str(extra)+'> is a literal face-detail crop of the same <Subject '+segment['identity_subjects'][0]+'>. Compare it with the original identity images only to preserve facial features. It is not a shot, keyframe, scene, costume or camera target. Never display the reference still or face card in the video.'
                    assert old.count(instruction)==1, 'ISOLATION_CROP_PROVENANCE_MISSING'
                    prompt = old.replace(instruction+'\n','',1)
                    ordered = [scene['original_slot']]+[slot for slot in slots if slot!=scene['original_slot']]
                    mapping = {str(i+1):ordered.index(slot)+1 for i,slot in enumerate(slots)}
                    def picture(match):
                        assert match[1] in mapping, 'ISOLATION_UNEXPECTED_PICTURE'
                        return '<Picture '+str(mapping[match[1]])+'>'
                    parts = re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
                    for index in range(0,len(parts),2):
                        parts[index] = re.sub(r'<Picture (\d+)>',picture,parts[index])
                    prompt = ''.join(parts)
                    face_local = ordered.index(face['original_slot'])+1
                    scene_local = ordered.index(scene['original_slot'])+1
                    contract = 'The complete room, background layout, furniture and scene props come exclusively from <Picture '+str(scene_local)+'>. <Picture '+str(face_local)+'> contains only the detected facial region of the same person and supplies facial identity only. Preserve the scene reference throughout this continuous shot, including while the person moves.\n'
                    prompt = prompt.replace('detailed_description:\n','detailed_description:\n'+contract,1)
                    assert re.findall(r'<d>.*?</d>',prompt,re.S)==re.findall(r'<d>.*?</d>',old,re.S), 'ISOLATION_DIALOGUE_CHANGED'
                    assert sorted(ordered)==sorted(slots), 'ISOLATION_ORIGINAL_REFERENCE_DROPPED'
                    assert set(re.findall(r'<Picture (\d+)>',prompt))==set(str(i+1) for i in range(len(slots))), 'ISOLATION_LABEL_ROUTE_MISMATCH'
                    result['prompt'] = prompt
                    for index in range(1,10):
                        result['route_slot_'+str(index)] = ordered[index-1] if index<=len(ordered) else 0
                        result['crop_'+str(index)] = index==face_local
                    for item in audit:
                        for binding in item['bindings']:
                            binding['local_picture'] = ordered.index(binding['original_slot'])+1
                    result['reference_content_isolation_v2'] = {'applied':True,'reason':'explicit_face_only_and_distinct_scene_with_detected_crop','faceSlot':face['original_slot'],'sceneSlot':scene['original_slot'],'faceLocal':face_local,'sceneLocal':scene_local,'originalOrder':slots,'routedOrder':ordered,'removedDuplicateCropLocal':extra,'originalInputsUnchanged':True}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed979001:
    """Fixed function formerly embedded in node 979001."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 979001."
    def run(self, input_text, input_json):
        return _fixed_979001(input_text, input_json)

def _fixed_979003(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        context = json.loads(input_json)
        segment = context['segment']
        previous = result.get('shot_event_scope_v1',{})
        cues = previous.get('afterSpeechCues',[])
        excluded = any(segment.get(k,False) for k in ['raw_passthrough','continuation','guide_enabled'])
        FIELDS = ('subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music')
        prompt = result['prompt']
        marks = [prompt.find(k+':\n') for k in FIELDS]
        if not excluded and len(cues)==1 and len(segment.get('declared_subjects',[]))==1 and min(marks)>=0 and marks==sorted(marks):
            fields = {k:prompt[marks[i]+len(k)+2:marks[i+1] if i<5 else len(prompt)] for i,k in enumerate(FIELDS)}
            detail = fields['detailed_description']
            head,separator,local = detail.partition('[Shot 1]')
            tags = re.findall(r'<d>(.*?)</d>',local,re.S)
            cue = cues[0]['cue']
            before = local.partition('<d>')[0]
            lower = before.lower()
            positions = []
            for marker in ['immediately after,','immediately after;','after that,','afterwards,','afterward,','说完后，','说完后,']:
                position = lower.find(marker)
                if position>=0:
                    positions.append((position,marker))
            state = ''
            opening_clauses = re.findall(r'(?:shot\s+)?(?:opens|begins|starts)\s+with[^.!?。！？\n]*',lower)
            for name,pattern in [('seated',r'\b(?:seated|sitting)\b|坐姿|坐着'),('standing',r'\bstanding\b|站姿|站着'),('lying',r'\blying\b|卧姿|躺着')]:
                if any(re.search(pattern,clause) for clause in opening_clauses) or re.search(pattern+r'\s*(?:medium|close|wide|中景|近景|远景)',lower):
                    state = name if not state else 'ambiguous'
            if not state:
                for name,token in [('seated','坐姿'),('standing','站姿'),('lying','卧姿')]:
                    if token in before:
                        state = name if not state else 'ambiguous'
            if separator and len(tags)==1 and len(positions)==1 and state and state!='ambiguous':
                result['_chronology_pending_v2'] = {'fields':fields,'head':head,'local':local,'dialogue':tags[0],'cue':cue,'before':before,'position':positions[0][0],'marker':positions[0][1],'state':state,'subject':str(segment['declared_subjects'][0])}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed979003:
    """Fixed function formerly embedded in node 979003."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 979003."
    def run(self, input_text, input_json):
        return _fixed_979003(input_text, input_json)

def _fixed_979005(input_text, input_json=""):
    result = ""
    try:
        result = json.loads(input_text)
        context = json.loads(input_json)
        segment = context['segment']
        FIELDS = ('subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music')
        if '_chronology_pending_v2' in result:
            pending = result.pop('_chronology_pending_v2')
            fields = pending['fields']
            head = pending['head']
            local = pending['local']
            dialogue = pending['dialogue']
            cue = pending['cue']
            before = pending['before']
            state = pending['state']
            position = pending['position']
            marker = pending['marker']
            language = re.match(r'\[[^\]\n]+\]',dialogue)
            label = language[0] if language else ''
            speech = dialogue[len(label):]
            characters = [(m[0],m.start()) for m in re.finditer(r'[^\s,，。.!！?？;；:：]',speech)]
            normalized = ''.join(pair[0] for pair in characters)
            offsets = [pair[1] for pair in characters]
            clean_cue = re.sub(r'[\s,，。.!！?？;；:：]','',cue)
            hits = list(re.finditer(re.escape(clean_cue),normalized)) if clean_cue else []
            prefix = before[:position].rstrip(' ;；,，')
            suffix = before[position+len(marker):]
            owner = re.search(r'\s*(<Subject \d+>\s*(?:\(S\d+\))?\s*:)\s*$',suffix)
            actor = owner[1] if owner else '<Subject '+str(segment['declared_subjects'][0])+'>:'
            if owner:
                suffix = suffix[:owner.start()]
            speech_link = re.search(r'\b(?:delivers|says|speaks|utters|saying|speaking)\b|说|讲',prefix,re.I)
            if len(hits)==1 and speech_link and suffix.strip():
                boundary = offsets[hits[0].end()-1]+1
                punctuation = re.match(r'[\s,，。.!！?？;；:：]+',speech[boundary:])
                if punctuation:
                    boundary += len(punctuation[0])
                lead = speech[:boundary]
                remainder = speech[boundary:]
                prefix = prefix.replace('"'+cue+'"','the following scripted words').replace('“'+cue+'”','the following scripted words')
                posture = 'The subject remains '+state+' through the final audible syllable of the following speech. Only the already described gestures occur during these words.'
                boundary_rule = 'After the preceding words have finished, begin the following authored action. Continue the same camera take without a cut or a change of location.'
                rebuilt = '[Shot 1] '+prefix+'.\n'+posture+'\n'+actor+' <d>'+label+lead+'</d>\n'+boundary_rule+'\n'+suffix.strip()
                if remainder:
                    rebuilt += '\nWhile the subsequent described action unfolds, '+actor+' <d>'+label+remainder+'</d>'
                tail = local.split('</d>',1)[1]
                timing_at = tail.find('\nAction timing: finish the existing scripted speech cue ')
                if timing_at>=0:
                    tail = tail[:timing_at]
                rebuilt += tail
                fields['detailed_description'] = head+rebuilt
                fields['summary'] = 'One continuous authored shot. The subject begins '+state+'. Deliver the existing dialogue in its original order, then begin the prescribed transition only after its explicitly preceding words finish.\n'
                after = ''.join(k+':\n'+fields[k] for k in FIELDS)
                spoken_after = ''.join(re.sub(r'^\[[^\]\n]+\]','',s) for s in re.findall(r'<d>(.*?)</d>',after,re.S))
                assert spoken_after==speech, 'CHRONOLOGY_SPOKEN_TEXT_CHANGED'
                assert lead+remainder==speech, 'CHRONOLOGY_SPLIT_NOT_LOSSLESS'
                assert suffix.strip() in after, 'CHRONOLOGY_AUTHORED_ACTION_LOST'
                assert re.findall(r'<d>.*?</d>',context['env']['source'],re.S), 'CHRONOLOGY_SOURCE_DIALOGUE_MISSING'
                result['prompt'] = after
                result['chronological_speech_action_v2'] = {'applied':True,'openingState':state,'cue':cue,'speechPrefix':lead,'speechRemainder':remainder,'sourceDialogue':dialogue,'originalWordsExact':True,'actionAfterSpeech':suffix.strip(),'continuousTake':True,'noNewGeneratedSegments':True}
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed979005:
    """Fixed function formerly embedded in node 979005."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 979005."
    def run(self, input_text, input_json):
        return _fixed_979005(input_text, input_json)

def _fixed_7801101(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        memo=s.pop('regex_memo_v1',{})
        def staged(site,text,live):
            table=memo.get(site,{})
            if text in table:return table[text]
            return live(text)
        mx_route_ok=not s.get('raw_passthrough') and env.get('structured') and not any(s.get(k) for k in ['continuation','guide_enabled','internal_split_origin','first_frame_enabled','boundary_image_inherit'])
        if mx_route_ok and env['inventory']['audios'] and not s.get('reference_scope') and sorted(s['original_slots'])==sorted(env['inventory']['images']):
         units=s.get('speaker_units',[]);prov={a['source_block']:a['original_action'] for a in s.get('action_provenance',[])}
         def label_live(label):
          offscreen_src=r"\boff[- ]?screen\s+(?:voice[- ]?over|voice|narration|narrator)\b|\bvoice[- ]?over\b|画外音|旁白"
          offscreen=re.compile(offscreen_src,re.I)
          oncam=re.compile(r"\bon[- ]?camera\b|\bto (?:the )?camera\b|\bfaces? the camera\b|\bselfie\b|对镜头|出镜",re.I)
          neg=re.search(r"\b(?:not|never|no)\b[^.;\n]{0,20}(?:"+offscreen_src+")",label,re.I)
          return [bool(offscreen.search(label)),bool(oncam.search(label)),bool(neg)]
         def visible_live(text):return bool(re.search(r"\b(?:face|facial|head|torso|shoulders?|lips|mouth|portrait|selfie|glasses|full[- ]body|over[- ]the[- ]shoulder|eye contact|on[- ]camera|mirror|reflection|smil\w*|nods?|sits?|seated|stands?|standing|walks?|walking)\b|faces? the camera|looks? (?:at|into) the camera",text,re.I))
         speakers=set();ok=bool(units) and len(prov)==len(units)
         visual=''
         for u in units:
          action=re.sub(r'<d>.*?</d>','',prov.get(u['source_block'],''),flags=re.S)
          lines=[x for x in action.split('\n') if x.strip()]
          label=lines[-1] if lines else ''
          sid=str(u.get('subject'))
          flags=staged('label',label,label_live)
          if not (flags[0] and not flags[1] and not flags[2] and ('<Subject '+sid+'>' in label or '(S'+sid+')' in label)):ok=False;break
          speakers.add(sid);visual+='\n'.join(lines[:-1])+'\n'
         if ok:
          visual_nolabel=re.sub(r'\[Shot\s+\d+\]','',visual)
          tagged={x for x in re.findall(r'<Subject\s+(\d+)>',visual_nolabel)}.union({x for x in re.findall(r'\(S(\d+)\)',visual_nolabel)})
          direct=[int(n) for n in re.findall(r'<Picture\s+(\d+)>',visual_nolabel)]
          if tagged.intersection(speakers) or staged('visible',visual_nolabel,visible_live) or not direct:ok=False
         if ok:
          direct_orig=[n for n in direct if n in s['original_slots']]
          others=sorted(tagged-speakers);keep=set(direct_orig)
          for b in s.get('bindings',[]):
           if set(b.get('subject_ids',[])).intersection(set(others)) and b['roles']==['speaker_identity']:keep.add(b['original_slot'])
          slots=s['original_slots'];selected=[n for n in slots if n in keep]
          if selected and len(selected)<len(slots):
           s['scope_pipeline_context_v1']=dict(slots=slots,selected=selected,speakers=sorted(speakers),others=others)
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801101:
    """Fixed function formerly embedded in node 7801101."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801101."
    def run(self, input_text, input_json):
        return _fixed_7801101(input_text, input_json)

def _fixed_7801102(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def mx_fields(prompt):
         keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         marks=list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\n',prompt))
         if [m[1] for m in marks]!=keys:return None,keys
         return {m[1]:prompt[m.end():marks[i+1].start() if i+1<len(marks) else len(prompt)] for i,m in enumerate(marks)},keys
        def mx_join(fields,keys):return ''.join(k+':\n'+fields[k] for k in keys)
        def mx_outside(text,fn):
         parts=re.split(r'(<d>.*?</d>)',text,flags=re.S)
         return ''.join(p if i%2 else fn(p) for i,p in enumerate(parts))
        state=s.get('scope_pipeline_context_v1')
        if state:
         slots=state['slots'];selected=state['selected'];speakers=set(state['speakers']);others=state['others']
         fields,keys=mx_fields(s['prompt'])
         if fields is not None:
          before=re.findall(r'<d>.*?</d>',s['prompt'],re.S)
          old_to_new={slots.index(n)+1:selected.index(n)+1 for n in selected}
          def inactive(text):return any(int(n) not in old_to_new for n in re.findall(r'<Picture\s+(\d+)>',text))
          defs=[]
          for line in fields['subject_definitions'].split('\n'):
           m=re.match(r'\s*<Subject\s+(\d+)>',line)
           if m and m[1] in speakers:
            voice='The established off-screen speaker (S'+m[1]+') is heard only in this shot and is not shown.'
            for sentence in re.split(r'[.;]',line):
             if re.search(r'\b(?:voice|vocal|timbre|pitch|accent)\b',sentence,re.I) and '<Picture' not in sentence:voice+=' '+re.sub(r'<Subject\s+\d+>\s*(?:\(S\d+\))?:?','the speaker',sentence).strip()+'.'
            defs.append(voice)
            for clause in re.split(r';|(?<=\.)\s+',line):
             used={int(n) for n in re.findall(r'<Picture\s+(\d+)>',clause)}
             if len(used)==1 and not inactive(clause) and not re.search(r'<Subject\s+\d+>',clause):
              defs.append('Declared visual reference: '+re.sub(r'^\s*Registered references:\s*','',clause.strip()).rstrip('.')+'.')
            continue
           defs.append(line)
          s['mx_scope_phase_v1']=dict(fields=fields,keys=keys,before=before,defs=defs)
         else:
          s.pop('scope_pipeline_context_v1',None)
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801102:
    """Fixed function formerly embedded in node 7801102."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801102."
    def run(self, input_text, input_json):
        return _fixed_7801102(input_text, input_json)

def _fixed_7801103(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def mx_fields(prompt):
         keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         marks=list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\n',prompt))
         if [m[1] for m in marks]!=keys:return None,keys
         return {m[1]:prompt[m.end():marks[i+1].start() if i+1<len(marks) else len(prompt)] for i,m in enumerate(marks)},keys
        def mx_join(fields,keys):return ''.join(k+':\n'+fields[k] for k in keys)
        def mx_outside(text,fn):
         parts=re.split(r'(<d>.*?</d>)',text,flags=re.S)
         return ''.join(p if i%2 else fn(p) for i,p in enumerate(parts))
        mx_audit={}
        state=s.get('scope_pipeline_context_v1')
        if state:
         slots=state['slots'];selected=state['selected'];speakers=set(state['speakers']);others=state['others']
         fields=state['fields'];keys=state['keys'];before=state['before'];old_to_new={int(k):v for k,v in state['old_to_new'].items()}
         prompt=mx_join(fields,keys)
         def remap(m):
          n=int(m[1]);assert n in old_to_new,'mixin_inactive_picture_left'
          return '<Picture '+str(old_to_new[n])+'>'
         def mx_remap_text(t):return re.sub(r'<Picture\s+(\d+)>',remap,t)
         prompt=mx_outside(prompt,mx_remap_text)
         assert re.findall(r'<d>.*?</d>',prompt,re.S)==before,'mixin_dialogue_changed'
         assert set(re.findall(r'<Audio\s+\d+>',prompt))==set(re.findall(r'<Audio\s+\d+>',s['prompt'])),'mixin_audio_reference_changed'
         s['prompt']=prompt
         s['reference_scope']=dict(reason='explicit_authored_shot',version='offscreen_voice_visual_scope_v1',source_shot=s['shot']+1,available_slots=slots,selected_slots=selected,excluded_slots=[n for n in slots if n not in selected],label_mapping={str(k):v for k,v in old_to_new.items()},voice_only_subjects=sorted(speakers))
         s['voice_visual_scope']=dict(version='offscreen_voice_visual_scope_v1',excluded_identity_slots=[n for n in slots if n not in selected],voice_only_subjects=sorted(speakers),source_shot=s['shot']+1)
         nb=[]
         for b in s.get('bindings',[]):
          if b['original_slot'] not in selected:continue
          b=dict(b,local_picture=selected.index(b['original_slot'])+1)
          if set(b.get('subject_ids',[]))<=speakers:b.update(subject_ids=[],subject_roles=['scene'],roles=['declared_reference'],role='declared_reference')
          nb.append(b)
         s['bindings']=nb
         for key in ['identity_subjects','declared_subjects']:s[key]=[x for x in s.get(key,[]) if x not in speakers]
         if s.get('crop_source') not in selected or not s['identity_subjects']:s['crop_source']=0
         s['original_slots']=selected;s['slot_indices']=selected+[0]*(9-len(selected))
         for i,v in enumerate(s['slot_indices'],1):s['slot_'+str(i)]=v
         mx_audit['offscreen_scope']=dict(selected=selected,speakers=sorted(speakers))
        s.pop('scope_pipeline_context_v1',None)
        if mx_audit:s['mixin_scope_v1']=mx_audit;s['scope_pipeline_audit_v1']=mx_audit
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801103:
    """Fixed function formerly embedded in node 7801103."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801103."
    def run(self, input_text, input_json):
        return _fixed_7801103(input_text, input_json)

def _fixed_7801104(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        memo=s.pop('regex_memo_v1',{})
        def staged(site,text,live):
            table=memo.get(site,{})
            if text in table:return table[text]
            return live(text)
        def mx_fields(prompt):
         keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         marks=list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\n',prompt))
         if [m[1] for m in marks]!=keys:return None,keys
         return {m[1]:prompt[m.end():marks[i+1].start() if i+1<len(marks) else len(prompt)] for i,m in enumerate(marks)},keys
        def mx_join(fields,keys):return ''.join(k+':\n'+fields[k] for k in keys)
        def mx_outside(text,fn):
         parts=re.split(r'(<d>.*?</d>)',text,flags=re.S)
         return ''.join(p if i%2 else fn(p) for i,p in enumerate(parts))
        mx_route_ok=not s.get('raw_passthrough') and env.get('structured') and not any(s.get(k) for k in ['continuation','guide_enabled','internal_split_origin','first_frame_enabled','boundary_image_inherit'])
        mx_audit=s.pop('scope_pipeline_audit_v1',{})
        if mx_route_ok:
         detail_src=env['source'].partition('detailed_description:')[2].partition('overall_soundscape:')[0]
         blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',detail_src)
         block=blocks[s['shot']+1] if len(blocks)>s['shot']+1 else ''
         visual=re.sub(r'<d>.*?</d>','',block,flags=re.S)
         def anchor_live(visual):
          layout_anchor=re.compile(r'(?:The\s+)?(?:current\s+)?(?:shot\s+|scene\s+|clip\s+|video\s+)?(?:begins?|opens?|starts?)\s+(?:from|with|on)\s+<Picture\s+(\d+)>\s+as\s+(?:(?:its|the|a)\s+)?(?P<role>[^.\n<]{0,80}?\b(?:scene|composition|layout|background|setting)\b[^.!?\n]*)[.!?]?',re.I)
          for clause in re.split(r'(?<=[.!?])\s+|\n+',visual):
           clause=re.sub(r'^\s*\[Shot\s+\d+\]\s*','',clause).strip()
           match=layout_anchor.fullmatch(clause)
           if match:return [match[0],match[1],match['role']]
          return None
         def literal_live(visual):return bool(re.search(r"first[- ]frame|last[- ]frame|keyframe|key frame|starting (?:frame|image)|exact (?:frame|still)|首帧|尾帧|关键帧",visual,re.I))
         anchor=staged('anchor',visual,anchor_live)
         literal=staged('literal',visual,literal_live)
         empty=s.get('shot_scope',{}).get('explicit_empty')
         if anchor and not literal and not empty and int(anchor[1]) in s['original_slots']:
          fields,keys=mx_fields(s['prompt'])
          if fields is not None:
           before=re.findall(r'<d>.*?</d>',s['prompt'],re.S)
           local=s['original_slots'].index(int(anchor[1]))+1
           people=' with the described people already in place and in their opening positions' if s.get('identity_subjects') or s.get('declared_subjects') else ''
           contract='Opening reference contract: <Picture '+str(local)+'> is the declared scene and composition reference of this shot; use its physical layout and camera composition (and any identity declared for it) without displaying the photograph itself as a frame. From the very first frame, render this shot\'s described framing'+people+'; never open on the reference photograph, an empty or people-free view of the scene, or a different framing and then cut in.\n'
           authored=anchor[0]
           mapped=re.sub(r'<Picture\s+\d+>', '<Picture '+str(local)+'>',authored)
           role='Scene/layout reference for this shot: <Picture '+str(local)+'> supplies '+anchor[2].strip()+'.'
           counts={}
           for key in ['summary','detailed_description']:
            counts[key]=re.sub(r'<d>.*?</d>','',fields[key],flags=re.S).count(mapped)
            def mx_role_text(t):return t.replace(mapped,role)
            fields[key]=mx_outside(fields[key],mx_role_text)
           if not env['inventory']['audios'] and counts['summary'] and counts['detailed_description']:
            prefix='[reference generation] Render the current authored shot as a newly generated scene. '
            if fields['summary'].startswith(prefix):
             fields['summary']='One continuous shot, already established from the first frame. '+fields['summary'][len(prefix):]
            line='The first frame already shows the current described location and physical state.'
            if line not in fields['retention_analysis']:
             fields['retention_analysis']=fields['retention_analysis'].rstrip('\n')+'\n'+line+'\n'
           s['opening_layout_projection_v2']=dict(original_slot=int(anchor[1]),local_picture=local,projected_fields=counts,reference_slots_unchanged=True,duration_unchanged=True)
           fields['detailed_description']=contract+fields['detailed_description']
           fields['retention_analysis']=fields['retention_analysis'].rstrip('\n')+'\n'+contract
           prompt=mx_join(fields,keys)
           assert re.findall(r'<d>.*?</d>',prompt,re.S)==before,'anchor_dialogue_changed'
           s['prompt']=prompt
           mx_audit['opening_anchor']=dict(original_slot=int(anchor[1]),local_picture=local)
        if mx_audit:s['mixin_scope_v1']=mx_audit
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801104:
    """Fixed function formerly embedded in node 7801104."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801104."
    def run(self, input_text, input_json):
        return _fixed_7801104(input_text, input_json)

def _fixed_7801105(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        mx_route_ok=not s.get('raw_passthrough') and env.get('structured') and not any(s.get(k) for k in ['continuation','guide_enabled','internal_split_origin','first_frame_enabled','boundary_image_inherit'])
        def ds_head_a(source,available):
         try:
          if not available or len(set(available))!=len(available):return None
          clean=re.sub(r'<d>.*?</d>','',source,flags=re.S)
         except Exception:return None
         if re.search(r'(?i)\b(?:uploaded|provided|registered|reference)\s+(?:assets?|photos?|pictures?|images?|materials?)\b|\b(?:use|follow|match)\s+(?:the|this|that)\s+(?:photo|picture|image)\b',clean):return None
         if any('\u3400'<=c<='\u9fff' for c in clean):return None
         return dict(ds_phase='head_a',clean=clean)
        ds_permitted=(mx_route_ok and not env['inventory']['audios'] and not s.get('reference_scope'))
        if ds_permitted:s['source_dependency_head_v1']=ds_head_a(env.get('source',''),env['inventory']['images'])
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801105:
    """Fixed function formerly embedded in node 7801105."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801105."
    def run(self, input_text, input_json):
        return _fixed_7801105(input_text, input_json)

def _fixed_7801106(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def mx_fields(prompt):
         keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         marks=list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\n',prompt))
         if [m[1] for m in marks]!=keys:return None,keys
         return {m[1]:prompt[m.end():marks[i+1].start() if i+1<len(marks) else len(prompt)] for i,m in enumerate(marks)},keys
        def mx_join(fields,keys):return ''.join(k+':\n'+fields[k] for k in keys)
        def mx_outside(text,fn):
         parts=re.split(r'(<d>.*?</d>)',text,flags=re.S)
         return ''.join(p if i%2 else fn(p) for i,p in enumerate(parts))
        mx_route_ok=not s.get('raw_passthrough') and env.get('structured') and not any(s.get(k) for k in ['continuation','guide_enabled','internal_split_origin','first_frame_enabled','boundary_image_inherit'])
        def ds_analysis(source,available):return s.get('source_dependency_analysis_v1')
        def ds_proof(source,available,previous,shot):
         available=sorted(available)
         if sorted(previous)!=sorted(available) or len(previous)!=len(set(previous)):return None
         analysis=ds_analysis(source,available)
         try:
          if analysis is None or not 1<=shot<=len(analysis['resolved_shots']):return None
         except Exception:return None
         selected=[n for n in previous if n in analysis['keep']]
         excluded=[n for n in previous if n not in selected]
         if not selected or not excluded:return None
         return dict(reason='source_grounded_dependencies_v1',version=1,complete=True,source_text=source,source_shot=shot,available_slots=list(available),previous_slots=list(previous),selected_slots=selected,excluded_slots=excluded,label_mapping={str(i+1):selected.index(n)+1 for i,n in enumerate(previous) if n in selected},analysis=analysis,exclusion_evidence=[dict(original_slot=n,role='inventory_only_no_authored_role',source_occurrences=[],basis='complete_original_source_role_scan',inventory_present=True) for n in excluded])
        ds_permitted=(mx_route_ok and not env['inventory']['audios'] and not s.get('reference_scope'))
        if ds_permitted:
         ds_p=ds_proof(env.get('source',''),env['inventory']['images'],s['original_slots'],s['shot']+1)
         if ds_p is not None:
          ds_old=list(s['original_slots']);ds_map=ds_p['label_mapping'];ds_prompt=s['prompt']
          ds_labels={int(n) for n in re.findall(r'<Picture\s+(\d+)>',re.sub(r'<d>.*?</d>','',ds_prompt,flags=re.S))}
          if all(str(n) in ds_map for n in ds_labels) and (not s.get('crop_source') or s['crop_source'] in ds_p['selected_slots']):
           def ds_label(m):return '<Picture '+str(ds_map[m[1]])+'>'
           def ds_relabel(t):return re.sub(r'<Picture\s+(\d+)>',ds_label,t)
           ds_new=mx_outside(ds_prompt,ds_relabel)
           assert re.findall(r'<d>.*?</d>',ds_new,re.S)==re.findall(r'<d>.*?</d>',ds_prompt,re.S),'dependency_scope_dialogue_changed'
           assert re.findall(r'<Audio\s+\d+>',ds_new)==re.findall(r'<Audio\s+\d+>',ds_prompt),'dependency_scope_audio_changed'
           s['prompt']=ds_new;s['original_slots']=ds_p['selected_slots'];s['reference_scope']=ds_p
           s['slot_indices']=s['original_slots']+[0]*(9-len(s['original_slots']))
           for ds_i,ds_slot in enumerate(s['slot_indices'],1):s['slot_'+str(ds_i)]=ds_slot
           s['bindings']=[dict(b,local_picture=s['original_slots'].index(b['original_slot'])+1) for b in s.get('bindings',[]) if b['original_slot'] in s['original_slots']]
           if s.get('opening_layout_projection_v2'):
            ds_o=dict(s['opening_layout_projection_v2']);ds_o['local_picture']=s['original_slots'].index(ds_o['original_slot'])+1;s['opening_layout_projection_v2']=ds_o
           if s.get('mixin_scope_v1',{}).get('opening_anchor'):
            s['mixin_scope_v1']['opening_anchor']['local_picture']=s['original_slots'].index(s['mixin_scope_v1']['opening_anchor']['original_slot'])+1
        result=s
        s.pop('source_dependency_analysis_v1',None)
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801106:
    """Fixed function formerly embedded in node 7801106."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801106."
    def run(self, input_text, input_json):
        return _fixed_7801106(input_text, input_json)

def _fixed_7801107(input_text, input_json=""):
    result = ""
    try:
        result=json.loads(input_text)
        result.pop('visible_voice_binding_stage_v1',None)
        memo=result.pop('regex_memo_v1',{})
        def staged(site,text,live):
            table=memo.get(site,{})
            if text in table:return table[text]
            return live(text)
        def owner_line(line):
         definition = re.match(r'^\s*-?\s*<Subject\s+(\d+)>\s*(?:\(S\d+\))?\s*:',line)
         if not definition: return None
         sid = definition[1]
         if set(re.findall(r'<Subject\s+(\d+)>',line)) != {sid}:return None
         clauses = re.findall(r'\b(?:voice|vocal|timbre)\b[^.!?\n]*<Audio\s+\d+>[^.!?\n]*',line,re.I)
         aliases = set(re.findall(r'\(S(\d+)\)',line))
         refs = set(re.findall(r'<Audio\s+(\d+)>',line))
         if len(clauses)!=1 or len(refs)!=1 or len(aliases)!=1:return None
         if re.search(r'\b(?:not|no|never|without|except|exclude|unassigned)\b|不|未|禁止',clauses[0],re.I):return None
         if any(q in clauses[0] for q in ['"',"'",'“','”','‘','’']):return None
         return [sid, int(list(refs)[0]), list(aliases)[0]]
        def stage_visible_reference_utterances(payload, context):
         out = dict(payload)
         segment, env = context['segment'], context['env']
         before = payload['prompt']
         def unchanged(reason):
          return out, dict(applied=False, reason=reason)
         if not segment.get('native_audio') or any(segment.get(k) for k in
           ('raw_passthrough','visual_only','guide_enabled','continuation','internal_split_origin','voice_visual_scope')):
          return unchanged('different_or_offscreen_route')
         audios = env.get('inventory',{}).get('audios',[])
         if len(audios)<2 or audios != list(range(1,len(audios)+1)):
          return unchanged('not_dense_multiple_reference_voices')
         visible = {str(x) for x in segment.get('identity_subjects',[])}
         units, blocks = segment.get('speaker_units',[]), segment.get('source_blocks',[])
         if len(visible)<2 or not units or [u['source_block'] for u in units] != blocks:
          return unchanged('not_multiple_explicit_identities')
         if 'Utterance voice/mouth binding:' in before:
          return unchanged('already_bound')
         keys = ['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         def blank(m):return ' '*len(m[0])
         masked = re.sub(r'<d>.*?</d>',blank,before,flags=re.S)
         marks = list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\r?\n',masked))
         if [m[1] for m in marks] != keys:
          return unchanged('noncanonical_sections')
         fields = {m[1]:before[m.end():marks[i+1].start() if i+1<len(marks) else len(before)] for i,m in enumerate(marks)}
         source = re.sub(r'<d>.*?</d>','',env.get('source',''),flags=re.S)
         head = source.partition('summary:')[0]
         owners = {}
         for line in head.splitlines():
          owned = staged('owner_line',line,owner_line)
          if owned is None: continue
          sid = owned[0]
          owner = (owned[1], owned[2])
          if sid in owners and owners[sid] != owner:return unchanged('conflicting_declarations')
          owners[sid] = owner
         if not visible <= set(owners) or len({owners[s][0] for s in visible})<2:
          return unchanged('unproven_multiple_voice_owners')
         return out, dict(owners=owners,fields=fields)
        staged, visible_voice_binding_stage = stage_visible_reference_utterances(result,json.loads(input_json))
        if visible_voice_binding_stage.get('owners') is not None:result['visible_voice_binding_stage_v1']=visible_voice_binding_stage
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801107:
    """Fixed function formerly embedded in node 7801107."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801107."
    def run(self, input_text, input_json):
        return _fixed_7801107(input_text, input_json)

def _fixed_7801111(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        s.pop('opening_layout_hold_v1',None)
        if not env['inventory']['audios'] and not s.get('raw_passthrough') and (env['structured'] or env['normalize']):
            # Opening-layout clause anchors (dialogue blanked). Official 720013 keeps its own legacy anchors.
            layout_anchor = re.compile(r'(?:The\s+)?(?:current\s+)?(?:shot\s+|scene\s+|clip\s+|video\s+)?(?:begins?|opens?|starts?)\s+(?:from|with|on)\s+<Picture\s+(\d+)>\s+as\s+(?:(?:its|the|a)\s+)?[^.\n<]{0,80}?\b(?:scene|composition|layout|background|setting)\b[^.!?\n]*[.!?]?',re.I)
            def blank_dialogue(m):return re.sub(r'[^\n]',' ',m[0])
            layout_source=re.sub(r'<d>.*?</d>',blank_dialogue,env['source'],flags=re.S)
            anchors=set()
            for clean in layout_source.splitlines():
                for clause in re.split(r'(?<=[.!?])\s+',clean):
                    clause=re.sub(r'^\s*\[Shot\s+\d+\]\s*','',clause).strip()
                    match=layout_anchor.fullmatch(clause)
                    if match:anchors.add(int(match[1]))
            held=[]
            for i,b in enumerate(s.get('bindings',[])):
                if b['roles']==['speaker_identity'] and len(b['subject_ids'])==1 and b['original_slot'] in anchors:
                    b['roles']=['speaker_identity','opening_layout_hold_v1'];held.append(i)
            if held:s['opening_layout_hold_v1']=held
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801111:
    """Fixed function formerly embedded in node 7801111."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801111."
    def run(self, input_text, input_json):
        return _fixed_7801111(input_text, input_json)

def _fixed_7801112(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        for i in s.pop('opening_layout_hold_v1',[]):
            assert s['bindings'][i]['roles']==['speaker_identity','opening_layout_hold_v1'],'opening_layout_hold_lost'
            s['bindings'][i]['roles']=['speaker_identity']
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801112:
    """Fixed function formerly embedded in node 7801112."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801112."
    def run(self, input_text, input_json):
        return _fixed_7801112(input_text, input_json)

def _fixed_7801121(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_head_a(source,available):
         try:
          if not available or len(set(available))!=len(available):return None
          clean=re.sub(r'<d>.*?</d>','',source,flags=re.S)
         except Exception:return None
         if re.search(r'(?i)\b(?:uploaded|provided|registered|reference)\s+(?:assets?|photos?|pictures?|images?|materials?)\b|\b(?:use|follow|match)\s+(?:the|this|that)\s+(?:photo|picture|image)\b',clean):return None
         if any('\u3400'<=c<='\u9fff' for c in clean):return None
         return dict(ds_phase='head_a',clean=clean)
        proof=s.get('reference_scope',{})
        staged=[]
        try:
         if proof.get('reason')=='source_grounded_dependencies_v1':
          available=sorted(e['inventory']['images']);staged=[dict(source=proof['source_text'],available=available,head=ds_head_a(proof['source_text'],available))]
        except Exception:staged=[]
        s['ds_guard_analysis_v1']=staged
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801121:
    """Fixed function formerly embedded in node 7801121."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801121."
    def run(self, input_text, input_json):
        return _fixed_7801121(input_text, input_json)

def _fixed_7801123(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_analysis_tail(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors'];evidence=head['evidence']
         resolved=[]
         safe_caps=set('The A An In On At With From To He She They It His Her Their This That These Those While As After Before During Use Uses Keep Preserve Retain Only Cut Camera Scene Shot Close Medium Wide Extreme POV MCU ECU One Continuous N A'.split())
         for index,row in enumerate(head['tail_rows'],1):
          found=set(row['found'])
          for sid in row['sids']:
           ident=sid[0] or sid[1]
           if ident not in {a['subject'] for a in actors}:return None
           found.add(ident)
          if any(w not in safe_caps for w in row['caps']):return None
          if row['people']:return None
          for obj in row['objects']:
           if obj.lower() not in {'resolved_subject','the','a','an','his','her','their','its','this','that','him','them'}:return None
          starts=set(w.lower() for w in safe_caps).union({'resolved_subject','while','speaks','says','asks','whispers','shouts'})
          for sentence in re.split(r'(?<=[.!?])\s+|\n+',row['text']):
           sentence=re.sub(r'^\s*(?:At\s+)?[0-9:. ,–-]+','',sentence).strip()
           word=re.match(r'([A-Za-z_]+)',sentence)
           if word and word[1].lower() not in starts:return None
          if not found:return None
          resolved.append(dict(shot=index,subjects=sorted(found),source=row['block'].strip()))
         authored=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',clean)})
         if not authored or not set(authored)<=set(available):return None
         pictures=list(re.finditer(r'<Picture\s+(\d+)>',clean))
         for n in authored:
          hits=[]
          for m in [x for x in pictures if x[1]==str(n)]:
           start=max(clean.rfind('\n',0,m.start())+1,0);end=clean.find('\n',m.end());end=len(clean) if end<0 else end
           hits.append(dict(start=m.start(),end=m.end(),source=clean[start:end]))
          evidence.append(dict(role='authored_reference_retained',slots=[n],occurrences=hits))
         return dict(version='conservative_all_authored_roles_v1',keep=authored,actors=actors,resolved_shots=resolved,role_evidence=evidence,audio_dependencies=[],exclusion_policy='inventory_only_and_no_authored_role')
        staged=[]
        for entry in s.get('ds_guard_analysis_v1',[]):
         try:staged.append(dict(source=entry['source'],available=entry['available'],analysis=ds_analysis_tail(entry['head'],entry['available'])))
         except Exception:staged.append(None)
        s['ds_guard_analysis_v1']=staged
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801123:
    """Fixed function formerly embedded in node 7801123."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801123."
    def run(self, input_text, input_json):
        return _fixed_7801123(input_text, input_json)

def _fixed_7801122(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_analysis(source,available):
         for entry in staged:
          if entry is not None and entry['source']==source and entry['available']==available:return entry['analysis']
         raise Exception('ds_guard_analysis_missing')
        def ds_proof(source,available,previous,shot):
         available=sorted(available)
         if sorted(previous)!=sorted(available) or len(previous)!=len(set(previous)):return None
         analysis=ds_analysis(source,available)
         try:
          if analysis is None or not 1<=shot<=len(analysis['resolved_shots']):return None
         except Exception:return None
         selected=[n for n in previous if n in analysis['keep']]
         excluded=[n for n in previous if n not in selected]
         if not selected or not excluded:return None
         return dict(reason='source_grounded_dependencies_v1',version=1,complete=True,source_text=source,source_shot=shot,available_slots=list(available),previous_slots=list(previous),selected_slots=selected,excluded_slots=excluded,label_mapping={str(i+1):selected.index(n)+1 for i,n in enumerate(previous) if n in selected},analysis=analysis,exclusion_evidence=[dict(original_slot=n,role='inventory_only_no_authored_role',source_occurrences=[],basis='complete_original_source_role_scan',inventory_present=True) for n in excluded])
        def ds_valid(proof,slots,available,source=None):
         try:
          if proof.get('reason')!='source_grounded_dependencies_v1':return False
          if source is not None and proof.get('source_text')!=source:return False
          expected=ds_proof(proof['source_text'],available,proof['previous_slots'],proof['source_shot'])
          return expected is not None and proof==expected and proof['selected_slots']==slots
         except Exception:return False
        staged=s.pop('ds_guard_analysis_v1',[])
        s['ds_guard_verdict_v1']=ds_valid(s.get('reference_scope',{}),s['original_slots'],e['inventory']['images'],e.get('source'))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801122:
    """Fixed function formerly embedded in node 7801122."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801122."
    def run(self, input_text, input_json):
        return _fixed_7801122(input_text, input_json)

def _fixed_7801131(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_head_a(source,available):
         try:
          if not available or len(set(available))!=len(available):return None
          clean=re.sub(r'<d>.*?</d>','',source,flags=re.S)
         except Exception:return None
         if re.search(r'(?i)\b(?:uploaded|provided|registered|reference)\s+(?:assets?|photos?|pictures?|images?|materials?)\b|\b(?:use|follow|match)\s+(?:the|this|that)\s+(?:photo|picture|image)\b',clean):return None
         if any('\u3400'<=c<='\u9fff' for c in clean):return None
         return dict(ds_phase='head_a',clean=clean)
        proof=s.get('reference_scope',{})
        staged=[]
        try:
         if proof.get('reason')=='source_grounded_dependencies_v1':
          available=sorted(env['inventory']['images']);staged=[dict(source=proof['source_text'],available=available,head=ds_head_a(proof['source_text'],available))]
        except Exception:staged=[]
        s['ds_guard_analysis_v1']=staged
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801131:
    """Fixed function formerly embedded in node 7801131."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801131."
    def run(self, input_text):
        return _fixed_7801131(input_text, "")

def _fixed_7801133(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_analysis_tail(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors'];evidence=head['evidence']
         resolved=[]
         safe_caps=set('The A An In On At With From To He She They It His Her Their This That These Those While As After Before During Use Uses Keep Preserve Retain Only Cut Camera Scene Shot Close Medium Wide Extreme POV MCU ECU One Continuous N A'.split())
         for index,row in enumerate(head['tail_rows'],1):
          found=set(row['found'])
          for sid in row['sids']:
           ident=sid[0] or sid[1]
           if ident not in {a['subject'] for a in actors}:return None
           found.add(ident)
          if any(w not in safe_caps for w in row['caps']):return None
          if row['people']:return None
          for obj in row['objects']:
           if obj.lower() not in {'resolved_subject','the','a','an','his','her','their','its','this','that','him','them'}:return None
          starts=set(w.lower() for w in safe_caps).union({'resolved_subject','while','speaks','says','asks','whispers','shouts'})
          for sentence in re.split(r'(?<=[.!?])\s+|\n+',row['text']):
           sentence=re.sub(r'^\s*(?:At\s+)?[0-9:. ,–-]+','',sentence).strip()
           word=re.match(r'([A-Za-z_]+)',sentence)
           if word and word[1].lower() not in starts:return None
          if not found:return None
          resolved.append(dict(shot=index,subjects=sorted(found),source=row['block'].strip()))
         authored=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',clean)})
         if not authored or not set(authored)<=set(available):return None
         pictures=list(re.finditer(r'<Picture\s+(\d+)>',clean))
         for n in authored:
          hits=[]
          for m in [x for x in pictures if x[1]==str(n)]:
           start=max(clean.rfind('\n',0,m.start())+1,0);end=clean.find('\n',m.end());end=len(clean) if end<0 else end
           hits.append(dict(start=m.start(),end=m.end(),source=clean[start:end]))
          evidence.append(dict(role='authored_reference_retained',slots=[n],occurrences=hits))
         return dict(version='conservative_all_authored_roles_v1',keep=authored,actors=actors,resolved_shots=resolved,role_evidence=evidence,audio_dependencies=[],exclusion_policy='inventory_only_and_no_authored_role')
        staged=[]
        for entry in s.get('ds_guard_analysis_v1',[]):
         try:staged.append(dict(source=entry['source'],available=entry['available'],analysis=ds_analysis_tail(entry['head'],entry['available'])))
         except Exception:staged.append(None)
        s['ds_guard_analysis_v1']=staged
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801133:
    """Fixed function formerly embedded in node 7801133."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801133."
    def run(self, input_text):
        return _fixed_7801133(input_text, "")

def _fixed_7801132(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_analysis(source,available):
         for entry in staged:
          if entry is not None and entry['source']==source and entry['available']==available:return entry['analysis']
         raise Exception('ds_guard_analysis_missing')
        def ds_proof(source,available,previous,shot):
         available=sorted(available)
         if sorted(previous)!=sorted(available) or len(previous)!=len(set(previous)):return None
         analysis=ds_analysis(source,available)
         try:
          if analysis is None or not 1<=shot<=len(analysis['resolved_shots']):return None
         except Exception:return None
         selected=[n for n in previous if n in analysis['keep']]
         excluded=[n for n in previous if n not in selected]
         if not selected or not excluded:return None
         return dict(reason='source_grounded_dependencies_v1',version=1,complete=True,source_text=source,source_shot=shot,available_slots=list(available),previous_slots=list(previous),selected_slots=selected,excluded_slots=excluded,label_mapping={str(i+1):selected.index(n)+1 for i,n in enumerate(previous) if n in selected},analysis=analysis,exclusion_evidence=[dict(original_slot=n,role='inventory_only_no_authored_role',source_occurrences=[],basis='complete_original_source_role_scan',inventory_present=True) for n in excluded])
        def ds_valid(proof,slots,available,source=None):
         try:
          if proof.get('reason')!='source_grounded_dependencies_v1':return False
          if source is not None and proof.get('source_text')!=source:return False
          expected=ds_proof(proof['source_text'],available,proof['previous_slots'],proof['source_shot'])
          return expected is not None and proof==expected and proof['selected_slots']==slots
         except Exception:return False
        staged=s.pop('ds_guard_analysis_v1',[])
        s['ds_guard_verdict_v1']=ds_valid(s.get('reference_scope',{}),s['original_slots'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801132:
    """Fixed function formerly embedded in node 7801132."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801132."
    def run(self, input_text):
        return _fixed_7801132(input_text, "")

def _fixed_7801141(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_head_a(source,available):
         try:
          if not available or len(set(available))!=len(available):return None
          clean=re.sub(r'<d>.*?</d>','',source,flags=re.S)
         except Exception:return None
         if re.search(r'(?i)\b(?:uploaded|provided|registered|reference)\s+(?:assets?|photos?|pictures?|images?|materials?)\b|\b(?:use|follow|match)\s+(?:the|this|that)\s+(?:photo|picture|image)\b',clean):return None
         if any('\u3400'<=c<='\u9fff' for c in clean):return None
         return dict(ds_phase='head_a',clean=clean)
        staged=[]
        for i,r in enumerate(state['records']):
         entry=None
         try:
          proof=r.get('reference_scope',{})
          if proof.get('reason')=='source_grounded_dependencies_v1':
           available=sorted(p['segments'][i]['original_slots']);entry=dict(source=proof['source_text'],available=available,head=ds_head_a(proof['source_text'],available))
         except Exception:entry=None
         staged.append(entry)
        state['ds_guard_analysis_v1']=staged
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801141:
    """Fixed function formerly embedded in node 7801141."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801141."
    def run(self, input_text, input_json):
        return _fixed_7801141(input_text, input_json)

def _fixed_7801143(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_analysis_tail(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors'];evidence=head['evidence']
         resolved=[]
         safe_caps=set('The A An In On At With From To He She They It His Her Their This That These Those While As After Before During Use Uses Keep Preserve Retain Only Cut Camera Scene Shot Close Medium Wide Extreme POV MCU ECU One Continuous N A'.split())
         for index,row in enumerate(head['tail_rows'],1):
          found=set(row['found'])
          for sid in row['sids']:
           ident=sid[0] or sid[1]
           if ident not in {a['subject'] for a in actors}:return None
           found.add(ident)
          if any(w not in safe_caps for w in row['caps']):return None
          if row['people']:return None
          for obj in row['objects']:
           if obj.lower() not in {'resolved_subject','the','a','an','his','her','their','its','this','that','him','them'}:return None
          starts=set(w.lower() for w in safe_caps).union({'resolved_subject','while','speaks','says','asks','whispers','shouts'})
          for sentence in re.split(r'(?<=[.!?])\s+|\n+',row['text']):
           sentence=re.sub(r'^\s*(?:At\s+)?[0-9:. ,–-]+','',sentence).strip()
           word=re.match(r'([A-Za-z_]+)',sentence)
           if word and word[1].lower() not in starts:return None
          if not found:return None
          resolved.append(dict(shot=index,subjects=sorted(found),source=row['block'].strip()))
         authored=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',clean)})
         if not authored or not set(authored)<=set(available):return None
         pictures=list(re.finditer(r'<Picture\s+(\d+)>',clean))
         for n in authored:
          hits=[]
          for m in [x for x in pictures if x[1]==str(n)]:
           start=max(clean.rfind('\n',0,m.start())+1,0);end=clean.find('\n',m.end());end=len(clean) if end<0 else end
           hits.append(dict(start=m.start(),end=m.end(),source=clean[start:end]))
          evidence.append(dict(role='authored_reference_retained',slots=[n],occurrences=hits))
         return dict(version='conservative_all_authored_roles_v1',keep=authored,actors=actors,resolved_shots=resolved,role_evidence=evidence,audio_dependencies=[],exclusion_policy='inventory_only_and_no_authored_role')
        staged=[]
        for entry in state.get('ds_guard_analysis_v1',[]):
         try:staged.append(dict(source=entry['source'],available=entry['available'],analysis=ds_analysis_tail(entry['head'],entry['available'])))
         except Exception:staged.append(None)
        state['ds_guard_analysis_v1']=staged
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801143:
    """Fixed function formerly embedded in node 7801143."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801143."
    def run(self, input_text, input_json):
        return _fixed_7801143(input_text, input_json)

def _fixed_7801142(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_analysis(source,available):
         for entry in staged:
          if entry is not None and entry['source']==source and entry['available']==available:return entry['analysis']
         raise Exception('ds_guard_analysis_missing')
        def ds_proof(source,available,previous,shot):
         available=sorted(available)
         if sorted(previous)!=sorted(available) or len(previous)!=len(set(previous)):return None
         analysis=ds_analysis(source,available)
         try:
          if analysis is None or not 1<=shot<=len(analysis['resolved_shots']):return None
         except Exception:return None
         selected=[n for n in previous if n in analysis['keep']]
         excluded=[n for n in previous if n not in selected]
         if not selected or not excluded:return None
         return dict(reason='source_grounded_dependencies_v1',version=1,complete=True,source_text=source,source_shot=shot,available_slots=list(available),previous_slots=list(previous),selected_slots=selected,excluded_slots=excluded,label_mapping={str(i+1):selected.index(n)+1 for i,n in enumerate(previous) if n in selected},analysis=analysis,exclusion_evidence=[dict(original_slot=n,role='inventory_only_no_authored_role',source_occurrences=[],basis='complete_original_source_role_scan',inventory_present=True) for n in excluded])
        def ds_valid(proof,slots,available,source=None):
         try:
          if proof.get('reason')!='source_grounded_dependencies_v1':return False
          if source is not None and proof.get('source_text')!=source:return False
          expected=ds_proof(proof['source_text'],available,proof['previous_slots'],proof['source_shot'])
          return expected is not None and proof==expected and proof['selected_slots']==slots
         except Exception:return False
        all_staged=state.pop('ds_guard_analysis_v1',[])
        verdicts=[]
        for i,r in enumerate(state['records']):
         staged=all_staged[i:i+1]
         try:verdicts.append(ds_valid(r.get('reference_scope',{}),r['original_slots'],p['segments'][i]['original_slots']) is True)
         except Exception:verdicts.append(False)
        state['ds_guard_verdicts_v1']=verdicts
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801142:
    """Fixed function formerly embedded in node 7801142."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801142."
    def run(self, input_text, input_json):
        return _fixed_7801142(input_text, input_json)

def _fixed_7801113(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def ds_analysis_tail(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors'];evidence=head['evidence']
         resolved=[]
         safe_caps=set('The A An In On At With From To He She They It His Her Their This That These Those While As After Before During Use Uses Keep Preserve Retain Only Cut Camera Scene Shot Close Medium Wide Extreme POV MCU ECU One Continuous N A'.split())
         for index,row in enumerate(head['tail_rows'],1):
          found=set(row['found'])
          for sid in row['sids']:
           ident=sid[0] or sid[1]
           if ident not in {a['subject'] for a in actors}:return None
           found.add(ident)
          if any(w not in safe_caps for w in row['caps']):return None
          if row['people']:return None
          for obj in row['objects']:
           if obj.lower() not in {'resolved_subject','the','a','an','his','her','their','its','this','that','him','them'}:return None
          starts=set(w.lower() for w in safe_caps).union({'resolved_subject','while','speaks','says','asks','whispers','shouts'})
          for sentence in re.split(r'(?<=[.!?])\s+|\n+',row['text']):
           sentence=re.sub(r'^\s*(?:At\s+)?[0-9:. ,–-]+','',sentence).strip()
           word=re.match(r'([A-Za-z_]+)',sentence)
           if word and word[1].lower() not in starts:return None
          if not found:return None
          resolved.append(dict(shot=index,subjects=sorted(found),source=row['block'].strip()))
         authored=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',clean)})
         if not authored or not set(authored)<=set(available):return None
         pictures=list(re.finditer(r'<Picture\s+(\d+)>',clean))
         for n in authored:
          hits=[]
          for m in [x for x in pictures if x[1]==str(n)]:
           start=max(clean.rfind('\n',0,m.start())+1,0);end=clean.find('\n',m.end());end=len(clean) if end<0 else end
           hits.append(dict(start=m.start(),end=m.end(),source=clean[start:end]))
          evidence.append(dict(role='authored_reference_retained',slots=[n],occurrences=hits))
         return dict(version='conservative_all_authored_roles_v1',keep=authored,actors=actors,resolved_shots=resolved,role_evidence=evidence,audio_dependencies=[],exclusion_policy='inventory_only_and_no_authored_role')
        if 'source_dependency_head_v1' in s:s['source_dependency_analysis_v1']=ds_analysis_tail(s.pop('source_dependency_head_v1'),env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801113:
    """Fixed function formerly embedded in node 7801113."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801113."
    def run(self, input_text, input_json):
        return _fixed_7801113(input_text, input_json)

def _fixed_7801108(input_text, input_json=""):
    result = ""
    try:
        result=json.loads(input_text)
        stage=result.pop('visible_voice_binding_stage_v1',None)
        def bind_visible_reference_utterances(payload, context):
         out = dict(payload)
         segment, env = context['segment'], context['env']
         before = payload['prompt']
         def unchanged(reason):
          return out, dict(applied=False, reason=reason)
         if stage is None:
          return unchanged('not_staged_by_visible_voice_gate')
         audios = env.get('inventory',{}).get('audios',[])
         visible = {str(x) for x in segment.get('identity_subjects',[])}
         units = segment.get('speaker_units',[])
         keys = ['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         fields = stage['fields']
         owners = {k:(v[0],v[1]) for k,v in stage['owners'].items()}
         body = fields['detailed_description']
         prose = re.sub(r'<d>.*?</d>','',body,flags=re.S)
         if re.search(r'off[ -]?screen|voice[ -]?over|out of frame|unseen|画外|旁白|不出镜',prose,re.I):
          return unchanged('offscreen_authorship')
         dialogues = list(re.finditer(r'<d>.*?</d>',body,re.S))
         if len(dialogues)!=len(units) or [m[0] for m in dialogues] != re.findall(r'<d>.*?</d>',segment['prompt'],re.S):
          return unchanged('nonexact_utterance_scope')
         edits=[];bindings=[]
         for unit, d in zip(units,dialogues):
          line_start = body.rfind('\n',0,d.start())+1
          prefix = body[line_start:d.start()]
          label = re.fullmatch(r'[ \t]*<Subject\s+(\d+)>\s*\(S(\d+)\)\s*(?::\s*|speaks\b[^\n<>]*:\s*)',prefix)
          if not label:return unchanged('no_positive_local_speaker_label')
          sid, alias = label[1],label[2]
          if sid not in visible or sid != str(unit['subject']) or owners.get(sid) != (unit['voice'],alias) or unit['voice'] not in audios:
           return unchanged('local_unit_definition_disagreement')
          audio = str(unit['voice'])
          defs = [line for line in fields['subject_definitions'].splitlines() if re.match(r'^\s*-?\s*<Subject\s+'+re.escape(sid)+r'>\s*(?:\(S\d+\))?\s*:',line)]
          if len(defs)!=1 or set(re.findall(r'<Audio\s+(\d+)>',defs[0])) != {audio}:
           return unchanged('final_definition_disagreement')
          cue = ('Utterance voice/mouth binding: <Subject '+sid+'> (S'+alias+') alone delivers the following written line using the vocal timbre of <Audio '+audio+'>. Synchronize this line\'s syllables only to <Subject '+sid+'>\'s mouth; other visible characters are listeners, not speakers of this line. Preserve separately authored non-speech reactions and shared laughter.\n')
          edits.append((line_start,cue));bindings.append(dict(source_block=unit['source_block'],subject=sid,speaker=alias,audio=unit['voice']))
         for pos,cue in edits[::-1]:body=body[:pos]+cue+body[pos:]
         fields['detailed_description']=body
         old = 'Generate synchronized native voice and mouth motion using the same speaker identity and natural delivery as the uploaded voice reference.'
         if fields['overall_soundscape'].count(old)!=1:
          return unchanged('unrecognized_native_guard')
         new = 'Generate synchronized native voice and mouth motion according to each local utterance voice/mouth binding above. Each referenced audio supplies only its declared character\'s timbre, never the other character\'s speech or mouth motion.'
         fields['overall_soundscape']=fields['overall_soundscape'].replace(old,new,1)
         after=''.join(k+':\n'+fields[k] for k in keys)
         assert re.findall(r'<d>.*?</d>',after,re.S)==re.findall(r'<d>.*?</d>',before,re.S), 'VISIBLE_VOICE_DIALOGUE_CHANGED'
         assert set(re.findall(r'<(?:Picture|Audio|Video|Subject)\s+\d+>',after)) == set(re.findall(r'<(?:Picture|Audio|Video|Subject)\s+\d+>',before)), 'VISIBLE_VOICE_REFERENCE_CHANGED'
         out['prompt']=after
         return out,dict(applied=True,version='explicit_visible_voice_mouth_v1',bindings=bindings,audio_tensors_unchanged=True)
        result, visible_voice_binding_audit = bind_visible_reference_utterances(result,json.loads(input_json))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801108:
    """Fixed function formerly embedded in node 7801108."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801108."
    def run(self, input_text, input_json):
        return _fixed_7801108(input_text, input_json)

def _fixed_7801501(input_text, input_json=""):
    result = ""
    try:
        result=input_text
        try:
            p=json.loads(input_text)
            def clock(token):
                parts=token.replace('：',':').split(':')
                assert len(parts)<=2, 'invalid_authored_clock'
                seconds=float(parts[-1])
                if len(parts)==2:
                    assert seconds<60, 'invalid_authored_clock'
                    seconds+=60*float(parts[0])
                return seconds
            def parser_view(raw):
                body=re.sub(r'<d>.*?</d>','',raw,flags=re.S)
                body=re.sub(r'^\s*\[Shot\s+\d+\]\s*','',body,flags=re.I)
                # Normalize only the parser view, never submitted source or spoken text.
                beat=re.match(r'^(?:At\s+\d+(?::\d+)?(?:\.\d+)?\s*,\s*)?Beat\s+\d+\s*[—–:-]\s*(\d+(?::\d+)?(?:\.\d+)?)\s*[–—-]\s*(\d+(?::\d+)?(?:\.\d+)?)\s*:',body,re.I)
                if beat:
                    leading=re.match(r'^At\s+(\d+(?::\d+)?(?:\.\d+)?)',body,re.I)
                    if leading:assert clock(leading[1])==clock(beat[1]), 'conflicting_beat_start'
                    body=beat[1]+' to '+beat[2]+', '+body[beat.end():]
                return body
            views={}
            for shot in p['shots']:
                try:views[shot['body']]=parser_view(shot['body'])
                except Exception:pass
            p['regex_memo_v1']=dict(view=views)
            result=p
        except Exception:result=input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801501:
    """Fixed function formerly embedded in node 7801501."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801501."
    def run(self, input_text):
        return _fixed_7801501(input_text, "")

def _fixed_7801502(input_text, input_json=""):
    result = ""
    try:
        result=input_text
        try:
            p=json.loads(input_text);memo=p['regex_memo_v1']
            number=r'\d+(?:[:：]\d+)?(?:\.\d+)?'
            span=r'^(?:(?:From|Between)\s+)?('+number+r')\s*(?:seconds?\b|s\b|秒)?\s*(?:to|and|[-–—到至])\s*('+number+r')\s*(?:seconds?\b|s\b|秒)?'
            def span_view(body):
                m=re.match(span,body,re.I)
                return [m[0],m[1],m[2],m.end()] if m else None
            def duration_view(summary):
                return re.sub(r'\b((?:total\s+)?duration)\s+of\s+(\d+(?::\d+)?(?:\.\d+)?)\s*(seconds?\b|s\b)?',r'\1 is \2 \3',summary,flags=re.I)
            memo['span']={body:span_view(body) for body in memo['view'].values()}
            if p.get('mode')=='without_voice' and 'summary:' in p['header']:
                head,sep,rest=p['header'].partition('summary:')
                summary,sep2,retention=rest.partition('retention_analysis:')
                memo['duration']={summary:duration_view(summary)}
            result=p
        except Exception:result=input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801502:
    """Fixed function formerly embedded in node 7801502."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801502."
    def run(self, input_text):
        return _fixed_7801502(input_text, "")

def _fixed_7801511(input_text, input_json=""):
    result = ""
    try:
        w=input_text;memo={}
        if w.lstrip().startswith('{'):
            staged_input=json.loads(w);memo=staged_input['regex_memo_v1'];w=staged_input['input_text']
        result=input_text
        try:
            p=json.loads(input_json);i=int(w)
            derived=memo.get('derive',{})
            if not derived:
                for k in [i,i+1]:
                    if 0<=k<len(p['segments']):
                        provenance=p['segments'][k].get('action_provenance',[])
                        if provenance:
                            raw=provenance[0].get('original_action','')
                            action=re.sub(r'<d>.*?</d>','',raw,flags=re.S)
                            derived[raw]=[action,re.split(r'[;。\n]|(?<!\d)\.(?!\d)',action)]
            memo['derive']=derived
            actions=[v[0] for v in derived.values()];clauses=[c for v in derived.values() for c in v[1]]
            memo['conflict0']={a:bool(re.search(r'\b(?:cut|switch|reset|change|pull\s+back|zoom\s+out)\s+(?:\w+\s+){0,3}(?:to\s+)?(?:a\s+)?(?:wide|close[- ]?up|medium|full[- ]body|long\s+shot|different\s+(?:framing|scene|room)|new\s+(?:scene|room))\b',a,re.I)) for a in actions}
            result=json.dumps(dict(input_text=w,regex_memo_v1=memo),ensure_ascii=False)
        except Exception:result=input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801511:
    """Fixed function formerly embedded in node 7801511."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801511."
    def run(self, input_text, input_json):
        return _fixed_7801511(input_text, input_json)

def _fixed_7801512(input_text, input_json=""):
    result = ""
    try:
        w=input_text;memo={}
        if w.lstrip().startswith('{'):
            staged_input=json.loads(w);memo=staged_input['regex_memo_v1'];w=staged_input['input_text']
        result=input_text
        try:
            p=json.loads(input_json);i=int(w)
            derived=memo.get('derive',{})
            if not derived:
                for k in [i,i+1]:
                    if 0<=k<len(p['segments']):
                        provenance=p['segments'][k].get('action_provenance',[])
                        if provenance:
                            raw=provenance[0].get('original_action','')
                            action=re.sub(r'<d>.*?</d>','',raw,flags=re.S)
                            derived[raw]=[action,re.split(r'[;。\n]|(?<!\d)\.(?!\d)',action)]
            memo['derive']=derived
            actions=[v[0] for v in derived.values()];clauses=[c for v in derived.values() for c in v[1]]
            memo['anchor']={a:bool(re.search(r'(?:current shot begins from|first[- ]frame|keyframe|composition anchor).{0,40}<Picture\s+\d+>',a,re.I)) for a in actions}
            memo['conflict']={a:memo['conflict0'][a] or bool(re.search(r'(?:切换|切到|改为|拉回|拉远|换成).{0,10}(?:全景|远景|全身|近景|中景|新场景|另一场景)',a,re.I)) or bool(re.search(r'(?:different|new)\s+(?:location|room|scene)\b',a,re.I)) or bool(re.search(r'换场|换装',a,re.I)) for a in actions}
            result=json.dumps(dict(input_text=w,regex_memo_v1=memo),ensure_ascii=False)
        except Exception:result=input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801512:
    """Fixed function formerly embedded in node 7801512."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801512."
    def run(self, input_text, input_json):
        return _fixed_7801512(input_text, input_json)

def _fixed_7801513(input_text, input_json=""):
    result = ""
    try:
        w=input_text;memo={}
        if w.lstrip().startswith('{'):
            staged_input=json.loads(w);memo=staged_input['regex_memo_v1'];w=staged_input['input_text']
        result=input_text
        try:
            p=json.loads(input_json);i=int(w)
            derived=memo.get('derive',{})
            if not derived:
                for k in [i,i+1]:
                    if 0<=k<len(p['segments']):
                        provenance=p['segments'][k].get('action_provenance',[])
                        if provenance:
                            raw=provenance[0].get('original_action','')
                            action=re.sub(r'<d>.*?</d>','',raw,flags=re.S)
                            derived[raw]=[action,re.split(r'[;。\n]|(?<!\d)\.(?!\d)',action)]
            memo['derive']=derived
            actions=[v[0] for v in derived.values()];clauses=[c for v in derived.values() for c in v[1]]
            memo['neg']={c:bool(re.search(r"""\b(?:not|never|avoid|without)\b|don't|do not|不要|不继承|不沿用|不承接|不保持""",c,re.I)) for c in clauses}
            previous_end=r'(?:previous|preceding)\s+(?:shot|take)(?:[’\x27]s)?'
            dimension=r'(?:framing|distance|shot\s+size|camera\s+distance)'
            memo['english3']={c:bool(re.search(r'\binherit(?:ed|s|ing)?\b',c,re.I) and re.search(previous_end,c,re.I) and re.search(dimension,c,re.I)) for c in clauses}
            result=json.dumps(dict(input_text=w,regex_memo_v1=memo),ensure_ascii=False)
        except Exception:result=input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801513:
    """Fixed function formerly embedded in node 7801513."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801513."
    def run(self, input_text, input_json):
        return _fixed_7801513(input_text, input_json)

def _fixed_7801514(input_text, input_json=""):
    result = ""
    try:
        w=input_text;memo={}
        if w.lstrip().startswith('{'):
            staged_input=json.loads(w);memo=staged_input['regex_memo_v1'];w=staged_input['input_text']
        result=input_text
        try:
            p=json.loads(input_json);i=int(w)
            derived=memo.get('derive',{})
            if not derived:
                for k in [i,i+1]:
                    if 0<=k<len(p['segments']):
                        provenance=p['segments'][k].get('action_provenance',[])
                        if provenance:
                            raw=provenance[0].get('original_action','')
                            action=re.sub(r'<d>.*?</d>','',raw,flags=re.S)
                            derived[raw]=[action,re.split(r'[;。\n]|(?<!\d)\.(?!\d)',action)]
            memo['derive']=derived
            actions=[v[0] for v in derived.values()];clauses=[c for v in derived.values() for c in v[1]]
            previous_end=r'(?:previous|preceding)\s+(?:shot|take)(?:[’\x27]s)?'
            dimension=r'(?:framing|distance|shot\s+size|camera\s+distance)'
            memo['english']={c:memo['english3'][c] or bool(re.search(r'\b(?:match|maintain|preserve|keep)\b.{0,90}'+previous_end+r'.{0,35}(?:final|ending|end).{0,35}'+dimension,c,re.I)) for c in clauses}
            memo['chinese']={c:bool(re.search(r'(?:继承|承接|沿用|保持).{0,20}(?:上一镜|前一镜|前镜).{0,15}(?:结束|末尾|结尾|最终).{0,12}(?:景别|距离|构图)',c)) for c in clauses}
            result=json.dumps(dict(input_text=w,regex_memo_v1=memo),ensure_ascii=False)
        except Exception:result=input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801514:
    """Fixed function formerly embedded in node 7801514."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801514."
    def run(self, input_text, input_json):
        return _fixed_7801514(input_text, input_json)

def _fixed_7801521(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        try:
            memo=s.get('regex_memo_v1',{})
            units=s.get('speaker_units',[]);prov={a['source_block']:a['original_action'] for a in s.get('action_provenance',[])}
            labels=[];visual=''
            for u in units:
                action=re.sub(r'<d>.*?</d>','',prov.get(u['source_block'],''),flags=re.S)
                lines=[x for x in action.split('\n') if x.strip()]
                labels.append(lines[-1] if lines else '');visual+='\n'.join(lines[:-1])+'\n'
            offscreen_src=r"\boff[- ]?screen\s+(?:voice[- ]?over|voice|narration|narrator)\b|\bvoice[- ]?over\b|画外音|旁白"
            offscreen=re.compile(offscreen_src,re.I)
            oncam=re.compile(r"\bon[- ]?camera\b|\bto (?:the )?camera\b|\bfaces? the camera\b|\bselfie\b|对镜头|出镜",re.I)
            memo['label']={x:[bool(offscreen.search(x)),bool(oncam.search(x)),bool(re.search(r"\b(?:not|never|no)\b[^.;\n]{0,20}(?:"+offscreen_src+")",x,re.I))] for x in labels}
            s['regex_memo_v1']=memo
        except Exception:result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801521:
    """Fixed function formerly embedded in node 7801521."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801521."
    def run(self, input_text, input_json):
        return _fixed_7801521(input_text, input_json)

def _fixed_7801522(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        try:
            memo=s.get('regex_memo_v1',{})
            units=s.get('speaker_units',[]);prov={a['source_block']:a['original_action'] for a in s.get('action_provenance',[])}
            labels=[];visual=''
            for u in units:
                action=re.sub(r'<d>.*?</d>','',prov.get(u['source_block'],''),flags=re.S)
                lines=[x for x in action.split('\n') if x.strip()]
                labels.append(lines[-1] if lines else '');visual+='\n'.join(lines[:-1])+'\n'
            visual_nolabel=re.sub(r'\[Shot\s+\d+\]','',visual)
            memo['visible']={visual_nolabel:bool(re.search(r"\b(?:face|facial|head|torso|shoulders?|lips|mouth|portrait|selfie|glasses|full[- ]body|over[- ]the[- ]shoulder|eye contact|on[- ]camera|mirror|reflection|smil\w*|nods?|sits?|seated|stands?|standing|walks?|walking)\b|faces? the camera|looks? (?:at|into) the camera",visual_nolabel,re.I))}
            s['regex_memo_v1']=memo
        except Exception:result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801522:
    """Fixed function formerly embedded in node 7801522."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801522."
    def run(self, input_text, input_json):
        return _fixed_7801522(input_text, input_json)

def _fixed_7801531(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        try:
            memo=s.get('regex_memo_v1',{})
            detail_src=env['source'].partition('detailed_description:')[2].partition('overall_soundscape:')[0]
            blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',detail_src)
            block=blocks[s['shot']+1] if len(blocks)>s['shot']+1 else ''
            visual=re.sub(r'<d>.*?</d>','',block,flags=re.S)
            memo['anchor_clauses']={visual:[re.sub(r'^\s*\[Shot\s+\d+\]\s*','',clause).strip() for clause in re.split(r'(?<=[.!?])\s+|\n+',visual)]}
            memo['literal']={visual:bool(re.search(r"first[- ]frame|last[- ]frame|keyframe|key frame|starting (?:frame|image)|exact (?:frame|still)|首帧|尾帧|关键帧",visual,re.I))}
            s['regex_memo_v1']=memo
        except Exception:result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801531:
    """Fixed function formerly embedded in node 7801531."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801531."
    def run(self, input_text, input_json):
        return _fixed_7801531(input_text, input_json)

def _fixed_7801532(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        try:
            memo=s.get('regex_memo_v1',{})
            layout_anchor=re.compile(r'(?:The\s+)?(?:current\s+)?(?:shot\s+|scene\s+|clip\s+|video\s+)?(?:begins?|opens?|starts?)\s+(?:from|with|on)\s+<Picture\s+(\d+)>\s+as\s+(?:(?:its|the|a)\s+)?(?P<role>[^.\n<]{0,80}?\b(?:scene|composition|layout|background|setting)\b[^.!?\n]*)[.!?]?',re.I)
            anchors={}
            for visual,clauses in memo['anchor_clauses'].items():
                anchors[visual]=None
                for clause in clauses:
                    match=layout_anchor.fullmatch(clause)
                    if match:anchors[visual]=[match[0],match[1],match['role']];break
            memo['anchor']=anchors
            s['regex_memo_v1']=memo
        except Exception:result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801532:
    """Fixed function formerly embedded in node 7801532."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801532."
    def run(self, input_text, input_json):
        return _fixed_7801532(input_text, input_json)

def _fixed_7801581(input_text, input_json=""):
    result = ""
    try:
        result=json.loads(input_text)
        try:
            memo=result.get('regex_memo_v1',{})
            env=json.loads(input_json)['env']
            def owner_line(line):
             definition = re.match(r'^\s*-?\s*<Subject\s+(\d+)>\s*(?:\(S\d+\))?\s*:',line)
             if not definition: return None
             sid = definition[1]
             if set(re.findall(r'<Subject\s+(\d+)>',line)) != {sid}:return None
             clauses = re.findall(r'\b(?:voice|vocal|timbre)\b[^.!?\n]*<Audio\s+\d+>[^.!?\n]*',line,re.I)
             aliases = set(re.findall(r'\(S(\d+)\)',line))
             refs = set(re.findall(r'<Audio\s+(\d+)>',line))
             if len(clauses)!=1 or len(refs)!=1 or len(aliases)!=1:return None
             if re.search(r'\b(?:not|no|never|without|except|exclude|unassigned)\b|不|未|禁止',clauses[0],re.I):return None
             if any(q in clauses[0] for q in ['"',"'",'“','”','‘','’']):return None
             return [sid, int(list(refs)[0]), list(aliases)[0]]
            source=re.sub(r'<d>.*?</d>','',env.get('source',''),flags=re.S)
            memo['owner_line']={line:owner_line(line) for line in source.partition('summary:')[0].splitlines()}
            result['regex_memo_v1']=memo
        except Exception:result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801581:
    """Fixed function formerly embedded in node 7801581."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801581."
    def run(self, input_text, input_json):
        return _fixed_7801581(input_text, input_json)

def _fixed_7801591(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def mx_fields(prompt):
         keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
         marks=list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\n',prompt))
         if [m[1] for m in marks]!=keys:return None,keys
         return {m[1]:prompt[m.end():marks[i+1].start() if i+1<len(marks) else len(prompt)] for i,m in enumerate(marks)},keys
        def mx_join(fields,keys):return ''.join(k+':\n'+fields[k] for k in keys)
        def mx_outside(text,fn):
         parts=re.split(r'(<d>.*?</d>)',text,flags=re.S)
         return ''.join(p if i%2 else fn(p) for i,p in enumerate(parts))
        ph=s.get('mx_scope_phase_v1')
        if ph is not None:
         state=s['scope_pipeline_context_v1']
         slots=state['slots'];selected=state['selected'];speakers=set(state['speakers']);others=state['others']
         if True:
          fields=ph['fields'];keys=ph['keys'];before=ph['before']
          old_to_new={slots.index(n)+1:selected.index(n)+1 for n in selected}
          def inactive(text):return any(int(n) not in old_to_new for n in re.findall(r'<Picture\s+(\d+)>',text))
          def narrow(sentence):
           items=re.split(r'(,\s+(?:and\s+)?|;\s+)',sentence)
           kept=[items[0]] if not inactive(items[0]) else []
           for j in range(1,len(items),2):
            if not inactive(items[j+1]):kept.extend([items[j],items[j+1]] if kept else [items[j+1]])
           text=''.join(kept).strip()
           if text and not re.search(r'[.!?;:]$',text) and re.search(r'[.!?]$',sentence.strip()):text+='.'
           return text if text and not re.fullmatch(r'[^A-Za-z]*(?:Declared uploaded references, with their original user roles:?)?[^A-Za-z]*',text) else ''
          def notes(m):
           active=[x for x in re.findall(r'<Picture\s+\d+>',m[1]) if not inactive(x)]
           return m[0][:m.start(1)-m.start(0)]+', '.join(active)+'.' if active else ''
          def scrub(text):
           text=re.sub(r'Declared uploaded references, with their original user roles: ((?:<Picture\s+\d+>(?:,\s*)?)+)\.',notes,text)
           out=[]
           for line in text.split('\n'):
            if not inactive(line):out.append(line);continue
            pieces=re.split(r'(?<=[.])\s+',line)
            out.append(' '.join(x for x in (narrow(p) if inactive(p) else p for p in pieces) if x))
           return '\n'.join(out)
          fields['subject_definitions']=scrub('\n'.join(ph.pop('defs')))
          for k in ['summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']:
           fields[k]=mx_outside(fields[k],scrub)
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801591:
    """Fixed function formerly embedded in node 7801591."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801591."
    def run(self, input_text, input_json):
        return _fixed_7801591(input_text, input_json)

def _fixed_7801592(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        ph=s.pop('mx_scope_phase_v1',None)
        if ph is not None:
         state=s['scope_pipeline_context_v1']
         slots=state['slots'];selected=state['selected'];speakers=set(state['speakers']);others=state['others']
         if True:
          fields=ph['fields'];keys=ph['keys'];before=ph['before']
          old_to_new={slots.index(n)+1:selected.index(n)+1 for n in selected}
          ident=' Preserve the same person, facial proportions, age, hair, clothing and accessories. Compare all references assigned to each identity together.'
          fields['retention_analysis']=fields['retention_analysis'].replace(ident,' The off-screen speaker is heard only and is not shown in this shot; only body parts explicitly described here may enter the frame.' if not others else ident)
          fields['retention_analysis']=fields['retention_analysis'].rstrip('\n')+'\nOnly the current authored shot is generated here. References of other shots are not active in this clip; do not show the off-screen speaker or another shot\'s location at the start, middle or end of this shot.\n'
          for old,new in [('Generate synchronized native voice and mouth motion using the same speaker identity and natural delivery as the uploaded voice reference.','Generate the specified off-screen voiceover using the same speaker identity and natural delivery as the uploaded voice reference.'),("Generate synchronized native voice and mouth motion using the assigned speaker's vocal timbre. ",'Generate the specified off-screen voiceover. ')]:
           if fields['overall_soundscape'].count(old)==1:fields['overall_soundscape']=fields['overall_soundscape'].replace(old,new,1)
          s['scope_pipeline_context_v1'].update(fields=fields,keys=keys,before=before,old_to_new={str(k):v for k,v in old_to_new.items()})
        result=s
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801592:
    """Fixed function formerly embedded in node 7801592."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801592."
    def run(self, input_text, input_json):
        return _fixed_7801592(input_text, input_json)

def _fixed_7801541(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def ds_head_b(state,available):
         if state is None:return None
         clean=state['clean']
         if re.search(r'(?i)\b(?:all|any|other|remaining|additional|unlisted)\s+(?:uploaded\s+|provided\s+|registered\s+)?(?:images?|pictures?|references?|materials?)\b|\b(?:everything|anything|whoever|everyone|everybody)\b|\bprevious\s+(?:shot|scene)\b',clean):return None
         if '<Audio' in clean or '<Video' in clean:return None
         defs=clean.partition('subject_definitions:')[2].partition('summary:')[0]
         if not defs.strip():return None
         state['lines']=[line.strip() for line in defs.splitlines() if line.strip()]
         state['ds_phase']='head_b'
         return state
        if 'source_dependency_head_v1' in s:s['source_dependency_head_v1']=ds_head_b(s['source_dependency_head_v1'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801541:
    """Fixed function formerly embedded in node 7801541."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801541."
    def run(self, input_text, input_json):
        return _fixed_7801541(input_text, input_json)

def _fixed_7801542(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def ds_head_c(state,available):
         if state is None:return None
         rows=[]
         for line in state['lines']:
          m=re.fullmatch(r'<Subject\s+(\d+)>\s*(?:\(S\1\)\s*)?is\s+(.+?),\s*referenced by\s+((?:<Picture\s+\d+>\s*(?:,|and)?\s*)+)\.',line)
          if m:
           names=re.split(r'\s+(?:aka|alias|also known as)\s+|\s*/\s*',m[2],flags=re.I)
           rows.append(dict(line=line,sid=m[1],names=names,names_ok=all(re.fullmatch(r'[A-Za-z][A-Za-z\x27 -]{0,60}',x) for x in names),refs=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',m[3])})))
          else:rows.append(dict(line=line))
         state['rows']=rows;state['ds_phase']='head_c'
         return state
        if 'source_dependency_head_v1' in s:s['source_dependency_head_v1']=ds_head_c(s['source_dependency_head_v1'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801542:
    """Fixed function formerly embedded in node 7801542."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801542."
    def run(self, input_text, input_json):
        return _fixed_7801542(input_text, input_json)

def _fixed_7801543(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def ds_analysis_head(state,available):
         if state is None:return None
         clean=state['clean']
         actors=[];aliases={};evidence=[]
         for row in state['rows']:
          line=row['line']
          if 'sid' in row:
           sid=row['sid'];names=row['names']
           if not row['names_ok']:return None
           refs=row['refs']
           if not refs or not set(refs)<=set(available):return None
           if any(a['subject']==sid for a in actors):return None
           for name in names:
            key=name.lower().strip()
            if key in aliases:return None
            aliases[key]=sid
           actors.append(dict(subject=sid,names=names,slots=refs,source=line))
           evidence.append(dict(role='declared_identity',slots=refs,source=line))
          else:
           p=re.fullmatch(r'<Picture\s+(\d+)>\s+is\s+(?:the\s+|a\s+)?((?:product|scene|setting|background|style|costume|composition|identity|object)(?:\s+and\s+(?:product|scene|style|identity|composition))?)\s+reference(?:\s+for\s+all\s+shots)?\.',line,re.I)
           if not p or int(p[1]) not in available:return None
           evidence.append(dict(role='explicit_global_'+p[2].lower(),slots=[int(p[1])],source=line))
         if not actors:return None
         return dict(clean=clean,actors=actors,evidence=evidence)
        if 'source_dependency_head_v1' in s:s['source_dependency_head_v1']=ds_analysis_head(s['source_dependency_head_v1'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801543:
    """Fixed function formerly embedded in node 7801543."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801543."
    def run(self, input_text, input_json):
        return _fixed_7801543(input_text, input_json)

def _fixed_7801544(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        case_fold=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
        def case_fold_char(m):return case_fold[m[0]]
        def case_fold_text(text):return re.sub('[A-Z]',case_fold_char,text).replace('\u0130','i').replace('\u0131','i').replace('\u017f','s').replace('\u212a','k')
        def ds_tail_a(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors']
         detail=clean.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
         blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',detail)[1:]
         if not blocks:return None
         rows=[]
         for block in blocks:
          found=set();text=block
          for actor in actors:
           for name in sorted(actor['names'],key=len,reverse=True):
            pattern=r'(?<![a-z])'+re.escape(name.lower())+r'(?![a-z])'
            spans=[m.span() for m in re.finditer(pattern,case_fold_text(text))]
            if spans:found.add(actor['subject'])
            for start,end in spans[::-1]:text=text[:start]+'resolved_subject'+text[end:]
          rows.append(dict(block=block,found=sorted(found),text=text))
         head['tail_rows']=rows;head['ds_phase']='tail_a'
         return head
        if 'source_dependency_head_v1' in s:s['source_dependency_head_v1']=ds_tail_a(s['source_dependency_head_v1'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801544:
    """Fixed function formerly embedded in node 7801544."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801544."
    def run(self, input_text, input_json):
        return _fixed_7801544(input_text, input_json)

def _fixed_7801545(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def ds_tail_b(head,available):
         if head is None:return None
         for row in head['tail_rows']:
          row['sids']=re.findall(r'<Subject\s+(\d+)>|\(S(\d+)\)',row['text'])
          text=re.sub(r'<Subject\s+\d+>|\(S\d+\)|<Picture\s+\d+>','',row['text'])
          row['text']=text;row['caps']=re.findall(r'\b[A-Z][A-Za-z]*\b',text)
          row['objects']=re.findall(r'(?i)\b(?:at|beside|near|toward|towards|greets?|meets?|recognizes?|helps?|follows?|chases?|embraces?)\s+([A-Za-z_]+)',text)
         head['ds_phase']='tail_b'
         return head
        if 'source_dependency_head_v1' in s:s['source_dependency_head_v1']=ds_tail_b(s['source_dependency_head_v1'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801545:
    """Fixed function formerly embedded in node 7801545."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801545."
    def run(self, input_text, input_json):
        return _fixed_7801545(input_text, input_json)

def _fixed_7801546(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);env=json.loads(input_json);result=s
        def ds_tail_c(head,available):
         if head is None:return None
         for row in head['tail_rows']:row['people']=bool(re.search(r'(?i)\b(?:stranger|visitor|person|people|man|woman|boy|girl|child|adult|friend|mother|father|parent|sister|brother|wife|husband|uncle|aunt|cousin|doctor|guard|officer|customer|waiter|neighbor|somebody|someone|another|others)\b',row['text']))
         head['ds_phase']='tail_c'
         return head
        if 'source_dependency_head_v1' in s:s['source_dependency_head_v1']=ds_tail_c(s['source_dependency_head_v1'],env['inventory']['images'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801546:
    """Fixed function formerly embedded in node 7801546."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801546."
    def run(self, input_text, input_json):
        return _fixed_7801546(input_text, input_json)

def _fixed_7801551(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_head_b(state,available):
         if state is None:return None
         clean=state['clean']
         if re.search(r'(?i)\b(?:all|any|other|remaining|additional|unlisted)\s+(?:uploaded\s+|provided\s+|registered\s+)?(?:images?|pictures?|references?|materials?)\b|\b(?:everything|anything|whoever|everyone|everybody)\b|\bprevious\s+(?:shot|scene)\b',clean):return None
         if '<Audio' in clean or '<Video' in clean:return None
         defs=clean.partition('subject_definitions:')[2].partition('summary:')[0]
         if not defs.strip():return None
         state['lines']=[line.strip() for line in defs.splitlines() if line.strip()]
         state['ds_phase']='head_b'
         return state
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_head_b(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801551:
    """Fixed function formerly embedded in node 7801551."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801551."
    def run(self, input_text, input_json):
        return _fixed_7801551(input_text, input_json)

def _fixed_7801552(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_head_c(state,available):
         if state is None:return None
         rows=[]
         for line in state['lines']:
          m=re.fullmatch(r'<Subject\s+(\d+)>\s*(?:\(S\1\)\s*)?is\s+(.+?),\s*referenced by\s+((?:<Picture\s+\d+>\s*(?:,|and)?\s*)+)\.',line)
          if m:
           names=re.split(r'\s+(?:aka|alias|also known as)\s+|\s*/\s*',m[2],flags=re.I)
           rows.append(dict(line=line,sid=m[1],names=names,names_ok=all(re.fullmatch(r'[A-Za-z][A-Za-z\x27 -]{0,60}',x) for x in names),refs=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',m[3])})))
          else:rows.append(dict(line=line))
         state['rows']=rows;state['ds_phase']='head_c'
         return state
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_head_c(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801552:
    """Fixed function formerly embedded in node 7801552."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801552."
    def run(self, input_text, input_json):
        return _fixed_7801552(input_text, input_json)

def _fixed_7801553(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_analysis_head(state,available):
         if state is None:return None
         clean=state['clean']
         actors=[];aliases={};evidence=[]
         for row in state['rows']:
          line=row['line']
          if 'sid' in row:
           sid=row['sid'];names=row['names']
           if not row['names_ok']:return None
           refs=row['refs']
           if not refs or not set(refs)<=set(available):return None
           if any(a['subject']==sid for a in actors):return None
           for name in names:
            key=name.lower().strip()
            if key in aliases:return None
            aliases[key]=sid
           actors.append(dict(subject=sid,names=names,slots=refs,source=line))
           evidence.append(dict(role='declared_identity',slots=refs,source=line))
          else:
           p=re.fullmatch(r'<Picture\s+(\d+)>\s+is\s+(?:the\s+|a\s+)?((?:product|scene|setting|background|style|costume|composition|identity|object)(?:\s+and\s+(?:product|scene|style|identity|composition))?)\s+reference(?:\s+for\s+all\s+shots)?\.',line,re.I)
           if not p or int(p[1]) not in available:return None
           evidence.append(dict(role='explicit_global_'+p[2].lower(),slots=[int(p[1])],source=line))
         if not actors:return None
         return dict(clean=clean,actors=actors,evidence=evidence)
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_analysis_head(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801553:
    """Fixed function formerly embedded in node 7801553."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801553."
    def run(self, input_text, input_json):
        return _fixed_7801553(input_text, input_json)

def _fixed_7801554(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        case_fold=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
        def case_fold_char(m):return case_fold[m[0]]
        def case_fold_text(text):return re.sub('[A-Z]',case_fold_char,text).replace('\u0130','i').replace('\u0131','i').replace('\u017f','s').replace('\u212a','k')
        def ds_tail_a(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors']
         detail=clean.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
         blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',detail)[1:]
         if not blocks:return None
         rows=[]
         for block in blocks:
          found=set();text=block
          for actor in actors:
           for name in sorted(actor['names'],key=len,reverse=True):
            pattern=r'(?<![a-z])'+re.escape(name.lower())+r'(?![a-z])'
            spans=[m.span() for m in re.finditer(pattern,case_fold_text(text))]
            if spans:found.add(actor['subject'])
            for start,end in spans[::-1]:text=text[:start]+'resolved_subject'+text[end:]
          rows.append(dict(block=block,found=sorted(found),text=text))
         head['tail_rows']=rows;head['ds_phase']='tail_a'
         return head
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_a(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801554:
    """Fixed function formerly embedded in node 7801554."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801554."
    def run(self, input_text, input_json):
        return _fixed_7801554(input_text, input_json)

def _fixed_7801555(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_tail_b(head,available):
         if head is None:return None
         for row in head['tail_rows']:
          row['sids']=re.findall(r'<Subject\s+(\d+)>|\(S(\d+)\)',row['text'])
          text=re.sub(r'<Subject\s+\d+>|\(S\d+\)|<Picture\s+\d+>','',row['text'])
          row['text']=text;row['caps']=re.findall(r'\b[A-Z][A-Za-z]*\b',text)
          row['objects']=re.findall(r'(?i)\b(?:at|beside|near|toward|towards|greets?|meets?|recognizes?|helps?|follows?|chases?|embraces?)\s+([A-Za-z_]+)',text)
         head['ds_phase']='tail_b'
         return head
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_b(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801555:
    """Fixed function formerly embedded in node 7801555."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801555."
    def run(self, input_text, input_json):
        return _fixed_7801555(input_text, input_json)

def _fixed_7801556(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);e=json.loads(input_json);result=s
        def ds_tail_c(head,available):
         if head is None:return None
         for row in head['tail_rows']:row['people']=bool(re.search(r'(?i)\b(?:stranger|visitor|person|people|man|woman|boy|girl|child|adult|friend|mother|father|parent|sister|brother|wife|husband|uncle|aunt|cousin|doctor|guard|officer|customer|waiter|neighbor|somebody|someone|another|others)\b',row['text']))
         head['ds_phase']='tail_c'
         return head
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_c(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801556:
    """Fixed function formerly embedded in node 7801556."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801556."
    def run(self, input_text, input_json):
        return _fixed_7801556(input_text, input_json)

def _fixed_7801561(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_head_b(state,available):
         if state is None:return None
         clean=state['clean']
         if re.search(r'(?i)\b(?:all|any|other|remaining|additional|unlisted)\s+(?:uploaded\s+|provided\s+|registered\s+)?(?:images?|pictures?|references?|materials?)\b|\b(?:everything|anything|whoever|everyone|everybody)\b|\bprevious\s+(?:shot|scene)\b',clean):return None
         if '<Audio' in clean or '<Video' in clean:return None
         defs=clean.partition('subject_definitions:')[2].partition('summary:')[0]
         if not defs.strip():return None
         state['lines']=[line.strip() for line in defs.splitlines() if line.strip()]
         state['ds_phase']='head_b'
         return state
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_head_b(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801561:
    """Fixed function formerly embedded in node 7801561."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801561."
    def run(self, input_text):
        return _fixed_7801561(input_text, "")

def _fixed_7801562(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_head_c(state,available):
         if state is None:return None
         rows=[]
         for line in state['lines']:
          m=re.fullmatch(r'<Subject\s+(\d+)>\s*(?:\(S\1\)\s*)?is\s+(.+?),\s*referenced by\s+((?:<Picture\s+\d+>\s*(?:,|and)?\s*)+)\.',line)
          if m:
           names=re.split(r'\s+(?:aka|alias|also known as)\s+|\s*/\s*',m[2],flags=re.I)
           rows.append(dict(line=line,sid=m[1],names=names,names_ok=all(re.fullmatch(r'[A-Za-z][A-Za-z\x27 -]{0,60}',x) for x in names),refs=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',m[3])})))
          else:rows.append(dict(line=line))
         state['rows']=rows;state['ds_phase']='head_c'
         return state
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_head_c(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801562:
    """Fixed function formerly embedded in node 7801562."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801562."
    def run(self, input_text):
        return _fixed_7801562(input_text, "")

def _fixed_7801563(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_analysis_head(state,available):
         if state is None:return None
         clean=state['clean']
         actors=[];aliases={};evidence=[]
         for row in state['rows']:
          line=row['line']
          if 'sid' in row:
           sid=row['sid'];names=row['names']
           if not row['names_ok']:return None
           refs=row['refs']
           if not refs or not set(refs)<=set(available):return None
           if any(a['subject']==sid for a in actors):return None
           for name in names:
            key=name.lower().strip()
            if key in aliases:return None
            aliases[key]=sid
           actors.append(dict(subject=sid,names=names,slots=refs,source=line))
           evidence.append(dict(role='declared_identity',slots=refs,source=line))
          else:
           p=re.fullmatch(r'<Picture\s+(\d+)>\s+is\s+(?:the\s+|a\s+)?((?:product|scene|setting|background|style|costume|composition|identity|object)(?:\s+and\s+(?:product|scene|style|identity|composition))?)\s+reference(?:\s+for\s+all\s+shots)?\.',line,re.I)
           if not p or int(p[1]) not in available:return None
           evidence.append(dict(role='explicit_global_'+p[2].lower(),slots=[int(p[1])],source=line))
         if not actors:return None
         return dict(clean=clean,actors=actors,evidence=evidence)
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_analysis_head(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801563:
    """Fixed function formerly embedded in node 7801563."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801563."
    def run(self, input_text):
        return _fixed_7801563(input_text, "")

def _fixed_7801564(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        case_fold=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
        def case_fold_char(m):return case_fold[m[0]]
        def case_fold_text(text):return re.sub('[A-Z]',case_fold_char,text).replace('\u0130','i').replace('\u0131','i').replace('\u017f','s').replace('\u212a','k')
        def ds_tail_a(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors']
         detail=clean.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
         blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',detail)[1:]
         if not blocks:return None
         rows=[]
         for block in blocks:
          found=set();text=block
          for actor in actors:
           for name in sorted(actor['names'],key=len,reverse=True):
            pattern=r'(?<![a-z])'+re.escape(name.lower())+r'(?![a-z])'
            spans=[m.span() for m in re.finditer(pattern,case_fold_text(text))]
            if spans:found.add(actor['subject'])
            for start,end in spans[::-1]:text=text[:start]+'resolved_subject'+text[end:]
          rows.append(dict(block=block,found=sorted(found),text=text))
         head['tail_rows']=rows;head['ds_phase']='tail_a'
         return head
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_a(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801564:
    """Fixed function formerly embedded in node 7801564."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801564."
    def run(self, input_text):
        return _fixed_7801564(input_text, "")

def _fixed_7801565(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_tail_b(head,available):
         if head is None:return None
         for row in head['tail_rows']:
          row['sids']=re.findall(r'<Subject\s+(\d+)>|\(S(\d+)\)',row['text'])
          text=re.sub(r'<Subject\s+\d+>|\(S\d+\)|<Picture\s+\d+>','',row['text'])
          row['text']=text;row['caps']=re.findall(r'\b[A-Z][A-Za-z]*\b',text)
          row['objects']=re.findall(r'(?i)\b(?:at|beside|near|toward|towards|greets?|meets?|recognizes?|helps?|follows?|chases?|embraces?)\s+([A-Za-z_]+)',text)
         head['ds_phase']='tail_b'
         return head
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_b(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801565:
    """Fixed function formerly embedded in node 7801565."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801565."
    def run(self, input_text):
        return _fixed_7801565(input_text, "")

def _fixed_7801566(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);s=p['segment'];env=p['env'];result=p
        def ds_tail_c(head,available):
         if head is None:return None
         for row in head['tail_rows']:row['people']=bool(re.search(r'(?i)\b(?:stranger|visitor|person|people|man|woman|boy|girl|child|adult|friend|mother|father|parent|sister|brother|wife|husband|uncle|aunt|cousin|doctor|guard|officer|customer|waiter|neighbor|somebody|someone|another|others)\b',row['text']))
         head['ds_phase']='tail_c'
         return head
        staged=s.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_c(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801566:
    """Fixed function formerly embedded in node 7801566."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801566."
    def run(self, input_text):
        return _fixed_7801566(input_text, "")

def _fixed_7801571(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_head_b(state,available):
         if state is None:return None
         clean=state['clean']
         if re.search(r'(?i)\b(?:all|any|other|remaining|additional|unlisted)\s+(?:uploaded\s+|provided\s+|registered\s+)?(?:images?|pictures?|references?|materials?)\b|\b(?:everything|anything|whoever|everyone|everybody)\b|\bprevious\s+(?:shot|scene)\b',clean):return None
         if '<Audio' in clean or '<Video' in clean:return None
         defs=clean.partition('subject_definitions:')[2].partition('summary:')[0]
         if not defs.strip():return None
         state['lines']=[line.strip() for line in defs.splitlines() if line.strip()]
         state['ds_phase']='head_b'
         return state
        staged=state.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_head_b(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801571:
    """Fixed function formerly embedded in node 7801571."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801571."
    def run(self, input_text, input_json):
        return _fixed_7801571(input_text, input_json)

def _fixed_7801572(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_head_c(state,available):
         if state is None:return None
         rows=[]
         for line in state['lines']:
          m=re.fullmatch(r'<Subject\s+(\d+)>\s*(?:\(S\1\)\s*)?is\s+(.+?),\s*referenced by\s+((?:<Picture\s+\d+>\s*(?:,|and)?\s*)+)\.',line)
          if m:
           names=re.split(r'\s+(?:aka|alias|also known as)\s+|\s*/\s*',m[2],flags=re.I)
           rows.append(dict(line=line,sid=m[1],names=names,names_ok=all(re.fullmatch(r'[A-Za-z][A-Za-z\x27 -]{0,60}',x) for x in names),refs=sorted({int(n) for n in re.findall(r'<Picture\s+(\d+)>',m[3])})))
          else:rows.append(dict(line=line))
         state['rows']=rows;state['ds_phase']='head_c'
         return state
        staged=state.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_head_c(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801572:
    """Fixed function formerly embedded in node 7801572."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801572."
    def run(self, input_text, input_json):
        return _fixed_7801572(input_text, input_json)

def _fixed_7801573(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_analysis_head(state,available):
         if state is None:return None
         clean=state['clean']
         actors=[];aliases={};evidence=[]
         for row in state['rows']:
          line=row['line']
          if 'sid' in row:
           sid=row['sid'];names=row['names']
           if not row['names_ok']:return None
           refs=row['refs']
           if not refs or not set(refs)<=set(available):return None
           if any(a['subject']==sid for a in actors):return None
           for name in names:
            key=name.lower().strip()
            if key in aliases:return None
            aliases[key]=sid
           actors.append(dict(subject=sid,names=names,slots=refs,source=line))
           evidence.append(dict(role='declared_identity',slots=refs,source=line))
          else:
           p=re.fullmatch(r'<Picture\s+(\d+)>\s+is\s+(?:the\s+|a\s+)?((?:product|scene|setting|background|style|costume|composition|identity|object)(?:\s+and\s+(?:product|scene|style|identity|composition))?)\s+reference(?:\s+for\s+all\s+shots)?\.',line,re.I)
           if not p or int(p[1]) not in available:return None
           evidence.append(dict(role='explicit_global_'+p[2].lower(),slots=[int(p[1])],source=line))
         if not actors:return None
         return dict(clean=clean,actors=actors,evidence=evidence)
        staged=state.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_analysis_head(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801573:
    """Fixed function formerly embedded in node 7801573."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801573."
    def run(self, input_text, input_json):
        return _fixed_7801573(input_text, input_json)

def _fixed_7801574(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        case_fold=dict(zip('ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'))
        def case_fold_char(m):return case_fold[m[0]]
        def case_fold_text(text):return re.sub('[A-Z]',case_fold_char,text).replace('\u0130','i').replace('\u0131','i').replace('\u017f','s').replace('\u212a','k')
        def ds_tail_a(head,available):
         if head is None:return None
         clean=head['clean'];actors=head['actors']
         detail=clean.partition('detailed_description:')[2].partition('overall_soundscape:')[0]
         blocks=re.split(r'(?m)^\s*\[Shot\s+\d+\]',detail)[1:]
         if not blocks:return None
         rows=[]
         for block in blocks:
          found=set();text=block
          for actor in actors:
           for name in sorted(actor['names'],key=len,reverse=True):
            pattern=r'(?<![a-z])'+re.escape(name.lower())+r'(?![a-z])'
            spans=[m.span() for m in re.finditer(pattern,case_fold_text(text))]
            if spans:found.add(actor['subject'])
            for start,end in spans[::-1]:text=text[:start]+'resolved_subject'+text[end:]
          rows.append(dict(block=block,found=sorted(found),text=text))
         head['tail_rows']=rows;head['ds_phase']='tail_a'
         return head
        staged=state.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_a(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801574:
    """Fixed function formerly embedded in node 7801574."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801574."
    def run(self, input_text, input_json):
        return _fixed_7801574(input_text, input_json)

def _fixed_7801575(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_tail_b(head,available):
         if head is None:return None
         for row in head['tail_rows']:
          row['sids']=re.findall(r'<Subject\s+(\d+)>|\(S(\d+)\)',row['text'])
          text=re.sub(r'<Subject\s+\d+>|\(S\d+\)|<Picture\s+\d+>','',row['text'])
          row['text']=text;row['caps']=re.findall(r'\b[A-Z][A-Za-z]*\b',text)
          row['objects']=re.findall(r'(?i)\b(?:at|beside|near|toward|towards|greets?|meets?|recognizes?|helps?|follows?|chases?|embraces?)\s+([A-Za-z_]+)',text)
         head['ds_phase']='tail_b'
         return head
        staged=state.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_b(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801575:
    """Fixed function formerly embedded in node 7801575."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801575."
    def run(self, input_text, input_json):
        return _fixed_7801575(input_text, input_json)

def _fixed_7801576(input_text, input_json=""):
    result = ""
    try:
        state=json.loads(input_text);p=json.loads(input_json);result=state
        def ds_tail_c(head,available):
         if head is None:return None
         for row in head['tail_rows']:row['people']=bool(re.search(r'(?i)\b(?:stranger|visitor|person|people|man|woman|boy|girl|child|adult|friend|mother|father|parent|sister|brother|wife|husband|uncle|aunt|cousin|doctor|guard|officer|customer|waiter|neighbor|somebody|someone|another|others)\b',row['text']))
         head['ds_phase']='tail_c'
         return head
        staged=state.get('ds_guard_analysis_v1',[])
        for i,entry in enumerate(staged):
         if entry is None:continue
         try:entry['head']=ds_tail_c(entry['head'],entry['available'])
         except Exception:staged[i]=None
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801576:
    """Fixed function formerly embedded in node 7801576."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801576."
    def run(self, input_text, input_json):
        return _fixed_7801576(input_text, input_json)

def _fixed_7801601(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        try:
            old='\nsummary:\n[reference generation] Render the current authored shot as a newly generated scene. '
            new='\nsummary:\n[inherited first frame] Continue from the supplied first frame, which is the final delivered frame of the previous shot. Begin at exactly its camera distance, framing scale, subject size, screen position and pose; do not reset to a new establishing composition. Any later change of distance or framing comes only from camera movement explicitly described for this shot. '
            if s.get('first_frame_enabled') is True and not s.get('raw_passthrough') and not s.get('visual_only'):
                prompt=s['prompt']
                if prompt.count(old)==1:
                    out=prompt.replace(old,new,1)
                    if re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S):
                        s['prompt']=out
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801601:
    """Fixed function formerly embedded in node 7801601."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801601."
    def run(self, input_text, input_json):
        return _fixed_7801601(input_text, input_json)


def _fixed_7801603(input_text, input_json=""):
    result = ""
    try:
        plan=json.loads(input_text);result=plan
        def segment_opening_text(action,original_slots,audios,videos):
            maps={'Picture':dict(zip(original_slots,range(1,10))),'Audio':dict(zip(audios,[1,2,3])),'Video':dict(zip(videos,[1,2,3]))}
            def token(m):return '<'+m[1]+' '+str(maps[m[1]][int(m[2])])+'>'
            opening=re.split(r'\n\s*\n',action.strip(),maxsplit=1)[0]
            opening=re.sub(r'^(\s*\[Shot\s+\d+\]\s*)(?:Smooth cut to|Cut to)\s+',r'\1From the first frame, the scene is ',opening,count=1)
            opening=re.sub(r'^\s*\[Shot\s+\d+\]\s*','',opening)
            return re.sub(r'<(Picture|Audio|Video)\s+(\d+)>',token,opening)
        try:
            if plan.get('mode')=='with_voice' and plan.get('count',0)>1:
                p=json.loads(input_json)
                audios=p['inventory']['audios'];videos=p['inventory']['videos']
                rows={}
                for row in p['rows']:rows[str(row['source_block'])]=row
                prefix='One continuous shot, already established from the first frame. '
                for s in plan['segments']:
                    blocks=s.get('source_blocks') or []
                    parts=p['shots'][s['shot']].get('parts') or []
                    if not blocks or not parts or s.get('visual_only'):continue
                    first=str(blocks[0])
                    if first==str(parts[0]['source_block']) or first not in rows:continue
                    row=rows[first]
                    if row.get('measured_sentence_window') or str(row.get('shot'))!=str(s['shot']):continue
                    old=prefix+segment_opening_text(parts[0]['action'],s['original_slots'],audios,videos)+'\n'
                    new=prefix+segment_opening_text(row['action'],s['original_slots'],audios,videos)+'\n'
                    prompt=s['prompt']
                    head,sep,rest=prompt.partition('\nsummary:\n')
                    if not sep or not rest.startswith(old) or re.search(r'<d>',old) or re.search(r'<d>',new):continue
                    out=head+sep+new+rest[len(old):]
                    if re.findall(r'<d>.*?</d>',out,re.S)!=re.findall(r'<d>.*?</d>',prompt,re.S):continue
                    s['prompt']=out
                    s['segment_opening_scope_v1']=dict(source_block=first,replaced_shot_opening_block=str(parts[0]['source_block']))
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801603:
    """Fixed function formerly embedded in node 7801603."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801603."
    def run(self, input_text, input_json):
        return _fixed_7801603(input_text, input_json)

def _fixed_7801631(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        try:
            head='[inherited first frame] Continue from the supplied first frame, which is the final delivered frame of the previous shot. Begin at exactly its camera distance, framing scale, subject size, screen position and pose; do not reset to a new establishing composition. Any later change of distance or framing comes only from camera movement explicitly described for this shot. '
            hold='Hold this inherited camera distance and framing scale for the entire clip, from the first frame to the last: the shot size and the subject size in frame stay the same; do not pull back, zoom out, widen or reveal more of the body or the room. Weight shifts, steps, leaning and hand or arm actions play out inside this same framing; body parts, furniture and room areas that are outside the first frame stay outside the frame. Handheld sway or a slight arc keeps this same distance. '
            full='Render the current shot as a full-frame scene.'
            fullnew='Render the current shot as a full-frame scene at the inherited framing scale; full-frame means edge-to-edge picture, not a wider view.'
            tail='\nFollow the chosen total duration'
            tailnew='\nFraming hold for the whole clip: keep the inherited first-frame shot size and camera distance until the last frame; no pull-back, zoom-out or widening reveal.'+tail
            wide=r'\b(?:pull(?:s|ed|ing)?\s+(?:back|out)|dolly(?:ing|ies)?[\s-]*(?:out|back)|zoom(?:s|ed|ing)?[\s-]*out|truck(?:s|ed|ing)?\s+(?:out|back)|crane(?:s|d|ing)?\s+up|widen(?:s|ed|ing)?|wider|wide\s+shot|full[\s-]*(?:body|length|shot)|long\s+shot|establishing|medium(?:[\s-]+wide)?\s+shot|waist[\s-]*up|knees?[\s-]*up|half[\s-]*body|reveal(?:s|ed|ing)?)\b|拉远|后拉|拉开|拉出|全身|全景|远景|中景|半身|广角'
            if s.get('first_frame_enabled') is True and not s.get('raw_passthrough') and not s.get('visual_only'):
                prompt=s['prompt']
                a=prompt.find('\nsummary:\n'+head)
                b=prompt.find('\nretention_analysis:\n')
                if prompt.count(head)==1 and a>=0 and b>a:
                    authored=re.sub(r'<d>.*?</d>','',prompt[a+len(head)+10:b],flags=re.S)
                    if not re.search(wide,authored,re.I):
                        out=prompt.replace(head,head+hold,1)
                        if out.count(full)==1:
                            out=out.replace(full,fullnew,1)
                        if out.count(tail)==1:
                            out=out.replace(tail,tailnew,1)
                        if re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S) and re.findall(r'<[A-Za-z]+ \d+>',out)==re.findall(r'<[A-Za-z]+ \d+>',prompt):
                            s['prompt']=out
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801631:
    """Fixed function formerly embedded in node 7801631."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801631."
    def run(self, input_text, input_json):
        return _fixed_7801631(input_text, input_json)

def _fixed_7801643(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);result=p
        try:
            fps=24;margin=0.15;guard=0.06;minsound=0.08;join=0.3;pad=0.12
            ht=p.get('head_trim') or {}
            old=int(p.get('crop_start_frames') or 0)
            audit=dict(version='g1_audio_led_boundary_v1',applied=False,warnings=[],start_frames=old)
            if p.get('crop_enabled') is True and ht.get('enabled') is True and not p.get('enabled') and old==int(ht.get('prefix_frames') or -1):
                data=json.loads(input_json);regions=data['regions']
                if data.get('total_regions')!=len(regions):
                    audit['warnings'].append('W_ANALYSIS_INVALID_KEEP_PLAN')
                else:
                    render=int(ht['render_frames']);planned=int(ht['delivered_frames']);rend=render/fps;cap=render-2
                    sil=sorted([[float(r['start_time']),float(r['end_time'])] for r in regions])
                    sound=[];prev=0.0
                    for x in sil+[[rend,rend]]:
                        if x[0]-prev>=minsound:
                            if sound and prev-sound[-1][1]<join:sound[-1][1]=x[0]
                            else:sound.append([prev,x[0]])
                        prev=max(prev,x[1])
                    start=old;end=old+planned
                    if sound:
                        onset=sound[0][0];last=sound[-1][1]
                        if onset<old/fps+guard:
                            start=min(old,max(0,int(math.floor((onset-margin)*fps))))
                        if onset<margin:audit['warnings'].append('W_SPEECH_AT_RENDER_START')
                        reach=last>=rend-guard
                        need=cap if reach else int(math.ceil((last+pad)*fps))
                        if reach:audit['warnings'].append('W_SOUND_AT_RENDER_END')
                        end=max(start+planned,min(cap,need))
                        if end>cap:
                            end=cap;start=max(0,min(start,end-planned))
                        audit['onset_seconds']=onset;audit['last_sound_seconds']=last
                    if start<old:audit['warnings'].append('W_OPENING_BEAT_VISIBLE_%d'%(old-start))
                    if end-start>planned:audit['warnings'].append('W_DURATION_PLUS_%d'%(end-start-planned))
                    p['crop_start_frames']=start;p['crop_start_seconds']=start/fps
                    p['delivered_frames']=end-start;p['delivered_seconds']=(end-start)/fps
                    audit.update(applied=True,start_frames=start,end_frames=end)
            p['g1_audio_led_boundary_v1']=audit
        except Exception:
            result=json.loads(input_text);result['g1_audio_led_boundary_v1']=dict(version='g1_audio_led_boundary_v1',applied=False,warnings=['W_EXCEPTION_KEEP_PLAN'])
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801643:
    """Fixed function formerly embedded in node 7801643."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801643."
    def run(self, input_text, input_json):
        return _fixed_7801643(input_text, input_json)

def _fixed_7801645(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);result=p
        try:
            fps=24;guard=0.06;tail_pad=0.12;cap_margin=2
            ht=p.get('head_trim') or {}
            g1=p.get('speech_onset_head_guard_v1') or {}
            audit=dict(version='speech_tail_end_keep_v1',applied=False,reason='not_reference_preroll_crop')
            if p.get('crop_enabled') is True and ht.get('enabled') is True and not p.get('enabled') and g1.get('original_start_frames')==24 and int(ht.get('prefix_frames') or 0)==24:
                data=json.loads(input_json)
                regions=data['regions']
                valid=data.get('total_regions')==len(regions) and len(regions)<=4096
                sil=[]
                for r in regions:
                    a=float(r['start_time']);b=float(r['end_time'])
                    if not (math.isfinite(a) and math.isfinite(b) and 0<=a<b) or 'silence' not in str(r.get('label') or 'silence').lower():
                        valid=False
                    sil.append([a,b])
                sil=sorted(sil)
                render=int(ht['render_frames']);planned=int(ht['delivered_frames'])
                render_end=render/fps;old_end=24+planned;cap=render-cap_margin
                start=int(p['crop_start_frames'])
                head=g1.get('head_start_frames')
                if head is not None and 4<=int(head)<start:
                    start=int(head)
                if not valid:
                    audit['reason']='analysis_invalid_keep_original'
                else:
                    ends=[x[0] for x in sil if x[1]>=render_end-guard]
                    last_sound=min(ends) if ends else render_end
                    if ends:
                        need=int(math.ceil((last_sound+tail_pad)*fps))
                    else:
                        need=cap
                    end=max(old_end,min(cap,need))
                    length=end-start
                    audit.update(start_frames=start,end_frames=end,original_end_frames=old_end,planned_frames=planned,length_frames=length,last_sound_seconds=last_sound,sound_reaches_raw_end=not ends,render_frames=render)
                    if 0<start<=24 and length>=planned and end<=render and (length!=planned or start!=int(p['crop_start_frames'])):
                        p['crop_start_frames']=start
                        p['crop_start_seconds']=start/fps
                        p['delivered_frames']=length
                        p['delivered_seconds']=length/fps
                        audit.update(applied=True,reason='keep_original_end_and_trailing_speech')
                    else:
                        audit['reason']='no_change_needed'
            p['speech_tail_end_keep_v1']=audit
        except Exception:
            result=json.loads(input_text)
            result['speech_tail_end_keep_v1']=dict(version='speech_tail_end_keep_v1',applied=False,reason='analysis_invalid_keep_original')

        ga=p.get('g1_audio_led_boundary_v1') or {}
        if ga.get('applied') is True:
            p['speech_tail_end_keep_v1']=dict(version='speech_tail_end_keep_v1',applied=True,reason='g1_audio_led_boundary_v1',length_frames=int(p['delivered_frames']),planned_frames=int(p['head_trim']['delivered_frames']))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801645:
    """Fixed function formerly embedded in node 7801645."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801645."
    def run(self, input_text, input_json):
        return _fixed_7801645(input_text, input_json)

def _fixed_7801652(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        try:
            p=json.loads(input_json)
            a=p.get('speech_tail_end_keep_v1') or {}
            if a.get('applied') is True and p.get('crop_enabled') is True and int(a['length_frames'])==int(p['delivered_frames']) and int(s.get('delivered_frames',s['model_frames']))==int(a['planned_frames']):
                s['delivered_frames']=int(p['delivered_frames'])
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801652:
    """Fixed function formerly embedded in node 7801652."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801652."
    def run(self, input_text, input_json):
        return _fixed_7801652(input_text, input_json)

def _fixed_7801651(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_text);result=r
        try:
            ctx=json.loads(input_json);seg=ctx['segment']
            hold='Hold this inherited camera distance and framing scale for the entire clip, from the first frame to the last:'
            prompt=r['prompt']
            plain=re.sub(r'<d>.*?</d>','',prompt,flags=re.S)
            subjects=set(re.findall(r'<Subject (\d+)>',plain))
            slots=[int(r['route_slot_'+str(k)]) for k in range(1,10)]
            crops=[r.get('crop_'+str(k)) for k in range(1,10)]
            ok=seg.get('first_frame_enabled') is True and not seg.get('raw_passthrough') and not seg.get('visual_only') and not seg.get('guide_enabled') and not seg.get('continuation')
            ok=ok and prompt.count(hold)==1 and r.get('crop_used') is not True and not [x for x in crops if x] and len(subjects)<=1 and [x for x in slots if x]
            ok=ok and not re.search(r'<(?:Video|Audio) \d+>',plain)
            if ok:
                parts=re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
                out=''.join(x if i%2 else re.sub(r'<Picture \d+>','the supplied first frame',x) for i,x in enumerate(parts))
                out=out.replace(hold,'The supplied first frame is the only visual reference for identity, wardrobe and environment in this clip. '+hold,1)
                if re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S) and '<Picture' not in re.sub(r'<d>.*?</d>','',out,flags=re.S):
                    r['prompt']=out
                    for k in range(1,10):
                        r['route_slot_'+str(k)]=0
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801651:
    """Fixed function formerly embedded in node 7801651."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801651."
    def run(self, input_text, input_json):
        return _fixed_7801651(input_text, input_json)

def _fixed_7801661(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_text);result=r
        try:
            mark='The supplied first frame is the only visual reference for identity, wardrobe and environment in this clip. '
            lock='Camera lock for every frame: the camera stays at the first-frame distance and framing; it never pulls back to show the full body, legs, floor or furniture, and never widens first in order to push in again later. Only the room area already visible behind the subject in the first frame appears. '
            envw=r'\b(?:environment|room|space|location|setting|background|scenery|interior|exterior|venue)\b'
            who=r'<Subject \d+>|\bSubject \d+\b|\(S\d+\)'
            cam=r'\b(?:dolly|push[- ]?in|pull[- ]?(?:back|out)|zoom|pans?|panning|tilts?|crane|tracking|arc|handheld|camera|shot durations?)\b'
            place=r'\b(?:room(?![- ]tone)|living room|standing position|beside|in front of|environment|background|location|space|setting)\b'
            feet=r'\s+(?:from\s+[a-z]+\s+)?(?:to|onto)\s+(?:her|his|their)\s+(?:right|left)\s+(?:foot|leg)\b'
            prompt=r['prompt']
            slots=[int(r['route_slot_'+str(k)]) for k in range(1,10)]
            a=prompt.find('subject_definitions:\n');b=prompt.find('\nsummary:\n');c=prompt.find('\nretention_analysis:\n');d=prompt.find('\ndetailed_description:\n')
            if prompt.count(mark)==1 and not [x for x in slots if x] and a==0 and a<b<c<d:
                parts=re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
                if len(parts)>1 and not re.search(r'<d>',prompt[:c]):
                    defs=prompt[len('subject_definitions:\n'):b]
                    kept=[x for x in re.split(r'(?<=[.!?])\s+',defs.strip()) if not (re.search(envw,x,re.I) and not re.search(who,x))]
                    defs2=' '.join(kept+['The environment is only the part of the same space already visible behind the subject in the supplied first frame.'])
                    summ=re.sub(feet,' slightly, shown only through the visible upper body',prompt[b:c])
                    rbody=prompt[c+len('\nretention_analysis:\n'):d]
                    first,nl,rest=rbody.partition('\n')
                    items=[]
                    for item in first.rstrip('.').split(';'):
                        if re.search(place,item,re.I):
                            continue
                        bits=[x for x in item.split(',') if not re.search(cam,x,re.I)]
                        if ''.join(bits).strip():
                            items.append(','.join(bits))
                    first2=';'.join(items).strip()
                    if first2 and not first2.endswith('.'):
                        first2=first2+'.'
                    tail=prompt[d:]
                    parts=re.split(r'(<d>.*?</d>)',tail,flags=re.S)
                    tail2=''.join(x if i%2 else re.sub(feet,' slightly, shown only through the visible upper body',x) for i,x in enumerate(parts))
                    out='subject_definitions:\n'+defs2+summ.replace(mark,mark+lock,1)+'\nretention_analysis:\n'+first2+nl+rest+tail2
                    if re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S) and set(re.findall(r'<Subject \d+>',out))==set(re.findall(r'<Subject \d+>',prompt)) and out.count(lock)==1:
                        r['prompt']=out
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801661:
    """Fixed function formerly embedded in node 7801661."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801661."
    def run(self, input_text, input_json):
        return _fixed_7801661(input_text, input_json)

def _fixed_7801671(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_text);result=r
        try:
            lock='Camera lock for every frame: the camera stays at the first-frame distance and framing'
            env='The environment is only the part of the same space already visible behind the subject in the supplied first frame.'
            add=' Clothing, bags and accessories appear only as far as they are already visible in the first frame; any part of them below or outside that frame, and any hand or arm outside it, stays unseen.'
            prompt=r['prompt']
            slots=[int(r['route_slot_'+str(k)]) for k in range(1,10)]
            c=prompt.find('\nretention_analysis:\n');d=prompt.find('\ndetailed_description:\n')
            if prompt.count(lock)==1 and prompt.count(env)==1 and not [x for x in slots if x] and 0<c<d and add not in prompt:
                side=r'\b(her|his|their) (left|right|other) (hand|arm) (?:hangs|rests|stays)(?: naturally| loosely| relaxed| down)* (?:at|by|beside|along) (?:her|his|their) (?:side|thigh|hip)s?\b'
                step=r'\b(leans|moves|comes|steps)((?: (?!half\b|a\b|one\b)[a-z]+)?) (?:half a|a half|a small|one|a) step (closer|forward|nearer|toward)'
                stand=r'\b(?:continues|keeps|remains) standing\b'
                out=[]
                for i,x in enumerate(re.split(r'(<d>.*?</d>)',prompt,flags=re.S)):
                    if i%2==0:
                        x=re.sub(side,r'\1 \2 \3 stays relaxed below the frame edge, unseen',x)
                        x=re.sub(step,r'\1\2 slightly \3',x)
                        x=re.sub(stand,'remains',x)
                    out.append(x)
                p=''.join(out).replace(env,env+add,1)
                c=p.find('\nretention_analysis:\n');d=p.find('\ndetailed_description:\n')
                seg=p[c:d]
                k=seg.find('from the supplied first frame')
                if k>0:
                    seg=seg[:k]+'from the supplied first frame, only as far as they are visible in it'+seg[k+len('from the supplied first frame'):]
                p=p[:c]+seg+p[d:]
                if re.findall(r'<d>.*?</d>',p,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S) and set(re.findall(r'<Subject \d+>',p))==set(re.findall(r'<Subject \d+>',prompt)) and p.count(add)==1:
                    r['prompt']=p
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801671:
    """Fixed function formerly embedded in node 7801671."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801671."
    def run(self, input_text, input_json):
        return _fixed_7801671(input_text, input_json)

def _fixed_7801681(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        try:
            p=json.loads(input_json)
            segs=p['segments'];i=int(s['segment_index'])
            def plain(x):
                return bool(x.get('native_audio')) and not [k for k in ['raw_passthrough','visual_only','internal_split_origin','guide_enabled','continuation'] if x.get(k)] and '<Video ' not in str(x.get('prompt',''))
            def same(a,b):
                return str(a.get('shot'))==str(b.get('shot')) and plain(a) and plain(b) and sorted(a.get('original_slots') or [])==sorted(b.get('original_slots') or []) and sorted(a.get('identity_subjects') or [])==sorted(b.get('identity_subjects') or [])
            now=bool(i>0 and same(segs[i-1],segs[i]) and plain(s) and not s.get('first_frame_enabled'))
            nxt=bool(i+1<len(segs) and same(segs[i],segs[i+1]) and plain(s))
            audit=dict(version='same_shot_continuation_v1',inherit=now,carry=nxt,shot=str(s.get('shot')))
            if nxt:
                s['carry_image']=True
            if now:
                line='Continue the same uninterrupted take from the supplied first frame, which is the final delivered frame of the previous part of this same authored shot: keep exactly its camera position, camera distance, framing, subject positions, poses, props and ongoing physical state at the boundary. Proceed naturally with only the current dialogue and its action; do not restart the opening, do not re-establish the composition from any reference image, and add no cut.'
                prompt=s.get('prompt','')
                out=prompt.replace('retention_analysis:','retention_analysis:\n'+line,1) if prompt.count('retention_analysis:')>=1 else prompt
                if re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S):
                    s['prompt']=out
                    s['first_frame_enabled']=True
                    s['same_shot_continuation_v1']=audit
                    pol=dict(s.get('boundary_image_policy_v1') or {})
                    pol['reason']='same_authored_shot_continuation'
                    s['boundary_image_policy_v1']=pol
            if nxt and not now:
                s['same_shot_continuation_v1']=audit
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801681:
    """Fixed function formerly embedded in node 7801681."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801681."
    def run(self, input_text, input_json):
        return _fixed_7801681(input_text, input_json)

def _fixed_7801682(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);result=p
        try:
            s=json.loads(input_json)
            mark=s.get('same_shot_continuation_v1') or {}
            ht=p.get('head_trim') or {}
            frames=int(s['model_frames'])
            audit=dict(version='first_frame_dedup_v1',applied=False,reason='not_same_shot_continuation')
            if mark.get('inherit') is True and s.get('first_frame_enabled') is True and not p.get('enabled') and not ht.get('enabled') and not p.get('crop_enabled') and int(p.get('crop_start_frames') or 0)==0 and int(p.get('delivered_frames'))==frames and frames>=24:
                p['crop_enabled']=True
                p['crop_start_frames']=1
                p['crop_start_seconds']=1/24
                p['delivered_frames']=frames-1
                p['delivered_seconds']=(frames-1)/24
                audit.update(applied=True,reason='drop_duplicated_inherited_first_frame',model_frames=frames,start_frames=1,length_frames=frames-1)
            p['first_frame_dedup_v1']=audit
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801682:
    """Fixed function formerly embedded in node 7801682."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801682."
    def run(self, input_text, input_json):
        return _fixed_7801682(input_text, input_json)

def _fixed_7801683(input_text, input_json=""):
    result = ""
    try:
        p=json.loads(input_text);result=p
        try:
            a=p.get('first_frame_dedup_v1') or {}
            if a.get('applied') is True and int(p.get('crop_start_frames'))==1:
                keep=False
                data=json.loads(input_json)
                regions=data['regions']
                if data.get('total_regions')==len(regions):
                    for r in regions:
                        x=float(r['start_time']);y=float(r['end_time'])
                        if 'silence' in str(r.get('label') or 'silence').lower() and x<=0.005 and y>=1/24+0.02:
                            keep=True
                if not keep:
                    n=int(a['model_frames'])
                    p['crop_start_frames']=0
                    p['crop_start_seconds']=0.0
                    p['delivered_frames']=n
                    p['delivered_seconds']=n/24
                    a=dict(a,applied=False,reason='sound_in_first_frame_keep_all')
                    p['first_frame_dedup_v1']=a
        except Exception:
            result=json.loads(input_text)
            a=result.get('first_frame_dedup_v1') or {}
            if a.get('applied') is True:
                n=int(a['model_frames'])
                result['crop_start_frames']=0
                result['crop_start_seconds']=0.0
                result['delivered_frames']=n
                result['delivered_seconds']=n/24
                result['first_frame_dedup_v1']=dict(a,applied=False,reason='analysis_invalid_keep_all')
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801683:
    """Fixed function formerly embedded in node 7801683."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801683."
    def run(self, input_text, input_json):
        return _fixed_7801683(input_text, input_json)

def _fixed_7801684(input_text, input_json=""):
    result = ""
    try:
        r=json.loads(input_text);result=r
        try:
            ctx=json.loads(input_json);seg=ctx['segment']
            mark=seg.get('same_shot_continuation_v1') or {}
            slots=[int(r['route_slot_'+str(k)]) for k in range(1,10)]
            active=[k for k in range(1,10) if slots[k-1]]
            scene=[]
            for b in seg.get('bindings') or []:
                if b.get('role')=='declared_reference' and not b.get('subject_ids'):
                    scene.append(int(b['local_picture']))
            scene=sorted(scene)
            ok=mark.get('inherit') is True and seg.get('first_frame_enabled') is True and not seg.get('raw_passthrough') and not seg.get('visual_only') and not seg.get('guide_enabled') and not seg.get('continuation')
            ok=ok and bool(scene) and len(scene)<len(active) and active==list(range(1,len(active)+1)) and scene==active[len(active)-len(scene):]
            ok=ok and r.get('crop_used') is not True and not [k for k in scene if r.get('crop_'+str(k))]
            if ok:
                prompt=r['prompt']
                parts=re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
                out=[]
                for i,x in enumerate(parts):
                    if i%2==0:
                        for k in scene:
                            tag='<Picture '+str(k)+'>'
                            x=re.sub(r',\s*'+tag+r'(?=\s*[,.;])','',x)
                            x=x.replace(tag,'the supplied first frame')
                    out.append(x)
                out=''.join(out)
                left=[k for k in scene if '<Picture '+str(k)+'>' in re.sub(r'<d>.*?</d>','',out,flags=re.S)]
                if not left and re.findall(r'<d>.*?</d>',out,re.S)==re.findall(r'<d>.*?</d>',prompt,re.S):
                    r['prompt']=out
                    for k in scene:
                        r['route_slot_'+str(k)]=0
        except Exception:
            result=json.loads(input_text)
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801684:
    """Fixed function formerly embedded in node 7801684."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801684."
    def run(self, input_text, input_json):
        return _fixed_7801684(input_text, input_json)

def _fixed_7801685(input_text, input_json=""):
    result = ""
    try:
        s=json.loads(input_text);result=s
        ht=s.get('head_trim') or {}
        if ht.get('enabled') and ht.get('render_setup'):
            before=s['prompt'];warn=[]
            TSP=re.compile(r'(?<!\d)(\d{2}):(\d{2}\.\d{3})(?!\d)');DP=re.compile(r'(<d>.*?</d>)',re.S)
            def fmt(x):
                ms=int(round(x*1000));return '%02d:%06.3f'%(ms//60000,ms%60000/1000)
            def secs(a,b):return int(a)*60+float(b)
            end=1.0+ht['delivered_seconds'];rend=ht['render_frames']/24
            pr=before.replace(ht['render_setup'],'',1).replace(ht['audio_setup'],'',1)
            dd=pr.partition('detailed_description:\n');od=dd[2].partition('overall_soundscape:\n')
            k0=max(od[0].find('[Shot 1]'),0);intro=od[0][:k0];parts=DP.split(od[0][k0:])
            st=[secs(a,b) for i,q in enumerate(parts) if i%2==0 for a,b in TSP.findall(q)]
            off=0.0;k=od[0].find('Beat 1',k0)
            if st and max(st)>end+0.05:
                warn.append('W_FILM_CLOCK');bm=TSP.search(od[0],k) if k>=0 else None
                if bm and bm.start()-k<12 and secs(bm.group(1),bm.group(2))>1.05:
                    off=secs(bm.group(1),bm.group(2))-1.0
            def fix(m):return fmt(min(max(secs(m.group(1),m.group(2))-off,1.0),end))
            shot=''.join(q if i%2 else TSP.sub(fix,q) for i,q in enumerate(parts))
            k=shot.find('[Shot 1]')
            if k>=0:
                k=k+8;head=shot[:k];body=shot[k:].lstrip()
                if body.startswith('At 00:01.000'):
                    body='From the first frame (00:00.000)'+body[12:]
                pre='';j=body.find('Beat 1')
                if 0<=j<45 and body[j:j+40].find('00:01.000')>=0:
                    body=body[:j]+body[j:j+40].replace('00:01.000','00:00.000',1)+body[j+40:]
                if body.startswith('From the first frame (00:00.000),'):
                    pre=body[:33]+' ';body=body[33:].lstrip()
                j=body.find(': ')
                if body.startswith('Beat 1') and 0<j<45:
                    pre=pre+body[:j+2];body=body[j+2:]
                low=body.lower()
                for t in ('the shot changes to ','the shot cuts to ','the camera cuts to ','the shot switches to ','the scene changes to ','the camera switches to ','cut to ','镜头切到','镜头切换到','画面切到'):
                    if low.startswith(t):
                        body=body[len(t):]
                        body=body[:1].upper()+body[1:];warn.append('W_OPENING_TRANSITION_NEUTRALIZED');break
                shot=head+' '+pre+body
            hd=dd[0].replace('first frame. At 00:01.000,','first frame.',1)
            k=shot.find('[Shot 1]');op=shot[k+8:] if k>=0 else ''
            cut=[x for x in [op.find(m) for m in ('<Subject','<d>','[Shot 2]','Follow the chosen','Perform each described')] if x>=0]
            op=op[:min(cut)] if cut else op[:420]
            op=op.replace('From the first frame (00:00.000),','').strip()
            if op.startswith('Beat 1') and 0<op.find(': ')<45:op=op[op.find(': ')+2:].strip()
            op=('. '.join(op.split('. ')[:2]).strip()[:420].rstrip('.')+'.') if op else 'the current authored shot.'
            setup='Opening beat 00:00.000\u201300:01.000 belongs to this same continuous shot and may be shown: from the very first frame the image already shows this shot\'s own framing, subjects and location as described here: '+op+' No other view, establishing view, empty scene, reference still, earlier shot or camera cut appears before, at or after 00:01.000 unless the authored text below explicitly asks for it. During the opening beat keep a quiet natural settle in that same framing with the scene ambience; the authored action and dialogue continue in the same take from about 00:01.000 to '+fmt(end)+'. After '+fmt(end)+' until '+fmt(rend)+', hold the final physical state without adding words or events.\n'
            sound='Opening-beat sound: the scene\'s natural ambience is present from 00:00.000. Begin the exact assigned dialogue at or after about 00:01.000 and speak every assigned word once inside this clip, ending by '+fmt(end)+'; never repeat words in the final hold.\n'
            pr=hd+dd[1]+setup+intro+shot+od[1]+sound+od[2]
            assert pr.count('detailed_description:\n')==1 and pr.count('overall_soundscape:\n')==1,'G1_SECTION_ENVELOPE'
            assert DP.split(pr)[1::2]==DP.split(before)[1::2],'G1_SCRIPT_CHANGED'
            assert pr.count('<Audio')==before.count('<Audio'),'G1_AUDIO_BINDING_CHANGED'
            result=dict(s,prompt=pr,head_trim=dict(ht,render_setup=setup,audio_setup=sound,g1_warnings=warn,contract='g1_deliverable_opening_beat'))
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed7801685:
    """Fixed function formerly embedded in node 7801685."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 7801685."
    def run(self, input_text, input_json):
        return _fixed_7801685(input_text, input_json)

def _fixed_9482052(input_text, input_json=""):
    result = ""
    try:
        import re
        p = input_text if input_text else ""
        window_text = (input_json or "").strip() if input_json else ""

        constraints = (
            "SYSTEM CONSTRAINTS (never speak, narrate, subtitle, or render these instructions as on-screen text): "
            "Keep the same character identity, face, hairstyle, and wardrobe as the character consistency reference images; do not replace the person. "
            "The desk and tabletop stay completely empty: no phone, notebook, paper, cup, bottle, or any other prop is visible. "
            "The person wears no watch, bracelet, ring, or jewelry; both hands and both wrists stay bare and empty. "
            "Do not render any on-screen subtitles, captions, lower-thirds, title cards, watermarks, or burned-in text. "
            "Speak only the current dialogue in <d> tags, verbatim, once, in order; do not add, delete, repeat, or invent lines; "
            "keep silent pauses between sentences as written. Never read these system constraints aloud."
        )

        before = re.findall(r"<d>.*?</d>", p, flags=re.S)

        # Safety: if this window's authored text is provided, drop <d> blocks that clearly belong to another window.
        # Never strip every tag (that would mute the window). Skip when window_text is empty or JSON.
        def _inner(tag):
            return re.sub(r"</?d>", "", tag).strip()

        if window_text and not window_text.lstrip().startswith("{") and before:
            kept = []
            compact_w = re.sub(r"[\s\W]+", "", window_text)
            for tag in before:
                inner = _inner(tag)
                if not inner:
                    kept.append(tag)
                    continue
                if inner in window_text:
                    kept.append(tag)
                    continue
                compact = re.sub(r"[\s\W]+", "", inner)
                if compact and compact in compact_w:
                    kept.append(tag)
            if kept:
                def _drop(m):
                    return m.group(0) if m.group(0) in kept else ""
                trial = re.sub(r"<d>.*?</d>", _drop, p, flags=re.S)
                if re.findall(r"<d>.*?</d>", trial, flags=re.S):
                    p = trial

        keys = ["subject_definitions", "summary", "retention_analysis", "detailed_description", "overall_soundscape", "non_diegetic_music"]
        idx = []
        search_from = 0
        ok = True
        for k in keys:
            token = k + ":"
            pos = p.find(token, search_from)
            if pos < 0:
                ok = False
                break
            idx.append(pos)
            search_from = pos + len(token)
        if ok and idx == sorted(idx):
            fields = {}
            for i, k in enumerate(keys):
                start = idx[i] + len(k) + 1
                end = idx[i + 1] if i + 1 < len(keys) else len(p)
                fields[k] = p[start:end]
            def inject(section, sentence):
                body = fields[section]
                if sentence in body:
                    return
                lead_nl = "\n" if body.startswith("\n") or body == "" else ""
                rest = body[1:] if body.startswith("\n") else body
                fields[section] = lead_nl + sentence + "\n" + rest
            # Unspeakable: retention / system only — never overall_soundscape or detailed_description.
            inject("retention_analysis", constraints)
            out = "".join(k + ":" + fields[k] for k in keys)
            after = re.findall(r"<d>.*?</d>", out, flags=re.S)
            if after == re.findall(r"<d>.*?</d>", p, flags=re.S):
                p = out
        else:
            trial = constraints + "\n" + p
            after = re.findall(r"<d>.*?</d>", trial, flags=re.S)
            if after == before:
                p = trial
        result = p
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed9482052:
    """Fixed function formerly embedded in node 9482052."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 9482052."
    def run(self, input_text, input_json):
        return _fixed_9482052(input_text, input_json)

def _fixed_9482060(input_text, input_json=""):
    result = ""
    try:
        result = input_text
        try:
            plan = json.loads(input_text) if input_text and str(input_text).lstrip()[:1] == "{" else None
            src = json.loads(input_json) if input_json and str(input_json).lstrip()[:1] == "{" else {}
            rows = src.get("rows") or []
            segs = (plan or {}).get("segments") or []
            if plan and plan.get("schema") == "rh-native-plan-v1" and int(plan.get("count") or 0) > 1 and segs:
                def row(i, k, d=""):
                    return (rows[i].get(k) or d) if 0 <= i < len(rows) else d
                groups, cur, prev = [], [], "__first__"
                for i, s in enumerate(segs):
                    shot = s.get("shot")
                    if cur and shot != prev:
                        groups.append(cur)
                        cur = []
                    cur.append(i)
                    prev = shot
                if cur:
                    groups.append(cur)
                dre = re.compile(r"<d>.*?</d>", re.S)
                orig_b = []
                for s in segs:
                    orig_b.extend(list(s.get("source_blocks") or []))
                silent = "This authored visual interval has no dialogue. Preserve requested ambience without inventing speech."
                changed = False
                for g in groups:
                    if len(g) < 2:
                        continue
                    blocks, seen = [], set()
                    for i in g:
                        for b in (segs[i].get("source_blocks") or []):
                            if b not in seen:
                                seen.add(b)
                                blocks.append(b)
                    later = any(not (segs[i].get("source_blocks") or []) for i in g[1:])
                    if not ((segs[g[0]].get("source_blocks") or []) and later and blocks):
                        continue
                    weights = []
                    for b in blocks:
                        w = float(row(b, "speech_seconds", 0) or 0) + float(row(b, "pause_before", 0) or 0)
                        weights.append(w if w > 0 else float(max(len(row(b, "text")), 1)))
                    tw = sum(weights) or 1.0
                    frames = [max(int(segs[i].get("model_frames") or 0), 1) for i in g]
                    tf = sum(frames) or 1
                    targets, acc = [], 0
                    for f in frames:
                        acc += f
                        targets.append(acc / tf)
                    alloc = [[] for _ in g]
                    cum, wi = 0.0, 0
                    for b, w in zip(blocks, weights):
                        mid = (cum + w / 2.0) / tw
                        wi = 0
                        for t_i, t in enumerate(targets[:-1]):
                            if mid > t:
                                wi = t_i + 1
                        alloc[wi].append(b)
                        cum += w
                    for i in range(len(alloc)):
                        if not alloc[i]:
                            j = i - 1 if i and len(alloc[i - 1]) >= 2 else -1
                            if j < 0:
                                j = i + 1 if i + 1 < len(alloc) and len(alloc[i + 1]) >= 2 else -1
                            if j >= 0:
                                alloc[i].append(alloc[j].pop(-1 if j < i else 0))
                    template = segs[g[0]].get("prompt") or ""
                    origin = [segs[g[0]].get("shot"), blocks[0]]
                    for k, i in enumerate(g):
                        s = segs[i]
                        assigned = alloc[k]
                        s["source_blocks"] = assigned
                        s["text"] = "".join(row(b, "text") for b in assigned)
                        s["visual_only"] = False
                        s["internal_split_origin"] = origin
                        tags = []
                        for b in assigned:
                            r = row(b, "raw_dialogue") or (("<d>" + row(b, "text") + "</d>") if row(b, "text") else "")
                            if r:
                                tags.append(r)
                        pr = dre.sub("", template.replace(silent, ""))
                        if tags:
                            d = pr.find("detailed_description:")
                            n = pr.find("\n", d) if d >= 0 else -1
                            at = n + 1 if n >= 0 else len(pr)
                            pr = pr[:at] + "\n".join(tags) + "\n" + pr[at:]
                        s["prompt"] = pr
                    changed = True
                if changed:
                    new_b = []
                    for s in segs:
                        new_b.extend(list(s.get("source_blocks") or []))
                    if new_b == orig_b:
                        result = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            result = input_text
        return pack_success(result)
    except UnboundLocalError as exc:
        return _pack_unbound(exc)
    except Exception as exc:
        return pack_error(exc)

class PPCFixed9482060:
    """Fixed function formerly embedded in node 9482060."""
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True})
            }
        }
    RETURN_TYPES = RUNNER_RETURN
    RETURN_NAMES = RUNNER_NAMES
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Fixed text/JSON planning for node 9482060."
    def run(self, input_text, input_json):
        return _fixed_9482060(input_text, input_json)

FIXED_TEXT_CLASS_MAPPINGS = {
    "PPCFixed500007": PPCFixed500007,
    "PPCFixed400510": PPCFixed400510,
    "PPCFixed414017": PPCFixed414017,
    "PPCFixed414015": PPCFixed414015,
    "PPCFixed414013": PPCFixed414013,
    "PPCFixed500116": PPCFixed500116,
    "PPCFixed764000": PPCFixed764000,
    "PPCFixed400501": PPCFixed400501,
    "PPCFixed764001": PPCFixed764001,
    "PPCFixed765200": PPCFixed765200,
    "PPCFixed1801": PPCFixed1801,
    "PPCFixed400443": PPCFixed400443,
    "PPCFixed400442": PPCFixed400442,
    "PPCFixed400441": PPCFixed400441,
    "PPCFixed500049": PPCFixed500049,
    "PPCFixed500050": PPCFixed500050,
    "PPCFixed762018": PPCFixed762018,
    "PPCFixed1701": PPCFixed1701,
    "PPCFixed500044": PPCFixed500044,
    "PPCFixed500043": PPCFixed500043,
    "PPCFixed762020": PPCFixed762020,
    "PPCFixed500042": PPCFixed500042,
    "PPCFixed500048": PPCFixed500048,
    "PPCFixed500047": PPCFixed500047,
    "PPCFixed500045": PPCFixed500045,
    "PPCFixed500161": PPCFixed500161,
    "PPCFixed762009": PPCFixed762009,
    "PPCFixed1601": PPCFixed1601,
    "PPCFixed762001": PPCFixed762001,
    "PPCFixed762000": PPCFixed762000,
    "PPCFixed409612": PPCFixed409612,
    "PPCFixed500099": PPCFixed500099,
    "PPCFixed400475": PPCFixed400475,
    "PPCFixed409040": PPCFixed409040,
    "PPCFixed409711": PPCFixed409711,
    "PPCFixed409033": PPCFixed409033,
    "PPCFixed409031": PPCFixed409031,
    "PPCFixed409030": PPCFixed409030,
    "PPCFixed400457": PPCFixed400457,
    "PPCFixed409702": PPCFixed409702,
    "PPCFixed760014": PPCFixed760014,
    "PPCFixed760015": PPCFixed760015,
    "PPCFixed400451": PPCFixed400451,
    "PPCFixed760013": PPCFixed760013,
    "PPCFixed760018": PPCFixed760018,
    "PPCFixed760019": PPCFixed760019,
    "PPCFixed760016": PPCFixed760016,
    "PPCFixed760017": PPCFixed760017,
    "PPCFixed400447": PPCFixed400447,
    "PPCFixed760021": PPCFixed760021,
    "PPCFixed400444": PPCFixed400444,
    "PPCFixed400289": PPCFixed400289,
    "PPCFixed1410": PPCFixed1410,
    "PPCFixed730023": PPCFixed730023,
    "PPCFixed500104": PPCFixed500104,
    "PPCFixed500108": PPCFixed500108,
    "PPCFixed500100": PPCFixed500100,
    "PPCFixed799281": PPCFixed799281,
    "PPCFixed798201": PPCFixed798201,
    "PPCFixed798204": PPCFixed798204,
    "PPCFixed798203": PPCFixed798203,
    "PPCFixed798241": PPCFixed798241,
    "PPCFixed799251": PPCFixed799251,
    "PPCFixed798202": PPCFixed798202,
    "PPCFixed799253": PPCFixed799253,
    "PPCFixed970010": PPCFixed970010,
    "PPCFixed978001": PPCFixed978001,
    "PPCFixed978003": PPCFixed978003,
    "PPCFixed978005": PPCFixed978005,
    "PPCFixed979001": PPCFixed979001,
    "PPCFixed979003": PPCFixed979003,
    "PPCFixed979005": PPCFixed979005,
    "PPCFixed7801101": PPCFixed7801101,
    "PPCFixed7801102": PPCFixed7801102,
    "PPCFixed7801103": PPCFixed7801103,
    "PPCFixed7801104": PPCFixed7801104,
    "PPCFixed7801105": PPCFixed7801105,
    "PPCFixed7801106": PPCFixed7801106,
    "PPCFixed7801107": PPCFixed7801107,
    "PPCFixed7801111": PPCFixed7801111,
    "PPCFixed7801112": PPCFixed7801112,
    "PPCFixed7801121": PPCFixed7801121,
    "PPCFixed7801123": PPCFixed7801123,
    "PPCFixed7801122": PPCFixed7801122,
    "PPCFixed7801131": PPCFixed7801131,
    "PPCFixed7801133": PPCFixed7801133,
    "PPCFixed7801132": PPCFixed7801132,
    "PPCFixed7801141": PPCFixed7801141,
    "PPCFixed7801143": PPCFixed7801143,
    "PPCFixed7801142": PPCFixed7801142,
    "PPCFixed7801113": PPCFixed7801113,
    "PPCFixed7801108": PPCFixed7801108,
    "PPCFixed7801501": PPCFixed7801501,
    "PPCFixed7801502": PPCFixed7801502,
    "PPCFixed7801511": PPCFixed7801511,
    "PPCFixed7801512": PPCFixed7801512,
    "PPCFixed7801513": PPCFixed7801513,
    "PPCFixed7801514": PPCFixed7801514,
    "PPCFixed7801521": PPCFixed7801521,
    "PPCFixed7801522": PPCFixed7801522,
    "PPCFixed7801531": PPCFixed7801531,
    "PPCFixed7801532": PPCFixed7801532,
    "PPCFixed7801581": PPCFixed7801581,
    "PPCFixed7801591": PPCFixed7801591,
    "PPCFixed7801592": PPCFixed7801592,
    "PPCFixed7801541": PPCFixed7801541,
    "PPCFixed7801542": PPCFixed7801542,
    "PPCFixed7801543": PPCFixed7801543,
    "PPCFixed7801544": PPCFixed7801544,
    "PPCFixed7801545": PPCFixed7801545,
    "PPCFixed7801546": PPCFixed7801546,
    "PPCFixed7801551": PPCFixed7801551,
    "PPCFixed7801552": PPCFixed7801552,
    "PPCFixed7801553": PPCFixed7801553,
    "PPCFixed7801554": PPCFixed7801554,
    "PPCFixed7801555": PPCFixed7801555,
    "PPCFixed7801556": PPCFixed7801556,
    "PPCFixed7801561": PPCFixed7801561,
    "PPCFixed7801562": PPCFixed7801562,
    "PPCFixed7801563": PPCFixed7801563,
    "PPCFixed7801564": PPCFixed7801564,
    "PPCFixed7801565": PPCFixed7801565,
    "PPCFixed7801566": PPCFixed7801566,
    "PPCFixed7801571": PPCFixed7801571,
    "PPCFixed7801572": PPCFixed7801572,
    "PPCFixed7801573": PPCFixed7801573,
    "PPCFixed7801574": PPCFixed7801574,
    "PPCFixed7801575": PPCFixed7801575,
    "PPCFixed7801576": PPCFixed7801576,
    "PPCFixed7801601": PPCFixed7801601,
    "PPCFixed7801603": PPCFixed7801603,
    "PPCFixed7801631": PPCFixed7801631,
    "PPCFixed7801643": PPCFixed7801643,
    "PPCFixed7801645": PPCFixed7801645,
    "PPCFixed7801652": PPCFixed7801652,
    "PPCFixed7801651": PPCFixed7801651,
    "PPCFixed7801661": PPCFixed7801661,
    "PPCFixed7801671": PPCFixed7801671,
    "PPCFixed7801681": PPCFixed7801681,
    "PPCFixed7801682": PPCFixed7801682,
    "PPCFixed7801683": PPCFixed7801683,
    "PPCFixed7801684": PPCFixed7801684,
    "PPCFixed7801685": PPCFixed7801685,
    "PPCFixed9482052": PPCFixed9482052,
    "PPCFixed9482060": PPCFixed9482060,
}

FIXED_TEXT_DISPLAY = {
    "PPCFixed500007": "PPC fixed 500007",
    "PPCFixed400510": "PPC fixed 400510",
    "PPCFixed414017": "PPC fixed 414017",
    "PPCFixed414015": "PPC fixed 414015",
    "PPCFixed414013": "PPC fixed 414013",
    "PPCFixed500116": "PPC fixed 500116",
    "PPCFixed764000": "PPC fixed 764000",
    "PPCFixed400501": "PPC fixed 400501",
    "PPCFixed764001": "PPC fixed 764001",
    "PPCFixed765200": "PPC fixed 765200",
    "PPCFixed1801": "PPC fixed 1801",
    "PPCFixed400443": "PPC fixed 400443",
    "PPCFixed400442": "PPC fixed 400442",
    "PPCFixed400441": "PPC fixed 400441",
    "PPCFixed500049": "PPC fixed 500049",
    "PPCFixed500050": "PPC fixed 500050",
    "PPCFixed762018": "PPC fixed 762018",
    "PPCFixed1701": "PPC fixed 1701",
    "PPCFixed500044": "PPC fixed 500044",
    "PPCFixed500043": "PPC fixed 500043",
    "PPCFixed762020": "PPC fixed 762020",
    "PPCFixed500042": "PPC fixed 500042",
    "PPCFixed500048": "PPC fixed 500048",
    "PPCFixed500047": "PPC fixed 500047",
    "PPCFixed500045": "PPC fixed 500045",
    "PPCFixed500161": "PPC fixed 500161",
    "PPCFixed762009": "PPC fixed 762009",
    "PPCFixed1601": "PPC fixed 1601",
    "PPCFixed762001": "PPC fixed 762001",
    "PPCFixed762000": "PPC fixed 762000",
    "PPCFixed409612": "PPC fixed 409612",
    "PPCFixed500099": "PPC fixed 500099",
    "PPCFixed400475": "PPC fixed 400475",
    "PPCFixed409040": "PPC fixed 409040",
    "PPCFixed409711": "PPC fixed 409711",
    "PPCFixed409033": "PPC fixed 409033",
    "PPCFixed409031": "PPC fixed 409031",
    "PPCFixed409030": "PPC fixed 409030",
    "PPCFixed400457": "PPC fixed 400457",
    "PPCFixed409702": "PPC fixed 409702",
    "PPCFixed760014": "PPC fixed 760014",
    "PPCFixed760015": "PPC fixed 760015",
    "PPCFixed400451": "PPC fixed 400451",
    "PPCFixed760013": "PPC fixed 760013",
    "PPCFixed760018": "PPC fixed 760018",
    "PPCFixed760019": "PPC fixed 760019",
    "PPCFixed760016": "PPC fixed 760016",
    "PPCFixed760017": "PPC fixed 760017",
    "PPCFixed400447": "PPC fixed 400447",
    "PPCFixed760021": "PPC fixed 760021",
    "PPCFixed400444": "PPC fixed 400444",
    "PPCFixed400289": "PPC fixed 400289",
    "PPCFixed1410": "PPC fixed 1410",
    "PPCFixed730023": "PPC fixed 730023",
    "PPCFixed500104": "PPC fixed 500104",
    "PPCFixed500108": "PPC fixed 500108",
    "PPCFixed500100": "PPC fixed 500100",
    "PPCFixed799281": "PPC fixed 799281",
    "PPCFixed798201": "PPC fixed 798201",
    "PPCFixed798204": "PPC fixed 798204",
    "PPCFixed798203": "PPC fixed 798203",
    "PPCFixed798241": "PPC fixed 798241",
    "PPCFixed799251": "PPC fixed 799251",
    "PPCFixed798202": "PPC fixed 798202",
    "PPCFixed799253": "PPC fixed 799253",
    "PPCFixed970010": "PPC fixed 970010",
    "PPCFixed978001": "PPC fixed 978001",
    "PPCFixed978003": "PPC fixed 978003",
    "PPCFixed978005": "PPC fixed 978005",
    "PPCFixed979001": "PPC fixed 979001",
    "PPCFixed979003": "PPC fixed 979003",
    "PPCFixed979005": "PPC fixed 979005",
    "PPCFixed7801101": "PPC fixed 7801101",
    "PPCFixed7801102": "PPC fixed 7801102",
    "PPCFixed7801103": "PPC fixed 7801103",
    "PPCFixed7801104": "PPC fixed 7801104",
    "PPCFixed7801105": "PPC fixed 7801105",
    "PPCFixed7801106": "PPC fixed 7801106",
    "PPCFixed7801107": "PPC fixed 7801107",
    "PPCFixed7801111": "PPC fixed 7801111",
    "PPCFixed7801112": "PPC fixed 7801112",
    "PPCFixed7801121": "PPC fixed 7801121",
    "PPCFixed7801123": "PPC fixed 7801123",
    "PPCFixed7801122": "PPC fixed 7801122",
    "PPCFixed7801131": "PPC fixed 7801131",
    "PPCFixed7801133": "PPC fixed 7801133",
    "PPCFixed7801132": "PPC fixed 7801132",
    "PPCFixed7801141": "PPC fixed 7801141",
    "PPCFixed7801143": "PPC fixed 7801143",
    "PPCFixed7801142": "PPC fixed 7801142",
    "PPCFixed7801113": "PPC fixed 7801113",
    "PPCFixed7801108": "PPC fixed 7801108",
    "PPCFixed7801501": "PPC fixed 7801501",
    "PPCFixed7801502": "PPC fixed 7801502",
    "PPCFixed7801511": "PPC fixed 7801511",
    "PPCFixed7801512": "PPC fixed 7801512",
    "PPCFixed7801513": "PPC fixed 7801513",
    "PPCFixed7801514": "PPC fixed 7801514",
    "PPCFixed7801521": "PPC fixed 7801521",
    "PPCFixed7801522": "PPC fixed 7801522",
    "PPCFixed7801531": "PPC fixed 7801531",
    "PPCFixed7801532": "PPC fixed 7801532",
    "PPCFixed7801581": "PPC fixed 7801581",
    "PPCFixed7801591": "PPC fixed 7801591",
    "PPCFixed7801592": "PPC fixed 7801592",
    "PPCFixed7801541": "PPC fixed 7801541",
    "PPCFixed7801542": "PPC fixed 7801542",
    "PPCFixed7801543": "PPC fixed 7801543",
    "PPCFixed7801544": "PPC fixed 7801544",
    "PPCFixed7801545": "PPC fixed 7801545",
    "PPCFixed7801546": "PPC fixed 7801546",
    "PPCFixed7801551": "PPC fixed 7801551",
    "PPCFixed7801552": "PPC fixed 7801552",
    "PPCFixed7801553": "PPC fixed 7801553",
    "PPCFixed7801554": "PPC fixed 7801554",
    "PPCFixed7801555": "PPC fixed 7801555",
    "PPCFixed7801556": "PPC fixed 7801556",
    "PPCFixed7801561": "PPC fixed 7801561",
    "PPCFixed7801562": "PPC fixed 7801562",
    "PPCFixed7801563": "PPC fixed 7801563",
    "PPCFixed7801564": "PPC fixed 7801564",
    "PPCFixed7801565": "PPC fixed 7801565",
    "PPCFixed7801566": "PPC fixed 7801566",
    "PPCFixed7801571": "PPC fixed 7801571",
    "PPCFixed7801572": "PPC fixed 7801572",
    "PPCFixed7801573": "PPC fixed 7801573",
    "PPCFixed7801574": "PPC fixed 7801574",
    "PPCFixed7801575": "PPC fixed 7801575",
    "PPCFixed7801576": "PPC fixed 7801576",
    "PPCFixed7801601": "PPC fixed 7801601",
    "PPCFixed7801603": "PPC fixed 7801603",
    "PPCFixed7801631": "PPC fixed 7801631",
    "PPCFixed7801643": "PPC fixed 7801643",
    "PPCFixed7801645": "PPC fixed 7801645",
    "PPCFixed7801652": "PPC fixed 7801652",
    "PPCFixed7801651": "PPC fixed 7801651",
    "PPCFixed7801661": "PPC fixed 7801661",
    "PPCFixed7801671": "PPC fixed 7801671",
    "PPCFixed7801681": "PPC fixed 7801681",
    "PPCFixed7801682": "PPC fixed 7801682",
    "PPCFixed7801683": "PPC fixed 7801683",
    "PPCFixed7801684": "PPC fixed 7801684",
    "PPCFixed7801685": "PPC fixed 7801685",
    "PPCFixed9482052": "PPC fixed 9482052",
    "PPCFixed9482060": "PPC fixed 9482060",
}

FIXED_TEXT_REGISTRY = (
    {"id": 500007, "class_type": "PPCFixed500007", "sha256": "38b393a4ab0d0a2ca0e1f5efe9c6987327413b947395ccc912dd8234021f8d1c", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400510, "class_type": "PPCFixed400510", "sha256": "2ae011e993a372422ded37717e23ff4cb43c6184fee6eacf0e31fc2be9c5ecc9", "linked": (("input_text", "STRING"),)},
    {"id": 414017, "class_type": "PPCFixed414017", "sha256": "c5583b4c63d6be68ae485510ab8b4ecf0aee921b7c02c30811526474da3e2729", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 414015, "class_type": "PPCFixed414015", "sha256": "b6f816bdf78707d0fb06a99e83ee566b5292069aec4e50fc25d0b9f99e109ede", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 414013, "class_type": "PPCFixed414013", "sha256": "72918c352e9c4ab1b13d2d25e2ab80b9213d586eb4ffa8e81edeaeb8c4b66b88", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500116, "class_type": "PPCFixed500116", "sha256": "eae77c23733e320ba81e943c686a74f695ac5dcadd82af7f0d5690d168b51789", "linked": (("input_text", "STRING"),)},
    {"id": 764000, "class_type": "PPCFixed764000", "sha256": "9171212b18c3a774c1ca3cf79064375ecfdc056015d2a016dc4552949566d407", "linked": (("input_text", "STRING"),)},
    {"id": 400501, "class_type": "PPCFixed400501", "sha256": "e07da0330d93929f17f5846be7595c97395e1a17f878e22a4b30707a6ad143ed", "linked": (("input_text", "STRING"),)},
    {"id": 764001, "class_type": "PPCFixed764001", "sha256": "c9c765ef495c80eef9639f6fa17746e0bf8afff97313c136aec34e5578ae2b70", "linked": (("input_text", "STRING"),)},
    {"id": 765200, "class_type": "PPCFixed765200", "sha256": "149e83a98a83e06bd4e66e59d0c05eeb29dcb1906ce003aa214df2ef4cdd34e3", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 1801, "class_type": "PPCFixed1801", "sha256": "ecbf186ffe971420d70801905c8d1e67a52d8b649c758f2d8fc1f5c8fda1aea6", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400443, "class_type": "PPCFixed400443", "sha256": "dc26374bfb1251249730f42c5e950b9d0ea51a008dd784651ea75b5181203e5a", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400442, "class_type": "PPCFixed400442", "sha256": "3886b2b6cc7ffa93f479e8cc471fb5165c29474a341761289aa31cda09d1da4b", "linked": (("input_text", "STRING"),)},
    {"id": 400441, "class_type": "PPCFixed400441", "sha256": "327ea4bb9dccebef3c84f796952a40b56018dc4ab5b787e7706715d43ccd6bdf", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500049, "class_type": "PPCFixed500049", "sha256": "df510f74b7efc2c0e7d946010542b4cbdc15b47801f524df7e18f942931caa6e", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500050, "class_type": "PPCFixed500050", "sha256": "9daabe50ba13bd57a41fd886b1f8312e8e4da96414eaca16d539bced67f3ff33", "linked": (("input_text", "STRING"),)},
    {"id": 762018, "class_type": "PPCFixed762018", "sha256": "03227978df0a9d7b97ebf32a6e0b703c740206ae0f562cc47e37cbd9a328ef64", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 1701, "class_type": "PPCFixed1701", "sha256": "ec954ce95e47c182c1ef5fdefecd19085d030bb8a8591e52d5b956603bcaf185", "linked": (("input_text", "STRING"),)},
    {"id": 500044, "class_type": "PPCFixed500044", "sha256": "c86dfb9b656451bfa67e3304125e4486dcc3acfca1b24ca385dcf54997e249b1", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500043, "class_type": "PPCFixed500043", "sha256": "9d35eb0ebdf4f36c94f08db0374bef82415fe71f4a00f9cefe12816e4357b996", "linked": (("input_text", "STRING"),)},
    {"id": 762020, "class_type": "PPCFixed762020", "sha256": "34358886e6c80da817e362cdf1d90b8f10d9b9c2142e1c142726aa77cce92f53", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500042, "class_type": "PPCFixed500042", "sha256": "fb503c0952a99f5f82a7f7a137659d2a42725baf512e018354f8636091c952cd", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500048, "class_type": "PPCFixed500048", "sha256": "a20c67a9eb4adda03c7cb7307ffe837b19086de89bc15b52fb981d8e88eeb140", "linked": (("input_text", "STRING"),)},
    {"id": 500047, "class_type": "PPCFixed500047", "sha256": "9d2a6df9e9c8cc84287c774d258f03abb7759418b8d81720b9a43da1ddf4df18", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500045, "class_type": "PPCFixed500045", "sha256": "6b7084a61e14e1fdb5f88205e6185ddb9329563b403b7672956d72b4c37f350c", "linked": (("input_text", "STRING"),)},
    {"id": 500161, "class_type": "PPCFixed500161", "sha256": "8ce3ab7e5aac5f6738101e1aa67348428be65312417f2672b2dbc135fe51489d", "linked": (("input_text", "STRING"),)},
    {"id": 762009, "class_type": "PPCFixed762009", "sha256": "b714b9c3262fdf132e7a1856be49469be8af93fb85dc7de5fe4a0ae8a7e4064c", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 1601, "class_type": "PPCFixed1601", "sha256": "dd2389c4ae324a1bb9e1372135fd373645ca5442e846fd4c9c586c64206fe420", "linked": (("input_text", "STRING"),)},
    {"id": 762001, "class_type": "PPCFixed762001", "sha256": "56c0df38a9fef6d47f4568440a38fec203d5b64492b0686efeba7db5ddcb3005", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 762000, "class_type": "PPCFixed762000", "sha256": "e508b4035363ea822ce560f29583a892f88578af1090401b0667f932ea353f46", "linked": (("input_text", "STRING"),)},
    {"id": 409612, "class_type": "PPCFixed409612", "sha256": "53298ac0a0be6fd466788a410be6c529f38b54eefc983cdf626843766c9b651b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500099, "class_type": "PPCFixed500099", "sha256": "e46ed4c3eb51c714e034532a321f456fdbebc573288a17896c5bef829529a2c5", "linked": (("input_text", "STRING"),)},
    {"id": 400475, "class_type": "PPCFixed400475", "sha256": "ba84f66496dd2010b3d2ee1f595edf1cd43fc41dba1a1d9c42494062e7881aae", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 409040, "class_type": "PPCFixed409040", "sha256": "f6a85538de1dd724cc3dc911839b729c3818742e6a2389c6c26a958daa7a4cc8", "linked": (("input_text", "STRING"),)},
    {"id": 409711, "class_type": "PPCFixed409711", "sha256": "669cdc291c26feb5cd58f4f0d7783c396b2b90a15336e421eb2c549814577a85", "linked": (("input_text", "STRING"),)},
    {"id": 409033, "class_type": "PPCFixed409033", "sha256": "5788ef249f3488b3150ced8278474315bfa1299b74176298a4a418950490261c", "linked": (("input_text", "STRING"),)},
    {"id": 409031, "class_type": "PPCFixed409031", "sha256": "1afa1235635d8a8eb9f37143475d2630adb5318a35e0525a0086b278f734faec", "linked": (("input_text", "STRING"),)},
    {"id": 409030, "class_type": "PPCFixed409030", "sha256": "b39e0c542125d64275f4c19ffe4fcfe4ca12cc061315a9311bb83dd3643e70b4", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400457, "class_type": "PPCFixed400457", "sha256": "cd56b29fef69c0cf15c6bd21c4dc8f28a5258fdb8c051257d9fc4b4dace344cf", "linked": (("input_text", "STRING"),)},
    {"id": 409702, "class_type": "PPCFixed409702", "sha256": "682723bf0a3b984b78c9f02c54e7d4050032e79a85876bc218acd2dd9cb5a8f5", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 760014, "class_type": "PPCFixed760014", "sha256": "7d96bb02050e02fbcaed7cbf3d3b9f0a96d6c10fe40d6f2b36e70353ffca05ca", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 760015, "class_type": "PPCFixed760015", "sha256": "928aa1bc9496b93df9210a08f50e5f01cdaeca57ab97cd46c471941c16b7fa32", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400451, "class_type": "PPCFixed400451", "sha256": "929196c44abe326d66a44344ad734765f0a7fb898ade7e807c69e4d0b598b38a", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 760013, "class_type": "PPCFixed760013", "sha256": "c0052bab5c0415a45c0e8c47010f59f81ff9b278149aeae48ba3e40500771102", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 760018, "class_type": "PPCFixed760018", "sha256": "a4425e405958a4876a9a601c912441035f437605b1e94ef88e1eb2a9a4e45f88", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 760019, "class_type": "PPCFixed760019", "sha256": "81d107b2071fc4f7ff4b01dd666a5eaa46e1287eb95814382ef6c443451a8c7c", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 760016, "class_type": "PPCFixed760016", "sha256": "e91bf346ff00f5c21ba96469e138d198826b2835f6a10ac9cf0fff530677ec17", "linked": (("input_text", "STRING"),)},
    {"id": 760017, "class_type": "PPCFixed760017", "sha256": "5678800c7e0ae24181c0e8e4b853bb2fa3f1a519b378a87f249c660c8dc7d8b8", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400447, "class_type": "PPCFixed400447", "sha256": "e43af53c7b0f4530a53a86466666ca12871ec348211aa6efe0e857fa7637c766", "linked": (("input_text", "STRING"),)},
    {"id": 760021, "class_type": "PPCFixed760021", "sha256": "60d612863d818d99f9f6fa95d871341dfbce8baf49aa8042222b252ec563b691", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 400444, "class_type": "PPCFixed400444", "sha256": "6495c883548829cbe2fea043295fa4ad79865f35d5dde7b2c35c2696d42bb8a5", "linked": (("input_text", "STRING"),)},
    {"id": 400289, "class_type": "PPCFixed400289", "sha256": "54722f3af42b63e304be5b6fc5855f88fe335efd4872e74cd63b89e4772741e5", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 1410, "class_type": "PPCFixed1410", "sha256": "ea467551990c1d24748f98cc639e3c461d523ffe6f61b15d0923e4be947be72e", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 730023, "class_type": "PPCFixed730023", "sha256": "85fa2ac4eb77ebeaab18fdc236b397f648fe94066f103af75f1188dd04dd7364", "linked": (("input_text", "STRING"),)},
    {"id": 500104, "class_type": "PPCFixed500104", "sha256": "9c7ab2e3c966b8ba708d596ea59113eb0b6536743f4b63d1ca4badb3f2e9bfd6", "linked": (("input_text", "STRING"),)},
    {"id": 500108, "class_type": "PPCFixed500108", "sha256": "06b6ac75f2716c68c03e7d9f5995b3609335d0c05bbd78a777eab9d3a8e983be", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 500100, "class_type": "PPCFixed500100", "sha256": "0adaa2d4262c5199504e6406aaa6b3b82384213fbc4572a5e8b348d7cd2a6a63", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 799281, "class_type": "PPCFixed799281", "sha256": "5d9d5aa1182276bb07ce914935c324acbabd23c336bce0567eb7ec1011de0a34", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 798201, "class_type": "PPCFixed798201", "sha256": "31f2b582520a75d74bf3029ec169aef6f39f9bc918b1e1d64f17a1bde90b5242", "linked": (("input_text", "STRING"),)},
    {"id": 798204, "class_type": "PPCFixed798204", "sha256": "0fd57b18513e781f631c1b21a74bb0421813454ae87b02f8e14a0edb4120c35c", "linked": (("input_text", "STRING"),)},
    {"id": 798203, "class_type": "PPCFixed798203", "sha256": "4ad50ac8dcb67b9c655e8dd8a47760c4f28127abb2b3e3b5983b159ca456bc4c", "linked": (("input_text", "STRING"),)},
    {"id": 798241, "class_type": "PPCFixed798241", "sha256": "ea895bef154ecf4b2d2ad2e7fa35cfa410f4f41c8ba3ef66c5b5ecaf6fb0889a", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 799251, "class_type": "PPCFixed799251", "sha256": "ff84e63a0e700a29c70256277cd3ed2d797aed094c69bc36039dd5c8c93004fe", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 798202, "class_type": "PPCFixed798202", "sha256": "8ac76bc1c23716e7a621314e8503da22c2d9da76d170bc358dcab441b27a114d", "linked": (("input_text", "STRING"),)},
    {"id": 799253, "class_type": "PPCFixed799253", "sha256": "0a9f1516e8e62839826f03551643ea678ff32491e036dcc628cb63daaf87c62e", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 970010, "class_type": "PPCFixed970010", "sha256": "d59a4643fb2bb13eae1e2f3bd78c7a527420789309522115e4bf112bef66ca33", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 978001, "class_type": "PPCFixed978001", "sha256": "c88dbf36e8de7bd9f33ac0c7c38601a1dffaf384ad825f06a97a30fa1505f57f", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 978003, "class_type": "PPCFixed978003", "sha256": "081b5deca4178203693bea9ab59341cbd5f8f39880536de0d36f7a7b9350553b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 978005, "class_type": "PPCFixed978005", "sha256": "a71196765db185c62b94193c69ecc4b2b1b010da07df858fa68f2baa18411b3d", "linked": (("input_text", "STRING"),)},
    {"id": 979001, "class_type": "PPCFixed979001", "sha256": "e777b69acf2e135228d8e44cdb7e2300985b76d84a2795dda2799b3ad273b6df", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 979003, "class_type": "PPCFixed979003", "sha256": "60c713fcb60f6f03946ebcc40abbef5d2508e0d631e96278cf15588832fb8d96", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 979005, "class_type": "PPCFixed979005", "sha256": "e00534ff0aa0938bcddc9ea3e4eaa24436f445f2f96e29818608117891f6b121", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801101, "class_type": "PPCFixed7801101", "sha256": "54ecddde03295ce8ed55105ef33ef96c8016c8164d5923cdef4f80c266c17837", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801102, "class_type": "PPCFixed7801102", "sha256": "ac7f224eca6377f786f1121455980f520786127996b481a56fa7bf7ffc15d828", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801103, "class_type": "PPCFixed7801103", "sha256": "d81b303df0d0af170bf58564a5ea221142571184e161092eb119bd3d385be1da", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801104, "class_type": "PPCFixed7801104", "sha256": "a46a504098f2ffc28626327e52c6cee1028061df2d55263d8e10c6aae7907b30", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801105, "class_type": "PPCFixed7801105", "sha256": "aedb2267c68e351006a0c69325383a91e67508a00f61be5e4c29005dc28ef2a6", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801106, "class_type": "PPCFixed7801106", "sha256": "a6b6194cb918bf30c04e63fa76b08eb7135facb35479bbf2b4b2063319680221", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801107, "class_type": "PPCFixed7801107", "sha256": "d31f61ae8d337bc4cb8ee4746022ac55f51ffb22d69ecf3aac16993e276c4918", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801111, "class_type": "PPCFixed7801111", "sha256": "08acd3c8e3c7f298d7edc1c1ab6bc29d4a6575fefb0358c533c99f980bc207fd", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801112, "class_type": "PPCFixed7801112", "sha256": "4f90206a395430adb968dab3d828d07f95d7b4075d792bf83c64b847ae3ce568", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801121, "class_type": "PPCFixed7801121", "sha256": "a85de3e12a36dab2291d49d57e717ac4d446d9031950781bef458e2ae4169c67", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801123, "class_type": "PPCFixed7801123", "sha256": "59028aacb259cfd672177a88b2626122b16f17e70b8536a584aa7953ff8e4b42", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801122, "class_type": "PPCFixed7801122", "sha256": "94d237d8c759fbca8c4951592630dc5bc51dbea99b94eee18729fcfddc8c2a9d", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801131, "class_type": "PPCFixed7801131", "sha256": "905a1d69d486c07d3cd184f7bdd2c7bba002cdee891fc38c21dd6ae1fee31d1c", "linked": (("input_text", "STRING"),)},
    {"id": 7801133, "class_type": "PPCFixed7801133", "sha256": "fc1b7333cfbdde0aea5f8034903b1997d19dbf31014104369160980c7892d018", "linked": (("input_text", "STRING"),)},
    {"id": 7801132, "class_type": "PPCFixed7801132", "sha256": "059143788fc7864ac1259558c875a939048b0e1504872656a801e60e5ce372cc", "linked": (("input_text", "STRING"),)},
    {"id": 7801141, "class_type": "PPCFixed7801141", "sha256": "88934b593c8f355a90a29d0244752b7d8b1d17d65e0409128738d46494741f2b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801143, "class_type": "PPCFixed7801143", "sha256": "44e00194ed553de8743850d99d7a78a06e0a0b01592471cd1978807cacc85ec8", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801142, "class_type": "PPCFixed7801142", "sha256": "47aef1b033158c40c6d2d20f18b6035a24351f9e45d41a7f03bc9efc45d4bcf6", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801113, "class_type": "PPCFixed7801113", "sha256": "54d9cfc1e0b8ae2d345d4bb00cac3929501314ba0736d96c9bf4eac5bdec5112", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801108, "class_type": "PPCFixed7801108", "sha256": "51c8824746ab42ea359c3cd08bac300b469608a7b0f9b02dd00131ad6f29ddcb", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801501, "class_type": "PPCFixed7801501", "sha256": "db98efc2cb1c944783d3f747888e2f985c1d200b528d61e303a1d3285df714fc", "linked": (("input_text", "STRING"),)},
    {"id": 7801502, "class_type": "PPCFixed7801502", "sha256": "d7d09b20939f07db94e82d31223617634c8c77eb1a7720442e04747792327d4a", "linked": (("input_text", "STRING"),)},
    {"id": 7801511, "class_type": "PPCFixed7801511", "sha256": "d792edabbe2479b0633a03728a5fb34d17dcb7a13e21a64e4e21e59575def09a", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801512, "class_type": "PPCFixed7801512", "sha256": "405cb0bfef0516fd7c09e6da752698414577861709636882234596c62b48aafe", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801513, "class_type": "PPCFixed7801513", "sha256": "e71455da71ba318c43fbb158c634d8f3d0870874ccd1534f377845f8a3933a8d", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801514, "class_type": "PPCFixed7801514", "sha256": "fc8d37a16d92c371a69a4f3dc21da855838ae7496a460daf3ea457e266a3562a", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801521, "class_type": "PPCFixed7801521", "sha256": "b7a9d710a7df62f7f954882deb55bd45e6582e29eb1355a6e2cfdea6a53acefe", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801522, "class_type": "PPCFixed7801522", "sha256": "465b699602d09d7955ed5bf7b86eb3c6916ad2c9eeb5550001784d9e7290ad70", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801531, "class_type": "PPCFixed7801531", "sha256": "36f8ebd5b6e6fe2a8effda695470bc3e66a13dbe4478e63f98275a8f62c62629", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801532, "class_type": "PPCFixed7801532", "sha256": "d99bb2febfbb7710cf4eeca37be504e3c5afcc7a6fce746be17cbb3d48252d26", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801581, "class_type": "PPCFixed7801581", "sha256": "52cc004f9918b520193377bebb0a8249cff3cf484e34f4164c1164b35019d322", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801591, "class_type": "PPCFixed7801591", "sha256": "fce9cda813a62b33e4d7ba6b1c55dd3b089bd022f7b75b2d3e0dc4e45305d6dd", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801592, "class_type": "PPCFixed7801592", "sha256": "1508a9f18d60aaed2b5988696a073d6bfdbe94ab378bf45095c6daba54026440", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801541, "class_type": "PPCFixed7801541", "sha256": "d165f3d1e0d577cf080afa950506b02df5ab6d44107f01e57bc36b2e1cd07c5b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801542, "class_type": "PPCFixed7801542", "sha256": "77fea35f27275c3a925ed07cfb044f18c98cab6904fb72bf0b65263b9f4cd8f3", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801543, "class_type": "PPCFixed7801543", "sha256": "23d6c96a94317c6a376cc6f7ea4072cc77a1c479276b2cc32b832db29f55a76e", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801544, "class_type": "PPCFixed7801544", "sha256": "9a18c016dbecc51ef840829121e783c79aa4d8c7c088f14ce1fb12184ed6c6f3", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801545, "class_type": "PPCFixed7801545", "sha256": "ee8a99fd47e25bcb3c73a0d2d14ef25edc67bd2a7dc600cfc1b43c92154349ca", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801546, "class_type": "PPCFixed7801546", "sha256": "c70565c65e7307aea31920e85a252a724d1323a95577c12e265cd7d074e2dfd0", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801551, "class_type": "PPCFixed7801551", "sha256": "c63da675c0d2d95f990c1a03e5510487b25509419d9bc2b9550fc9300e6eb4db", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801552, "class_type": "PPCFixed7801552", "sha256": "8b210a4d1f3217c058623467073d64c6069c370e5e713e049ae632e0da935866", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801553, "class_type": "PPCFixed7801553", "sha256": "08ce1a77d322cb3ba5f44c53df08b1ac2f883ead88cff36f71e1452dfe80369b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801554, "class_type": "PPCFixed7801554", "sha256": "41c7115c1214ae4ce55b97430f9e3a40baa89653bcb647ce9a063203b0a3d65c", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801555, "class_type": "PPCFixed7801555", "sha256": "ff4110280d8623b3060b7a7b8c0afe982e02f749352a0e9a6c822deaf98eeec8", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801556, "class_type": "PPCFixed7801556", "sha256": "66b14ea45abd1022740416238e65f8c2d0ccb0f12f2dfe4c9e657898d0da1188", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801561, "class_type": "PPCFixed7801561", "sha256": "2499e17d7551c97f6a559bd561c805acd7cb32fb4c63028a2fddf239f9601674", "linked": (("input_text", "STRING"),)},
    {"id": 7801562, "class_type": "PPCFixed7801562", "sha256": "0e59f8884e2be5a789220e65a53dfc9ee999bd4d5e3e61dc2b7f2952e0c090f2", "linked": (("input_text", "STRING"),)},
    {"id": 7801563, "class_type": "PPCFixed7801563", "sha256": "5ca0e431682fd0945253bceb24dae2cace213e8c899dd12840627696f568bff6", "linked": (("input_text", "STRING"),)},
    {"id": 7801564, "class_type": "PPCFixed7801564", "sha256": "6c8e4738409ab605b62da829228cf56b6e6a102377f10a6e215385660b7a5a6e", "linked": (("input_text", "STRING"),)},
    {"id": 7801565, "class_type": "PPCFixed7801565", "sha256": "33df819747076f11c21e4461b9d560fa06867236b2a8106ded7a5071eed160a0", "linked": (("input_text", "STRING"),)},
    {"id": 7801566, "class_type": "PPCFixed7801566", "sha256": "a07cfa4e11db51dbabc18948ba0e322739b03f53b02af9b43668753889fcfab5", "linked": (("input_text", "STRING"),)},
    {"id": 7801571, "class_type": "PPCFixed7801571", "sha256": "781d9f0336eb981190901788a86e62bf45607a04c14e23a9b64b0c8021daa0b2", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801572, "class_type": "PPCFixed7801572", "sha256": "dad66e31ec9b7edcdaacecf1c0667f64519e3820a7ffab73f8d683c73b849d9b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801573, "class_type": "PPCFixed7801573", "sha256": "dd68351d575ce1641c99c0029108f1f4bf74d0a4dbc7ee98cf0f0a9e20cebed2", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801574, "class_type": "PPCFixed7801574", "sha256": "4bd5ea659fd693536432c960b5396f5728048c1a5684aa543e7c42ed9536e678", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801575, "class_type": "PPCFixed7801575", "sha256": "eede4e45dce1459eb16aed270be56dc5859041393a7e17346e7ca5af55c3adf2", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801576, "class_type": "PPCFixed7801576", "sha256": "2b89b8dd6d1ce1a10f34a951f642b67f2f0279b77b02a248864bf8b0e9ac280b", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801601, "class_type": "PPCFixed7801601", "sha256": "5eea62f24d3d3e95693d967b0f8e17857cec37054a9d99b2c63cec0c824d7350", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801603, "class_type": "PPCFixed7801603", "sha256": "581d1d04f270cc40833baaa8748eaeb4a434341519b863ccb0b499d2926f3615", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801631, "class_type": "PPCFixed7801631", "sha256": "0b364954232bf21f29598b7100d0f52493d67d577fed21f30db43a4309204b80", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801643, "class_type": "PPCFixed7801643", "sha256": "2f13c3fc653463d37a922fe28eaf62caf1e4abf52650c25322ded23d6614d0e9", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801645, "class_type": "PPCFixed7801645", "sha256": "6183959a34bb2920b417079159d903938ae684e8bb287a38a062d85abd4b7b1e", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801652, "class_type": "PPCFixed7801652", "sha256": "9c8c62c00390a8411e0f82da4909079ef597fa4abfc8f3360e9cb5df9e9f7369", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801651, "class_type": "PPCFixed7801651", "sha256": "19730916ec51575ef7d1063fae31b6fdc032755ddbcc9099fd486c8630739121", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801661, "class_type": "PPCFixed7801661", "sha256": "9b8014468653b896ddc24ab3a51b0d8eab2ecc97ba809dd97e93ce70dadf3bf7", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801671, "class_type": "PPCFixed7801671", "sha256": "02ba7a47ddfe36b79d46e6728098263948a21a3d69abee658dc69d4ea6058c8c", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801681, "class_type": "PPCFixed7801681", "sha256": "b6bcb5cab6935e3fc14a96b0ff5b3d38885274763700e29387d918f8f5a2d5f9", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801682, "class_type": "PPCFixed7801682", "sha256": "e7fdc1d1d4c008445b9296805e5cfc6658b1b62def4ef786ba8b8bd4680b2e9e", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801683, "class_type": "PPCFixed7801683", "sha256": "068739b36c735fc77ae61d704e34d316177d3f85b03710b1cec27192c1dcae9f", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801684, "class_type": "PPCFixed7801684", "sha256": "4d2cb020d7c29e8cbd8de3887bd07e5e4e8fd7111b2d21f8361c11b6f3856e81", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 7801685, "class_type": "PPCFixed7801685", "sha256": "09f31c594c58d00b8ef58933b5d2ad96c3e18eaf2924168928dcf6170c69aec9", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 9482052, "class_type": "PPCFixed9482052", "sha256": "6c4d9cb7830269a8c46340632ec0b256bcd3d55f5c43606ccc96e39373e3ff99", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
    {"id": 9482060, "class_type": "PPCFixed9482060", "sha256": "de7094e0828d1eb66875e506980286c5806bebf12a77ba621bda79dc85803857", "linked": (("input_text", "STRING"), ("input_json", "STRING"),)},
)
FIXED_TEXT_SHA256 = {item['id']: item['sha256'] for item in FIXED_TEXT_REGISTRY}
