#!/usr/bin/env python3
"""Deterministic contract/security tests for the imagemagick Nift package.

A fake `magick` executable records exact argv for boundary tests. When the real
`magick` executable is available, non-destructive integration runs against
temporary fixture images under the test work directory.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

NIFT = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/nick/Repositories/nift/nift/nift").resolve()
PACKAGE = Path(__file__).resolve().parent.parent
TESTS = PACKAGE / "tests"
SOURCE = PACKAGE / "src" / "magick.f"

manifest = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
if manifest != {"name": "imagemagick", "version": "0.1.0", "entry": "src/magick.f", "description": "ImageMagick image processing package"}:
    raise SystemExit(f"FAIL unexpected package manifest: {manifest!r}")

source = SOURCE.read_text(encoding="utf-8")
exports = re.findall(r"^export\(([^)]+)\)$", source, re.MULTILINE)
public_methods = re.findall(r"^    fn\(([A-Za-z_][A-Za-z0-9_]*)\(", source, re.MULTILINE)
expected_public = ["available", "version", "resize", "crop", "rotate", "convert", "compose", "identify"]
if exports != ["magick"] or public_methods != expected_public:
    raise SystemExit(f"FAIL unexpected public surface: exports={exports!r} methods={public_methods!r}")

FAKE = r"""#!/usr/bin/env bash
n=0
if [ -f "${MAGICK_CAPTURE}.count" ]; then n=$(cat "${MAGICK_CAPTURE}.count"); fi
dir="${MAGICK_CAPTURE}.call${n}"
mkdir -p "$dir"
i=0
for a in "$@"; do printf '%s' "$a" > "$dir/$i"; i=$((i+1)); done
echo $((n+1)) > "${MAGICK_CAPTURE}.count"
for a in "$@"; do
  if [ "$a" = "--version" ]; then echo "Version: ImageMagick 7.1.2-18 (fake)"; exit 0; fi
done
for a in "$@"; do
  if [ "$a" = "identify" ]; then printf '10|20|PNG|8|sRGB'; exit 0; fi
