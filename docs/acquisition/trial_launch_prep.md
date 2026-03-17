# Acquisition Trial Launch Prep

**Purpose:** Everything needed to launch a first controlled paid acquisition trial the day the web goes live.
**Last updated:** 2026-03-16

---

## 1. First channel

**Meta Ads (Facebook / Instagram).**

Why Meta first:
- Visual product (boats) — image-driven ads perform well
- Geo-targeting by coastal areas and marinas
- Lead generation objective available (can send to external landing)
- Lowest setup friction for first test
- No SEO wait, no Google Ads learning curve

Do NOT run Google Ads, organic social, or referral programs until Meta Ads has produced at least 15 leads with recorded outcomes.

---

## 2. Landing

**Use the existing landing at `/vender/`** (`static/site/vender/index.html`).

- Form already built with all required fields
- Posts to `POST /api/leads/webhook/landing-barcos-venta`
- Honeypot anti-bot already in place
- Dedup already handled (409 shown as success to user)
- Mobile-ready (font-size >= 16px, responsive)
- Success message: "Solicitud recibida. Le contactaremos en 24-48 horas"

Do NOT build a new landing. Do NOT modify the existing one for the first trial.

---

## 3. Source naming map

| Traffic origin | Source string (auto-generated) | How it happens |
|---|---|---|
| Meta Ads → `/vender/` landing form | `webhook:landing-barcos-venta` | Form POSTs to `/api/leads/webhook/landing-barcos-venta` — source auto-assigned |
| Manual test leads via API | `trial:manual-test` | Operator sends via `POST /leads/external` with explicit source |

**For the first trial, there is only one real source: `webhook:landing-barcos-venta`.**

The landing form auto-generates the source. The operator does not need to configure anything. All Meta Ads traffic that reaches the landing and submits the form will appear under this source in `source-intelligence`.

If a second landing or a second ad destination is added later, it gets its own source (e.g., `webhook:landing-barcos-compra`). Do not reuse the same source for different landings.

---

## 4. Ad copy variants

### Meta Ads format constraints

| Element | Max chars | Notes |
|---|---|---|
| Primary text (body) | 125 visible (more truncated) | First 2 lines matter most |
| Headline | 40 | Shown below image |
| Description | 30 | Optional, shown in some placements |
| CTA button | Fixed options | Use "Mas informacion" or "Contactar" |

### Variant A — Direct seller value

```
Primary text:
Vende tu barco con respaldo profesional.
Mas de 50 anos de experiencia en Puerto Deportivo del Masnou.
Valoracion sin compromiso.

Headline:
Vende tu barco sin complicaciones

Description:
Gestion integral de la venta

CTA: Mas informacion
```

### Variant B — Urgency + network

```
Primary text:
Tu barco merece una venta a la altura de su valor.
Red de compradores activa en el sur de Europa.
Te contactamos en 24-48h.

Headline:
Venda su embarcacion con profesionales

Description:
+1.000 embarcaciones gestionadas

CTA: Contactar
```

### Variant C — Problem-first

```
Primary text:
Llevas meses intentando vender tu barco?
Dejalo en manos de profesionales con mas de 50 anos
en el Puerto Deportivo del Masnou.

Headline:
Gestion profesional de venta nautica

Description:
Valoracion gratuita y sin compromiso

CTA: Mas informacion
```

### Image requirements

- **Format:** 1080x1080 px (square) or 1200x628 px (landscape)
- **Content:** Real boat photos. Professional, well-lit, marina or sea background
- **Avoid:** Stock photos, text overlay > 20% of image, low-resolution images
- **Minimum for launch:** 2-3 real boat images

### First trial ad structure

| Element | Recommendation |
|---|---|
| Campaign objective | Traffic (send to landing) or Leads (if using instant forms — but prefer landing) |
| Ad sets | 1 ad set, broad coastal targeting |
| Ads per ad set | 2-3 variants (A, B, C above) — let Meta optimize |
| Daily budget | 5-15 EUR/day (enough for signal, not enough to waste) |
| Duration | 7-10 days minimum |
| Audience | Spain, coastal provinces (Barcelona, Tarragona, Girona, Baleares, Valencia, Alicante, Malaga) |
| Age | 35-65 |
| Interests | Nautica, navegacion, barcos, puertos deportivos, vela |
| Placements | Automatic (let Meta optimize across Facebook + Instagram) |

