# Security

Vanguard is built to run **completely offline** on a Soldier's own device. No account, no tracking, no GPS, no data sent anywhere.

## What protects the Soldier's data

| Threat | Protection |
|---|---|
| A website open in the same browser tries to send commands to Vanguard (CSRF) | Commands must be JSON (browsers must ask permission first, and Vanguard never grants it); any request from another site's origin is refused; no CORS headers are ever sent. |
| A website tries to read Vanguard's data by pointing its name at this computer (DNS rebinding) | Requests are only accepted for Vanguard's own address (`127.0.0.1` / `localhost`). |
| Another Soldier on a shared device | Each Soldier has their own **profile** (separate folder, own PIN). A session is bound to one profile; every request can only reach that profile's files, and Soldier data can't be read or written at all without an unlocked profile. |
| Someone else on the same network | Vanguard only listens on this device. LAN mode (`--lan`) refuses to start unless every profile has a PIN. |
| One Soldier changing Vanguard for everyone on a shared device | Installing an update (and reloading the library) needs a separate **device admin PIN**, stored as a salted PBKDF2 hash outside every profile, with the same growing lockouts. A profile PIN is not enough. |
| Someone picks up the device | **PIN lock** (strongly recommended — it also turns on encryption): 6–12 digits, stored only as a salted PBKDF2-SHA256 hash (400,000 rounds). Sessions are random tokens in an HttpOnly, SameSite=Strict cookie and expire after inactivity (5–60 minutes). Five wrong PINs start a lockout that doubles each time (up to 1 hour) and survives restarts. |
| Someone copies the files off the device (stolen tablet, USB, another Windows user) | A profile with a PIN has **its files encrypted** with AES-256-GCM using its own random 256-bit key. That key is stored only locked by the PIN (scrypt, 32 MB, memory-hard) and by the Soldier's recovery code, and is held in memory only while the profile is unlocked. Each file is bound to its name, so changed, damaged, swapped or renamed files are refused, never read. Only `security.json` (PIN hash, locked key) is unencrypted. |
| A crash or power loss while saving | Every file is written to a temporary file, flushed to disk, then renamed into place, so a save is all-or-nothing. |
| Injected scripts (from a document, an answer, a pasted letter) | All text is escaped before display, and a strict Content-Security-Policy only allows Vanguard's own script file. |
| Path tricks to read other files | Only files inside `web/` are served. |
| A tampered download | The private build page shows each zip's SHA-256 fingerprint. |

Automated attack tests for all of the above: `python -m unittest discover tests`.

## Forgotten PINs: the recovery code

When a Soldier sets a PIN, Vanguard shows a **recovery code** once (`XXXXX-XXXXX-XXXXX-XXXXX`, 100 bits). It's a second key to that Soldier's files. If they forget their PIN, **Forgot PIN?** on the lock screen takes the code and a new PIN; the files stay encrypted throughout and a fresh code is issued. Wrong codes count toward the same lockout as wrong PINs. A new code can be made any time in Me → Security (with the PIN).

There is deliberately **no master key**: not the device owner, not a leader, not Vanguard can open a profile without its PIN or recovery code. Anything that could would also let a thief in. If a Soldier loses both, their encrypted backup (below) is the way back.

## What the device owner must do too

Vanguard encrypts each Soldier's files, but full-disk encryption still protects everything else on the device (the AI model, the library, Windows itself). **Turn it on:**

- **Windows**: BitLocker (Settings → Privacy & security → Device encryption, or BitLocker on Pro editions). Use a Windows sign-in PIN/password.
- **Linux / Raspberry Pi**: LUKS full-disk encryption at install time.

Also: keep the OS updated, use a standard (non-admin) account for daily use, and don't install other software on a dedicated Vanguard device.

## Backups
**Me → Download encrypted backup** saves one file (profile, logbook, letters, address book, study progress, memory), encrypted with AES-256-GCM under a **backup password of at least 10 characters** that the Soldier chooses (a backup can be attacked offline, so a 6-digit PIN isn't enough). Without the password the file can't be opened. Device settings (AI model, online switch, keys) are never included, and restoring a backup can never change them.

## Library tamper check
When the library is installed, Vanguard records a SHA-256 fingerprint of every manual (`library/integrity.json`). At startup it recomputes them: **Me → Library check** says whether every file still matches, and search marks any result from a changed file. If the publisher signed the list (`tools/sign.py library` → `integrity.json.sig`), the signature is checked too, so editing a manual *and* its fingerprint doesn't go unnoticed.

## Signed offline updates
An update is the normal release zip plus a `.sig` file. On a device: **Me → Install an update from a USB stick**, choose both files. Vanguard installs it only if:
- the signature matches the publisher's public key (`vanguard/data/release_key.pub`, Ed25519);
- it's a **newer** version (no downgrades);
- every file is inside the app's own folders (no unexpected or `..` paths).
Soldiers' data (`~/.vanguard`) is never touched. Then restart Vanguard.

**For the publisher (build machine only):**
1. Once: `python tools/sign.py keygen` — writes the private key to `~/.vanguard-release/release_key.pem` (keep it safe and **off every device**; back it up) and the public key to `vanguard/data/release_key.pub` (commit it, so devices get it with the next install).
2. Each release: `python site/build.py` signs the zip automatically when that key is present (`tools/sign.py sign <zip>` does it by hand). Optionally `python tools/sign.py library` before building, to ship a signed library list.
Anyone who has the private key can sign updates — treat it like a password.

## Online AI (off by default)
Vanguard has no online options in its screens. A technical operator can enable an online AI provider by editing `~/.vanguard/config.json` (`"online": true` plus a key). Doing so sends the Soldier's questions to that provider — don't enable it on devices meant to stay fully offline.

## For military IT: adding CAC sign-in
Vanguard deliberately ships without CAC/PIV sign-in so that it can be configured by the Army's own IT, with its certificate validation and approval. All sign-in logic is in `vanguard/security.py`: a profile is unlocked by `unlock(profile, secret)`, which creates a session bound to that one profile. A smart-card provider would (1) have the card sign a random challenge with its PIV authentication key, (2) validate the certificate chain against the DoD PKI roots (and revocation, where a network is available), and (3) map the certificate to a profile by a hash of the certificate — never storing the DoD ID number. Nothing else in Vanguard needs to change.

## Official use
Use inside military networks or as an issued device would additionally require formal accreditation (Authority to Operate, STIG compliance). This project is designed to make that process straightforward: no network services, one well-known dependency (`cryptography`, PyCA, for AES via OpenSSL), all data local.
