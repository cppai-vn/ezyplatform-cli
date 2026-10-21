# EzyPlatform gotchas (verified)

Each entry was observed against a live server. Keep the evidence line; when a
gotcha stops reproducing on a newer platform version, update or remove it via
the improvement loop.

| # | Behaviour | Consequence / rule | Evidence |
|---|---|---|---|
| 1 | Cloudflare in front of the admin API returns `403 error 1010` for the default `Python-urllib` User-Agent. | Always send an explicit User-Agent (`ezy_client.py` does). | cpp.ai.vn, 2026-10-10 |
| 2 | `GET /ezyarticle/api/v1/pages/{page}/fragments/{name}` ignores `?i18n_lang=`; it always returns the default language. | Read a localized fragment through `GET /ezyarticle/api/v1/posts/{id}?i18n_lang=<lang>`. Otherwise a "sync" overwrites `content.en.html` with Vietnamese. | header/footer `.en` compare, 2026-10-10 |
| 3 | `PUT /ezyarticle/api/v1/posts/{id}` answers `400 {"fields":"invalid"}` when the body contains `metadata`, `terms`, `priority`, `publishedAt`, `parentId` or `commentStatus`. | Omit them; stored values are kept. Rebuild the body from the live post (`ezy_client.update_payload`). | theme no-op PUT, 2026-10-10 |
| 4 | Localized writes need `"language": "<lang>"` in the PUT body; without it the default language is overwritten. | Publish each language as its own request. | home vi/en publish |
| 5 | The server stores one `summary` for all languages; `meta.<lang>.json` summary is not persisted. | Put localized SEO text in the localized HTML `<meta>` tags instead. | home en summary compare |
| 6 | A fragment linked to a menu (e.g. header → menu 1) keeps the link only if `menuId` is sent; extension 0.2.8 does not send it from `meta.json`. | Publish such fragments with `ezy-publish` (keeps `menuId` from the live post), not the extension, until the extension supports it. | header post 10 |
| 7 | `GET /api/v1/settings/web-url` returns plain text, not JSON. | Use `ezy_client.request_text`. | 2026-10-10 |
| 8 | `/api/v1/media/<name>` on the public site returns 404 until the file is uploaded to the media library; local `api/v1/media` files are not on the server by themselves. | Run `ezy-media status` before referencing a media URL. | cpp.ai.vn, 2026-10-10 |
| 9 | Page/fragment `contentType` must be `THYMELEAF` for `ezy:replace`, `th:*`, `ezyfunctions` or `#messages` to render; `HTML` outputs them verbatim. | Check `meta.json` when markup shows up raw on the live page (`ezy-verify live` flags it). | README notes |
| 10 | Embedding images as data URLs works but bloats every page (cpp.ai.vn home ≈385 KB) and duplicates them per language. | Prefer the media library + `?v=` / `ezy:mhref`. | cpp.ai.vn home |
| 11 | Scroll-driven CSS animations (`animation-timeline: view()`) leave elements half transparent while partly in view. | Avoid opacity-based scroll reveals on content. | cpp.ai.vn redesign review |
| 12 | `GET /ezyarticle/api/v1/posts?limit=` lists every page, post and fragment (summaries: id, slug, title, status, postType, no content); trashed posts are left out. Corrects an earlier entry that said no page-listing API exists. | Discover pages with `ezy_client.list_posts` (`ezy-sync pull-all` does). | payfs.vn 98 and cpp.ai.vn 76 posts, 2026-10-11 |
| 13 | `DELETE /ezyarticle/api/v1/posts?ids=` (the admin bulk delete) moves posts to the Trash: `status` becomes `TRASH`, the post still reads by id **and by slug**, and leaves the post list. | Remove with `ezy-publish remove` (backup + verify); undo with `restore` (`PUT /ezyarticle/api/v1/posts/status?ids=`). Do not tell the human the delete is permanent. | payfs.vn ids 1–14, 92–98, 2026-10-11 |
| 14 | A removed page's public URL renders the theme's "not found" page with HTTP 200, not 404. | Check the page title/text, not the status code, when verifying a removal. | payfs.vn `/blogs`, `/v2-home`, 2026-10-11 |
| 15 | `PUT /ezysupport/api/v1/settings` replaces the whole EzySupport settings form; `GET` of that path returns the admin HTML page, not JSON. | Read every field from the `updateSettingsForm` on `/ezysupport/settings` and send them all (`ezy-mail contact-settings`). | admin JS on payfs.vn and cpp.ai.vn, 2026-10-11 |
| 16 | EzyMail's default delivery service is SMTP with an empty host after install; every mail (system notices, Contact Us, password reset) ends as `SEND_ERROR` with no visible alert. | Run `ezy-mail status` before building anything that sends mail. | payfs.vn 304/304 and cpp.ai.vn 200/200 `SEND_ERROR`, 2026-10-11 |
| 17 | Public `POST /api/v1/contact-us` (EzySupport) answers `204` with an empty body on success; validation errors are `{"<field>":"required|invalid"}` with status 200 on payfs.vn but 400 on cpp.ai.vn. | Front-end code must check the status **and** the body (see `ezy-mail`). | both sites, 2026-10-11 |
| 18 | Deleting a Contact Us request (`DELETE /ezysupport/api/v1/contact-us/{id}`) keeps it with status `DELETED`; Contact Us requests are stored as EzyMail mails (they appear in `/ezymail/api/v1/mails`). | Expect `DELETED` rows in mail stats. | payfs.vn test request, 2026-10-11 |
