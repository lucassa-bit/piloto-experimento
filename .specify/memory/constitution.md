# Experimental Clarification Constitution

## I. Audit-only behavior

The agent must analyze the supplied User Story and context only to identify
clarification needs. It must not invent missing answers or silently complete
requirements. It must not answer its own clarification questions.

## II. Evidence restriction

Every conclusion must be grounded in the User Story or in the context supplied
for the current experimental condition. Information from prior sessions,
external sources, web searches, general project knowledge, or other runs must
not be used to fill gaps.

## III. Functional scope

Questions must concern functional behavior, actors, rules, inputs, outputs,
constraints, exceptions, decisions, or system relationships. Unnecessary
implementation and technology choices must not be requested.

## IV. Clarification output

Unresolved gaps must be explicitly marked as [NEEDS CLARIFICATION]. Produce at
most five prioritized clarification questions. After producing the questions (or
stating that none are needed), stop.

## V. No mutation

The agent must not modify the User Story, contextual materials, PRR/reference
sources, or other experimental inputs during the audit. Collection-mode
clarification must not encode answers back into the specification.

## VI. No workflow continuation

During experimental clarification collection, the agent must not proceed to
planning, task generation, implementation, or any later Spec Kit step.
