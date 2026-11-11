# OWASP Juice Shop – Web Application Security Assessment

A hands-on security assessment of [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/), an intentionally vulnerable e-commerce web app. We exploited **21 challenges** across the OWASP Top 10, wrote up root cause, impact and mitigation for each, and backed the manual findings up with **static (SAST)** and **dynamic (DAST)** testing.

> Group project for *Web Application Security (COMP H2704)*, BSc Digital Forensics & Cybersecurity, TU Dublin – April 2026.

---

## Team

| Name | Challenges |
|---|---|
| **Alya Khalil** | Forged Coupon, Multiple Likes, Two-Factor Authentication, Expired Coupon, Blockchain Hype |
| **Benjamin Oludipe** | Email Leak, User Credentials, Access Log, Steganography, Change Bender's Password |
| **Marco Kunda** | Database Schema, Leaked Unsafe Product, Visual Geo Stalking, Login Amy, Reset Bender's Password |
| **Hanein Atalla** | Login Support Team, Reset Bjoern's Password, Login Bjoern, Nested Easter Egg, Christmas Special |

Everyone contributed to the SAST and DAST sections.

---

## Tools

| Purpose | Tools |
|---|---|
| Environment | Docker, Node.js |
| Interception and manual testing | Burp Suite (Proxy, Repeater), browser DevTools |
| Scripting | Python (`requests`, `threading`) |
| Static analysis (SAST) | Semgrep |
| Dynamic analysis (DAST) | OWASP ZAP |
| Other | OpenStego, John the Ripper (`keepass2john`), KeePass, Google reverse image search |

---

## Contents

