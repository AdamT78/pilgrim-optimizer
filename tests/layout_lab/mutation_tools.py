"""One trustworthy definition of "a mutation was actually applied".

A mutation suite's whole claim is negative: it says these tests would have noticed if the code
were wrong. That claim rests entirely on the code having actually been made wrong, and a
`source.replace(old, new)` whose `old` no longer appears returns the source unchanged and
perfectly happily. The suite then runs the tests against the REAL build, they pass, and the line
prints as a clean result. Nothing anywhere says the mutation never happened.

That is not hypothetical. Three markers in the V4.2 suite stopped matching the moment a lock
guard was inserted as the first line of the functions they were anchored to, and the BUILD_VERSION
mutation sat pinned at "4.2" for a whole version, testing nothing. Both were found by accident.

So: every target must resolve to exactly one occurrence, a target that resolves to none or to
several is a FAILURE OF THE SUITE rather than a skipped line, and the summary counts applied
separately from caught. A run with a stale target is red even when nothing survived, because a
suite that cannot prove it broke the code cannot prove the tests caught anything.
"""
import re


class MutationTargetError(Exception):
    """A mutation's target does not resolve to exactly one place in the source."""


def _context(source, needle, limit=3):
    """Where a partial match got to, which is usually enough to see what moved."""
    head = needle.strip().splitlines()[0].strip() if needle.strip() else ""
    if not head:
        return ""
    hits = [i + 1 for i, line in enumerate(source.splitlines()) if head in line]
    if not hits:
        return "        (its first line appears nowhere either)"
    shown = ", ".join(str(h) for h in hits[:limit])
    more = "" if len(hits) <= limit else " and %d more" % (len(hits) - limit)
    return "        (its first line is at line %s%s -- the rest has moved)" % (shown, more)


def replace_exactly_once(source, old, new, label):
    """Apply one mutation, or raise. Never returns the source unchanged.

    `old` must appear exactly once. Zero means the marker has gone stale -- the code moved and
    this mutation has quietly stopped testing anything. More than one means the mutation is
    ambiguous: it would change several places at once, and a test that then failed would not say
    which of them mattered.
    """
    n = source.count(old)
    if n != 1:
        raise MutationTargetError(
            "Mutation target failure:\n"
            "        %r\n"
            "        expected exactly 1 occurrence\n"
            "        found %d\n%s" % (label, n, _context(source, old)))
    out = source.replace(old, new, 1)
    if out == source:
        # `old` and `new` are the same text: the mutation is a no-op and would report a clean
        # pass having changed nothing at all.
        raise MutationTargetError(
            "Mutation target failure:\n"
            "        %r\n"
            "        the replacement is identical to the target, so nothing was mutated" % label)
    return out


def replace_regex_exactly_once(source, pattern, repl, label, flags=0):
    """The same contract for a pattern, for targets that must not be pinned to a literal.

    Chiefly the version declaration: a literal marker for it is wrong the day the version moves,
    which is the one day it matters.
    """
    rx = re.compile(pattern, flags)
    hits = rx.findall(source)
    if len(hits) != 1:
        raise MutationTargetError(
            "Mutation target failure:\n"
            "        %r\n"
            "        pattern %s\n"
            "        expected exactly 1 match\n"
            "        found %d" % (label, pattern, len(hits)))
    out = rx.sub(repl, source, count=1)
    if out == source:
        raise MutationTargetError(
            "Mutation target failure:\n"
            "        %r\n"
            "        the substitution left the source unchanged" % label)
    return out


class MutationRun:
    """Counts what happened, and decides whether the run is green.

    The distinction the summary exists to make is between a mutation that was applied and
    survived -- a real hole in the tests -- and one that was never applied at all, which tells you
    nothing about the tests and everything about the suite. Both are red. Only the first is
    interesting.
    """

    def __init__(self, name, total=None):
        self.name = name
        self.declared = total
        self.applied = 0
        self.caught = 0
        self.survived = []
        self.invalid = []
        # A few mutations are declared BENIGN: the page repairs the value on load, so breaking it
        # changes nothing observable and no test should fail. They are documentation of a repair,
        # and they must still be applied exactly once -- a benign mutation whose marker has gone
        # stale is just as blind as any other.
        self.benign_noop = []
        self.benign_caught = []
        self.crash_only = []

    def record_invalid(self, label, err):
        self.invalid.append(label)
        print("INVALID %-70s TARGET DID NOT RESOLVE" % label)
        for line in str(err).splitlines():
            print("        " + line if not line.startswith("        ") else line)

    def record(self, label, caught, detail="", extra=(), benign=False, crashed=False):
        """`crashed` means the checker died rather than reporting a verdict.

        A non-zero exit is how a mutation is normally judged caught, but a process that crashed
        never ran its assertions to a conclusion -- something threw and took the summary with it.
        That still shows the mutation is detectable, so it is not a survivor; it is weaker
        evidence than a named failing assertion, and it is worth knowing about, because a harness
        that crashes for a reason unrelated to the mutation would be scored as a catch.
        """
        self.applied += 1
        if benign:
            (self.benign_caught if caught else self.benign_noop).append(label)
            verdict = "EXTRA" if caught else "NO-OP"
        elif caught:
            self.caught += 1
            verdict = "CRASH" if crashed else "CAUGHT"
        else:
            self.survived.append(label)
            verdict = "SURVIVED"
        if caught and crashed:
            self.crash_only.append(label)
        print("%-8s %-70s %s" % (verdict, label, detail))
        for line in extra:
            print("         -> " + line)

    def report(self):
        declared = self.declared if self.declared is not None else self.applied + len(self.invalid)
        print("\n%s" % self.name)
        print("  mutations declared : %d" % declared)
        print("  mutations applied  : %d" % self.applied)
        print("  mutations caught   : %d" % self.caught)
        print("  mutations survived : %d" % len(self.survived))
        print("  invalid / stale    : %d" % len(self.invalid))
        if self.benign_noop or self.benign_caught:
            print("  benign no-ops      : %d (expected: the value is repaired on load)"
                  % len(self.benign_noop))
            for s in self.benign_caught:
                print("    EXTRA     %s -- declared benign but a test caught it" % s)
        if self.crash_only:
            print("  caught by crash    : %d (the checker died instead of reporting; the "
                  "mutation is detectable, but no named assertion says so)" % len(self.crash_only))
            for s in self.crash_only:
                print("    CRASH     %s" % s)
        for s in self.survived:
            print("    SURVIVED  %s" % s)
        for s in self.invalid:
            print("    INVALID   %s" % s)
        ok = not self.survived and not self.invalid and self.applied == declared
        if self.applied != declared and not self.invalid:
            print("  ** declared and applied disagree with nothing marked invalid: the loop "
                  "skipped a mutation without saying so")
        print("  RESULT: %s" % ("GREEN" if ok else "RED"))
        return 0 if ok else 1
