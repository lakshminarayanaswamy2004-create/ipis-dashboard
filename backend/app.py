# IPIS Dashboard - Backend Server
# Run with: python app.py
# Then open: http://127.0.0.1:5000 in your browser

import os
import re
import json
import asyncio
import requests
from flask import Flask, request, jsonify, send_from_directory

# ============== CONFIG ==============
# OPTIONAL: if you ever get a free API key from https://indianrailapi.com/,
# paste it here. The app works fully without one — it does NOT require this.
INDIAN_RAIL_API_KEY = ""

INDIAN_RAIL_API_BASE = "http://indianrailapi.com/api/v2/TrainSchedule/apikey/{key}/TrainNumber/{train_no}/"

VOICE = "hi-IN-SwaraNeural"   # the girl voice used in the original FoggPass app
TTS_RATE = "-5%"              # close to normal speed, slightly clear

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Support PyInstaller EXE: env vars set by main.py override defaults
STATIC_DIR  = os.environ.get('IPIS_STATIC',  os.path.join(BASE_DIR, '..', 'static'))
OUTPUT_DIR  = os.environ.get('IPIS_OUTPUT',  os.path.join(BASE_DIR, '..', 'output'))
BACKEND_DIR = os.environ.get('IPIS_BACKEND', BASE_DIR)
LOOKUP_FILE         = os.path.join(BACKEND_DIR, 'train_lookup.json')
STATION_LOOKUP_FILE_PATH = os.path.join(BACKEND_DIR, 'station_lookup.json')
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__, static_folder=STATIC_DIR)

# ============== Main offline train database ==============
# Loaded once at startup from train_lookup.json (~5,200 real trains,
# sourced from the public datameet/railways dataset, CC0 license).
# No internet, no signup, no API key needed for this to work.
try:
    with open(LOOKUP_FILE, "r", encoding="utf-8") as f:
        TRAIN_DB = json.load(f)
    print(f"Loaded {len(TRAIN_DB)} trains from local database.")
except Exception as e:
    TRAIN_DB = {}
    print("Warning: could not load train_lookup.json:", e)

# ============== Station code database (for expanding names like "ERS-SRR") ==============
STATION_LOOKUP_FILE = STATION_LOOKUP_FILE_PATH
try:
    with open(STATION_LOOKUP_FILE, "r", encoding="utf-8") as f:
        STATION_DB = json.load(f)
    print(f"Loaded {len(STATION_DB)} station codes.")
except Exception as e:
    STATION_DB = {}
    print("Warning: could not load station_lookup.json:", e)

# Train-type / class abbreviations to expand for speech.
# These get spoken out in full (EXP -> Express, SF -> Superfast, etc.)
TRAIN_TYPE_EXPANSIONS = {
    "EXP": "Express",
    "EXPRESS": "Express",
    "EXPRES": "Express",
    "EXPR": "Express",
    "SF": "Superfast",
    "SPL": "Special",
    "SPECIAL": "Special",
    "PASS": "Passenger",
    "PGR": "Passenger",
    "PASSENGER": "Passenger",
    "MAIL": "Mail",
    "JNS": "Jan Shatabdi",
    "RAJ": "Rajdhani",
    "RAJDHANI": "Rajdhani",
    "SHTBDI": "Shatabdi",
    "SHATABDI": "Shatabdi",
    "DRNT": "Duronto",
    "DURONTO": "Duronto",
    "GR": "Garib Rath",
    "SK": "Sampark Kranti",
    "INT": "Intercity",
    "FST": "Fast",
    "FAST": "Fast",
    "VANDE": "Vande",
    "MX": "Mixed",
    "MXD": "Mixed",
    # --- additional categories ---
    "VB": "Vande Bharat",
    "VBE": "Vande Bharat",
    "TJS": "Tejas",
    "TEJAS": "Tejas",
    "GTM": "Gatimaan",
    "GATIMAAN": "Gatimaan",
    "HSFR": "Humsafar",
    "HMSFR": "Humsafar",
    "HUMSAFAR": "Humsafar",
    "GARIB": "Garib Rath",
    "TOURIST": "Tourist",
    "LUX": "Luxury",
    "LUXURY": "Luxury",
    "DD": "Double Decker",
    "MEMU": "MEMU",
    "DEMU": "DEMU",
    "EMU": "EMU",
    "DMU": "DMU",
    "MMTS": "MMTS",
    "LOCAL": "Local",
    "SUB": "Suburban",
    "SUBURBAN": "Suburban",
}

