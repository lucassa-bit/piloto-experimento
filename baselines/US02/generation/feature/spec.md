# Feature Specification: Nearby Recycling Facilities

**Feature Branch**: Baseline generation
**Created**: 2026-09-23
**Status**: Draft
**Input**: User Story: "As a user, I want to be able to enter my zip code and get a list of nearby recycling facilities, so that I can determine which ones I should consider."

## User Scenarios & Testing

### Primary User Story

As a user, I enter my ZIP code and receive a list of nearby recycling facilities so I can decide which facilities are worth considering.

### Acceptance Scenarios

1. **Given** a user provides a valid ZIP code in the supported service area, **When** they request nearby recycling facilities, **Then** the system shows facilities near that ZIP code sorted by proximity.
2. **Given** nearby facilities are available, **When** results are shown, **Then** each result includes enough information for the user to compare facilities, including facility name, address, distance, and available recycling details when known.
3. **Given** no nearby recycling facilities are found for the ZIP code, **When** the user submits the search, **Then** the system clearly explains that no nearby facilities were found and suggests trying a different ZIP code.
4. **Given** the user enters an invalid ZIP code, **When** they submit the search, **Then** the system asks for a valid ZIP code without showing misleading facility results.

### Edge Cases

- The ZIP code is empty, incomplete, or contains unsupported characters.
- The ZIP code is valid but outside the supported service area.
- Facility information is partially unavailable, such as unknown hours or accepted material types.
- Multiple facilities have the same distance from the searched ZIP code.
- The facility list is temporarily unavailable or cannot be refreshed.

## Requirements

### Functional Requirements

- **FR-001**: The system MUST allow the user to enter one ZIP code as the basis for a recycling facility search.
- **FR-002**: The system MUST validate that the submitted ZIP code is in an accepted ZIP code format before returning results.
- **FR-003**: The system MUST return nearby recycling facilities for a valid ZIP code when matching facilities are available.
- **FR-004**: The system MUST sort returned facilities by distance from the submitted ZIP code, with the nearest facility listed first.
- **FR-005**: The system MUST show, for each facility result, the facility name, address, and distance from the searched ZIP code.
- **FR-006**: The system SHOULD show available decision-support details for each facility, such as accepted materials, operating hours, phone number, website, and any access notes when that information is known.
- **FR-007**: The system MUST distinguish unavailable optional facility details from details that are known not to apply.
- **FR-008**: The system MUST clearly inform the user when no nearby facilities are found for the submitted ZIP code.
- **FR-009**: The system MUST clearly inform the user when the submitted ZIP code is invalid or outside the supported service area.
- **FR-010**: The system MUST avoid requiring the user to create an account or provide personal information beyond the ZIP code to complete the search.

### Key Entities

- **ZIP Code Search**: A user-submitted ZIP code used to identify a geographic search area for recycling facilities.
- **Recycling Facility**: A location that may accept recyclable materials and can be considered by the user. Key attributes include name, address, distance from the searched ZIP code, accepted materials, hours, contact information, website, and access notes.
- **Facility Result List**: The ordered set of recycling facilities returned for a ZIP code search, including empty and unavailable-result states.

## Assumptions

- "ZIP code" refers to a postal code format accepted by the product's supported region.
- "Nearby" means facilities within 25 miles of the submitted ZIP code unless the product later defines a different service radius.
- Facility results are intended to help users compare options, not to guarantee that a facility is open or accepts a material at the exact moment of search.
- When optional facility details are not available, the result remains usable as long as the facility name, address, and distance are shown.
- Users can search without signing in because the story only requires location-based lookup by ZIP code.

## Success Criteria

### Measurable Outcomes

- **SC-001**: At least 95% of valid supported ZIP code searches with available facilities show a facility list within 3 seconds.
- **SC-002**: 100% of facility result lists show facilities in nearest-first order.
- **SC-003**: 100% of facility results include name, address, and distance when facilities are returned.
- **SC-004**: At least 90% of users in validation testing can identify one facility to consider from the returned list without additional assistance.
- **SC-005**: 100% of invalid, empty, unsupported, or no-result ZIP code searches produce a clear message and do not show misleading facility results.
