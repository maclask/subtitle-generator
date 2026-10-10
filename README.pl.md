# Generator napisów (Subtitle Generator)

[English](README.md) · **Polski**

Zamienia wideo lub audio na gotowe napisy (`.srt`, `.vtt`, `.ass` albo sam tekst `.txt`) i tłumaczy je na inne języki.
Pliki działają w Premiere Pro, DaVinci Resolve, Final Cut Pro, na YouTube i wszędzie, gdzie można wczytać SRT.

- **Rozpoznawanie mowy:** Whisper large-v3 ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)), uruchamiany lokalnie. Na Windows i Linuksie korzysta z karty NVIDIA (CUDA), na macOS z procesora.
- **Podział na napisy:** tekst dzielony jest na granicach zdań i wtrąceń, z wyrównanymi liniami i minimalnym czasem wyświetlania.
- **Tłumaczenie:** do wyboru Claude (CLI lub API), Codex CLI, OpenAI, lokalny model przez Ollamę, dowolne API zgodne z OpenAI (OpenRouter, LM Studio, Mistral…) albo DeepL. Czasy wszystkich napisów zostają bez zmian.
- **GUI i wersja konsolowa** na Windows, macOS i Linuksie. Interfejs jest po polsku i po angielsku.

## Wymagania

| Wymaganie | Szczegóły |
|---|---|
| Python | 3.10 – 3.13 ([python.org](https://www.python.org/downloads/)) |
| Dysk | ok. 6 GB (biblioteki CUDA i model Whisper) |
| GPU (opcjonalnie) | NVIDIA z aktualnym sterownikiem. Bez karty program używa procesora, co jest kilka razy wolniejsze. |
| Tłumaczenie | jeden z tłumaczy opisanych niżej. Sama transkrypcja go nie wymaga. |

## Instalacja

Pobierz paczkę dla swojego systemu z [Releases](https://github.com/maclask/subtitle-generator/releases/latest):

| | GUI + konsola | Tylko konsola |
|---|---|---|
| Windows | `subtitle-generator-<wersja>-windows.zip` | `subtitle-generator-cli-<wersja>-windows.zip` |
| macOS | `subtitle-generator-<wersja>-macos.zip` | `subtitle-generator-cli-<wersja>-macos.zip` |
| Linux | `subtitle-generator-<wersja>-linux.tar.gz` | `subtitle-generator-cli-<wersja>-linux.tar.gz` |

Paczka konsolowa nie wymaga tkintera, więc dobrze sprawdza się na serwerach.

### Windows

1. Zainstaluj Pythona 3.13 z [python.org](https://www.python.org/downloads/). W instalatorze zostaw zaznaczoną opcję **py launcher**.
2. Rozpakuj paczkę dla Windows albo uruchom `git clone https://github.com/maclask/subtitle-generator`.
3. Kliknij dwukrotnie **`setup.bat`**. Skrypt tworzy lokalne środowisko w `.venv` i instaluje zależności. Trwa to kilka minut.
4. Uruchamiaj program skrótem **Subtitle Generator** (setup tworzy go w folderze programu i w menu Start) albo przez `generator.bat`. Wersja konsolowa: `generator-cli.bat`.

### macOS

1. Zainstaluj Pythona 3.13 z [python.org](https://www.python.org/downloads/); ta wersja ma wbudowany tkinter. Z Homebrew zamiast tego uruchom `brew install python@3.13 python-tk@3.13`.
2. Rozpakuj paczkę dla macOS albo sklonuj repozytorium.
3. W Terminalu, w folderze programu, uruchom:
   ```sh
   sh setup.sh
   ```
4. Uruchamiaj **Subtitle Generator.app** (setup tworzy ją w folderze programu; możesz ją przeciągnąć do Docka lub Programów) albo poleceniem `./generator.sh`.

> Jeśli macOS za pierwszym razem zablokuje aplikację, kliknij ją prawym przyciskiem, wybierz **Otwórz** i potwierdź.

### Linux

1. Zainstaluj Pythona z tkinterem i venv:
   ```sh
   sudo apt install python3 python3-tk python3-venv   # Debian / Ubuntu
   sudo dnf install python3 python3-tkinter          # Fedora
   ```
2. Rozpakuj paczkę dla Linuksa (`tar xzf subtitle-generator-*-linux.tar.gz`) albo sklonuj repozytorium.
3. W folderze programu uruchom:
   ```sh
   sh setup.sh
   ```
4. Uruchamiaj **Subtitle Generator** z menu aplikacji (skrypt instalacyjny dodaje skrót) albo poleceniem `./generator.sh`.

Model Whisper pobierasz w programie, w sekcji **Rozpoznawanie mowy**: do wyboru `large-v3-turbo` (1,6 GB, zalecany), `large-v3` (3,1 GB, najdokładniejszy) i `medium` (1,5 GB). Pobieranie można przerwać, a następne je wznowi. Dopóki żaden model nie jest pobrany, wybór modelu jest wyłączony, a pliki wideo i audio są pomijane. Tłumaczenie gotowych plików napisów działa bez modelu. Wersja konsolowa pobiera wybrany model sama przy pierwszej transkrypcji.

## Konfiguracja tłumacza

| Tłumacz | Konfiguracja |
|---|---|
| **Claude CLI** (domyślny) | Zainstaluj [Claude Code](https://claude.com/claude-code), uruchom raz `claude` i zaloguj się przez `/login`. Klucz API nie jest potrzebny. Program znajdzie `claude` w PATH albo w aplikacji desktopowej Claude. |
| **Claude API** | Wklej [klucz Anthropic](https://console.anthropic.com/) albo ustaw `ANTHROPIC_API_KEY`. |
| **Codex CLI** | `npm install -g @openai/codex`, potem `codex login`. Korzysta z konta ChatGPT. Codex to agent, który może czytać pliki na komputerze (piaskownica tylko do odczytu), więc do napisów z niezaufanych źródeł lepiej użyć innego tłumacza. |
| **OpenAI API** | Wklej [klucz OpenAI](https://platform.openai.com/api-keys) (lub ustaw `OPENAI_API_KEY`) i wpisz nazwę modelu. |
| **Ollama (lokalnie)** | Zainstaluj [Ollamę](https://ollama.com) i pobierz model, np. `ollama pull qwen3`. Zainstalowane modele pojawią się na liście. Działa offline, ale duże modele są wolne na kartach z małą ilością pamięci. |
| **Własne API** | Dowolny serwer zgodny z API OpenAI: adres, model i opcjonalny klucz (`CUSTOM_API_KEY`). Przykłady: `https://openrouter.ai/api/v1`, LM Studio `http://localhost:1234/v1`. |
| **DeepL** | Wklej [klucz DeepL](https://www.deepl.com/pro-api) (wystarczy plan Free) albo ustaw `DEEPL_API_KEY`. Obsługuje tylko języki DeepL; pozostałe przetłumaczy tłumacz LLM. |

Klucze wpisane w programie trafiają do systemowego magazynu haseł: na Windows do Menedżera poświadczeń, na macOS do Pęku kluczy, na Linuksie do Secret Service (GNOME Keyring lub KWallet). Nie trafiają do `config.json` ani nigdzie indziej w folderze programu.

## Użycie

### GUI

Program startuje w języku systemu (polski albo angielski; przy innych językach systemu — angielski). Przełącznik **PL / EN** w prawym górnym rogu zmienia język, a wybór jest zapamiętywany.

1. **Dodaj pliki**: przeciągnij je na okno albo użyj **Dodaj pliki…**. Możesz dodać wideo, audio, albo gotowe napisy `.srt` / `.vtt` / `.ass` (zostaną przetłumaczone bez transkrypcji). Przeciągnięcie folderu dodaje wszystkie obsługiwane pliki z niego. Po najechaniu na nazwę pliku widać pełną ścieżkę.
2. Wybierz **język mowy** (domyślnie wykrywany automatycznie) i **model**. `large-v3` jest najdokładniejszy, `large-v3-turbo` kilka razy szybszy. Jeśli wybrany model nie jest pobrany, pod spodem pojawi się przycisk **Pobierz**. Jeśli wybrany język wyraźnie nie pasuje do nagrania, program użyje wykrytego i napisze o tym w logu.
   **Popraw tekst przez LLM**: po rozpoznaniu mowy tłumacz wybrany w sekcji Tłumaczenie poprawia przesłyszenia, nazwy własne i interpunkcję. Pomaga mu w tym pole **Kontekst**, np. nazwiska albo nazwy sprzętu. Czasy napisów zostają bez zmian, a tłumaczenia powstają z poprawionego tekstu. Poprawka, która za bardzo odbiega od oryginału (model przepisał zdanie zamiast je poprawić), jest odrzucana. Jeśli poprawka się nie uda, zapisywany jest tekst z Whispera. Nie działa z DeepL.
3. Opcjonalnie zaznacz **języki docelowe** i wybierz tłumacza. Przy tłumaczach API lista modeli uzupełnia się z Twojego konta po wpisaniu klucza. Języki spoza listy wpisz w pole **Inne języki** (tylko tłumacze LLM).
4. W **Formacie napisów** wybierz typ pliku: **SRT** (najszerzej obsługiwany), **WebVTT** (strony WWW, odtwarzacze HTML5), **ASS** (Aegisub, VLC, mpv — ze stylem: biały tekst z obwódką) albo **TXT** (sam tekst, bez czasów — np. transkrypcja wywiadu).
5. Opcjonalnie dodaj **kontekst**: temat, nazwy własne, słownik albo regułę, np. *nie tłumacz nazwy marki*.
6. Kliknij **Generuj napisy** (w trakcie pracy przycisk zmienia się w **Zatrzymaj**). Pliki zapisują się obok źródła jako `nazwa.pl.srt`, `nazwa.en.srt` itd. (rozszerzenie zależy od wybranego typu pliku). **Otwórz folder** pokazuje wyniki. W polu **Log** widać przebieg pracy osobno dla każdego pliku: zapisane pliki (✓), ostrzeżenia (!) i błędy (✕).

### Wersja konsolowa

```sh
generator-cli.bat film.mp4 -l pl -t en,de          # Windows
./generator-cli.sh film.mp4 -l pl -t en,de         # macOS / Linux
```

| Opcja | Opis |
|---|---|
| `-l pl` | język mowy / napisów (kod lub nazwa); bez tej opcji wykrywany automatycznie |
| `-t en,de,kataloński` | języki docelowe; nazwy spoza `--list-languages` działają z każdym tłumaczem oprócz DeepL |
| `-e cli\|api\|codex\|openai\|ollama\|custom\|deepl` | tłumacz (domyślnie ostatnio użyty w GUI, inaczej `cli`) |
| `--llm-model`, `--llm-url` | model dla `api`, `openai`, `ollama`, `custom`; adres serwera dla `ollama`, `custom` |
| `-m large-v3-turbo` | model Whisper: `large-v3`, `large-v3-turbo`, `medium` |
| `-c "…"` | kontekst dla tłumacza |
| `-o folder` | folder wyjściowy (domyślnie obok pliku źródłowego) |
| `-f vtt` | typ pliku: `srt` (domyślnie), `vtt`, `ass`, `txt` |
| `--correct` | popraw transkrypcję tłumaczem LLM z `-e` (nie z DeepL) |
| `--chars 42 --lines 2` | układ napisów |
| `--overwrite` | nadpisuj istniejące pliki napisów (domyślnie zapisywana jest kopia, np. `film.en (2).srt`) |
| `--ui-lang pl` | język komunikatów (`pl` lub `en`); domyślnie język systemu, a dla innych języków niż polski — angielski |

### Zalecany obieg przy poprawianiu napisów

1. Wygeneruj napisy w języku mowy.
2. Zaimportuj `.srt` do programu do montażu i popraw je tam.
3. Wyeksportuj poprawione napisy do SRT.
4. Dodaj poprawiony `.srt` do generatora i przetłumacz go. Tłumaczenia powstaną wtedy z poprawionego tekstu.

W Premiere Pro: **File → Import**, wybierz `.srt` i przeciągnij na timeline.

### Kodowanie i końce linii

Pliki napisów zapisują się w **UTF-8** (bez BOM). Czyta je każdy współczesny program: Premiere Pro, DaVinci Resolve, Final Cut Pro, YouTube, VLC. Zmieszczą się w nim wszystkie obsługiwane języki, łącznie z chińskim, arabskim czy greckim.

Końce linii zależą od systemu: na Windows `CRLF`, na macOS i Linuksie `LF`. Wymienione programy obsługują oba warianty.

Program nie ma opcji zmiany kodowania. Jeśli jakieś stare urządzenie (np. telewizor albo odtwarzacz DVD czytający z USB) pokazuje krzaczki zamiast polskich znaków, przekonwertuj plik w Notepad++ albo Subtitle Edit (np. do Windows-1250).

Pliki wczytywane do tłumaczenia mogą być w UTF-8, UTF-16 lub Windows-1250/1252 — kodowanie jest rozpoznawane automatycznie.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| *GPU nie zadziałało… przełączam na CPU* | Zaktualizuj sterownik NVIDIA. Transkrypcja nadal działa na procesorze, tylko wolniej. |
| *Claude CLI: Failed to authenticate* | Uruchom w terminalu `claude` i zaloguj się przez `/login`. |
| Tłumaczenie przez Ollamę jest bardzo wolne | Wybierz mniejszy model, który zmieści się w pamięci karty (np. 7–14 mld parametrów). |
| *Brak systemowego magazynu haseł* (Linux) | Zainstaluj i odblokuj GNOME Keyring lub KWallet albo ustaw `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CUSTOM_API_KEY` lub `DEEPL_API_KEY`. |
| `setup` nie znajduje Pythona | Zainstaluj Pythona 3.10–3.13. Nowsze wersje mogą jeszcze nie mieć wszystkich zależności. |

Ustawienia (bez kluczy) zapisują się w `config.json` w folderze programu.

## Licencja

[GPL-3.0](LICENSE)
