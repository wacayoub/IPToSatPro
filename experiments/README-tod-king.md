# Experimental: dynamic King TOD + real black-screen recovery

**Status:** isolated, offline-tested policy modules only. NOT DEPLOYED. The main r69-beta updater, existing IPK, mappings and receiver settings remain untouched. No merge or release without actual receiver validation.

## User requirement (corrected 11 October 2026)

1. **ÉCRAN NOIR, NOT BLACKLIST**: when decoder/video evidence proves a channel has no playable picture, try the next playable IPTV candidate first; if no candidate remains and user enabled auto-skip, temporarily skip to the next channel. Never use a permanent name-based blacklist to decide what to skip. Do not skip on a short black transition, dark movie scene, missing bitrate, source title or EPG alone.
2. **King source TOD 1–14 only:** map TOD slots to SAT beIN Sports 1–10 dynamically from repeated on-air **video logo** evidence (e.g. TOD Sports 3 displaying beIN Sports 6). Invalidate old association when URL, event, watermark or stream identity changes. A title-only fuzzy match must NOT be evidence.
3. **Fast Zap:** preserve existing r64+ MANUAL LOCK and audio/decoder behavior. Avoid probes/discovery on already proven streams and never scan all 14 TOD feeds concurrently on Vu+ Zero 4K.

## Code actually created

- `experiments/king_tod_router.py`: temporary in-memory TOD/beIN associations from at least 3 properly spaced high-confidence logo detections; event+stream discontinuities clear old routes *even when the new frame has no visible logo*. TTL expiry, no saved mappings.
- `experiments/tod_dynamic_runtime.py`: exact King provider-ID scope, accepts evidence only from `decoded_video`, needs stream/event identity, respects manual locks during automatic route lookup; exposes on-air change and playback recovery APIs. It does not perform device-level navigation.
- `experiments/black_screen_recovery.py`: advisory, evidence-driven first-backup/then-next-channel recovery, startup grace, dark-image+confirmed silence safeguards, stale-generation rejection and bounded consecutive skips. This is **not** a blacklist; no channel is permanently excluded.
- `experiments/test_tod_dynamic_runtime.py` + `test_king_tod_router.py`: offline simulations for dynamic source isolation, logo switch, stale event invalidation, false-positive protections, decoder no-frames, dark+silent, EOF, fallback priority, hop limits and manual locks.
- `.github/workflows/king-tod-tests.yml`: runs offline Python tests on pushes/PRs. A green test is NOT evidence of real hardware playback.

## Integrations still REQUIRED before use on your receiver

1. Identify the exact internal provider ID for your King source rather than relying on an alias.
2. Attach a **real live decoded-video frame reader** and a logo recognizer using on-air beIN watermark templates. The recognizer does not exist in this branch yet. Synthetic or playlist-title labels must NEVER mark a channel as beIN.
3. Feed reliable video-frame counters, first actual decoded frame, EOF and independent audio evidence into BlackScreenAutoSkip from the active Enigma2 generation; the current module does not collect receiver telemetry itself.
4. Connect optional advisory recovery to actual channel-list CH+/CH- navigation, preserving direction, parental control, timeshift, SAT native channels and recorded manual locks; cap retries and cancel on zap race.
5. Supply verifiable provider/URL/event transitions to invalidate old TOD mapping immediately; reject stale/wrong-provider decoder frames.
6. Measure zapping p50/p95 on 20 LOCKED and TOD channels including 4K, stream with no image, genuinely dark video, 5002/4097, sound-only cases, source failover, audio loss and timeshift. 1–2 seconds remains a performance target, not a claim.
7. Run a rollback check and test the exact packaging/install paths on Vu+ Zero 4K OpenATV 8.0.1.

## Offline test command

```sh
python3 -m unittest discover -s experiments -p 'test_*.py' -v
```

## Safety status

- Not installed; no IPK available for this feature.
- No `main`, `update.json`, `latest-version.txt`, package payload or receiver file was changed.
- Do not use this as automatic TOD logo switching until video capture, detection and actual integration are present.


## 11 Oct 2026 — additional isolated prototype

