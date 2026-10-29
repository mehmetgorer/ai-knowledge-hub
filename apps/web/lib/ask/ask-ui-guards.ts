/** Pure guards for Ask AI race and stale-result avoidance. */

export type AskViewStateKind =
  | "idle"
  | "loading"
  | "ready"
  | "error";

export function shouldDisplayAskState(input: {
  askStateKind: AskViewStateKind;
  askCollectionId: string | undefined;
  selectedCollectionId: string;
  currentQuestionTrimmed: string;
  submittedQuestionTrimmed: string;
}): boolean {
  if (input.askStateKind === "idle") {
    return false;
  }
  if (
    !input.askCollectionId ||
    input.askCollectionId !== input.selectedCollectionId
  ) {
    return false;
  }
  if (input.currentQuestionTrimmed !== input.submittedQuestionTrimmed) {
    return false;
  }
  return true;
}

export function shouldDisableAskSubmit(input: {
  collectionSelected: boolean;
  questionValid: boolean;
  inFlight: boolean;
}): boolean {
  return (
    !input.collectionSelected || !input.questionValid || input.inFlight
  );
}

export function askGroundingStatusLabel(grounded: boolean): string {
  if (grounded) {
    return "Citations passed structural validation (not fact-checked).";
  }
  return "Not supported by verified citations.";
}
