Dokumentacja projektu: Aplikacja do analizy fundamentalnej dla tradingu na ES Futures
1. Wprowadzenie
Aplikacja stanowi narzędzie wspomagające podejmowanie decyzji tradingowych na kontraktach terminowych ES (E-mini S&P 500) poprzez dostarczenie kompleksowego obrazu sytuacji makroekonomicznej oraz sentymentu rynkowego. Umożliwia szybki dostęp do kluczowych wskaźników, kalendarza publikacji, porównywanie komunikatów FOMC oraz śledzenie głównych klas aktywów.

Aplikacja będzie działać jako lokalny serwer webowy z interfejsem graficznym opartym o Dash (Python), co pozwala na tworzenie interaktywnych dashboardów bez konieczności budowania tradycyjnego GUI. Dane będą przechowywane lokalnie w bazie SQLite, a aktualizowane poprzez scraping i zewnętrzne API.

2. Wymagania funkcjonalne
2.1. Pozyskiwanie danych
Scrapowanie Forex Factory

Pobieranie kalendarza ekonomicznego dla bieżącego i nadchodzących dni.

Wyciąganie konkretnych wskaźników: CPI (r/r, m/m), PPI, Payrolls, Unemployment, GDP, Core Retail Sales, Core PCE, ISM Manufacturing, ISM Services.

Dla każdego wskaźnika: data publikacji, oczekiwana wartość (forecast), faktyczna wartość (actual), poprzednia wartość (previous).

Możliwość pobierania danych historycznych dla wybranego przedziału.

Pobieranie danych z yfinance

Symbole: ^TNX (US10Y), DX-Y.NYB (DXY), BTC-USD, GC=F (Gold), CL=F (WTI Oil), ES=F (ES Futures – kontrakt ciągły).

Zakres danych: ostatnie 30 dni (lub konfigurowalny).

Metryki: cena zamknięcia, zmiana %, wolumen.

Scrapowanie komunikatów FOMC

Pobieranie listy dostępnych oświadczeń (statements) z oficjalnej strony Fed (lub archiwum).

Zapisywanie pełnego tekstu każdego oświadczenia wraz z datą wydania.

Automatyczne uzupełnianie brakujących wpisów przy każdym uruchomieniu.

Storage danych

Wszystkie pozyskane dane zapisywane w lokalnej bazie danych SQLite.

Struktura tabel dostosowana do rodzaju danych (kalendarz, wskaźniki, ceny, oświadczenia).

Mechanizm aktualizacji przyrostowej (nie pobieramy ponownie tych samych danych).

2.2. Elementy wizualne (Dashboard)
Porównanie statementów FOMC

Lista rozwijana umożliwiająca wybór dwóch oświadczeń z bazy.

Po wybraniu, wyświetlony zostaje tekst różnicowy:

treść usunięta w nowszym oświadczeniu → przekreślona (czerwona?)

treść dodana → podświetlona na zielono.

Wykorzystanie algorytmu difflib (SequenceMatcher) do generowania diff w formacie HTML.

Dane makro

Tabela prezentująca ostatnie opublikowane wartości dla wymienionych wskaźników (CPI, PPI, itd.).

Kolumny: wskaźnik, data publikacji, actual, forecast, previous.

Możliwość odświeżenia danych na żądanie (przycisk "Odśwież").

Opcjonalnie: wykresy zmian w czasie dla wybranego wskaźnika.

Porównanie rynków

Interaktywny wykres liniowy (Plotly) przedstawiający zmiany cen wybranych aktywów w czasie.

Suwak zakresu czasowego (ostatnie 7, 14, 30 dni).

Opcja normalizacji (start = 100%), aby łatwo porównać względne zmiany.

Aktualne wartości (% zmiany) wyświetlane jako karty nad wykresem.

Kalendarz ekonomiczny

Widok tabelaryczny podobny do Forex Factory, ale filtrowany tylko pod kątem interesujących wskaźników (wymienionych w pkt 2).

Kolumny: data/godzina, waluta (USD), wskaźnik, ważność (gwiazdki), actual, forecast, previous.

Kolorowanie komórek w zależności od relacji actual vs forecast (np. zielony gdy lepszy niż oczekiwany).

Możliwość wyboru zakresu dat (np. bieżący tydzień, następny tydzień).

3. Wymagania niefunkcjonalne
Język: Python 3.9+

System operacyjny: Windows / macOS / Linux (testowane na jednym, zakładamy kompatybilność)

