"""Check the experimental Unicode music renderer with an original scale exercise."""

from fractions import Fraction
from xml.etree.ElementTree import fromstring

from pytest import mark, raises

from unicoda import format_abc, parse_abc, render_abc

scale = 'T:Scale exercise\nM:4/4\nL:1/4\nK:C\nD E F G | A B c d |]'


def test_scale():
    headers, measures = parse_abc(scale)
    assert headers['K'] == 'C'
    assert len(measures) == 2
    assert [note.pitch for note in measures[1].notes] == ['A', 'B', 'c', 'd']
    assert sum(note.duration for note in measures[0].notes) == 1
    assert measures[1].final
    html = render_abc(scale)
    assert html.count('class="event"') == 8
    assert html.count('class="clef"') == 1
    assert html.count('class="meter"') == 2
    assert 'https://raw.githubusercontent.com/google/fonts/main/ofl/notomusic/' in html
    assert 'data:font' not in html
    assert '<svg' not in html
    assert format_abc(scale) == html
    assert render_abc(scale.replace('K:C', 'K:G')).count('class="key"') == 1


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
    _, measures = parse_abc(scale + '\nw: Step-ping up _ | then~we * come down')
    assert measures[0].lyrics == [['Step-', 'ping', 'up', '_']]
    assert measures[1].lyrics == [['then we', '', 'come', 'down']]


def test_lyric_bar_skips():
    _, measures = parse_abc(
        scale + '\nw: first | then we come down\nw: one two three four | last |'
    )
    assert measures[0].lyrics == [['first', '', '', ''], ['one', 'two', 'three', 'four']]
    assert measures[1].lyrics == [['then', 'we', 'come', 'down'], ['last', '', '', '']]


def test_chords():
    source = 'M:4/4\nL:1/4\nK:C\n"<&>" D E F G |]\nw: one two three <&>'
    root = fromstring(f'<main>{render_abc(source)}</main>')  # noqa: S314 generated from fixture
    assert [span.text for span in root.findall('.//span[@class="chord"]')] == ['<&>']
    assert root.findall('.//div[@class="lyrics"]/span')[-1].text == '<&> '


def test_coordinates():
    html = str(render_abc('M:4/4\nL:1/4\nK:C\nD/ E/ F3/2 G/ A | B2 c2 |]'))
    root = fromstring(f'<main>{html}</main>')  # noqa: S314 generated from fixture
    assert [span.attrib['data-pos'] for span in root.findall('.//span[@class="event"]')] == [
        'D04',
        'E06',
        'F08',
        'G14',
        'A16',
        'B04',
        'c12',
    ]
    assert [span.attrib['data-pos'] for span in root.findall('.//span[@class="clef"]')] == ['G01']
    assert [span.attrib['data-pos'] for span in root.findall('.//span[@class="meter"]')] == [
        'c03',
        'a03',
    ]
    assert 'style="left:' not in html
    assert 'style="--pitch:' not in html


def test_lyric_rows():
    source = scale + (
        '\nw: Step-ping up _ | then~we * come down\nw: One two three four | five six _ *'
    )
    root = fromstring(f'<main>{render_abc(source)}</main>')  # noqa: S314 generated from fixture
    rows = root.findall('.//div[@class="lyrics"]')
    assert [[span.attrib['data-pos'] for span in row] for row in rows] == [
        ['A04', 'A08', 'A12', 'A16'],
        ['B04', 'B08', 'B12', 'B16'],
        ['A04', 'A08', 'A12', 'A16'],
        ['B04', 'B08', 'B12', 'B16'],
    ]
    assert [[(span.text or '').strip() for span in row] for row in rows] == [
        ['Step-', 'ping', 'up', '_'],
        ['One', 'two', 'three', 'four'],
        ['then we', '', 'come', 'down'],
        ['five', 'six', '_', ''],
    ]
    assert ''.join(rows[1].itertext()).strip() == 'One two three four'
    assert all(
        not staff.findall('.//div[@class="lyrics"]')
        for staff in root.findall('.//div[@class="staff-items"]')
    )


@mark.parametrize(
    'source',
    (
        '',
        scale.replace('K:C', 'K:D'),
        scale.replace('M:4/4', 'M:3/4'),
        scale.replace('D E F G', 'D E F'),
        scale.replace('D E F G', '^D E F G'),
        scale.replace('D E F G', '[DE] E F G'),
        scale + '\nD E F G |',
        scale + '\nw: Step-ping',
        scale + '\nw: Step-ping up the scale and down a-gain',
        scale + '\nw: one two three four five six seven eight' * 27,
    ),
)
def test_reject_unsupported_notation(source: str):
    with raises(ValueError, match=r'.+'):
        parse_abc(source)
