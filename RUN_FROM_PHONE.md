# Run Losica from a phone

## GitHub Actions

1. Open the repository's **Actions** tab.
2. Open **Build Losica**.
3. Tap **Run workflow**.
4. Keep seed `19020` and scale `large`, then run it.
5. When the run finishes, open it and download the `losica-generated-language` artifact.

The artifact contains the generated `language.json`, build report, validation
report, input lock, and architecture documents.

## Google Colab

Open `Losica_Colab.ipynb` in Colab and choose **Runtime → Run all**. The final
cell downloads the same generated-language ZIP to the phone.

The generator consumes numeric observations and controls. External human-language
expressions remain in separately built adapter files and do not choose Losica's
internal meanings.
