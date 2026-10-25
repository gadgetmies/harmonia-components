"""The ffmpeg components we enable on top of ``--disable-everything``.

Derived (2026-10-20) from every ffmpeg/ffprobe invocation in Harmonia (the
desktop app and its audio-processing service, plus their test suites) and from
the component contract's list. Harmonia uses only local files and pipes: no
network protocols, no video, no cover-art extraction.
"""
from __future__ import annotations

from typing import Dict, List

# Encoders: contract (libmp3lame, aac, libopus, libvorbis, pcm_*). aac_at
# (AudioToolbox, macOS only) is added per platform in recipes.py: live
# streaming prefers it for HE-AAC and falls back to the native aac encoder.
ENCODERS = [
    "libmp3lame",
    "aac",
    "libopus",
    "libvorbis",
    "pcm_s16le",
    "pcm_s16be",
    "pcm_s24le",
    "pcm_s24be",
    "pcm_s32le",
    "pcm_s32be",
    "pcm_f32le",
    "pcm_f32be",
    "pcm_f64le",
    "pcm_u8",
]

# Decoders: all common audio inputs (mp3, aac, alac, flac, vorbis, opus,
# wavpack, pcm in wav/aiff/caf/w64, mp1/mp2) + the raw pcm variants.
DECODERS = [
    "mp1",
    "mp1float",
    "mp2",
    "mp2float",
    "mp3",
    "mp3float",
    "aac",
    "aac_latm",
    "alac",
    "flac",
    "vorbis",
    "opus",
    "libopus",
    "wavpack",
    "pcm_s8",
    "pcm_u8",
    "pcm_s16le",
    "pcm_s16be",
    "pcm_s16le_planar",
    "pcm_s16be_planar",
    "pcm_s24le",
    "pcm_s24be",
    "pcm_s24le_planar",
    "pcm_s32le",
    "pcm_s32be",
    "pcm_s32le_planar",
    "pcm_f32le",
    "pcm_f32be",
    "pcm_f64le",
    "pcm_f64be",
    "pcm_alaw",
    "pcm_mulaw",
    "adpcm_ima_wav",
    "adpcm_ms",
]

MUXERS = [
    "wav",
    "w64",
    "aiff",
    "mp3",
    "ogg",
    "opus",
    "adts",
    "ipod",
    "mp4",
    "mov",
    "hls",
    "mpegts",
    # raw PCM (-f f32le / s16le / ...): the muxer components are pcm_<fmt>
    "pcm_f32le",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    "null",
]

DEMUXERS = [
    "wav",
    "w64",
    "aiff",
    "caf",
    "mp3",
    "flac",
    "mov",  # mp4 / m4a / alac
    "aac",
    "ogg",  # vorbis, opus, flac-in-ogg
    "wv",  # wavpack
    "matroska",  # mka / webm audio
    "hls",
    "mpegts",
    "concat",
    # raw PCM inputs (-f f32le -i pipe:0 ...)
    "pcm_f32le",
    "pcm_f64le",
    "pcm_s16le",
    "pcm_s24le",
    "pcm_s32le",
    "pcm_u8",
]

PARSERS = ["mpegaudio", "aac", "aac_latm", "flac", "opus", "vorbis"]

BSFS = ["aac_adtstoasc"]

PROTOCOLS = ["file", "pipe"]

# `-f lavfi` is a libavdevice input device (test fixtures synthesise audio).
INDEVS = ["lavfi"]

