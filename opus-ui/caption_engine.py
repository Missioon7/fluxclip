def generate_captions(segments):
    captions = []

    for seg in segments:
        captions.append({
            "text": seg["text"],
            "start": seg["start"],
            "end": seg["end"]
        })

    return captions