- `enigma2_tod_event_bridge.py`: optional `nav.event` handler for real Enigma2 evStart, evEnd, evEOF, evUpdatedEventInfo. It monitors only the exact configured King source ID and TOD slot; video-logo callbacks are bound to the current service reference and navigation generation. Event/stream changes invalidate routes, including when no new logo is yet recognizable. On verified EOF it may **propose** backup recovery; timeshift/recording/manual-LOCK bypass it. It does NOT call playService or install a hook automatically.
- `video_logo_probe.py`: bounded **video-only** `grab -v -r 480` BMP capture using only stdlib, plus confidence/margin-gated white-watermark shape comparison against explicit manually verified cropped beIN logo templates. **No logo templates supplied yet; no real beIN recognition in production.** Different ROI/capture sizes and uncertain/ambiguous matches fail closed. This conservative recognizer may often return no result until actual broadcaster frames and ROIs are calibrated.
- `test_enigma2_tod_event_bridge.py`, `test_video_logo_probe.py`: fake navigation events and synthetic BMP frames, **not receiver evidence**.

### Integration and release gate
1. Determine exact provider ID from the real source configuration, and wire monitor-owned service context and lifecycle to the bridge; refuse title/EPG inference.
2. Obtain at least three **real, independent** decoded-video frames per actual logo from King at 480-pixel width; calibrate source-specific ROI/contrast and manually verify authentic beIN 1–10 templates. Do not misinterpret screenshot errors as black-screen evidence.
3. Call `grab_video_bmp` OFF the GUI thread, rate-limited to the currently selected TOD; discard identical capture digests, stale generation, switched reference or event changes before passing classifier output to the bridge. Never scan all 14 simultaneously.
4. Wire a **separate** reliable current decoder frame counter and independent audio state before enabling the no-picture/dark recovery rules. The current bridge only safely handles a verified EOF proposal; no automatic navigation is enabled.
5. Preserve explicit manual mappings, parental controls, timeshift, recordings and existing fast-LOCK path; validate 20 real channels, 4K/audio and fallback interactions on Vu+ Zero 4K OpenATV 8.0.1.
6. Only after hardware acceptance, create an opt-in test package with an install and rollback route. Do not modify `main`, `update.json`, latest version or publish an automatic IPK before then.

**As of this commit:** simulator CI passed for new modules, but actual on-air beIN watermark accuracy and receiver hooks are NOT validated. No user installation required.

## 11 Oct 2026 — static screenshots in BOTH upper corners

- No video recording: use individual screenshots of the live decoded picture with Enigma2 grab -v -r 480; -v excludes GUI/OSD overlays. Worker integration is not yet deployed.
- The beIN number watermark may be UPPER-RIGHT or UPPER-LEFT. VideoLogoMatcher now accepts verified reference watermarks with rois for left and right or individually calibrated placements. The top_corner_rois() helper is only an initial search region: real coordinates need broadcaster screenshot calibration.
- TodScreenshotSession checks exact service reference, navigation generation, provider ID, TOD slot, stream and event across each capture. Duplicate SHA-256 screenshot digests, stale events, rapid repeats and wrong providers are rejected. Distinct accepted captures must be >=0.45 seconds apart and the downstream router still requires 3 matching observations.
- Conflicting different broadcaster logos return NO assignment. Do not infer a channel from playlist text, EPG or the location of a crop alone.
- Offline tests cover right-to-left logo moves, competing logos, stale/duplicate screenshots, event changes and wrong provider; these are not real King signal or Vu+ Zero 4K measurements.
- Still missing: manually verified genuine beIN 1-10 on-air screenshot reference crops, a non-blocking worker scheduler with GUI handoff, actual decoder/audio-state telemetry for black-screen recovery and hardware acceptance. No live deployment or automatic release.

## 11 Oct 2026 — opt-in screenshot worker + verified template preparation

