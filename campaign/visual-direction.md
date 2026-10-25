# CallStencil campaign visual direction

Five beats share warm ivory, deep navy and teal, with coral used sparingly for refused examples. The conceptual pair uses dimensional cut-paper stencil/card imagery. The later three assets show actual software output or data from the controlled run. Keep type large enough for a social feed; use generous whitespace and restrained engineering publication styling.

1. **Problem — `connection-is-not-permission.png`:** Original AI-generated conceptual illustration. Exact visible text: “CallStencil” and “Connection is not permission.” Matching and mismatching cards illustrate an explicit aperture. The period is a harmless addition to the requested wording.
2. **Design — `test-the-boundary.png`:** Original AI-generated conceptual illustration. Exact visible text: “CallStencil” and “Test the boundary”. A workbench, stencil, coral/teal cards and a receipt roll illustrate review and testability.
3. **Demo — `demo-report.png`:** Capture the actual report rendered from the software. Show scenario names, outcomes and the receipt comparison legibly. No generated or reconstructed application UI.
4. **Experiment — `receipts-comparison.png`:** Plot the actual recorded 10 baseline and 2 guarded receipts. Explain that receipt means fixture arrival before validation, not successful mutation. Eight call attempts have baseline receipt 1 and guarded receipt 0; invalid-policy startup is a separate eleventh scenario.
5. **Release — `release-quickstart.png`:** Capture real clean-install command output and the resulting evidence report. Finalize the release availability claim only after public release readback and downloaded artifact verification.

The generated images are concept art, never evidence of enforcement. The receipt chart describes a fixed local fixture, never production security coverage or benchmark performance. Do not add customer logos, adoption numbers, novelty claims, a sandbox metaphor implying OS isolation, or claims of complete protection.

Full English prompts, visible-text checks, generator disclosure, source references, hashes, dimensions and inspection states live in `provenance.json`. Alt text is canonical in `campaign.json`. The first two assets were inspected using the image viewer: English wording is legible and the intended concept is present. Later assets require a visual inspection of the actual captures before provenance is marked passed.

`campaign.json` is the copy and metadata source of truth; `CAMPAIGN.md` is its readable rendering. Run `python3 campaign/validate.py --render --refresh-provenance` after inspecting all five assets. `--copy-only` permits copy review while the later captures are being prepared. `--require-release` additionally requires the release verification record. The validator checks receipt totals against the recorded software report and checks the image files and their hashes. It cannot establish visual quality or public release availability by itself.

All ten platform items remain prepared, unscheduled and unpublished. Preparing assets conveys no posting authorization or access to an account or scheduling queue.
