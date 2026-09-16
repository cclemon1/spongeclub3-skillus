# 인사말 작성 레퍼런스

해외 거래처·유통사·파트너·고객에게 **이메일과 왓츠앱**으로
명절·국경일 인사를 보낼 때의 작성 지침. 날짜 조회는 `scripts/upcoming.py`, 발송 시각은
`scripts/sendtime.py`가 담당한다. 이 문서는 **무엇을 어떻게 쓰느냐**만 다룬다.

## 목차

| 절 | 내용 | 언제 읽나 |
|---|---|---|
| §1 | 채널 레지스터 — 이메일 vs 왓츠앱, 왓츠앱 차단 위험 | 채널을 정할 때 |
| §2 | 메시지 구조, 개인화 사다리 | 매번 |
| §3.1 | Merry Christmas / Happy Holidays / Season's Greetings 선택 | 연말 |
| §3.2 | 축하일 vs 추모일 — "Happy ___" 오류 | **매번, 가장 중요** |
| §3.3 | 타 종교 인사를 보내도 되는가 | 이드·디왈리·부활절 |
| §3.4 | 라마단 — 인사와 업무 템포 | 무슬림권 |
| §3.5 | 숫자·색·사물 금기 | 이미지나 숫자를 쓸 때 |
| §3.6 | 이름·직함·경칭 — 가장 효과가 큰 한 수 | **매번** |
| §3.7 | 타이밍 | 발송 계획 |
| §4 | 훔칠 만한 문형 15개 | 초안이 막힐 때 |
| §5 | 안티패턴 — 대량발송 티가 나는 문장들 | **쓰고 나서 점검** |

> 시간대별 실제 발송 시각은 §3.7이 아니라 `scripts/sendtime.py`가 계산한다.
> §3.7은 "며칠 전에 보내느냐"의 원칙만 다룬다.

---

---

## 1. Channel register: email vs WhatsApp

The two channels are not the same message in two boxes. They are two different registers.

| | Email | WhatsApp |
|---|---|---|
| Length | 60–120 words; 3–5 short lines of body | 25–60 words; 2–4 lines, no scrolling |
| Salutation | Full honorific + name ("Dear Mr. Al-Harbi,") | Short ("Hello Mr. Al-Harbi," / "Ahmet Bey,") |
| Sign-off | Full block: name, title, company, one contact line | First name + company only; signature block looks robotic |
| Emoji | None, or at most one at the very end | Zero to one, and only with an established contact |
| Subject line | Required; name the occasion + the relationship | N/A — the first line *is* the subject |
| Attachments | Optional, and usually a mistake (see §2) | Never a PDF; at most one image, and only if it is genuinely yours |
| Reply expected | No. Say nothing that demands one | No. A thumbs-up or a one-word reply is a full success |
| Best send window | Business hours, recipient's local time | Business hours, recipient's local time, **never** evening or a rest day |

### WhatsApp-specific rules (the part that can get a number banned)

WhatsApp is the highest-risk channel for a holiday campaign, because a holiday greeting sent to a
list is structurally identical to spam. Three separate mechanisms matter:

