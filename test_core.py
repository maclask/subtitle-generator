"""Szybki test bez sieci i bez modeli: python test_core.py"""
import os
import sys
import tempfile
import time

import core
import i18n


def write(text, ext):
    fd, path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def test_formats():
    cues = core.read_subs(write("{1}{1}25\n{25}{50}Hello|/world\n{100}{}{y:i}Bye\n", ".txt"))
    assert [(c.start, c.end, c.text) for c in cues] == [(1.0, 2.0, "Hello world"), (4.0, 9.0, "Bye")], cues
    cues = core.read_subs(write("{24}{48}No header\n", ".sub"), fps=24)
    assert (cues[0].start, cues[0].end) == (1.0, 2.0)
    cues = core.read_subs(write("[10][25]/Line one|two\n[30][]Last\n", ".txt"))
    assert [(c.start, c.end, c.text) for c in cues] == [(1.0, 2.5, "Line one two"), (3.0, 8.0, "Last")], cues
    cues = core.read_subs(write("1\n00:00:01,000 --> 00:00:02,000\nSRT in a .txt\n", ".txt"))
    assert cues[0].text == "SRT in a .txt"
    cues = core.read_subs(write("{1}{1}1984\n{48}{72}x\n", ".sub"))  # „1984” to tekst, nie klatki/s
    assert cues[0].text == "1984" and cues[1].start == 48 / 23.976
    cues = core.read_subs(write("{200}{}late\n{100}{150}early --> arrow\n", ".txt"))  # nieposortowane, „-->” w tekście
    assert [c.text for c in cues] == ["early --> arrow", "late"] and all(c.end > c.start for c in cues)
    assert core.looks_like_subs(write("{1}{25}x\n", ".txt"))
    assert not core.looks_like_subs(write("Notatki do filmu\nlinia 2\n", ".txt"))


def test_llm_cues():
    cues = [core.Cue(i, i + 1, f"t{i}") for i in range(10)]
    seen, logs, prog = [], [], []
    calls = {"n": 0}

    def ask(system, user):
        calls["n"] += 1
        if calls["n"] == 1:
            raise core.LLMTimeout("hang")  # pierwsza partia: brak odpowiedzi → jedna powtórka
        import json
        items = json.loads(user.split("Cues to translate:\n")[1])
        seen.append(len(items))
        return [{"id": x["id"], "text": x["text"].upper()} for x in items]

    out = core._llm_cues(cues, "sys", "", logs.append, ask, chunk=3, progress=prog.append, jobs=3)
    assert [c.text for c in out] == [f"T{i}" for i in range(10)]
    assert sorted(seen) == [1, 3, 3, 3] and prog[-1] == 1.0
    assert any("tłumacz nie odpowiada" in m or "no response" in m for m in logs), logs

    def always_hangs(system, user):
        raise core.LLMTimeout("hang")
    try:
        core._llm_cues(cues, "sys", "", logs.append, always_hangs, chunk=5, jobs=2)
        raise AssertionError("expected LLMTimeout")
    except core.LLMTimeout:
        pass


def test_stop_on_error():
    cues = [core.Cue(i, i + 1, f"t{i}") for i in range(40)]
    calls = []

    def ask(system, user):
        calls.append(user)
        if len(calls) == 2:
            raise RuntimeError("auth failed")
        time.sleep(0.3)
        return []

    try:
        core._llm_cues(cues, "sys", "", lambda m: None, ask, chunk=4, jobs=3)
        raise AssertionError("expected RuntimeError")
    except RuntimeError as e:
        assert "auth failed" in str(e)
    assert len(calls) <= 6, len(calls)  # bez poprawki szło wszystkie 10 partii (po 2 próby)


def test_api_retries():
    class Timeout(Exception): pass
    class Overloaded(Exception): pass
    sdk = type("sdk", (), {"APITimeoutError": Timeout, "RateLimitError": Overloaded,
                           "InternalServerError": Overloaded, "APIConnectionError": Overloaded})
    n = {"i": 0}

    def flaky(system, user):
        n["i"] += 1
        if n["i"] == 1:
            raise Overloaded()
        return ["ok"]
    import time as _t
    real_sleep, _t.sleep = _t.sleep, lambda s: None
    try:
        assert core._api_retries(flaky, sdk)("s", "u") == ["ok"] and n["i"] == 2
        try:
            core._api_retries(lambda s, u: (_ for _ in ()).throw(Timeout()), sdk)("s", "u")
            raise AssertionError("expected LLMTimeout")
        except core.LLMTimeout:
            pass
    finally:
        _t.sleep = real_sleep


def test_convert():
    folder = tempfile.mkdtemp()
    src = os.path.join(folder, "film.pl.txt")
    with open(src, "w", encoding="cp1250") as f:
        f.write("{1}{1}25\n{25}{50}Zażółć|gęślą jaźń\n")
    o = core.Options(language="pl", convert=True, on_exists=lambda p: "overwrite")
    out = core.process_file(src, o, lambda m: None, plan=core.plan_outputs(src, o, lambda m: None))
    assert out == [os.path.join(folder, "film.pl.srt")], out
    with open(out[0], encoding="utf-8") as f:
        assert f.read() == "1\n00:00:01,000 --> 00:00:02,000\nZażółć gęślą jaźń\n\n"
    # input already SRT with the same name: never overwritten, even with "overwrite"
    out2 = core.process_file(out[0], o, lambda m: None)
    assert out2 == [os.path.join(folder, "film.pl (2).srt")], out2


def test_proc_timeout():
    started = time.monotonic()
    try:
        core._run_proc([sys.executable, "-c", "import time; time.sleep(30)"], "", timeout=1)
        raise AssertionError("expected LLMTimeout")
    except core.LLMTimeout:
        assert time.monotonic() - started < 10


if __name__ == "__main__":
    i18n.set_lang("pl")
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
