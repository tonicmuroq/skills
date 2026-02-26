# Repository Analysis Report Template

Use this structure unless the user asks for a different format.
Sections 1-3 are required. Sections 4-5 are conditional.

## 1. This repo does what

- Summarize the repository's primary purpose in 2-4 sentences.
- Describe target users or systems.

Evidence:
- `path/to/file`: why this file supports the claim

## 2. Design and implementation approach

- Describe major components and their responsibilities.
- Explain how requests move through the system.
- Explain where and how data is validated, transformed, stored, and returned.

Evidence:
- `path/to/file`: key logic
- `path/to/file`: integration point

## 3. Notable implementation/design decisions worth learning

1. Decision title
   - Why it is good
   - Where it is implemented
2. Decision title
   - Why it is good
   - Where it is implemented

Evidence:
- `path/to/file`: concrete implementation detail

## 4. ASCII flow diagram (request + data) [Conditional]

Include this section only if the repo has meaningful multi-step request/data flow.
If not meaningful, write:
- `Skipped: no meaningful request/data flow for this repo.`

```text
Request flow:
[Client] -> [Entry/API Router] -> [Service Layer] -> [Data Access] -> [Database]
[Database] -> [Data Access] -> [Service Layer] -> [Entry/API Router] -> [Client]

Data flow:
[Input] -> [Validation] -> [Domain Logic] -> [Persistence] -> [Read Model/Output]
```

- Add a short explanation of each path.

## 5. Minimal usable example [Conditional]

Library determination:
- `Yes` or `No` with 1-2 reasons.

If `Yes` and example adds value, provide:
- minimal setup command(s)
- minimal import/use snippet
- expected output or behavior

If `No`, output:
- `Skipped: repo is application-oriented, not a reusable library API.`

If `Yes` but repo is extremely trivial (for example one pure function with obvious call pattern), output:
- `Skipped: usage is self-evident and example would be redundant.`

## Confidence and gaps

- Confirmed:
- Likely:
- Missing information:
