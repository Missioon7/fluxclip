import os

def to_srt_time(t):
    h = int(t//3600)
    m = int((t%3600)//60)
    s = int(t%60)
    ms = int((t - int(t))*1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def write_srt(path, seg):
    text = seg["text"].strip()

    srt = f"""1
{to_srt_time(seg['start'])} --> {to_srt_time(seg['end'])}
{text}
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(srt)