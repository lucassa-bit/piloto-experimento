# Feature Specification: Simultaneous Estimate Reveal

**Feature Branch**: Not used (baseline generation mode)

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "As a participant, I want to be shown all estimates at the same time after all estimators have given their estimate, so that I can be sure estimates are independent and not influenced by other estimates given in the same draw."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reveal Estimates Together (Priority: P1)

A participant waits while estimators independently submit estimates for the current draw. Once every estimator required for that draw has submitted, the participant sees all submitted estimates revealed together at the same time.

**Why this priority**: This is the core feature value: participants need confidence that estimates were not influenced by seeing other estimates earlier in the same draw.

**Independent Test**: Can be fully tested by running a draw with multiple estimators, confirming that no submitted estimate is visible before all required estimators have submitted, and confirming that all submitted estimates become visible together once the final required estimate is submitted.

**Acceptance Scenarios**:

1. **Given** a draw with multiple required estimators and no estimator has submitted yet, **When** one estimator submits an estimate, **Then** the participant cannot see that estimate or any other hidden estimate.
2. **Given** a draw where all but one required estimator have submitted estimates, **When** the final required estimator submits, **Then** the participant is shown every estimate for that draw at the same time.
3. **Given** a draw where estimates have been revealed, **When** the participant views the draw results, **Then** the participant sees the complete set of estimates together, with no indication that any estimate was revealed earlier than another.

---

### Edge Cases

- If no estimators are assigned to a draw, no estimate reveal occurs and the participant is informed that there are no estimates to show.
- If at least one required estimator has not submitted, submitted estimates remain hidden from the participant.
- If an estimator changes or resubmits an estimate before reveal, only that estimator's final submitted estimate for the draw is included in the simultaneous reveal.
- If an estimator attempts to submit after estimates have already been revealed, the late estimate is not added to the revealed set for that draw.
- If two or more final submissions happen nearly at the same time, the participant still sees a single complete reveal event for the draw.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST keep estimates hidden from participants until every required estimator for the draw has submitted an estimate.
- **FR-002**: The system MUST reveal all estimates for a draw together once every required estimator has submitted an estimate.
- **FR-003**: The system MUST prevent participants from seeing partial estimate results for a draw before the simultaneous reveal condition is met.
- **FR-004**: The system MUST determine reveal readiness separately for each draw.
- **FR-005**: The system MUST include exactly one estimate per required estimator in the revealed result set for a draw.
- **FR-006**: The system MUST use the latest submitted estimate from each estimator when reveal occurs, when changes before reveal are allowed by the surrounding estimation workflow.
- **FR-007**: The system MUST leave revealed estimates visible together after reveal so participants can review the completed draw results.
- **FR-008**: The system MUST clearly communicate to the participant when estimates are still waiting on one or more estimator submissions.

### Key Entities

- **Draw**: A single estimation round in which estimators provide estimates independently before results are revealed.
- **Estimator**: A person whose estimate is required for the draw before the reveal can occur.
- **Estimate**: A submitted value from an estimator for a draw; only the final submitted value before reveal is shown.
- **Participant**: A person viewing the estimates for a draw and relying on simultaneous reveal to confirm independence.
- **Reveal State**: The draw's visibility condition, either waiting for required estimates or revealed to participants.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of draws with required estimators, participants cannot view any submitted estimate before every required estimator has submitted.
- **SC-002**: In 100% of completed draws, all estimates become visible to the participant as a single complete result set after the final required estimate is submitted.
- **SC-003**: Participants can correctly identify whether a draw is still waiting for estimates or has revealed estimates in 95% of validation attempts.
- **SC-004**: In validation sessions with at least three estimators, no participant observes a partial estimate result before the simultaneous reveal.
- **SC-005**: 90% of participants report that the reveal behavior makes the estimates feel independent within the same draw.

## Assumptions

- A draw has a known set of required estimators before reveal readiness is evaluated.
- The participant is not allowed to see any individual estimate for the draw before all required estimates are submitted.
- Estimates may be submitted in any order, but reveal happens only after the complete required set exists.
- The surrounding estimation workflow defines whether estimators can revise estimates before reveal; if revisions are allowed, the latest pre-reveal submission is authoritative.
- This feature covers participant visibility of estimates, not how estimators are invited, authenticated, reminded, or timed out.
