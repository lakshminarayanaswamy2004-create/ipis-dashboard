╔══════════════════════════════════════════════════════════╗
║         IPIS — Train Announcement Dashboard              ║
║                    HOW TO USE                            ║
╚══════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FIRST TIME SETUP (takes 2 min)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Make sure Python is installed on this PC.
   → Download from: https://www.python.org/downloads/
   → IMPORTANT: Tick "Add Python to PATH" during install!

2. Double-click:  START_IPIS.bat

   First time only — it will auto-install Flask, edge-tts,
   and pydub. This takes about 1-2 minutes.
   After that it opens the app in your browser automatically.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  EVERY TIME AFTER THAT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Just double-click START_IPIS.bat
Browser opens automatically at http://127.0.0.1:5000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OPEN ON PHONE OR TABLET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When the app starts, the black console window shows TWO addresses:

  Local access:    http://127.0.0.1:5000      (this PC only)
  Network access:  http://192.168.1.XX:5000   (any device)

On your phone/tablet — connect to the SAME WiFi network,
then type the "Network access" address into the browser.
The full IPIS Dashboard opens on any device — no install needed!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DOWNLOADED WAV FILES SAVED TO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  IPIS_Dashboard\output\

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TO STOP THE APP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Close the black console window (START_IPIS.bat window).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FOLDER CONTENTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  START_IPIS.bat     ← Double-click this to run
  backend/           ← Python server + train database
  static/            ← Frontend (HTML/CSS/JS)
  output/            ← Your generated WAV files go here
  README.txt         ← This file
