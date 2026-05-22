class TimelineMapper:

    @staticmethod
    def global_to_relative(captions, clip_start, clip_end, min_len=0.15):

        result = []

        for c in captions:

            if "start" not in c or "end" not in c:
                continue

            # no overlap
            if c["end"] < clip_start or c["start"] > clip_end:
                continue

            rel_start = c["start"] - clip_start
            rel_end = c["end"] - clip_start

            # clamp
            rel_start = max(0, rel_start)
            rel_end = min(clip_end - clip_start, rel_end)

            if rel_end - rel_start < min_len:
                continue

            result.append({
                "start": rel_start,
                "end": rel_end,
                "text": c.get("text", "")
            })

        return result