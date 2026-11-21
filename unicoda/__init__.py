"""Render musical notes on a staff with Unicode ♪ and CSS."""

from dataclasses import dataclass, field
from fractions import Fraction
from itertools import accumulate, zip_longest
from re import finditer, fullmatch, match

from jinja2 import Environment, PackageLoader
from markupsafe import Markup

key_signatures = {
    'C': (),
    'G': (('f', '♯'),),  # music sharp sign
}


@dataclass
class Note:
    pitch: str
    duration: Fraction


@dataclass
class Measure:
    notes: list[Note] = field(default_factory=list)
    lyrics: list[list[str]] = field(default_factory=list)
    final: bool = False


def read_notes(source: str, unit: Fraction) -> list[Measure]:
    """Read one complete line of bars; reject syntax we cannot render."""
    measures = [Measure()]
    position = 0
    while position < len(source):
        token = match(r'\s+|\|\]|\||[A-Ga-g](?:\d+(?:/\d+)?|/\d*)?', source[position:])
        if token is None:
            raise ValueError(f'Unsupported ABC near {source[position:]!r}')
        value = token[0]
        position += len(value)
        if value.isspace():
            continue
        if value.startswith('|'):
            if not measures[-1].notes:
                raise ValueError('Empty bar')
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
            measures[-1].notes.append(Note(value[0], duration))
    if measures[-1].notes:
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
            if headers['K'] not in key_signatures or headers['M'] != '4/4':
                raise ValueError('This renderer supports K:C or K:G and M:4/4')
            preceding = read_notes(line, Fraction(headers['L']))
            if any(sum(note.duration for note in measure.notes) != 1 for measure in preceding):
                raise ValueError('Each bar must contain four quarter-note beats')
            measures.extend(preceding)
    if not measures:
        raise ValueError('No music found')
    return headers, measures


def columns(notes: list[Note]) -> list[int]:
    """Return the starting column of each note on the sixteenth-note grid."""
    return list(accumulate((int(note.duration * 16) for note in notes), initial=1))[:-1]


def glyph(duration: Fraction) -> str:
    """Choose the Unicode note glyph and any augmentation dot."""
    return {
        Fraction(1, 8): '\U0001d160',  # musical symbol eighth note
        Fraction(1, 2): '\U0001d15e',  # musical symbol half note
        Fraction(3, 8): '\U0001d15f\U0001d16d',  # quarter note with combining augmentation dot
    }.get(duration, '\U0001d15f')  # musical symbol quarter note


environment = Environment(
    autoescape=True, loader=PackageLoader(__name__, '.'), lstrip_blocks=True, trim_blocks=True
)
environment.filters.update(columns=columns, glyph=glyph)  # pyright: ignore[reportArgumentType]


def render_abc(source: str) -> Markup:
    """Return HTML and CSS that load Noto Music from a URL; usable as a Jinja filter."""
    headers, measures = parse_abc(source)
    return Markup(  # noqa: S704 Jinja autoescapes user input
        environment.get_template('music.j2.html').render(
            accidentals=key_signatures[headers['K']],
            headers=headers,
            measures=measures,
            source=source,
            verses=zip_longest(*(measure.lyrics for measure in measures), fillvalue=()),
        )
    )


def format_abc(source: str, *_arguments: object, **_keywords: object) -> str:
    """Format an abc SuperFences block with the same renderer as the Jinja filter."""
    return str(render_abc(source))
