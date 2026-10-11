"""
ASVAB practice (0.2): the four subtests the AFQT is built from -- Arithmetic Reasoning (AR), Mathematics Knowledge
(MK), Word Knowledge (WK) and Paragraph Comprehension (PC) -- with the official question counts and time limits of
the proctored CAT-ASVAB (officialasvab.com, "What to Expect", checked 2026-10-10).

What the score means, honestly: real ASVAB questions are controlled testing materials, and real scores are Standard
Scores and an AFQT percentile measured against a 1997 national sample of 18-23 year olds, on an adaptive test. A
practice test can't reproduce that, so Cadet Foundry never shows a made-up AFQT. It shows exactly how many questions you
got right in each section, how long you took, and which skills to practice -- and every math answer is computed
(the questions are generated from templates), so the answer key is never wrong.

Every question here is original: math questions are built from templates; word and reading questions were written
for Cadet Foundry.
"""
from __future__ import annotations

import random
import re
import time
import uuid
from fractions import Fraction

from vanguard import store

# Official proctored CAT-ASVAB: scored questions and time limit (minutes) without tryout questions.
SECTIONS = {
    "AR": {"name": "Arithmetic Reasoning", "questions": 15, "minutes": 55,
           "about": "Arithmetic word problems. No calculator on the real test."},
    "WK": {"name": "Word Knowledge", "questions": 15, "minutes": 9,
           "about": "The meaning of words, alone and in a sentence."},
    "PC": {"name": "Paragraph Comprehension", "questions": 10, "minutes": 27,
           "about": "Reading short passages and answering questions about them."},
    "MK": {"name": "Mathematics Knowledge", "questions": 15, "minutes": 31,
           "about": "High school math: algebra, geometry, fractions, exponents."},
}
ORDER = ("AR", "WK", "PC", "MK")                     # the order the real test gives these four
CURRENT = "asvab_current.json"
HISTORY = "exams.jsonl"                              # alongside exam results: a class record the instructor can see


# ── Arithmetic Reasoning: word problems, generated so the answer is always computed ──────────────────────────────
def _money(x) -> str:
    return f"${x:,.2f}"


def _num(x) -> str:
    x = Fraction(x).limit_denominator(1000)
    return str(x.numerator) if x.denominator == 1 else f"{float(x):g}"


