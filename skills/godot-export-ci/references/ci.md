# GitHub Actions for Godot 4.7 (.NET or standard)

Asset names and template folders match the 4.7.2 release. Set `MONO` to `""` for the standard editor or `"_mono"` for .NET.

```yaml
name: build
on: [push, pull_request]

env:
  GODOT_VERSION: "4.7.2"
  MONO: "_mono"                      # "" for the standard (non-.NET) editor
  TEMPLATE_DIR_SUFFIX: ".mono"       # "" for standard

jobs:
  export:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { lfs: true }

      - uses: actions/setup-dotnet@v4          # only for C# projects
        with: { dotnet-version: "8.0.x" }

      - name: Cache Godot + templates
        id: cache
        uses: actions/cache@v4
        with:
          path: |
            ~/godot
            ~/.local/share/godot/export_templates
          key: godot-${{ env.GODOT_VERSION }}${{ env.MONO }}

      - name: Install Godot and export templates
        if: steps.cache.outputs.cache-hit != 'true'
        run: |
          base=https://github.com/godotengine/godot/releases/download/${GODOT_VERSION}-stable
          mkdir -p ~/godot && cd ~/godot
          if [ -n "$MONO" ]; then
            curl -sSL -o g.zip "$base/Godot_v${GODOT_VERSION}-stable_mono_linux_x86_64.zip"
          else
            curl -sSL -o g.zip "$base/Godot_v${GODOT_VERSION}-stable_linux.x86_64.zip"
          fi
          unzip -q g.zip && rm g.zip
          curl -sSL -o t.tpz "$base/Godot_v${GODOT_VERSION}-stable${MONO}_export_templates.tpz"
          dest=~/.local/share/godot/export_templates/${GODOT_VERSION}.stable${TEMPLATE_DIR_SUFFIX}
          mkdir -p "$dest" && unzip -q t.tpz && mv templates/* "$dest/" && rm -rf templates t.tpz

      - name: Locate Godot
        run: echo "GODOT_EXE=$(find ~/godot -type f -name 'Godot_v*' ! -name '*.zip' | head -1)" >> "$GITHUB_ENV"

      - name: Import, check, build
        run: |
          "$GODOT_EXE" --headless --path . --import
          python3 .agents/skills/godot-gdscript/scripts/gd_check.py --no-import
          if ls *.csproj >/dev/null 2>&1; then python3 .agents/skills/godot-csharp/scripts/cs_build.py; fi

      - name: Tests (GdUnit4 / gdUnit4Net if present)
        run: python3 .agents/skills/godot-testing-debug/scripts/test_run.py || [ $? -eq 2 ]   # 2 = no test framework

      - name: Export
        env:
          GODOT_ANDROID_KEYSTORE_RELEASE_PATH: ${{ secrets.ANDROID_KEYSTORE_PATH }}
          GODOT_ANDROID_KEYSTORE_RELEASE_USER: ${{ secrets.ANDROID_KEYSTORE_USER }}
          GODOT_ANDROID_KEYSTORE_RELEASE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
        run: |
          mkdir -p build/linux build/windows
          python3 .agents/skills/godot-export-ci/scripts/export.py "Linux" --out build/linux/game.x86_64
          python3 .agents/skills/godot-export-ci/scripts/export.py "Windows Desktop" --out build/windows/game.exe

      - uses: actions/upload-artifact@v4
        with: { name: builds, path: build/ }
```

Notes
- The skill scripts are referenced from `.agents/skills/` (project-scope install via `install/install.sh --project . --agent agents`). Use plain `godot --export-release` commands if you don't vendor the skills.
- Headless Linux runners can't render, so visual tests need a GPU runner or Xvfb plus `--rendering-driver opengl3`.
- macOS signing and notarization need a macOS runner. iOS needs Xcode on macOS.
- Android: install JDK 17 (`actions/setup-java`) and the Android SDK, then export `JAVA_HOME` and `ANDROID_HOME`. On a fresh runner they become the defaults of the editor settings `export/android/java_sdk_path` and `android_sdk_path` (verified in the 4.7.2 source).
