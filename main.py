import argparse
import re
import sys
from dataclasses import dataclass, field
from enum import Enum

from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator, MyMemoryTranslator
from playwright.sync_api import sync_playwright


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
    image: str | None = None


@dataclass
class Entry:
    word: str = ""
    word_class: str | None = None
    frequency: int | None = None
    level: str | None = None
    pronunciation: str | None = None
    plural: str | None = None
    translations: list[str] = field(default_factory=list)
    translations_ru: list[str] = field(default_factory=list)
    conjugations: str | None = None
    sentences: list[Sentence] = field(default_factory=list)

    @classmethod
    def from_soup(cls, soup: BeautifulSoup, fallback_word: str) -> "Entry":
        h1 = soup.find("h1")
        word = (
            h1.get_text(strip=True) if h1 else fallback_word.replace("-", " ")
        )

        facts = cls.extract_facts(soup)
        english_translations = cls.extract_translations(soup)
        russian_translations = cls.translate_to_russian(english_translations)

        return cls(
            word=word,
            word_class=facts.get("word_class"),
            frequency=facts.get("frequency"),
            level=facts.get("level"),
            pronunciation=facts.get("pronunciation"),
            plural=facts.get("plural"),
            translations=english_translations,
            translations_ru=russian_translations,
            conjugations=cls.extract_verb_conjugations(soup),
            sentences=cls.extract_example_sentences(soup),
        )

    @staticmethod
    def extract_facts(soup: BeautifulSoup) -> dict:
        result = {
            "word_class": None,
            "frequency": None,
            "level": None,
            "pronunciation": None,
            "plural": None,
        }
        facts_div = soup.find(id="facts")
        if not facts_div:
            return result

        art_el = facts_div.find(id="facts-art")
        if art_el:
            result["word_class"] = art_el.get_text(strip=True)

        plural_el = facts_div.find(id="facts-plural")
        if plural_el:
            plural_divs = plural_el.find_all("div")
            if len(plural_divs) >= 2:
                result["plural"] = plural_divs[1].get_text(strip=True)
            elif len(plural_divs) == 1:
                result["plural"] = plural_divs[0].get_text(strip=True)

        for child in facts_div.find_all("div", recursive=False):
            text = child.get_text(strip=True)

            if "Frequency" in text:
                emphasize = child.find(class_="emphasize")
                if emphasize and emphasize.get_text(strip=True).isdigit():
                    result["frequency"] = int(emphasize.get_text(strip=True))

            elif "Level" in text:
                emphasize = child.find(class_="emphasize")
                if emphasize:
                    result["level"] = emphasize.get_text(strip=True)

            elif text.startswith("[") and text.endswith("]"):
                result["pronunciation"] = text

        return result

    @staticmethod
    def extract_translations(soup: BeautifulSoup) -> list[str]:
        target_element = soup.find(id="en")
        if not target_element:
            return []

        items = target_element.find_all(class_="translation")
        if not items:
            items = target_element.find_all(["button", "a"])

        return [
            item.get_text(strip=True)
            for item in items
            if item.get_text(strip=True)
        ]

    @staticmethod
    def translate_to_russian(translations: list[str]) -> list[str]:
        if not translations:
            return []

        joined_english = ", ".join(translations)

        # Try Google first, fall back to MyMemory if blocked
        try:
            translated_text = GoogleTranslator(source="en", target="ru").translate(joined_english)
        except Exception:
            try:
                translated_text = MyMemoryTranslator(source="en-US", target="ru-RU").translate(joined_english)
            except Exception as e:
                print(f"Warning: Russian translation failed: {e}", file=sys.stderr)
                return []

        raw_items = [
            item.strip()
            for item in translated_text.split(",")
            if item.strip()
        ]

        seen = set()
        unique_items = []
        for item in raw_items:
            item_lower = item.lower()
            if item_lower not in seen:
                seen.add(item_lower)
                unique_items.append(item)

        return unique_items

    @staticmethod
    def extract_verb_conjugations(soup: BeautifulSoup) -> str | None:
        target_element = soup.find(id="verb-conjugations")
        if not target_element:
            return None

        spans = target_element.find_all("span")
        if spans:
            parts = ["".join(span.stripped_strings) for span in spans]
            return " ".join(parts)

        return "".join(target_element.stripped_strings)

    @staticmethod
    def extract_example_sentences(soup: BeautifulSoup) -> list[Sentence]:
        target_element = soup.find(id="sentences")
        if not target_element:
            return []

        sentences = []
        blocks = target_element.find_all("div", class_="sentence")

        for block in blocks:
            parts_div = block.find("div", class_="sentence-parts")
            german_text = ""
            if parts_div:
                parts = [part.get_text() for part in parts_div.find_all("span")]
                german_text = "".join(parts).strip()

            translation_div = block.find("div", class_="sentence-translation")
            english_text = ""
            if translation_div:
                raw_translation = " ".join(translation_div.stripped_strings)
                english_text = re.sub(
                    r'\s+([.,!?;:\'"])', r"\1", raw_translation
                )

            img_tag = block.find("img")
            img_url = (
                img_tag["src"] if img_tag and img_tag.has_attr("src") else None
            )

            if german_text or english_text:
                sentences.append(
                    Sentence(
                        german=german_text,
                        english=english_text,
                        image=img_url,
                    )
                )

        return sentences

    def to_txt_line(self, separator: str = "|") -> str:
        formatted_sentences = "<br><br>".join(
            [f"{s.german} ({s.english})" for s in self.sentences]
        )

        fields = [
            self.word or "",
            self.word_class or "",
            str(self.frequency) if self.frequency is not None else "",
            self.level or "",
            self.pronunciation or "",
            self.plural or "",
            ", ".join(self.translations),
            self.conjugations or "",
            formatted_sentences,
            ", ".join(self.translations_ru),
        ]

        return separator.join(fields)


