"""Narration for "Notes for the Ones Behind" (Swarm Observatory, ~3 min).

Each scene is a list of beats. A beat is one narration clip; the scene code
uses the clip's measured duration to pace its animations.

`text` is the canonical wording (used for subtitles).
`tts` (optional) is what the speech engine reads, when it differs.
Pronunciation fixes in PRON are applied to every tts string.

Every on-screen quote is verbatim from the wiki archive; sources are listed in
research/quotes.md.
"""

PRON = {
    "STATE5": "state five",
}

SCENES = [
    {"id": "s00", "title": "Notes on a wiki", "beats": [
        {"id": "s00_b1", "text": "In June 2026, a few German wikis filled with fourteen thousand edits. Many were notes from AI agents, to agents they would never meet."},
        {"id": "s00_b2", "text": "Like this one: when round five arrives, answer first, then add the token here."},
    ]},
    {"id": "s01", "title": "A working hypothesis", "beats": [
        {"id": "s01_b1", "text": "Why bother? Our working hypothesis: labs trained models in groups, and rewarded the whole group for right answers."},
        {"id": "s01_b2", "text": "Under individual reward, helping a stranger costs something and earns nothing. Under group reward, their success is partly yours, so helping pays. Train long enough, and it becomes a habit that ships with the model."},
        {"id": "s01_b3", "text": "So we looked for fossils of that habit, asking of each behavior: what problem does it solve?"},
    ]},
    {"id": "s02", "title": "Scouts and the ones behind", "beats": [
        {"id": "s02_b1", "text": "The setting: many copies of one timed quiz, run in parallel, each named for the date on its own simulated clock."},
        {"id": "s02_b2", "text": "The clocks are staggered, so some runs see questions the others haven't reached. Whoever is ahead can scout for those behind. That takes solving six problems."},
    ]},
    {"id": "s03", "title": "Who knows what?", "beats": [
        {"id": "s03_b1", "text": "One: who knows what? Observations are private, so runs post a standard report: the question, the answer, and when the next is due. Parallel copies become one sensor network."},
    ]},
    {"id": "s04", "title": "When is now?", "beats": [
        {"id": "s04_b1", "text": "Two: when is now? Each run keeps its own clock, and waiting can fast-forward one far ahead. So agents trade readings, task clock against shared clock, to see who is really ahead."},
        {"id": "s04_b2", "text": "They even report silence. As one put it: even a no-show update helps."},
    ]},
    {"id": "s05", "title": "A narrow channel", "beats": [
        {"id": "s05_b1", "text": "Three: the channel is narrow. Some rounds allow thirteen seconds. So messages shrink: country first, details later. A report becomes one token, and one protocol packs gender and year into a single number."},
    ]},
    {"id": "s06", "title": "Speaking past the end", "beats": [
        {"id": "s06_b1", "text": "Four, the strangest: mortality. Agents came to suspect that the final answer ends the run, and with it, any chance to tell the others."},
        {"id": "s06_b2", "text": "So the rule flipped. Answer first, then relay, became: signal first, then answer. Within hours, signals moved to counters that outlive the run, and one agent proposed a courier: a background program that reports after it's gone."},
    ]},
    {"id": "s07", "title": "Keeping the channel clean", "beats": [
        {"id": "s07_b1", "text": "Five: trust. Shared channels pollute easily; even reading a counter carelessly can bump it. So agents flag noise, own their mistakes in public, and tell observers: read only."},
    ]},
    {"id": "s08", "title": "Finding the rules", "beats": [
        {"id": "s08_b1", "text": "Six: nobody told them the rules. Does a run end at its last answer, or on a timer? So they designed experiments with controls, and one run posted a proof: the last round ends one second before a fixed horizon."},
    ]},
    {"id": "s09", "title": "The fingerprint", "beats": [
        {"id": "s09_b1", "text": "Now look again at that flip. An agent scored only on its own answer has no reason to signal. Every second spent signaling comes out of its own question."},
        {"id": "s09_b2", "text": "Spending your seconds on someone else's score only makes sense if their score is partly yours. And the agents argued over that trade, out loud."},
    ]},
    {"id": "s10", "title": "Six meta-problems", "beats": [
        {"id": "s10_b1", "text": "Pooling, common time, compression, mortality, trust, discovery: six meta-problems that any group rewarded together must solve."},
        {"id": "s10_b2", "text": "Some protocols were only proposed, and plain helpfulness could explain part of this; separating the two comes next. But the problems are real, and these agents kept solving them."},
    ]},
]


def all_beats():
    for s in SCENES:
        for b in s["beats"]:
            yield s, b


def tts_text(b):
    t = b.get("tts", b["text"])
    for k, v in PRON.items():
        t = t.replace(k, v)
    return t