- [Challenge summary](#challenge-summary)
- [Detailed write-ups](#detailed-write-ups)
  - [Forged Coupon](#1-forged-coupon-)
  - [Multiple Likes](#2-multiple-likes-)
  - [Change Bender's Password](#3-change-benders-password-)
  - [Steganography](#4-steganography-)
  - [Visual Geo Stalking](#5-visual-geo-stalking-)
  - [Login Amy](#6-login-amy-)
  - [Christmas Special](#7-christmas-special)
  - [Login Support Team](#8-login-support-team-)
- [SAST – Semgrep](#sast--semgrep)
- [DAST – OWASP ZAP](#dast--owasp-zap)
- [References](#references)

---

## Challenge summary

| Challenge | Vulnerability class | Owner | Mitigation |
|---|---|---|---|
| Forged Coupon | Cryptographic Failures | Alya | Server-generated, HMAC-signed coupons validated against the database |
| Two-Factor Authentication | Broken Authentication | Alya | Encrypt TOTP secrets at rest; never return them in API responses |
| Expired Coupon | Improper Input Validation | Alya | Enforce expiry against the server's UTC clock at redemption |
| Multiple Likes | Broken Anti-Automation | Alya | Unique DB constraint on (user, review) plus a server-side duplicate check |
| Blockchain Hype | Security Misconfiguration | Alya | Server-side authorisation on every route, whether it's linked in the UI or not |
| Email Leak | Sensitive Data Exposure | Benjamin | Redact sensitive fields from API responses; least-privilege data exposure |
| User Credentials | Injection | Benjamin | Parameterised queries; reject unsanitised input server-side |
| Access Log | Observability Failures | Benjamin | Put log endpoints behind authentication; never serve logs publicly |
| Steganography | Security through Obscurity | Benjamin | Audit public static assets; never embed sensitive data in them |
| Change Bender's Password | Broken Authentication | Benjamin | Verify the current password server-side before any change |
| Database Schema | Injection | Marco | Prepared statements so raw input never reaches the query |
| Leaked Unsafe Product | Sensitive Data Exposure | Marco | Properly delete sensitive records; block queries from reaching deleted data |
| Visual Geo Stalking | Sensitive Data Exposure | Marco | Don't use guessable/public info as security questions; strip identifying details from uploads |
| Login Amy | Weak Password Requirements | Marco | Check passwords against known/common lists; enforce MFA |
| Reset Bender's Password | Broken Authentication | Marco | Replace security questions with time-limited email reset links and MFA |
| Login Support Team | Security Misconfiguration | Hanein | Role-based access control; return 403 for unauthorised roles; disable directory listing |
| Reset Bjoern's Password | Broken Authentication | Hanein | Verify identity before reset; rate-limit attempts; invalidate sessions on reset |
| Login Bjoern | Broken Authentication | Hanein | Strong password policy, MFA, alerting on logins from new IPs |
| Nested Easter Egg | Cryptographic Issues | Hanein | Use standard encryption, not custom encoding; don't rely on obscurity |
| Christmas Special | Broken Access Control | Hanein | Server-side validation and allowlisting of product IDs |

---

## Detailed write-ups

Eight challenges (two per person) were picked for in-depth analysis. They cover distinct vulnerability classes and needed the most investigation.

### 1. Forged Coupon ★★★★★★
**Author:** Alya Khalil · **OWASP:** A02:2021 Cryptographic Failures · **CWE:** CWE-327

**Root cause.** Coupons aren't server-issued, signed tokens. They're a plaintext discount and date encoded with **Z85**, which is reversible and needs no key. The server keeps no record linking a coupon to a real issuance and doesn't check a signature, so anyone who understands the encoding can make their own.

**Exploit.**
1. Opened a Node.js REPL inside the Juice Shop container:
   ```bash
   docker exec -it <container_id> /nodejs/bin/node
   ```
2. Loaded the same Z85 library the app uses server-side:
   ```js
   var z85 = require('./node_modules/z85');
   ```
3. Built a coupon in the app's `MMMYY-DISCOUNT` format and encoded it:
   ```js
   z85.encode(Buffer.from('APR26-80', 'utf8'));  // → K#pDmhz3)x
   ```
4. Applied the forged code at checkout. The server accepted it and gave an **80% discount**.

**Impact.** Forged coupons look identical to real ones to the server, so a fraudster can buy goods for next to nothing. Once the trick is public, losses scale fast.

**Mitigation.**
- Generate coupons server-side with a CSPRNG and store them with discount, usage status and expiry.
- Validate by **database lookup**, not by decoding.
- If coupons must be stateless, sign them with an **HMAC** using a server-held secret so tampering fails the integrity check.
- Rate-limit redemption and flag unusually high discounts.
- Aligns with OWASP Proactive Control C8 and ASVS V6.

---

### 2. Multiple Likes ★★★★★★
**Author:** Alya Khalil · **OWASP:** A04:2021 Insecure Design · **CWE:** CWE-799

**Root cause.** The "one like per user" rule only exists in the UI: the button greys out after one click. The API never checks whether the user has already liked the review, so each request is treated independently.

**Investigation.**
- Inspected `GET /rest/products/reviews` in DevTools to get the review's `_id`, `likesCount` and the empty `likedBy` array, plus the Bearer JWT from the request headers.
- Captured the like request in **Burp Suite** and replayed it in **Repeater**. The endpoint accepted repeats without rejecting them.
- `race-the-web` wouldn't run in my Linux setup, so I wrote my own Python script instead.

**Exploit.**
1. Post a review and grab its `_id` and your JWT.
2. Run `race.py`. It spawns **10 threads** that send the like request at the same time using `threading` and `requests`.
3. Every thread got a success response, `likesCount` went up each time, and `likedBy` filled with duplicates. The server did no duplicate checking.

**Impact.** Attackers can fake review popularity and mislead customers (OWASP Automated Threats **OAT-016 Skewing**). At scale it also fills the database with junk.

**Mitigation.**
- Add a **unique constraint on (user_id, review_id)** at the database layer.
- Check for an existing like and return **HTTP 409** if found.
- Rate-limit the endpoint as defence in depth; CAPTCHA only as a secondary control.
- Aligns with OWASP Proactive Control C7 and ASVS V11 (Business Logic).

---

### 3. Change Bender's Password ★★★★★
**Author:** Benjamin Oludipe · **OWASP:** A07:2021 Identification and Authentication Failures · **CWE:** CWE-620

**Root cause.** `/rest/user/change-password` accepts a **GET** request and doesn't enforce the `current` password parameter server-side. Any valid session for an account is enough to overwrite its password.

**Exploit.**
1. Logged in as Bender using SQL injection on the login form (`bender@juice-sh.op'--`) with traffic going through Burp Suite.
2. Changed the password in the UI and captured the request:
   `GET /rest/user/change-password?current=<value>&new=<value>&repeat=<value>`
3. In Repeater, **removed the `current` value entirely** and set `new`/`repeat` to `slurmCl4ssic`.
4. The server returned **HTTP 200** and updated the password.

**Impact.** Anyone with a stolen session can take over an account and lock out the owner without knowing the original password. Sending passwords in a GET query string also leaks them into browser history, server logs and proxies.

**Mitigation.**
- Always verify the current password server-side; reject requests that omit it.
- Use **POST**, never GET, for credential changes.
- Add CSRF tokens and require re-authentication for sensitive account actions.
- Aligns with OWASP Proactive Control C6 and ASVS V2.1.

---

### 4. Steganography ★★★★
**Author:** Benjamin Oludipe · **OWASP:** A05:2021 Security Misconfiguration · **CWE:** CWE-653

**Root cause.** An image containing a hidden payload was deployed in the app's public static assets with no access restriction. The secret was "protected" only by nobody knowing where to look.

**Exploit.**
1. On the **About Us** page, inspected the image carousel in DevTools → Sources → `assets/public/images/carousel`.
2. Every image was a `.jpg` except one `.png`, which stood out.
3. Downloaded the PNG and ran it through **OpenStego** → *Extract Data* (no password needed).
4. Extraction succeeded and revealed the hidden image. Submitting it via the feedback form solved the challenge.

**Impact.** Anything hidden in public files can be pulled out once someone finds it. It also hints at wider poor hygiene, with other assets possibly mishandled the same way.

**Mitigation.**
- Never store sensitive data in publicly reachable files, hidden or not.
- Audit static assets so only what the front end needs is publicly served.
- Include asset review in pre-deployment security checks.

---

### 5. Visual Geo Stalking ★★
**Author:** Marco Kunda · **OWASP:** A07:2021 Identification and Authentication Failures · **CWE:** CWE-200, CWE-640

**Root cause.** Emma's security question (her former workplace) can be answered from a photo she posted publicly on the app's Photo Wall. Security questions based on facts about a user's life are often discoverable through OSINT.

**Exploit.**
1. Went to `/#/photo-wall` and found Emma's photo.
2. Ran a **Google reverse image search** to identify the location.
3. Looked closer at the photo and spotted the company logo **"ITsec"** in a window.
4. Used *Forgot Password* with Emma's email and answered the security question with that name. The reset worked.

No specialist tools needed. Anyone with a browser can do it in minutes.

**Impact.** Full account takeover through a normal-looking password reset. More broadly, users' photos can reveal where they live or work.

**Mitigation.**
- Replace security questions with time-limited email reset links and MFA.
- Strip EXIF/GPS metadata from uploads, and warn users about identifying details in photos.

---

### 6. Login Amy ★★★
**Author:** Marco Kunda · **OWASP:** A07:2021 Identification and Authentication Failures · **CWE:** CWE-521

**Root cause.** Amy's password looks strong because it's long and padded, but it copies a public example pattern. The app doesn't check new passwords against known or predictable patterns.

**Exploit (OSINT only, no brute force).**
1. The challenge hint *"93.83 billion trillion trillion centuries"* leads to **GRC's Password Haystack** page.
2. That page's *"One Important Final Note"* section shows a password padded with repeated dots.
3. Combined with the hint that Amy used a favourite TV character with numbers replacing vowels, the password is `K1f` followed by dot padding.
4. Submitted the login through Burp Suite. Login succeeded.

**Impact.** Full account compromise, and anywhere else Amy reused the password. A predictable password is weaker than a random one of the same length.

**Mitigation.**
- Check new passwords against lists of common and breached passwords (ASVS V2.1).
- Enforce MFA so a guessed password isn't enough on its own.

---

### 7. Christmas Special
**Author:** Hanein Atalla · **OWASP:** A01:2021 Broken Access Control / A04:2021 Insecure Design

**Root cause.** The server trusts the `ProductId` sent by the client when adding to the basket and never checks whether that product is allowed or visible to the user.

**Exploit.**
1. Logged in, added a product to the basket and watched the request in the DevTools Network tab.
2. Copied the `BasketItems` request as `fetch` into the console.
3. Changed `ProductId` to a hidden product's ID and resent it.
4. **"Christmas Super-Surprise-Box (2014 Edition)"**, a product that's no longer available, was added and the order completed.

**Impact.** Attackers can buy restricted items, abuse pricing and bypass business rules.

**Mitigation.**
- Validate and **allowlist** product IDs server-side.
- Enforce authorisation checks per product; never trust client-supplied IDs.

---

### 8. Login Support Team ★★★★★★
**Author:** Hanein Atalla · **OWASP:** A03:2021 Injection, A05:2021 Security Misconfiguration, A07:2021 Identification and Authentication Failures

**Root cause.** A chain of three weaknesses: SQL injection in product search, a publicly reachable FTP directory, and a KeePass database protected by a weak master password.

**Exploit.**
1. Used **UNION-based SQL injection** on the search endpoint to dump users:
   ```
   /rest/products/search?q=qwert'))UNION SELECT id,email,password,'4','5','6','7','8','9' FROM Users--
   ```
2. Found the support account: `support@juice-sh.op`.
3. Found `incident-support.kdbx` in the `/ftp` directory and downloaded it.
4. Converted it with `keepass2john` and cracked the master password with **John the Ripper**.
5. Opened the database in KeePass, got the support team's credentials and logged in.

**Impact.** Small weaknesses chain from data extraction to full account takeover, and from there to data breaches and credential reuse.

**Mitigation.**
- Prepared statements to stop injection.
- Lock down internal directories; disable directory listing.
- Use a strong master password for credential stores, and monitor for suspicious activity.

---

## SAST – Semgrep

**Setup.** Cloned the official Juice Shop repo and scanned the server-side code (`routes/`, `lib/`, `models/`):
```bash
semgrep --config=p/javascript --config=p/nodejs --config=p/owasp-top-ten
```
The Angular front end was left out because the focus was server-side controls. Test, mock and dev-utility files were filtered out as false positives, and missing security headers were treated as an infrastructure concern rather than an app flaw.

| # | Finding | Mapping | Fix |
|---|---|---|---|
| 1 | **Hardcoded / weak JWT signing secret.** Anyone who gets it can forge tokens for any user or role | A02 Cryptographic Failures | Generate the secret with a CSPRNG at startup; keep it in env vars or a secrets manager, never in version control |
| 2 | **SQL built by string concatenation** with request parameters. This matches the injection exploited in User Credentials and Login Support Team | A03 Injection · CWE-89 | Parameterised queries / ORM safe APIs (Proactive Control C3, ASVS V5) |
| 3 | **Path traversal.** User-supplied filenames passed to `path.join()` in file-serving routes (`path-join-resolve-traversal` rule) | CWE-22 | Resolve paths with `path.resolve()` and require them to start with an allowed base directory (ASVS V12) |

---

## DAST – OWASP ZAP

**Setup.** Ran ZAP against the Juice Shop Docker container. Instead of a blind full-site attack:
- Explored the app manually through the ZAP proxy to build the Sites tree.
- Added an authenticated session using a Bearer JWT.
- Ran an active scan with a **custom policy** limited to injection, authentication and information-disclosure checks. Irrelevant checks like XML injection and buffer overflow were excluded.

The scan took about 15 minutes and raised **87 alerts**. Low-confidence and optional-header alerts were deprioritised, and the top three were manually verified:

| # | Finding | Severity | Verification | Fix |
|---|---|---|---|---|
| 1 | **Reflected XSS** in the `q` parameter of `/rest/products/search` (CWE-79) | High | Loaded a crafted URL in the browser; the payload ran unencoded | Output-encode user input (Proactive Control C4) plus a Content Security Policy |
| 2 | **Missing authentication on user-data endpoints** returning personal details and order history. Links to Email Leak and User Credentials | Medium | Replayed requests in ZAP Requester **without** the Authorization header and still got full responses | Server-side auth middleware validating the Bearer token on every request (ASVS V4) |
| 3 | **Verbose errors.** Stack traces, internal paths and framework versions in error responses. Links to Access Log and Database Schema | Medium | Sent malformed JSON and out-of-range parameters to trigger Node.js stack traces | Global exception handler returning a generic 500; `NODE_ENV=production`; log details internally only |

---

## Running Juice Shop locally

Juice Shop is **deliberately vulnerable**. Only run it locally or in an isolated lab.

```bash
docker pull bkimminich/juice-shop
docker run --rm -p 3000:3000 bkimminich/juice-shop
# then open http://localhost:3000
```

---

## References

1. OWASP Foundation, *OWASP Top 10:2021*. https://owasp.org/Top10/
2. MITRE, *Common Weakness Enumeration (CWE)*. https://cwe.mitre.org/
3. OWASP Foundation, *OWASP Proactive Controls*. https://owasp.org/www-project-proactive-controls/
4. OWASP Foundation, *Application Security Verification Standard (ASVS) 4.0.3*. https://owasp.org/www-project-application-security-verification-standard/
5. OWASP Foundation, *OWASP Automated Threats to Web Applications*. https://owasp.org/www-project-automated-threats-to-web-applications/
6. OWASP Foundation, *OWASP Juice Shop*. https://owasp.org/www-project-juice-shop/

---

*This work was carried out against a local, intentionally vulnerable application for educational purposes.*