# Words that must NOT be expanded - these are train CATEGORY names in
# their own right, not station-board shorthand, so they're spoken as-is.
TRAIN_TYPE_NO_EXPAND = {
    "MEMU", "DEMU", "LOCAL", "EMU", "DMU", "AC", "MMTS", "MAIL",
}


# Common short English words that happen to also be real station codes.
# These are BLOCKED from expansion even if all-caps, since in real train
# names they're almost always the English word, not the station.
# (e.g. "BI" in "BI-Weekly", not the station coded "BI")
SHORT_CODE_BLOCKLIST = {
    "TO", "AT", "ON", "IN", "IS", "IT", "BE", "BY", "AS", "NO", "SO",
    "DO", "UP", "GO", "MY", "WE", "OF", "OR", "AN", "IF", "BI", "AM",
}

def expand_train_name_for_speech(name: str) -> str:
    """Expand abbreviated train names into full spoken words.

    Examples:
      "ERS-SRR MEMU"        -> "Ernakulam Jn - Shoranur Jn MEMU"
      "MDU MS SF EXP"        -> "Madurai Jn Chennai Egmore Superfast Express"
      "AII HYB SF EXP"       -> "Ajmer Hyderabad Decan Superfast Express"

    Station codes are looked up in STATION_DB. Train-type words are
    expanded via TRAIN_TYPE_EXPANSIONS, except anything in
    TRAIN_TYPE_NO_EXPAND, which stays untouched.

    Safety rules to avoid false-positive collisions with ordinary words
    (e.g. "BI" in "BI-Weekly" matching a real but unrelated station code):
      - Train-type words (EXP, SF, ...) are matched case-insensitively,
        since that list is small and curated, so collisions are unlikely.
      - Station codes must appear in ALL CAPS in the original text to be
        expanded, AND must not be in SHORT_CODE_BLOCKLIST (common English
        words that happen to collide with real station codes).
    """
    if not name:
        return name

    # Split on spaces and hyphens, but remember the separators so we can
    # rejoin naturally (hyphen-joined codes become space-joined full names).
    tokens = re.split(r"([\s\-]+)", name)

    out_tokens = []
    for tok in tokens:
        if tok.strip() == "" or re.match(r"^[\s\-]+$", tok):
            # separator - normalize to a single space
            out_tokens.append(" ")
            continue

        stripped_tok = tok.strip(".,")
        upper_tok = stripped_tok.upper()
        is_alpha_word = stripped_tok.isalpha()
        looks_like_caps_code = stripped_tok.isupper() and is_alpha_word

        if upper_tok in TRAIN_TYPE_NO_EXPAND:
            out_tokens.append(tok)
        elif is_alpha_word and upper_tok in TRAIN_TYPE_EXPANSIONS:
            # train-type words: case-insensitive match is safe (small, curated list)
            out_tokens.append(TRAIN_TYPE_EXPANSIONS[upper_tok])
        elif (
            looks_like_caps_code
            and upper_tok not in SHORT_CODE_BLOCKLIST
            and upper_tok in STATION_DB
        ):
            out_tokens.append(STATION_DB[upper_tok])
        else:
            out_tokens.append(tok)

    result = "".join(out_tokens)
    # collapse any double spaces introduced by the rejoin
    result = re.sub(r"\s+", " ", result).strip()
    # Expand "Jn" suffix (meaning Junction) that appears after station names
    # e.g. "Ernakulam Jn" -> "Ernakulam Junction"
    result = re.sub(r"\bJn\b", "Junction", result)
    return result


# A few manually-added trains, in case you want to add ones missing
# from the main database above. Add more rows here any time:
MANUAL_EXTRAS = {
    # "12345": {"name": "Some Express", "source": "City A", "destination": "City B"},
}


def lookup_train_manual(train_no: str):
    """Check developer-entered manual overrides (MANUAL_EXTRAS dict above).
    These always win over everything else, since they're an intentional fix."""
    train_no = train_no.strip()
    if train_no in MANUAL_EXTRAS:
        e = MANUAL_EXTRAS[train_no]
        return {
            "number": train_no,
            "name": e["name"],
            "source": e["source"],
            "destination": e["destination"],
            "source_mode": "local_manual",
        }
    return None


