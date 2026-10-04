import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "script"))
from narration import all_beats, tts_text
rows = [{"id": b["id"], "tts": tts_text(b)} for s, b in all_beats()]
out = Path(__file__).resolve().parents[1] / "audio" / "beats_tts.json"
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
print(len(rows), "beats ->", out)