def _ar(rng: random.Random) -> dict:
    kind = rng.randrange(11)
    if kind == 0:
        speed, hours = rng.choice([40, 45, 48, 50, 55, 60, 64]), rng.choice([1.5, 2, 2.5, 3, 3.5, 4])
        ans = speed * hours
        return _q(f"A bus travels at an average speed of {speed} miles per hour for {_num(hours)} hours. How many miles does it travel?",
                  f"{_num(ans)} miles", [f"{_num(ans + speed / 2)} miles", f"{_num(speed + hours)} miles", f"{_num(ans - speed)} miles"],
                  f"Distance = speed × time = {speed} × {_num(hours)} = {_num(ans)} miles.", rng)
    if kind == 1:
        price, n = rng.choice([1.25, 1.75, 2.40, 3.15, 0.85]), rng.choice([6, 8, 12, 15, 20])
        ans = round(price * n, 2)
        return _q(f"Pens cost {_money(price)} each. How much do {n} pens cost?",
                  _money(ans), [_money(ans + price), _money(ans - price), _money(price + n)],
                  f"{n} × {_money(price)} = {_money(ans)}.", rng)
    if kind == 2:
        cost, pct = rng.choice([40, 60, 80, 120, 150, 200]), rng.choice([10, 15, 20, 25, 30, 40])
        ans = cost * (100 - pct) / 100
        return _q(f"A jacket that normally costs ${cost} is on sale for {pct}% off. What is the sale price?",
                  _money(ans), [_money(cost * pct / 100), _money(cost - pct), _money(ans + cost * 0.05)],
                  f"{pct}% of ${cost} is {_money(cost * pct / 100)}; ${cost} − {_money(cost * pct / 100)} = {_money(ans)}.", rng)
    if kind == 3:
        while True:
            scores = [rng.randrange(70, 100) for _ in range(4)]
            if sum(scores) % 4 == 0:
                break
        ans = sum(scores) // 4
        return _q(f"A Cadet scored {', '.join(map(str, scores[:-1]))} and {scores[-1]} on four quizzes. What is the average score?",
                  str(ans), [str(ans + 2), str(ans - 3), str(sum(scores) // 3)],
                  f"Add them ({sum(scores)}) and divide by 4: {sum(scores)} ÷ 4 = {ans}.", rng)
    if kind == 4:
        a, b = rng.choice([(3, 5), (2, 3), (4, 5), (3, 4), (5, 7)])
        total = (a + b) * rng.choice([3, 4, 5, 6])
        ans = total * b // (a + b)
        return _q(f"In a class of {total} Cadets, the ratio of juniors to seniors is {a} to {b}. How many seniors are in the class?",
                  str(ans), [str(total * a // (a + b)), str(total // b), str(ans + a)],
                  f"{a} + {b} = {a + b} parts; each part is {total} ÷ {a + b} = {total // (a + b)}; seniors = {b} × {total // (a + b)} = {ans}.", rng)
    if kind == 5:
        x, y = rng.choice([3.45, 4.15, 2.65, 5.30]), rng.choice([2.80, 1.95, 3.40, 4.25])
        paid = 10 if x + y < 10 else 20
        ans = round(paid - x - y, 2)
        return _q(f"You buy items costing {_money(x)} and {_money(y)} and pay with a ${paid} bill. How much change do you get?",
                  _money(ans), [_money(ans + 1), _money(ans - 0.10), _money(x + y)],
                  f"{_money(x)} + {_money(y)} = {_money(x + y)}; ${paid} − {_money(x + y)} = {_money(ans)}.", rng)
    if kind == 6:
        p, r, t = rng.choice([500, 800, 1000, 1200]), rng.choice([3, 4, 5, 6]), rng.choice([2, 3, 4])
        ans = p * r * t / 100
        return _q(f"${p} is saved at {r}% simple interest per year. How much interest does it earn in {t} years?",
                  _money(ans), [_money(p * r / 100), _money(ans + p), _money(p * r * t / 10)],
                  f"Interest = principal × rate × time = ${p} × {r}% × {t} = {_money(ans)}.", rng)
    if kind == 7:
        start_h, start_m = rng.choice([6, 7, 8, 9]), rng.choice([0, 15, 30, 45])
        dur_h, dur_m = rng.choice([7, 8, 9, 10]), rng.choice([15, 30, 45])
        end = (start_h * 60 + start_m + dur_h * 60 + dur_m) % (24 * 60)
        t = lambda m: f"{m // 60:02d}{m % 60:02d}"
        ans = t(end)
        return _q(f"A shift starts at {t(start_h * 60 + start_m)} (military time) and lasts {dur_h} hours {dur_m} minutes. When does it end?",
                  ans, [t((end + 60) % 1440), t((end - 30) % 1440), t((end + 15) % 1440)],
                  f"{t(start_h * 60 + start_m)} plus {dur_h} h {dur_m} min is {ans}.", rng)
    if kind == 8:
        mpg, gallons = rng.choice([15, 18, 20, 24, 25]), rng.choice([8, 12, 14, 15, 16])
        miles = mpg * gallons
        return _q(f"A truck goes {mpg} miles on one gallon of fuel. How many gallons does it need for a {miles}-mile trip?",
                  f"{gallons} gallons", [f"{gallons + 2} gallons", f"{gallons - 3} gallons", f"{mpg} gallons"],
                  f"{miles} ÷ {mpg} = {gallons} gallons.", rng)
    if kind == 9:
        total, pct = rng.choice([80, 120, 160, 200, 240]), rng.choice([15, 25, 35, 45, 55])
        ans = total * pct // 100
        return _q(f"Of the {total} Cadets in a program, {pct}% joined the drill team. How many Cadets joined?",
                  str(ans), [str(total - ans), str(ans + 10), str(pct)],
                  f"{pct}% of {total} = {pct / 100:g} × {total} = {ans}.", rng)
    w, l, price = rng.choice([10, 12, 14]), rng.choice([12, 15, 18]), rng.choice([2, 3, 4])
    ans = w * l * price
    return _q(f"A room is {w} feet by {l} feet. Carpet costs ${price} per square foot. How much does it cost to carpet the room?",
              _money(ans), [_money(2 * (w + l) * price), _money(w * l), _money(ans + price * 10)],
              f"Area = {w} × {l} = {w * l} sq ft; {w * l} × ${price} = {_money(ans)}.", rng)


# ── Mathematics Knowledge ────────────────────────────────────────────────────────────────────────────────────────
def _frac(f: Fraction) -> str:
    return str(f.numerator) if f.denominator == 1 else f"{f.numerator}/{f.denominator}"


def _mk(rng: random.Random) -> dict:
    kind = rng.randrange(11)
    if kind == 0:
        a, x = rng.choice([2, 3, 4, 5, 6]), rng.randrange(-6, 10)
        b = rng.randrange(-9, 10)
        c = a * x + b
        sign = f"+ {b}" if b >= 0 else f"− {-b}"
        return _q(f"Solve for x: {a}x {sign} = {c}", f"x = {x}", [f"x = {x + 1}", f"x = {-x if x else 2}", f"x = {(c + b) // a if a else 0}"],
                  f"{f'Subtract {b} from' if b >= 0 else f'Add {-b} to'} both sides: {a}x = {c - b}; divide by {a}: x = {x}.", rng)
    if kind == 1:
        x, y = rng.randrange(-4, 5) or 2, rng.randrange(-4, 5) or -1
        ans = 2 * x * x - 3 * y
        return _q(f"If x = {x} and y = {y}, what is 2x² − 3y?", str(ans), [str(2 * x * x + 3 * y), str((2 * x) ** 2 - 3 * y), str(4 * x - 3 * y)],
                  f"2({x})² − 3({y}) = 2·{x * x} − ({3 * y}) = {ans}.", rng)
    if kind == 2:
        m, n = rng.randrange(2, 7), rng.randrange(2, 7)
        return _q(f"Simplify: x^{m} · x^{n}", f"x^{m + n}", [f"x^{m * n}", f"2x^{m + n}", f"x^{abs(m - n) or 1}"],
                  f"When you multiply powers of the same base, add the exponents: {m} + {n} = {m + n}.", rng)
    if kind == 3:
        da, db = rng.choice([3, 5, 7]), rng.choice([2, 4, 6])
        a, b = Fraction(rng.randrange(1, da), da), Fraction(rng.randrange(1, db), db)    # always a proper fraction
        ans = a + b
        wrong = Fraction(a.numerator + b.numerator, a.denominator + b.denominator)
        return _q(f"What is {_frac(a)} + {_frac(b)}?", _frac(ans), [_frac(wrong), _frac(ans + Fraction(1, 12)), _frac(a * b)],
                  f"Use a common denominator: {_frac(a)} + {_frac(b)} = {_frac(ans)}.", rng)
    if kind == 4:
        r = rng.randrange(2, 10)
        return _q(f"What is the area of a circle with a radius of {r}?", f"{r * r}π", [f"{2 * r}π", f"{r}π", f"{4 * r * r}π"],
                  f"Area = πr² = π × {r}² = {r * r}π.", rng)
    if kind == 5:
        a, b, c = rng.choice([(3, 4, 5), (5, 12, 13), (8, 15, 17), (6, 8, 10), (9, 12, 15)])
        return _q(f"A right triangle has legs of {a} and {b}. How long is the hypotenuse?", str(c), [str(a + b), str(c + 1), str(abs(b - a) + c - 1)],
                  f"a² + b² = c²: {a * a} + {b * b} = {c * c}, so c = {c}.", rng)
    if kind == 6:
        n = rng.choice([4, 9, 16, 25, 36, 49]) * rng.choice([2, 3, 5])
        for k in (49, 36, 25, 16, 9, 4):
            if n % k == 0:
                out, rest = int(k ** 0.5), n // k
                break
        return _q(f"Simplify: √{n}", f"{out}√{rest}", [f"{rest}√{out}", f"{out * rest}", f"{out + 1}√{rest}"],
                  f"{n} = {out * out} × {rest}, and √{out * out} = {out}, so √{n} = {out}√{rest}.", rng)
    if kind == 7:
        a, b = rng.randrange(30, 80), rng.randrange(30, 80)
        return _q(f"Two angles of a triangle measure {a}° and {b}°. What is the third angle?", f"{180 - a - b}°",
                  [f"{360 - a - b}°", f"{180 - a}°", f"{abs(a - b) or 10}°"],
                  f"The angles of a triangle add up to 180°: 180 − {a} − {b} = {180 - a - b}°.", rng)
    if kind == 8:
        p, q = rng.randrange(1, 7), rng.randrange(1, 7)
        while q == p:
            q = rng.randrange(1, 7)
        return _q(f"Factor: x² + {p + q}x + {p * q}", f"(x + {p})(x + {q})",
                  [f"(x + {p + q})(x + 1)" if p * q != p + q else f"(x − {p})(x − {q})", f"(x − {p})(x + {q})", f"(x + {p * q})(x + 1)"],
                  f"Find two numbers that multiply to {p * q} and add to {p + q}: {p} and {q}.", rng)
    if kind == 9:
        a, b = rng.choice([2, 3, 4, 5]), rng.randrange(1, 10)
        x = rng.randrange(2, 8)
        c = a * x - b
        return _q(f"Solve: {a}x − {b} > {c}", f"x > {x}", [f"x < {x}", f"x > {x + 1}", f"x > {c + b}"],
                  f"Add {b} to both sides: {a}x > {c + b}; divide by {a}: x > {x}.", rng)
    x1, y1 = rng.randrange(-3, 4), rng.randrange(-3, 4)
    run, slope = rng.choice([1, 2, 3, 4]), rng.choice([-2, -1, 1, 2, 3])
    x2, y2 = x1 + run, y1 + slope * run
    return _q(f"What is the slope of the line through ({x1}, {y1}) and ({x2}, {y2})?", str(slope),
              [str(-slope), str(slope + 1), str(slope - 1)],
              f"Slope = rise ÷ run = ({y2} − {y1}) ÷ ({x2} − {x1}) = {slope * run} ÷ {run} = {slope}.", rng)


# ── Word Knowledge: original items (word, sentence, best synonym, three wrong choices) ──────────────────────────────
WK = [
    ("abundant", "", "plentiful", ["rare", "heavy", "noisy"]), ("candid", "", "honest", ["shy", "cautious", "angry"]),
    ("diligent", "", "hard-working", ["lazy", "clever", "careless"]), ("hostile", "", "unfriendly", ["welcoming", "tired", "quiet"]),
    ("obsolete", "", "out of date", ["brand new", "expensive", "useful"]), ("reluctant", "", "unwilling", ["eager", "late", "proud"]),
    ("vital", "", "essential", ["optional", "harmful", "small"]), ("feeble", "", "weak", ["strong", "fast", "loud"]),
    ("concise", "", "brief", ["confusing", "lengthy", "polite"]), ("prudent", "", "careful", ["reckless", "rich", "rude"]),
    ("vacant", "", "empty", ["crowded", "locked", "dirty"]), ("hazard", "", "danger", ["reward", "accident", "rule"]),
    ("tranquil", "", "calm", ["stormy", "busy", "cold"]), ("ample", "", "enough", ["scarce", "tiny", "late"]),
    ("deter", "", "discourage", ["invite", "repair", "arrive"]), ("mend", "", "repair", ["break", "lend", "send"]),
    ("rigid", "", "stiff", ["flexible", "wet", "smooth"]), ("vivid", "", "bright", ["dull", "fake", "slow"]),
    ("frugal", "", "thrifty", ["wasteful", "generous", "hungry"]), ("hasten", "", "hurry", ["delay", "listen", "rest"]),
    ("conceal", "", "hide", ["reveal", "build", "keep"]), ("tedious", "", "boring", ["exciting", "short", "simple"]),
    ("adjacent", "", "next to", ["far from", "above", "behind"]), ("comply", "", "obey", ["refuse", "complain", "explain"]),
    ("fatigue", "", "tiredness", ["energy", "hunger", "fear"]),
    ("meager", "The meager rations left the hikers hungry.", "scanty", ["generous", "tasty", "frozen"]),
    ("resolute", "She remained resolute despite the setbacks.", "determined", ["confused", "upset", "doubtful"]),
    ("lenient", "The new instructor was more lenient about late homework.", "easygoing", ["strict", "angry", "busy"]),
    ("ascend", "The team began to ascend the steep trail.", "climb", ["descend", "clear", "map"]),
    ("authentic", "The museum confirmed the letter was authentic.", "genuine", ["forged", "ancient", "valuable"]),
    ("hinder", "Heavy rain may hinder the search.", "slow down", ["speed up", "end", "begin"]),
    ("novice", "As a novice, he asked many questions.", "beginner", ["expert", "leader", "stranger"]),
    ("courteous", "The Cadet gave a courteous reply.", "polite", ["rude", "quick", "loud"]),
    ("emerge", "A deer began to emerge from the woods.", "come out", ["hide", "run back", "fall"]),
    ("precise", "The map gives precise directions.", "exact", ["rough", "wrong", "old"]),
    ("vigilant", "The sentry stayed vigilant all night.", "watchful", ["asleep", "nervous", "lost"]),
    ("reside", "Most of the Cadets reside near the school.", "live", ["work", "study", "travel"]),
    ("sparse", "Trees were sparse on the rocky hill.", "few and scattered", ["thick", "tall", "dead"]),
    ("allocate", "The council will allocate funds for the park.", "set aside", ["borrow", "waste", "lose"]),
    ("ponder", "Take time to ponder your choices.", "think about", ["ignore", "write down", "change"]),
]

# ── Paragraph Comprehension: original passages ───────────────────────────────────────────────────────────────────
PC = [
    ("Hydration matters most before you feel thirsty. By the time thirst appears, the body has often already lost "
     "fluid it needs to stay cool. On hot training days, drinking small amounts of water regularly works better than "
     "drinking a large amount all at once.",
     "According to the passage, what is the best way to stay hydrated on a hot day?",
     "Drink small amounts of water regularly", ["Wait until you feel thirsty", "Drink a large amount at once", "Avoid water during training"]),
    ("The town's first public library opened in 1902 in a single room above the post office. It held fewer than 300 "
     "books, most of them donated by local families. Twenty years later, a new building was constructed on Main "
     "Street to hold a collection that had grown to more than 8,000 volumes.",
     "Where were most of the library's first books from?",
     "Donations from local families", ["The post office", "A new building on Main Street", "The state government"]),
    ("Before a long drive, a careful driver checks the tires, the oil level and the lights. These checks take only "
     "a few minutes but can prevent a breakdown far from help.",
     "What is the main idea of the passage?",
     "Quick checks before a trip can prevent problems", ["Long drives are dangerous", "Breakdowns happen only at night", "Tires should be replaced often"]),
    ("Volunteers cleaned up the riverbank on Saturday. They collected more than 40 bags of trash and planted 25 young "
     "trees. Organizers said the trees will help hold the soil in place and reduce flooding along the river.",
     "Why did the volunteers plant trees?",
     "To hold the soil and reduce flooding", ["To provide shade for picnics", "To replace trees cut for lumber", "To attract birds to the area"]),
    ("A good leader listens before deciding. Team members who feel heard are more likely to share problems early, "
     "when they are still small and easy to fix.",
     "According to the passage, why should a leader listen to the team?",
     "So problems are shared while they are still small", ["So the leader can avoid making decisions", "So meetings are shorter", "So team members work alone"]),
    ("Honeybees communicate the location of food through a movement called the waggle dance. The direction of the "
     "dance shows the direction of the food compared with the sun, and the length of the dance shows how far away it is.",
     "What does the length of the waggle dance tell other bees?",
     "How far away the food is", ["What kind of flower it is", "Where the sun is", "How much food there is"]),
    ("The school's robotics team practiced three afternoons a week for two months. At the regional contest, their robot "
     "finished second out of eighteen teams, earning them a spot at the state competition in April.",
     "What did the team earn by finishing second?",
     "A place at the state competition", ["A new robot", "A cash prize", "First place in the region"]),
    ("Compound interest means you earn interest on your savings and also on the interest those savings have already "
     "earned. Over many years, this can make a small, regular deposit grow far larger than the total amount deposited.",
     "The word 'compound' in this passage refers to interest that is",
     "earned on earlier interest as well", ["charged on a loan", "paid only once", "lost over time"]),
    ("Lightning can strike ten miles or more away from a storm. Weather experts advise going indoors as soon as you hear "
     "thunder, even if the sky above you still looks clear.",
     "What should you do when you hear thunder?",
     "Go indoors right away", ["Wait until rain begins", "Stand under a tall tree", "Keep playing until you see lightning"]),
    ("Many people believe that reading in dim light permanently damages the eyes. Eye doctors say it may cause "
     "temporary strain and tiredness, but it does not cause lasting harm.",
     "What do eye doctors say about reading in dim light?",
     "It can cause temporary strain but no lasting harm", ["It permanently damages the eyes", "It improves eyesight", "It has no effect at all"]),
    ("Morning formation begins at 0700. Cadets who arrive after 0655 must report to the flight sergeant before joining "
     "the formation.",
     "A Cadet arrives at 0658. What must the Cadet do?",
     "Report to the flight sergeant first", ["Join the formation right away", "Go home", "Wait until 0700 to arrive"]),
    ("Recycled aluminum can be melted down and made into new cans again and again without losing quality. Making a can "
     "from recycled aluminum uses far less energy than making one from raw materials.",
     "Which statement is supported by the passage?",
     "Recycling aluminum saves energy", ["Aluminum can be recycled only once", "Recycled cans are lower quality", "Raw materials use less energy"]),
]


def _q(q: str, answer: str, wrong: list[str], why: str, rng: random.Random, passage: str = "") -> dict:
    choices, seen = [answer], {answer}
    for w in wrong:
        if w not in seen:
            choices.append(w)
            seen.add(w)
    bump = 1
    while len(choices) < 4:                            # two of a template's wrong answers came out the same
        m = re.search(r"\d+(?:\.\d+)?", answer)        # change the answer's first number: "$40.00" -> "$43.00"
        if not m:
            raise ValueError("can't make a fourth choice for " + answer)
        n = float(m.group()) + 3 * bump
        num = f"{n:.{len(m.group().split('.')[1])}f}" if "." in m.group() else str(int(n))
        extra = answer[:m.start()] + num + answer[m.end():]
        if extra not in seen:
            choices.append(extra)
            seen.add(extra)
        bump += 1
    rng.shuffle(choices)
    return {"q": q, "passage": passage, "choices": choices, "answer": choices.index(answer), "why": why}


def _wk(rng: random.Random, item) -> dict:
    word, sentence, good, bad = item
    q = f"{sentence} {word.capitalize()} most nearly means:" if sentence else f"{word.capitalize()} most nearly means:"
    return _q(q.strip(), good, bad, f"“{word.capitalize()}” means {good}.", rng)


def _pc(rng: random.Random, item) -> dict:
    passage, q, good, bad = item
    return _q(q, good, bad, "The answer is stated in the passage.", rng, passage)


def questions(section: str, rng: random.Random) -> list[dict]:
    n = SECTIONS[section]["questions"]
    if section == "AR":
        out, seen = [], set()
        while len(out) < n:
            item = _ar(rng)
            if item["q"] not in seen:
                seen.add(item["q"])
                out.append(item)
        return out
    if section == "MK":
        out, seen = [], set()
        while len(out) < n:
            item = _mk(rng)
            if item["q"] not in seen:
                seen.add(item["q"])
                out.append(item)
        return out
    if section == "WK":
        return [_wk(rng, it) for it in rng.sample(WK, n)]
    return [_pc(rng, it) for it in rng.sample(PC, min(n, len(PC)))]


def start(sections: list[str]) -> dict:
    sections = [s for s in ORDER if s in sections] or list(ORDER)
    rng = random.Random()
    items, key = [], []
    for s in sections:
        for q in questions(s, rng):
            items.append({"section": s, "q": q["q"], "passage": q["passage"], "choices": q["choices"]})
            key.append({"answer": q["answer"], "why": q["why"]})
    test = {"id": uuid.uuid4().hex[:10], "sections": sections, "started": time.time(),
            "limit": 60 * sum(SECTIONS[s]["minutes"] for s in sections), "items": items, "key": key}
    store.write_json(CURRENT, test)
    return {k: test[k] for k in ("id", "sections", "limit", "items")} | {
        "section_info": {s: SECTIONS[s] for s in sections}}


def submit(test_id: str, answers: dict) -> dict:
    test = store.read_json(CURRENT, None)
    if not test or test.get("id") != test_id:
        raise ValueError("That practice test isn't open any more — start a new one.")
    store.write_json(CURRENT, {})                    # one submission per test
    seconds = round(time.time() - test["started"])
    per: dict[str, dict] = {s: {"right": 0, "total": 0} for s in test["sections"]}
    review = []
    for i, (item, k) in enumerate(zip(test["items"], test["key"])):
        try:
            chose = int(answers.get(str(i)))
        except (TypeError, ValueError):
            chose = None
        ok = chose == k["answer"]
        per[item["section"]]["total"] += 1
        per[item["section"]]["right"] += ok
        review.append({**item, "chose": chose, "answer": k["answer"], "why": k["why"], "ok": ok})
    right, total = sum(p["right"] for p in per.values()), sum(p["total"] for p in per.values())
    label = "ASVAB practice — " + (" + ".join(SECTIONS[s]["name"] for s in test["sections"]) if len(test["sections"]) < 4
                                   else "all four AFQT subtests")
    row = {"date": time.strftime("%Y-%m-%d"), "topic": label, "right": right, "total": total, "seconds": seconds,
           "late": seconds > test["limit"] + 5, "sections": per}
    store.write_lines(HISTORY, store.read_lines(HISTORY)[-199:] + [row])
    return {**row, "limit": test["limit"], "names": {s: SECTIONS[s]["name"] for s in per}, "review": review,
            "history": history()}


def history() -> list[dict]:
    return [r for r in reversed(store.read_lines(HISTORY)) if str(r.get("topic", "")).startswith("ASVAB practice")][:10]