Wydajność: Aplikacja powinna uruchamiać się w ciągu kilku sekund; operacje scrapowania mogą trwać dłużej (do 30s) – wykonywane asynchronicznie (np. w tle) lub z komunikatem postępu.

Niezawodność: Obsługa błędów sieciowych, brakujących danych, zmian w strukturze scrapowanych stron – logowanie błędów.

Bezpieczeństwo: Aplikacja działa lokalnie, nie przesyła danych poza sieć (poza zapytaniami do zewnętrznych API).

Łatwość instalacji: requirements.txt i instrukcja uruchomienia.

Konfigurowalność: Plik config.yaml z ustawieniami (ścieżki, interwały odświeżania, symbole, itp.).

4. Architektura systemu
4.1. Przegląd komponentów
text
├── app/
│   ├── __init__.py
│   ├── dashboard.py          # Główny serwer Dash i układ stron
│   ├── callbacks.py          # Logika interakcji (callbacki Dash)
│   ├── layout.py             # Elementy UI (html, dcc)
│   └── assets/               # Pliki CSS, obrazy
├── data/
│   ├── database.py           # Klasa zarządzająca połączeniem z SQLite
│   ├── models.py             # Definicje tabel (SQLAlchemy lub raw SQL)
│   └── db_init.py            # Skrypty tworzące tabele
├── scrapers/
│   ├── forex_factory.py      # Scraper kalendarza FF
│   ├── fomc.py               # Scraper oświadczeń FOMC
│   └── base.py               # Wspólne narzędzia (np. obsługa User-Agent)
├── fetchers/
│   ├── yfinance_fetcher.py   # Pobieranie danych z yfinance
│   └── fred_fetcher.py       # (opcjonalnie) dane z FRED
├── utils/
│   ├── diff_utils.py         # Narzędzia do porównywania tekstów
│   └── helpers.py            # Formatowanie dat, walidacja, itp.
├── config.yaml               # Plik konfiguracyjny
├── requirements.txt
└── run.py                    # Punkt wejściowy
4.2. Przepływ danych
Uruchomienie – aplikacja inicjalizuje połączenie z bazą, odczytuje konfigurację.

Pierwsze ładowanie dashboardu – dane są pobierane z bazy; jeśli brakuje danych dla bieżącego dnia, uruchamiane są scrapery (w tle lub synchronicznie z informacją o postępie).

Interakcja użytkownika – wybór zakresów, przycisk odświeżenia wywołują odpowiednie callbacki, które mogą ponownie pobrać dane (jeśli nieaktualne) i zaktualizować komponenty.

Scrapowanie – realizowane przez dedykowane moduły, które:

Dla FF: pobierają kalendarz za pomocą Selenium (lub requests + emulacja XHR), parsują, zapisują do bazy.

Dla FOMC: pobierają listę linków do oświadczeń, następnie treść każdego, zapisują z datą.

Aktualizacja danych rynkowych – co określony interwał (np. co 5 minut) lub na żądanie użytkownika.

4.3. Wybór technologii – uzasadnienie
Komponent	Wybór	Uzasadnienie
GUI	Dash + Plotly	Szybkie tworzenie interaktywnych wykresów, łatwość obsługi callbacków, działa w przeglądarce (lokalny serwer), nie wymaga zewnętrznych zależności GUI.
Baza danych	SQLite	Lekka, nie wymaga instalacji, idealna do lokalnych danych, wspiera zapytania SQL, dobrze współpracuje z Pandas.
Scrapowanie FF	Selenium (lub requests + XHR)	Strona FF jest dynamiczna (JavaScript); Selenium daje pełną kontrolę, ale może być wolne. W przyszłości można przejść na bezpośrednie wywoływanie API (analiza ruchu sieciowego).
Scrapowanie FOMC	BeautifulSoup4 + requests	Strona Fed jest statyczna, więc wystarczy parsowanie HTML.
Dane rynkowe	yfinance	Łatwe API, darmowe, obejmuje wszystkie potrzebne instrumenty.
Porównywanie tekstów	difflib (biblioteka standardowa)	Proste i skuteczne do generowania diff w formacie HTML.
Konfiguracja	PyYAML	Czytelny format, łatwa edycja.
Logowanie	logging (standard)	Proste logowanie do pliku i konsoli.
5. Szczegółowy opis komponentów
5.1. Moduł database.py
Klasa Database z metodami:

connect() – tworzy połączenie.

execute(query, params) – wykonuje zapytanie.

fetch_all(query, params) – zwraca listę słowników.

