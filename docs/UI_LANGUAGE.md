# Interface language

The default interface language is **English**, including existing installations without a saved language preference. Chinese remains available through the language selector in Settings and the More menu in the listening workspace.

- Controls, open dialogs, and status labels update immediately; no restart is needed.
- The language preference is saved even when Remember key is disabled.
- ASR input language, provider/model IDs, reasoning settings, prompts, personal context, stored source transcripts, and generated answers do not change. Caption and answer languages have independent controls in the listening workspace.
- Existing speech records can be translated for display without modifying the saved originals. Provider errors and device names may retain their original language.

## Implementation

`localization.py` translates widgets associated with the application root. Display variables are separate from canonical configuration variables; combobox selections map back to stored values. `locale_catalog.py` contains the English display catalog. Editable text and generated responses are excluded from automatic translation.

Documentation, code comments, and docstrings use English. Chinese translation entries, compatibility keys, and multilingual test fixtures remain intentionally unchanged to preserve the bilingual interface and existing settings. These are runtime data, not developer commentary.


## Caption language

The listening workspace has separate **Transcript language** and **Answer language** selectors. They stay visible in the listening toolbar. Transcript language supports Original, English and Chinese; answer language supports English and Chinese. Changing interface language does not change either selection. Both are saved even when Remember key is disabled. Existing installations initially inherit the saved interface language; afterwards each preference is independent.

Finalized speech captions follow the selected transcript display language. Original displays the unmodified speech text and does not request translation. The ASR input language/model remains controlled by the existing audio settings.
Cross-language segments are translated asynchronously by the selected answer provider;
the HUD and transcript pane display the translated result. Translation has its own
request, adds provider usage, and never shares the answer conversation. Reported tokens
appear in the existing usage ledger. Same-language captions do not require a request.
Chinese passages may retain short English names and technical terms.

While cross-language speech is still a revisable draft, the display shows a localized
transcription status. Translation starts after the segment is finalized, so it adds
latency determined by the selected model. Missing configuration or translation failures
remain visible; changing the transcript language retries translations. Original speech
records, answer context and saved transcripts remain unchanged. Translation results are
cached for the current transcript language selection. Changing only the interface language keeps that cache.

Answer language is captured when an answer starts, including continuations, retries and document analysis. It is sent through API and local CLI transports. Changing it affects subsequent requests without rewriting history or interrupting active answers. Original speech remains available as model context regardless of caption display language.

Ctrl+mouse wheel adjusts reader font size and saves the preference. Mini mode keeps
Answer and Expand visible in both languages, and returning to Focus restores both panes.
Streaming Markdown formatting is coalesced and restricted to affected answer regions.