- Experimental tod_screenshot_worker.py now supports ONE screenshot in flight; only the subprocess video-only grab and BMP classification happen on a background Python thread. All Enigma2 bridge state access and recognition decisions happen on the GUI thread through an owner-controlled eTimer. No import or startup schedules any screenshot.
- Requests use an initial 2-second grace period, a >=0.65-second interval and at most 8 attempts per selected event. They stop after a verified watermark match, and never scan all 14 TOD channels. Nothing runs without actual verified logo references.
- Pending captures are rejected if the service reference or provider/event identity changes, or if manual lock, recording, timeshift or parental blocking applies. On unsupported decoder/grab, do nothing; an empty screenshot is NOT black-screen evidence.
- Experimental tod_reference_builder.py prepares actual manually verified watermark BMPs from on-air video-only screenshots, with distinct upper-left/right ROIs. It never guesses the channel from playlist names. Its --verified input is a human assertion; it does not verify the real broadcast or calibrate the watermark automatically.
- Offline tests cover one-in-flight behavior, GUI nonblocking, TTL and event changes, protected playback, manual validation and dual-corner synthetic reference crops. GitHub CI passing DOES NOT establish real Vu+ compatibility or the accuracy of any real beIN on-air logo.
- Still missing: real King source ID, genuine beIN Sports 1-10 calibrated logo samples, actual receiver-owned GUI context binding, instrumented decoded frame/audio evidence, end-to-end hardware tests, rollback and an optional receiver package. The test worker is NOT installed or attached to the existing IPToSatPro fast-zap runtime.

## 11 Oct 2026 — read-only live calibration capture gate

- `receiver_tod_capture.py` is a standalone **ONE-SHOT** tool for Vu+ Zero 4K. After the user has manually selected one King TOD 1–14 stream, it takes only THREE 480-width picture-only BMP screenshots with >0.5-second gaps, plus upper-left/right crops. It never zaps, touches playlists/mappings, installs packages, reaches a provider, scans 14 streams, or uploads imagery.
- The only output is a private new directory under `/tmp` containing the screenshots, corner crops, `report.json`, and `tod-images.zip`. The ZIP is a convenient optional manual one-file transfer, never an automatic upload. The report deliberately does not include URLs, provider credentials, channel names or service reference strings.
- If `grab` is unsupported, produces a PNG instead of BMP or yields non-distinct frames, the report says capture failed/unsupported. Such a result is NEVER classified as a black screen and NEVER used to confirm a beIN number.
- On receiver when ready: `wget -qO /tmp/tod-capture.py https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/fast-zap-tod-king-v1/experiments/receiver_tod_capture.py && python3 /tmp/tod-capture.py`
- This is not a receiver plugin or an on-air matcher. Human-authenticated examples of genuine beIN 1–10 logos and exact King source identity still must be established before calibration and any opt-in installation.

## 11 Oct 2026 — first receiver screenshots inspected: beIN Sports 7

- Three genuine 480x270 screenshots were supplied privately by the receiver owner and inspected. They depict tennis, visible beIN SPORTS 7 LIVE broadcaster bug at upper RIGHT and a distinct TOD watermark at lower RIGHT. The TOD watermark must be ignored. Screenshots were never uploaded to this public repository.
- The visible beIN 7 badge occupies approximately pixel bounding rectangle x=404..455, y=19..29 in the 480x270 sample. The discriminating numeral covers only about 5x5 pixels, so more real examples and preferably a larger capture are essential for validating all digits without false positives.
- Offline cross-frame white-mask Dice overlap for a manually selected 52x11 logo ROI was 0.9362 and 0.9371 relative to frame 1. Its tiny dark-digit mask overlapped 1.0 on the other two images. This is REPEATABILITY on one on-air logo only, NOT cross-channel precision/recall.
- The exact King provider ID, TOD 1-14 slot and actual ability to recognize any other beIN number could not be inferred from the screenshots (source_verified=false). A provisional calibration bundle stays private to the current conversation, not deployed to the box or committed as pixels.
- Critical safety gate: the experimental auto-mapping worker now refuses ALL screenshot-driven routes until independently verified samples for beIN 1 through 10 are present. A single 7 template alone could match the common beIN SPORTS banner from 6 or 8. Read-only offline diagnostics remain possible. This safety gate is covered by regression tests.


## 11 Oct 2026 — receiver-confirmed TOD slot correction

