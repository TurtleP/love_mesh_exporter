# LÖVE Mesh Binary Exporter for Blender

This Blender addon allows you to export mesh objects as flat binary files compatible with LÖVE's Mesh API.
It supports optional vertex colors and UV coordinates, as well as customizable export axes.

## Installation

1. Download the addon .py file.
2. Open Blender → Edit → Preferences → Add-ons → Install...
3. Select the .py file and enable the addon.

## Usage

1. Select a mesh object in your scene.
2. Go to File → Export → MSH.
3. In the export panel (right-hand sidebar):
    - Forward / Up: Choose the axes to map Blender’s coordinates to LÖVE.
    - Flip UV U / V: Optionally flip UV coordinates to match your texture orientation.
4. Enter a file path and click Export.

## Vertex Format

The exported mesh uses the following format per vertex:

| Component | Type | Size |
|-----------|------|-------|
| Position  (x,y,z)  | float | 12 bytes |
| UV (u,v)           | float | 8 bytes  |
| Color (r, g, b, a) |float	 | 16 bytes |

If UVs or colors are missing, defaults are used ([0,0] for UVs, [1,1,1,1] for color)

## Notes
- Vertex Colors: Use Blender’s Vertex Paint mode to assign colors.
