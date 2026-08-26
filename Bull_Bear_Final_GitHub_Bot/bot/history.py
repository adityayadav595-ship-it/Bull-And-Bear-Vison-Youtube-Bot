from pathlib import Path

def load_history(path):
    p=Path(path)
    if not p.exists(): return set()
    return {x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()}

def append_history(path,key):
    with Path(path).open("a",encoding="utf-8") as f: f.write(key+"\n")
