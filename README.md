# imagemagick

ImageMagick image processing package for Nift.

The package repository is named `imagemagick`, but the exported module-style
value is `magick` — a deliberate demonstration that the package name and the
exported name can differ.

Runtime dependency: the `magick` executable (ImageMagick 7) on `PATH`. The
package drives `magick` through Nift's structured process API (argv, never shell
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
magick.available()                      // bool: magick on PATH and process execution enabled
magick.version()                         // magick --version first line, or "" when unavailable
magick.resize(input, output, opts)       // {width, height} or {percent}
magick.crop(input, output, opts)         // {width, height, left, top}
magick.rotate(input, output, degrees)
magick.convert(input, output)            // format conversion by output extension
magick.compose(base, overlay, output, opts)  // {gravity}, {geometry}
magick.identify(input)                   // {ok, width, height, format, depth, colorspace, error, error_code, exit_code}
```

```text
@import("imagemagick")

print(magick.resize("photo.png", "thumb.png", {"width": 200, "height": 200}).ok)
id := magick.identify("thumb.png")
print(id.width + "x" + id.height + " " + id.format)
print(magick.crop("photo.png", "square.png", {"width": 100, "height": 100, "left": 0, "top": 0}).ok)
print(magick.convert("photo.png", "photo.jpg").ok)
```

`resize` requires an options object with `percent`, or `width` and/or `height`.
`crop` requires `width`/`height` and optional non-negative `left`/`top`. Numeric
options must be positive numbers (except crop `left`/`top`, which may be zero).

## Result shape

Every operation returns `{ok, error, error_code, exit_code}`; `identify`
additionally and always returns `width`, `height`, `format`, `depth` and
`colorspace` (empty strings on failure) so the shape is stable.

`error_code` values:

```text
backend_unavailable   magick is missing or process execution is disabled (exit_code 127)
invalid_input         a path is empty or begins with '-' / '+' / '@'
invalid_options       a numeric or option value is missing/invalid (exit_code 2)
operation_failed      magick exited non-zero; error carries stderr
```

## Argument safety

Every caller-controlled value is an independent argv element. Because ImageMagick
interprets operands beginning with `-`, `+` or `@` as options (or script files),
such paths are rejected with `invalid_input` rather than passed through. This
applies to inputs, outputs, `compose` overlay inputs, and `compose`
gravity/geometry values. ImageMagick 7 does support a `--` operand, but output
operands cannot be disambiguated uniformly, so a single rejection rule is used.

## Availability

`available()` is false when `magick` is missing or Nift runs with
`--no-process` (`NIFT_NO_PROCESS`). Operations then return a recoverable
`backend_unavailable` result without launching the process.

## Limitations (v0.1.0)

- Requires the `magick` executable (ImageMagick 7; the ImageMagick 6 `convert`
  spelling is not used).
- Paths beginning with `-`, `+` or `@` are rejected (see above).

## Tests

```sh
python3 -B tests/test_imagemagick.py /path/to/nift
```

The suite uses a fake `magick` for argv/security boundaries and runs
non-destructive real ImageMagick integration against temporary fixtures when
`magick` is installed (including paths with spaces/Unicode).

Version: 0.1.0