---

## 5. Pre-launch checklist

Run this checklist in order. Every item must be true before turning ads on.

### Infrastructure

- [ ] VPS is running and accessible
- [ ] `curl https://sentyacht.com/api/health` returns 200
- [ ] Home page loads at `https://sentyacht.com/`
- [ ] Landing loads at `https://sentyacht.com/vender/`
- [ ] HTTPS certificate is active (no browser warnings)
- [ ] Landing form submits successfully (test with a real email)
- [ ] Test lead appears in `GET /api/leads?source=webhook:landing-barcos-venta`
- [ ] Duplicate test: same email submitted twice — second returns success to user, only one lead in DB
- [ ] Honeypot test: filled hidden field — success shown but no lead created
- [ ] Mobile: landing loads and form submits correctly on phone

### Commercial

- [ ] Real phone number in home page header (tested: rings, someone answers or voicemail)
- [ ] Real email configured and monitored
- [ ] Operator identified: who reviews leads daily?
- [ ] Operator has read `docs/external_trial_runbook.md`
- [ ] Operator has the curl commands saved or bookmarked
- [ ] Contact commitment verified: leads will be contacted within 24-48h
- [ ] At least 2 real boat images ready for ads
- [ ] Meta Ads account active and payment method configured
- [ ] Ad copy variants loaded as drafts (not yet published)

### Go signal

- [ ] All infrastructure items checked
- [ ] All commercial items checked
- [ ] Daily backup cron running
- [ ] Operator confirms: "I am ready to review leads daily and contact within 48h"
- [ ] Ads published

---

## 6. First-week daily operating checklist

### Every morning (10 min)

```bash
# 1. Are we alive?
curl https://sentyacht.com/api/health

# 2. How many leads came in since yesterday?
curl "https://sentyacht.com/api/leads?source=webhook:landing-barcos-venta&limit=10"

# 3. Quick ops snapshot
curl https://sentyacht.com/api/internal/ops/snapshot

# 4. Daily actions — what needs attention?
curl https://sentyacht.com/api/internal/daily-actions
```

### For each new lead (5 min per lead)

```bash
# 1. Review the lead pack
curl https://sentyacht.com/api/leads/{id}/pack

# 2. Contact the lead (phone or email — within 48h)

# 3. Record the outcome
curl -X POST https://sentyacht.com/api/internal/outcomes \
  -H "Content-Type: application/json" \
  -d '{"lead_id": {id}, "outcome": "contacted", "reason": "Called, interested in valuation"}'
```

### Every evening (5 min)

```bash
# Check source intelligence — how is the source performing?
curl "https://sentyacht.com/api/internal/source-intelligence?source=webhook:landing-barcos-venta"
```

Check: `leads`, `outcomes`, `recommendation`, `rationale`.

### Meta Ads check (daily, in Ads Manager)

| Metric | Where to look | What matters |
|---|---|---|
| Spend | Campaign dashboard | Is it spending? (if 0, ad may be rejected or audience too narrow) |
| Impressions | Campaign dashboard | Are people seeing the ad? |
| Clicks | Campaign dashboard | Are people clicking? |
| CTR | Campaign dashboard | > 1% is acceptable for first test |
| Cost per click | Campaign dashboard | Note it, do not optimize yet |
| Link clicks → leads ratio | Compare clicks with new leads in API | If many clicks but few leads, landing has friction |

### Followup (when no_answer leads accumulate)

```bash
# Download followup CSV
curl -o followup.csv "https://sentyacht.com/api/internal/followup-automation/export.csv?source=webhook:landing-barcos-venta"
```

Then follow `docs/followup_csv_runbook.md`: open CSV, copy to/subject/body, send, record outcome.

---

## 7. Stop / continue criteria

### Continue the trial if (after 7 days or 10+ leads, whichever comes first)

- Leads are coming in (> 0 leads)
- At least some leads have real boat data in notes (not spam/junk)
- At least 1 lead has been contacted and responded (outcome: contacted, qualified, or won)
- Cost per lead < 15 EUR (acceptable for boat brokerage vertical)
- `source-intelligence` does not show `recommendation: "deprioritize"`