**The 24-hour customer service window.** When a customer messages your business, a 24-hour window
opens during which you can send free-form messages. Every new inbound message resets it. Once it
closes, business-initiated messages must use a pre-approved template ([Enchant](https://www.enchant.com/whatsapp-business-platform-24-hour-rule);
[smsmode](https://www.smsmode.com/en/whatsapp-business-api-customer-care-window-ou-templates-comment-les-utiliser/)).
Practical consequence: a partner who WhatsApped you yesterday about an order can receive a
free-form Eid greeting today. A contact you have not heard from in three months cannot — not on the
API, anyway.

**Template categories and approval.** Templates are classified Marketing, Utility, or Authentication,
and anything mixing utility with promotion is classified Marketing. Templates need Meta approval
(up to ~24 hours) before use. A holiday greeting with no transactional content is a Marketing
template. Meta monitors quality; if recipients block or report, the quality rating drops and Meta
may pause or disable the template ([SleekFlow](https://sleekflow.io/en-us/blog/whatsapp-business-template);
Enchant). Never trust a vendor claiming a way around the window — Enchant's warning is blunt:
promises of a workaround "will likely get your account blocked."

**Opt-in and consent.** Template messages are available only to contacts who have opted in.
WhatsApp etiquette guidance for B2B is consistent: get consent before messaging a client or partner
on WhatsApp at all, and ask what timeframes are acceptable
([Business Numbers Direct](https://businessnumbersdirect.com/best-practices-for-whatsapp-business-messaging-etiquette/)).

**Broadcast list vs 1:1.** Broadcast lists deliver as private 1:1 chats — recipients don't see each
other, and replies come back privately. But every message in a broadcast list is byte-identical:
you cannot insert a first name or a machine model ([EngageLab](https://www.engagelab.com/blog/whatsapp-broadcast-message)).
That is exactly the personalization the greeting depends on. Broadcast lists on the consumer
Business app also cap at 256 contacts.

> **Working rule for this business.** Keep WhatsApp holiday greetings 1:1 and hand-sent, to contacts
> who already message you on WhatsApp, during their working hours. Use email for anyone else. If
> the contact list grows past what one person can send by hand, that is an argument for the Business
> API with approved templates and recorded opt-in — not for a broadcast list.

### Register in practice

Same occasion, two channels:

- **Email body:** "Eid Mubarak to you and your family. We are grateful for a year of working with
  Al-Rashid Trading — the Riyadh project your team delivered in March was a highlight for us.
  Wishing you a peaceful and blessed Eid."
- **WhatsApp:** "Eid Mubarak, Eng. Faisal. Wishing you and your family a blessed Eid. — Minjun"

Both work. Neither is the other one trimmed or padded.

---

## 2. Structure of a greeting that lands

### The shape

1. **Named salutation with the correct honorific.** (§3.6 — the single highest-leverage move.)
2. **The occasion, stated plainly**, in the right emotional key (§3.2).
3. **One specific, verifiable detail from the shared year.** This is the whole message. A named
   project, a machine model, a site visit, a trade show booth, a shipment that went out on time, a
   warranty case handled well.
4. **A forward-looking wish** — the year, the season, the family, health, safe work.
5. **Sign-off from a named human**, ideally the person the recipient actually deals with.

### Rules that repeat across sources

- **One to four sentences is the sweet spot.** Short and specific beats long and vague
  ([Gallery Collection](https://www.gallerycollection.com/blog/holiday-cards-and-tidbits/5-recommended-greetings-for-business-holiday-cards/)).
- **No ask, no pitch, no offer.** Appreciation guidance is unanimous: a thank-you should focus on
  gratitude, not marketing; don't fill it with promotions or discounts
  ([Designmodo](https://designmodo.com/customer-appreciation-emails/)). Greenvelope puts it as: don't
  use holiday cards as "the place where you push a hard sell." A greeting with a price list attached
  is a price list.
- **No attachments.** A PDF catalogue, a "2026 promotion" flyer, or a branded JPEG card converts the
  greeting into a campaign. The one defensible exception: a genuine photo of your own team or
  factory, sent once, on a real relationship.
- **Sign it from the account manager, not the CEO.** A message from someone the client actually
  works with feels more meaningful than one from an executive they have never met (Greenvelope).
  For the top handful of accounts, escalate the *channel* instead — a phone call or a handwritten
  note outperforms any email.
- **Mention business only as memory, never as agenda.** "The project we launched in March still
  fills our team with pride" is the model — it is business, but it is *past* business, offered as
  gratitude. Compare: "looking forward to your Q1 order."
- **Lead with the relationship, then pivot to the wish.** Guidance on Lunar New Year emails is
  transferable: open by acknowledging the shared connection before the seasonal wish, which
  "grounds the greeting in reciprocity, not ritual" ([Alibaba](https://www.alibaba.com/product-insights/how-to-wish-chinese-new-year-in-email-complete-guide.html)).

### The personalization ladder (cheapest to strongest)

1. Correct name and honorific (mandatory — not optional personalization)
2. Company name in the body
3. Something concrete they bought, received or shipped — a product, an order, a delivered scope
4. A named site, city, or project
5. A shared physical event — an office or site visit, a trade-show booth, a conference, a dinner
6. A named person on their side other than the recipient (a service manager, a son who has joined
   the business)

Levels 4–6 are what make a message unforgeable by a mail-merge. If you cannot reach level 3 for a
given contact, consider whether that contact should get a greeting at all this cycle.

---

## 3. Cross-cultural landmines

### 3.1 "Merry Christmas" vs "Happy Holidays" vs "Season's Greetings"

The decision is driven by **audience width**, not politics.

- **"Merry Christmas"** — for contacts you personally know celebrate Christmas. Strong and warm
  when correct; a category error when not. Note that in Latin America, the Philippines, Poland,
  Italy, Spain and much of Africa, Christmas is culturally enormous and "Happy Holidays" reads as
  oddly cold and American. Use the local form where you can: *Feliz Navidad*, *Feliz Natal*,
  *Buon Natale*, *Wesołych Świąt*.
- **"Season's Greetings" / "Happy Holidays"** — for wide mailings and for mixed or unknown
  audiences. The standard advice: unless you know for certain every recipient celebrates Christmas,
  a broader greeting shows respect ([Gallery Collection](https://www.gallerycollection.com/blog/corporate-greeting-cards/merry-christmas-happy-holidays-write-business-christmas-cards/)).
  Caveat: "Happy Holidays" is a distinctly North American construction and can land as filler
  elsewhere.
- **"Wishing you a wonderful year ahead" / a New Year message** — the genuinely universal option,
  and the recommended house default for a mixed contact list. Greenvelope makes the same suggestion
  directly: when the religious question feels complicated, send a New Year card instead, which
  looks forward rather than assuming a shared observance. A January 1 / New Year greeting is
  received without friction almost everywhere, including Gulf and East Asian markets.
- **Do not send Christmas greetings** to contacts you know to be Jehovah's Witnesses, or into
  markets where Christmas has no purchase, unless you have a reason
  ([Diversity Resources](https://www.diversityresources.com/holiday-greetings-across-cultures/)).

**Note on the Gregorian vs local new year.** Many key markets run a different new year: Lunar New
Year (China, Vietnam's Tết, Korea's Seollal), Nowruz (Iran, Central Asia, Kurdish regions, ~Mar 20),
Hijri New Year, Thai Songkran (April), Ethiopian Enkutatash (September). "Lunar New Year" is the
inclusive label when the audience spans Chinese, Korean and Vietnamese contacts; "Chinese New Year"
is correct only when the recipient is Chinese.

### 3.2 Solemn vs celebratory: the "Happy ___" error

Attaching "Happy" to a day of mourning or atonement is the single most common and most damaging
mistake a foreign sender makes. It reads as ignorance at best.

| Occasion | Not this | This instead |
|---|---|---|
| Memorial Day (US, last Mon of May) | "Happy Memorial Day" | "Wishing you a meaningful Memorial Day" / say nothing at all |
| Veterans Day (US, Nov 11) | — | "Happy Veterans Day" **is** correct; thanking for service is encouraged |
| ANZAC Day (AU/NZ, Apr 25) | "Happy ANZAC Day" | "Remembering with you on ANZAC Day" / "Lest we forget" |
| Remembrance Day (UK/CA, Nov 11) | "Happy…" | "Thinking of you on Remembrance Day" |
| Yom Kippur | "Happy Yom Kippur" | *G'mar chatima tova* ("a good final sealing") or *tzom kal* ("easy fast"); "wishing you a meaningful fast" |
| Rosh Hashanah | — | *Shana tova* / *L'shana tova* — this one **is** celebratory |
| Ashura / Muharram | "Happy Muharram" | "Wishing you peace and reflection this Muharram" — or, safer, nothing |
| Ramadan | "Happy Ramadan" (not wrong, but foreign) | *Ramadan Kareem* or *Ramadan Mubarak* |
| Good Friday | "Happy Good Friday" | "Wishing you a blessed Easter" — send on Easter Sunday instead |
| Day of the Dead / All Souls | festive framing | acknowledge rather than congratulate |
| Holocaust Remembrance, Nakba Day, national disaster anniversaries | any greeting | **send nothing** |

Sources: [KTLA](https://ktla.com/news/heres-why-you-shouldnt-say-happy-memorial-day-and-what-you-should-say-instead/),
[Code of Support](https://www.codeofsupport.org/news-feed/why-you-dont-say-happy-memorial-day/),
[My Jewish Learning](https://www.myjewishlearning.com/article/how-to-greet-someone-on-yom-kippur/),
[Reform Judaism](https://reformjudaism.org/learning/answers-jewish-questions/what-greetings-are-appropriate-rosh-hashanah-and-yom-kippur),
Diversity Resources.

**The test:** *does this day commemorate a loss?* If yes, the register is respect, not celebration —
the vocabulary is "meaningful," "remembrance," "reflection," "peace," not "happy," "enjoy,"
"celebrate." My Jewish Learning states it plainly for Yom Kippur: it is not standard to wish
someone a happy one, but it is fine to wish them a meaningful one.

**Ambiguous cases — check before sending.** Some national days are celebratory (Saudi National Day
Sep 23, UAE National Day Dec 2, Indonesian Independence Day Aug 17) and greetings are welcome.
Others commemorate a war or a partition and are handled quietly. When in doubt on a national day,
the safe form is congratulatory-but-restrained: "Warm wishes to you and your colleagues on [Country]
National Day." Avoid political commentary, maps, flags of disputed territory, and anything touching
a border dispute.

### 3.3 Religious greetings from a non-co-religionist

**Verdict: welcomed, when sincere and correctly used.** A non-Muslim company saying "Eid Mubarak" to a
Saudi or Indonesian partner is a plus, not an intrusion. Etiquette guidance is consistent that it is
not rude and is read as a gesture of respect and goodwill; sincerity matters more than perfect
pronunciation ([Muslim Culture Hub](https://muslimculturehub.com/can-i-say-eid-mubarak-as-a-non-muslim/);
[Yulys](https://yulys.com/blog/how-to-wish-someone-happy-eid)). The same holds for Diwali: guidance
for corporate senders is that it is appropriate to send Diwali wishes to international clients even
when the sender doesn't celebrate, as a gesture of goodwill
([SmartSMS](https://smartsmssolutions.com/resources/blog/events/corporate-diwali-greetings-us)).

Constraints that keep it welcome:

- **Greet, don't perform.** Say the greeting; don't quote scripture, don't invoke God on the
  recipient's behalf beyond the standard formula, don't explain the holiday back to them.
- **Keep the religious content light.** Diwali guidance: keep wishes secular, focused on light,
  happiness and prosperity rather than theology (SmartSMS).
- **Get the formula right, and stop there.** *Eid Mubarak*. *Ramadan Kareem*. *Shana tova*.
  *Shubh Deepavali* / *Happy Diwali*. *Gong Xi Fa Cai* / *Chúc Mừng Năm Mới*. One phrase,
  transliterated correctly, then English.
- **Don't guess a person's religion from their country.** Indonesia, India, Lebanon, Nigeria,
  Malaysia and Egypt are all religiously mixed. If you don't know, a national-day or new-year
  greeting carries no risk where a religious one does.
- **Avoid lumping.** Folding Diwali into a generic "Happy Holidays" is called out specifically as
  a way to damage the relationship (SmartSMS). The same is true of Eid.

### 3.4 Ramadan: greeting, tempo, and Eid

**At the start of Ramadan:** *Ramadan Kareem* or *Ramadan Mubarak* — both are standard, both mean
roughly "a generous / blessed Ramadan," and both are appropriate in email and at the top of a
meeting ([Gulf News](https://gulfnews.com/lifestyle/ramadan-etiquette-guide-respectful-phrases-to-use-and-what-not-to-say-1.500440544);
[Gulf Business](https://gulfbusiness.com/ramadan-etiquette-uae-cultural-workplace-guide/)). If
someone says *Ramadan Kareem* to you, the traditional reply is *Allahu Akram*.

**At the end:** *Eid Mubarak*, for Eid al-Fitr. Note Eid al-Adha (~70 days later) takes the same
greeting and is the larger holiday in some markets.

**Business tempo during the month — this matters more than the greeting:**

- Working hours shorten. UAE public sector runs roughly 9:00–14:30; private sector typically works
  two hours less per day. Saudi offices commonly shift to a ~10:00 start (Gulf Business;
  [Dq Living](https://dqliving.com/workplace-etiquette-during-ramadan-in-saudi-arabia/)).
- Schedule meetings and calls **mid-morning to mid-afternoon**; avoid the hours before iftar
  entirely — that time belongs to family
  ([Commisceo Global](https://www.commisceo-global.com/blog/doing-business-in-muslim-countries-during-ramadan)).
- Decisions slow. Don't read a slow reply as disinterest, and don't chase.
- Don't reference food, coffee, lunch meetings, or how hard the fasting must be. Gulf News lists
  these explicitly among what not to say.
- The last ten days and the Eid week itself are effectively out of office. Plan shipments,
  approvals and quotations around it — a supplier who anticipates this without being told earns
  more credit than any greeting.

**Practical pattern for this business:** send *Ramadan Kareem* at the start (day 1–2), go quiet
operationally, send *Eid Mubarak* on the first day of Eid. Two touches, a month apart, both short.

### 3.5 Number, color and object taboos that carry into text

These are gift and design taboos, but they leak into written wishes, e-card design, subject lines,
promotional numbering and anything visual you attach.

- **The number 4** — avoided across China, Korea, Japan and Vietnam because it sounds like "death"
  ([Tetraphobia, Wikipedia](https://en.wikipedia.org/wiki/Tetraphobia);
  [Etiquette in South Korea](https://en.wikipedia.org/wiki/Etiquette_in_South_Korea)). Don't build
  a "4 reasons" holiday mail, a set of 4, a "4% off," or a 4-item list for East Asian markets.
  **8 and 6 are lucky**; 9 is positive in China; 88 is excellent.
- **13** — avoided in much of Europe and the Americas. **17** is the unlucky one in Italy.
- **Clocks and watches to Chinese recipients** — "giving a clock" (送钟) is homophonous with
  "attending a funeral" (送终) ([DigMandarin](https://www.digmandarin.com/chinese-taboos-gifts.html)).
  Never a clock, never a countdown-clock graphic as a Lunar New Year visual.
- **White and black** — funeral colors across East Asia; white flowers, white wrapping, white-on-
  black card design read as mourning. **Red and gold** are the correct festive palette for Chinese
  and Vietnamese New Year.
- **Chrysanthemums** — funeral flowers in China, Japan, Korea and much of Europe (France, Italy,
  Poland, Belgium). Never in a card image.
- **Lilies and white carnations** — funerals in several European markets.
- **Also avoid:** sharp objects in imagery (knives, blades — "cutting the relationship"), umbrellas in Chinese contexts (散 sǎn, "to part"), green hats
  to Chinese men, handkerchiefs (tears), alcohol into Gulf and Muslim-majority markets, anything
  leather to Hindu contacts, anything pork- or dog-related to Muslim and Jewish contacts.
- **Left hand / soles of feet** in imagery for Middle Eastern and South Asian audiences.

### 3.6 Names, titles and honorifics — the highest-leverage move

Getting the honorific right signals that a real person wrote this. Getting it wrong signals a
database. In many of these markets, dropping a title too early is read as
disrespect, not friendliness.

| Market | Form | Notes |
|---|---|---|
| **Gulf (SA, UAE, Qatar, Kuwait, Oman)** | Title + **first** name | "Eng. Fahad," "Dr. Al-Rashid," "Mr. Ahmed." Engineering and academic titles are used actively — **"Eng." / "Engineer"** is standard and used far more actively than in the West. Wait to be invited to first-name-only; it rarely happens early ([Bridge-Connect](https://www.bridge-connect.com/post/business-etiquette-saudi-arabia-practical-guide-visitors-and-investors); [Creative Zone](https://www.creativezone.ae/saudi-arabia-business-etiquette-guide-for-expat-business-owners/)) |
| **Gulf — Sheikh / Hajji** | Use with care | *Sheikh/Sheikha* for rulers and religious figures. *Hajji/Hajjah* honors someone who has performed Hajj — respectful in some contexts, over-familiar in others. Guidance: use sparingly, and only if the person uses it themselves ([Hisar Travel](https://hisartravel.sg/arabic-honorifics-in-saudi-address-people-politely/)) |
| **Turkey** | **First name + Bey / Hanım** | "Ahmet Bey," "Ayşe Hanım." Never surname + Bey. Stacks with titles: *Doktor Bey*, *Müdür Bey*. Calling a Turkish counterpart by bare first name in a formal setting is rare ([HandsOnTurkish](https://turkishonline.eu/greeting-colleague-turkey/); [Easy Turkish Grammar](https://www.easyturkishgrammar.com/post/forms-of-address-in-turkish)) |
| **Indonesia** | **Pak / Bapak + first name**, **Bu / Ibu + first name** | "Pak Joko," "Bu Sari." Never with the surname. Addressing an older person with no form of address is considered quite offensive ([Bahasa.fun](https://bahasa.fun/blog/indonesian-forms-of-address); [Cultural Atlas](https://culturalatlas.sbs.com.au/indonesian-culture/indonesian-culture-naming)) |
| **Vietnam** | **Anh / Chị + given name** | Vietnamese names run Family–Middle–Given; the title attaches to the **given** name, the last element. Nguyễn Ngọc Minh → "Anh Minh." *Anh* male, *Chị* female, roughly "older brother/sister." Unless you are clearly senior, Anh/Chị is the safe default ([Preply](https://preply.com/en/blog/vietnamese-titles/); [Kathryn Read](https://kathrynread.com/business-etiquette-in-vietnam-some-do-and-donts-in-vietnam-business/)) |
| **Latin America** | **Ing. / Lic. / Dr. + name**; *Don/Doña* + first name | *Ingeniero/a* for engineers — near-universal in technical and industrial roles in Mexico, Colombia, Peru. *Licenciado/a* for other degree holders. *Don/Doña* honors age and standing, first name only. Dropping the title early reads as disrespectful in Mexico and Colombia ([Na'atik](https://naatikmexico.org/blog/the-use-of-personal-and-business-titles-in-mexico); [italki](https://www.italki.com/en/blog/spanish-titles)) |
| **Germany / Austria / Switzerland** | **Herr / Frau + (Dr. / Prof.) + surname** | The doctorate is effectively part of the legal name; omitting it is read as disrespect. "Sehr geehrter Herr Dr. Müller." Never Herr + first name. Formal *Sie* until explicitly invited otherwise ([Chillistore](https://www.chillistore.com/blog/german-business-correspondence-dont-mix-up-your-du-and-sie/)) |
| **Japan** | **Surname + -san** | Never first name. "Tanaka-san." *-sama* in very formal writing; never *-san* about yourself |
| **Korea (inbound)** | Title + 님 / position title | Surname + position ("김 사장님") rather than given name |
| **China** | Surname + title | "Manager Wang / Wang Jingli," "Director Li." Family name comes first |
| **Thailand** | **Khun + first name** | Gender-neutral. "Khun Somchai" |
| **India** | Mr./Ms. + surname; "Sir" is common | "Sir" from a counterpart is normal courtesy, not deference |
| **Nordics, NL, AU, NZ** | First name, quickly | Over-formality reads as stiff or distant here |

**Operational rules**

1. **Copy the signature block.** How a person signs their own email is the authoritative answer.
   If they sign "Eng. Faisal Al-Otaibi," address them as Eng. Faisal.
2. **Copy their salutation to you.** If they open "Dear Mr. Kim," match the level.
3. **Match the language of the name.** Don't anglicize: Ayşe not Ayse, Nguyễn not Nguyen, Müller
   not Mueller, if you can render the diacritics reliably.
4. **When you genuinely don't know, address the company, not a wrong title.** "Dear colleagues at
   Al-Rashid Trading" is safer than "Dear Mr. Al-Rashid" when Al-Rashid is a company name.
5. **Never "Dear Valued Partner," "Dear Sir/Madam," "Dear Customer," or "Dear [FirstName]".** These
   announce a mail merge.
6. **Female recipients:** Ms. unless she signs otherwise. Do not assume a married name. In Spanish-
   speaking markets women keep their own surnames; in Korea, a wife does not take her husband's.

### 3.7 Timing

- **Fixed-date holidays (Christmas, New Year, national days):** arrive **on the morning of the day**,
  local time, or 1–2 days before. For wide December mailings, business-card guidance converges on
  **December 1–10** so the message arrives before inboxes fill with out-of-office replies
  ([Red Paper Plane](https://www.redpaperplane.com/blog-post/when-should-businesses-send-holiday-cards.html);
  [Greenvelope](https://www.greenvelope.com/resources/when-to-send-holiday-cards)). Digital removes
  the print lead-time excuse — schedule for the moment you want.
- **Lunar New Year:** **3–5 days before** the holiday, not during it — recipients have already left
  for their hometowns and factories are shut (Alibaba). Reaching into the holiday week is a miss.
- **Ramadan:** day 1–2. **Eid:** the morning of Eid day 1 (confirm the date — it is moon-sighted and
  can shift by a day between countries; Saudi and Indonesia may differ).
- **Never late.** A greeting that arrives after the holiday reads worse than no greeting; it says
  you noticed only when you saw it on someone else's out-of-office.
- **Time zone is the whole point.** A message timestamped 03:40 local proves it was a scheduled
  blast. Send into the recipient's 09:00–11:00 window. Korea is UTC+9: a 09:00 Riyadh arrival is
  15:00 Korean time; a 09:00 São Paulo arrival is 21:00 Korean time. `scripts/sendtime.py` does this
  arithmetic for any sender time zone (`--home`). Use scheduled send.
- **Never send on the recipient's rest day** unless the holiday itself falls there. Friday is the
  rest/prayer day across the Gulf; Friday–Saturday is the weekend in Saudi, the UAE, Egypt and much
  of the region. Israel: Friday evening–Saturday.
- **Cadence discipline.** Two to four greetings per contact per year. More than that and each one
  costs you rather than earns.

---

## 4. Formulas and openers worth stealing

Quoted briefly with attribution — take the **pattern**, then rewrite in your own voice with a real
specific detail. Copying these verbatim reproduces the exact genericness you are trying to escape.

**Specificity as the engine**

1. "The project we launched in March still fills our team with pride" — held up as far more powerful
   than a vague thank you ([Quo](https://www.quo.com/blog/holiday-text-messages/)). *Pattern: name the
   month and the thing.*
2. "It's been a pleasure collaborating with your team this year" — recommended as the **opener**,
   before the seasonal wish, to ground the greeting in reciprocity (Alibaba). *Pattern: relationship
   first, occasion second.*
3. "Let them know this isn't a mass message" — stated as the actual objective of personalization
   (Quo). *Pattern: treat it as a test the message must pass.*

**Gratitude without a pitch**

4. "We truly wouldn't be where we are without them" — the tone of sincere client gratitude, and
   Greenvelope's accompanying point is that you shouldn't feel obliged to pair it with an offer.
5. "Your clients might not be the reason for the season, but they are the reason for your success"
   (Greenvelope). *Pattern: a light turn of phrase that makes gratitude concrete.*
6. "Thank you for your trust and continued partnership" — standard Diwali corporate close
   (SmartSMS). Workmanlike; safe in almost any market as the final line.

**Occasion-correct formulas**

7. *Ramadan Kareem* / *Ramadan Mubarak* — "wishing someone a blessed or generous Ramadan"
   (Gulf News). Reply to receiving one: *Allahu Akram*.
8. *Eid Mubarak* — "wishing someone a blessed celebration at Ramadan's end" (Gulf News).
9. "Eid Mubarak to our team members observing Eid" — the inclusive construction for a mixed
   audience, when you can't be sure who observes (Yulys). *Pattern: "to those celebrating."*
10. *G'mar chatima tova* ("a good final sealing") or *tzom kal* ("easy fast") — Yom Kippur
    (My Jewish Learning; Chabad).
11. "Wishing you peace and reflection this Muharram" — the non-celebratory construction for a
    mourning observance (Ashura guidance, per §3.2 sources).
12. "Have a meaningful Memorial Day" — the recommended replacement for "Happy" (KTLA).
13. *Gong Xi Fa Cai* (恭喜发财, "wishing you prosperity") and *Wan Shi Ru Yi* (万事如意, "may all
    your wishes come true") — Lunar New Year, with the warning that wrong characters or
    mispronunciation cause confusion or offense (Alibaba; JustLogin).
14. "Season's Greetings" and "Peace on Earth, Goodwill Toward Men" — the standard non-denominational
    December options (Greenvelope).
15. "Wishing you and your family a joyous and prosperous Diwali" — secular framing around light and
    prosperity rather than theology (SmartSMS).

**Register anchors**

16. "Hope your fast is going well" / "I admire your dedication" — the supportive-but-not-intrusive
    register during Ramadan (Gulf News). *Pattern: support the person, don't interrogate the practice.*
17. "Wishing you a wonderful year ahead" — the universal fallback. No religion, no assumption, works
    in every market on the list, correct at New Year and usable as a closing line on almost any
    occasion.

---

## 5. Anti-patterns — how a greeting announces it was mass-produced

### Dead phrases

Retire on sight: "As we reflect on the year that has passed." "Our thriving partnership." "Dear
Valued Partner / Valued Customer / Esteemed Client." "We look forward to continued success
together." "In today's fast-paced world." "Your continued support means the world to us." "As the
year draws to a close." "Wishing you joy, peace, and prosperity in the coming year" (correct, and
so worn it is invisible). "It has been an honor to serve you." "Here's to another year of growth
and success."

The general AI-writing tells apply directly: "delve," "leverage" as a verb, "utilize," "in the
ever-evolving landscape of," "it is important to note that," "cutting-edge," "innovative," and
faux-conversational bridges like "Here's the thing…" or "At the end of the day…"
([Grammarly](https://www.grammarly.com/blog/ai/common-ai-words/); [Async](https://async.com/blog/overused-ai-words/);
[AITextKit](https://aitextkit.com/blog/ai-words-and-phrases-that-give-you-away/)).

### Structural tells

- **The em-dash triplet** and perfectly balanced three-item lists ("joy, peace, and prosperity").
- **Uniform paragraph length.** Real people write one line, then four, then two.
- **The abstract-noun sandwich**: a sentence made entirely of partnership / trust / excellence /
  commitment / journey, with no object you could photograph.
- **"Not just X, but Y"** and "more than a supplier — a partner."
- **Exclamation stacking.** One exclamation mark in a business greeting, maximum. Zero is fine.
  Three is a flyer.
- **Emoji stacks** (🎉🎊✨🥳). In B2B email: none. In WhatsApp: at most one, only with someone you
  actually talk to, and never on a solemn occasion. Formal guidance says avoid emoji entirely on
  first contact and in formal messages ([Sobot](https://www.sobot.io/article/how-to-send-a-formal-message-on-whatsapp-etiquette-guide/)).
- **ALL CAPS holiday words**, animated GIFs, glitter cards, stock photography of a generic family
  by a fireplace.
- **The tacked-on ask.** Any sentence after the wish that contains "by the way," "also," a
  catalogue link, an order deadline, or a price. It retroactively converts the whole message into
  a sales email.
- **A signature longer than the message** — six lines of legal disclaimer under a 30-word wish.
- **Timestamp evidence**: identical send time across a whole list, or 03:00 local delivery.
- **No specific noun anywhere.** The reliable test: **if you could send this exact message to any
  of your contacts without changing a word, it is not a greeting — it is a broadcast.**

### The three-question pre-send check

1. **Is the occasion celebratory or solemn?** Does the verb match?
2. **Is the name and honorific right, and would the recipient recognize the specific detail I
   named?**
3. **Is there anything in here that asks for something?** If yes, cut it and send it separately in
   February.

---

## Sources

**WhatsApp Business / channel rules**
- https://www.enchant.com/whatsapp-business-platform-24-hour-rule
- https://sleekflow.io/en-us/blog/whatsapp-business-template
- https://www.smsmode.com/en/whatsapp-business-api-customer-care-window-ou-templates-comment-les-utiliser/
- https://respond.io/help/whatsapp/whatsapp-message-templates
- https://www.engagelab.com/blog/whatsapp-broadcast-message
- https://respond.io/blog/whatsapp-broadcast
- https://businessnumbersdirect.com/best-practices-for-whatsapp-business-messaging-etiquette/
- https://www.sobot.io/article/how-to-send-a-formal-message-on-whatsapp-etiquette-guide/
- https://devrix.com/tutorial/whatsapp-b2b/
- https://www.accountex.co.uk/insight/2024/08/29/navigating-corporate-messaging-best-practices-and-whatsapp-etiquette-for-work/

**Greeting structure, personalization, timing**
- https://www.greenvelope.com/blog/holiday-message-to-clients/
- https://www.greenvelope.com/resources/when-to-send-holiday-cards
- https://www.quo.com/blog/holiday-text-messages/
- https://www.gallerycollection.com/blog/holiday-cards-and-tidbits/5-recommended-greetings-for-business-holiday-cards/
- https://www.gallerycollection.com/blog/corporate-greeting-cards/merry-christmas-happy-holidays-write-business-christmas-cards/
- https://www.redpaperplane.com/blog-post/when-should-businesses-send-holiday-cards.html
- https://designmodo.com/customer-appreciation-emails/
- https://bigideasforsmallbusiness.com/holiday-etiquette-for-business-greetings/

**Cross-cultural greetings, religion, solemn occasions**
- https://www.diversityresources.com/holiday-greetings-across-cultures/
- https://ktla.com/news/heres-why-you-shouldnt-say-happy-memorial-day-and-what-you-should-say-instead/
- https://www.codeofsupport.org/news-feed/why-you-dont-say-happy-memorial-day/
- https://www.myjewishlearning.com/article/how-to-greet-someone-on-yom-kippur/
- https://reformjudaism.org/learning/answers-jewish-questions/what-greetings-are-appropriate-rosh-hashanah-and-yom-kippur
- https://www.chabad.org/library/article_cdo/aid/5254206/jewish/What-Does-GMar-Chatima-Tova-Mean.htm
- https://muslimculturehub.com/can-i-say-eid-mubarak-as-a-non-muslim/
- https://yulys.com/blog/how-to-wish-someone-happy-eid
- https://gulfnews.com/lifestyle/ramadan-etiquette-guide-respectful-phrases-to-use-and-what-not-to-say-1.500440544
- https://gulfbusiness.com/ramadan-etiquette-uae-cultural-workplace-guide/
- https://dqliving.com/workplace-etiquette-during-ramadan-in-saudi-arabia/
- https://www.commisceo-global.com/blog/doing-business-in-muslim-countries-during-ramadan
- https://smartsmssolutions.com/resources/blog/events/corporate-diwali-greetings-us
- https://www.alibaba.com/product-insights/how-to-wish-chinese-new-year-in-email-complete-guide.html
- https://justlogin.com/blog/chinese-new-year-greetings/

**Numbers, colors, gift taboos**
- https://en.wikipedia.org/wiki/Tetraphobia
- https://en.wikipedia.org/wiki/Etiquette_in_South_Korea
- https://www.digmandarin.com/chinese-taboos-gifts.html
- https://www.mandarinzone.com/chinese-gift-giving-taboos/
- https://bloomboxhk.com/en/blog/2025/12/14/cultural-guide-flowers-to-avoid-around-the-world/
- https://acec-association.org/the-dos-and-donts-of-gift-giving-around-the-world/

**Names, titles, honorifics**
- https://www.bridge-connect.com/post/business-etiquette-saudi-arabia-practical-guide-visitors-and-investors
- https://www.creativezone.ae/saudi-arabia-business-etiquette-guide-for-expat-business-owners/
- https://hisartravel.sg/arabic-honorifics-in-saudi-address-people-politely/
- https://turkishonline.eu/greeting-colleague-turkey/
- https://www.easyturkishgrammar.com/post/forms-of-address-in-turkish
- https://bahasa.fun/blog/indonesian-forms-of-address
- https://culturalatlas.sbs.com.au/indonesian-culture/indonesian-culture-naming
- https://preply.com/en/blog/vietnamese-titles/
- https://kathrynread.com/business-etiquette-in-vietnam-some-do-and-donts-in-vietnam-business/
- https://culturalatlas.sbs.com.au/vietnamese-culture/vietnamese-culture-naming
- https://naatikmexico.org/blog/the-use-of-personal-and-business-titles-in-mexico
- https://www.italki.com/en/blog/spanish-titles
- https://www.mexperience.com/this-title-is-better-than-no-title/
- https://www.chillistore.com/blog/german-business-correspondence-dont-mix-up-your-du-and-sie/
- https://www.businessemailetiquette.com/cultural-business-email-etiquette/

**AI-tell / cliché detection**
- https://www.grammarly.com/blog/ai/common-ai-words/
- https://async.com/blog/overused-ai-words/
- https://aitextkit.com/blog/ai-words-and-phrases-that-give-you-away/
- https://humanaizer.io/blog/ai-writing-clichs-to-avoid-and-what-to-write-instead
