# Unicoda

Render musical notes on a staff with Unicode ♪ and CSS.

```bash
uv pip install unicoda
```

The [scale exercise](examples/scale.abc) has [checked-in HTML output](examples/scale.html).
Open the HTML in a browser to review the score. Regenerate it with `mise render-examples`
(or `mise build`); `mise test` checks that it matches the renderer.

## To do

- [ ] Evaluate how screen readers and other assistive tools can convey pitch, rhythm, and lyrics.
  Test candidate approaches with those tools, then update the score markup, ARIA attributes, and
  rendering to match the chosen approach.
