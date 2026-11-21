"""Check the experimental Unicode music renderer with an original scale exercise."""

from fractions import Fraction
from xml.etree.ElementTree import fromstring

from pytest import mark, raises

from unicoda import parse_abc, render_abc

melody = 'M:4/4\nL:1/4\nK:C\nD E F G | A B c d |]'


def test_parse_melody():
    headers, measures = parse_abc(melody)
    assert headers['K'] == 'C'
    assert len(measures) == 2
    assert [note.pitch for note in measures[1].notes] == ['A', 'B', 'c', 'd']
    assert sum(note.duration for note in measures[0].notes) == 1
    assert measures[1].final


def test_subdivisions():
    _, measures = parse_abc('M:4/4\nL:1/4\nK:C\nD/ E/ F3/2 G/ A | B2 c2 |')
    assert [note.duration for note in measures[0].notes] == [
        Fraction(1, 8),
        Fraction(1, 8),
        Fraction(3, 8),
        Fraction(1, 8),
        Fraction(1, 4),
    ]


def test_alignment():
    _, measures = parse_abc(melody + '\nw: Step-ping up _ | then~we * come down')
    assert measures[0].lyrics == [['Step-', 'ping', 'up', '_']]
    assert measures[1].lyrics == [['then we', '', 'come', 'down']]


def test_lyric_bar_skips():
    _, measures = parse_abc(
        melody + '\nw: first | then we come down\nw: one two three four | last |'
    )
    assert measures[0].lyrics == [['first', '', '', ''], ['one', 'two', 'three', 'four']]
    assert measures[1].lyrics == [['then', 'we', 'come', 'down'], ['last', '', '', '']]


def test_escape_html():
    source = 'T:<script>alert(1)</script>\nM:4/4\nL:1/4\nK:C\nD E F G |]\nw: one two three <&>'
    root = fromstring(f'<main>{render_abc(source)}</main>')  # noqa: S314 generated from fixture
    assert root.findall('.//div[@class="lyrics"]/span')[-1].text == '<&> '
    assert root.findtext('.//figcaption') == '<script>alert(1)</script>'
    assert root.findtext('.//pre') == source
    assert not root.findall('.//script')


@mark.parametrize(('key', 'opening_positions'), (('C', ['G-2']), ('G', ['G-3', 'f-2'])))
def test_coordinates(key: str, opening_positions: list[str]):
    html = str(render_abc(f'M:4/4\nL:1/4\nK:{key}\nD/ E/ F3/2 G/ A | B2 c2 |]'))
    root = fromstring(f'<main>{html}</main>')  # noqa: S314 generated from fixture
    spans = root.findall('.//figure/div/div[@class="staff-items"]/span')
    notes = [span for span in spans if '-' not in span.attrib['data-pos']]
    assert [span.attrib['data-pos'] for span in notes] == [
        'D01',
        'E03',
        'F05',
        'G11',
        'A13',
        'B01',
        'c09',
    ]
    assert [span.attrib['data-pos'] for span in spans if '-' in span.attrib['data-pos']] == [
        *opening_positions,
        'c-1',
        'a-1',
    ]
    assert 'style="left:' not in html
    assert not root.findall('.//*[@style]')
    assert all(span.keys() == ['data-pos'] and len(span) == 0 for span in notes)
    assert [span.text for span in notes] == [
        '\U0001d160',
        '\U0001d160',
        '\U0001d15f\U0001d16d',
        '\U0001d160',
        '\U0001d15f',
        '\U0001d15e',
        '\U0001d15e',
    ]


def test_lyric_rows():
    source = melody + (
        '\nw: Step-ping up _ | then~we * come down\nw: One two three four | five six _ *'
    )
    source = source.replace('|]', '|') + '\nD E F G |]'
    root = fromstring(f'<main>{render_abc(source)}</main>')  # noqa: S314 generated from fixture
    rows = root.findall('.//div[@class="lyrics"]')
    assert [[span.attrib['data-pos'] for span in row] for row in rows] == [
        ['A01', 'A05', 'A09', 'A13'],
        ['B01', 'B05', 'B09', 'B13'],
        ['A01', 'A05', 'A09', 'A13'],
        ['B01', 'B05', 'B09', 'B13'],
    ]
    assert [[(span.text or '').strip() for span in row] for row in rows] == [
        ['Step-', 'ping', 'up', '_'],
        ['One', 'two', 'three', 'four'],
        ['then we', '', 'come', 'down'],
        ['five', 'six', '_', ''],
    ]
    assert ''.join(rows[1].itertext()).strip() == 'One two three four'
    assert [paragraph.text for paragraph in root.findall('.//details/p')] == [
        'Step- ping up _ then we  come down',
        'One two three four five six _ ',
    ]
    assert all(
        not staff.findall('.//div[@class="lyrics"]')
        for staff in root.findall('.//div[@class="staff-items"]')
    )


@mark.parametrize(
    'source',
    (
        '',
        melody.replace('K:C', 'K:D'),
        melody.replace('M:4/4', 'M:3/4'),
        melody.replace('D E F G', 'D E F'),
        melody.replace('D E F G', '^D E F G'),
        melody.replace('D E F G', '[DE] E F G'),
        melody.replace('D E F G', '"G" D E F G'),
        melody + '\nD E F G |',
        melody + '\nw: Step-ping',
        melody + '\nw: Step-ping up the scale and down a-gain',
        melody + '\nw: one two three four five six seven eight' * 27,
    ),
)
def test_reject_unsupported_notation(source: str):
    with raises(ValueError, match=r'.+'):
        parse_abc(source)
