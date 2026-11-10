# Samhitha — User Stories #4 and #13

This README documents the two Project 3 user stories assigned to Samhitha and explains what is currently implemented, what behavior is temporary, and what still needs to be integrated with the team's RAG backend and dataset pipeline.

---

## Story #4: Source Citations

### User Story

> As an End User, I want to see which documents or sources were used to generate an answer, so I can verify the response.

### What I implemented

The `/chat/` page currently includes:

- A natural-language question input
- A grounded-response section
- A **Sources used** section directly below the answer
- Citation cards for each source
- Source title
- Publisher / source name
- Disaster label
- Published/source date when available
- Supporting excerpt / description
- Clickable link to the original source
- Duplicate source removal
- A safe empty state if no valid source metadata is returned
- Logic that does **not fabricate citations** when required source information is missing
- Responsive styling so the citation cards work on smaller screens

The citation rendering and validation logic is implemented in `relief/services.py` and the user-facing citation cards are rendered in `relief/templates/relief/chat.html`.

---

## Why the Story #4 responses currently look the way they do

The current chatbot answer is **temporary demo behavior**.

The project does not yet have the team's final RAG retrieval/generation backend connected to this branch. Because the citation UI still needed to be built and tested, `relief/services.py` currently contains a temporary `ask_rag()` function.

That function returns prewritten demo responses using the four articles selected by the team for Project 3.

Current temporary behavior:

- If the question contains words such as **"Texas"** or **"flood"**, the demo function returns a Texas Hill Country flood response and uses the team's Texas sources.
- Otherwise, the demo function falls back to a Hurricane Helene response and uses the team's Hurricane Helene sources.

Because of this fallback, a question that is outside the current disaster dataset, such as:

> "Will there be severe weather soon?"

may still return a Hurricane Helene response.

That does **not** mean the final chatbot is intended to answer unrelated questions that way. It only happens because the current `ask_rag()` implementation is a placeholder that allows the citation UI to be demonstrated before the full RAG backend is integrated.

### Current demo sources

The temporary Story #4 response uses the articles already selected by the team:

**Hurricane Helene**
- ProPublica — *The Fight to Get FEMA Aid After Hurricane Helene in Hardest-Hit North Carolina Counties*
- WNCW — *Hurricane Helene Aftermath Updates and Resources*

**Texas Hill Country Floods**
- Associated Press — *What to know about the flash floods in Texas that killed over 100 people*
- The Texas Tribune — *Texas Hill Country floods: What we know so far*

These are currently used only to demonstrate how the final answer and citation cards should look.

---

## What needs to change for Story #4 to be fully functional

The citation UI itself does **not** need to be rewritten.

The temporary function:

```python
ask_rag(question)
```

inside:

```text
relief/services.py
```

needs to be replaced or connected to the team's real RAG pipeline.

The final RAG backend should:

1. Receive the user's question.
2. Search the team's curated disaster dataset.
3. Retrieve the most relevant document chunks.
4. Generate an answer grounded in those retrieved chunks.
5. Return the answer together with metadata for the exact sources that were used.
6. Pass that response to the existing Story #4 citation UI.

### Backend contract

The teammate RAG function should return data in this general format:

```python
{
    "answer": "Generated answer based on retrieved disaster documents...",
    "sources": [
        {
            "title": "Source title",
            "url": "https://...",
            "source_name": "Publisher",
            "published_date": "YYYY-MM-DD",
            "excerpt": "Retrieved supporting text",
            "disaster": "Hurricane Helene"
        }
    ]
}
```

`normalize_rag_response()` in `relief/services.py` already converts this structure into the citation cards used by the page.

### Team integration responsibilities

Based on the Sprint 1 responsibilities defined in the team proposal:

- **Anish** is responsible for dataset definition/update, ingestion methods, and cleaning/preprocessing.
- **Aditya** is responsible for grounded RAG answers and shares Story #4 source-citation integration.
- **Samhitha** is responsible for the Story #4 front-end citation display and integration-ready response handling.

Once the real RAG backend exists, the team should connect it where the temporary `ask_rag()` function is currently used.

The final flow should be:

```text
User question
    ↓
Real RAG backend
    ↓
Retrieve relevant chunks from curated dataset
    ↓
Generate grounded answer
    ↓
Return answer + exact source metadata
    ↓
normalize_rag_response()
    ↓
Story #4 citation cards
```

---

## Story #13: Prioritized Resource Finder

### User Story

> As an End User, I want to enter my location, urgent need, and key constraints so the system can return a prioritized list of nearby verified resources with source dates and eligibility notes, so I can act quickly without searching multiple websites.

### What I implemented

The `/find-help/` page currently includes:

- Location input
- Urgent need selection
- Constraint checkboxes
- Deterministic resource ranking
- Verified-resource badge
- Source date
- Eligibility information
- Explanation of why a resource matched
- Link to the source/original page
- Clear no-results state
- Responsive layout

Current need categories include:

- Housing / shelter
- Food / water
- Financial assistance
- Transportation
- Medical support
- Documents / recovery paperwork

Current constraints include:

- Pet friendly
- Accessible
- No car / transportation needed
- Family friendly

---

## Where the Story #13 dataset is

The current resource dataset is stored in:

```text
relief/data/resources.json
```

Each resource contains information such as:

```json
{
  "name": "Western North Carolina Recovery Housing Resources",
  "city": "Asheville",
  "state": "NC",
  "region": "Western North Carolina",
  "need": "housing",
  "constraints": [
    "accessible",
    "family",
    "pet_friendly"
  ],
  "verified": true,
  "description": "Recovery information for residents seeking temporary housing.",
  "eligibility": "Availability and program eligibility vary by provider.",
  "source_date": "2024-10-15",
  "source_url": "https://..."
}
```

