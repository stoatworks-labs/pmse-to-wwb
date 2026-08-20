/*
 * Stoatworks Labs — tell the support footer which build it is running in.
 *
 * The footer's "report a bug" form sends `data-version`, and triage renders it
 * as the build a report came from. This page is hand-written with no build step
 * and no manifest of its own, so there is nothing to stamp the attribute in: the
 * version reaches the page only through about-data.js, which sync-about.py
 * regenerates from the website's projects.json.
 *
 * So it is copied from there rather than written into index.html as a second
 * literal, which would drift from the About dialog the first time either was
 * updated alone.
 *
 * Classic and deferred, loaded after about-data.js and before support-footer.js:
 * deferred scripts run in document order, so STOATWORKS_ABOUT is already set when
 * this runs, and the attribute is already set when the footer reads it.
 */
(() => {
  const version = window.STOATWORKS_ABOUT && window.STOATWORKS_ABOUT.version;
  const tag = document.querySelector('script[src="/support-footer.js"]');
  if (version && tag) tag.dataset.version = version;
})();
