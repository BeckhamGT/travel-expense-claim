# Native source acquisition and safe resume

Read the five URLs from the learner's unchanged original interview; the supplied policy slug resolves to POL-2026.2. Source URLs are evidence inputs, not permission to edit remote content. Current source identities and locators are retained in the selected run's `sources.json`.

For each new collection, attempt all five native locations through the browser or connected Google Drive tools. Record the actual completed observation time, native URL/locator and observed version. Retain unsuccessful scope with status `unavailable`, actual error and null path/hash/version; retain usable partial pieces separately. Never copy a previous manifest's observation time or claim fresh access from a URL/hash alone.

## PDF binders

Read Drive metadata before raw fetch. Use `fetch(download_raw_file=true, include_base64=false)` for these stored PDFs. Materialize the returned authenticated file reference into `retained/`; keep signed download links out of the repository. Preserve the raw complete bytes. Extract every page with `pypdf.PdfReader(...).pages`, retaining UTF-8 page records `{page, text}` and original wording in layout mode. Inspect page counts and empty pages, read every relevant record and visually check ambiguous layout.

The adapter source IDs are `INITIAL`, `UPDATES`, `RECEIPTS` for raw files and `INITIAL-PAGES`, `UPDATES-PAGES`, `RECEIPTS-PAGES` for extracted page arrays. Text derivatives are optional. The adapter parses the supplied SRC-D-3 claim and receipt layouts; a changed incompatible layout is a source-format defect to diagnose, not permission to guess fields.

## Workbook

Read spreadsheet metadata to discover actual tab names/IDs and bounds. Export the entire native workbook to XLSX. Read bounded native CellData for every populated tab, including headers/notes, `formattedValue`, `effectiveValue` and `userEnteredValue`. Retain each complete native response as `REGISTERS-<UPPERCASE-TAB-WITH-HYPHENS>`; `Sources.table` reads row-five headings and records starting at row six. Current tabs are People, Trips, Merchant payments, FX, Caps, Budget, Review ledger, Review packets, Finance activity and Travel cancellations.

Compare every populated native value with the complete export, including numeric precision and calendar/date representation. Preserve the source timezone metadata, but interpret local calendar dates and UTC event timestamps using the actual policy, not the workbook display timezone. Effective cap dates exposed as Excel serials are calendar dates. Record hidden/unread content, comments, formulas or external references when present; a successful header read is insufficient evidence of whole-workbook access.

## Policy

Use the browser to read and retain the complete original policy, including later paragraphs loaded by scrolling. Exclude browser chrome. Preserve original words and version in `POLICY`; document plain-text formatting normalization. When a freshly read document is unchanged, explicit comparison with the prior original representation is allowed; do not silently substitute an old document or an AI summary.

## Manifest and adapter

`sources.json` contains `run_id`, `source_version`, `case_clock`, `case_timezone` and `files`. Each file entry requires unique `source_id`, relative `path`, actual `sha256`, `status`, nullable `error`, native `url`, exact `locator`, UTC `observed_at` and observed `source_version`. Cover all five native URLs. Derivatives identify their original source; raw originals and the native workbook are retained alongside them. Paths resolve inside the run; no file hashes itself. `Sources` checks the retained bytes before arithmetic or decisions.

The submission collection contains all 229 searchable PDF pages, 16 policy paragraphs and 10 populated native tabs; all 13,703 populated workbook values match the fresh export. Its `retained/source-read-verification.json` records that acquisition check. This is evidence for that collection, not an assertion about future inputs.

To import changed sources or a changed implementation, obtain a complete new collection with a distinct run ID, `prior_run: {run_id, path, sha256}` binding the prior sibling run's `sources.json`, and `change_reason`. Retain full event/version history. This assignment supports arrivals 1–4. Start with preview, then seal batch1 and explicitly continue one batch at a time using README's commands. Every consumed stage is retained; actual operation timestamps remain separate from source business times.

For missing/corrupt consumption state, preserve the damaged run and use `recover --from-run <old-sources> --through-batch N` with a distinct freshly collected linked manifest. Recovery verifies the prior-manifest link and reconstructs the selected prefix only in the new run, recording current recovery observations. Normal continuation rejects missing, corrupt, unpaired or changed implementation state; it cannot silently recreate old snapshots. All retained-source reconstruction/verification is labelled offline processing, separate from the fresh acquisition observations. Never edit original sources, interview exports or earlier sealed stages.

The current revision collection is `artifacts/runs/revision-20261018T003113Z/`. All five fresh native reads succeeded at observed completion 2026-10-18T00:34:57Z. Its 21 bindings retain 229 complete PDF pages, all 16 policy paragraphs and all ten CellData tabs; 13,703 native values match the fresh XLSX. Business content is unchanged. The new XLSX ZIP differs while its cell values agree. `retained/source-read-verification.json` discloses actual sandbox-DNS failure/recovery, refreshed browser state after a stale accessibility reference, and representative rendering warnings/checks. Missing business definitions remain missing; see the learner's follow-up topics.
