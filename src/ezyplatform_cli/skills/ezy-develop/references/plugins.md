# Choosing plugins and reusing their data

Always confirm with the live market (`ezydev market search --limit 100`, `ezydev market info <name>`, `ezydev market docs <name>`): this table is a starting point, the market is the truth (new plugins, prices, versions). Prefer free plugins. A paid plugin needs the user's agreement and a purchase.

## Business need → plugin

| The user wants | Install / link | Reuse (tables, prefix) |
|---|---|---|
| Pages, blog, news, menus, categories, tags, comments, landing pages, FAQ, docs | `ezyarticle` | `ezyarticle_posts` (+ `post_type`), `ezyarticle_post_meta`, `ezyarticle_terms`, `ezyarticle_post_terms`, `ezyarticle_menus`, `ezyarticle_menu_items`, `ezyarticle_comments`, `ezyarticle_posts_i18n` |
| Shop: products, prices, sizes/colors, stock, cart, orders, vouchers, shops, branches, warehouses, invoices, affiliate, sellers, agencies | `ecommerce` (depends on others, installed automatically) | `ecommerce_products`, `ecommerce_product_prices`, `ecommerce_product_categories`, `ecommerce_product_meta`, `ecommerce_shopping_carts`, `ecommerce_orders`, `ecommerce_order_products`, `ecommerce_vouchers`, `ecommerce_shops`, `ecommerce_shop_warehouses`... |
| Online payment (gateways), payment plans, subscriptions | `ezypayment` | `ezypayment_payment_plans`, `ezypayment_payment_subscriptions` |
| Shipping, shipping rates, vehicles | `ezydelivery` | `ezydelivery_*` (with `ecommerce_delivery_orders`) |
| User sign up / login pages, OAuth2, sessions, social login | `ezylogin` | `ezylogin_*`; users themselves are core `ezy_users`, `ezy_user_meta` |
| User account pages and APIs, member organisations / teams | `ezyaccount` | `ezyaccount_account_member_entities`, `ezyaccount_account_member_entity_roles` |
| Contact info, contact form, social links, support | `ezysupport` | `ezysupport_contact_methods`, `ezysupport_social_networks` |
| Customers, groups, events, participants, CRM | `ezycrm` | `ezycrm_customers`, `ezycrm_user_groups`, `ezycrm_user_group_members`, `ezycrm_events`, `ezycrm_event_participants` |
| Ratings, reviews, likes, views, visitor analytics | `ezyrating` | `ezyrating_item_ratings`, `ezyrating_user_item_ratings`, `ezyrating_user_item_actions`, `ezyrating_daily_*` |
| Sending emails, mail templates, newsletters | `ezymail` | `ezymail_mails`, `ezymail_mail_histories`, `ezymail_unsubscribed_emails` |
| Chat, channels, messages (realtime) | `ezychat` | `ezychat_channels`, `ezychat_channel_members`, `ezychat_messages` |
| SEO (meta, sitemap) | `ezyseo` | settings only |
| Accounting, ledgers, invoices, financial reports | `accounting` | `accounting_accounts`, `accounting_ledger_entries`, `accounting_invoices`, `accounting_vouchers`, `accounting_*_reports` |
| Marketing campaigns, segments, workflows, short links | `ezymarketing` | `ezymarketing_campaigns`, `ezymarketing_participant_segments`, `ezymarketing_workflows`, `ezymarketing_shorted_urls` |
| Selling on several channels (marketplaces, social) | `omnichannel` | see `ezydev tables omnichannel` |
| Official accounts (Zalo OA...) messages | `ezyoa` | `ezyoa_oa_users`, `ezyoa_oa_user_messages` |
| AI chat / AI features, several AI providers | `ezyai` | settings + APIs |
| Search documents with AI (RAG), vectors | `ezyrag`, `ezyvector` | `ezyrag_data_chunks`, `ezyvector_collections` |
| IoT devices, MQTT | `ezyiot` | `ezyiot_devices` |
| Blockchain addresses, transactions, NFTs | `ezyblockchain` | `ezyblockchain_*` |
| Protect the site (IP blocking, rate limits) | `ezydefence` | `ezydefence_*` |
| Markdown content | `markdown` | - |
| Online games, rooms, matchmaking | `ezygame`, `game-master-server` (+ socket modules) | see their tables |
| GraphQL / generic REST APIs on data | `graphql` | - |
| Migrate from WordPress | `wordpress` | - |
| Backups, logs, multi-node | `data-backup`, `logs-monitor`, `sites` | - |

Ready-made themes and solutions (often paid): `fashion`, `retail`, `dropship`, `logistics`, `official-shipping`, `story`, `publishing`, `community`, `stackask`, `elearning`, `tournament`, `ai-skill-marketplace`; free themes: `freestyle`, `ezyblog`, `consulting`, `welcome`. When one of them already does what the user wants, tell the user: installing it (`ezydev install-plugin <name> --activate-theme`) may be enough, or the new project can build on it.

## Core tables (always installed, no plugin needed)

| Need | Table | Service (common-sdk) |
|---|---|---|
| Settings, feature flags, JSON config | `ezy_settings` | `SettingService` |
| Extra fields of any record | `ezy_data_meta` | `DataMetaService` |
| One unique value per record and key | `ezy_unique_data` | `UniqueDataService` |
| Relations between two records (with quantity / order / data) | `ezy_data_mappings` | `DataMappingService` |
| Translations of any record | `ezy_data_i18n` | `Data18nService` |
| Search keywords, counters | `ezy_data_indices`, `ezy_data_record_counts` | `DataIndexService`, `DataRecordCountService` |
| Users, user meta, roles | `ezy_users`, `ezy_user_meta`, `ezy_user_roles`, `ezy_user_role_names` | `UserService`, `UserMetaService` |
| Admins, roles, permissions | `ezy_admins`, `ezy_admin_roles`, `ezy_role_features` | admin services |
| Files and images | `ezy_medias` | `MediaService` |
| Letters (inbox), notifications | `ezy_letters`, `ezy_notifications` | `LetterService`, `NotificationService` |
| Content templates (mail, page snippets) | `ezy_content_templates` | `ContentTemplateService` |
| Short links | `ezy_links` | `LinkService` |

Use `data_type` / `mapping_name` values prefixed with the project name (`myshop_booking`) so they never collide with other projects.

## Examples of reuse instead of new tables

- Bookings of a spa: services = `ecommerce_products` (+ `ecommerce_product_meta` for duration), a booking = an `ecommerce_orders` row with order products; or, without a shop, posts of type `myspa_service` in `ezyarticle_posts` plus `ezy_data_mappings` (`myspa_booking`, user → service) with the time in the mapping data.
- Courses: course = `ezyarticle_posts` with `post_type=course`, lessons = posts linked by `ezyarticle_post_meta` or `ezy_data_mappings`, sales = `ecommerce`.
- Event registration: `ezycrm_events` and `ezycrm_event_participants`.
- Member profile fields: `ezy_user_meta`.
- Job board: jobs = `ezyarticle_posts` (`post_type=job`), categories = `ezyarticle_terms`, applications = `ezy_data_mappings` or a small own table if they need many fields and queries.

Create a new table only when none of these fits (many own fields, own queries and indexes). Then follow the generated project's `SKILL.md` section "Create a new table".
