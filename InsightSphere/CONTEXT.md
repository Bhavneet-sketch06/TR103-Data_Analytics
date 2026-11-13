# InsightSphere: context for the next session

A handoff note. Read this first to continue the work without re-discovering it. Last updated 2026-11-13.

## What this is

InsightSphere is a Streamlit sales-analytics dashboard. The owner rebuilt it from a 5.5/10 student project into something close to a real-world BI product. The main ideas:

- Upload any sales CSV or Excel file, confirm the column mapping, and every page fills in.
- It runs locally, and the data is never uploaded anywhere.
- It's built for non-technical users: every page states its conclusions in plain words.

**Status: complete.** Phases 1, 2, 3 and 5 of the rebuild plan are done, along with a final plain-language pass. Phase 4 (a Claude "Ask AI" assistant) was **deliberately skipped**: the owner decided the app is complete without it, and it would need an API key and paid credit. Don't add AI features unless asked.

The original plan file: `C:\Users\bhavn\.claude\plans\indexed-toasting-fog.md`.

## The owner's preferences (follow these)

- **Push as you go.** Commit and push every finished step to GitHub (see "Git and GitHub" below) without being asked. Never force-push.
- **Plain language everywhere.** The user isn't technical. Avoid jargon ("vs last year", not "vs LY"; "pts", not "pp"; "Method / Typical error", not "model / MASE"). Pages should say what to conclude: profit or loss, up or down, what to do.
- **Never present made-up numbers.** Every sentence and figure must be computed from the data.
- **"Clean SaaS" look** (Stripe/Linear-like) with designed light and dark themes. Check UI changes in **both themes**, and at 1440, 1280, 768 and 390 px.
- **The app starts empty.** Nothing is analysed until a file is uploaded, or until "Try sample data" is pressed on purpose.
- **The landing page hero is a fixed screenshot** of the dashboard (`static/hero-light.png`, `static/hero-dark.png`). It's shown whatever data is loaded, with no caption under it. Retake it if the Overview's look changes.

## Run and test

```bash
python -m streamlit run app.py      # opens http://localhost:8501
python -m pytest                    # 111 tests, about 1.5 minutes
```

- **Python setup:** the packages are installed in the system Python 3.14. The `venv/` folder is old and empty; ignore it.
- **Requirements:** `requirements.txt` lists streamlit 1.59, pandas 3, numpy 2, plotly 6, statsmodels 0.15 and openpyxl. `requirements-dev.txt` adds pytest.
- **`.claude/launch.json`** (git-ignored) runs a preview server on port 8510 with `--server.headless true`. `.streamlit/config.toml` itself has `headless = false`, so `streamlit run` opens the user's browser.
- **`.streamlit/config.toml` is generated.** Change `ui/tokens.py`, then run `python -m ui.tokens` to rewrite it.

## Architecture

```
app.py            st.navigation; theme CSS; background warm-up of statsmodels; sidebar (not on Home)
core/             pure pandas, unit-tested; no UI
  schema.py       18 canonical fields (order_date + revenue required), synonym matching, capabilities
  cleaning.py     safe cleaning: blank rows, duplicates, text normalising, numbers ($€,%), dates
                  (day-first vs month-first detected from the whole column); never fills missing numbers
  ingest.py       read CSV/XLSX (encoding fallback), apply mapping, derive (profit = revenue - cost,
                  discount 20 -> 0.20, ship_days, synthetic order_id), save uploads to data/uploads/<digest>
  state.py        active dataset: None until upload; "sample" only when chosen; kept in ?ds= URL param
  filters.py      date presets anchored to the data's last date, comparison windows (only when fully
                  covered by data), dimension filters (region/category/segment), cross-filter queue
  metrics.py      KPIs, series, breakdowns, top movers, comparison-series alignment
  insights.py     plain-language: overview_verdict, trend/breakdown one-liners, *_takeaways per page
  anomalies.py    unusual months: out-of-sample expectation, robust z >= 3.5, skips slices < 15 orders/month
  forecasting.py  seasonal naive / ETS / SARIMA, rolling-origin back-test, Auto = lowest MASE, 80/95% ranges
  simulator.py    what-if: discount (data-driven slope per category), price, volume; waterfall steps
  analytics/      customers.py (RFM, cohorts, new vs returning), products.py (Pareto/ABC, loss-makers,
                  discount bands, seasonality), operations.py (shipping, US state detection)
  db.py           SQLite database/insightsphere.db (git-ignored): revenue targets, saved forecast runs
ui/
  tokens.py       single source of design tokens (light/dark) -> CSS variables + config.toml
  theme.css       all styling, written against --is-* variables
  components.py   KPI tile, card(help=, insight=), verdict_banner, takeaways, item lists, empty states, tips
  blocks.py       KPI row (+ hover help), trend card, ranked bars, cross-filter charts, cached forecast/anomalies
  charts.py       Plotly house style, color maps, heatmap labels, formatters
  shell.py        page shell: header with date controls + theme switch, sidebar, PageContext, page()
  upload.py       shared upload + column-mapping flow (Home and Data pages)
  report.py       one-click self-contained HTML report (inline SVG charts), prints to A4 PDF
views/            one file per page: home, overview, sales, customers, regions, operations, forecast, data
static/           hero images, served at app/static/ (enableStaticServing = true)
docs/screenshots/ README images
tests/            unit tests + AppTest renders of every page with 4 uploads (sample, renamed, minimal, messy)
```

**Navigation:**

