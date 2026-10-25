"""Per-source WebRTC speech detection; no audio is sent to a service."""
import audioop


class SpeechActivity:
    def __init__(self, rate):
        self.rate=rate
        self.pending=b''
        self.last=False
        self.vad=None
        if rate in (8000,16000,32000,48000):
            import webrtcvad
            self.vad=webrtcvad.Vad(1)

    def voiced(self, pcm):
        if self.vad is None: return audioop.rms(pcm,2)>=100
        self.pending+=pcm
        size=self.rate//50*2
        decisions=[]
        while len(self.pending)>=size:
            frame,self.pending=self.pending[:size],self.pending[size:]
            decisions.append(self.vad.is_speech(frame,self.rate))
        if decisions: self.last=any(decisions)
        return self.last


def apply_terms(text, rules):
    # Apply explicit user corrections once; replacements never cascade.
    import re
    mapping={}
    for line in rules.splitlines():
        if '=>' in line:
            wrong,right=line.split('=>',1)
            if wrong.strip() and right.strip(): mapping[wrong.strip()]=right.strip()
    if not mapping: return text
    pattern='|'.join(re.escape(key) for key in sorted(mapping,key=len,reverse=True))
    return re.sub(pattern,lambda match:mapping[match.group()],text)