insert(table, data) – wstawia dane (lub aktualizuje na konflikt).

upsert(table, data, conflict_columns) – logika upsert (używamy INSERT OR REPLACE lub ON CONFLICT).

Tabele:

forex_calendar – pola: id, date, time, currency, event_name, importance, actual, forecast, previous, unit, created_at.

fomc_statements – id, date, title, content, url, created_at.

market_prices – id, symbol, date, open, high, low, close, volume, created_at.

macro_indicators – (opcjonalnie) agregowane wskaźniki; możemy je jednak generować na żywo z forex_calendar.

Indeksy dla przyspieszenia wyszukiwania (np. po dacie, symbolu).

5.2. Scraper Forex Factory (scrapers/forex_factory.py)
Klasa ForexFactoryScraper:

get_calendar(start_date, end_date) – główna metoda.

Używa Selenium WebDriver (Chrome/Firefox) do otwarcia strony kalendarza.

Zmiana zakresu dat poprzez kliknięcie w przyciski nawigacyjne.

Parsowanie tabeli za pomocą BeautifulSoup (lub Selenium find_elements).

Mapowanie nagłówków na nazwy zdarzeń (np. "CPI" → "CPI m/m").

Filtracja tylko interesujących wskaźników (zdefiniowanych w konfiguracji).

Zwraca listę słowników.

Alternatywnie – jeśli uda się znaleźć bezpośrednie API:

