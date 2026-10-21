# Admin API endpoints used by the ezy-* skills

All calls: `Authorization: Bearer <admin_access_token>`, explicit `User-Agent`,
base URL = `admin_url` from `environment.json`. Sources: EzyArticle VS Code
extension 0.2.8 (`out/network.js`, `out/media.js`, `out/uploader.js`) plus live
checks. "Verified" = exercised against a live server.

## Identity
| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/admins/me/roles` | roles of the token owner (verified) |
| GET | `/api/v1/settings/web-url` | public site URL, plain text (verified) |
| GET | `/api/v1/settings` | `{items: [{name, value}]}`; `web_languages` (JSON) and `web_default_language` give the site languages (verified) |

## Content (EzyArticle)
| Method | Path | Notes |
|---|---|---|
| GET | `/ezyarticle/api/v1/pages/fragments?keyword=` | map page_name → fragment names (verified) |
| GET | `/ezyarticle/api/v1/pages/{page}/fragments/{name}` | default language only (verified, gotcha 2) |
| GET | `/ezyarticle/api/v1/post-by-slug/{slug}[?i18n_lang=]` | pages/posts, localized (verified) |
| GET | `/ezyarticle/api/v1/posts/{id}[?i18n_lang=]` | any post incl. fragments, localized (verified) |
| GET | `/ezyarticle/api/v1/posts?limit=&nextPageToken=` | list pages, posts and fragments without content; Trash excluded (verified, gotcha 12) |
| PUT | `/ezyarticle/api/v1/posts/{id}` | update; body rules in gotchas 3–4 (verified) |
| DELETE | `/ezyarticle/api/v1/posts?ids=1,2` | move to Trash, status `TRASH` (verified, gotcha 13) |
| PUT | `/ezyarticle/api/v1/posts/status?ids=1,2` | bulk status `{status}`; takes posts out of Trash (admin JS; not yet exercised) |
| POST | `/ezyarticle/api/v1/posts/save-simply[?publish=true]` | create or update as the extension does; body `title, content, additionalHead, additionalFoot, summary, contentType, status, postType, slug` (pages) or `pageFragmentPageName, pageFragmentName` (fragments), `language` for translations (verified by a site build script on payfs.vn) |
| GET | `/ezyarticle/api/v1/menus` | menus with items (verified) |
| GET | `/ezyarticle/api/v1/terms/{type}/{slugOrName}`, POST `/ezyarticle/api/v1/terms/add-or-update` | terms (extension) |

## Media
| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/media/{name}/contains` | `{contains: bool}` (verified) |
| POST | `/api/v1/media/add?notPublic=false` | multipart field `file` (extension) |
| POST | `/api/v1/media/{name}/replace-by-name` | multipart field `file` (extension) |
| GET | `/api/v1/media/{name}/public` | `{publicMedia: bool}` (extension) |
| PUT | `/api/v1/media/{name}/public` / `/unpublic` | toggle visibility (extension) |
| GET | `/api/v1/media/{name}` | binary download (extension) |

## I18n (EzySupport)
| Method | Path | Notes |
|---|---|---|
| GET | `/ezysupport/api/v1/{web|admin}/messages[?i18n_lang=]` | flat `{key: value}` map (verified) |
| PUT | `/ezysupport/api/v1/{web|admin}/messages` | `{languageCode, messageValueByKey}`; send only changed keys (extension shape) |

## Mail and Contact Us
| Method | Path | Notes |
|---|---|---|
| GET | `/ezymail/api/v1/mails?limit=` | sent/failed mails with `status` `SENT`/`SEND_ERROR`/`DELETED` (verified) |
| GET | `/ezymail/api/v1/templates?limit=` | template list (verified) |
| GET | `/ezymail/settings/mail-delivery-services/{CODE}` | admin HTML; form `mailSettingsForm` (`mailHost`, `mailPort`, `mailUsername`, `mailPassword`, `defaultSender`) — read, never print the password (verified) |
| PUT | `/ezysupport/api/v1/settings` | whole settings form; `supporterEmails`/`recruitmentEmails` as lists (verified, gotcha 15) |
| POST | `<web_url>/api/v1/contact-us` | public; `contactUsYourName`, `contactUsYourEmail`, `contactUsSubject`, `contactUsMessage`; 204 on success (verified, gotcha 17) |
| GET | `/ezysupport/api/v1/contact-us?limit=` | stored requests (verified) |
| DELETE | `/ezysupport/api/v1/contact-us/{id}` | marks a request `DELETED` (verified, gotcha 18) |

## Templates
| Method | Path | Notes |
|---|---|---|
| GET | `/ezymail/api/v1/template-by-name/{name}`, POST `/ezymail/api/v1/templates/add-or-update` | EzyMail (extension) |
| GET | `/ezysupport/api/v1/templates/{type}/{name}`, POST `/ezysupport/api/v1/templates/add-or-update` | EzySupport content templates (extension) |