The current file is a **small temporary/sample resource dataset** used so Story #13 can be developed and demonstrated before the team's full data pipeline is available.

It currently contains sample resources centered mainly around:

- Asheville / Western North Carolina
- Kerrville / Texas Hill Country

Because of that, searching for something such as:

```text
Atlanta, GA
Housing / shelter
```

currently returns:

```text
No matching verified resources
```

This is expected with the current sample data because there is no Atlanta housing resource stored in `resources.json`.

---

## How Story #13 currently ranks resources

The ranking logic is in:

```text
relief/services.py
```

inside:

```python
find_resources(...)
```

The current ranking considers:

1. **Need category**
   - A resource must match the selected urgent need.

2. **Location relevance**
   - Resources matching the searched city/state/region receive a strong ranking boost.
   - Resources outside the requested area are not treated as nearby matches.

3. **Verified status**
   - Verified resources receive a ranking boost.

4. **Constraint matches**
   - Resources that support selected constraints such as accessibility, pet friendliness, family support, or transportation needs receive additional ranking points.

5. **Missing constraint support**
   - Resources that do not match all selected constraints can rank lower than stronger matches.

6. **Source date**
   - Source date can be used as a tie-breaker so more recent information is preferred when other ranking factors are similar.

Each displayed result also includes a **Why it matched** field so the user can understand why the system ranked that resource.

---

## Why Story #13 is currently temporary

The feature itself works, but the resource dataset is intentionally limited.

The final system should eventually use a larger and more current set of disaster recovery resources rather than relying only on the small manually created `resources.json` file.

The temporary dataset exists so the following can already be implemented and tested:

- Search form behavior
- Filtering
- Ranking
- Constraint handling
- Result presentation
- Source-date display
- Eligibility display
- Verified-source presentation
- No-results behavior

Once the team's data ingestion and preprocessing pipeline is complete, the resource finder can either:

1. Receive a larger generated/curated resource dataset, or
2. Be connected to the team's shared backend/database instead of reading only from the local JSON file.

The UI and ranking behavior can remain mostly the same even when the source of the data changes.

---

## What needs to change for Story #13 to be fully complete

To move from the current demo dataset to the final Project 3 implementation:

### Dataset / backend work

The team needs to expand or replace:

```text
relief/data/resources.json
```

with a larger set of verified disaster recovery resources.

That dataset should include:

- Location
- Need/category
- Constraints
- Verification/source information
- Eligibility requirements
- Source date
- Original URL
- Description
- Any additional metadata needed for ranking

Because the Sprint 1 proposal assigns dataset definition, ingestion, and preprocessing work to Anish, the final shared dataset/backend produced from that work can eventually feed Story #13.

### Samhitha's Story #13 work

The Story #13 front end and ranking behavior are already implemented.

My portion is responsible for:

- Collecting the user's search criteria
- Calling the resource ranking logic
- Displaying the prioritized resources
- Showing source date and eligibility
- Explaining why each resource matched
- Providing the original source link
- Handling no-result searches
- Keeping the UI responsive and consistent with the ReliefRoute design

---

## Story #4 vs Story #13 data

These two features currently use data differently.

### Story #4

Current source:

```text
Temporary demo responses inside relief/services.py
```

Final source:

```text
Real RAG retrieval + generation backend
```

The RAG backend should return the exact source metadata used to create each answer.

### Story #13

Current source:

```text
relief/data/resources.json
```

Final source:

```text
Expanded curated resource data or the team's shared backend/database
```

Story #13 does not need to generate an LLM answer to rank resources. It can use structured resource metadata and deterministic ranking.

---

## Important integration rule

Do **not** rewrite the Story #4 citation UI when the real RAG backend is ready.

Instead, connect the real backend to the existing response format.

Similarly, Story #13 does not require replacing the front-end page when more data becomes available. The dataset/backend can be expanded while keeping the existing form, ranking result structure, and presentation.

---

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/chat/
```

for Story #4.

Open:

```text
http://127.0.0.1:8000/find-help/
```

for Story #13.

---

## Files Samhitha owns

- `relief/forms.py`
- `relief/services.py`
- `relief/views.py`
- `relief/urls.py`
- `relief/tests.py`
- `relief/data/resources.json`
- `relief/templates/relief/home.html`
- `relief/templates/relief/chat.html`
- `relief/templates/relief/resource_finder.html`
- `static/relief/styles.css`

Top-level Django files are included only because the repository was empty when this starter was created.

---

## Current status summary

### Story #4

**Working now**
- Citation cards
- Source metadata display
- Original source links
- Citation deduplication
- Safe handling of incomplete citations
- Responsive front-end

**Temporary**
- `ask_rag()` answer generation
- Hardcoded/demo source selection
- No vector retrieval yet

**Needs teammate integration**
- Curated dataset ingestion
- Vector retrieval / relevant chunk retrieval
- Real grounded response generation
- Passing real source metadata into the existing Story #4 interface

### Story #13

**Working now**
- Resource search form
- Need filtering
- Location matching
- Constraint handling
- Prioritized ranking
- Verified status
- Source date
- Eligibility
- Why-it-matched explanation
- Source links
- No-results behavior
- Responsive front-end

**Temporary**
- Small local `resources.json` dataset
- Limited supported locations/resources

**Needs later integration**
- Expanded current/verified recovery resource dataset
- Optional connection to the team's shared backend/database
