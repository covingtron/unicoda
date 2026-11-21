"""Compare the rendered scale exercise with its reviewable HTML output."""

from pathlib import Path
from subprocess import check_output

from unicoda import format_abc, parse_abc, render_abc

root = Path(__file__).resolve().parent
example = root / 'examples' / 'scale'
example_html = example.with_suffix('.html')


def format_html(html: str) -> str:
    return check_output(
        [root / 'node_modules/.bin/prettier', '--stdin-filepath', example_html],
        cwd=root,
        encoding='utf-8',
        input=html,
    )


def test_scale():
    source = example.with_suffix('.abc').read_text()
    expected = example_html.read_text()
    rendered = render_abc(source)
    assert format_html(rendered) == expected
    assert format_abc(source) == rendered
    _, measures = parse_abc(source)
    assert ''.join(note.pitch for measure in measures for note in measure.notes) == (
        'GABcdefggfedcBAG'
    )
    assert expected.count('class="lyrics"') == 8
    assert expected.count('data-pos="f-2"') == 1
    assert 'data-pos="f-2"' not in render_abc(source.replace('K:G', 'K:C'))


if __name__ == '__main__':
    example_html.write_text(format_html(render_abc(example.with_suffix('.abc').read_text())))
