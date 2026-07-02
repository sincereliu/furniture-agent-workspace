# Coordinate System

Use one shared furniture coordinate system:

- origin: lower-left-rear ground corner of the finished furniture envelope;
- X: left to right;
- Y: rear toward the user-facing front;
- Z: floor upward;
- units: millimeters unless an input explicitly states otherwise.

Positions describe a part's minimum corner. Compute centers only inside CAD
primitives that require center-based placement.

For a table, back legs therefore have smaller Y values and front legs have
larger Y values. For a cabinet, a recessed back panel has a smaller Y value than
shelves and doors, while doors lie at or near the largest Y extent.
