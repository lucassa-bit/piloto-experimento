# Feature Specification: Join Game by Name

**Feature Branch**: `N/A - baseline generation`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "As an estimator, I want to join a game by entering my name on the page I received the URL for, so that I can participate."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Join a Received Game (Priority: P1)

An estimator opens the game page from the URL they received, enters their name, and joins the game as a participant.

**Why this priority**: This is the entry point for estimator participation; without it, the estimator cannot take part in the game.

**Independent Test**: Can be fully tested by opening a valid game URL, entering a valid name, submitting the join action, and confirming the estimator is accepted into that game.

**Acceptance Scenarios**:

1. **Given** an estimator opens a valid game URL, **When** they enter a valid name and submit it, **Then** they are joined to the game and can participate.
2. **Given** an estimator opens a valid game URL, **When** they view the page before joining, **Then** the page provides a clear way to enter their name and join.
3. **Given** an estimator has joined a game, **When** the join completes, **Then** the estimator receives confirmation that they are participating in the intended game.

---

### Edge Cases

- The estimator submits the join form without entering a name.
- The estimator enters a name that is only whitespace.
- The estimator opens a URL that does not identify a joinable game.
- The estimator attempts to join after the game is no longer accepting participants.
- The estimator submits the join action more than once from the same page.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow an estimator who opens a valid received game URL to view a join page for that game.
- **FR-002**: System MUST provide a name entry field on the join page before the estimator participates.
- **FR-003**: System MUST require a non-empty estimator name before allowing the estimator to join.
- **FR-004**: System MUST reject names that contain only whitespace and explain that a name is required.
- **FR-005**: System MUST allow the estimator to submit a valid name to join the game associated with the received URL.
- **FR-006**: System MUST add the estimator as a participant in the game after a valid join submission.
- **FR-007**: System MUST show the estimator a confirmation or participating state after they successfully join.
- **FR-008**: System MUST show a clear error state when the received URL does not identify a joinable game.
- **FR-009**: System MUST show a clear error state when the game is no longer accepting participants.
- **FR-010**: System MUST avoid creating duplicate participant entries from repeated submissions of the same join attempt.

### Key Entities *(include if feature involves data)*

- **Estimator**: A participant who joins a game using the received URL and a display name.
- **Game**: The session identified by the received URL that estimators can join.
- **Participation**: The association between an estimator display name and a game, representing that the estimator can participate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 95% of estimators with a valid game URL and valid name can complete joining in under 30 seconds.
- **SC-002**: 100% of empty or whitespace-only name submissions are blocked before participation begins.
- **SC-003**: 100% of successful joins associate the estimator with the game identified by the received URL.
- **SC-004**: At least 90% of first-time estimators can complete the join flow without assistance in usability validation.

## Assumptions

- The received URL identifies the game the estimator intends to join.
- The estimator's entered name is used as their display name within the game.
- A valid name is any non-empty, non-whitespace text value acceptable for display to other participants.
- Joining the game is complete once the estimator is recorded as a participant and sees confirmation that they can participate.
- Creating or sending the game URL is outside the scope of this feature.
- Gameplay after the estimator has joined is outside the scope of this feature.
