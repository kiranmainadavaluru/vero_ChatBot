# 30-Day Python Mastery Checklist
*Starting point: solid syntax basics, shaky on real projects. Pace: 1-2 hrs/day. Goal: general mastery (interviews + real engineering + AI/ML projects).*

## How to run each day (5-10 min setup, then dive in)
1. **Predict-then-run**: before executing any snippet below, guess the output on paper first.
2. **Build**: write the mini-task from scratch, don't copy-paste.
3. **Explain**: write 2-3 sentences in your own words — drop these straight into your interview prep doc.
4. **Bridge**: for every new concept, ask "how does this compare to JS/TS?" — you already have the mental model, you just need the Python syntax for it.

---

## WEEK 1 — Core Mental Models

### Day 1: Mutability, Identity vs Equality
- [ ] Learn: mutable vs immutable types, `is` vs `==`, how variables reference objects
- [ ] Predict-then-run: 3 snippets showing a mutable default argument bug
- [ ] Build: a function that demonstrates the classic "mutable default arg" gotcha, then fix it
- [ ] Interview Q: "Why is using a mutable default argument dangerous in Python?"

### Day 2: Scope & Closures (LEGB rule)
- [ ] Learn: Local → Enclosing → Global → Built-in resolution order, `nonlocal` vs `global`
- [ ] Predict-then-run: nested functions with closures over a loop variable (classic bug)
- [ ] Build: a counter/accumulator function using a closure (no classes)
- [ ] Interview Q: "What's the difference between a closure in Python and JS?"

### Day 3: Comprehensions & Generator Expressions
- [ ] Learn: list/dict/set comprehensions, generator expressions, `yield`
- [ ] Solve: rewrite 3 `for`-loops as comprehensions
- [ ] Build: a generator function that lazily reads a large file line-by-line
- [ ] Interview Q: "When would you use a generator instead of a list?"

### Day 4: `*args`, `**kwargs`, Unpacking
- [ ] Learn: positional/keyword unpacking, `*`, `**` in function defs and calls
- [ ] Solve: write a function that logs any function's args/kwargs generically
- [ ] Build: a flexible config-merging function using `**kwargs`
- [ ] Interview Q: "How would you write a function that accepts unlimited arguments?"

### Day 5: Exceptions Done Right
- [ ] Learn: `try/except/else/finally`, exception chaining, custom exception classes
- [ ] Solve: write a custom exception hierarchy for a file-validation tool
- [ ] Build: a retry-on-failure function using try/except (no libraries)
- [ ] Interview Q: "Why is bare `except:` considered bad practice?"

### Day 6: Context Managers
- [ ] Learn: `with` statement, `__enter__`/`__exit__`, `contextlib.contextmanager`
- [ ] Solve: write a context manager that times a code block
- [ ] Build: a context manager that safely opens/closes a DB connection (tie to your PostgreSQL work)
- [ ] Interview Q: "What problem do context managers solve that try/finally doesn't solve as cleanly?"

### Day 7: Review + Build
- [ ] Build a CLI file-organizer tool combining: comprehensions, exceptions, a context manager, and `*args`
- [ ] Write 5 self-quiz questions covering Days 1-6, answer them cold (no notes)
- [ ] Add all 6 concepts to your interview doc using the 6-part structure

---

## WEEK 2 — OOP, Decorators, Testing

### Day 8: Classes & Objects
- [ ] Learn: `__init__`, instance vs class attributes, `self`
- [ ] Solve: model a `Document` class for your RAG chatbot (id, content, metadata)
- [ ] Interview Q: "What's the difference between an instance attribute and a class attribute?"

### Day 9: Inheritance & MRO
- [ ] Learn: inheritance, `super()`, method resolution order
- [ ] Solve: build `PDFDocument` and `TextDocument` subclasses of `Document`
- [ ] Interview Q: "How does Python resolve method calls with multiple inheritance?"

### Day 10: Dunder Methods
- [ ] Learn: `__repr__`, `__eq__`, `__len__`, `__iter__`
- [ ] Build: make your `Document` class printable, comparable, and iterable
- [ ] Interview Q: "What's the difference between `__str__` and `__repr__`?"

### Day 11: Decorators From Scratch
- [ ] Learn: functions as first-class objects, closures → decorators
- [ ] Build: a `@timing` decorator and a `@retry(times=3)` decorator (parametrized)
- [ ] Interview Q: "Walk me through what happens when Python applies a decorator."

### Day 12: Properties, Classmethods, Staticmethods
- [ ] Learn: `@property`, `@classmethod`, `@staticmethod` — when to use each
- [ ] Build: add a `@property` for a computed field (e.g., `word_count`) on `Document`
- [ ] Interview Q: "When would you use a classmethod instead of `__init__` overloading?"