### Pause and investigate if

- 0 leads after 3+ days with active spend → check landing form, API health, ad approval
- > 50% of leads are spam or clearly fake → check honeypot, add exclusions in Meta Ads
- Cost per lead > 30 EUR → narrow targeting or test different copy
- All leads are `no_answer` after 5+ contacts → review contact timing and method
- `source-intelligence` shows `recommendation: "review"` with `rationale: "high no_answer rate"` → investigate responsiveness

### Stop the trial if

- 0 leads after 7 days with confirmed active spend → fundamental problem (ad rejected, audience wrong, landing broken)
- > 80% spam after 10+ leads → bot problem, need stronger protection
- Cost per lead > 50 EUR sustained → channel not viable for this vertical at this budget
- All outcomes are `bad_fit` or `lost` after 10+ leads → targeting is wrong or offer doesn't match audience

### When data is insufficient

- Fewer than 10 leads: do not make channel decisions. Keep running.
- Fewer than 5 recorded outcomes: do not trust source-intelligence recommendations. Keep recording.
- Fewer than 7 days: do not judge cost efficiency. Meta Ads needs time to optimize.

---

## 8. Known unknowns

### What this first trial CAN prove

- Whether Meta Ads produces leads that reach the landing and submit the form
- Whether the landing converts ad traffic into form submissions
- Whether the leads contain real boat data (not just spam)
- Whether the operator can contact leads within 48h and get responses
- Whether the intake → review → outcome → followup cycle works in practice
- Approximate cost per lead for this audience and copy
- Which ad variant gets more clicks (basic A/B signal)

### What this first trial CANNOT prove

- **Conversion to sale.** Boat sales take weeks/months. 7-10 days of ads will not close deals.
- **Optimal targeting.** First audience is broad and hypothesis-based. Real optimization requires volume.
- **Scoring accuracy.** Scoring is a placeholder (50/60). It does not differentiate lead quality.
- **Channel comparison.** Running only Meta Ads. Cannot say "Meta is better than Google" without testing both.
- **Copy optimization.** 2-3 variants with 10-30 leads total is not statistically significant. It gives direction, not proof.
- **Landing conversion rate.** Need 100+ clicks to measure conversion rate reliably. First trial may not reach this.
- **Long-term unit economics.** Cost per lead != cost per acquisition. Acquisition cost requires sale data.

### Assumptions that must be validated during trial

| Assumption | How to validate | Signal |
|---|---|---|
| Coastal boat owners use Facebook/Instagram | Leads come in at < 15 EUR CPL | Yes if leads arrive; no if 0 leads after 7 days |
| The form collects enough info for a first contact | Operator can call/email without asking "who are you?" | Check notes field of first 5 leads |
| 24-48h contact commitment is realistic | Operator actually contacts within window | Track time between lead creation and first outcome recording |
| Honeypot blocks bots effectively | Spam rate < 20% | Compare total form submissions vs real leads |
| One landing is enough for first test | Conversion rate is acceptable | Compare ad clicks to form submissions |

---

## 9. After the trial

After 7-10 days (or 15+ leads with outcomes recorded), run the assessment:

```bash
curl https://sentyacht.com/api/internal/source-intelligence
```

Answer these questions:
1. How many leads? (`leads`)
2. Cost per lead? (Meta Ads spend / leads)
3. How many contacted? (`outcomes.contacted + outcomes.qualified + outcomes.won`)
4. How many dead? (`outcomes.bad_fit + outcomes.lost`)
5. How many need followup? (`followup_candidates`)
6. What does the system recommend? (`recommendation` + `rationale`)
7. Is the data sufficient? (`data_sufficient`)

**Decision:**

| Result | Action |
|---|---|
| Recommendation "keep", CPL < 15 EUR, real boat leads | Scale: increase budget to 15-30 EUR/day, same setup |
| Recommendation "review", mixed signals | Extend trial 7 more days, same budget, record more outcomes |
| Recommendation "deprioritize", high CPL, spam or bad_fit | Stop Meta Ads. Investigate: wrong audience, wrong copy, or wrong channel |
| Too few leads for signal (< 10) | Extend trial, increase budget slightly (10-20 EUR/day) |