- The receiver owner clarified the source channel of the three captured images was **King TOD Sports 3, NOT TOD Sports 7**. The upper-right broadcaster watermark visibly identified **beIN SPORTS 7 LIVE**. Correct field observation: **TOD Sports 3 → beIN Sports 7**, only during that observed event; do not persist it as a fixed mapping.
- The two numerals have distinct meanings: **TOD 3 is the IPTV slot** and **beIN 7 is the on-air broadcaster logo**. They need not match, and the TOD slot may later carry beIN 1/6/8 or another beIN channel as events change.
- The channel slot was explicitly supplied by the receiver owner after capture; `report.json` did not itself verify the slot or King's exact provider ID. This one-off observation is calibration-only. Existing mappings, `main`, IPK, and receiver settings remain untouched.


## 11 Oct 2026 — offline SHADOW comparison without mapping

- The confirmed one-off field label is TOD Sports **3**, visible beIN Sports **7** at upper-right. That does NOT mean TOD 3 is always beIN 7.
- `experiments/tod_shadow_compare.py` is a new standalone, read-only command that compares three previously captured BMP images against three from another screenshot session. It never invokes Enigma2, `grab`, IPTV APIs, playlist scanning, navigation or writes a mapping.
- The current 480x270 field-specific reference ROIs are the beIN upper-right banner (404,19)-(455,29) and the miniature upper-right number (449,21)-(453,25). A human must label the reference number; `--reference-logo 7` is merely metadata and is NOT recognition evidence.
- SHADOW verdict is `CONSISTENT_WITH_REFERENCE` only when both sessions have 3 distinct frames, do not reuse the same full images, the reference digit pixels are stable, reference banner is stable, and all three current frames have sufficiently similar upper-right banner PLUS the exact small 5x5 numeral mask. Otherwise `UNKNOWN` (no guess about a replacement channel number). The output always sets `mapping_enabled=false` and `receiver_changes=false`. Same-image verdict is NOT proof of 10-way beIN precision.
- Run only when the original folders still exist (they are transient /tmp paths), using your own confirmed reference and fresh comparison folder: `python3 /tmp/tod-shadow.py --reference /tmp/reference-capture-folder --current /tmp/new-capture-folder --slot 3 --reference-logo 7`. Download the shadow script from the feature branch first. The two known sessions can be compared without capturing anything else.
- No broadcaster imagery nor channel credentials were committed to GitHub. Compare is purely diagnostic; the runtime still requires all 10 numbered beIN classes independently calibrated before automatic mapping can even be considered.


## 11 Oct 2026 — shadow calibration first field result: UNKNOWN

- First field comparison command used first receiver directory `tod-king-diagnostic-128o1n64` as reference and second `tod-king-diagnostic-r7ztwtov` as current, both labelled TOD Sports 3 with beIN 7 visible in the **uploaded second session**. It returned `UNKNOWN`, `reference numeral not independently stable`, no scores and mapping disabled.
- The three actual frame BMPs uploaded from the **second session** were inspected: the 5x5 numeral at `(449,21)-(453,25)` had exactly **7 dark pixels in each frame**, with **zero pixel-mask flips** between frames. This supports the chosen ROI only for the second session. The original first-session images were not uploaded, so we cannot conclude whether their instability is due to compression/background, logo animation, different channel, or event transition.
- Rather than relaxing the decision or asserting a false channel assignment, `tod_shadow_compare.py` now emits **reference_health/current_health** diagnostic fields including per-frame digit dark-pixel counts, pairwise 5x5 bit differences and banner overlap, plus a non-actionable suggestion for stable references. It returns `UNKNOWN` as before when a source is unstable. No new user capture or mapping required to run diagnostics; download latest tool and compare the same local folders.


## 11 Oct 2026 — first/second receiver screenshot pixel diagnosis

- User reran SHA-pinned shadow V4.1 on the same two capture sessions. `reference_health`: 5x5 numeral dark counts `[10,11,10]`, 1 maximum pixel flip; broadcaster banner similarity from first `[1.0,.9172,.92]`. `current_health`: numeral counts `[7,7,7]`, zero flips; banner `[1.0,.9362,.9371]`. Automatic mapping remains disabled.
- The reference is not three identical numeral masks, and a mask with 10 dark pixels differs from one with 7 dark pixels in **at least three bits**; this is more than just the one-bit instability *within* the reference. This does not prove a broadcaster change because both compression and different on-screen watermarks can cause changes. `UNKNOWN` remains the only safe classification.
- New offline diagnostic `cross_session_health` compares the full 3x3 set of source/target numeral masks and broadcaster banner overlaps and reports the 3-frame majority mask for ANALYSIS ONLY. It does not relax fail-closed acceptance, create a mapping, enable background capture, or install anything. No further receiver action needed unless user opts into evaluating the two existing folders again.


