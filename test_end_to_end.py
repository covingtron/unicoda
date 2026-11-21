"""Compare the rendered scale exercise with its reviewable HTML output."""

from pathlib import Path

from unicoda import format_abc, render_abc

example = Path(__file__).parent / 'examples' / 'scale'


def test_scale():
    source = example.with_suffix('.abc').read_text()
    expected = example.with_suffix('.html').read_text()
    assert render_abc(source) == expected
    assert format_abc(source) == expected
    assert render_abc(source.replace('K:C', 'K:G')).count('class="key"') == 1


if __name__ == '__main__':
    example.with_suffix('.html').write_text(str(render_abc(example.with_suffix('.abc').read_text())))
