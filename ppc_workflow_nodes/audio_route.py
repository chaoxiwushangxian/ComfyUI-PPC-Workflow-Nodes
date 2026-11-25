"""Single-speaker audio route for node 7801602.

Deliberate bug-fix: the recorded VRGDG sandbox does not provide isinstance, so
this script raised NameError before the route could run. This function is
ordinary Python and keeps the script's route rules, including isinstance.
It does not read a code string and it does not restore that NameError.
"""

from __future__ import annotations

import json
import re

from .serialize import pack_error, pack_success


def route_single_speaker(input_text, input_json=""):
    result = ""
    try:
        result=json.loads(input_text)
        route_context=json.loads(input_json)
        uploaded_audio_slots=route_context['env']['inventory']['audios']
        if (not isinstance(uploaded_audio_slots,list) or
            any(not isinstance(slot,int) or isinstance(slot,bool) or slot not in (1,2,3) for slot in uploaded_audio_slots)):
            raise ValueError('invalid_audio_inventory')
        for slot in (1,2,3):
            result['route_audio_slot_'+str(slot)]=slot if slot in uploaded_audio_slots else 0
        def route_single_speaker_audio(payload,context):
            segment=context['segment'];env=context['env']
            audios=env.get('inventory',{}).get('audios',[])
            if len(audios)<2 or audios!=list(range(1,len(audios)+1)):return None,'not_dense_multiple_reference_voices'
            if not segment.get('native_audio') or any(segment.get(k) for k in ['raw_passthrough','visual_only','guide_enabled','continuation','internal_split_origin','voice_visual_scope']):return None,'different_or_offscreen_route'
            units=segment.get('speaker_units') or []
            if not units:return None,'no_speaker_units'
            voices=sorted({int(u['voice']) for u in units})
            speakers=sorted({str(u['subject']) for u in units})
            if len(voices)!=1 or len(speakers)!=1:return None,'multiple_voices_in_segment'
            voice=voices[0];speaker=speakers[0]
            if voice not in audios:return None,'voice_not_uploaded'
            prompt=payload['prompt']
            dialogues=re.findall(r'<d>.*?</d>',prompt,re.S)
            if len(dialogues)!=len(units):return None,'nonexact_utterance_scope'
            for line in dialogues:
                if re.search(r'<Audio\s+\d+>',line):return None,'audio_tag_in_dialogue'
            def blank(m):return ' '*len(m[0])
            masked=re.sub(r'<d>.*?</d>',blank,prompt,flags=re.S)
            cues=re.findall(r'(?m)^Utterance voice/mouth binding: <Subject (\d+)> \(S(\d+)\) alone delivers the following written line using the vocal timbre of <Audio (\d+)>\.',masked)
            if len(cues)!=len(units):return None,'binding_not_applied'
            for cue in cues:
                if cue[0]!=speaker or int(cue[2])!=voice:return None,'binding_disagreement'
            guard="Each referenced audio supplies only its declared character's timbre, never the other character's speech or mouth motion."
            if masked.count(guard)!=1:return None,'binding_guard_missing'
            keys=['subject_definitions','summary','retention_analysis','detailed_description','overall_soundscape','non_diegetic_music']
            marks=list(re.finditer(r'(?m)^('+'|'.join(keys)+r'):[ \t]*\r?\n',masked))
            if [m[1] for m in marks]!=keys:return None,'noncanonical_sections'
            owners={}
            for line in masked[marks[0].end():marks[1].start()].splitlines():
                refs=re.findall(r'<Audio\s+(\d+)>',line)
                if not refs:continue
                owner=re.match(r'^\s*-?\s*<Subject\s+(\d+)>',line)
                if not owner or len(set(refs))!=1:return None,'unowned_audio_definition'
                number=int(refs[0])
                if number in owners and owners[number]!=owner[1]:return None,'conflicting_audio_owner'
                owners[number]=owner[1]
            if owners.get(voice)!=speaker:return None,'speaker_definition_disagreement'
            for number in re.findall(r'<Audio\s+(\d+)>',masked[marks[3].start():]):
                if int(number)!=voice:return None,'other_audio_used_by_current_action'
            for number in re.findall(r'<Audio\s+(\d+)>',masked):
                if int(number)!=voice and int(number) not in owners:return None,'unowned_audio_mention'
            for number in re.findall(r'(?:emotion|情绪|语气|mood|tone)[^<\n]{0,40}<Audio\s+(\d+)>',masked,re.I):
                if int(number)!=voice:return None,'other_audio_used_as_emotion'
            def renumber(m):
                number=int(m[1])
                if number==voice:return '<Audio 1>'
                return 'the separate voice of <Subject '+owners[number]+'> (its reference audio is not attached in this segment)'
            parts=re.split(r'(<d>.*?</d>)',prompt,flags=re.S)
            pieces=[]
            for i,part in enumerate(parts):
                if i%2:pieces.append(part)
                else:pieces.append(re.sub(r'<Audio\s+(\d+)>',renumber,part))
            out=''.join(pieces)
            out=out.replace(guard,guard+' In this segment only <Audio 1> is attached: it is the voice of <Subject '+speaker+'>, who alone speaks every scripted line here; every other visible character keeps its mouth closed except for separately authored non-speech reactions.',1)
            assert re.findall(r'<d>.*?</d>',out,re.S)==dialogues,'AUDIO_ROUTE_DIALOGUE_CHANGED'
            expected=re.findall(r'<(?:Picture|Video|Subject)\s+\d+>',masked)+['<Subject '+speaker+'>']
            for number in re.findall(r'<Audio\s+(\d+)>',masked):
                if int(number)!=voice:expected.append('<Subject '+owners[int(number)]+'>')
            assert sorted(re.findall(r'<(?:Picture|Video|Subject)\s+\d+>',re.sub(r'<d>.*?</d>','',out,flags=re.S)))==sorted(expected),'AUDIO_ROUTE_REFERENCE_CHANGED'
            assert set(re.findall(r'<Audio\s+\d+>',re.sub(r'<d>.*?</d>','',out,flags=re.S)))=={'<Audio 1>'},'AUDIO_ROUTE_LOCAL_NUMBERING'
            return dict(prompt=out,voice=voice,speaker=speaker),'single_speaker_segment'
        try:
            routed,reason=route_single_speaker_audio(result,route_context)
        except Exception:
            routed,reason=None,'fail_closed_original_route'
        if routed is not None:
            result['prompt']=routed['prompt']
            result['route_audio_slot_1']=routed['voice']
            result['route_audio_slot_2']=0
            result['route_audio_slot_3']=0
        result['reference_audio_route_v1']=dict(applied=routed is not None,reason=reason)
        return pack_success(result)
    except Exception as exc:
        return pack_error(exc)


class PPCFixed7801602:
    """Fixed single-speaker audio route. isinstance works; the sandbox NameError does not."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "input_text": ("STRING", {"forceInput": True}),
                "input_json": ("STRING", {"forceInput": True}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "BOOLEAN")
    RETURN_NAMES = ("result_text", "result_json", "has_error")
    FUNCTION = "run"
    CATEGORY = "PPC/Workflow"
    DESCRIPTION = "Route one dense reference voice onto Audio 1 without rewriting <d> lines."

    def run(self, input_text, input_json):
        return route_single_speaker(input_text, input_json)