## 11 Oct 2026 — optional HD 960px screenshot preparation

- `receiver_tod_capture.py` now accepts optional `--width 960` (default remains the proven `480`). Captures exactly three snapshots of the CURRENT on-air service only with video-only `grab -v -r 960`; no automatic zapping, source access or upload.
- The original pixel-by-pixel whole-frame BMP decoding allocated many Python RGB tuples and could cause memory pressure at 960x540. New `bmp_metadata` and `crop_raw_bmp` extract upper-left/right regions directly from BMP byte rows; the full high-resolution RGB matrix is never expanded in Python objects. Supports 24/32-bit and top-down/bottom-up BMP, guarded against malformed files. Corner crops remain BMP with same pixels as previous implementation.
- Higher requested grab width may improve the tiny beIN numeral *if the receiver's video decoder exposes more source detail*, but upscaling a lower-quality source cannot create missing data. Actual output dimensions must be checked in `report.json`; the 960 path is **NOT hardware-tested yet**. Never promote a provisional single beIN 7 reference to a 1–10 classifier merely by upscaling.
- The older one-shot command without options still captures at 480. An optional later 960 diagnostic only, if wanted: `wget -qO /tmp/tod-capture.py https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/fast-zap-tod-king-v1/experiments/receiver_tod_capture.py && python3 /tmp/tod-capture.py --width 960`. It creates a private temporary folder; never installs any plugin or sets a mapping.
- `tod_shadow_compare.py` intentionally still requires 480x270 references, so do not feed 960 images into it; HD multi-class matcher calibration is separate future work. No new receiver testing is requested at this stage.


## 11 Oct 2026 — V6 multi-resolution read-only catalogue laboratory

- New experimental `experiments/tod_logo_catalog_lab.py` implements a purely offline `OFFLINE_CALIBRATION_AUDIT`, never an Enigma2/plugin mapper. It accepts three pre-existing independent BMP video frames per manually labelled beIN channel (1..10), verifies small-frame safety, repeated numeral-mask stability, banner repeatability, and near-duplicate numbered-logo mask collisions. It reports which real numbers have **not** been sampled. A `--sample 7=FOLDER` value is a human label, NOT independent proof of broadcaster identity.
- Supports screenshots of exactly **480x270** and **960x540** at their actual resolutions; rejects different resolutions combined in a catalogue. Scales measured reference ROIs only for diagnostic comparison, never pretends 480 screenshots contain 960 detail. The only field-calibrated ROI so far is the real upper-right **beIN Sports 7** badge in the user's three uploaded 480 snapshots from **King TOD Sports 3**; other digits, placement changes, and the beIN 10 double numeral need their OWN verified screenshots and ROIs before legitimate recognition.
- 960 lab also counts 2x2 numeral-mask blocks with mixed pixels. Such mixed blocks can indicate native detail **OR compression artifacts**, and uniform 2x2 blocks may indicate upscaling but do not prove it; this is an advisory metric only. Offline synthetic tests cover both cases without asserting real Vu+ HD output quality.
- Every single output explicitly sets `mapping_enabled=false`, `receiver_changes=false`, and `labels_verified_from_video=false` regardless of catalogue content. Even 10 apparently distinct templates only satisfy a very preliminary shape audit; held-out real cross-event and cross-channel testing plus hardware safety checks are still mandatory before any opt-in automatic mapping.
- When the existing local capture directory still exists, the V6 standalone **read-only** audit can be run (no need to do this now): `python3 tod_logo_catalog_lab.py --sample 7=/var/volatile/tmp/tod-king-diagnostic-r7ztwtov` after downloading the script. It does not recapture anything; it never edits user settings.
- NO screenshots, customer IPTV provider data or other private receiver content were committed to GitHub. No main, IPK, updater or installed plugin files changed. The 480 hardware capture was proven previously; **960 real receiver output and any true 1-10 recognition are not yet validated**.