- Home (`/`, the landing page; no sidebar)
- Analytics: Overview (`/overview`), Sales, Customers, Regions, Operations
- Planning: Forecast (`/forecast`), with Forecast / What-if / Saved runs tabs
- Data (`/data`)

## What each page shows

- **Home:**
  - A hero ("Your sales, decoded.") with the fixed screenshot.
  - "Upload your data" scrolls to a big drop zone where column mapping happens.
  - "Try sample data"; "Continue with <file>" when data is loaded.
  - Feature cards and a footer.
- **Overview:**
  - A "Bottom line" verdict banner.
  - KPI tiles (change vs the comparison period, sparkline, target progress).
  - A trend chart with a bold conclusion line.
  - "Alerts and changes" (anomalies plus highlights).
  - Revenue by category and region; clicking a bar filters every page.
  - Top movers.
  - **Download report**.
- **Sales:** takeaways, a treemap colored by margin, Pareto/ABC, a seasonality heatmap, loss-makers, and a product table.
- **Customers:** takeaways, RFM segments, "Do customers come back?" cohorts, new vs returning, and top customers.
- **Regions:** region tiles, takeaways, a US map (revenue or margin), a state ranking with a Making/Losing money column, a breakdown table, and a state explorer.
- **Operations:** takeaways, discount bands vs margin, loss lines by band, discount vs margin scatter, ship modes, and ship time.
- **Forecast:**
  - Takeaways, a forecast chart with ranges, the method comparison, values and Save run.
  - **What-if** tab: sliders and a waterfall with a one-sentence result.
  - **Saved runs** tab: compare runs, and delete with confirmation.
- **Data:** upload or try the sample, Remove dataset, health checks, the mapping table, an explorer with CSV/Excel export, and monthly targets.

## Gotchas learned the hard way

- **Theme switching:** done in place by calling Streamlit's own React `setTheme`, found through the `.stApp` fiber (see `ui/shell.py`).
  - Never reload the page for it.
  - The helper script and a hidden "theme-sync" button live in `st-key-hidden-*` containers. They, and their layout wrapper, are `display:none`.
  - On a session's first run, the switch is synced to the theme stored in localStorage.
- **Charts read the theme from the switch's value** (`charts.current_mode()`), because `st.context.theme` lags one rerun.
- **Streamlit's header and toolbar** sit above the page. When the sidebar is collapsed they swallow clicks, so `theme.css` gives them `pointer-events: none`, with their own buttons re-enabled.
  - The header logo (`stHeaderLogo`) is hidden on Home.
  - On other pages, content gets extra top padding whenever that logo shows.
- **`st.html` strips inline SVG**, so HTML components render through `st.markdown(unsafe_allow_html=True)`. Use `<div>`, not `<p>`.
- **Run scripts with `st.html(..., unsafe_allow_javascript=True)`** inside a hidden container, not `components.html`. The iframe it creates shifts the layout.
- **Deferred `st.download_button(data=callable)`** runs in a background thread with no session. Capture everything the callable needs when the button is drawn (see `views/overview.py`).
- **AppTest `switch_page` matches pages by URL path**, so each page's file name must equal its `url_path`. That's why the Forecast page is `views/forecast.py`.
- **pandas 3:** `stack()` keeps NaN, and `.round()` warns on datetimes.
- **Headless-browser screenshots (Edge over CDP)** were used for visual QA. The scripts lived in the session scratchpad, which is temporary, so recreate them if needed.
  - Use a random debugging port and wait about 15 seconds for Streamlit to render.
  - The in-app browser pane is too small for layout checks.
- **Shell heredocs** in this Windows Git Bash sometimes choke on apostrophes. Write longer edit scripts to a file and run them.

## Git and GitHub

- **Branch:** work happens on `rebuild/v2` (the old `master` has only the original commit).
- **Destination:** pushes go to **TR103-Data_Analytics**, https://github.com/Bhavneet-sketch06/TR103-Data_Analytics, into the `InsightSphere/` folder on `main`, next to the owner's weekly training PDFs. Never touch the PDFs.
- **Remotes:**
  - `tr103` is that repo.
  - `origin` is `Bhavneet-sketch06/InsightSphere`, which still has the **old** version. Only push there if asked.
- **How a push works:** a separate git worktree on branch `tr103-main` follows `tr103/main`, and changes move into it with `git subtree`:

```bash
# 1. commit in the project (end the message with the Co-Authored-By line)
git add -A && git commit -m "..."

# 2. merge into the TR103 checkout and push
cd <worktree>                                  # git worktree list shows it
git fetch tr103 && git merge --ff-only tr103/main
git subtree merge --prefix=InsightSphere rebuild/v2 -m "Update InsightSphere: ..."
git push tr103 tr103-main:main
```

- **If the worktree is gone** (it lived in a temporary folder):

```bash
git worktree prune
git worktree add <some-folder> tr103-main
cd <some-folder> && git fetch tr103 && git merge --ff-only tr103/main
```

- **Check that GitHub matches the project:** `git rev-parse "rebuild/v2^{tree}"` must equal `git rev-parse "tr103/main:InsightSphere"`.
- **State at handoff:** both pointed to the same content (`77047cb…`), and nothing was uncommitted.

## Possible next steps (none requested yet)

- Deploy for free on Streamlit Community Cloud, so the dashboard opens from a link.
- Update the old `origin` repo (`Bhavneet-sketch06/InsightSphere`) to the new version.
- After any visible UI change, retake `static/hero-*.png` and `docs/screenshots/*`.
