## What this changes

<!-- One or two sentences. -->

## Why

<!-- What was wrong, unclear, or missing. -->

## Checklist

- [ ] `cd backend && pytest` is green
- [ ] `cd frontend && npm run build` is green
- [ ] No result is faked — connectivity outcomes still come from the engine
- [ ] New engine behaviour has a test describing a mistake a learner could make
- [ ] New UI either works or is visibly marked as coming later
- [ ] Any new limitation is written down in the README

## If this adds a mission

- [ ] A test asserts the shipped topology fails and the fix makes it pass
- [ ] Hints go from a nudge to the answer
- [ ] Exactly one thing is broken
