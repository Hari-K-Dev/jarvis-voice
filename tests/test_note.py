import json
import shutil
import sys
import types

import numpy
import pytest
import soundfile

from jarvis_voice import cli, config, hook, label, note, transcribe, worker
from jarvis_voice.brief import Brief


def _fake_synth(parts, path):
    soundfile.write(path, numpy.zeros(int(24000 * 2.2), dtype="float32"), 24000)


@pytest.fixture
def stubbed(monkeypatch):
    monkeypatch.setattr(note, "synthesise", _fake_synth)
    monkeypatch.setattr(note, "encode_voice_note", lambda wav, out: open(out, "wb").close())
    monkeypatch.setattr(
        note, "prepare", lambda payload: ("Acme, login fix.", Brief("login fix", "It's fixed."))
    )


def test_render_reports_caption_and_rounded_up_duration(stubbed, tmp_path):
    out = tmp_path / "n.ogg"
    result = note.render({"last_assistant_message": "A long reply\nwith lines."}, str(out))
    assert out.exists()
    assert result == {
        "caption": "Acme, login fix.\nIt's fixed.",
        "duration": 3,
        "complete": False,
    }


def test_render_says_when_the_brief_is_the_whole_reply(stubbed, tmp_path):
    result = note.render({"last_assistant_message": "It's fixed."}, str(tmp_path / "n.ogg"))
    assert result["complete"] is True


def test_a_failed_note_exits_1_and_keeps_the_words_out_of_the_log(monkeypatch, capsys):
    def broken(payload, out):
        raise RuntimeError("SECRET-BRIEF")

    monkeypatch.setattr(note, "render", broken)
    monkeypatch.setattr(sys, "stdin", types.SimpleNamespace(buffer=_bytes_stdin(b"{}")))
    with pytest.raises(SystemExit) as caught:
        cli.run_note("x.ogg")
    assert caught.value.code == 1
    log = config.LOG.read_text(encoding="utf-8")
    assert "voice note failed: RuntimeError" in log and "SECRET" not in log


def _bytes_stdin(data):
    return types.SimpleNamespace(read=lambda: data)


def test_missing_ffmpeg_is_an_error_not_silence(monkeypatch):
    monkeypatch.setattr(note.system, "which", lambda name: None)
    with pytest.raises(FileNotFoundError):
        note.encode_voice_note("a.wav", "a.ogg")


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_real_encoding_produces_ogg_opus(tmp_path):
    config.ensure_home()
    wav, out = tmp_path / "a.wav", tmp_path / "a.ogg"
    _fake_synth([], str(wav))
    note.encode_voice_note(str(wav), str(out))
    data = out.read_bytes()
    assert data.startswith(b"OggS") and b"OpusHead" in data[:64]


def test_away_silences_the_hook_for_every_session():
    config.ensure_home()
    cli.set_away(True)
    assert config.is_away()
    assert hook.skip_reason(
        {"last_assistant_message": "x"},
        {"CLAUDE_CODE_ENTRYPOINT": "cli"},
        config.is_muted() or config.is_away(),
    )
    cli.set_away(False)
    assert not config.is_away()


def test_away_set_while_a_brief_is_queued_stays_silent(monkeypatch):
    spoken = []
    monkeypatch.setattr(worker, "make_brief", lambda *a: Brief("t", "Done."))
    monkeypatch.setattr(worker, "speak", lambda *a: spoken.append(a))
    config.ensure_home()
    config.AWAY.touch()
    worker.run({"last_assistant_message": "Done."})
    assert spoken == []


def test_away_does_not_clear_a_mute_the_person_chose():
    config.ensure_home()
    config.MUTED.touch()
    cli.set_away(True)
    cli.set_away(False)
    assert config.is_muted()


def test_request_sent_from_a_phone_names_the_task(tmp_path):
    """Regression: the channel tag was stripped with its contents, so the request vanished."""
    transcript = tmp_path / "t.jsonl"
    rows = [
        {"type": "user", "message": {"content": "an older request"}},
        {
            "type": "user",
            "message": {"content": '<channel source="telegram-afk" from="H">push it</channel>'},
        },
    ]
    transcript.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    assert label.last_request(str(transcript)) == "push it"


def test_transcribe_joins_segments_and_filters_silence(monkeypatch):
    seen = {}

    class Model:
        def __init__(self, name, **options):
            seen.update(options, name=name)

        def transcribe(self, path, **options):
            seen.update(options)
            segment = types.SimpleNamespace
            return [segment(text=" yes, "), segment(text=" push it ")], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    assert transcribe.transcribe("a.ogg") == "yes, push it"
    assert seen["local_files_only"] is True and seen["vad_filter"] is True
    assert seen["language"] == "en"


def test_transcribe_downloads_the_model_only_when_it_is_missing(monkeypatch):
    attempts = []

    class Model:
        def __init__(self, name, **options):
            attempts.append(options.get("local_files_only", False))
            if options.get("local_files_only"):
                raise OSError("not downloaded")

        def transcribe(self, path, **options):
            return [], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Model))
    assert transcribe.transcribe("a.ogg") == ""
    assert attempts == [True, False]


def test_empty_transcription_is_a_failure(monkeypatch):
    monkeypatch.setattr(transcribe, "transcribe", lambda path: "")
    with pytest.raises(SystemExit) as caught:
        cli.run_transcribe("a.ogg")
    assert caught.value.code == 1


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_whisper_can_really_decode_a_voice_note(tmp_path):
    """Regression: a newer PyAV broke the decoder, which a stubbed model could never catch."""
    audio = pytest.importorskip("faster_whisper.audio")
    config.ensure_home()
    wav, out = tmp_path / "a.wav", tmp_path / "a.ogg"
    _fake_synth([], str(wav))
    note.encode_voice_note(str(wav), str(out))
    assert len(audio.decode_audio(str(out))) > 16000
