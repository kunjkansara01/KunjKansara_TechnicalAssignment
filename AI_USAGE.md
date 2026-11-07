# AI assistance disclosure

Tool used — OpenAI Codex.

Codex read and summarized the supplied assignment, designed the Flask/MySQL application, generated the Python, JavaScript, HTML, CSS, SQL, automated tests and documentation, and ran the available checks. The user requested a complete implementation in two phases.

Representative prompts supplied by the user were “I have to complete this assignment first give me summary” and “I want to you start building this project in 2 phase complete the assignment”.

Generated code was reviewed against the assignment requirements and exercised through API tests for calculations, rollback, repeated requests, access controls, CSV validation and reporting. Actual test outcomes and any remaining verification gaps are recorded in `docs/VERIFICATION.md`.

Review decisions included retaining saved item rates when editing drafts, ensuring stock edits always create movements, aggregating customer reports before joining customers, and locking the order before product rows. The implementation and test results should be reviewed personally by the candidate before submission. This disclosure does not claim the candidate independently authored or already understands every line.

A final review corrected oversized quantity handling so malformed input returns a validation error. The customer selector received an explicit accessible label during browser verification. Python and frontend code were formatted for readability. The supplied demo was recorded automatically against the live local application with explanatory captions and no narration.