def lookup_train_local(train_no: str):
    """Look up a train in the local offline database (instant, no internet)."""
    train_no = train_no.strip()

    rec = TRAIN_DB.get(train_no)
    if rec:
        return {
            "number": train_no,
            "name": rec["name"],
            "source": rec["source"],
            "destination": rec["destination"],
            "source_mode": "local_database",
        }
    return None


def lookup_train_erail(train_no: str):
    """Look up a train via erail.in's public train-search page (no key needed).

    This calls the same backend their own website search box uses.
    It's not an official documented API, so treat it as best-effort:
    if erail.in changes their page format, this may need updating.
    """
    url = f"https://erail.in/rail/getTrains.aspx?TrainNo={train_no}&DataSource=0&Language=0&Cache=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        text = resp.text
    except Exception as e:
        return None, f"Network error reaching erail.in: {e}"

    if not text:
        return None, "Empty response from erail.in"

    sections = text.split("~~~~~~~~")
    first_section = sections[0]

    if first_section in ("~~~~~Please try again after some time.", "~~~~~Train not found"):
        return None, "Train not found on erail.in"

    fields = [f for f in first_section.split("~") if f != ""]
    if len(fields) < 2:
        return None, "Unexpected response from erail.in"

    # Matches the reference parser: train_no normally lives at index 1.
    # If index 1 looks too long to be a train number, there's an extra
    # leading field, so shift everything down by one.
    if len(fields[1]) > 6:
        fields = fields[1:]

    if len(fields) < 7:
        return None, "Could not parse erail.in response"

    try:
        train_name = fields[2].strip()
        source = fields[3].strip()
        destination = fields[5].strip()
    except IndexError:
        return None, "Could not parse erail.in response"

    if not train_name:
        return None, "Could not parse erail.in response"

    return {
        "number": train_no,
        "name": train_name,
        "source": source,
        "destination": destination,
        "source_mode": "erail_live",
    }, None


def lookup_train_online(train_no: str):
    """Optional: query indianrailapi.com if a key has been configured."""
    if not INDIAN_RAIL_API_KEY:
        return None, "No online API key configured"

    url = INDIAN_RAIL_API_BASE.format(key=INDIAN_RAIL_API_KEY, train_no=train_no)
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
    except Exception as e:
        return None, f"Network/parse error: {e}"

    if str(data.get("ResponseCode")) != "200" or data.get("Status") != "SUCCESS":
        return None, data.get("Message") or "Train not found"

    train_name = data.get("TrainName", "").strip()
    route = data.get("Route", [])
    source = route[0]["StationName"] if route else data.get("Source", {}).get("Code", "")
    destination = route[-1]["StationName"] if route else data.get("Destination", {}).get("Code", "")
    # Some responses include a separate category/type field even when
    # TrainName is missing - grab it so the fallback name builder can use
    # it (e.g. "SF", "MAIL EXP", "SUPERFAST").
    type_hint = data.get("Type") or data.get("TrainType") or data.get("train_type") or ""

    return {
        "number": train_no,
        "type_hint": type_hint,
        "name": train_name or "UNKNOWN",
        "source": source or "UNKNOWN",
        "destination": destination or "UNKNOWN",
        "source_mode": "online",
    }, None


def lookup_train(train_no: str):
    train_no = train_no.strip()

    # 1) manual developer overrides always win - intentional fixes
    info = lookup_train_manual(train_no)
    if info:
        return info, None

    # 2) try erail.in's live train-search page next. Routes get extended/
    #    changed by Indian Railways over time, and the bundled local
    #    database is just a one-time snapshot, so live data is preferred
    #    whenever it's reachable.
    info, erail_err = lookup_train_erail(train_no)
    if info:
        return info, None

    # 3) live lookup failed (network hiccup, site down, train not found
    #    there) -> fall back to the local offline database so the app
    #    still works instead of failing outright
    info = lookup_train_local(train_no)
    if info:
        return info, None

    # 4) still nothing -> try indianrailapi.com if a key is configured
    if INDIAN_RAIL_API_KEY:
        info, err = lookup_train_online(train_no)
        if info:
            return info, None
        return None, err

    return None, erail_err or "Train not found"


def is_train_name_missing(name) -> bool:
    """True if a train's name is blank, None, or a known placeholder value."""
    if not name:
        return True
    return name.strip().upper() in ("", "UNKNOWN", "N/A", "NA", "NONE")


