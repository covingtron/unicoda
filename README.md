# Unicoda

Render musical notes on a staff with Unicode ♪ and CSS.

```bash
uv pip install unicoda
```

The [scale exercise](examples/scale.abc) has [checked-in HTML output](examples/scale.html).
Open the HTML in a browser to review the score. Regenerate it with `mise render-examples`
(or `mise build`); `mise test` checks that it matches the renderer.

## To do

- [ ] Figure out the best way to convey pitch, rhythm, and lyrics to people using screen readers
  or other assistive tools. This may involve asking people who use these tools or have experience
  with accessible music notation. Then update the score markup, ARIA attributes, and rendering
  accordingly.
