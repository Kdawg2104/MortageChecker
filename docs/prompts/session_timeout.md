# Statement upload + 10-minute session timeout

Read CLAUDE.md first. Use plan mode and show me the plan before building.

## Check first
If the Statement Analyser / upload feature from docs/prompts/phase2_5.md does not exist yet, build that first
(following its privacy rules), then add this. If it exists, add to it.

## 1. Upload
- On the Statement Analyser page, an upload box (st.file_uploader) accepting PDF and CSV, multiple files allowed
  (e.g. 3 monthly statements or one 3-month statement).
- Only shown when HEADROOM_ALLOW_UPLOADS=1 (local use). Online/demo mode keeps upload hidden.
- Test it with data/samples/sample_jamie_statement.pdf and .csv (synthetic, Sample Bank) — both must parse to
  88 transactions, 1 Jul–30 Sep 2026, opening balance $40,000.00, closing $49,322.77.
  Compare categories against data/samples/sample_jamie_ground_truth.csv and report accuracy.
- Before upload, show the privacy notice, including: "Your data is processed on this computer only and is
  automatically deleted after 10 minutes of inactivity, when you click 'Clear my data', or when you close the tab."

## 2. Session timeout (10 minutes of inactivity)
Create ui/session_guard.py so the logic is in one place and testable:
- TIMEOUT_SECONDS = 600 and WARNING_SECONDS = 60 as named constants.
  (Timeout mode: INACTIVITY — every user interaction resets the timer.
   If I later want an absolute limit from upload time instead, make that a single constant: TIMEOUT_MODE = "inactivity" | "absolute".)
- All statement data lives under ONE session_state namespace (e.g. st.session_state["statement"]) — raw parsed
  transactions, reviewed categories, summary figures, AND any figures copied into the Calculator / Stress Scenarios /
  Simulator pages from the statement. Nothing statement-derived anywhere else.
- touch(): updates last_activity timestamp. Call it on every rerun of every page while statement data exists.
- check_and_expire(): if now − last_activity ≥ TIMEOUT_SECONDS, wipe.
- wipe():
  - delete every key in the statement namespace and any statement-derived pre-fills on other pages
  - reset the file uploader by changing its widget key (so the uploaded file objects are released)
  - clear any local variables holding DataFrames, then gc.collect()
  - set a flag so the next screen shows: "Your statement data was deleted after 10 minutes of inactivity."
  - pages that were using statement figures fall back to the manual form / defaults
- Inject the clock as a parameter (now_fn=time.time) so it can be tested without waiting 10 minutes.

## 3. Make the timeout work even if the user walks away
A normal Streamlit page only reruns when the user interacts, so an idle tab would never check the timer.
- Use st.fragment(run_every="15s") (check this is supported in the installed Streamlit version) on every page,
  running check_and_expire() and redrawing a small session status chip. The fragment's periodic run must NOT
  count as activity (must not call touch()).
- Status chip (top of page, only while statement data exists): "🔒 Statement data loaded — auto-deletes in 8 min".
- In the final minute show a warning with a "Keep my session" button (which calls touch()) and a "Clear now" button.
- Also check the timer at the start of every normal rerun, so expiry is enforced even if the fragment didn't run
  (e.g. the laptop was asleep).
- Closing the tab: check whether the installed Streamlit version has a server option for how long disconnected
  sessions are kept (e.g. server.disconnectedSessionTTL). If it exists, set it short (e.g. 60 seconds) in
  .streamlit/config.toml. If it doesn't, tell me what the actual behaviour is so the privacy notice is accurate.

## 4. Other safeguards (keep from Phase 2.5)
- No st.cache_data / st.cache_resource on anything statement-related.
- Nothing written to disk, logs or temp files. No network calls.
- "Clear my data" button always visible while data is loaded.
- Telemetry off: [browser] gatherUsageStats = false.

## 5. Tests (tests/test_session_guard.py) — use a fake clock
- Data present at 9:59 of inactivity; wiped at 10:00
- An interaction at minute 8 resets the timer: data still present at minute 17, wiped at minute 18
- The periodic fragment check does not reset the timer
- wipe() removes the statement namespace AND statement-derived pre-fills on other pages, and leaves unrelated
  state (e.g. disclaimer acknowledgement) alone
- "Clear my data" wipes immediately
- With HEADROOM_ALLOW_UPLOADS unset, upload is not available
- Parsing the sample PDF and CSV writes no files (working directory and temp dir unchanged)

## When done
- Run pytest (all pass), report categorisation accuracy on the Jamie sample.
- Tell me how to test the timeout manually (e.g. temporarily set TIMEOUT_SECONDS to 60 via an env var
  HEADROOM_TIMEOUT_SECONDS for testing — default stays 600).
- Plain-English explanation of session_guard.py I can use in an interview, including the limits
  (Python can't guarantee memory is overwritten, only released; the honest wording for the privacy notice).
- Update CLAUDE.md and README privacy section.
- Commit: "Statement upload with 10-minute inactivity timeout and automatic data wipe"