---
name: ezy-mail
description: Check and manage email on an EzyPlatform site — EzyMail delivery health (is anything actually being sent?), EzyMail mail templates in `mail-templates/`, and the EzySupport Contact Us flow (supporter notification and confirmation mail settings, end-to-end form test). Use before building any feature that sends email, when a contact form, password reset or order mail "does not arrive", when editing mail templates, or when wiring a site form to `POST /api/v1/contact-us`.
---

# ezy-mail

> Paths: `${CLAUDE_SKILL_DIR}` is this skill's folder (Claude Code substitutes it; other agents: replace it with the folder containing this SKILL.md). Sibling skills and the shared library `ezy-shared` sit next to it. Run commands from the site project root (the folder with `environment.json`).

Read `ezy-guide` (safety rules, gotchas 13–18) first.

## 1. Health check (always first, read-only)

```bash
S=${CLAUDE_SKILL_DIR}/scripts/ezy_mail.py
python3 $S status
```

Reports the default delivery service and its non-secret fields, which required fields are empty, the status counts of the last 200 mails (`SENT` / `SEND_ERROR`), and the EzySupport Contact Us settings. On a fresh install the SMTP host is empty and **every** mail fails silently (gotcha 16): tell the human before building anything that depends on mail.

**Credentials are the human's job.** Never read, print, store or type an SMTP password or provider API key, even when the human pastes one in chat: tell them which fields to fill in Admin → EzyMail → Settings → the service (for an SMTP relay such as Resend: host `smtp.resend.com`, port 587, username `resend`, password = API key, sender on a domain verified at the provider), and suggest rotating a key that was pasted into a chat. Then re-run `status`.

## 2. Contact Us flow (EzySupport)

`POST <web_url>/api/v1/contact-us` (public, JSON) with `contactUsYourName`, `contactUsYourEmail`, `contactUsSubject`, `contactUsMessage`. It stores a request (Admin → EzySupport → Contact Us), mails `contact_us_notification` to the **Supporter Emails**, and, when **Response Mail** is on, mails `thanks_for_contacting_us` to the visitor.

```bash
python3 $S contact-settings                                               # show
python3 $S contact-settings --response-mail on --supporter-emails info@example.com   # dry run
python3 $S contact-settings --response-mail on --supporter-emails info@example.com --yes
python3 $S test-contact --email <inbox the owner controls> --yes          # after approval
```

- `contact-settings` resends the whole settings form (the PUT replaces it; gotcha 15), backs up the old values and checks that nothing else changed.
- `test-contact` sends one real request, lists the mails it produced and deletes the request again. It sends real mail: get approval and use an inbox the site owner controls.
- Front-end form: `fetch('/api/v1/contact-us', {method: 'POST', headers: {'Content-Type': 'application/json'}, body})`. Success is `204` with an empty body; validation errors come back as `{"<field>": "required|invalid"}` with status 200 on some sites and 400 on others (gotcha 17), so check both the status and the body. Disable the button while sending and keep a `mailto:` fallback for network errors.
- A topic select maps to `contactUsSubject`; extra fields need **Accepted Contact Us Metadata Keys** first.

## 3. Mail templates (`mail-templates/<name>/`)

```bash
python3 $S templates                        # local vs server, plus server-only templates
python3 $S pull thanks_for_contacting_us --write
python3 $S push thanks_for_contacting_us    # dry run
python3 $S push thanks_for_contacting_us --yes
```

- Layout and placeholders follow the project `AGENTS.md` (`title.html`, `content.html`, `meta.json` with `contentType`, `status`, local-only `parameters`).
- Plugin templates (`contact_us_notification`, `thanks_for_contacting_us`, `forgot-password`, order mails) ship in English with generic text; localize them for the site's audience. Keep every `${variable}` the plugin fills in (`username`, `email`, `subject`, `message`, `phoneNumber` for Contact Us).
- A template has one language; for a bilingual site write both languages in the same mail.
- `push` backs up the server version to `.artifacts/backups/` and re-reads it to verify.

## Finish

Report the health result, what changed (settings, templates) with backup paths, the test result, then run the improvement check (`references/skill-improvement.md` of `ezy-guide`).