## 11 Oct 2026 — V7 strict held-out shape study and offline-to-live safety gate

- The V7 `experiments/tod_holdout_study_v7.py` module performs an **OFFLINE**, read-only holdout study of labelled, independently captured images. It requires labels 1–10, pixel-separated digit masks, at least three distinct images per label, and similarity between live-broadcast watermark shapes; tested synthetic shapes do **not** authenticate labels or demonstrate real receiver recognition.
- The default 480-base x449..453 5×5 ROI reflects real King TOD Sports 3 carrying beIN Sports 7 only. It is explicitly **too small to represent beIN Sports 10's two digits**. A full 10-class study with that ROI returns `DIGIT_ROI_TOO_NARROW_FOR_BEIN10`, not a successful classification. A wider manually verified ROI is required. Upper-left placement is supported only when the investigator supplies **both** verified left numeral and broadcaster-banner ROIs; it never guesses a mirror as a real-live calibration.
- Even on 30/30 synthetic leave-one-out matches, the report always returns `deployment_ready=false`, `receiver_validated=false`, `labels_authenticated=false`, `mapping_enabled=false`, `capture_attempted=false`, `receiver_changed=false`. Real separate match/event holdouts and real King provider identity are still missing. Three frames from ONE event are correlated, so 30/30 does not establish precision or recall.
- Added a **second safety gate** on `tod_screenshot_worker.py`: ten reference template keys alone never activate the worker. The matcher must have explicit `receiver_validated is True` and `live_mapping_approved is True` as well as its 10 templates and the existing enabled/context checks. The present production VideoLogoMatcher does NOT set either approval field, so the experimental worker is now explicitly inert by default. Unit tests inject the flags only into fake matcher objects to test hypothetical control flow; they do not certify production.
- No branch merge, IPK, installer, updater, receiver settings, auto-lock, audio path or actual live mapping was changed. No user hardware test requested.


## 11 October 2026 — V8 cross-session, ten-number SHADOW-only validation

- Added `experiments/tod_cross_session_v8.py`, with explicit `--reference NUMBER=FOLDER` and `--holdout NUMBER=FOLDER` inputs. It reads precisely three `frame-01..03.bmp` files from each of two independent screenshot sessions per **human-labelled** beIN Sports 1–10 channel. It does not tune, fetch streams, scan IPTV, inspect credentials, capture images, update settings, or persist routes.
- The V8 comparison requires **all ten numerical labels**, a manually verified numeral ROI wide enough for the two-digit beIN Sports 10 badge, uniform 480 or 960 resolution, stable on-air numeral/banner masks, no reused full BMP digests across sessions or labels, and sufficiently separated class templates. Left-corner study requires separately verified upper-left ROI geometry; position is never inferred from a right-corner sample.
- Its per-number confusion results have three choices: correctly matched numerical **shape**, numerical **wrong match** (false positive), or **abstain** (UNKNOWN). If the numeral shape and banner disagree or margin is inadequate, it abstains instead of assigning a slot. V8 synthetic regression tests deliberately swap the held-out label 7 with the shape 8 and confirm this is counted as 3 wrong predictions, not accepted as a success.
- The two sessions MUST be authenticated by an observer as distinct real King event/stream observations: six different frame digests establish only unique frames, not independent match/event identity. The V8 code cannot authenticate labels from video content or prove true beIN precision/recall. One old receiver sample (King TOD Sports 3 broadcasting beIN Sports 7) is insufficient; 9 beIN number classes and future independent sessions are not yet provided. These real-world gaps are NOT covered by synthetic CI.
- Regardless of synthetic confusion counts, output always states `mapping_enabled=false`, `deployment_ready=false`, `receiver_validated=false`, and `receiver_modified=false`. No V8 code is connected to Enigma2 and no automatic mapping will be enabled without real held-out testing, audio/4K/timeshift validation and explicit receiver operator opt-in.
- GitHub Actions test suite reached 105 green tests at V8 test commit `e0d4ffcbbe0fc49199792224b47da60ffdb7bbcd`, including 9 V8 cross-session tests. Existing `main`, updater, IPK and the user's installed receiver plugin remain untouched. No further user action needed now.