done
exit 0
"""


def require(condition, message, result=None):
    if condition:
        return
    if result is not None:
        message += f"\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}\nreturn code: {result.returncode}"
    raise SystemExit("FAIL " + message)


def run(args, cwd, env):
    return subprocess.run([str(NIFT), *args], cwd=cwd, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60, check=False, env=env)


def base_env(bin_dir, capture):
    env = dict(os.environ)
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin"
    env["MAGICK_CAPTURE"] = str(capture)
    env.pop("NIFT_NO_PROCESS", None)
    return env


def clear_capture(capture):
    for path in Path(capture).parent.glob(Path(capture).name + "*"):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)


def calls(capture):
    parsed = []
    index = 0
    while True:
        directory = Path(f"{capture}.call{index}")
        if not directory.is_dir():
            break
        args = []
        i = 0
        while (directory / str(i)).exists():
            args.append((directory / str(i)).read_text(encoding="utf-8"))
            i += 1
        parsed.append(args)
        index += 1
    return parsed


def nift_string(text):
    if text == "":
        return '""'
    return "bytes([" + ",".join(str(b) for b in text.encode("utf-8")) + ']).decode("utf-8")'


WORK = Path(tempfile.mkdtemp(prefix=".imagemagick-tests-", dir=TESTS))
try:
    fake_bin = WORK / "bin"
    fake_bin.mkdir()
    fake = fake_bin / "magick"
    fake.write_text(FAKE, encoding="utf-8")
    fake.chmod(0o755)

    consumer = WORK / "consumer"
    consumer.mkdir()
    (consumer / ".nift").mkdir()
    added = run(["add", str(PACKAGE)], consumer, base_env(fake_bin, WORK / "add.txt"))
    require(added.returncode == 0, "nift add into fresh consumer failed", added)

    def run_script(name, body, env=None, capture="cap.txt"):
        capfile = WORK / capture
        clear_capture(capfile)
        (consumer / name).write_text(body, encoding="utf-8")
        return run([name], consumer, env or base_env(fake_bin, capfile))

    # 1. Structured argv for adversarial file names: each stays one element.
    hostile = "in; $(touch " + str(WORK / "pwned") + ") `id` & | \n ' \" é😀.png"
    output = "out; $(touch " + str(WORK / "pwned2") + ").png"
    cap = WORK / "argv.txt"
    body = ('@import("imagemagick")\n'
            'print(magick.resize(' + nift_string(hostile) + ', ' + nift_string(output) + ', {"width":10}).ok.to_string())\n')
    res = run_script("argv.f", body, capture="argv.txt")
    require(res.returncode == 0 and res.stdout.strip() == "true", "hostile resize failed", res)
    argv = calls(cap)[0]
    require(argv == [hostile, "-resize", "10x", output], f"hostile argv not structural: {argv!r}")
    require(not (WORK / "pwned").exists() and not (WORK / "pwned2").exists(), "filename caused shell side effect")

    # 2. Leading-dash paths are rejected before process execution.
    cap = WORK / "dash.txt"
    dash_cases = [
        ("resize", "magick.resize(\"-file.png\", \"out.png\", {\"width\":10})"),
        ("resize-out", "magick.resize(\"in.png\", \"-out.png\", {\"width\":10})"),
        ("convert", "magick.convert(\"--help\", \"out.png\")"),
        ("convert-out", "magick.convert(\"in.png\", \"-version\")"),
        ("crop", "magick.crop(\"+profile\", \"out.png\", {\"width\":5,\"height\":5})"),
        ("rotate", "magick.rotate(\"@something\", \"out.png\", 90)"),
        ("compose", "magick.compose(\"in.png\", \"-over.png\", \"out.png\", null)"),
        ("identify", "magick.identify(\"-file.png\")"),
    ]
    for index, (name, call) in enumerate(dash_cases):
        res = run_script(f"dash{index}.f",
                         '@import("imagemagick")\nprint(' + call + '.error_code)\n',
                         capture="dash.txt")
        require(res.returncode == 0 and res.stdout.strip() == "invalid_input",
                f"leading-dash case {name} not rejected: {res.stdout!r} {res.stderr!r}")
    require(calls(WORK / "dash.txt") == [], "leading-dash rejection still launched the executable")

    # 3. Invalid option types/values are structured rejections.
    bad_options = [
        'magick.resize("in.png", "out.png", null)',
        'magick.resize("in.png", "out.png", {"percent":-1})',
        'magick.resize("in.png", "out.png", {"width":"10"})',
        'magick.resize("in.png", "out.png", {"width":0})',
        'magick.resize("in.png", "out.png", {})',
        'magick.crop("in.png", "out.png", {"width":0,"height":5})',
        'magick.crop("in.png", "out.png", {"width":5,"height":5,"left":-1})',
        'magick.rotate("in.png", "out.png", "90")',
        'magick.compose("a.png", "b.png", "c.png", {"gravity":"-center"})',
    ]
    for index, call in enumerate(bad_options):
        res = run_script(f"bad{index}.f", '@import("imagemagick")\nprint(' + call + '.error_code)\n', capture="badopt.txt")
        require(res.returncode == 0 and res.stdout.strip() in ("invalid_options", "invalid_input"),
                f"bad option case {index} not rejected: {res.stdout!r} {res.stderr!r}")

    # 4. Missing executable and --no-process fail closed without launching.
    empty_bin = WORK / "emptybin"
    empty_bin.mkdir()
    missing_env = dict(os.environ)
    missing_env["PATH"] = str(empty_bin)
    missing_env["MAGICK_CAPTURE"] = str(WORK / "missing.txt")
    missing_env.pop("NIFT_NO_PROCESS", None)
    probe = """@import("imagemagick")
