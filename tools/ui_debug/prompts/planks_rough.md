<!-- attach: ui/assets-gothic/grounds/cobbles_oval.png -->
<!-- attach: ui/assets-gothic/grounds/candidates/planks_rough_c01.png -->
<!-- TWO ATTACHMENTS, EACH DOING ONE JOB, because the thing that went wrong in every cobbles
     batch was a single reference being asked to carry both the camera and the look.

     FIRST is cobbles_oval.png, the plate filed on 2026-09-23. It is here ONLY for the
     camera: it measures 31.6 degrees, and its measuring ring on the source image read 31.5
     independently -- a 0.1 degree agreement, the tightest on file. It is also a rimless
     ragged patch, so it already shows the kind of edge this brief wants.

     SECOND is planks_rough_c01.png, the timber patch this brief exists to reproduce
     properly. It is here ONLY for the material and the construction. It carries NO usable
     camera and the brief says so: the ink is 1181 x 855, h/w 0.724, which is 46.4 degrees
     if the patch is square in plan, 32.9 if 3:4 and 74.9 if 4:3 -- a rectangle cannot give
     up a camera, because its foreshortening and its plan proportions are not separable.
     ground_ellipse returns 21.8 on it and that number means nothing; 14% of its rows are
     within 2% of the widest, so it is not an ellipse at all. That is the whole reason the
     green ring below exists.

     THE CEILING IS 0.530, NOT 0.500. This brief is built on the cobbles_oval one, and 0.530
     is the figure with a pass on record -- it put flagstones_slab at 32.0 and the cobbles
     batch at a mean of 32.6. The five plates on file sit between 0.517 and 0.530, so a
     plank plate briefed at 0.500 would come in around 30 degrees and be the only plate on
     the board outside the 1.0 degree tolerance.

     STATED AS A CEILING AND NOT AS A TARGET, deliberately. Measured twice on this
     generator, on monks and again on plates: it hugs a stated BOUND and ignores a stated
     TARGET. The same slab brief with the ratio written as a target produced 50.8 to 68.3;
     written as a ceiling it produced 31.8, 31.9, 32.0, 32.2 and 33.5. -->
Based on the two attached images, generate five versions of a rough timber plank floor.

THE FIRST ATTACHED IMAGE is a cobbled stone plate. Take from it ONLY the camera direction,
the flat orthographic projection, the lighting, and the general scale in frame. Do not copy
its stone, and do not copy the shape of its outline.

THE SECOND ATTACHED IMAGE is a patch of heavy timber baulks. Take from it ONLY the material
and the construction: the plank sizes, the way they are laid, the split and worn surfaces,
and the ragged stepped perimeter. DO NOT TAKE THE CAMERA FROM IT. It is a rectangular patch
and it carries no camera; the camera is specified below and that specification wins.

ONE LIMIT, AND IT IS A MEASUREMENT, NOT AN IMPRESSION: the measuring ring described below
must never be more than 0.530 as tall as it is wide. Measure it on your own output before
you finish. Past that the camera has climbed too high and the tile is wrong, however good
the timber looks.

THE MEASURING RING

Draw one closed ellipse around the entire tile in pure spring green, RGB 0 255 128.

It is a measuring mark, not part of the scene:

- flat solid colour
- no shading
- no texture
- no glow
- crisp edge
- line thickness about 2% of the tile width

The green ellipse is a perfect circle lying flat on exactly the same ground plane as the
planks, seen from the same camera, so it is foreshortened exactly as they are.

Its measured height must be no more than 0.530 of its measured width.

The ring must be about 1.5x the width of the planked area, with an obvious transparent gap
between the planks and the ring on every side. It must not touch, overlap, or pass behind
the tile.

The entire ring must be visible and unbroken, with its long axis perfectly horizontal.

THE TIMBER

Heavy split oak baulks and planks, roughly hewn, laid flat on packed earth as a working
floor or a crude boarded yard.

- weathered grey-brown oak, some pieces darker than others
- deep split grain running the length of each piece
- open shakes and checks along the grain
- knots, worn nail holes, chipped and rounded arrises
- dirt and moss packed into the gaps between planks
- surfaces worn smooth where feet have passed, rough at the edges
- grim, dirty, muted appearance
- appropriate to 14th-century England

Do not make the timber varnished, glossy, wet, sawn-smooth, painted, or modern. This is
adze-worked oak, not milled lumber.

THE PLANKS ARE LAID IN A RUNNING BOND

Pieces of differing length laid in rough courses, joints staggered from course to course,
as in the second attached image. Not a regular parquet and not a single row of identical
boards.

PLANK PROJECTION

This is critical.

Every plank lies on the same horizontal plane. The projection is ORTHOGRAPHIC.

- planks at the rear must be exactly the same apparent scale as planks at the front
- no perspective shrinkage
- no converging lines
- no wide-angle appearance
- no exaggerated depth

Imagine the scene photographed from extremely far away with an infinitely long lens.

EACH PLANK IS A SOLID OBJECT, not a pattern printed on a flat surface. Every piece shows a
top face and a dark side face where it stands proud of its neighbour, exactly as the second
attached image shows. The camera elevation must be evident from the compressed front-to-back
appearance of every plank, not merely from the outer green ellipse.

THE EDGE

There is NO RIM, CURB OR KERB.

The planked patch simply ends irregularly in packed earth, as the second attached image
ends irregularly.

The perimeter should be naturally ragged:

- plank ends protruding at different lengths, so the outline steps in and out
- a missing or broken board near some margins
- patches of earth showing through at the boundary
- moss encroaching irregularly
- a few loose offcuts near the edge

Overall the patch may loosely follow the ellipse, but DO NOT turn its edge into a clean
geometric ellipse.

OUTPUT

Produce FIVE SEPARATE IMAGES, not a contact sheet.

Each image contains exactly one planked ground patch and one green measurement ellipse.

- transparent background
- no ground outside the planked patch
- no drop shadow
- no contact shadow
- no glow
- no haze
- no scenery
- nothing below the near edge
- crisp non-feathered silhouette
- whole planked patch visible
- whole green ellipse visible
- centred approximately
- long axis exactly horizontal
- nothing standing on the planks

LIGHTING

Soft restrained light from the upper left, matching the first attached image.

Matte timber and earth. No wetness, no dramatic highlights.

FINAL GEOMETRY CHECK BEFORE OUTPUT

Measure the green ellipse: height divided by width.

It must be no more than 0.530. If it is taller than that, the camera is too high. Lower the
camera and redraw the image before outputting it.
