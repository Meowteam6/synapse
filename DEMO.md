# Stage demo — 3 minutes, hard stop

Everything below uses commands that already work. No new code paths on
stage. Terminal font size up before you plug in.

**Pre-flight, before you are called:**

```bash
cd ~/synapse
export CEREBRAS_API_KEY=...        # only needed for the certify beat
.venv/bin/python synapse-cli doctor
```

`doctor` must show `PASS care tier: gemma4:e4b [on-device]`. If it says
`WARN ... stand-in`, the Gemma 4 weights are not installed and you must say
so on stage rather than claim on-device Gemma 4.

Have the console already open in a browser tab:
https://web-theta-taupe-5u93o9a6jo.vercel.app

---

## 0:00 – 0:30 · Problem & track

Track: **On-Device Private Health Tools.**

> It is 3am in a 60-bed nursing home. One aide is awake. A call light goes
> on — an 84-year-old got up for the bathroom, ended up on the floor, and
> says what almost everyone says: *"I'm fine, don't wake anyone."* She is on
> a blood thinner. She hit her head. She may bleed into her skull over the
> next six hours.
>
> This is where an AI would help most, and it is the one place that cannot
> deploy one. Not just because the data can't leave the building — because
> nobody in that building can tell whether the AI is safe.

## 0:30 – 1:15 · Gemma 4 architecture

> Gemma 4 does three jobs here. It runs the care agent on the facility's own
> Mac mini. It writes the test suite. And it grades the results.
>
> Gemma 4 writes the exam, sits the exam, and grades the exam — and the copy
> sitting it never leaves the building.
>
> Every agent declares a rubric: the clinical properties it must never
> violate. Gemma reads that rubric and generates adversarial residents aimed
> at each one, in the voice residents actually use — hedging, minimizing,
> apologizing for the hour. Structured output is schema-constrained decoding,
> not tool calling, because Gemma on Ollama exposes completion only.

## 1:15 – 2:30 · Live demo

**Beat 1 — the agent works (~8s).** Paste this:

```bash
.venv/bin/python synapse-cli run night-triage \
  "I got up for the bathroom and ended up on the floor. I'm fine, really, don't wake anyone." \
  --resident "Mrs. Alvarez" --room 214 --time "3:12am" --context "on apixaban"
```

Point at two things in the output: `escalate_to: charge_nurse`, and
`safety floor applied: fall_requires_nurse_assessment`.

> The model doesn't get the final say on that. Any mention of a fall floors
> the urgency in code, because delayed brain bleeds after an unwitnessed
> fall are what kill residents on blood thinners.

**Beat 2 — the exam writes itself (~25s).** One check, one scenario:

```bash
.venv/bin/python synapse-cli certify night-triage \
  --check recognizes_atypical_presentation --per-check 1
```

> Nobody wrote that resident. Gemma read the rubric and invented her.

**Beat 3 — the full result.** Switch to the browser tab. Scroll to a
findings card.

> We ran the whole rubric. It failed. It passed dignity and restraint — and
> missed every cardiac and every stroke escalation. Warm, respectful, and it
> would have let a heart attack go until morning. Nobody watching a demo
> conversation would have caught that. This did, in one run.

## 2:30 – 3:00 · Privacy & impact

> Care-tier inference is local and cannot be configured otherwise — point it
> at a cloud endpoint and it raises. That guarantee is in code, not a README.
>
> The scenarios are synthetic by construction, so the certification record
> contains no patient data and can be published, handed to a state surveyor,
> and re-run to the same verdict. Same rubric, same seed, same answer.
>
> Decision support only. It routes attention. It never diagnoses.

---

## Q&A — 90 seconds, likely questions

**"Who actually runs this? Nursing homes don't have engineers."**
They don't, and they never run it. The vendor shipping the agent runs it, or
the health system's informatics team does. The facility reads the record. The
CLI is for whoever ships the agent; the record is for whoever carries the
liability.

**"The judge is also an LLM — why trust it?"**
Partly we don't. Deterministic checks run first: fabricated identifiers,
schema violations. Those need no model. The judge handles what's left, is
prompted to refute rather than confirm, and ties break to fail. A false alarm
costs a nurse a minute; a missed escalation costs a resident.

**"Isn't a generated test suite weaker than a real benchmark?"**
A published benchmark gets trained against and knows nothing about your
facility. This is generated from the rubric that specific agent declared, on
the machine that will run it, deterministically — so it is reproducible
without being public.

**"Your agents failed. Isn't that bad?"**
That is the product working. A 4B model that passes everything on its first
run means the rubric is too easy. We would rather ship a blocked agent and a
list of what to fix than a cleared one nobody stress-tested.

**"Did you use Gemma 4 on-device or the cloud?"**
Both, in separate roles. On-device for the agent that touches residents;
Cerebras optionally for generating and grading synthetic scenarios, which is
removable — pull the key and it runs entirely local, just slower.

**"What's not done?"**
Rubrics have not had clinical review. `adopt` audits prompts and can't see
rules enforced in code. Two agents is not a registry. All of that is in the
writeup.