# The full audio filter set of ffmpeg 7.1 (libavfilter/allfilters.c ff_af_*,
# ff_asrc_*, ff_asink_*) plus the generic `concat` filter, MINUS the ones that
# need an external library we do not build (EXCLUDED_FILTERS). abuffer /
# abuffersink are always built (libavfilter needs them) and are not listed. The audio->video visualisation filters
# (showwaves, showspectrum, ...) are left out: no video encoder is built and
# nothing in Harmonia uses them.
AUDIO_FILTERS = """
aap abench acompressor acontrast acopy acrossfade acrossover acrusher acue
adeclick adeclip adecorrelate adelay adenorm aderivative adrc adynamicequalizer
adynamicsmooth aecho aemphasis aeval aexciter afade afftdn afftfilt afir aformat
afreqshift afwtdn agate aiir aintegral ainterleave alatency alimiter allpass
aloop amerge ametadata amix amultiply anequalizer anlmdn anlmf anlms anull apad
aperms aphaser aphaseshift apsnr apsyclip apulsator arealtime aresample areverse
arls arnndn asdr asegment aselect asendcmd asetnsamples asetpts asetrate asettb
ashowinfo asidedata asisdr asoftclip aspectralstats asplit astats
astreamselect asubboost asubcut asupercut asuperpass asuperstop atempo atilt
atrim axcorrelate bandpass bandreject bass biquad channelmap channelsplit chorus
compand compensationdelay crossfeed crystalizer dcshift deesser dialoguenhance
drmeter dynaudnorm earwax ebur128 equalizer extrastereo firequalizer flanger
haas hdcd headphone highpass highshelf join loudnorm lowpass lowshelf mcompand
pan replaygain sidechaincompress sidechaingate silencedetect silenceremove
speechnorm stereotools stereowiden superequalizer surround tiltshelf treble
tremolo vibrato virtualbass volume volumedetect
anullsink
aevalsrc afdelaysrc afireqsrc afirsrc anoisesrc anullsrc hilbert sinc sine
concat
""".split()

EXCLUDED_FILTERS: Dict[str, str] = {
    "ladspa": "needs LADSPA (external)",
    "lv2": "needs lilv (external)",
    "bs2b": "needs libbs2b (external)",
    "sofalizer": "needs libmysofa (external)",
    "flite": "needs libflite (external)",
    "azmq": "needs libzmq (external)",
    "asr": "needs pocketsphinx (external)",
    "rubberband": "needs librubberband (GPL) — Harmonia runs the rubberband CLI instead",
}


KINDS = {
    "encoder": "encoders",
    "decoder": "decoders",
    "muxer": "muxers",
    "demuxer": "demuxers",
    "parser": "parsers",
    "bsf": "bsfs",
    "protocol": "protocols",
    "indev": "indevs",
    "filter": "filters",
}


def lists() -> Dict[str, List[str]]:
    return {
        "encoder": ENCODERS,
        "decoder": DECODERS,
        "muxer": MUXERS,
        "demuxer": DEMUXERS,
        "parser": PARSERS,
        "bsf": BSFS,
        "protocol": PROTOCOLS,
        "indev": INDEVS,
        "filter": AUDIO_FILTERS,
    }


def unknown_names(available: Dict[str, List[str]], extra_encoders: List[str] = ()) -> Dict[str, List[str]]:
    """Names we enable that ffmpeg's ``configure --list-<kind>s`` does not know.
    configure silently ignores unknown ``--enable-<kind>=`` names, so the build
    checks this before configuring."""
    out = {}
    for kind, names in lists().items():
        if kind == "encoder":
            names = names + list(extra_encoders)
        known = set(available.get(kind, []))
        bad = [n for n in names if n not in known]
        if bad:
            out[kind] = bad
    return out


def configure_flags(extra_encoders: List[str] = ()) -> List[str]:
    def flag(kind: str, names: List[str]) -> str:
        return f"--enable-{kind}=" + ",".join(names)

    return [
        flag("encoder", ENCODERS + list(extra_encoders)),
        flag("decoder", DECODERS),
        flag("muxer", MUXERS),
        flag("demuxer", DEMUXERS),
        flag("parser", PARSERS),
        flag("bsf", BSFS),
        flag("protocol", PROTOCOLS),
        flag("indev", INDEVS),
        flag("filter", AUDIO_FILTERS),
    ]
