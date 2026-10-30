# LearnLyt – Intelligent Knowledge Retention Tool

LearnLyt is a local study application that turns subjects and notes into scheduled flashcard reviews. It uses a spaced-repetition algorithm to show difficult information more frequently and delay well-remembered information, helping students build long-term retention.

## Features

- Create, update and delete subjects, topics and flashcards.
- Organize topics by subject, category and difficulty.
- Search and filter the knowledge library.
- Run active-recall review sessions.
- Rate answers as Again, Hard, Good or Easy.
- Automatically schedule the next review using an SM-2-inspired algorithm.
- Measure overall, subject and topic retention.
- Identify weak topics through progress reports.
- Store all learning data permanently in SQLite.
- Export and restore subjects, cards, schedules and history using JSON.
- Load safe demonstration data from the dashboard.
- Use the responsive interface on desktop or mobile browsers.

## Technology

- **Python and Flask:** application logic and controllers
- **HTML, CSS and JavaScript:** responsive user interface
- **SQLite:** persistent relational database
- **JSON:** portable backup, restore and demonstration data

## Project structure

```text
LearnLyt/
├── app.py                  # Flask routes and validation
├── database.py             # SQLite CRUD, analytics and backup
├── retention.py            # Spaced-repetition algorithm
├── templates/              # HTML interface
├── static/                 # CSS and JavaScript
├── sample_data/            # Importable demonstration backup
├── tests/                  # Automated tests
└── data/                   # Runtime SQLite database
```

## Run on macOS

Open Terminal inside the `LearnLyt` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 app.py
```

Open <http://127.0.0.1:5000>.

On the empty dashboard, click **Load demo data** to create two subjects, three topics and six due flashcards.

## Run automated tests

```bash
python3 -m unittest discover -s tests -v
```

## How spaced repetition works

Each card stores its interval, repetition count, ease factor and next review date. A forgotten card returns the next day. Successfully remembered cards progress from one day to six days and then to increasingly longer intervals. Ratings also adjust the ease factor, so difficult cards return sooner.

## Responsible data handling

LearnLyt runs locally. Notes and progress stay in the SQLite database on the same computer unless the user explicitly downloads a JSON backup.
