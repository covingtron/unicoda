"""Render music and more with Unicode glyphs and CSS."""

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import accumulate
from re import finditer, fullmatch, match

from markupsafe import Markup, escape

staff_size_rem = 4.8
music_css = r"""@font-face {
    font-family: 'Unicoda Music';
    src: url('https://raw.githubusercontent.com/google/fonts/main/ofl/notomusic/NotoMusic-Regular.ttf')
        format('truetype');
}

.unicoda-music {
    --staff-size: STAFF_SIZE_REMrem;
    --staff-step: calc(var(--staff-size) * 0.122);
    --note-size: calc(var(--staff-step) * 4);
    margin: 1.5rem 0;
    color: inherit;
}

.unicoda-music details {
    text-align: left;
}

.unicoda-music .music-score {
    display: flex;
    flex-wrap: wrap;
    overflow-x: auto;
    padding: 0.5rem 0;
    gap: 0.5rem 0;
}

.unicoda-music .music-measure {
    flex: 0 0 var(--width);
    height: 10rem;
    position: relative;
    break-inside: avoid;
}

.unicoda-music .music-measure::before {
    content: '\1d11a'; /* MUSICAL SYMBOL FIVE-LINE STAFF */
    font: var(--staff-size) / 1 'Unicoda Music';
    left: calc(-0.05 * var(--staff-size) * var(--stretch));
    position: absolute;
    top: 2rem;
    transform: scaleX(var(--stretch));
    transform-origin: left top;
}

.unicoda-music .music-measure::after {
    border-right: 1px solid;
    content: '';
    height: calc(var(--staff-step) * 8);
    position: absolute;
    right: 0;
    top: 2.036rem;
}

.unicoda-music .music-final::after {
    border-right: 4px double;
}
.unicoda-music .music-event {
    position: absolute;
    top: 0;
}
.unicoda-music .music-chord {
    position: absolute;
    top: 0;
    font-weight: bold;
}
.unicoda-music .music-lyric {
    position: absolute;
    top: 8rem;
    white-space: pre;
}

.unicoda-music .music-note {
    font: var(--note-size) / 1 'Unicoda Music';
    position: absolute;
    left: 0;
    top: calc(2.036rem + var(--pitch) * var(--staff-step) - var(--note-size) * 0.873);
}

.unicoda-music .music-down {
    transform: rotate(180deg);
    top: calc(2.036rem + var(--pitch) * var(--staff-step) - var(--note-size) * 0.127);
}

.unicoda-music .music-dot {
    position: absolute;
    left: 0.9rem;
    top: calc(2.036rem + var(--pitch) * var(--staff-step) - 0.6rem);
}

.unicoda-music .music-clef {
    font: var(--note-size) / 1 'Unicoda Music';
    position: absolute;
    left: 0.1rem;
    top: calc(2.036rem + 6 * var(--staff-step) - var(--note-size) * 0.873);
}

.unicoda-music .music-key {
    font: 1.5rem/1 'Unicoda Music';
    position: absolute;
    left: 1.8rem;
    top: calc(2.036rem - 1.5rem * 0.8645);
}

.unicoda-music .music-meter {
    font: bold 1.7rem/1.37 serif;
    position: absolute;
    left: 2.45rem;
    top: 2rem;
}
""".replace('STAFF_SIZE_REM', str(staff_size_rem))


@dataclass
class Note:
    pitch: str
    duration: Fraction
    chord: str = ''
    lyric: str = ''


@dataclass
class Measure:
    notes: list[Note] = field(default_factory=list)
    final: bool = False


def read_notes(source: str, unit: Fraction) -> list[Measure]:  # noqa: C901
    """Read one complete line of bars; reject syntax we cannot render."""
    measures = [Measure()]
    chord = ''
    position = 0
    while position < len(source):
        token = match(r'\s+|"[^"\n]+"|\|\]|\||[A-Ga-g](?:\d+(?:/\d+)?|/\d*)?', source[position:])
        if token is None:
            raise ValueError(f'Unsupported ABC near {source[position:]!r}')
        value = token[0]
        position += len(value)
        if value.isspace():
            continue
        if value.startswith('"'):
            if chord:
                raise ValueError('A chord must precede a note')
            chord = value[1:-1]
        elif value.startswith('|'):
            if not measures[-1].notes or chord:
                raise ValueError('Empty bar or chord without a note')
            measures[-1].final = value == '|]'
            if measures[-1].final and source[position:].strip():
                raise ValueError('Music follows the final bar')
            measures.append(Measure())
        else:
            length = value[1:]
            numerator, separator, denominator = (length or '1').partition('/')
            duration = unit * Fraction(
                int(numerator or '1'), int(denominator or '2') if separator else 1
            )
            if duration not in {Fraction(1, 8), Fraction(1, 4), Fraction(3, 8), Fraction(1, 2)}:
                raise ValueError(f'Unsupported note duration: {value}')
            if value[0] not in 'DEFGABcdefg':
                raise ValueError(f'Pitch outside D4 to G5: {value}')
            measures[-1].notes.append(Note(value[0], duration, chord))
            chord = ''
    if measures[-1].notes or chord:
        raise ValueError('End each music line with a barline')
    return measures[:-1]


