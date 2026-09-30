# Planning Risk Radar

Will this proposed UK data centre get planning permission? A focused prototype for a Chief Risk
Officer, built for the Antler UK16 Wednesday sprint, 30 Sep 2026.

Read `spec.md` first. It records what was verified before anything was built.

## Run it

```bash
cp .env.example .env        # then put a real GEMINI_API_KEY in it
./run.sh                    # http://localhost:8099
```

`GEMINI_API_KEY` is the only credential. No GCP project, no gcloud, no Custom Search key. Nothing
is hardcoded; with no key the app renders a setup state and shows no findings at all.

## What it does

Five planning concerns (grid capacity, water use, environmental impact, community opposition,
planning policy). For each it runs live Google Search grounding, stores only sources whose link
resolves to a real publisher, and assesses impact and likelihood **separately**.

## The three rules that make it trustworthy

1. **Impact is a pure function of your project inputs.** Nothing found online moves it. Every rule
   that fired is printed on the risk detail screen.
2. **Likelihood counts only outcomes a human has confirmed.** A press report of a council decision
   is a *lead*, never a fact. Open the link, check the authority's page, record the outcome, and
   only then does it count. Below three confirmed decisions the band is `INSUFFICIENT EVIDENCE`,
   which is rendered differently from `LOW` and explicitly labelled as a gap to close.
3. **They are never multiplied into one score,** and article counts and tone are never turned into
   a probability of refusal.

## Tests

```bash
./venv/bin/python test_journey.py     # 16 assertions on the parts that must not lie
```

Including: five unconfirmed leads still yield insufficient evidence; a confirmed *news* item never
counts; an evidence gap on a high impact concern outranks a low likelihood; and "what changed"
reports having no prior review instead of inventing a trend.

## Known limits

- Grounding returns no publication date, so every source shows "published: not available".
- Source classification is URL based. It is deliberately conservative: a decision reported in the
  press is `reported_decision`, never `planning_decision`.
- Redirect URLs from grounding expire, so links are resolved once at retrieval and the resolved URL
  is stored.
- A review takes about 80 seconds because it runs five grounded searches serially.