def detect_train_categories(text: str):
    """Scan raw text for known train-type keywords (Superfast, Passenger,
    Mail, Express, Duronto, Rajdhani, etc. - the same list used to expand
    names for speech) and return the matches, expanded to full words, in
    the order they appear, with no duplicates."""
    if not text:
        return []
    found = []
    seen = set()
    for tok in re.split(r"[\s\-/,]+", text.upper()):
        tok = tok.strip(".,")
        if tok in TRAIN_TYPE_EXPANSIONS:
            expanded = TRAIN_TYPE_EXPANSIONS[tok]
            if expanded not in seen:
                seen.add(expanded)
                found.append(expanded)
    return found


def build_fallback_name(train) -> str:
    """Build a spoken name like 'Kacheguda Superfast Express' for a train
    whose real name is missing/unknown. Uses any category hints available
    (e.g. a 'type_hint' field from an online API) plus the destination
    station. If no category can be detected at all, just the destination
    is announced - nothing is invented that wasn't actually in the data."""
    hint_text = " ".join([
        str(train.get("type_hint") or ""),
        str(train.get("name") or ""),
    ])
    categories = detect_train_categories(hint_text)
    destination = (train.get("destination") or "").strip() or "Unknown Destination"
    destination = expand_train_name_for_speech(destination)
    if not categories:
        return destination
    return f"{destination} " + " ".join(categories)


def build_announcement_text(train, spoken_override=None):
    """Build the spoken text for TTS.

    If spoken_override is provided (non-empty), it's used as-is - this lets
    the person manually correct mispronounced abbreviations from the dashboard.
    Otherwise, the train name is auto-expanded (station codes, EXP/SF, etc.)
    for clearer speech.
    """
    if spoken_override and spoken_override.strip():
        return spoken_override.strip()
    if is_train_name_missing(train.get('name')):
        return build_fallback_name(train)
    return expand_train_name_for_speech(train['name'])


async def _generate_tts(text, out_path, rate="-5%"):
    import edge_tts
    comm = edge_tts.Communicate(text=text, voice=VOICE, rate=rate)
    with open(out_path, "wb") as f:
        async for chunk in comm.stream():
            if chunk.get("type") == "audio":
                f.write(chunk.get("data"))


def generate_wav(train, volume_percent=300, speed_percent=120, spoken_override=None):
    """Generate an announcement audio file named after the train number, saved as .wav.

    volume_percent: 100 = original loudness, 200 = double, 300 = triple, etc.
    speed_percent: 100 = normal speed, 150 = 50% faster, 70 = 30% slower, etc.
    spoken_override: if provided, spoken text is exactly this instead of the
    auto-expanded train name (lets the person manually fix mispronunciations).
    Trailing/leading silence is trimmed automatically.
    """
    safe_no = re.sub(r"[^A-Za-z0-9]", "", str(train["number"]))
    mp3_path = os.path.join(OUTPUT_DIR, f"{safe_no}.mp3")
    wav_path = os.path.join(OUTPUT_DIR, f"{safe_no}.wav")

    text = build_announcement_text(train, spoken_override=spoken_override)

    # Convert speed_percent (100 = normal) into edge-tts's rate string (e.g. "+25%", "-10%")
    speed_percent = max(50, min(250, int(speed_percent or 100)))
    rate_offset = speed_percent - 100
    rate_str = f"{'+' if rate_offset >= 0 else ''}{rate_offset}%"

    asyncio.run(_generate_tts(text, mp3_path, rate=rate_str))

    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent

    audio = AudioSegment.from_file(mp3_path)

    # Resample to 44100 Hz. edge-tts natively outputs 24000 Hz, which plays
    # fine in software players but many embedded/hardware PA announcement
    # decoders only support standard rates (44100/48000 etc.) and will
    # silently refuse to play 24000 Hz audio.
    audio = audio.set_frame_rate(44100)

    # --- trim leading/trailing silence ---
    nonsilent_ranges = detect_nonsilent(audio, min_silence_len=100, silence_thresh=-40)
    if nonsilent_ranges:
        start = nonsilent_ranges[0][0]
        end = nonsilent_ranges[-1][1]
        # small natural padding so words aren't clipped
        start = max(0, start - 50)
        end = min(len(audio), end + 50)
        audio = audio[start:end]

    # --- apply volume boost ---
    volume_percent = max(50, min(500, int(volume_percent or 100)))
    if volume_percent != 100:
        import math
        gain_db = 20 * math.log10(volume_percent / 100.0)
        audio = audio.apply_gain(gain_db)

    audio.export(wav_path, format="wav")
    os.remove(mp3_path)

    return wav_path