print(magick.available().to_string())
print(magick.version() == "")
r := magick.resize("in.png", "out.png", {"width":10})
print(r.ok.to_string() + ":" + r.error_code + ":" + r.exit_code.to_string())
print(magick.identify("in.png").error_code)
"""
    res = run_script("missing.f", probe, env=missing_env, capture="missing.txt")
    require(res.returncode == 0 and res.stdout.strip().splitlines() == ["false", "true", "false:backend_unavailable:127", "backend_unavailable"],
            f"missing executable behavior wrong: {res.stdout!r} {res.stderr!r}")

    noproc = base_env(fake_bin, WORK / "noproc.txt")
    noproc["NIFT_NO_PROCESS"] = "1"
    clear_capture(WORK / "noproc.txt")
    res = run_script("noproc.f", probe, env=noproc, capture="noproc.txt")
    require(res.returncode == 0 and res.stdout.strip().splitlines() == ["false", "true", "false:backend_unavailable:127", "backend_unavailable"],
            f"--no-process behavior wrong: {res.stdout!r} {res.stderr!r}")
    require(calls(WORK / "noproc.txt") == [], "--no-process still launched the executable")

    # 5. identify uses the documented format and returns the exact shape.
    cap = WORK / "identify.txt"
    body = ('@import("imagemagick")\n'
            'id := magick.identify("in.png")\n'
            'print("shape=" + type(id).to_string() + " ok=" + id.ok.to_string())\n'
            'print(id.width + "|" + id.height + "|" + id.format + "|" + id.depth + "|" + id.colorspace)\n'
            'print("keys=" + (id.has("width").to_string() + id.has("error_code").to_string()))\n')
    res = run_script("identify.f", body, capture="identify.txt")
    require(res.returncode == 0 and "shape=object ok=true" in res.stdout and "10|20|PNG|8|sRGB" in res.stdout and "keys=truetrue" in res.stdout,
            f"identify shape wrong: {res.stdout!r} {res.stderr!r}")
    ident_argv = calls(cap)[0]
    require(ident_argv == ["identify", "-format", "%w|%h|%m|%[bit-depth]|%[colorspace]", "in.png"],
            f"identify argv wrong: {ident_argv!r}")

    # 6. Determinism.
    body = '@import("imagemagick")\nmagick.resize("in.png", "out.png", {"width":10,"height":5})\n'
    (consumer / "det.f").write_text(body, encoding="utf-8")
    a, b = WORK / "det_a.txt", WORK / "det_b.txt"
    for capfile in (a, b):
        clear_capture(capfile)
        r = run(["det.f"], consumer, base_env(fake_bin, capfile))
        require(r.returncode == 0, "determinism run failed", r)
    require(calls(a) == calls(b), "argv not deterministic")

    # 7. Privacy: only magick is exported and helpers are inaccessible.
    for helper in ["process_available", "is_number", "safe_path", "safe_option", "failure", "guard", "run_command", "identify_failure"]:
        (consumer / "privacy.f").write_text(f'@import("imagemagick")\nmagick.{helper}("x")\n', encoding="utf-8")
        res = run(["privacy.f"], consumer, base_env(fake_bin, WORK / "privacy.txt"))
        require(res.returncode != 0, f"private helper {helper} was accessible")

    # 8. Real ImageMagick integration (non-destructive, isolated fixtures).
    real = shutil.which("magick")
    if real:
        real_bin = WORK / "realbin"
        real_bin.mkdir()
        os.symlink(real, real_bin / "magick")
        real_env = dict(os.environ)
        real_env["PATH"] = f"{real_bin}:/usr/bin:/bin"
        real_env.pop("NIFT_NO_PROCESS", None)
        fixture = consumer / "fixture space é.png"
        made = subprocess.run([real, "-size", "24x12", "xc:red", str(fixture)], capture_output=True, text=True)
        require(made.returncode == 0, "could not create fixture", made)
        real_script = """@import("imagemagick")
print(magick.resize("fixture space é.png", "resized space é.png", {"width":12}).ok)
id := magick.identify("resized space é.png")
print(id.ok.to_string() + " " + id.width + "x" + id.height)
print(magick.crop("fixture space é.png", "crop.png", {"width":6,"height":6}).ok)
print(magick.rotate("fixture space é.png", "rot.png", 90).ok)
print(magick.convert("fixture space é.png", "conv.jpg").ok)
print(magick.compose("fixture space é.png", "crop.png", "comp.png", {"gravity":"center"}).ok)
"""
        res = run_script("real.f", real_script, env=real_env, capture="real.txt")
        require(res.returncode == 0, "real integration script failed", res)
        require(res.stdout.strip().splitlines() == ["true", "true 12x6", "true", "true", "true", "true"],
                f"real integration results wrong: {res.stdout!r} {res.stderr!r}")
        require((consumer / "resized space é.png").exists() and (consumer / "comp.png").exists(),
                "real integration outputs missing")
    else:
        print("SKIP real ImageMagick integration (magick unavailable)")

finally:
    shutil.rmtree(WORK, ignore_errors=True)

print("PASS imagemagick package tests")
