# Vocabeo Parser

A [Vocabeo.com](https://vocabeo.com) parser that creates Anki notes in `.txt` format.

Give it German words, and it scrapes each entry (part of speech, pronunciation, translations, example sentences, plural, conjugations, frequency and CEFR level) into a delimited text file you can import into Anki.

## Screenshots
 
<img width="761" height="636" alt="Screenshot 1" src="https://github.com/user-attachments/assets/0d033c10-c35f-4cbb-8504-d052809eee50" />
<img width="762" height="633" alt="Screenshot 2" src="https://github.com/user-attachments/assets/0bccfea5-2d9b-4f59-afa8-9ca364c57dc2" />


## Download (Windows)

Grab `vocabeo_parser.exe` from the [latest release](../../releases/latest).

**Requirements:** Windows 10/11 with Microsoft Edge (preinstalled) and an internet connection.

> Windows SmartScreen or your antivirus may warn about an unsigned exe. Click **More info → Run anyway**.

## Anki deck (required)
 
Also download the `.apkg` deck from the [latest release](../../releases/latest) and import it into Anki once (double-click the file, or **File → Import**).
 
**Why it's needed:** the deck contains the **Vocabeo Entry** note type. The parser writes 11 fields per word in a fixed order (see [Output format](#output-format)), and this note type has the matching fields and card templates. Without it, Anki has no note type that fits the `.txt` file. **Otherwise you would have to build one** with the same fields yourself before importing.


## Usage

**Double-click** the exe and enter words separated by commas:

```
gehen, der Hund, die Katze
```

**Command line:**

```bash
vocabeo_parser.exe gehen, der Hund -o words.txt
```

| Option | Description |
| --- | --- |
| `-o`, `--output` | Output file. Default: `vocabeo_words_<date>_<time>.txt` next to the exe. Relative paths are resolved next to the exe. |
| `-s`, `--separator` | Field separator. Default: `\|`. |

Words can also be piped in, one per line or comma-separated.

### Entering words

- **Nouns need their article** (`der`, `die`, `das`), e.g. `der Hund` or `der-Hund`.
- Verbs, adjectives and other words are entered as they are, e.g. `gehen`, `schnell`.
- Capitalization doesn't matter, `der hund` works too.
- To fetch one exact page, pass its path, e.g. `noun/der-Hund`.

Without a path, every part-of-speech page is tried for the word. Pages that don't exist are skipped.

## Output format

One line per entry, fields separated by `|`:

| # | Field |
| --- | --- |
| 1 | Word |
| 2 | Part of Speech |
| 3 | Pronunciation |
| 4 | English Translations |
| 5 | Other Translations (blank) |
| 6 | Example Sentences (separated by `<br><br>`) |
| 7 | Plural Form |
| 8 | Conjugations |
| 9 | Frequency Level |
| 10 | CEFR Level |
| 11 | Word Sound (blank) |

Fields 5 and 11 are intentionally empty so you can fill them with Anki add-ons or map them later.

> [!IMPORTANT]
> ## 🤖 AI-GENERATED
> **The code and all the descriptions are mostly written by AI.**
