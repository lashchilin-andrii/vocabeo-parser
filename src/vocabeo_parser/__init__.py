"""Scrape word data from Vocabeo into a delimited text file, one line per entry."""

import argparse
import re
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from playwright.sync_api import Page, Playwright, sync_playwright

BASE_URL = "https://vocabeo.com/browse/"
DEFAULT_SEPARATOR = "|"
ARTICLE_PATTERN = re.compile(r"^(der|die|das)[\s-]+(.*)$", re.IGNORECASE)


class PartOfSpeech(Enum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adj"
    ADVERB = "adv"
    PRONOUN = "pron"
    PREPOSITION = "prep"
    NUMBER = "num"
    CONJUNCTION = "conj"
    INTERJECTION = "inter"


@dataclass
class Sentence:
    german: str
    english: str


@dataclass
class Entry:
    word: str
    word_class: str | None
    pronunciation: str | None
    translations: list[str]
    sentences: list[Sentence]
    plural: str | None
    conjugations: str | None
    frequency: str | None
    level: str | None

    @classmethod
    def from_soup(cls, soup: BeautifulSoup, fallback_slug: str) -> "Entry":
        return cls(
            word=get_text(soup.find("h1")) or fallback_slug.replace("-", " "),
            translations=extract_translations(soup),
            sentences=extract_sentences(soup),
            conjugations=extract_conjugations(soup),
            **extract_facts(soup),
        )

    def to_line(self, separator: str = DEFAULT_SEPARATOR) -> str:
        columns = [
            self.word,  # 1: Word
            self.word_class,  # 2: Part of Speech
            self.pronunciation,  # 3: Pronunciation
            ", ".join(self.translations),  # 4: English Translations
            "",  # 5: Other Translations (intentionally blank)
            "<br><br>".join(f"{s.german} ({s.english})" for s in self.sentences),  # 6: Example Sentences
            self.plural,  # 7: Plural Form
            self.conjugations,  # 8: Conjugations
            self.frequency,  # 9: Frequency Level
            self.level,  # 10: CEFR Level
            "",  # 11: Word Sound (intentionally blank)
        ]
        return separator.join(column or "" for column in columns)


# --- HTML extraction -------------------------------------------------------


def get_text(element: Tag | None) -> str | None:
    return element.get_text(strip=True) if element is not None else None


def extract_facts(soup: BeautifulSoup) -> dict[str, str | None]:
    facts: dict[str, str | None] = {
        "word_class": None,
        "pronunciation": None,
        "plural": None,
        "frequency": None,
        "level": None,
    }
    facts_div = soup.find(id="facts")
    if facts_div is None:
        return facts

    facts["word_class"] = get_text(facts_div.find(id="facts-art"))

    plural_el = facts_div.find(id="facts-plural")
    plural_divs = plural_el.find_all("div") if plural_el is not None else []
    if plural_divs:
        facts["plural"] = get_text(plural_divs[min(1, len(plural_divs) - 1)])

    for child in facts_div.find_all("div", recursive=False):
        text = child.get_text(strip=True)
        emphasized = get_text(child.find(class_="emphasize"))

        if "Frequency" in text:
            if emphasized and emphasized.isdigit():
                facts["frequency"] = emphasized
        elif "Level" in text:
            facts["level"] = emphasized
        elif text.startswith("[") and text.endswith("]"):
            facts["pronunciation"] = text.replace("|", "")

    return facts


def extract_translations(soup: BeautifulSoup) -> list[str]:
    container = soup.find(id="en")
    if container is None:
        return []

    items = container.find_all(class_="translation") or container.find_all(["button", "a"])
    texts = (item.get_text(strip=True) for item in items)
    return [text for text in texts if text]


def extract_conjugations(soup: BeautifulSoup) -> str | None:
    container = soup.find(id="verb-conjugations")
    if container is None:
        return None

    spans = container.find_all("span")
    if spans:
        return " ".join("".join(span.stripped_strings) for span in spans)
    return "".join(container.stripped_strings)


def extract_sentences(soup: BeautifulSoup) -> list[Sentence]:
    container = soup.find(id="sentences")
    if container is None:
        return []

    sentences = []
    for block in container.find_all("div", class_="sentence"):
        german = ""
        parts = block.find("div", class_="sentence-parts")
        if parts is not None:
            german = "".join(span.get_text() for span in parts.find_all("span")).strip()

        english = ""
        translation = block.find("div", class_="sentence-translation")
        if translation is not None:
            raw = " ".join(translation.stripped_strings)
            english = re.sub(r'\s+([.,!?;:\'"])', r"\1", raw)

        if german or english:
            sentences.append(Sentence(german, english))

    return sentences


# --- Input handling --------------------------------------------------------


def normalize_term(term: str) -> str:
    """Turn user input into a Vocabeo slug: 'der hund' -> 'der-Hund', 'auf stehen' -> 'auf-stehen'."""
    cleaned = term.strip()
    match = ARTICLE_PATTERN.match(cleaned)
    if match is None:
        return re.sub(r"[\s_]+", "-", cleaned.lower())

    article = match.group(1).lower()
    first, *rest = re.split(r"[\s_]+", match.group(2).strip())
    return "-".join([article, first.capitalize(), *(word.lower() for word in rest)])


def build_urls(term: str) -> tuple[str, list[str]]:
    """Return (slug, candidate URLs) for a plain term or an explicit 'pos/slug' path."""
    if "/" in term and not term.startswith("http"):
        return term.split("/")[-1], [BASE_URL + term.strip("/")]

    slug = normalize_term(term)
    return slug, [f"{BASE_URL}{pos.value}/{slug}" for pos in PartOfSpeech]


def split_terms(raw: str) -> list[str]:
    """Split on commas if present, otherwise on lines."""
    items = raw.split(",") if "," in raw else raw.splitlines()
    return [item.strip() for item in items if item.strip()]


def read_terms(cli_terms: list[str]) -> list[str]:
    if cli_terms:
        return split_terms(" ".join(cli_terms))
    if not sys.stdin.isatty():
        return split_terms(sys.stdin.read())

    print("Enter words separated by commas:")
    return split_terms(input("> "))


# --- Paths -----------------------------------------------------------------


def app_dir() -> Path:
    """Folder containing the .exe (or this script when run from Python)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resolve_output_path(output: str | None) -> Path:
    """Default to a timestamped file next to the .exe; relative paths resolve against it too."""
    if not output:
        output = f"vocabeo_words_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
    return app_dir() / output


# --- Scraping --------------------------------------------------------------


def launch_browser(playwright: Playwright):
    """Prefer Microsoft Edge (preinstalled on Windows), fall back to bundled Chromium."""
    try:
        return playwright.chromium.launch(channel="msedge", headless=True)
    except Exception:
        return playwright.chromium.launch(headless=True)


def fetch_entries(page: Page, term: str) -> Iterator[Entry]:
    slug, urls = build_urls(term)
    for url in urls:
        try:
            page.goto(url, wait_until="networkidle")
            entry = Entry.from_soup(BeautifulSoup(page.content(), "html.parser"), slug)
        except Exception as error:
            print(f"Error parsing {url}: {error}\n", file=sys.stderr)
            continue

        if entry.word_class != "Article":
            yield entry


def scrape(terms: list[str], output_file: Path, separator: str) -> None:
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()

        with open(output_file, "w", encoding="utf-8") as file:
            for term in terms:
                for entry in fetch_entries(page, term):
                    file.write(entry.to_line(separator) + "\n")
                    file.flush()
                    print(entry.word, entry.word_class, entry.translations, sep=" | ")

        browser.close()


# --- CLI -------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Blindly scrape word data from Vocabeo across all POS endpoints."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Space or comma-separated list of word paths or terms",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output text file path (default: vocabeo_words_<datetime>.txt next to the exe)",
    )
    parser.add_argument(
        "-s",
        "--separator",
        default=DEFAULT_SEPARATOR,
        help="Field separator character",
    )
    return parser


def pause() -> None:
    """Keep the console window open when launched interactively (e.g. by double-click)."""
    if sys.stdin.isatty():
        input("Press Enter to exit...")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    terms = read_terms(args.paths)
    if not terms:
        parser.print_help()
        pause()
        sys.exit(1)

    output_path = resolve_output_path(args.output)
    scrape(terms, output_path, args.separator)

    print(f"File saved to {output_path}")
    pause()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Fatal error: {error}", file=sys.stderr)
        pause()
        sys.exit(1)