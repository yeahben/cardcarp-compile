"""Convert a folder of card scans to AVIF, with a thumbnail cut of each.

    cardcarp-image image/wow/card                 # in place, sources kept
    cardcarp-image image/wow/card --limit 50      # calibrate first
    cardcarp-image image/wow/card --sweep         # delete each source once both AVIFs exist
    cardcarp-image image/wow/card --out dist/img  # write the tree elsewhere

Every PNG or JPEG under the folder becomes two files at the same stem:

    set/01-azeroth/01-heroes-of-azeroth/185-galway-steamwhistle.png
    set/01-azeroth/01-heroes-of-azeroth/185-galway-steamwhistle.avif          the scan
    set/01-azeroth/01-heroes-of-azeroth/185-galway-steamwhistle-thumb.avif    the cut

The cut is what the deckbox grid and table rows show: an app names it in its
config as card.thumbnail ('thumb'), and @cardcarp/core builds the URL as
{dir}-{thumbnail}.avif. The scan is for the card dialog and the table.

Resumable: a stem whose outputs exist is skipped, so an interrupted run picks up
where it stopped, and a tree converted before thumbnails existed only needs the
thumbnails added. An AVIF with no PNG or JPEG beside it is read as the scan
itself, so an AVIF-only archive gets its thumbnails too.

Needs avifenc (brew install libavif) and, for thumbnails, Pillow.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

CONVERTIBLE = ('.png', '.jpg', '.jpeg')
KEPT = '.avif'

DEFAULT_WORKERS = 8
DEFAULT_THUMB_SUFFIX = 'thumb'
# A 480px cut: a grid cell is around 240 CSS pixels wide, and screens are 2x.
DEFAULT_THUMB_WIDTH = 480

# A partial file must never be mistaken for a finished encode
PART_SUFFIX = '.part'
# Anything smaller is a truncated encode, not an image
MIN_BYTES = 1024

# AVIF is served into a grid of hundreds of cards, so bytes are the binding
# constraint and quality floats to fit. A fixed quality does not work: what
# drives the bitrate on these scans is film grain and holo-foil speckle, not
# hue or card size. Measured across 20 MTG cards, a flat q60 ranged 63KB-165KB
# and only ~40% landed under 100KB. Pinning the quality low enough for the
# worst card (~q45) needlessly wrecks the clean ones that reach the cap at q70,
# so each image instead searches this ladder for the best rung that fits.
# Typical cards settle at 65-70, grainy holos at 45-55.
QUALITY_LADDER = (40, 45, 50, 55, 60, 65, 70)
DEFAULT_MAX_BYTES = 100 * 1024
# A 480px cut of a 745px scan at q60 is ~50KB; the grid loads hundreds at once.
DEFAULT_THUMB_MAX_BYTES = 50 * 1024

# Encoder speed. Encoding dominates the runtime, and the ladder multiplies it,
# so this is the single biggest lever on how long a full run takes. Measured on
# MTG scans: -s 4 is 1.71s/encode, -s 6 is 0.33s/encode for the same byte count
# and -0.35dB, -s 8 is 0.11s/encode but -0.85dB. 6 is the knee.
AVIF_SPEED = 6


def plausible(path):
    return os.path.exists(path) and os.path.getsize(path) >= MIN_BYTES


def sources(root, thumb_suffix):
    """[(source, stem)] for every image under root, stem relative to root.

    A PNG or JPEG is a source. An AVIF is a source only where no PNG or JPEG
    shares its stem (then it is the scan and can only yield a thumbnail), and
    is never one where it is itself a thumbnail of another file here.
    """
    by_stem = {}

    for directory, _, filenames in os.walk(root):
        for filename in filenames:
            stem, extension = os.path.splitext(filename)
            extension = extension.lower()
            if extension not in CONVERTIBLE and extension != KEPT:
                continue
            relative = os.path.relpath(os.path.join(directory, stem), root)
            by_stem.setdefault(relative, {})[extension] = os.path.join(directory, filename)

    found = []
    for stem in sorted(by_stem):
        files = by_stem[stem]
        raster = [files[ext] for ext in CONVERTIBLE if ext in files]
        if raster:
            found.append((raster[0], stem))
            continue
        # Only an AVIF here. Skip it if it is the thumbnail of a stem we hold.
        marker = f'-{thumb_suffix}'
        if stem.endswith(marker) and stem[:-len(marker)] in by_stem:
            continue
        found.append((files[KEPT], stem))

    return found


def run(command, temporary):
    """Encode into a .part sidecar. The caller decides whether to keep it."""
    try:
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as err:
        if os.path.exists(temporary):
            os.remove(temporary)
        detail = err.stderr.decode('utf-8', 'replace').strip().splitlines()
        raise RuntimeError(detail[-1] if detail else f'exit {err.returncode}')

    return os.path.getsize(temporary)


def encode(source, path, max_bytes):
    """Find the best ladder rung that fits the cap. Returns (quality, size)."""
    # avifenc always writes AVIF regardless of the output extension, so the
    # .part sidecar needs no format hint.
    temporary = path + PART_SUFFIX

    def attempt(quality):
        return run(['avifenc', '-q', str(quality), '-s', str(AVIF_SPEED),
                    '-j', '1', source, temporary], temporary)

    # Size rises monotonically with quality, so the ladder can be bisected
    # rather than walked: ~3 encodes per image instead of up to 7. Every rung
    # that fits is better than the last one that fit, so promoting on each fit
    # leaves the winner in place without a confirming re-encode.
    low, high = 0, len(QUALITY_LADDER) - 1
    best = None

    while low <= high:
        middle = (low + high) // 2
        size = attempt(QUALITY_LADDER[middle])

        if size <= max_bytes:
            best = (QUALITY_LADDER[middle], size)
            os.replace(temporary, path)
            low = middle + 1
        elif middle == 0 and best is None:
            # The floor of the ladder still overshoots. Nothing smaller is
            # available without visible damage, so keep this encode rather than
            # discarding it and paying for the identical one again.
            best = (QUALITY_LADDER[0], size)
            os.replace(temporary, path)
            high = middle - 1
        else:
            os.remove(temporary)
            high = middle - 1

    return best


def cut(source, path, width, max_bytes):
    """Resize the source to the thumbnail width and encode it. (quality, size)."""
    from PIL import Image

    # The cut goes through a PNG sidecar so avifenc, the one encoder here,
    # produces both files: the same quality scale, and the same color handling.
    sidecar = path + PART_SUFFIX + '.png'
    try:
        with Image.open(source) as image:
            image.load()
            if image.width > width:
                image.thumbnail((width, width * 64), Image.Resampling.LANCZOS)
            image.save(sidecar, 'PNG')
        return encode(sidecar, path, max_bytes)
    finally:
        if os.path.exists(sidecar):
            os.remove(sidecar)


def convert(source, stem, out_root, options):
    """('skipped', {}) or ('ok', {'scan': (q, size), 'thumb': (q, size)})."""
    scan = os.path.join(out_root, stem + KEPT)
    thumb = os.path.join(out_root, f'{stem}-{options.thumb_suffix}{KEPT}')

    is_avif = source.lower().endswith(KEPT)
    want_scan = not is_avif and (options.force or not plausible(scan))
    want_thumb = not options.no_thumb and (options.force or not plausible(thumb))

    if not want_scan and not want_thumb:
        return 'skipped', {}

    os.makedirs(os.path.dirname(scan), exist_ok=True)
    result = {}
    if want_scan:
        result['scan'] = encode(source, scan, options.max_bytes)
    if want_thumb:
        result['thumb'] = cut(source, thumb, options.thumb_width, options.thumb_max_bytes)
    return 'ok', result


def sweep(targets, out_root, options):
    """Delete every PNG/JPEG whose outputs are present. Returns (removed, stranded).

    A source is only removed once its scan and, unless thumbnails are off, its
    thumbnail exist at a plausible size. Deleting one whose conversion failed
    would serve no purpose and cost a re-fetch, so those are reported and kept.
    """
    removed, stranded = 0, []

    for source, stem in targets:
        if source.lower().endswith(KEPT) or not os.path.exists(source):
            continue
        outputs = [os.path.join(out_root, stem + KEPT)]
        if not options.no_thumb:
            outputs.append(os.path.join(out_root, f'{stem}-{options.thumb_suffix}{KEPT}'))
        if all(plausible(path) for path in outputs):
            os.remove(source)
            removed += 1
        else:
            stranded.append(source)

    return removed, stranded


def spread(qualities):
    return '  '.join(f'q{q}: {qualities[q]}' for q in sorted(qualities, reverse=True))


def kb(value):
    return f'{value / 1024:.0f}KB'


def main():
    parser = argparse.ArgumentParser(
        description="Convert a folder of card scans to AVIF, with a thumbnail cut of each.")
    parser.add_argument('source', help="folder of PNG/JPEG scans (searched recursively)")
    parser.add_argument('--out', help="write the AVIF tree here instead of beside the sources")
    parser.add_argument('--workers', type=int, default=DEFAULT_WORKERS)
    parser.add_argument('--max-bytes', type=int, default=DEFAULT_MAX_BYTES,
                        help=f"size cap the scan's quality ladder targets ({kb(DEFAULT_MAX_BYTES)})")
    parser.add_argument('--thumb-width', type=int, default=DEFAULT_THUMB_WIDTH,
                        help=f"thumbnail width in pixels ({DEFAULT_THUMB_WIDTH}); never upscales")
    parser.add_argument('--thumb-max-bytes', type=int, default=DEFAULT_THUMB_MAX_BYTES,
                        help=f"size cap the thumbnail's ladder targets ({kb(DEFAULT_THUMB_MAX_BYTES)})")
    parser.add_argument('--thumb-suffix', default=DEFAULT_THUMB_SUFFIX,
                        help=f"the variant name, as the app's card.thumbnail ({DEFAULT_THUMB_SUFFIX})")
    parser.add_argument('--no-thumb', action='store_true', help="scans only, no thumbnails")
    parser.add_argument('--force', action='store_true',
                        help="re-encode even where the outputs already exist")
    parser.add_argument('--sweep', action='store_true',
                        help="delete each PNG/JPEG once its outputs exist")
    parser.add_argument('--limit', type=int, help="stop after this many (for calibrating)")
    options = parser.parse_args()

    if not os.path.isdir(options.source):
        sys.exit(f"Error: {options.source} is not a folder.")
    if not shutil.which('avifenc'):
        sys.exit("Error: avifenc not found. Install libavif (brew install libavif).")
    if not options.no_thumb:
        try:
            import PIL  # noqa: F401 - only probing that it is installed
        except ImportError:
            sys.exit("Error: thumbnails need Pillow (pip install pillow), "
                     "or pass --no-thumb.")

    out_root = options.out or options.source

    targets = sources(options.source, options.thumb_suffix)
    if options.limit:
        targets = targets[:options.limit]

    if not targets:
        print(f"Nothing to convert: {options.source} holds no "
              f"{'/'.join(e.lstrip('.') for e in CONVERTIBLE + (KEPT,))} files.")
        return

    thumb_note = ('no thumbnails' if options.no_thumb else
                  f"thumbnails {options.thumb_width}px cap {kb(options.thumb_max_bytes)}")
    print(f"{len(targets)} images, scan cap {kb(options.max_bytes)}, {thumb_note}, "
          f"{options.workers} workers")

    counts = {'ok': 0, 'skipped': 0}
    qualities = {'scan': {}, 'thumb': {}}
    produced = {'scan': 0, 'thumb': 0}
    bytes_out = {'scan': 0, 'thumb': 0}
    over_cap = {'scan': [], 'thumb': []}
    failures = []
    started = time.time()

    with ThreadPoolExecutor(max_workers=options.workers) as pool:
        futures = {
            pool.submit(convert, source, stem, out_root, options): (source, stem)
            for source, stem in targets
        }

        for done, future in enumerate(as_completed(futures), start=1):
            source, stem = futures[future]
            try:
                status, result = future.result()
            except Exception as err:  # noqa: BLE001 - one bad file must not stop the run
                failures.append((source, f'{type(err).__name__}: {err}'))
            else:
                counts[status] += 1
                for kind, (quality, size) in result.items():
                    produced[kind] += 1
                    bytes_out[kind] += size
                    qualities[kind][quality] = qualities[kind].get(quality, 0) + 1
                    cap = options.max_bytes if kind == 'scan' else options.thumb_max_bytes
                    if size > cap:
                        over_cap[kind].append((stem, size))

            if done % 500 == 0 or done == len(targets):
                elapsed = time.time() - started
                rate = done / elapsed if elapsed else 0
                remaining = (len(targets) - done) / rate if rate else 0
                # Flushed so a redirected log stays watchable across a long run
                print(f"  {done}/{len(targets)}  "
                      f"converted {counts['ok']}  skipped {counts['skipped']}  "
                      f"failed {len(failures)}  "
                      f"{rate:.1f}/s  ~{remaining / 60:.0f}m left", flush=True)

    print(f"Converted {counts['ok']}, skipped {counts['skipped']}, failed {len(failures)}")

    for kind, label in (('scan', 'Scans'), ('thumb', 'Thumbnails')):
        if not produced[kind]:
            continue
        average = bytes_out[kind] / produced[kind]
        print(f"{label}: {produced[kind]} written, {kb(average)} average, "
              f"quality {spread(qualities[kind])}")
        if over_cap[kind]:
            # These overshot at the ladder's floor, not its ceiling: the cap is
            # simply unreachable for them without visible damage.
            print(f"  over cap even at q{QUALITY_LADDER[0]} ({len(over_cap[kind])}):")
            for stem, size in sorted(over_cap[kind], key=lambda item: -item[1])[:10]:
                print(f"  - {stem}: {kb(size)}")
            if len(over_cap[kind]) > 10:
                print(f"  ... and {len(over_cap[kind]) - 10} more")

    if failures:
        print("Failures (re-run to retry, finished files are skipped):")
        for path, reason in failures[:15]:
            print(f"  - {path}: {reason}")
        if len(failures) > 15:
            print(f"  ... and {len(failures) - 15} more")

    if options.sweep:
        removed, stranded = sweep(targets, out_root, options)
        print(f"Removed {removed} source file(s).")
        if stranded:
            print(f"Kept {len(stranded)} whose outputs are missing or too small:")
            for path in stranded[:10]:
                print(f"  - {path}")
    else:
        print("Sources kept. Pass --sweep to delete them once converted.")

    if failures:
        sys.exit(1)


if __name__ == '__main__':
    main()
