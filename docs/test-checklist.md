# Pre-deployment checklist

Local preview: `python3 -m http.server 58422 --bind 127.0.0.1`
Browser: Chrome (latest), Firefox (latest), Safari (iOS simulator width).

## Smoke
- [ ] Page loads with HTTP 200 on `/`
- [ ] No console errors
- [ ] No 404s in Network tab
- [ ] OG image appears when URL is pasted into iMessage / Slack (test via https://opengraph.xyz)

## Hero
- [ ] Title, venue tag, author line, affiliations all render
- [ ] Both resource pills link to the correct URL in a new tab
- [ ] Mail link launches the mail client

## Summary / Abstract
- [ ] Summary has teal left-border and larger font
- [ ] Abstract matches hero.json exactly

## Method
- [ ] 3 numbered steps render with teal circles
- [ ] architecture.png loads and shows the workflow diagram

## Results
- [ ] Figure 7 renders 2×2 grid
- [ ] Enhanced TimeAutoDiff has ★ + teal ring on all 4 panels
- [ ] Table 2 has per-cell bars and best-cell highlight
- [ ] Figure 6 renders two panels; HealthGen is a whisker (not a bar)
- [ ] Numbers match data/results.json / paper Table 2 / paper Section 5.3 exactly

## Subgroup Explorer
- [ ] Only eICU Mortality24 tab enabled (3 others disabled with "Data aggregation pending" tooltip)
- [ ] Clicking an age/sex/ethnicity pill updates the readout
- [ ] Subgroup where a method isn't exported shows a hatched bar
- [ ] Subgroup with single-class labels shows the single-class message
- [ ] Best method has ★ prefix

## BibTeX
- [ ] Copy button works; clipboard contains full BibTeX
- [ ] Matches data/bibtex.txt exactly

## Footer
- [ ] All 3 links open correctly
- [ ] "Last updated" date is current

## Accessibility
- [ ] Lighthouse Accessibility ≥ 95
- [ ] Tab order is hero → summary → … → footer
- [ ] `prefers-reduced-motion` disables bar-chart animations
- [ ] Keyboard-only navigation: every interactive element reachable, visible focus ring

## Responsive
- [ ] 1280 px: 2×2 Figure 7 grid, full hero
- [ ] 880 px: content padding halves
- [ ] 600 px: Figure 7 becomes 1 column; hero author line wraps
