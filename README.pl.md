# Generator napisów (Subtitle Generator)

[English](README.md) · **Polski**

Generator napisów tworzy napisy z nagrań wideo i audio oraz tłumaczy je na inne języki. Obsługuje formaty SRT, WebVTT i ASS, a także transkrypcję w postaci zwykłego tekstu.

## Funkcje

- **Rozpoznawanie mowy** lokalnie, modelem Whisper ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)). W systemach Windows i Linux z akceleracją GPU (NVIDIA CUDA), w macOS na procesorze.
- **Podział na napisy** na granicach zdań i fraz, z wyrównaną długością linii i minimalnym czasem wyświetlania.
- **Korekta transkrypcji** (opcjonalna) przez model językowy: poprawa błędnie rozpoznanych słów, nazw własnych i interpunkcji, bez zmiany czasów napisów.
- **Tłumaczenie** przez Claude (CLI lub API), Codex CLI, OpenAI API, lokalne modele w Ollamie, dowolne API zgodne z OpenAI (np. OpenRouter, LM Studio) lub DeepL. Czasy napisów pozostają bez zmian.
- **Interfejs graficzny i wiersz poleceń** w systemach Windows, macOS i Linux. Interfejs w języku polskim i angielskim.

## Wymagania

| Składnik | Wymaganie |
|---|---|
| Python | 3.10–3.13 ([python.org](https://www.python.org/downloads/)) |
| Miejsce na dysku | do ok. 6 GB (biblioteki CUDA i model Whisper) |
| GPU (opcjonalnie) | karta NVIDIA z aktualnym sterownikiem; bez niej transkrypcja działa na procesorze, kilkukrotnie wolniej |
| Tłumaczenie i korekta | jeden z tłumaczy opisanych w sekcji [Konfiguracja tłumacza](#konfiguracja-tłumacza); sama transkrypcja go nie wymaga |

## Instalacja

Pakiety instalacyjne są dostępne w sekcji [Releases](https://github.com/maclask/subtitle-generator/releases/latest):

| System | Interfejs graficzny i wiersz poleceń | Tylko wiersz poleceń |
|---|---|---|
| Windows | `subtitle-generator-<wersja>-windows.zip` | `subtitle-generator-cli-<wersja>-windows.zip` |
| macOS | `subtitle-generator-<wersja>-macos.zip` | `subtitle-generator-cli-<wersja>-macos.zip` |
| Linux | `subtitle-generator-<wersja>-linux.tar.gz` | `subtitle-generator-cli-<wersja>-linux.tar.gz` |

Pakiet „tylko wiersz poleceń” nie wymaga biblioteki tkinter i jest przeznaczony do systemów bez środowiska graficznego, np. serwerów.

### Windows

1. Zainstaluj Python 3.13 z [python.org](https://www.python.org/downloads/), pozostawiając zaznaczoną opcję **py launcher**.
2. Rozpakuj pakiet lub sklonuj repozytorium: `git clone https://github.com/maclask/subtitle-generator`.
3. Uruchom **`setup.bat`**. Skrypt tworzy środowisko wirtualne w katalogu `.venv` i instaluje zależności.
4. Uruchom program skrótem **Subtitle Generator** (w katalogu programu i w menu Start) lub plikiem `generator.bat`. Wersja dla wiersza poleceń: `generator-cli.bat`.

### macOS

1. Zainstaluj Python 3.13 z [python.org](https://www.python.org/downloads/) (zawiera tkinter) lub przez Homebrew: `brew install python@3.13 python-tk@3.13`.
2. Rozpakuj pakiet lub sklonuj repozytorium.
3. W katalogu programu wykonaj:
   ```sh
   sh setup.sh
   ```
4. Uruchom **Subtitle Generator.app** (utworzoną w katalogu programu) lub `./generator.sh`.

> Przy pierwszym uruchomieniu macOS może zablokować aplikację. Aby ją otworzyć, wybierz **Otwórz** z menu kontekstowego aplikacji i potwierdź.

### Linux

1. Zainstaluj Python z modułami tkinter i venv:
   ```sh
   sudo apt install python3 python3-tk python3-venv   # Debian / Ubuntu
   sudo dnf install python3 python3-tkinter          # Fedora
   ```
2. Rozpakuj pakiet (`tar xzf subtitle-generator-*-linux.tar.gz`) lub sklonuj repozytorium.
3. W katalogu programu wykonaj:
   ```sh
   sh setup.sh
   ```
4. Uruchom **Subtitle Generator** z menu aplikacji lub poleceniem `./generator.sh`.

### Modele Whisper

Model rozpoznawania mowy pobiera się z poziomu programu, w sekcji **Rozpoznawanie mowy**:

| Model | Rozmiar | Charakterystyka |
|---|---|---|
| `large-v3-turbo` | 1,6 GB | szybki, dokładność zbliżona do `large-v3` (zalecany) |
| `large-v3` | 3,1 GB | najwyższa dokładność |
| `medium` | 1,5 GB | niższa dokładność |

Pobieranie można przerwać. Do czasu pobrania modelu pliki wideo i audio są pomijane, a tłumaczenie istniejących plików napisów pozostaje dostępne. Wersja dla wiersza poleceń przed pobraniem brakującego modelu (domyślnie `large-v3`) prosi o potwierdzenie; w skryptach pobranie bez pytania umożliwia opcja `--download-model`. Bez modelu pliki wideo i audio są pomijane.

## Konfiguracja tłumacza

| Tłumacz | Konfiguracja |
|---|---|
| **Claude CLI** (domyślny) | Zainstaluj [Claude Code](https://claude.com/claude-code), uruchom `claude` i zaloguj się poleceniem `/login`. Klucz API nie jest wymagany. Program wyszukuje `claude` w zmiennej PATH oraz w aplikacji desktopowej Claude. |
| **Claude API** | Klucz [Anthropic](https://console.anthropic.com/) lub zmienna `ANTHROPIC_API_KEY`. |
| **Codex CLI** | `npm install -g @openai/codex`, następnie `codex login` (konto ChatGPT). Codex działa jako agent z dostępem do odczytu plików lokalnych; do przetwarzania napisów z niezaufanych źródeł zalecany jest inny tłumacz. |
| **OpenAI API** | Klucz [OpenAI](https://platform.openai.com/api-keys) lub zmienna `OPENAI_API_KEY` oraz nazwa modelu. |
| **Ollama** | Zainstaluj [Ollamę](https://ollama.com) i pobierz model, np. `ollama pull qwen3`. Zainstalowane modele są wyświetlane na liście. Działa bez dostępu do internetu; wydajność zależy od ilości pamięci GPU. |
| **Własne API** | Dowolny serwer zgodny z API OpenAI: adres, model i opcjonalny klucz (`CUSTOM_API_KEY`), np. `https://openrouter.ai/api/v1` lub LM Studio `http://localhost:1234/v1`. |
| **DeepL** | Klucz [DeepL API](https://www.deepl.com/pro-api) (również w planie Free) lub zmienna `DEEPL_API_KEY`. Obsługuje wyłącznie języki dostępne w DeepL i nie wykonuje korekty transkrypcji. |

Klucze API wprowadzone w programie są przechowywane w systemowym magazynie poświadczeń: Menedżerze poświadczeń (Windows), Pęku kluczy (macOS) lub Secret Service — GNOME Keyring albo KWallet (Linux). Nie są zapisywane w plikach programu.

## Użycie

### Interfejs graficzny

Język interfejsu odpowiada językowi systemu (polski lub angielski; dla pozostałych języków — angielski). Przełącznik **PL / EN** zmienia język, a wybór jest zapamiętywany.

1. **Pliki** — dodaj nagrania wideo lub audio albo istniejące napisy `.srt`, `.vtt` lub `.ass` (tylko tłumaczenie, bez transkrypcji; język napisów należy wtedy wskazać w polu **Język mowy**). Pliki można przeciągnąć do okna; przeciągnięcie katalogu dodaje wszystkie obsługiwane pliki.
2. **Rozpoznawanie mowy** — wybierz język mowy (domyślnie wykrywany automatycznie) i model. Jeśli wybrany język wyraźnie nie odpowiada nagraniu, użyty zostaje język wykryty, a w logu pojawia się ostrzeżenie.
   Opcja **Popraw tekst przez LLM** włącza korektę transkrypcji: po rozpoznaniu mowy tłumacz wybrany w sekcji **Tłumaczenie** koryguje błędnie rozpoznane słowa, nazwy własne i interpunkcję, korzystając z pola **Kontekst**. Czasy napisów pozostają bez zmian, a tłumaczenia powstają z poprawionego tekstu. Poprawki odbiegające znacząco od oryginału są odrzucane; w razie błędu zapisywany jest tekst z rozpoznawania mowy.
3. **Format napisów** — typ pliku, maksymalna liczba znaków w linii i liczba linii w napisie.
4. **Tłumaczenie** — wybierz tłumacza i języki docelowe. Języki spoza listy można wpisać w polu **Inne języki** (tylko tłumacze LLM). W polu **Kontekst** można podać temat, nazwy własne, słownik terminów lub reguły, np. *nie tłumacz nazwy marki*.
5. Kliknij **Generuj napisy**. Przebieg pracy dla każdego pliku jest widoczny w kolumnie **Log**; przycisk **Otwórz folder** wskazuje zapisane pliki.

### Wiersz poleceń

```sh
generator-cli.bat film.mp4 -l pl -t en,de          # Windows
./generator-cli.sh film.mp4 -l pl -t en,de         # macOS / Linux
```

| Opcja | Opis |
|---|---|
| `-l pl` | język mowy lub napisów (kod albo nazwa); domyślnie wykrywany automatycznie, dla plików napisów wymagany |
| `-t en,de,kataloński` | języki docelowe; języki spoza `--list-languages` są obsługiwane przez wszystkich tłumaczy oprócz DeepL |
| `-e cli\|api\|codex\|openai\|ollama\|custom\|deepl` | tłumacz (domyślnie ostatnio użyty w interfejsie graficznym, w przeciwnym razie `cli`) |
| `--llm-model`, `--llm-url` | model dla `api`, `openai`, `ollama`, `custom`; adres serwera dla `ollama`, `custom` |
| `-m large-v3-turbo` | model Whisper: `large-v3` (domyślnie), `large-v3-turbo`, `medium` |
| `--download-model` | pobranie brakującego modelu Whisper bez pytania (np. w skryptach) |
| `--correct` | korekta transkrypcji tłumaczem wskazanym w `-e` (z wyjątkiem DeepL) |
| `-c "…"` | kontekst dla korekty i tłumaczenia |
| `-f vtt` | format pliku: `srt` (domyślnie), `vtt`, `ass`, `txt` |
| `--chars 42 --lines 2` | maksymalna liczba znaków w linii i linii w napisie |
| `-o katalog` | katalog wyjściowy (domyślnie katalog pliku źródłowego) |
| `--overwrite` | nadpisywanie istniejących plików (domyślnie zapisywana jest kopia, np. `film.en (2).srt`) |
| `--ui-lang pl` | język komunikatów: `pl` lub `en` (domyślnie język wybrany w interfejsie graficznym, a w jego braku język systemu) |

### Zalecany proces redakcji

1. Wygeneruj napisy w języku mowy.
2. Zaimportuj je do programu do montażu (np. w Premiere Pro: **File → Import**) i wprowadź poprawki.
3. Wyeksportuj poprawione napisy do pliku SRT.
4. Dodaj poprawiony plik do generatora, wskaż jego język i przetłumacz go — tłumaczenia powstaną z zatwierdzonego tekstu.

## Pliki wynikowe

Pliki są zapisywane w katalogu pliku źródłowego jako `nazwa.<kod języka>.<rozszerzenie>`, np. `film.pl.srt`, `film.en.srt`.

| Format | Rozszerzenie | Zastosowanie |
|---|---|---|
| SRT | `.srt` | format uniwersalny: programy do montażu, platformy wideo, odtwarzacze |
| WebVTT | `.vtt` | odtwarzacze HTML5 i serwisy internetowe |
| ASS | `.ass` | Aegisub, VLC, mpv; zawiera styl (biały tekst z obrysem) |
| TXT | `.txt` | sama treść, bez kodów czasowych |

**Kodowanie.** Pliki są zapisywane w UTF-8 bez znacznika BOM. Znaki końca linii odpowiadają konwencji systemu (CRLF w Windows, LF w macOS i Linuksie). Kodowanie wyjściowe nie jest konfigurowalne; jeśli urządzenie docelowe wymaga kodowania jednobajtowego, np. Windows-1250, plik należy przekonwertować zewnętrznym narzędziem (np. Subtitle Edit). Pliki wejściowe mogą być zapisane w UTF-8, UTF-16 (ze znacznikiem BOM) lub Windows-1250.

## Rozwiązywanie problemów

| Komunikat lub objaw | Rozwiązanie |
|---|---|
| *GPU nie zadziałało… przełączam na CPU* | Zaktualizuj sterownik NVIDIA. Transkrypcja jest kontynuowana na procesorze. |
| *Claude CLI: Failed to authenticate* | Uruchom `claude` w terminalu i zaloguj się poleceniem `/login`. |
| Wolne tłumaczenie przez Ollamę | Wybierz mniejszy model, mieszczący się w pamięci GPU (np. 7–14 mld parametrów). |
| *Brak systemowego magazynu haseł* (Linux) | Zainstaluj i odblokuj GNOME Keyring lub KWallet albo ustaw zmienne `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CUSTOM_API_KEY` lub `DEEPL_API_KEY`. |
| Skrypt `setup` nie znajduje Pythona | Zainstaluj Python w wersji 3.10–3.13; nowsze wersje mogą nie być obsługiwane przez wszystkie zależności. |

Ustawienia programu (bez kluczy API) są zapisywane w pliku `config.json` w katalogu programu.

## Licencja

[GPL-3.0](LICENSE)
