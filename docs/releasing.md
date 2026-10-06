# Releasing the starter

Publish versioned source releases on GitHub, with the tag matching
`project.version` in `pyproject.toml`. The initial version is **v0.1.0**. PyPI
publishing and a project-generator package are outside this release process.

## Versioning and release evidence

Use `vMAJOR.MINOR.PATCH` Git tags. Before 1.0, patch releases contain compatible
fixes and minor releases may change the starter's setup or customization
contracts. Describe migration requirements in the changelog. Never move a
published tag; ship a new version to correct a release.

The final commit SHA, CI run links, source-archive results, and any remaining
blockers belong in
[readiness issue #9](https://github.com/pranman/django-tailwind-daisyui-template/issues/9)
and the GitHub release notes. Evidence must identify the exact commit tested.
A pass on an earlier PR commit does not establish that the final release commit
passes. Keep the release in draft until all gates below are satisfied.

## Required checks

The workflow is [Verify starter](../.github/workflows/verify.yml). Its baseline
matrix exercises these combinations rather than every Cartesian combination:

| Runner | Python | Node.js | Installer | Additional coverage |
| --- | --- | --- | --- | --- |
| Ubuntu 24.04 | 3.12 | 22.x, at least 22.10 | uv | Cold setup; lock/export drift |
| Ubuntu 24.04 | 3.14 | 24.x | pip | Cold setup; Chromium/browser checks |
| macOS 15 | 3.13 | 24.x | uv | Setup and process lifecycle |
| Windows 2025 | 3.13 | 22.x, at least 22.10 | pip | Setup and process lifecycle |

Use npm 10 or 11. Review matrix changes alongside the supported-runtime policy.
Retain the workflow's `starter-<matrix id>` verification artifacts when
investigating a failure. The `verification-artifacts` directory contains
diagnostic outputs; it is not part of the release source.

Public reproduction commands, from a disposable checkout with supported tools:

```bash
python scripts/check_dependencies.py --exports-only
python scripts/verify_starter.py --installer uv --cold
python scripts/verify_starter.py --installer pip --cold --browser
```

The export check requires uv on PATH. Browser verification requires the browser
runtime and host libraries documented by the verification script/workflow.
Run these commands against clean copies so a working local environment cannot
hide a setup failure. A successful command is evidence only for the machine and
commit on which it ran; the hosted matrix is still required.

Before tagging, record results for every gate:

- [ ] All acceptance criteria in issues #1–#8 are satisfied and linked from #9;
  outstanding requirements remain explicit release blockers.
- [ ] Python manifests, `uv.lock`, and both hashed requirements exports agree.
  npm installation uses the committed frontend lockfile.
- [ ] Cold uv and pip setup succeeds from a fresh checkout, with no activation
  or manual directory changes required by the README's quick start.
- [ ] Repeated setup preserves the existing secret, configuration, and database
  records, and recovers from a failed installation without resetting data.
- [ ] The homepage loads with compiled CSS; light, dark, and cupcake themes
  render and persist as documented. Keyboard controls, form labels, and mobile
  layout pass the supplied browser checks and a visual review.
- [ ] CSS edits rebuild, template/CSS edits refresh the browser, and Python
  changes preserve Django autoreload during development.
- [ ] Ctrl+C, occupied ports, and failure of either managed process leave no
  managed process tree or bound development port behind on every platform lane.
- [ ] A production CSS build, static collection, and Django deployment checks
  pass with explicit production settings. Confirm collected assets are present
  and browser reload routes/assets are absent from production behavior.
- [ ] README setup, customization, and deployment instructions have been walked
  through against the release candidate. Screenshots match the delivered demo.
- [ ] Hosted CI passes on the exact release commit, including the full matrix,
  browser checks, and export-drift check. Record the SHA and run permalinks.
- [ ] The renamed repository, template button, documentation links, private
  security-reporting route, and release URLs resolve correctly.
- [ ] The source archive passes the checks below. License files and their
  existing choice remain intact.

## Source archive walkthrough

Build a source archive from the candidate commit, then inspect its file list
before extracting it into a new directory. Do not package the live working
directory or upload an archive of an initialized application.

The archive must include `bootstrap.py`, Django source and templates, the CSS
entry point, `pyproject.toml`, `uv.lock`, both requirements exports,
`theme/static_src/package.json` and its lockfile, `.env.example`, documentation,
and both `LICENSE` and `LICENSE.GPL`.

It must exclude `.env`, databases, `.venv`, `node_modules`, caches, machine-local
files, and verification outputs. Prebuilt CSS and collected static files are
generated by setup/build commands and are not required in the source archive.
Check the archive for unintended symlinks and local absolute-path references.

Follow the README from the extracted archive using only the documented
prerequisites. Verify the styled homepage and safe rerun behavior. A source
archive has no `.git` directory, so setup must not depend on Git metadata.
Record the archive's source SHA, SHA-256 checksum, platform, installer, commands,
and results in #9. Repeat the file-list/download check against GitHub's published
source archive after publication.

## Tagging and publication

1. Update `project.version` and the changelog for the chosen release. Use the
   version and actual release date as its heading, and describe supported
   limitations and migration requirements. Regenerate dependency metadata if
   needed and commit these changes.
2. Complete all required checks on that final commit. Put the exact SHA and
   evidence links in #9. If another commit is needed, rerun the affected checks
   and the final hosted matrix; do not tag the previous candidate by accident.
3. Create an annotated tag `v0.1.0` pointing explicitly to the verified SHA and
   push that tag. Confirm the tag resolves to the recorded commit before
   creating the release. Later versions follow the same process.
4. Create a draft GitHub release for the existing tag. With `gh release create`,
   use `--verify-tag` so a missing tag is an error rather than an implicit tag
   on the current default branch. Include the changelog, tested matrix, evidence
   links, and source-only/PyPI limitations in the release notes.
5. Check the draft's links and source archive. Publish only when no readiness
   blocker remains. Check the public release page and downloadable contents,
   then link the release from #9 and close the completed issues/milestones.

## Recording release evidence

Keep verified results outside the source files so recording a commit SHA does
not create a new, unverified source commit. For v0.1.0, record the evidence in
[release issue #9](https://github.com/pranman/django-tailwind-daisyui-template/issues/9)
and copy it into the GitHub release notes. For later versions, create the
corresponding release issue and follow the same procedure.

1. Record the version, full final commit SHA, and annotated tag that resolves to
   that SHA. Include the permalink to the completed **Verify starter** run and
   the successful **Starter verification** aggregate check. State the tested
   platform/runtime matrix and browser results; retain a summary beyond the
   workflow artifacts' retention period.
2. Record the source archive's SHA-256 checksum, its source commit, the inspected
   file list, and the platform, installer, and commands used for clean setup and
   safe-rerun verification. Distinguish a locally generated candidate archive
   from GitHub's downloadable source archive and record checksums separately.
3. Link the completed requirement checks, documentation walkthrough, visual
   review, repository/security settings checks, and any explicitly supported
   limitations. Resolve every release blocker before publication.
4. After publication, add the public release/tag links and the downloadable
   archive inspection results to the same issue and release notes. Confirm
   that the published tag still resolves to the tested SHA.

A passing check on a different commit is supporting evidence only. If the
source changes after verification, complete the required checks on the new
commit and replace the release evidence before tagging or publishing.
