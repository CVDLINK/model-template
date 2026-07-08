# Publishing this project

This repo was created from the CVDLINK **repo-template**. To publish it to
Zenodo → OpenAIRE → EOSC (and, if it's an AI model, register it in AIMe), follow the full guide:

➡ **[cvdlink/ai-model-publishing → docs/instructions.md](https://github.com/cvdlink/ai-model-publishing/blob/main/docs/instructions.md)**

## Checklist

- [ ] Fill in `README.md`.
- [ ] Update `CHANGELOG.md` for the release.
- [ ] Confirm the `LICENSE` (default MIT — change if needed; don't hand-write license text).
- [ ] Edit `.zenodo.json` (title, description, creators, keywords) — keep `communities: cvdlink`.
- [ ] Make the repo **public** and confirm no sensitive content (data, credentials, internal URLs).
- [ ] Cut a versioned GitHub **release** (this is the distributable snapshot).
- [ ] Link the repo to **Zenodo** once → each future release is then archived with a DOI automatically.

### If this project is an AI model, also:

- [ ] Only if the model isn't already in the **AI model store**: describe it in a single-source input file (it feeds both the AI Card and the AIMe record). If it's already in the store, the description is retrieved from there — nothing to re-enter.
- [ ] Generate the **AI Card** and upload it to the model's **Zenodo record** — no need to duplicate it into this repo.
- [ ] Generate and submit the **AIMe registry record**; add the registry link to `README.md`.

## Notes

- This template uses **`.zenodo.json`** for citation/metadata — it's the file Zenodo reads,
  and the only one that can carry the `cvdlink` community and EU grant info.
- Optional: add a `CITATION.cff` too if you want GitHub's "Cite this repository" button.
  Zenodo ignores it when `.zenodo.json` is present, so it's purely for the GitHub UI.
- The `contributors` block is **optional** — fill it in for people who aren't authors (e.g. data curator, supervisor), or **delete the whole block** if there are none. Each contributor needs a `type` (e.g. `ProjectMember`, `DataCurator`, `Supervisor`).
- `.zenodo.json` `"upload_type"` defaults to `software` (models, tools, code). Change it for other outputs: `dataset` for data, or `publication` for documentation/deliverables. Full list: `publication`, `poster`, `presentation`, `dataset`, `image`, `video`, `software`, `lesson`, `physicalobject`, `other`.
  - `publication` also needs a `"publication_type"` (e.g. `report`, `deliverable`, `softwaredocumentation`, `article`); `image` needs an `"image_type"` (e.g. `figure`, `diagram`).
- The `grants` entry is pre-filled with CVDLINK's Horizon Europe grant (`101137278`) — leave it as-is so the record links to the project in OpenAIRE/EOSC.
- If you change the `LICENSE`, update the `.zenodo.json` `"license"` id to match (Zenodo uses lowercase ids, e.g. `"mit"`, `"apache-2.0"`, `"cc-by-4.0"`).
