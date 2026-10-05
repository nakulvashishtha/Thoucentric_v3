# Checkpoint 3: the real UI, end to end, in demo data mode

Each `step_NN_*.jpg` shows the approved reference screen on the **left** and the live app on the **right**, both at
1440x860, driven by `tools/ui_walkthrough.js` (Playwright) through all 12 steps of Sample 1.

- The tool pane matches the reference on 11 of 12 steps with no visible difference (pixel diff under 0.01%).
  Step 5 differs only in how far collection had got when the picture was taken.
- Expected difference: the top-right button reads "Home" instead of "Restart" (live mode, as the guide spec says).
- `extra_*.jpg`: sign-in, a blank case in demo data mode (plain failure with Try again), History, an evidence drawer,
  the reply on step 9, a moved slider on step 11 and the saved conclusion.
- Fonts: the build sandbox blocks Google Fonts, so these pictures use the fallback font. The deployed app loads IBM Plex.