def align_lyrics(source: str, measures: list[Measure]) -> None:
    """Align syllables, hyphens, skipped notes, and melismas to the preceding music line."""
    notes = [note for measure in measures for note in measure.notes]
    boundaries = set(accumulate(len(measure.notes) for measure in measures))
    position = 0
    for token in finditer(r'[^\s\-_*|]+-?|[-_*|]', source):
        value = token[0]
        if value == '|':
            position = min((end for end in boundaries if end >= position), default=len(notes))
            continue
        if position >= len(notes):
            raise ValueError('More lyric syllables than notes')
        notes[position].lyric = '' if value == '*' else value.replace('~', ' ')
        position += 1
    if position != len(notes):
        raise ValueError(f'Lyrics cover {position} of {len(notes)} notes; use * to skip notes')


def parse_abc(source: str) -> tuple[dict[str, str], list[Measure]]:  # noqa: C901
    """Read one treble melody in C or G, with explicit meter, unit length, and lyrics."""
    headers: dict[str, str] = {}
    measures: list[Measure] = []
    preceding: list[Measure] = []
    for raw_line in source.splitlines():
        line = raw_line.split('%', 1)[0].strip()
        if not line:
            continue
        if line.startswith('w:'):
            if not preceding:
                raise ValueError('Use one w: lyric line after each music line')
            align_lyrics(line[2:].strip(), preceding)
            preceding = []
        elif fullmatch(r'[A-Za-z]:.*', line):
            name, value = line.split(':', 1)
            if name not in {'X', 'T', 'C', 'M', 'L', 'K'} or measures:
                raise ValueError(f'Unsupported ABC field: {name}')
            headers[name] = value.strip()
        else:
            if measures and measures[-1].final:
                raise ValueError('Music follows the final bar')
            if not {'M', 'L', 'K'} <= headers.keys():
                raise ValueError('Specify M:, L:, and K: before the music')
            if headers['K'] not in {'C', 'G'} or headers['M'] != '4/4':
                raise ValueError('This renderer supports K:C or K:G and M:4/4')
            preceding = read_notes(line, Fraction(headers['L']))
            if any(sum(note.duration for note in measure.notes) != 1 for measure in preceding):
                raise ValueError('Each bar must contain four quarter-note beats')
            measures.extend(preceding)
    if not measures:
        raise ValueError('No music found')
    return headers, measures


def render_measure(measure: Measure, key: str, *, first: bool) -> str:
    """Place glyphs on a measured Noto Music staff, with duration and lyric spacing."""
    widths = [
        max(float(note.duration) * 12, len(note.lyric) * 0.55 + 0.75) for note in measure.notes
    ]
    position = 3.5 if first else 0.75
    width = sum(widths) + position
    items = (
        [
            '<span class="music-clef">\U0001d11e</span>',  # MUSICAL SYMBOL G CLEF
            '<span class="music-meter">4<br>4</span>',
        ]
        if first
        else []
    )
    if first and key == 'G':
        items.append('<span class="music-key">\u266f</span>')  # MUSIC SHARP SIGN
    for note, spacing in zip(measure.notes, widths, strict=True):
        step = 'gfedcBAGFED'.index(note.pitch) - 1
        glyph = {
            Fraction(1, 8): '\U0001d160',  # MUSICAL SYMBOL EIGHTH NOTE
            Fraction(1, 2): '\U0001d15e',  # MUSICAL SYMBOL HALF NOTE
        }.get(note.duration, '\U0001d15f')  # MUSICAL SYMBOL QUARTER NOTE
        direction = ' music-down' if step <= 4 else ''
        items.append(
            f'<span class="music-event" style="left:{position:.3f}rem">'
            f'<span class="music-chord">{escape(note.chord)}</span>'
            f'<span class="music-note{direction}" style="--pitch:{step}" '
            f'data-pitch="{note.pitch}" data-duration="{note.duration}">{glyph}</span>'
            + (
                f'<span class="music-dot" style="--pitch:{step}">\u00b7</span>'  # MIDDLE DOT
                if note.duration == Fraction(3, 8)
                else ''
            )
            + f'<span class="music-lyric">{escape(note.lyric)}</span></span>'
        )
        position += spacing
    final = ' music-final' if measure.final else ''
    return (
        f'<div class="music-measure{final}" style="--width:{width:.3f}rem;'
        f'--stretch:{width / staff_size_rem:.5f}" aria-hidden="true">{"".join(items)}</div>'
    )


def render_abc(source: str) -> Markup:
    """Return HTML and CSS that load Noto Music from a URL; usable as a Jinja filter."""
    headers, measures = parse_abc(source)
    title = escape(headers.get('T', 'Music'))
    lyrics = ' '.join(note.lyric for measure in measures for note in measure.notes)
    return Markup(  # noqa: S704 escaped text surrounds only generated markup
        f'<style>{music_css}</style><figure class="unicoda-music">'
        f'<figcaption>{title}</figcaption><div class="music-score">'
        + ''.join(
            render_measure(measure, headers['K'], first=index == 0)
            for index, measure in enumerate(measures)
        )
        + f'</div><details><summary>Lyrics and ABC source</summary><p>{escape(lyrics)}</p>'
        f'<pre>{escape(source)}</pre></details></figure>'
    )


def format_abc(source: str, *_arguments: object, **_keywords: object) -> str:
    """Format an abc SuperFences block with the same renderer as the Jinja filter."""
    return str(render_abc(source))
