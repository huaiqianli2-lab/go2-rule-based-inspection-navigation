# Indoor and outdoor LiDAR maps

| Scene | Binary XYZ PCD | Points | Route and observation poses | Stops |
| --- | --- | ---: | --- | ---: |
| Indoor | [indoor.pcd](indoor.pcd?raw=1) | 246,739 | [indoor-route.json](indoor-route.json) | 22 + return |
| Outdoor | [outdoor.pcd](outdoor.pcd?raw=1) | 1,385,388 | [outdoor-route.json](outdoor-route.json) | 8 + return |

These are geometry exports from the same frozen localization maps and original plans used in the [physical simulation](../docs/physics-patrol.md). Each scene uses its own mission start as the local origin. All finite XYZ points are retained. The export translates the coordinates without changing the axes. Units are metres and yaw is in degrees about +Z. Route coordinates are rounded to 10 µm.

PCDs contain XYZ float32 fields. The JSON includes the planned XY path and the ordered observation poses, including the return. Its pose identifiers are ordinal. The dataset scope is mapped geometry and planned routes. It excludes raw sensor logs, imagery, timestamps, site metadata, and robot configuration.

[File and source SHA-256 checksums](manifest.json) · [Rights and attribution](../LICENSE)

## Verify downloaded files

Download `indoor.pcd`, `indoor-route.json`, `outdoor.pcd`,
`outdoor-route.json`, and `manifest.json` from the same repository revision.
Use the raw/download links to save the file contents, rather than the GitHub
HTML preview, and keep all five files together. Do not reformat the JSON files
before checking: SHA-256 hashes the exact downloaded bytes.

From the repository root, calculate the four data-file hashes:

```sh
cd datasets
sha256sum indoor.pcd indoor-route.json outdoor.pcd outdoor-route.json
```

On macOS, use `shasum -a 256` in place of `sha256sum`. For each filename,
compare the printed 64-character hash with its value in the corresponding
scene's `files` object in [manifest.json](manifest.json). The
`input_cloud_sha256` and `input_plan_sha256` values describe the original source
inputs, so use the `files` values for these downloaded exports.

Alternatively, run this Python 3 check from the same directory containing the
five downloaded files. It calculates each hash and compares it automatically:

```sh
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

manifest = json.loads(Path("manifest.json").read_text(encoding="utf-8"))
failed = False
for scene in manifest:
    for filename, expected in scene["files"].items():
        path = Path(filename)
        if not path.is_file():
            print(f"{filename}: MISSING")
            failed = True
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        matches = actual == expected
        print(f"{filename}: {'OK' if matches else 'FAILED'}")
        failed |= not matches
raise SystemExit(1 if failed else 0)
PY
```

All four files must report `OK`; the check exits with a nonzero status if a
file is missing or a hash differs. Re-download any failing file and confirm
that it and the manifest come from the same revision before using the data.