# ============== ROUTES ==============

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(STATIC_DIR, path)


@app.route("/api/lookup", methods=["POST"])
def api_lookup():
    body = request.get_json(force=True)
    raw = body.get("train_numbers", "")
    numbers = [n.strip() for n in re.split(r"[,\s]+", raw) if n.strip()]

    results = []
    for no in numbers:
        info, err = lookup_train(no)
        if info:
            results.append(info)
        else:
            results.append({"number": no, "error": err or "Not found"})
    return jsonify({"results": results})


@app.route("/api/expand_preview", methods=["POST"])
def api_expand_preview():
    body = request.get_json(force=True)
    name = body.get("name", "")
    return jsonify({"expanded": expand_train_name_for_speech(name)})


@app.route("/api/generate_audio", methods=["POST"])
def api_generate_audio():
    body = request.get_json(force=True)
    train = body.get("train")
    volume_percent = body.get("volume_percent", 300)
    speed_percent = body.get("speed_percent", 120)
    spoken_override = body.get("spoken_override")
    if not train or "number" not in train:
        return jsonify({"error": "Missing train data"}), 400

    try:
        wav_path = generate_wav(
            train,
            volume_percent=volume_percent,
            speed_percent=speed_percent,
            spoken_override=spoken_override,
        )
        filename = os.path.basename(wav_path)
        return jsonify({"ok": True, "filename": filename, "url": f"/output/{filename}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/text_to_speech", methods=["POST"])
def api_text_to_speech():
    """Generate a WAV from arbitrary free-form text (standalone TTS tool)."""
    body = request.get_json(force=True)
    text = (body.get("text") or "").strip()
    volume_percent = body.get("volume_percent", 300)
    speed_percent  = body.get("speed_percent", 120)
    custom_filename = (body.get("custom_filename") or "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # Build a safe filename from custom name or first few words
        if custom_filename:
            safe_name = re.sub(r"[^A-Za-z0-9_\-]+", "_", custom_filename).strip("_") or "tts"
        else:
            safe_name = re.sub(r"[^A-Za-z0-9]+", "_", text[:40]).strip("_") or "tts"
        mp3_path = os.path.join(OUTPUT_DIR, f"{safe_name}.mp3")
        wav_path = os.path.join(OUTPUT_DIR, f"{safe_name}.wav")

        speed_percent = max(50, min(250, int(speed_percent or 100)))
        rate_offset = speed_percent - 100
        rate_str = f"{'+' if rate_offset >= 0 else ''}{rate_offset}%"

        asyncio.run(_generate_tts(text, mp3_path, rate=rate_str))

        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent
        import math

        audio = AudioSegment.from_file(mp3_path)
        audio = audio.set_frame_rate(44100)

        nonsilent_ranges = detect_nonsilent(audio, min_silence_len=100, silence_thresh=-40)
        if nonsilent_ranges:
            start = max(0, nonsilent_ranges[0][0] - 50)
            end   = min(len(audio), nonsilent_ranges[-1][1] + 50)
            audio = audio[start:end]

        volume_percent = max(50, min(500, int(volume_percent or 100)))
        if volume_percent != 100:
            gain_db = 20 * math.log10(volume_percent / 100.0)
            audio = audio.apply_gain(gain_db)

        audio.export(wav_path, format="wav")
        os.remove(mp3_path)

        filename = os.path.basename(wav_path)
        return jsonify({"ok": True, "filename": filename, "url": f"/output/{filename}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/output/<path:filename>")
def output_file(filename):
    resp = send_from_directory(OUTPUT_DIR, filename)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


if __name__ == "__main__":
    import socket

    # Auto-detect local IP for network mode
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    PORT = 5000
    print("=" * 55)
    print("  IPIS Train Announcement Dashboard")
    print("=" * 55)
    print(f"  Local access:    http://127.0.0.1:{PORT}")
    print(f"  Network access:  http://{local_ip}:{PORT}")
    print("  Share Network address with phone/tablet on same WiFi")
    print("=" * 55)
    print("  Do NOT close this window while using the app.")
    print("=" * 55)

    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