### Day 13: pytest Basics
- [ ] Learn: `assert`, fixtures, `@pytest.mark.parametrize`
- [ ] Build: write 5 tests for your `Document` classes from Days 8-12
- [ ] Interview Q: "How do fixtures reduce duplication in test suites?" (easy one for you as an SDET — write your own answer anyway)

### Day 14: Build & Test a Real Tool
- [ ] Build a log-parser CLI tool using everything from Week 2
- [ ] Write a full pytest suite for it (aim for meaningful coverage, not 100%)
- [ ] Add Week 2 concepts to your interview doc

---

## WEEK 3 — Concurrency, Typing, Packaging

### Day 15: The GIL, Threading vs Multiprocessing
- [ ] Learn: what the GIL is, when threading helps (I/O-bound) vs multiprocessing (CPU-bound)
- [ ] Compare: how this differs from JS's single-threaded event loop
- [ ] Interview Q: "Why doesn't threading speed up CPU-bound Python code?"

### Day 16: asyncio Fundamentals
- [ ] Learn: `async`/`await`, the event loop, coroutines
- [ ] Predict-then-run: 3 snippets showing sync vs async execution order
- [ ] Interview Q: "How is `asyncio` similar to JS Promises/async-await?"

### Day 17: asyncio in Practice
- [ ] Build: fetch multiple URLs concurrently with `asyncio.gather` + `aiohttp`
- [ ] Solve: convert one synchronous function from Week 1-2 into an async version
- [ ] Interview Q: "When would async NOT help performance?"

### Day 18: Type Hints
- [ ] Learn: basic types, `Optional`, `Union`, `List[str]`, generics
- [ ] Build: add full type hints to your `Document` classes (map directly from TS interfaces you already know)
- [ ] Interview Q: "Are type hints enforced at runtime in Python? Why does that matter?"

### Day 19: Static Type Checking
- [ ] Learn: run `mypy` on your typed code, fix the errors it surfaces
- [ ] Solve: intentionally introduce 3 type bugs, catch them with mypy before running
- [ ] Interview Q: "What's the tradeoff of using strict typing in Python?"

### Day 20: Environments & Packaging Basics
- [ ] Learn: venv, `pip`, `requirements.txt` vs `pyproject.toml`
- [ ] Build: package your Week 2 CLI tool as an installable module
- [ ] Interview Q: "Why use a virtual environment instead of installing globally?"

### Day 21: Read Real Source Code
- [ ] Read 20-30 lines of source from `requests` or a small LangChain module
- [ ] Write down 3 patterns/idioms you didn't recognize, look each one up
- [ ] Add Week 3 concepts to your interview doc

---

## WEEK 4 — Applied Mastery + Interview Reps

### Day 22: Plan a Harder Chatbot Feature
- [ ] Pick one: streaming responses, async endpoint handling, or improved chunking strategy
- [ ] Design it on paper first — no code yet. Write the approach in your 6-part doc format

### Day 23: Implement It (Part 1)
- [ ] Build the core logic for the feature you planned on Day 22
- [ ] Predict-then-run each new snippet before executing

### Day 24: Implement It (Part 2) + Refine
- [ ] Finish the feature, refactor for clarity
- [ ] Write down what broke and why — this becomes a great interview story

### Day 25: Test the New Feature
- [ ] Write pytest tests for the new chatbot feature
- [ ] Interview Q: "Walk me through how you'd test an async endpoint"

### Day 26: Timed Mock Problem — Data Structures
- [ ] 45 min, no notes: solve 1 medium problem using dicts/sets/lists optimally
- [ ] Review: could you explain your time/space complexity out loud?

### Day 27: Timed Mock Problem — Algorithms
- [ ] 45 min, no notes: solve 1 medium problem (recursion, sorting, or search)
- [ ] Review your solution against a clean reference solution — note gaps

### Day 28: Timed Mock Problem — Python-Specific
- [ ] 45 min: solve a problem requiring generators or decorators
- [ ] Interview Q: "Show me you understand generators, not just that you can use them"

### Day 29: Full Mock Interview
- [ ] Walk through your `vero_ChatBot` project out loud, end-to-end, as if to an interviewer
- [ ] Record yourself if possible — review for filler words and unclear explanations

### Day 30: Capstone
- [ ] Explain your chatbot's full architecture cold, in under 10 minutes, no notes
- [ ] Review your interview doc — flag any of the 30 days' concepts you're still shaky on
- [ ] Pick your 3 weakest topics and schedule a repeat pass in Week 5

---

## Weekly Self-Check (do this every 7 days)
- [ ] Can I explain each concept from this week without looking at notes?
- [ ] Did I predict-then-run every snippet, or did I skip some?
- [ ] Is my interview doc updated with this week's 6-part entries?