Wykorzystać requests i analizować odpowiedzi JSON (np. endpoint https://www.forexfactory.com/calendar/ z parametrami).

Wymaga to śledzenia ruchu sieciowego.

Obsługa błędów: jeśli strona nie odpowiada, próba ponowna z wykładniczym opóźnieniem; logowanie.

5.3. Scraper FOMC (scrapers/fomc.py)
Klasa FOMCScraper:

get_statements_list() – pobiera listę linków do oświadczeń z archiwum (np. https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm).

fetch_statement(url) – pobiera treść oświadczenia (odpowiedni div z tekstem).

update_statements() – porównuje z bazą i dodaje nowe.

Uwaga: struktura strony może się zmieniać – warto użyć elastycznych selektorów CSS.

5.4. Fetcher yfinance (fetchers/yfinance_fetcher.py)
Klasa YFinanceFetcher:

fetch_prices(symbols, start, end) – pobiera dane dzienne dla listy symboli.

Korzysta z yfinance.download().

Zwraca DataFrame, który jest zapisywany do bazy (upsert).

Dla kontraktów futures (ES) – yfinance obsługuje symbole z przyrostkiem =F (np. ES=F), ale trzeba uważać na ciągłość. Można też użyć kontraktu głównego.

Dodatkowo: obliczanie dziennej zmiany procentowej.

5.5. Moduł diff (utils/diff_utils.py)
Funkcja generate_diff_html(old_text, new_text):

Używa difflib.SequenceMatcher do znalezienia różnic.

Zwraca string HTML z <del> i <ins> lub odpowiednie style (przekreślenie, zielone tło).

5.6. Dashboard (app/dashboard.py)
Tworzy instancję dash.Dash.

Definiuje layout (podzielony na zakładki lub widżety).

Callbacki:

Aktualizacja listy statementów.

Wywołanie diff po wyborze dwóch.

Pobieranie danych makro z bazy i wyświetlanie w tabeli.

Generowanie wykresu porównania rynków.

Wyświetlanie kalendarza z filtrem.

Używa komponentów:

dcc.Dropdown – wybór statementów.

dcc.Graph – wykresy.

dcc.Store – przechowywanie danych pośrednich.

html.Table / dash_table.DataTable – tabele.

dcc.Interval – (opcjonalnie) automatyczne odświeżanie co minutę.

5.7. Konfiguracja (config.yaml)
Przykładowa zawartość:

yaml
database:
  path: "data/analytics.db"

forexfactory:
  url: "https://www.forexfactory.com/calendar"
  events:
    - "CPI"
    - "CPI m/m"
    - "PPI m/m"
    - "Non-Farm Employment Change"
    - "Unemployment Rate"
    - "GDP"
    - "Core Retail Sales"
    - "Core PCE Price Index m/m"
    - "ISM Manufacturing PMI"
    - "ISM Services PMI"

fomc:
  url: "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
  statement_selector: "div.col-xs-12 col-sm-8 col-md-8" # przykład

markets:
  symbols:
    - "^TNX"
    - "DX-Y.NYB"
    - "BTC-USD"
    - "GC=F"
    - "CL=F"
    - "ES=F"
  range_days: 30

logging:
  level: "INFO"
  file: "app.log"
6. Plan implementacji (kroki)
6.1. Przygotowanie środowiska
Utworzenie wirtualnego środowiska (venv).

Instalacja zależności: dash, plotly, pandas, yfinance, requests, beautifulsoup4, selenium, webdriver-manager, pyyaml, pytest (testy).

6.2. Baza danych
Zdefiniowanie schematu SQLite (skrypt db_init.py).

Testowe wstawienie danych.

6.3. Moduły scrapujące
Napisanie forex_factory.py – przetestowanie na żywo (pobranie kilku dni).

Napisanie fomc.py – pobranie listy i treści.

6.4. Fetcher yfinance
Pobranie danych i zapis do bazy.

6.5. Narzędzia pomocnicze
diff_utils – testy na przykładowych tekstach.

6.6. Dashboard
Stworzenie prostego layoutu z jedną funkcjonalnością (np. kalendarz).

Stopniowe dodawanie pozostałych elementów.

Integracja z bazą i scraperami (callbacki).

6.7. Testy
Testy jednostkowe dla każdego modułu (mockowanie zewnętrznych API).

Testy integracyjne (uruchomienie całej aplikacji).

6.8. Dokumentacja użytkownika
Instrukcja uruchomienia, opis interfejsu.

6.9. Pakowanie i dystrybucja (opcjonalnie)
Możliwość stworzenia pliku wykonywalnego (PyInstaller) lub dockeryzacji.

7. Zagadnienia techniczne do rozwagi
7.1. Scrapowanie Forex Factory – ryzyko blokady
Użycie odpowiednich nagłówków (User-Agent, Referer).

Dodanie opóźnień między żądaniami.

W przypadku Selenium – ukrycie automatyzacji (np. options.add_argument("--disable-blink-features=AutomationControlled")).

7.2. Aktualizacja danych w tle
Aby nie blokować interfejsu, można użyć wątków (threading) lub zadań asynchronicznych (Dash nie wspiera bezpośrednio asynchronicznych callbacków, ale można użyć dash-extensions lub uruchomić scraper w oddzielnym procesie i odświeżyć dane przez dcc.Store).

7.3. Czasowa różnica stref
Dane z Forex Factory są w strefie czasowej (np. EST). Należy je konwertować na lokalną lub UTC dla spójności.

7.4. Porównywanie statementów – dokładność
Różnice mogą być subtelne (zmiany pojedynczych słów). difflib radzi sobie dobrze.

Formatowanie HTML z kolorami zostanie wstrzyknięte do komponentu html.Div z dangerously_allow_html=True.

7.5. Skalowalność
Baza SQLite jest wystarczająca dla danych osobowych; jeśli liczba rekordów przekroczy kilkadziesiąt tysięcy, można rozważyć PostgreSQL, ale to nie jest przewidywane.

8. Bezpieczeństwo i prywatność
Aplikacja nie zbiera danych osobowych użytkownika.

Wszystkie dane przechowywane lokalnie.

API klucze (np. do FRED) nie są używane na razie; jeśli zostaną dodane, będą przechowywane w zmiennych środowiskowych, a nie w config.yaml.

9. Testowanie
Testy jednostkowe – dla każdego modułu (np. mockowanie requests i yfinance).

Testy integracyjne – uruchomienie aplikacji i symulacja kliknięć (np. za pomocą dash.testing).

Testy wydajnościowe – pomiar czasu scrapowania i aktualizacji.

10. Dalszy rozwój (potencjalne rozszerzenia)
Dodanie powiadomień push/email o nadchodzących publikacjach.

Integracja z danymi z FRED (np. inflacja, stopy procentowe).

Możliwość eksportu danych do CSV/Excel.

Dodanie analizy sentymentu na podstawie statementów FOMC (np. liczba słów "inflation", "growth").

Wsparcie dla innych rynków (np. europejskie indeksy).

11. Podsumowanie
Proponowane rozwiązanie spełnia wszystkie wymagania, wykorzystując sprawdzone biblioteki Pythona. Centralnym punktem jest interaktywny dashboard Dash, który zapewnia przyjazny interfejs bez konieczności tworzenia osobnego GUI. Modułowa architektura ułatwia testowanie i ewentualną rozbudowę. Scrapowanie danych odbywa się w sposób elastyczny, z możliwością przejścia na bardziej stabilne API w przyszłości. Baza SQLite gwarantuje szybki dostęp do danych historycznych. Aplikacja jest w pełni lokalna, co zwiększa prywatność i niezależność od zewnętrznych usług.

Dokumentacja została przygotowana na podstawie analizy wymagań i najlepszych praktyk inżynierii oprogramowania. Wszelkie uwagi i zmiany mogą być wprowadzane w trakcie implementacji.

---

## 12. Stan implementacji (2026-06-30)

### Utworzona struktura katalogów i plików

```
├── app/
│   ├── __init__.py
│   ├── assets/
│   │   └── style.css              # Podstawowe style CSS
│   ├── dashboard.py               # Główny serwer Dash (create_app, run_server)
│   ├── callbacks.py               # Logika callbacków Dash
│   └── layout.py                  # Komponenty UI (tabele, wykresy, dropdowny)
├── data/
│   ├── __init__.py
│   ├── database.py                # Klasa Database (connect, execute, insert, upsert)
│   ├── models.py                  # Definicje tabel i indeksów SQLite
│   └── db_init.py                 # Inicjalizacja bazy danych
├── scrapers/
│   ├── __init__.py
│   ├── base.py                    # Wspólne narzędzia (User-Agent, retry, fetch_page)
│   ├── forex_factory.py           # Klasa ForexFactoryScraper (szkielet)
│   └── fomc.py                    # Klasa FOMCScraper (lista + treść statementów)
├── fetchers/
│   ├── __init__.py
│   └── yfinance_fetcher.py        # Klasa YFinanceFetcher (pobieranie OHLCV)
├── utils/
│   ├── __init__.py
│   ├── diff_utils.py              # Funkcja generate_diff_html (difflib)
│   └── helpers.py                 # Parsowanie dat, safe_float itp.
├── config.yaml                    # Plik konfiguracyjny
├── requirements.txt               # Zależności Pythona
└── run.py                         # Punkt wejściowy (argparse + logging)
```

### Zaimplementowane klasy i funkcje

| Moduł | Klasa / funkcja | Opis |
|-------|----------------|------|
| `data/database.py` | `Database` | Zarządzanie połączeniem SQLite: `connect()`, `close()`, `execute()`, `fetch_all()`, `fetch_one()`, `insert()`, `upsert()` |
| `data/models.py` | (stałe) | Definicje tabel: `forex_calendar`, `fomc_statements`, `market_prices` wraz z indeksami |
| `data/db_init.py` | `init_db()` | Tworzy wszystkie tabele i indeksy, zwraca instancję `Database` |
| `scrapers/base.py` | `fetch_page()`, `retry()` | Pobieranie stron z User-Agent, dekorator z ponawianiem i backoffem |
| `scrapers/forex_factory.py` | `ForexFactoryScraper` | Szkielet scrapowania kalendarza FF (`get_calendar()`, `_parse()`, `_filter_events()`) |
| `scrapers/fomc.py` | `FOMCScraper` | Pobieranie listy statementów (`get_statements_list()`) i treści (`fetch_statement()`, `update_statements()`) |
| `fetchers/yfinance_fetcher.py` | `YFinanceFetcher` | Pobieranie dziennych OHLCV dla listy symboli (`fetch_prices()`), obliczanie `change_pct` |
| `utils/diff_utils.py` | `generate_diff_html()` | Porównywanie tekstów, zwraca HTML z `<del>` (czerwony) i `<ins>` (zielony) |
| `utils/helpers.py` | `parse_date()`, `format_date()`, `safe_float()` itp. | Pomocnicze funkcje do dat i konwersji |
| `app/dashboard.py` | `create_app()`, `run_server()` | Inicjalizacja Dash, wczytanie configu, rejestracja callbacków |
| `app/layout.py` | `layout`, `TAB_LAYOUTS` | Layout z zakładkami: Kalendarz, Makro, Rynki, FOMC Diff |
| `app/callbacks.py` | `register_callbacks()` | Callbacki do przełączania zakładek, odświeżania danych, rysowania wykresów i diffa FOMC |
| `run.py` | `main()` | Punkt wejściowy z parsingiem argumentów CLI i konfiguracją logowania |

### Uwagi

- **ForexFactoryScraper._parse()** jest szkieletem – wymaga implementacji z Selenium/BeautifulSoup do prawdziwego scrapowania dynamicznej strony.
- Przed uruchomieniem należy zainstalować zależności: `pip install -r requirements.txt`.
- Aplikację uruchamia się komendą: `python run.py` (domyślnie na porcie 8050).