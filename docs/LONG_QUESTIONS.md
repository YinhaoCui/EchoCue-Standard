# Long questions and Quick Q&A

Choose **Question mode** in the listening workspace or audio settings. New installations and settings without this field default to **Long question**.

## Long question

Keep speaking through pauses. Finalized segments accumulate locally without triggering candidate answers. Select Answer (or its configured shortcut) when the question is complete. The request waits for audio captured before that click to finish transcription and uses the complete transcript snapshot, reference material and enabled conversation history. Later speech belongs to subsequent requests; existing answers continue.

The model is instructed to distinguish background, examples, constraints and the final request, honor explicit corrections, and lead with a conclusion or approach before details. This is an instruction, not a guarantee of model accuracy. No summary replaces the original transcript and no new application truncation is added. Provider context-window limits still apply.

Context preparation and incremental updates continue to use the existing retained-session path. This mode does not make a paid summarization call for every speech segment or continuously upload unfinished speech. Reference preparation happens on Prepare; new transcript content is sent on Answer. This avoids paying for intermediate interpretations of incomplete questions.

## Quick Q&A

Allows the existing prediction policy (questions only, every finalized segment, or off). A prediction is adopted only if the request snapshot matches. Switching question mode discards unclaimed predictions, never an explicitly submitted answer. Predictions can consume tokens even when discarded.

The mode is independent of transcript language, answer language and reasoning effort. Save settings to persist it. Complete code remains available; there is no forced short-answer cutoff. Neither mode promises subsecond cloud latency.

## Validation

Regression coverage checks prediction suppression, mode switching without cancelling explicit work, preservation of a long original input, independent request snapshots, and exclusion of answer-specific instructions from caption/analysis requests. Existing prediction tests explicitly select Quick Q&A. These are local behavioral tests, not new account-backed latency measurements; see the dated release validation report for the previous live measurements.