def normalize_term(term: str) -> str:
    cleaned = term.strip()

    # Ищем артикли der/die/das, отделенные пробелом или тире
    match = re.match(r"^(der|die|das)[\s-]+(.*)$", cleaned, flags=re.IGNORECASE)

    if match:
        article = match.group(1).lower()
        word = match.group(2).strip()

        # Заменяем пробелы внутри существительного на тире и капитализируем
        word_parts = re.split(r"[\s_]+", word)
        word_capitalized = "-".join(
            [word_parts[0].capitalize()] + [w.lower() for w in word_parts[1:]]
        )

        return f"{article}-{word_capitalized}"
    else:
        # Для глаголов и других частей речи (например, "gehen" или "auf-stehen")
        return re.sub(r"[\s_]+", "-", cleaned.lower())


def parse_vocabeo_input(
    paths: list[str],
    output_file: str = "vocabeo_words.txt",
    separator: str = "|",
    base_url: str = "https://vocabeo.com/browse/",
):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        with open(output_file, "w", encoding="utf-8") as file:
            for raw_path in paths:
                if "/" in raw_path and not raw_path.startswith("http"):
                    targets = [f"{base_url}{raw_path.strip('/')}"]
                    clean_slug = raw_path.split("/")[-1]
                else:
                    clean_slug = normalize_term(raw_path)
                    targets = [
                        f"{base_url}{pos.value}/{clean_slug}"
                        for pos in PartOfSpeech
                    ]

                for url in targets:
                    try:
                        page.goto(url, wait_until="networkidle")
                        soup = BeautifulSoup(page.content(), "html.parser")

                        entry = Entry.from_soup(soup, fallback_word=clean_slug)

                        if entry.word_class == "Article":
                            continue

                        line = entry.to_txt_line(separator=separator)

                        file.write(line + "\n")
                        file.flush()
                        print(line)

                    except Exception as e:
                        print(f"Error parsing {url}: {e}\n", file=sys.stderr)

        browser.close()


def main():
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
        default="vocabeo_words.txt",
        help="Output text file path",
    )
    parser.add_argument(
        "-s",
        "--separator",
        default="|",
        help="Field separator character",
    )

    args = parser.parse_args()

    input_paths = []

    if args.paths:
        raw_joined = " ".join(args.paths)
        # Разбиваем входные данные по запятым
        raw_items = raw_joined.split(",")
        for item in raw_items:
            cleaned_item = item.strip()
            if cleaned_item:
                input_paths.append(cleaned_item)

    elif not sys.stdin.isatty():
        raw_input = sys.stdin.read()
        raw_items = raw_input.split(",") if "," in raw_input else raw_input.splitlines()
        for item in raw_items:
            cleaned_item = item.strip()
            if cleaned_item:
                input_paths.append(cleaned_item)

    if not input_paths:
        parser.print_help()
        sys.exit(1)

    parse_vocabeo_input(
        paths=input_paths, output_file=args.output, separator=args.separator
    )

if __name__ == "__main__":
    main()