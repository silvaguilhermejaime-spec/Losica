# Run Losica from a phone

## Working translator in Termux

```bash
pkg install python git -y
git clone https://github.com/silvaguilhermejaime-spec/Losica.git
cd Losica
python BUILD_WORKING_LANGUAGE.py --out working-language.json
python USE_WORKING_LANGUAGE.py translate working-language.json "Can you buy bread for me today?"
```

For a download without building, open **Actions → Build working Losica → Run
workflow**, run it, and download `losica-working-language` when it finishes.

## GitHub Actions

1. Open the repository's **Actions** tab.
2. Open **Build Losica**.
3. Tap **Run workflow**.
4. Keep seed `19020` and scale `large`, then run it.
5. When the run finishes, open it and download the `losica-generated-language` artifact.

The artifact contains the generated `language.json`, build report, validation
report, input lock, and architecture documents.

The run also uploads `losica-complete-release`. That artifact contains the
exact 0.29 source bundle, its generated language, and the external-source
catalog. Download it when you need the complete reproducible release.

## Google Colab

Open `Losica_Colab.ipynb` in Colab and choose **Runtime → Run all**. The final
cell downloads the same generated-language ZIP to the phone.

The generator consumes numeric observations and controls. External human-language
expressions remain in separately built adapter files and do not choose Losica's
internal meanings.

## Real recordings

Open **Actions → Build Real-Media Losica → Run workflow**. The workflow fetches
pinned real ESC-10 audio and an OpenCV sample video, generates a language from
their acoustic and optical signals, aligns the upstream category wording afterward, and publishes
`losica-real-media-demo` for download.
