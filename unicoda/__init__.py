"""Render musical notes on a staff with Unicode ♪ and CSS."""

from dataclasses import dataclass, field
from fractions import Fraction
from importlib.resources import files
from itertools import accumulate, zip_longest
from re import finditer, fullmatch, match

from markupsafe import Markup, escape

slots_per_measure = 16
staff_size_rem = 4.8
stylesheet = (
    files(__package__)
    .joinpath('music.css')
    .read_text()
    .replace('SLOTS_PER_MEASURE', str(slots_per_measure))
    .replace('STAFF_SIZE_REM', str(staff_size_rem))
    + ''.join(
        '.unicoda-music [data-pos$="%02d"] { --column: %d; }' % (column, column - 4)
        for column in range(4, 4 + slots_per_measure)
    )
    + ''.join(
        '.unicoda-music .staff-items [data-pos^="%s"] '
        '{ --pitch: %d; --turn: %ddeg; --head-center: %s; }'
        % (pitch, index - 1, 180 if index <= 5 else 0, 0.127 if index <= 5 else 0.873)
        for index, pitch in enumerate('gfedcBAGFED')
    )
)


@dataclass
class Note:
    pitch: str
    duration: Fraction
    chord: str = ''


@dataclass
class Measure:
    notes: list[Note] = field(default_factory=list)
    lyrics: list[list[str]] = field(default_factory=list)
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
    boundaries = list(accumulate(len(measure.notes) for measure in measures))
    if len(measures[0].lyrics) == 26:
        raise ValueError('Use at most 26 lyric rows per music line')
    lyrics = [''] * boundaries[-1]
    position = 0
    for token in finditer(r'[^\s\-_*|]+-?|[-_*|]', source):
        value = token[0]
        if value == '|':
            position = next((end for end in boundaries if end >= position), len(lyrics))
            continue
        if position >= len(lyrics):
            raise ValueError('More lyric syllables than notes')
        lyrics[position] = '' if value == '*' else value.replace('~', ' ')
        position += 1
    if position != len(lyrics):
        raise ValueError(f'Lyrics cover {position} of {len(lyrics)} notes; use * to skip notes')
    for measure, end in zip(measures, boundaries, strict=True):
        measure.lyrics.append(lyrics[end - len(measure.notes) : end])


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
                raise ValueError('Place w: lyrics after a music line')
            align_lyrics(line[2:].strip(), preceding)
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
    slot_width_rem = max(
        max(
            0.75,
            (max((len(row[index]) for row in measure.lyrics), default=0) * 0.55 + 0.75)
            / (note.duration * slots_per_measure),
        )
        for index, note in enumerate(measure.notes)
    )
    prefix_width_rem = 3.5 if first else 0.75
    width_rem = slot_width_rem * slots_per_measure + prefix_width_rem
    columns = list(
        accumulate([4, *(int(note.duration * slots_per_measure) for note in measure.notes)])
    )
    items = (
        [
            '<span class="clef" data-pos="G01">\U0001d11e</span>',  # MUSICAL SYMBOL G CLEF
            '<span class="meter" data-pos="c03">4</span>',
            '<span class="meter" data-pos="a03">4</span>',
        ]
        if first
        else []
    )
    if first and key == 'G':
        items.append('<span class="key" data-pos="f02">\u266f</span>')  # MUSIC SHARP SIGN
    for note, column in zip(measure.notes, columns[:-1], strict=True):
        glyph = {
            Fraction(1, 8): '\U0001d160',  # MUSICAL SYMBOL EIGHTH NOTE
            Fraction(1, 2): '\U0001d15e',  # MUSICAL SYMBOL HALF NOTE
        }.get(note.duration, '\U0001d15f')  # MUSICAL SYMBOL QUARTER NOTE
        items.append(
            f'<span class="event" data-pos="{note.pitch}{column:02}">'
            + (f'<span class="chord">{escape(note.chord)}</span>' if note.chord else '')
            + f'<span class="note" data-duration="{note.duration}">{glyph}</span>'
            + (
                '<span class="dot">\u00b7</span>'  # MIDDLE DOT
                if note.duration == Fraction(3, 8)
                else ''
            )
            + '</span>'
        )
    lyrics = ''.join(
        '<div class="lyrics">'
        + ''.join(
            f'<span data-pos="{chr(65 + index)}{column:02}">{escape(lyric)} </span>'
            for lyric, column in zip(row, columns[:-1], strict=True)
        )
        + '</div>'
        for index, row in enumerate(measure.lyrics)
    )
    final = ' final' if measure.final else ''
    return (
        f'<div class="measure{final}" style="--stretch:{width_rem / staff_size_rem:.5f};'
        f'--slot:{slot_width_rem:.3f}rem;'
        f'--prefix:{prefix_width_rem}rem"><div class="staff-items" aria-hidden="true">'
        f'{"".join(items)}</div>{lyrics}</div>'
    )


def render_abc(source: str) -> Markup:
    """Return HTML and CSS that load Noto Music from a URL; usable as a Jinja filter."""
    headers, measures = parse_abc(source)
    title = escape(headers.get('T', 'Music'))
    lyrics = ''.join(
        f'<p>{escape(" ".join(lyric for row in verse for lyric in row))}</p>'
        for verse in zip_longest(*(measure.lyrics for measure in measures), fillvalue=())
    )
    return Markup(  # noqa: S704 escaped text surrounds only generated markup
        f'<style>{stylesheet}</style><figure class="unicoda-music">'
        f'<figcaption>{title}</figcaption><div class="score">'
        + ''.join(
            render_measure(measure, headers['K'], first=index == 0)
            for index, measure in enumerate(measures)
        )
        + f'</div><details><summary>Lyrics and ABC source</summary>{lyrics}'
        f'<pre>{escape(source)}</pre></details></figure>'
    )


def format_abc(source: str, *_arguments: object, **_keywords: object) -> str:
    """Format an abc SuperFences block with the same renderer as the Jinja filter."""
    return str(render_abc(source))
