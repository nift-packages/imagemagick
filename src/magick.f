/*
    ImageMagick image processing package for Nift. v0.1.0 backend: the magick
    executable. The package repository is named "imagemagick" but the exported
    module-style value is `magick` (deliberate: package name != exported name).
    Public API: the `magick` struct. Helpers stay private.
*/

fn(magick_available()) { return which("magick") != null }

fn(magick_version_text()) {
    r := run("magick", "--version")
    if(r.exit_code != 0) { return "" }
    return r.stdout.split("\n")[0]
}

fn(magick_guard()) {
    if(!magick_available()) { return {"ok":false,"error":"magick executable not found","width":"","height":"","format":"","depth":"","colorspace":"","exit_code":127} }
    return null
}

fn(magick_run(argv)) {
    guard := magick_guard()
    if(guard != null) { return guard }
    result := run("magick", ...argv)
    if(result.exit_code != 0) { return {"ok":false,"error":result.stderr,"exit_code":result.exit_code} }
    return {"ok":true,"error":"","exit_code":0}
}

fn(magick_resize(input, output, opts)) {
    size := ""
    if(opts != null) {
        if(opts.has("percent")) { size = opts.get("percent").to_string() + "%" }
        else if(opts.has("width") && opts.has("height")) { size = opts.get("width").to_string() + "x" + opts.get("height").to_string() }
        else if(opts.has("width")) { size = opts.get("width").to_string() + "x" }
        else if(opts.has("height")) { size = "x" + opts.get("height").to_string() }
    }
    if(size == "") { return {"ok":false,"error":"resize requires width/height/percent","exit_code":2} }
    return magick_run([input, "-resize", size, output])
}

fn(magick_crop(input, output, opts)) {
    if(opts == null) { return {"ok":false,"error":"crop requires width/height","exit_code":2} }
    w := opts.get("width", 0)
    h := opts.get("height", 0)
    x := opts.get("left", 0)
    y := opts.get("top", 0)
    return magick_run([input, "-crop", w.to_string() + "x" + h.to_string() + "+" + x.to_string() + "+" + y.to_string(), output])
}

fn(magick_rotate(input, output, degrees)) { return magick_run([input, "-rotate", degrees.to_string(), output]) }
fn(magick_convert(input, output)) { return magick_run([input, output]) }

fn(magick_compose(base, overlay, output, opts)) {
    argv := [base, overlay]
    if(opts != null) {
        if(opts.has("gravity")) { argv.push("-gravity"); argv.push(opts.get("gravity")) }
        if(opts.has("geometry")) { argv.push("-geometry"); argv.push(opts.get("geometry")) }
    }
    argv.push("-composite")
    argv.push(output)
    return magick_run(argv)
}

fn(magick_identify(input)) {
    guard := magick_guard()
    if(guard != null) { return guard }
    result := run("magick", "identify", "-format", "%w|%h|%m|%[bit-depth]|%[colorspace]", input)
    if(result.exit_code != 0) { return {"ok":false,"width":"","height":"","format":"","depth":"","colorspace":"","error":result.stderr,"exit_code":result.exit_code} }
    parts := result.stdout.trim().split("|")
    width := ""; height := ""; format := ""; depth := ""; colorspace := ""
    if(parts.size() > 0) { width = parts[0] }
    if(parts.size() > 1) { height = parts[1] }
    if(parts.size() > 2) { format = parts[2] }
    if(parts.size() > 3) { depth = parts[3] }
    if(parts.size() > 4) { colorspace = parts[4] }
    return {"ok":true,"width":width,"height":height,"format":format,"depth":depth,"colorspace":colorspace,"error":"","exit_code":0}
}

@struct(magick_api) {
    available := () => magick_available()
    version := () => magick_version_text()
    resize := (input, output, opts) => magick_resize(input, output, opts)
    crop := (input, output, opts) => magick_crop(input, output, opts)
    rotate := (input, output, degrees) => magick_rotate(input, output, degrees)
    convert := (input, output) => magick_convert(input, output)
    compose := (base, overlay, output, opts) => magick_compose(base, overlay, output, opts)
    identify := (input) => magick_identify(input)
}

magick := magick_api()
export(magick)
