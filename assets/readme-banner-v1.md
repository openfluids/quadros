# README banner - readme-banner-v1.jpg

Asset: `assets/readme-banner-v1.jpg` (1408x469, 3:1)

Tool/model: xAI Grok CLI, built-in `image_gen` tool, plus local compositing.

Generated as candidate `v2_quadros`; the rejected alternative is kept in the brand
archive alongside its own prompt.

## Subject prompt

```text
A wide flat plane of fluid seen in gentle three-quarter perspective, receding from the lower right toward a distant horizon, its surface traced with exquisitely fine cyan and teal streamlines that grow finer and hazier with distance. A slender wireframe viewing frustum descends from above the middle of the frame and touches down onto the plane, and the patch of surface it encloses is the only part rendered sharply.
```

## The exact payload sent to the model

```text
Use your image_gen tool ONE time. Generate this image: A wide flat plane of fluid seen in gentle three-quarter perspective, receding from the lower right toward a distant horizon, its surface traced with exquisitely fine cyan and teal streamlines that grow finer and hazier with distance. A slender wireframe viewing frustum, drawn as a few straight hairlines, descends from above the middle of the frame and touches down onto the plane, and the patch of surface it encloses is the only part rendered sharply — its streamlines crisp and fully drawn, with a few small hot coral cores at the vortex centres inside that patch. Everything outside the frustum footprint is soft, dim and dissolving. IMPORTANT: the LEFT THIRD of the frame is calm, dark and completely empty; the plane and the frustum occupy the centre and right. Delicate hairlines throughout, sparse, with much empty dark ground. A stunning abstract scientific artwork, wide 2:1 landscape, for a premium software banner. RENDERING — this governs everything: rendered as exquisitely fine, delicate, hairline glowing lines and fine stippled luminous points. Atmospheric depth of field, volumetric glow, fine film grain, rich deep blacks and luminous highlights. Generous empty dark space; the artwork should feel sparse and restrained, with only a small fraction of the frame actually lit. Cinematic, elegant, refined, expensive, gallery-quality scientific data art. EXPLICITLY AVOID: thick or bold strokes, heavy lines, chunky shapes, neon, garish or oversaturated colour, poster-like flat high contrast, dense solid blocks of glow, a busy or crowded frame. Restraint and delicacy matter more than impact. FRAMING: the image will afterwards be cropped to a very wide 3:1 letterbox, keeping only the middle horizontal band. All important subject matter must sit within the central horizontal band, with generous empty dark margins along the top and bottom edges. Leave the LEFT THIRD dark, calm and completely empty as negative space — a wordmark goes there. PALETTE: a deep near-black charcoal ground with a cool blue cast, approximately #0D1116. Electric cyan and teal as the primary luminous colour, with a hot coral used sparingly on only a few selected features. NO amber, NO gold, NO orange-yellow, NO violet, NO purple, NO green, NO magenta, NO rainbow or spectral colourmaps. Full bleed: no border, no frame, no matte, no letterbox bars, no vignette ring. ABSOLUTELY NO TEXT: no letters, no words, no numbers, no axis labels, no tick marks, no logos, no watermarks, no signatures.
```

## The shared specification

Every banner in the openfluids family is generated from an identical
specification block; only the subject sentence changes per repository. The
`RENDERING`, `FRAMING` and `PALETTE` blocks used here are byte-identical to the
ones that produced the existing seven banners - verified before generating, not
assumed.

The `EXPLICITLY AVOID` clause exists because an earlier revision asked for
"thick", "bold", "punchy" and "very high contrast" artwork and got exactly that:
strokes 3-5 px, lit area up to 2.5x higher, accent saturation 177 against a
baseline of 126. Delicacy has to be stated, and its opposite has to be forbidden.

## Typography

The wordmark is **not** generated. Image models render short lowercase words
unpredictably, and accepting whatever letterforms come back is most of what makes
a generated banner look cheap. The artwork is generated deliberately textless and
the type is set locally:

- **Lato Light at 96 px**, constant across the whole family, tracking 6% of point
  size, ink `#F7F3EC`, left margin 82 px.
- Vertical placement by **optical centring**: the x-height band is centred on the
  frame midline. Measured at 233.5 px for this name, identical to every other
  banner in the family, so the wordmarks sit at the same apparent height despite
  differing ascenders and descenders.
- A small coral `openfluids` eyebrow sits above the repository wordmark.

## Grading

- Ground normalised to `#0D1116` through a shadow-weighted mask, with the black
  point estimated from the darkest 8% of pixels wherever they fall.
- Saturation lifted **only on the brightest accent cores** - a spike tip, a vortex
  centre - leaving the surrounding glow and the ground untouched.

Format: 1408x469 (3:1), JPEG quality 95, no chroma subsampling.
