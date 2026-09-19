# imagemagick

ImageMagick image processing package for Nift.

The package repository is named `imagemagick`, but the exported module-style
value is `magick` — a deliberate demonstration that the package name and the
exported name can differ.

Runtime dependency: the `magick` executable on `PATH`. The package drives
`magick` through Nift's structured process API (argv, never shell
concatenation). The v0.1.0 backend may change later without requiring consumers
to rewrite around it.

## Installation

```text
nift add nift-packages/imagemagick
```

## Import

```text
@import("imagemagick")
```

## API

The exported `magick` struct:

```text
magick.available()                      // bool: magick on PATH
magick.version()                        // magick --version first line
magick.resize(input, output, opts)      // {width, height} or {percent}
magick.crop(input, output, opts)        // {width, height, left, top}
magick.rotate(input, output, degrees)
magick.convert(input, output)           // format conversion by output extension
magick.compose(base, overlay, output, opts)  // {gravity}, {geometry}
magick.identify(input)                  // {ok, width, height, format, depth, colorspace, error, exit_code}
```

```text
@import("imagemagick")

print(magick.resize("photo.png", "thumb.png", {"width": 200, "height": 200}).ok)
id := magick.identify("thumb.png")
print(id.width + "x" + id.height + " " + id.format)
print(magick.crop("photo.png", "square.png", {"width": 100, "height": 100, "left": 0, "top": 0}).ok)
print(magick.convert("photo.png", "photo.jpg").ok)
```

`identify` runs `magick identify -format "%w|%h|%m|%[bit-depth]|%[colorspace]"`
and parses the pipe-separated fields.

## Result shape

All operations return `{ok, error, exit_code}`; `identify` additionally returns
`width`, `height`, `format`, `depth` and `colorspace`. `exit_code` is `127`
when `magick` is missing.

## Limitations (v0.1.0)

- Requires the `magick` executable (ImageMagick 7; the ImageMagick 6 `convert`
  spelling is not used).
- `resize` needs `width`/`height`/`percent` in the options object.

Version: 0.1.0